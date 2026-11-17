import math
from dataclasses import replace

import pytest

from bias import (BiasInput, CircuitType, Region, ValidationError, analyze,
                  classify, compare, parse_input, solve_emitter_bias,
                  solve_fixed_bias, solve_nodal_emitter_bias,
                  solve_nodal_fixed_bias, solve_nodal_voltage_divider,
                  solve_voltage_divider)

GOLDEN_VD = BiasInput(CircuitType.VOLTAGE_DIVIDER, 12.0, 47.0, 10.0, None, 2.2, 0.47, 150.0, 0.7)
GOLDEN_FIXED = BiasInput(CircuitType.FIXED_BIAS, 12.0, None, None, 470.0, 2.2, None, 150.0, 0.7)
GOLDEN_EMITTER = BiasInput(CircuitType.EMITTER_BIAS, 12.0, None, None, 470.0, 2.2, 0.47, 150.0, 0.7)

VALID_VD = {"circuit": "voltage_divider", "vcc": "12", "r1": "47", "r2": "10",
            "rc": "2.2", "re": "0.47", "beta": "150", "vbe": "0.7"}
VALID_FIXED = {"circuit": "fixed_bias", "vcc": "12", "rb": "470",
               "rc": "2.2", "beta": "150", "vbe": "0.7"}
VALID_EMITTER = {"circuit": "emitter_bias", "vcc": "12", "rb": "470", "rc": "2.2",
                 "re": "0.47", "beta": "150", "vbe": "0.7"}


@pytest.mark.parametrize("raw,expected", [
    (VALID_VD, BiasInput(CircuitType.VOLTAGE_DIVIDER, 12.0, 47.0, 10.0, None,
                         2.2, 0.47, 150.0, 0.7)),
    (VALID_FIXED, BiasInput(CircuitType.FIXED_BIAS, 12.0, None, None, 470.0,
                            2.2, None, 150.0, 0.7)),
    (VALID_EMITTER, BiasInput(CircuitType.EMITTER_BIAS, 12.0, None, None, 470.0,
                              2.2, 0.47, 150.0, 0.7)),
])
def test_parses_each_circuit(raw, expected):
    assert parse_input(raw) == expected


def test_accepts_whitespace_sign_and_scientific_notation():
    inp = parse_input(dict(VALID_VD, vcc=" 1.2e1 ", r1="+47"))
    assert inp.vcc_v == 12.0
    assert inp.r1_kohm == 47.0


def test_accepts_beta_of_one():
    assert parse_input(dict(VALID_VD, beta="1")).beta == 1.0


def test_missing_circuit_defaults_to_voltage_divider():
    raw = {key: value for key, value in VALID_VD.items() if key != "circuit"}
    assert parse_input(raw).circuit is CircuitType.VOLTAGE_DIVIDER


def test_unknown_circuit_is_a_form_error():
    with pytest.raises(ValidationError) as info:
        parse_input(dict(VALID_VD, circuit="bogus"))
    assert "Choose a valid circuit type" in info.value.errors["circuit"]


@pytest.mark.parametrize("raw,field", [
    ({key: value for key, value in VALID_VD.items() if key != "r1"}, "r1"),
    ({key: value for key, value in VALID_FIXED.items() if key != "rb"}, "rb"),
    ({key: value for key, value in VALID_EMITTER.items() if key != "re"}, "re"),
])
def test_required_fields_per_circuit(raw, field):
    with pytest.raises(ValidationError) as info:
        parse_input(raw)
    assert field in info.value.errors


def test_ignored_fields_are_ignored():
    fixed = parse_input(dict(VALID_FIXED, r1="abc", r2="0", re="not-a-number"))
    assert fixed.circuit is CircuitType.FIXED_BIAS
    assert (fixed.r1_kohm, fixed.r2_kohm, fixed.re_kohm) == (None, None, None)
    assert fixed.rb_kohm == 470.0

    emitter = parse_input(dict(VALID_EMITTER, r1="abc"))
    assert emitter.circuit is CircuitType.EMITTER_BIAS
    assert (emitter.r1_kohm, emitter.r2_kohm) == (None, None)

    divider = parse_input(dict(VALID_VD, rb="abc"))
    assert divider.circuit is CircuitType.VOLTAGE_DIVIDER
    assert divider.rb_kohm is None


@pytest.mark.parametrize("base,field,value,message", [
    (VALID_VD, "vcc", "", "must be a number"),
    (VALID_VD, "vcc", "abc", "must be a number"),
    (VALID_VD, "vcc", "nan", "must be a number"),
    (VALID_VD, "vcc", "inf", "must be a number"),
    (VALID_VD, "vcc", "0", "greater than 0"),
    (VALID_VD, "r1", "0", "greater than 0"),
    (VALID_VD, "r2", "-1", "greater than 0"),
    (VALID_VD, "rc", "0", "greater than 0"),
    (VALID_VD, "re", "0", "greater than 0"),
    (VALID_FIXED, "rb", "0", "greater than 0"),
    (VALID_FIXED, "rb", "-1", "greater than 0"),
    (VALID_VD, "beta", "0", "between 1 and 10000"),
    (VALID_VD, "beta", "10001", "between 1 and 10000"),
    (VALID_VD, "vbe", "0.3", "between 0.4 V and 0.9 V"),
    (VALID_VD, "vbe", "1.2", "between 0.4 V and 0.9 V"),
])
def test_rejects_invalid_values(base, field, value, message):
    with pytest.raises(ValidationError) as info:
        parse_input(dict(base, **{field: value}))
    assert message in info.value.errors[field]


def test_collects_every_error():
    with pytest.raises(ValidationError) as info:
        parse_input(dict(VALID_VD, vcc="0", beta="0"))
    assert set(info.value.errors) == {"vcc", "beta"}


def test_reports_markup_as_a_field_error():
    with pytest.raises(ValidationError) as info:
        parse_input(dict(VALID_VD, vcc="<script>alert(1)</script>"))
    assert "vcc" in info.value.errors


def test_golden_voltage_divider():
    p = solve_voltage_divider(GOLDEN_VD)
    assert p.vbb_v == pytest.approx(2.1052631579, rel=1e-9)
    assert p.rb_ohm == pytest.approx(8245.6140351, rel=1e-9)
    assert p.ib_a == pytest.approx(1.7739724359e-05, rel=1e-6)
    assert p.ic_a == pytest.approx(2.6609586538e-03, rel=1e-6)
    assert p.ie_a == pytest.approx(2.6786983782e-03, rel=1e-6)
    assert p.ve_v == pytest.approx(1.2589882377, rel=1e-6)
    assert p.vb_v == pytest.approx(1.9589882377, rel=1e-6)
    assert p.vc_v == pytest.approx(6.1458909616, rel=1e-6)
    assert p.vce_v == pytest.approx(4.8869027239, rel=1e-6)


def test_golden_fixed_bias():
    p = solve_fixed_bias(GOLDEN_FIXED)
    assert p.vbb_v == pytest.approx(12.0, rel=1e-12)
    assert p.rb_ohm == pytest.approx(470000.0, rel=1e-12)
    assert p.ib_a == pytest.approx(2.4042553191e-05, rel=1e-6)
    assert p.ic_a == pytest.approx(3.6063829787e-03, rel=1e-6)
    assert p.ie_a == pytest.approx(3.6304255319e-03, rel=1e-6)
    assert p.ve_v == pytest.approx(0.0, abs=1e-12)
    assert p.vb_v == pytest.approx(0.7, rel=1e-9)
    assert p.vc_v == pytest.approx(4.0659574468, rel=1e-6)
    assert p.vce_v == pytest.approx(4.0659574468, rel=1e-6)


def test_golden_emitter_bias():
    p = solve_emitter_bias(GOLDEN_EMITTER)
    assert p.vbb_v == pytest.approx(12.0, rel=1e-12)
    assert p.rb_ohm == pytest.approx(470000.0, rel=1e-12)
    assert p.ib_a == pytest.approx(2.0888404163e-05, rel=1e-6)
    assert p.ic_a == pytest.approx(3.1332606244e-03, rel=1e-6)
    assert p.ie_a == pytest.approx(3.1541490286e-03, rel=1e-6)
    assert p.ve_v == pytest.approx(1.4824500434, rel=1e-6)
    assert p.vb_v == pytest.approx(2.1824500434, rel=1e-6)
    assert p.vc_v == pytest.approx(5.1068266262, rel=1e-6)
    assert p.vce_v == pytest.approx(3.6243765828, rel=1e-6)


METHOD_CASES = [
    (GOLDEN_VD, solve_voltage_divider, solve_nodal_voltage_divider),
    (GOLDEN_FIXED, solve_fixed_bias, solve_nodal_fixed_bias),
    (GOLDEN_EMITTER, solve_emitter_bias, solve_nodal_emitter_bias),
    (replace(GOLDEN_VD, beta=1.0), solve_voltage_divider, solve_nodal_voltage_divider),
    (replace(GOLDEN_FIXED, beta=1.0), solve_fixed_bias, solve_nodal_fixed_bias),
    (replace(GOLDEN_EMITTER, beta=1.0), solve_emitter_bias, solve_nodal_emitter_bias),
    (replace(GOLDEN_VD, r1_kohm=4700.0, r2_kohm=1000.0),
     solve_voltage_divider, solve_nodal_voltage_divider),
    (replace(GOLDEN_FIXED, rb_kohm=10000.0), solve_fixed_bias, solve_nodal_fixed_bias),
    (replace(GOLDEN_EMITTER, rb_kohm=10000.0), solve_emitter_bias, solve_nodal_emitter_bias),
]


@pytest.mark.parametrize("inp,closed_form,nodal", METHOD_CASES)
def test_methods_agree(inp, closed_form, nodal):
    result = compare(closed_form(inp), nodal(inp))
    assert result.agrees
    assert max(row.rel_diff for row in result.rows) < 1e-9


@pytest.mark.parametrize("inp,nodal", [
    (GOLDEN_VD, solve_nodal_voltage_divider),
    (GOLDEN_FIXED, solve_nodal_fixed_bias),
    (GOLDEN_EMITTER, solve_nodal_emitter_bias),
])
def test_nodal_respects_transistor_relations(inp, nodal):
    p = nodal(inp)
    assert p.vb_v - p.ve_v == pytest.approx(inp.vbe_v, abs=1e-9)
    assert p.ie_a == pytest.approx(p.ib_a + p.ic_a, abs=1e-12)
    assert p.ic_a / p.ib_a == pytest.approx(inp.beta, rel=1e-9)


def test_compare_detects_injected_error():
    reference = solve_voltage_divider(GOLDEN_VD)
    candidate = replace(reference, ic_a=reference.ic_a * 1.01)
    result = compare(reference, candidate)
    assert not result.agrees
    row = next(r for r in result.rows if r.key == "ic")
    assert row.rel_diff == pytest.approx(0.01)


@pytest.mark.parametrize("inp", [GOLDEN_VD, GOLDEN_FIXED, GOLDEN_EMITTER])
def test_golden_analysis_is_forward_active_and_agrees(inp):
    a = analyze(inp)
    assert a.region is Region.FORWARD_ACTIVE
    assert a.warning is None
    assert a.comparison is not None
    assert a.comparison.agrees


CUTOFF_CASES = [
    replace(GOLDEN_VD, r2_kohm=1.0),
    BiasInput(CircuitType.FIXED_BIAS, 0.5, None, None, 470.0, 2.2, None, 150.0, 0.7),
    BiasInput(CircuitType.EMITTER_BIAS, 0.5, None, None, 470.0, 2.2, 0.47, 150.0, 0.7),
]


@pytest.mark.parametrize("inp", CUTOFF_CASES)
def test_cutoff_analysis_skips_cross_check(inp):
    a = analyze(inp)
    assert a.region is Region.CUTOFF
    assert (a.point.ib_a, a.point.ic_a, a.point.ie_a) == (0.0, 0.0, 0.0)
    assert a.point.ve_v == 0.0
    assert a.point.vce_v == inp.vcc_v
    assert a.comparison is None
    assert a.warning


def test_saturation_and_near_saturation():
    sat = analyze(BiasInput(CircuitType.VOLTAGE_DIVIDER, 12.0, 22.0, 47.0, None,
                            2.2, 0.1, 150.0, 0.7))
    assert sat.region is Region.SATURATION
    assert sat.warning
    near = analyze(replace(GOLDEN_VD, rc_kohm=3.9))
    assert near.region is Region.NEAR_SATURATION
    assert near.warning

    sat = analyze(BiasInput(CircuitType.FIXED_BIAS, 12.0, None, None, 47.0,
                            2.2, None, 150.0, 0.7))
    assert sat.region is Region.SATURATION
    assert sat.warning
    near = analyze(replace(GOLDEN_FIXED, rc_kohm=3.2))
    assert near.region is Region.NEAR_SATURATION
    assert near.warning

    sat = analyze(BiasInput(CircuitType.EMITTER_BIAS, 12.0, None, None, 47.0,
                            2.2, 0.47, 150.0, 0.7))
    assert sat.region is Region.SATURATION
    assert sat.warning
    near = analyze(replace(GOLDEN_EMITTER, rc_kohm=3.2))
    assert near.region is Region.NEAR_SATURATION
    assert near.warning


@pytest.mark.parametrize("vce,region", [
    (0.2, Region.SATURATION),
    (0.19, Region.SATURATION),
    (0.21, Region.NEAR_SATURATION),
    (0.499, Region.NEAR_SATURATION),
    (0.5, Region.FORWARD_ACTIVE),
    (5.0, Region.FORWARD_ACTIVE),
])
def test_classify_boundaries(vce, region):
    point = replace(solve_voltage_divider(GOLDEN_VD), vce_v=vce)
    assert classify(point) is region


@pytest.mark.parametrize("inp,solver", [
    (BiasInput(CircuitType.VOLTAGE_DIVIDER, 1e6, 1e12, 1e12, None, 1e3, 1e3, 10000.0, 0.7),
     solve_voltage_divider),
    (BiasInput(CircuitType.FIXED_BIAS, 1e6, None, None, 1e12, 1e3, None, 10000.0, 0.7),
     solve_fixed_bias),
    (BiasInput(CircuitType.EMITTER_BIAS, 1e6, None, None, 1e12, 1e3, 1e3, 10000.0, 0.7),
     solve_emitter_bias),
])
def test_huge_but_finite_values_stay_finite(inp, solver):
    p = solver(inp)
    assert math.isfinite(p.vce_v)
    assert p.vce_v > 0
