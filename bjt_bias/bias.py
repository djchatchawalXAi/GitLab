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

REL_TOL = 1e-3
ABS_TOL = 1e-9

FIELD_NAMES = ("vcc", "r1", "r2", "rc", "re", "beta", "vbe")

CUTOFF_WARNING = (
    "Cutoff: VBB is at or below VBE, so the transistor is off and the "
    "cross-check is not applicable."
)
SATURATION_WARNING = (
    "Saturation: the active-region model is invalid here; these values are "
    "an extrapolation, not a physical operating point."
)
NEAR_SATURATION_WARNING = (
    "Near saturation: VCE is close to the edge of saturation; treat the "
    "result with caution."
)


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


@dataclass(frozen=True)
class ComparisonRow:
    """One quantity compared between the reference and candidate solves."""

    key: str
    unit: str
    reference: float
    candidate: float
    abs_diff: float
    rel_diff: float
    agrees: bool


@dataclass(frozen=True)
class Comparison:
    """The full cross-check between two operating points."""

    rows: tuple[ComparisonRow, ...]
    agrees: bool


@dataclass(frozen=True)
class Analysis:
    """The complete result of analysing one set of bias inputs."""

    input: BiasInput
    point: OperatingPoint
    region: Region
    warning: str | None
    comparison: Comparison | None


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


def _solve_linear_3x3(a: list[list[float]],
                      b: list[float]) -> tuple[float, float, float]:
    """Solve a 3x3 linear system by Gaussian elimination with partial pivoting."""
    matrix = [list(row) for row in a]
    rhs = list(b)

    for col in range(3):
        pivot = max(range(col, 3), key=lambda row: abs(matrix[row][col]))
        if matrix[pivot][col] == 0.0:
            raise ZeroDivisionError("singular system")
        if pivot != col:
            matrix[col], matrix[pivot] = matrix[pivot], matrix[col]
            rhs[col], rhs[pivot] = rhs[pivot], rhs[col]
        for row in range(col + 1, 3):
            factor = matrix[row][col] / matrix[col][col]
            if factor == 0.0:
                continue
            for k in range(col, 3):
                matrix[row][k] -= factor * matrix[col][k]
            rhs[row] -= factor * rhs[col]

    x = [0.0, 0.0, 0.0]
    for row in range(2, -1, -1):
        total = rhs[row]
        for k in range(row + 1, 3):
            total -= matrix[row][k] * x[k]
        x[row] = total / matrix[row][row]
    return x[0], x[1], x[2]


def solve_nodal(inp: BiasInput) -> OperatingPoint:
    """Solve the operating point independently by nodal analysis."""
    model = thevenin_model(inp)
    r1_ohm = inp.r1_kohm * KOHM_TO_OHM
    r2_ohm = inp.r2_kohm * KOHM_TO_OHM
    rc_ohm = inp.rc_kohm * KOHM_TO_OHM
    re_ohm = inp.re_kohm * KOHM_TO_OHM
    vcc_v = inp.vcc_v
    beta = inp.beta

    # x = [VB, VE, VC]; see design section 3 for the three equations.
    a = [
        [1.0 / r1_ohm + 1.0 / r2_ohm, 0.0, -1.0 / (beta * rc_ohm)],
        [0.0, 1.0 / re_ohm, (1.0 + 1.0 / beta) / rc_ohm],
        [1.0, -1.0, 0.0],
    ]
    b = [
        vcc_v / r1_ohm - vcc_v / (beta * rc_ohm),
        vcc_v * (1.0 + 1.0 / beta) / rc_ohm,
        inp.vbe_v,
    ]
    vb_v, ve_v, vc_v = _solve_linear_3x3(a, b)

    ic_a = (vcc_v - vc_v) / rc_ohm
    ib_a = ic_a / beta
    ie_a = ve_v / re_ohm

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


_COMPARED_QUANTITIES = (
    ("ib", "A", "ib_a"),
    ("ic", "A", "ic_a"),
    ("ie", "A", "ie_a"),
    ("vce", "V", "vce_v"),
    ("vb", "V", "vb_v"),
    ("vc", "V", "vc_v"),
    ("ve", "V", "ve_v"),
)


def compare(reference: OperatingPoint, candidate: OperatingPoint) -> Comparison:
    """Compare two operating points quantity by quantity."""
    rows = []
    for key, unit, attribute in _COMPARED_QUANTITIES:
        reference_value = getattr(reference, attribute)
        candidate_value = getattr(candidate, attribute)
        abs_diff = abs(candidate_value - reference_value)
        if reference_value != 0:
            rel_diff = abs_diff / abs(reference_value)
        elif abs_diff == 0:
            rel_diff = 0.0
        else:
            rel_diff = math.inf
        rows.append(ComparisonRow(
            key=key,
            unit=unit,
            reference=reference_value,
            candidate=candidate_value,
            abs_diff=abs_diff,
            rel_diff=rel_diff,
            agrees=abs_diff <= ABS_TOL or rel_diff <= REL_TOL,
        ))
    return Comparison(rows=tuple(rows), agrees=all(row.agrees for row in rows))


def classify(point: OperatingPoint) -> Region:
    """Classify the operating point from its VCE."""
    if point.vce_v <= VCE_SAT_V:
        return Region.SATURATION
    if point.vce_v < VCE_NEAR_SAT_V:
        return Region.NEAR_SATURATION
    return Region.FORWARD_ACTIVE


def analyze(inp: BiasInput) -> Analysis:
    """Solve, classify, warn, and cross-check one set of bias inputs."""
    model = thevenin_model(inp)
    if model.vbb_v <= inp.vbe_v:
        point = OperatingPoint(
            vbb_v=model.vbb_v,
            rb_ohm=model.rb_ohm,
            ib_a=0.0,
            ic_a=0.0,
            ie_a=0.0,
            vb_v=model.vbb_v,
            vc_v=inp.vcc_v,
            ve_v=0.0,
            vce_v=inp.vcc_v,
        )
        return Analysis(
            input=inp,
            point=point,
            region=Region.CUTOFF,
            warning=CUTOFF_WARNING,
            comparison=None,
        )

    point = solve_thevenin(inp)
    region = classify(point)
    comparison = compare(point, solve_nodal(inp))
    if region is Region.SATURATION:
        warning = SATURATION_WARNING
    elif region is Region.NEAR_SATURATION:
        warning = NEAR_SATURATION_WARNING
    else:
        warning = None
    return Analysis(
        input=inp,
        point=point,
        region=region,
        warning=warning,
        comparison=comparison,
    )
