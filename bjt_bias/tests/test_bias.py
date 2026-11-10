import math
from dataclasses import replace

import pytest

from bias import (BiasInput, Region, ValidationError, classify, parse_input,
                  solve_thevenin)

VALID = {
    "vcc": "12", "r1": "47", "r2": "10", "rc": "2.2",
    "re": "0.47", "beta": "150", "vbe": "0.7",
}


def test_parses_valid_values():
    assert parse_input(VALID) == BiasInput(12.0, 47.0, 10.0, 2.2, 0.47, 150.0, 0.7)


def test_accepts_whitespace_sign_and_scientific_notation():
    inp = parse_input(dict(VALID, vcc=" 1.2e1 ", r1="+47"))
    assert inp.vcc_v == 12.0
    assert inp.r1_kohm == 47.0


def test_accepts_beta_of_one():
    assert parse_input(dict(VALID, beta="1")).beta == 1.0


@pytest.mark.parametrize("field,value,message", [
    ("vcc", "", "must be a number"),
    ("vcc", "abc", "must be a number"),
    ("vcc", "nan", "must be a number"),
    ("vcc", "inf", "must be a number"),
    ("vcc", "0", "greater than 0"),
    ("r1", "0", "greater than 0"),
    ("r2", "-1", "greater than 0"),
    ("rc", "0", "greater than 0"),
    ("re", "0", "greater than 0"),
    ("beta", "0", "between 1 and 10000"),
    ("beta", "10001", "between 1 and 10000"),
    ("vbe", "0.3", "between 0.4 V and 0.9 V"),
    ("vbe", "1.2", "between 0.4 V and 0.9 V"),
])
def test_rejects_invalid_values(field, value, message):
    with pytest.raises(ValidationError) as info:
        parse_input(dict(VALID, **{field: value}))
    assert message in info.value.errors[field]


def test_collects_every_error():
    with pytest.raises(ValidationError) as info:
        parse_input(dict(VALID, vcc="0", beta="0"))
    assert set(info.value.errors) == {"vcc", "beta"}


def test_reports_markup_as_a_field_error():
    with pytest.raises(ValidationError) as info:
        parse_input(dict(VALID, vcc="<script>alert(1)</script>"))
    assert "vcc" in info.value.errors


GOLDEN = BiasInput(12.0, 47.0, 10.0, 2.2, 0.47, 150.0, 0.7)


def test_thevenin_golden_point():
    p = solve_thevenin(GOLDEN)
    assert p.vbb_v == pytest.approx(2.1052631579, rel=1e-9)
    assert p.rb_ohm == pytest.approx(8245.6140351, rel=1e-9)
    assert p.ib_a == pytest.approx(1.7739724359e-05, rel=1e-6)
    assert p.ic_a == pytest.approx(2.6609586538e-03, rel=1e-6)
    assert p.ie_a == pytest.approx(2.6786983782e-03, rel=1e-6)
    assert p.ve_v == pytest.approx(1.2589882377, rel=1e-6)
    assert p.vb_v == pytest.approx(1.9589882377, rel=1e-6)
    assert p.vc_v == pytest.approx(6.1458909616, rel=1e-6)
    assert p.vce_v == pytest.approx(4.8869027239, rel=1e-6)


@pytest.mark.parametrize("vce, region", [
    (0.2, Region.SATURATION),
    (0.19, Region.SATURATION),
    (0.21, Region.NEAR_SATURATION),
    (0.499, Region.NEAR_SATURATION),
    (0.5, Region.FORWARD_ACTIVE),
    (5.0, Region.FORWARD_ACTIVE),
])
def test_classify_boundaries(vce, region):
    point = replace(solve_thevenin(GOLDEN), vce_v=vce)
    assert classify(point) is region


def test_huge_but_finite_values_stay_finite():
    p = solve_thevenin(BiasInput(1e6, 1e12, 1e12, 1e3, 1e3, 10000.0, 0.7))
    assert math.isfinite(p.vce_v)
    assert p.vce_v > 0

from bias import compare, analyze, solve_nodal

CASES = [
    (12, 47, 10, 2.2, 0.47, 150, 0.7),
    (12, 47, 10, 2.2, 0.47, 1, 0.7),
    (5, 10, 2.2, 1, 0.1, 2, 0.7),
    (15, 100, 22, 4.7, 1, 50, 0.65),
    (9, 33, 6.8, 1.5, 0.22, 300, 0.75),
]


@pytest.mark.parametrize("case", CASES)
def test_methods_agree(case):
    inp = BiasInput(*case)
    result = compare(solve_thevenin(inp), solve_nodal(inp))
    assert result.agrees
    assert max(row.rel_diff for row in result.rows) < 1e-9


def test_nodal_respects_transistor_relations():
    p = solve_nodal(GOLDEN)
    assert p.vb_v - p.ve_v == pytest.approx(0.7)
    assert p.ie_a == pytest.approx(p.ib_a + p.ic_a)
    assert p.ic_a / p.ib_a == pytest.approx(150.0)


def test_compare_detects_injected_error():
    reference = solve_thevenin(GOLDEN)
    candidate = replace(reference, ic_a=reference.ic_a * 1.01)
    result = compare(reference, candidate)
    assert not result.agrees
    row = next(r for r in result.rows if r.key == "ic")
    assert row.rel_diff == pytest.approx(0.01)


def test_golden_analysis_is_forward_active_and_agrees():
    a = analyze(GOLDEN)
    assert a.region is Region.FORWARD_ACTIVE
    assert a.warning is None
    assert a.comparison is not None
    assert a.comparison.agrees


def test_cutoff_analysis_skips_cross_check():
    a = analyze(BiasInput(12.0, 47.0, 1.0, 2.2, 0.47, 150.0, 0.7))
    assert a.region is Region.CUTOFF
    assert (a.point.ib_a, a.point.ic_a, a.point.ie_a) == (0.0, 0.0, 0.0)
    assert a.point.vce_v == 12.0
    assert a.comparison is None
    assert a.warning


def test_high_vbe_gives_cutoff_not_negative_current():
    a = analyze(BiasInput(12.0, 47.0, 1.0, 2.2, 0.47, 150.0, 0.9))
    assert a.region is Region.CUTOFF
    assert a.point.ic_a == 0.0
    # VBE above VCC is valid input and still yields cutoff, not a crash.
    b = analyze(BiasInput(0.5, 47.0, 10.0, 2.2, 0.47, 150.0, 0.9))
    assert b.region is Region.CUTOFF


def test_saturation_and_near_saturation():
    sat = analyze(BiasInput(12.0, 22.0, 47.0, 2.2, 0.1, 150.0, 0.7))
    assert sat.region is Region.SATURATION
    assert sat.warning
    near = analyze(replace(GOLDEN, rc_kohm=3.9))
    assert near.region is Region.NEAR_SATURATION
    assert near.warning
