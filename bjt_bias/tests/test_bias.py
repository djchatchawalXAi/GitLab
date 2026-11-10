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
