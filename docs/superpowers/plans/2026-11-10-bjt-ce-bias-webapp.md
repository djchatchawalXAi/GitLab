# BJT Common-Emitter DC Bias Web App — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A minimal Flask app that computes the DC operating point of a voltage-divider NPN common-emitter bias, validates input, warns on non-active regions, and cross-checks the result with an independently coded nodal solution.

**Architecture:** `bias.py` holds pure functions (parse → Thevenin solve → nodal solve → compare → classify) with no Flask import. `app.py` is a Flask app factory with `GET /` and `POST /calculate`. One Jinja template and one stylesheet render the form, results, warnings, and comparison. pytest covers both files.

**Tech Stack:** Python 3.12, Flask 3, Jinja2, pytest 8, plain CSS, no JavaScript.

**Spec:** `docs/superpowers/specs/2026-11-10-bjt-ce-bias-webapp-design.md`

## Global Constraints

- Python 3.12.7; `Flask>=3.0,<4`; `pytest>=8.0,<9`.
- Engineering math in SI internally (Ω, A, V). Inputs are kΩ and V; display is µA, mA, V, kΩ.
- `VCE(sat) = 0.2 V` is a fixed constant, not an input. Saturation is warned, never re-solved.
- Cutoff is `VBB <= VBE`: zero currents, `VCE = VCC`, cross-check not applicable.
- Comparison tolerance: 0.1 % relative, absolute fallback 1e-9 (SI). Thevenin is the reference.
- No JavaScript, CSS framework, CDN, database, authentication, or runtime network calls.
- All new files live under `bjt_bias/`. `electrical.py`, `test_electrical.py` and the root `README.md` are untouched.
- Run tests from `bjt_bias/` with `.\.venv\Scripts\python.exe -m pytest -q`.
- Git is not on PATH. Use `& "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe"` for every git command. Branch `main`, remote `origin`.
- Every task ends with a green test run and one commit.

## Review Focus

Each item is a failure mode the spec implies but no happy-path test exercises. The owning task adds the test.

1. **Huge but finite inputs** (`R = 1e12 kΩ`, `beta = 10000`): must stay finite, never overflow or divide by zero. Task 2 (Thevenin).
2. **Scientific notation, whitespace, leading sign** (`" 1.2e1 "`, `"+47"`): parsed as numbers, never an exception. Task 1.
3. **Markup in a field** (`<script>…`): treated as a field error and HTML-escaped in the response, never executed or echoed raw. Task 1 (parse) and Task 5 (rendering).
4. **Boundary values** `beta = 1` and `VBE = 0.9 V`: `beta = 1` stays valid and both methods agree; `VBE = 0.9` with a low divider yields cutoff, not negative currents. Task 1 (`beta = 1`), Task 3 (agreement, cutoff).
5. **Deep saturation with negative VCE**: must be labelled saturation, never forward active, and still render numbers. Task 3 (classification) and Task 5 (page).

---

### Task 1: Project skeleton and input validation

**Files:**
- Create: `bjt_bias/requirements.txt`
- Create: `bjt_bias/pytest.ini`
- Create: `bjt_bias/bias.py`
- Test: `bjt_bias/tests/test_bias.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `BiasInput` frozen dataclass with fields `vcc_v, r1_kohm, r2_kohm, rc_kohm, re_kohm, beta, vbe_v` (all `float`); `ValidationError(ValueError)` with `.errors: dict[str, str]`; `parse_input(raw: Mapping[str, str]) -> BiasInput`.

- [ ] **Step 1: Create dependencies and test configuration**

`bjt_bias/requirements.txt`:

```
Flask>=3.0,<4
pytest>=8.0,<9
```

`bjt_bias/pytest.ini`:

```ini
[pytest]
pythonpath = .
testpaths = tests
```

From `bjt_bias/`, run:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest --version
```

Expected: `pytest 8.x` printed with no install errors.

- [ ] **Step 2: Write the failing validation tests**

`bjt_bias/tests/test_bias.py`:

```python
import pytest

from bias import BiasInput, ValidationError, parse_input

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
```

- [ ] **Step 3: Run the tests to verify they fail**

Run from `bjt_bias/`: `.\.venv\Scripts\python.exe -m pytest tests/test_bias.py -q`

Expected: collection error, `ModuleNotFoundError: No module named 'bias'`.

- [ ] **Step 4: Implement the dataclass, error type, and parser**

In `bjt_bias/bias.py`, implement exactly this surface (body is the implementer's, but the message strings and aggregation order are fixed):

```python
FIELD_LABELS = {"vcc": "VCC", "r1": "R1", "r2": "R2", "rc": "RC",
                "re": "RE", "beta": "β", "vbe": "VBE"}
BETA_MIN, BETA_MAX = 1.0, 10000.0
VBE_MIN, VBE_MAX = 0.4, 0.9

@dataclass(frozen=True)
class BiasInput:
    vcc_v: float
    r1_kohm: float
    r2_kohm: float
    rc_kohm: float
    re_kohm: float
    beta: float
    vbe_v: float

class ValidationError(ValueError):
    def __init__(self, errors: dict[str, str]) -> None: ...

def parse_input(raw: Mapping[str, str]) -> BiasInput: ...
```

Rules:
- For each field, `str(raw.get(key, "")).strip()`, then `float(...)`.
- On `ValueError` or `not math.isfinite(number)`: `f"{label} must be a number."`
- Range checks append, and all errors are collected before raising:
  - `vcc <= 0` → `"VCC must be greater than 0."`
  - `r1/r2/rc/re <= 0` → `"R<n> must be greater than 0."`
  - `beta < 1 or beta > 10000` → `"β must be between 1 and 10000."`
  - `vbe < 0.4 or vbe > 0.9` → `"VBE must be between 0.4 V and 0.9 V."`
- Raise `ValidationError(errors)` only after the whole pass; return `BiasInput` with `vcc_v`, `r1_kohm`, `r2_kohm`, `rc_kohm`, `re_kohm`, `beta`, `vbe_v`.

- [ ] **Step 5: Run the tests to verify they pass**

Run from `bjt_bias/`: `.\.venv\Scripts\python.exe -m pytest tests/test_bias.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit**

```powershell
& "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe" add bjt_bias/requirements.txt bjt_bias/pytest.ini bjt_bias/bias.py bjt_bias/tests/test_bias.py
& "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe" commit -m "feat: add BJT bias input validation"
```

---

### Task 2: Thevenin operating point and region classification

**Files:**
- Modify: `bjt_bias/bias.py`
- Test: `bjt_bias/tests/test_bias.py`

**Interfaces:**
- Consumes: `BiasInput` from Task 1.
- Produces: `TheveninModel` frozen dataclass `vbb_v: float, rb_ohm: float`; `OperatingPoint` frozen dataclass `vbb_v, rb_ohm, ib_a, ic_a, ie_a, vb_v, vc_v, ve_v, vce_v` (all `float`); `Region(str, Enum)` with members `CUTOFF="cutoff"`, `SATURATION="saturation"`, `NEAR_SATURATION="near_saturation"`, `FORWARD_ACTIVE="forward_active"`; `thevenin_model(inp) -> TheveninModel`; `solve_thevenin(inp) -> OperatingPoint`; `classify(point) -> Region`.

- [ ] **Step 1: Write the failing tests**

Append to `bjt_bias/tests/test_bias.py`:

```python
import math
from dataclasses import replace

from bias import (BiasInput, Region, classify, solve_thevenin)

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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_bias.py -q`

Expected: `ImportError` for `Region`, `classify`, `solve_thevenin`.

- [ ] **Step 3: Implement `thevenin_model`, `solve_thevenin`, and `classify`**

Use the formulas in spec §3 exactly. All resistances are converted with `* 1000` to Ω before use; `OperatingPoint` stores SI, except `vbb_v` (V) and `rb_ohm` (Ω).

`classify` boundaries: `vce_v <= 0.2` → `SATURATION`; `vce_v < 0.5` → `NEAR_SATURATION`; otherwise `FORWARD_ACTIVE`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_bias.py -q`

Expected: all tests pass, including the earlier validation tests.

- [ ] **Step 5: Commit**

```powershell
& "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe" add bjt_bias/bias.py bjt_bias/tests/test_bias.py
& "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe" commit -m "feat: add Thevenin operating point and region classification"
```

---

### Task 3: Nodal cross-check, comparison, and analysis

**Files:**
- Modify: `bjt_bias/bias.py`
- Test: `bjt_bias/tests/test_bias.py`

**Interfaces:**
- Consumes: `BiasInput`, `OperatingPoint`, `Region`, `thevenin_model`, `solve_thevenin`, `classify` from Tasks 1–2.
- Produces: `solve_nodal(inp) -> OperatingPoint`; `ComparisonRow` frozen dataclass `key: str, unit: str, reference: float, candidate: float, abs_diff: float, rel_diff: float, agrees: bool`; `Comparison` frozen dataclass `rows: tuple[ComparisonRow, ...], agrees: bool`; `compare(reference, candidate) -> Comparison`; `Analysis` frozen dataclass `input: BiasInput, point: OperatingPoint, region: Region, warning: str | None, comparison: Comparison | None`; `analyze(inp) -> Analysis`; constants `REL_TOL = 1e-3`, `ABS_TOL = 1e-9`.

- [ ] **Step 1: Write the failing tests**

Append to `bjt_bias/tests/test_bias.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_bias.py -q`

Expected: `ImportError` for `compare`, `analyze`, `solve_nodal`.

- [ ] **Step 3: Implement the nodal solver, comparator, and analysis**

- `solve_nodal`: build the 3×3 system from spec §3 in SI units (`x = [VB, VE, VC]`), solve with Gaussian elimination and partial pivoting (a private `_solve_linear_3x3(a, b)`), then recover `IB`, `IC`, `IE`, `VCE`. Fill `vbb_v`/`rb_ohm` from `thevenin_model`.
- `compare`: rows in this order and with these keys/units:
  `ib:A, ic:A, ie:A, vce:V, vb:V, vc:V, ve:V`.
  `abs_diff = abs(candidate - reference)`.
  `rel_diff = abs_diff / abs(reference)` when `reference != 0`, else `0.0` when `abs_diff == 0`, else `math.inf`.
  `row.agrees = abs_diff <= ABS_TOL or rel_diff <= REL_TOL`; `Comparison.agrees` is the `and` of all rows.
- `analyze`:
  1. `model = thevenin_model(inp)`; if `model.vbb_v <= inp.vbe_v`, return cutoff: point has zero currents, `ve_v=0`, `vb_v=model.vbb_v`, `vc_v=inp.vcc_v`, `vce_v=inp.vcc_v`; `region=Region.CUTOFF`; a warning naming cutoff; `comparison=None`.
  2. Else `point = solve_thevenin(inp)`, `region = classify(point)`, `comparison = compare(point, solve_nodal(inp))`.
  3. Warnings (exact text, tests assert presence only): saturation mentions "active-region model" and "extrapolation"; near-saturation mentions "close to the edge"; forward active has `warning=None`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_bias.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
& "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe" add bjt_bias/bias.py bjt_bias/tests/test_bias.py
& "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe" commit -m "feat: add nodal cross-check and DC analysis"
```

---

### Task 4: Flask app factory and input form

**Files:**
- Create: `bjt_bias/app.py`
- Create: `bjt_bias/templates/index.html`
- Create: `bjt_bias/static/style.css`
- Test: `bjt_bias/tests/test_app.py`

**Interfaces:**
- Consumes: `bias` module from Tasks 1–3.
- Produces: `create_app() -> Flask`; `FIELD_SPECS: tuple[tuple[str, str, str, str], ...]` where each item is `(name, label, unit, default)`; `FIELD_DEFAULTS: dict[str, str]`; `REGION_LABELS: dict[Region, str]`; `format_quantity(value_si: float, key: str) -> str`. `GET /?blank=1` renders every field empty.

- [ ] **Step 1: Write the failing GET test**

`bjt_bias/tests/test_app.py`:

```python
import pytest

from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_get_form_shows_all_fields_with_units(client):
    response = client.get("/")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    for name in ("vcc", "r1", "r2", "rc", "re", "beta", "vbe"):
        assert f'name="{name}"' in body
    assert "kΩ" in body
    assert "VBE" in body


def test_reset_link_renders_a_blank_form(client):
    body = client.get("/?blank=1").get_data(as_text=True)
    assert 'value=""' in body
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_app.py -q`

Expected: `ModuleNotFoundError: No module named 'app'`.

- [ ] **Step 3: Implement the app factory, form template, and stylesheet**

- `FIELD_SPECS`, in order:
  `("vcc", "VCC", "V", "12")`, `("r1", "R1", "kΩ", "47")`, `("r2", "R2", "kΩ", "10")`,
  `("rc", "RC", "kΩ", "2.2")`, `("re", "RE", "kΩ", "0.47")`, `("beta", "β", "—", "150")`,
  `("vbe", "VBE", "V", "0.7")`.
- `REGION_LABELS`: `CUTOFF: "Cut-off"`, `SATURATION: "Saturation"`, `NEAR_SATURATION: "Near saturation"`, `FORWARD_ACTIVE: "Forward active"`.
- `create_app()` builds `Flask(__name__)`, registers `GET /` rendering `index.html` with `fields=FIELD_SPECS`, `errors={}`, `analysis=None`, `region_labels=REGION_LABELS`, and returns the app. `form` is `FIELD_DEFAULTS` normally, or `{name: "" for ...}` when `request.args.get("blank") == "1"`. A `__main__` block runs `create_app().run(debug=True)` on `127.0.0.1:5000`.
- `templates/index.html`: one page, `<form method="post" action="/calculate">`, one labelled `<input type="text" inputmode="decimal" value="{{ form.get(name, default) }}">` per field with the unit in the label, a submit button, an empty `<section id="results">` placeholder used by Task 5, and a `<a href="/?blank=1">Reset</a>` link. No JavaScript, no external assets.
- `static/style.css`: readable single-column layout, form grid, and classes `.region-cutoff`, `.region-saturation`, `.region-near_saturation`, `.region-forward_active` (text labels must also be present; colour alone is not enough).

- [ ] **Step 4: Run the test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_app.py -q`

Expected: the GET test passes.

- [ ] **Step 5: Commit**

```powershell
& "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe" add bjt_bias/app.py bjt_bias/templates/index.html bjt_bias/static/style.css bjt_bias/tests/test_app.py
& "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe" commit -m "feat: add bias input form"
```

---

### Task 5: Calculation route, results, errors, and comparison display

**Files:**
- Modify: `bjt_bias/app.py`
- Modify: `bjt_bias/templates/index.html`
- Modify: `bjt_bias/static/style.css`
- Test: `bjt_bias/tests/test_app.py`

**Interfaces:**
- Consumes: `parse_input`, `ValidationError`, `analyze`, `ComparisonRow`; `create_app` and `format_quantity` from Task 4.
- Produces: `POST /calculate` returning HTTP 200 with either results or field errors; `format_quantity` mapping: `ib → µA (×1e6)`, `ic/ie → mA (×1e3)`, `vbb/vb/vc/ve/vce → V (×1)`, `rb → kΩ (×1e-3)`, formatted with `:.4g` and the unit appended.

- [ ] **Step 1: Write the failing route tests**

Append to `bjt_bias/tests/test_app.py`:

```python
VALID = {
    "vcc": "12", "r1": "47", "r2": "10", "rc": "2.2",
    "re": "0.47", "beta": "150", "vbe": "0.7",
}


def test_valid_post_shows_results_and_cross_check(client):
    response = client.post("/calculate", data=VALID)
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Forward active" in body
    assert "17.74" in body
    assert "2.661" in body
    assert "4.887" in body
    assert "Thevenin" in body and "Nodal" in body
    assert "agree" in body.lower()


def test_invalid_post_returns_form_with_errors(client):
    response = client.post("/calculate", data=dict(VALID, r1="0"))
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "greater than 0" in body
    assert 'value="0"' in body
    assert "Operating point" not in body


def test_missing_or_empty_body_does_not_500(client):
    assert client.post("/calculate", data={}).status_code == 200
    assert client.post("/calculate").status_code == 200


def test_markup_is_escaped(client):
    response = client.post("/calculate", data=dict(VALID, vcc="<script>alert(1)</script>"))
    body = response.get_data(as_text=True)
    assert "&lt;script&gt;" in body
    assert "<script>alert(1)</script>" not in body


def test_saturation_page_is_not_labelled_forward_active(client):
    response = client.post("/calculate", data=dict(VALID, r1="22", r2="47", re="0.1"))
    body = response.get_data(as_text=True)
    assert "Saturation" in body
    assert "Forward active" not in body
    assert "extrapolation" in body.lower()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_app.py -q`

Expected: POST tests fail with 404/405; the GET test still passes.

- [ ] **Step 3: Implement the route, formatting, and result template**

- `format_quantity` as specified in Interfaces; return e.g. `"17.74 µA"`, `"2.661 mA"`, `"4.887 V"`, `"8.246 kΩ"`.
- `POST /calculate`: `raw = request.form.to_dict()`; `try: inp = parse_input(raw)`; on `ValidationError` render `index.html` with `form=raw`, `errors=error.errors`, `analysis=None`, status 200. Otherwise render with `form=raw`, `errors={}`, `analysis=analyze(inp)`.
- Template result block, rendered only when `analysis` is set:
  - Region badge text from `region_labels[analysis.region]` plus `class="region-{{ analysis.region.value }}"`.
  - `analysis.warning` in a callout when present.
  - A table headed exactly `Operating point` with IB, IC, IE, VCE, VB, VC, VE using `format_quantity`.
  - A model line showing VBB and RB in kΩ.
  - A `Cross-check` table with columns Quantity, Thevenin, Nodal, |Δ|, Δ%, Result for each comparison row; a verdict line containing "agree" or "do not agree".
  - When `analysis.comparison is None`, show "not applicable" and explain cutoff.
- Error block: each field's message beside its input, plus a summary; submitted values stay in `value="..."`.
- Jinja autoescape stays on (default for `.html`).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest -q`

Expected: all `test_bias.py` and `test_app.py` tests pass.

- [ ] **Step 5: Commit**

```powershell
& "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe" add bjt_bias/app.py bjt_bias/templates/index.html bjt_bias/static/style.css bjt_bias/tests/test_app.py
& "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe" commit -m "feat: add calculation results and cross-check page"
```

---

### Task 6: README, live-server verification, and push

**Files:**
- Create: `bjt_bias/README.md`
- Modify: `docs/` is committed here (design and plan documents).

**Interfaces:**
- Consumes: the completed app.
- Produces: runnable documentation and a pushed `main`.

- [ ] **Step 1: Write `bjt_bias/README.md`**

Sections, with these exact commands and facts:

```text
# BJT Common-Emitter DC Bias Calculator (ENG29 2121)
What it does / Requirements / Setup / Run / Test / Model and assumptions /
Formulas / Region rules / Worked example / Project layout
```

Must state: Python 3.12; `python -m venv .venv`;
`.\.venv\Scripts\python.exe -m pip install -r requirements.txt`;
run with `.\.venv\Scripts\python.exe app.py` then open `http://127.0.0.1:5000`;
test with `.\.venv\Scripts\python.exe -m pytest -q`.
Must state the assumptions: fixed `VBE`, constant `beta`, no Early effect, `VCE(sat) = 0.2 V`, saturation warned not re-solved, comparison is nodal analysis at 0.1 % tolerance.
Must include the worked example values from the spec and both method formulas.

- [ ] **Step 2: Run the full suite**

From `bjt_bias/`: `.\.venv\Scripts\python.exe -m pytest -q`

Expected: all tests pass; zero failures/errors.

- [ ] **Step 3: Verify the live server end to end**

From `bjt_bias/`, run:

```powershell
$proc = Start-Process -PassThru -FilePath ".\.venv\Scripts\python.exe" -ArgumentList "app.py"
Start-Sleep -Seconds 2
curl.exe -s http://127.0.0.1:5000/
curl.exe -s -X POST http://127.0.0.1:5000/calculate -d "vcc=12&r1=47&r2=10&rc=2.2&re=0.47&beta=150&vbe=0.7"
Stop-Process -Id $proc.Id
```

Expected: the GET body contains `name="vcc"`; the POST body contains `Forward active`, `2.661`, and `agree`. If the port is occupied, stop the other process and rerun.

- [ ] **Step 4: Commit documentation**

From the repository root:

```powershell
& "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe" add bjt_bias/README.md docs/superpowers
& "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe" commit -m "docs: add BJT bias app README and design records"
```

- [ ] **Step 5: Push and verify the remote state**

```powershell
& "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe" push origin main
& "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe" status --short --branch
& "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe" log --oneline -6
```

Expected: push succeeds; status shows `main...origin/main` with no ahead/behind and no modified files; the log shows the six task commits.
