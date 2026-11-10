"""Engineering calculations for the BJT bias-point calculator."""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

FIELD_LABELS = {"vcc": "VCC", "r1": "R1", "r2": "R2", "rc": "RC",
                "re": "RE", "beta": "β", "vbe": "VBE"}
BETA_MIN, BETA_MAX = 1.0, 10000.0
VBE_MIN, VBE_MAX = 0.4, 0.9

KOHM_TO_OHM = 1000.0
VCE_SAT_V = 0.2
VCE_NEAR_SAT_V = 0.5

FIELD_NAMES = ("vcc", "r1", "r2", "rc", "re", "beta", "vbe")


@dataclass(frozen=True)
class BiasInput:
    vcc_v: float
    r1_kohm: float
    r2_kohm: float
    rc_kohm: float
    re_kohm: float
    beta: float
    vbe_v: float


@dataclass(frozen=True)
class TheveninModel:
    """The Thevenin equivalent of the base divider."""

    vbb_v: float
    rb_ohm: float


@dataclass(frozen=True)
class OperatingPoint:
    """The solved operating point, in SI units (V, A, Ω)."""

    vbb_v: float
    rb_ohm: float
    ib_a: float
    ic_a: float
    ie_a: float
    vb_v: float
    vc_v: float
    ve_v: float
    vce_v: float


class Region(str, Enum):
    """The transistor operating region."""

    CUTOFF = "cutoff"
    SATURATION = "saturation"
    NEAR_SATURATION = "near_saturation"
    FORWARD_ACTIVE = "forward_active"


class ValidationError(ValueError):
    """Raised when one or more submitted fields fail validation."""

    def __init__(self, errors: dict[str, str]) -> None:
        self.errors = dict(errors)
        super().__init__("; ".join(self.errors.values()))


def _read_number(raw: Mapping[str, str], key: str) -> float | None:
    """Return the field value as a finite float, or None when it is not one."""
    text = str(raw.get(key, "")).strip()
    try:
        value = float(text)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def _range_error(key: str, value: float) -> str | None:
    """Return the range complaint for a parsed value, or None when it is in range."""
    if key == "vcc":
        if value <= 0:
            return "VCC must be greater than 0."
    elif key in ("r1", "r2", "rc", "re"):
        if value <= 0:
            return f"{FIELD_LABELS[key]} must be greater than 0."
    elif key == "beta":
        if value < BETA_MIN or value > BETA_MAX:
            return f"β must be between {BETA_MIN:g} and {BETA_MAX:g}."
    elif key == "vbe":
        if value < VBE_MIN or value > VBE_MAX:
            return f"VBE must be between {VBE_MIN:g} V and {VBE_MAX:g} V."
    return None


def parse_input(raw: Mapping[str, str]) -> BiasInput:
    """Parse and validate raw form fields into a BiasInput.

    Every field is checked before raising, so all problems are reported at once.
    """
    errors: dict[str, str] = {}
    numbers: dict[str, float] = {}

    for key in FIELD_NAMES:
        value = _read_number(raw, key)
        if value is None:
            errors[key] = f"{FIELD_LABELS[key]} must be a number."
            continue
        error = _range_error(key, value)
        if error is not None:
            errors[key] = error
            continue
        numbers[key] = value

    if errors:
        raise ValidationError(errors)

    return BiasInput(
        vcc_v=numbers["vcc"],
        r1_kohm=numbers["r1"],
        r2_kohm=numbers["r2"],
        rc_kohm=numbers["rc"],
        re_kohm=numbers["re"],
        beta=numbers["beta"],
        vbe_v=numbers["vbe"],
    )


def thevenin_model(inp: BiasInput) -> TheveninModel:
    """Return the Thevenin equivalent of the base divider."""
    r1_ohm = inp.r1_kohm * KOHM_TO_OHM
    r2_ohm = inp.r2_kohm * KOHM_TO_OHM
    total_ohm = r1_ohm + r2_ohm
    return TheveninModel(
        vbb_v=inp.vcc_v * r2_ohm / total_ohm,
        rb_ohm=r1_ohm * (r2_ohm / total_ohm),
    )


def solve_thevenin(inp: BiasInput) -> OperatingPoint:
    """Solve the operating point from the Thevenin equivalent of the base network."""
    model = thevenin_model(inp)
    rc_ohm = inp.rc_kohm * KOHM_TO_OHM
    re_ohm = inp.re_kohm * KOHM_TO_OHM

    ib_a = (model.vbb_v - inp.vbe_v) / (model.rb_ohm + (inp.beta + 1.0) * re_ohm)
    ic_a = inp.beta * ib_a
    ie_a = (inp.beta + 1.0) * ib_a

    ve_v = ie_a * re_ohm
    vb_v = ve_v + inp.vbe_v
    vc_v = inp.vcc_v - ic_a * rc_ohm

    return OperatingPoint(
        vbb_v=model.vbb_v,
        rb_ohm=model.rb_ohm,
        ib_a=ib_a,
        ic_a=ic_a,
        ie_a=ie_a,
        vb_v=vb_v,
        vc_v=vc_v,
        ve_v=ve_v,
        vce_v=vc_v - ve_v,
    )


def classify(point: OperatingPoint) -> Region:
    """Classify the operating point from its VCE."""
    if point.vce_v <= VCE_SAT_V:
        return Region.SATURATION
    if point.vce_v < VCE_NEAR_SAT_V:
        return Region.NEAR_SATURATION
    return Region.FORWARD_ACTIVE
