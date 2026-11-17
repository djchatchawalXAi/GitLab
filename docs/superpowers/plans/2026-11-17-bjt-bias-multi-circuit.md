# Multi-Circuit BJT Bias App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the Lab 02 Flask bias calculator so a user can choose voltage-divider, fixed, or emitter bias, with CSS-only field/schematic switching and per-circuit equations and cross-checks.

**Architecture:** `bias.py` gains a `CircuitType` enum, circuit-aware validation, three closed-form solvers, three independent nodal solvers, and a dispatching `analyze()`. `app.py` adds circuit metadata and route-level circuit resolution. One template renders every field, schematic, and state block for all circuits; CSS `:has()` rules show only the blocks that match the checked radio. No JavaScript is added.

**Tech Stack:** Python 3.12, Flask 3.1, Jinja2, pytest 8.4, plain CSS.

**Spec:** `docs/superpowers/specs/2026-11-17-bjt-bias-multi-circuit-design.md`

## Global Constraints

- Python 3.12, `Flask>=3.0,<4`, `pytest>=8.0,<9`; no new dependencies.
- No JavaScript, no `<script>`, no inline `on*=` handlers, no CDN, no build step.
- Circuit switching is CSS `:has()` keyed on radio ids `circuit-voltage-divider`, `circuit-fixed-bias`, `circuit-emitter-bias`.
- All seven resistor fields plus shared fields are rendered on every page, in the order `VCC, R1, R2, RB, RC, RE, β, VBE`.
- One shared default set: `VCC=12`, `R1=47`, `R2=10`, `RB=470`, `RC=2.2`, `RE=0.47`, `β=150`, `VBE=0.7`.
- Internally SI units (Ω, A, V); convert only at the input and display edges. Display: `IB` in µA, `IC`/`IE` in mA, voltages in V, `RB` in kΩ.
- `VCE(sat) = 0.2 V`, near-saturation band `0.2 < VCE < 0.5 V`, `1 <= β <= 10000`, `0.4 <= VBE <= 0.9 V`.
- Unknown GET `circuit` falls back to voltage divider; unknown POST `circuit` is a form error, never a 500.
- Ignored fields are not parsed and cannot affect the selected circuit's result.
- Keep the SUT orange/gold palette and the three-column `.layout` desktop grid.
- Run commands from `C:\Users\B6839031\Desktop\GitLab\bjt_bias`; git is `"$env:LOCALAPPDATA\Programs\Git\cmd\git.exe"` (not on PATH).

## Review Focus

- Hidden stale values in unused resistor fields must be ignored by validation and calculation (test in Task 1).
- Flipping the radio after a POST must hide stale results, the region badge, the error summary, and the wrong reset link; it must not leave "fix R1" under Fixed Bias (tests in Tasks 2–3).
- Fixed bias has no `RE`: `VE=0`, `IE=IB+IC`, and the nodal system must not divide by zero (Task 1).
- Fixed/emitter cutoff at `VCC <= VBE` must return zero currents, not negative currents or a division error (Task 1).
- A browser without `:has()` must still render every field and submit a valid circuit; no server path may depend on CSS (Tasks 2–3).

---

### Task 1: Circuit-aware engineering core

**Files:**
- Modify: `bjt_bias/bias.py` (rewrite the model, validation, solvers, and analysis)
- Modify: `bjt_bias/tests/test_bias.py` (rewrite around the new API)

**Interfaces:**
- Consumes: nothing outside the standard library.
- Produces:
  - `CircuitType(str, Enum)` with `VOLTAGE_DIVIDER="voltage_divider"`, `FIXED_BIAS="fixed_bias"`, `EMITTER_BIAS="emitter_bias"`.
  - `DEFAULT_CIRCUIT: CircuitType = CircuitType.VOLTAGE_DIVIDER`.
  - `BiasInput(circuit: CircuitType, vcc_v: float, r1_kohm: float | None, r2_kohm: float | None, rb_kohm: float | None, rc_kohm: float, re_kohm: float | None, beta: float, vbe_v: float)`.
  - `CIRCUIT_FIELDS: dict[CircuitType, tuple[str, ...]]`.
  - `parse_input(raw: Mapping[str, str]) -> BiasInput`.
  - `solve_voltage_divider(inp) -> OperatingPoint`, `solve_fixed_bias(inp) -> OperatingPoint`, `solve_emitter_bias(inp) -> OperatingPoint`.
  - `solve_nodal_voltage_divider(inp) -> OperatingPoint`, `solve_nodal_fixed_bias(inp) -> OperatingPoint`, `solve_nodal_emitter_bias(inp) -> OperatingPoint`.
  - `analyze(inp: BiasInput) -> Analysis`; `classify`, `compare`, `Region`, `ValidationError`, `OperatingPoint`, `Analysis` keep their existing shapes.

- [ ] **Step 1: Write the failing tests in `bjt_bias/tests/test_bias.py`**

Include these fixtures and cases:

```python
GOLDEN_VD = BiasInput(CircuitType.VOLTAGE_DIVIDER, 12.0, 47.0, 10.0, None, 2.2, 0.47, 150.0, 0.7)
GOLDEN_FIXED = BiasInput(CircuitType.FIXED_BIAS, 12.0, None, None, 470.0, 2.2, None, 150.0, 0.7)
GOLDEN_EMITTER = BiasInput(CircuitType.EMITTER_BIAS, 12.0, None, None, 470.0, 2.2, 0.47, 150.0, 0.7)

VALID_VD = {"circuit": "voltage_divider", "vcc": "12", "r1": "47", "r2": "10",
            "rc": "2.2", "re": "0.47", "beta": "150", "vbe": "0.7"}
VALID_FIXED = {"circuit": "fixed_bias", "vcc": "12", "rb": "470",
               "rc": "2.2", "beta": "150", "vbe": "0.7"}
VALID_EMITTER = {"circuit": "emitter_bias", "vcc": "12", "rb": "470", "rc": "2.2",
                 "re": "0.47", "beta": "150", "vbe": "0.7"}
```

Tests and assertions:

- `test_parses_each_circuit`: each `VALID_*` parses to the matching `CircuitType`, with unused resistors `None` and used resistors set.
- `test_accepts_whitespace_sign_and_scientific_notation`: `vcc=" 1.2e1 "`, `r1="+47"` parse to 12.0 and 47.0.
- `test_accepts_beta_of_one`: `beta="1"` parses.
- `test_missing_circuit_defaults_to_voltage_divider`: parse `VALID_VD` without `circuit`; result circuit is `VOLTAGE_DIVIDER`.
- `test_unknown_circuit_is_a_form_error`: parse `dict(VALID_VD, circuit="bogus")`; `ValidationError.errors["circuit"]` contains "Choose a valid circuit type".
- `test_required_fields_per_circuit`: missing `r1` for VD, missing `rb` for fixed, missing `re` for emitter each raise with that field key.
- `test_ignored_fields_are_ignored`: fixed with `r1="abc", r2="0", re="not-a-number"` parses; emitter with `r1="abc"` parses; VD with `rb="abc"` parses.
- `test_rejects_invalid_values` (table-driven, existing cases): blank/non-numeric/NaN/inf, `VCC=0`, resistance `0`/negative, `beta` 0/10001, `VBE` 0.3/1.2.
- `test_collects_every_error`: VD with `vcc="0"`, `beta="0"` reports both keys.
- `test_reports_markup_as_a_field_error`: VD with `vcc="<script>alert(1)</script>"`.
- `test_golden_voltage_divider` using the Lab 02 values (1e-9 for VBB/RB, 1e-6 for the rest):
  `vbb=2.1052631579`, `rb=8245.6140351`, `ib=1.7739724359e-05`, `ic=2.6609586538e-03`, `ie=2.6786983782e-03`, `ve=1.2589882377`, `vb=1.9589882377`, `vc=6.1458909616`, `vce=4.8869027239`.
- `test_golden_fixed_bias`:
  `vbb=12.0`, `rb=470000.0`, `ib=2.4042553191e-05`, `ic=3.6063829787e-03`, `ie=3.6304255319e-03`, `ve=0.0`, `vb=0.7`, `vc=4.0659574468`, `vce=4.0659574468`.
- `test_golden_emitter_bias`:
  `vbb=12.0`, `rb=470000.0`, `ib=2.0888404163e-05`, `ic=3.1332606244e-03`, `ie=3.1541490286e-03`, `ve=1.4824500434`, `vb=2.1824500434`, `vc=5.1068266262`, `vce=3.6243765828`.
- `test_methods_agree` parametrised over `(input, closed_form, nodal)` for all three goldens plus low-beta and large-RB variants; assert `compare(...).agrees` and `max(row.rel_diff) < 1e-9`.
- `test_nodal_respects_transistor_relations` parametrised over the three goldens: `vb - ve ≈ vbe`, `ie ≈ ib + ic`, `ic / ib ≈ beta`.
- `test_compare_detects_injected_error`: inject 1 % into `ic`; comparison disagrees and that row's `rel_diff ≈ 0.01`.
- `test_golden_analysis_is_forward_active_and_agrees` parametrised over the three goldens.
- `test_cutoff_analysis_skips_cross_check` parametrised:
  VD `R2=1`; fixed `VCC=0.5, RB=470, RC=2.2, VBE=0.7`; emitter `VCC=0.5, RB=470, RC=2.2, RE=0.47`.
  Assert zero currents, `VE=0`, `VCE=VCC`, `comparison is None`, and a warning.
- `test_saturation_and_near_saturation`:
  VD existing (`R1=22, R2=47, RE=0.1`) saturation; `GOLDEN_VD` with `RC=3.9` near.
  Fixed `RB=47, RC=2.2` saturation; `GOLDEN_FIXED` with `RC=3.2` near.
  Emitter `RB=47, RC=2.2, RE=0.47` saturation; `GOLDEN_EMITTER` with `RC=3.2` near.
- `test_classify_boundaries`: `vce` 0.2→saturation, 0.19→saturation, 0.21→near, 0.499→near, 0.5→forward, 5.0→forward.
- `test_huge_but_finite_values_stay_finite` for the fixed and emitter variants as well as VD.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_bias.py -q`

Expected: collection fails because `CircuitType` and the new solver names do not exist.

- [ ] **Step 3: Implement `bias.py`**

Use these exact signatures and decisions:

```python
class CircuitType(str, Enum):
    VOLTAGE_DIVIDER = "voltage_divider"
    FIXED_BIAS = "fixed_bias"
    EMITTER_BIAS = "emitter_bias"

DEFAULT_CIRCUIT = CircuitType.VOLTAGE_DIVIDER

CIRCUIT_FIELDS = {
    CircuitType.VOLTAGE_DIVIDER: ("vcc", "r1", "r2", "rc", "re", "beta", "vbe"),
    CircuitType.FIXED_BIAS: ("vcc", "rb", "rc", "beta", "vbe"),
    CircuitType.EMITTER_BIAS: ("vcc", "rb", "rc", "re", "beta", "vbe"),
}
```

`BiasInput` field order is exactly `circuit, vcc_v, r1_kohm, r2_kohm, rb_kohm, rc_kohm, re_kohm, beta, vbe_v`. Add `"rb": "RB"` to `FIELD_LABELS`; treat `rb` as a resistance in `_range_error`.

`parse_input`:

```python
def parse_input(raw: Mapping[str, str]) -> BiasInput:
    errors: dict[str, str] = {}
    circuit = DEFAULT_CIRCUIT
    text = str(raw.get("circuit", "")).strip()
    if text:
        try:
            circuit = CircuitType(text)
        except ValueError:
            errors["circuit"] = "Choose a valid circuit type."

    numbers: dict[str, float] = {}
    for key in CIRCUIT_FIELDS[circuit]:
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
        circuit=circuit,
        vcc_v=numbers["vcc"],
        r1_kohm=numbers.get("r1"),
        r2_kohm=numbers.get("r2"),
        rb_kohm=numbers.get("rb"),
        rc_kohm=numbers["rc"],
        re_kohm=numbers.get("re"),
        beta=numbers["beta"],
        vbe_v=numbers["vbe"],
    )
```

Keep `thevenin_model` for the divider. Add two private helpers:

```python
def _point_from_ib(inp: BiasInput, *, vbb_v: float, rb_ohm: float, ib_a: float) -> OperatingPoint: ...
def _point_from_nodal(inp: BiasInput, *, vb_v: float, ve_v: float, vc_v: float,
                      vbb_v: float, rb_ohm: float) -> OperatingPoint: ...
```

`_point_from_ib` computes `ic=beta*ib`, `ie=(beta+1)*ib`, `re_ohm=(inp.re_kohm or 0.0)*KOHM_TO_OHM`, `ve=ie*re_ohm`, `vb=ve+vbe`, `vc=vcc-ic*rc_ohm`, `vce=vc-ve`. `_point_from_nodal` computes `ic=(vcc-vc)/rc_ohm`, `ib=ic/beta`, `ie=ib+ic`, `vce=vc-ve`.

Closed-form solvers:

- `solve_voltage_divider`: existing Thevenin equations, `ib=(vbb-vbe)/(rb+(beta+1)*re_ohm)`.
- `solve_fixed_bias`: `rb_ohm=inp.rb_kohm*KOHM_TO_OHM`, `ib=(vcc-vbe)/rb_ohm`, `_point_from_ib(..., vbb_v=vcc, rb_ohm=rb_ohm, ib_a=ib)`.
- `solve_emitter_bias`: `rb_ohm` and `re_ohm` from inputs, `ib=(vcc-vbe)/(rb_ohm+(beta+1)*re_ohm)`, `_point_from_ib(..., vbb_v=vcc, rb_ohm=rb_ohm, ib_a=ib)`.

Nodal solvers, with `x=[VB, VE, VC]`:

- Divider rows exactly as the existing `solve_nodal` (base KCL, emitter KCL, `VB-VE=VBE`), then `_point_from_nodal`.
- Fixed rows: `[1/RB, 0, -1/(beta*RC)] = VCC/RB - VCC/(beta*RC)`; `[0, 1, 0] = 0`; `[1, -1, 0] = VBE`.
- Emitter rows: `[1/RB, 0, -1/(beta*RC)] = VCC/RB - VCC/(beta*RC)`; `[0, 1/RE, (1+1/beta)/RC] = VCC*(1+1/beta)/RC`; `[1, -1, 0] = VBE`.

`analyze` resolves the base source and dispatch:

```python
def analyze(inp: BiasInput) -> Analysis:
    if inp.circuit is CircuitType.VOLTAGE_DIVIDER:
        model = thevenin_model(inp)
        vbb_v, rb_ohm = model.vbb_v, model.rb_ohm
        solve, nodal = solve_voltage_divider, solve_nodal_voltage_divider
    elif inp.circuit is CircuitType.FIXED_BIAS:
        vbb_v, rb_ohm = inp.vcc_v, inp.rb_kohm * KOHM_TO_OHM
        solve, nodal = solve_fixed_bias, solve_nodal_fixed_bias
    else:
        vbb_v, rb_ohm = inp.vcc_v, inp.rb_kohm * KOHM_TO_OHM
        solve, nodal = solve_emitter_bias, solve_nodal_emitter_bias

    if vbb_v <= inp.vbe_v:
        point = OperatingPoint(vbb_v=vbb_v, rb_ohm=rb_ohm, ib_a=0.0, ic_a=0.0,
                               ie_a=0.0, vb_v=vbb_v, vc_v=inp.vcc_v, ve_v=0.0,
                               vce_v=inp.vcc_v)
        return Analysis(input=inp, point=point, region=Region.CUTOFF,
                        warning=CUTOFF_WARNING, comparison=None)

    point = solve(inp)
    region = classify(point)
    comparison = compare(point, nodal(inp))
    warning = (SATURATION_WARNING if region is Region.SATURATION else
               NEAR_SATURATION_WARNING if region is Region.NEAR_SATURATION else None)
    return Analysis(input=inp, point=point, region=region,
                    warning=warning, comparison=comparison)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_bias.py -q`

Expected: all bias tests pass.

- [ ] **Step 5: Commit**

```powershell
& "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe" add bjt_bias/bias.py bjt_bias/tests/test_bias.py
& "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe" commit -m "feat: solve three BJT bias circuits with nodal cross-checks"
```

---

### Task 2: Circuit metadata, routes, and template

**Files:**
- Modify: `bjt_bias/app.py`
- Modify: `bjt_bias/templates/index.html`
- Modify: `bjt_bias/tests/test_app.py`

**Interfaces:**
- Consumes: `CircuitType`, `DEFAULT_CIRCUIT`, `ValidationError`, `analyze`, `parse_input` from Task 1; `Region` for labels.
- Produces:
  - `FieldSpec(name: str, label: str, unit: str, default: str, circuits: tuple[CircuitType, ...])` with a `css_class` property returning `for-all` or space-separated `for-<hyphenated-circuit>` classes.
  - `CIRCUIT_LABELS: dict[CircuitType, str]`, `FIELD_SPECS: tuple[FieldSpec, ...]`, `FIELD_DEFAULTS: dict[str, str]`, `resolve_circuit(value: str | None) -> CircuitType`, and `css_name(circuit: CircuitType) -> str` returning `circuit.value.replace("_", "-")`.
  - Template context: `fields`, `form`, `errors`, `analysis`, `region_labels`, `circuits`, `selected_circuit`, `result_circuit`.
  - HTML classes: `.circuit-picker`, `.circuit-option`, `.for-all`, `.for-voltage-divider`, `.for-fixed-bias`, `.for-emitter-bias`, `.diagram-<circuit>`, `.circuit-heading-<circuit>`, `.results-for-<circuit>`, `.results-placeholder-for-<circuit>`, `.error-summary-for-<circuit>`, `.reset-link-for-<circuit>`, `.result-region-for-<circuit>`, `.result-circuit`.

- [ ] **Step 1: Write the failing app tests in `bjt_bias/tests/test_app.py`**

Use these raw payloads:

```python
VALID_VD = {"circuit": "voltage_divider", "vcc": "12", "r1": "47", "r2": "10",
            "rc": "2.2", "re": "0.47", "beta": "150", "vbe": "0.7"}
VALID_FIXED = {"circuit": "fixed_bias", "vcc": "12", "rb": "470",
               "rc": "2.2", "beta": "150", "vbe": "0.7"}
VALID_EMITTER = {"circuit": "emitter_bias", "vcc": "12", "rb": "470", "rc": "2.2",
                 "re": "0.47", "beta": "150", "vbe": "0.7"}
```

Tests and assertions:

- `test_get_form_shows_all_fields_and_picker`: GET `/`; status 200; body contains all eight `name="…"` fields, three radio ids, `kΩ`, `VBE`, and the visibility classes `for-voltage-divider`, `for-fixed-bias`, `for-emitter-bias`.
- `test_default_circuit_is_voltage_divider`: body contains `id="circuit-voltage-divider"` and that radio is `checked`; the fixed radio is not.
- `test_query_selects_circuit_without_changing_defaults`: GET `/?circuit=fixed_bias`; fixed radio checked; `name="rb"` still has `value="470"` and `name="rc"` still `value="2.2"`.
- `test_unknown_query_circuit_falls_back`: GET `/?circuit=bogus`; voltage-divider radio checked; status 200.
- `test_reset_links_keep_each_circuit`: GET `/?circuit=emitter_bias`; body contains `blank=1` and `circuit=emitter_bias`; three reset links are present.
- `test_reset_link_renders_a_blank_form`: GET `/?blank=1`; body contains `value=""`.
- `test_valid_post_each_circuit` parametrised:
  - VD: "Results for Voltage Divider Bias", "Forward active", "17.74", "2.661", "4.887".
  - Fixed: "Results for Fixed Bias", "Forward active", "24.04", "3.606", "4.066".
  - Emitter: "Results for Emitter Bias", "Forward active", "20.89", "3.133", "3.624".
  Each also contains "Closed-form", "Nodal", and "agree".
- `test_invalid_post_per_circuit`: VD `r1="0"`, fixed `rb="abc"`, emitter `re="0"`; status 200, the field message appears, the submitted value is preserved, and "Operating point" is absent.
- `test_unknown_circuit_post_is_form_error`: POST `dict(VALID_VD, circuit="bogus")`; status 200; "Choose a valid circuit type" appears.
- `test_missing_or_empty_body_does_not_500`: `client.post("/calculate", data={})` and `client.post("/calculate")` both 200.
- `test_markup_is_escaped`: POST VD with `vcc="<script>alert(1)</script>"`; body contains `&lt;script&gt;` and not the raw tag.
- `test_saturation_page_is_not_labelled_forward_active` parametrised: fixed `rb="47"`; emitter `rb="47", re="0.47"`; body contains "Saturation", "extrapolation", and not "Forward active".
- `test_results_markup_is_tagged_for_css`: POST VD and assert `results-for-voltage-divider`, `results-placeholder-for-fixed-bias`, `results-placeholder-for-emitter-bias`, and all three `reset-link-for-…` classes appear.
- `test_page_has_no_javascript`: GET `/`; body contains no `<script` and no `onchange=`, `onclick=`, or `onsubmit=`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_app.py -q`

Expected: failures for missing radio, field classes, and circuit routing.

- [ ] **Step 3: Implement `app.py` metadata and routes**

Use these exact declarations:

```python
ALL_CIRCUITS = tuple(CircuitType)

CIRCUIT_LABELS = {
    CircuitType.VOLTAGE_DIVIDER: "Voltage Divider Bias",
    CircuitType.FIXED_BIAS: "Fixed Bias",
    CircuitType.EMITTER_BIAS: "Emitter Bias",
}

def css_name(circuit: CircuitType) -> str:
    return circuit.value.replace("_", "-")

@dataclass(frozen=True)
class FieldSpec:
    name: str
    label: str
    unit: str
    default: str
    circuits: tuple[CircuitType, ...]

    @property
    def css_class(self) -> str:
        if len(self.circuits) == len(ALL_CIRCUITS):
            return "for-all"
        return " ".join(f"for-{css_name(circuit)}" for circuit in self.circuits)

FIELD_SPECS = (
    FieldSpec("vcc", "VCC", "V", "12", ALL_CIRCUITS),
    FieldSpec("r1", "R1", "kΩ", "47", (CircuitType.VOLTAGE_DIVIDER,)),
    FieldSpec("r2", "R2", "kΩ", "10", (CircuitType.VOLTAGE_DIVIDER,)),
    FieldSpec("rb", "RB", "kΩ", "470", (CircuitType.FIXED_BIAS, CircuitType.EMITTER_BIAS)),
    FieldSpec("rc", "RC", "kΩ", "2.2", ALL_CIRCUITS),
    FieldSpec("re", "RE", "kΩ", "0.47", (CircuitType.VOLTAGE_DIVIDER, CircuitType.EMITTER_BIAS)),
    FieldSpec("beta", "β", "—", "150", ALL_CIRCUITS),
    FieldSpec("vbe", "VBE", "V", "0.7", ALL_CIRCUITS),
)
FIELD_DEFAULTS = {spec.name: spec.default for spec in FIELD_SPECS}

def resolve_circuit(value: str | None) -> CircuitType:
    try:
        return CircuitType((value or "").strip())
    except ValueError:
        return DEFAULT_CIRCUIT
```

Add a form helper:

```python
def _form_values(raw: Mapping[str, str], *, blank: bool = False) -> dict[str, str]:
    return {spec.name: ("" if blank else raw.get(spec.name, spec.default))
            for spec in FIELD_SPECS}
```

`GET /`:

```python
circuit = resolve_circuit(request.args.get("circuit"))
form = _form_values({}, blank=request.args.get("blank") == "1")
form["circuit"] = circuit.value
return render_template("index.html", fields=FIELD_SPECS, form=form, errors={},
                       analysis=None, region_labels=REGION_LABELS,
                       circuits=CIRCUIT_LABELS, selected_circuit=circuit,
                       result_circuit=None)
```

`POST /calculate`:

```python
raw = request.form.to_dict()
try:
    inp = parse_input(raw)
except ValidationError as error:
    circuit = resolve_circuit(raw.get("circuit"))
    form = _form_values(raw)
    form["circuit"] = circuit.value
    return render_template("index.html", fields=FIELD_SPECS, form=form,
                           errors=error.errors, analysis=None,
                           region_labels=REGION_LABELS, circuits=CIRCUIT_LABELS,
                           selected_circuit=circuit, result_circuit=circuit)
form = _form_values(raw)
form["circuit"] = inp.circuit.value
return render_template("index.html", fields=FIELD_SPECS, form=form, errors={},
                       analysis=analyze(inp), region_labels=REGION_LABELS,
                       circuits=CIRCUIT_LABELS, selected_circuit=inp.circuit,
                       result_circuit=inp.circuit)
```

Keep `format_quantity` and the `_QUANTITY_FORMATS` map unchanged. Register `css_name` as a Jinja global in `create_app()`:

```python
app.jinja_env.globals["css_name"] = css_name
```

Change the page title and brand heading to `Lab 03: BJT DC Bias Web App` and the subtitle to `ENG29 2121 – Common Emitter Bias Circuits`.

- [ ] **Step 4: Implement the template**

Keep the existing header, watermark, panel order, icons, and results styling. Add:

- A `fieldset.circuit-picker` above the fields with `legend` "Circuit type" and three `label.circuit-option` wrappers. Each radio:
  `name="circuit"`, `id="circuit-{{ css_name(value) }}"`, `value="{{ value.value }}"`, `{% if selected_circuit == value %} checked{% endif %}`.
- Render every field from `fields`, with `class="field {{ field.css_class }}"`, the label, note, input, unit, and per-field error. Add `"rb": "Base Resistor"` to `field_notes`.
- Three heading spans inside the circuit panel heading:
  `circuit-heading circuit-heading-{{ css_name(value) }}` for each circuit.
- Three `<figure class="diagram diagram-{{ css_name(value) }}">` schematics:
  - divider: existing SVG unchanged;
  - fixed: `VCC` rail, `RB` from `VCC` to base, `RC` from `VCC` to collector, NPN emitter directly to ground;
  - emitter: same as fixed plus `RE` from emitter to ground.
  Use unique `<title>`/`<desc>` ids per figure, the existing `wire`/`zigzag`/`transistor`/`node`/`arrow` classes, and the same 440×430 viewBox.
- Error summary: `class="error-summary{% if result_circuit %} error-summary-for-{{ css_name(result_circuit) }}{% endif %}"`.
- Region badge: add `result-region-for-{{ css_name(analysis.input.circuit) }}` when `analysis`.
- Results:
  - `{% if analysis %}` wrap the table, model line, status, and cross-check in `<div class="results-state results-for-{{ css_name(analysis.input.circuit) }}">`.
  - Add `<p class="result-circuit">Results for {{ circuits[analysis.input.circuit] }}</p>`.
  - Model line: "Thevenin base model" for the divider, "Base source model" otherwise.
  - Cross-check summary "Cross-check: Closed-form vs Nodal"; column headers "Closed-form" and "Nodal"; verdict "The closed-form and nodal solutions agree within tolerance."
  - After the result block, render a placeholder for every circuit that is not `analysis.input.circuit`:
    `<p class="results-placeholder results-placeholder-for-{{ css_name(value) }}">Press <strong>Calculate DC Bias</strong> to solve the {{ label }} circuit.</p>`.
  - When `analysis` is absent, keep the existing `results-empty` message.
- Reset row: three links, one per circuit:
  `<a class="reset-link reset-link-for-{{ css_name(value) }}" href="{{ url_for('index', blank=1, circuit=value.value) }}">Reset form</a>`.
- No `<script>` element and no inline event handler.

- [ ] **Step 5: Run the app tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_app.py -q`

Expected: pass. The CSS contract test arrives in Task 3.

- [ ] **Step 6: Commit**

```powershell
& "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe" add bjt_bias/app.py bjt_bias/templates/index.html bjt_bias/tests/test_app.py
& "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe" commit -m "feat: add circuit picker and per-circuit results markup"
```

---

### Task 3: CSS-only visibility and styling

**Files:**
- Modify: `bjt_bias/static/style.css`
- Modify: `bjt_bias/tests/test_app.py`

**Interfaces:**
- Consumes: the HTML classes from Task 2.
- Produces: the radio-driven visibility contract; no Python interface changes.

- [ ] **Step 1: Write the failing CSS contract test**

Add to `bjt_bias/tests/test_app.py`:

```python
from pathlib import Path

def test_css_contract_has_radio_state_rules():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text(encoding="utf-8")
    for circuit in ("voltage-divider", "fixed-bias", "emitter-bias"):
        assert f"#circuit-{circuit}:checked" in css
    for token in ("for-all", "diagram-", "circuit-heading-", "results-for-",
                  "results-placeholder-for-", "error-summary-for-",
                  "reset-link-for-", "result-region-for-"):
        assert token in css
    assert "<script" not in css
```

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_app.py::test_css_contract_has_radio_state_rules -q`

Expected: fail because the selectors are absent.

- [ ] **Step 2: Add the picker styles**

Append near the input-form section:

- `.circuit-picker` (no border, small margin), `.circuit-picker legend` (navy, semibold).
- `.circuit-options` grid with `gap: 0.35rem`.
- `.circuit-option` as a bordered row using `--line`, `--panel-bg`, `--gold-soft` on `:has(input:checked)`, `accent-color: var(--teal)`, pointer cursor, and a focus-visible outline using `--gold-deep`.
- At `max-width: 460px`, keep the options stacked (the default grid already is).

- [ ] **Step 3: Add the visibility rules**

Use these exact selectors:

```css
/* Fields */
body:has(#circuit-voltage-divider:checked) .field:not(.for-all):not(.for-voltage-divider),
body:has(#circuit-fixed-bias:checked) .field:not(.for-all):not(.for-fixed-bias),
body:has(#circuit-emitter-bias:checked) .field:not(.for-all):not(.for-emitter-bias) {
  display: none;
}

/* Diagrams */
.diagram { display: none; }
.diagram-voltage-divider { display: block; }
body:has(#circuit-fixed-bias:checked) .diagram-voltage-divider,
body:has(#circuit-emitter-bias:checked) .diagram-voltage-divider { display: none; }
body:has(#circuit-fixed-bias:checked) .diagram-fixed-bias { display: block; }
body:has(#circuit-emitter-bias:checked) .diagram-emitter-bias { display: block; }

/* Heading spans */
.circuit-heading { display: none; }
.circuit-heading-voltage-divider { display: inline; }
body:has(#circuit-fixed-bias:checked) .circuit-heading-voltage-divider,
body:has(#circuit-emitter-bias:checked) .circuit-heading-voltage-divider { display: none; }
body:has(#circuit-fixed-bias:checked) .circuit-heading-fixed-bias { display: inline; }
body:has(#circuit-emitter-bias:checked) .circuit-heading-emitter-bias { display: inline; }

/* Stale results and region badge */
body:has(#circuit-fixed-bias:checked) .results-for-voltage-divider,
body:has(#circuit-emitter-bias:checked) .results-for-voltage-divider,
body:has(#circuit-voltage-divider:checked) .results-for-fixed-bias,
body:has(#circuit-emitter-bias:checked) .results-for-fixed-bias,
body:has(#circuit-voltage-divider:checked) .results-for-emitter-bias,
body:has(#circuit-fixed-bias:checked) .results-for-emitter-bias,
body:has(#circuit-fixed-bias:checked) .result-region-for-voltage-divider,
body:has(#circuit-emitter-bias:checked) .result-region-for-voltage-divider,
body:has(#circuit-voltage-divider:checked) .result-region-for-fixed-bias,
body:has(#circuit-emitter-bias:checked) .result-region-for-fixed-bias,
body:has(#circuit-voltage-divider:checked) .result-region-for-emitter-bias,
body:has(#circuit-fixed-bias:checked) .result-region-for-emitter-bias {
  display: none;
}

/* Placeholders */
.results-placeholder { display: none; margin: 0; padding: 1.75rem 0.9rem;
  border: 1px dashed var(--line); border-radius: 8px; color: var(--muted);
  font-size: 0.9rem; text-align: center; }
body:has(#circuit-voltage-divider:checked) .results-placeholder-for-voltage-divider,
body:has(#circuit-fixed-bias:checked) .results-placeholder-for-fixed-bias,
body:has(#circuit-emitter-bias:checked) .results-placeholder-for-emitter-bias {
  display: block;
}

/* Error summary */
body:has(#circuit-fixed-bias:checked) .error-summary-for-voltage-divider,
body:has(#circuit-emitter-bias:checked) .error-summary-for-voltage-divider,
body:has(#circuit-voltage-divider:checked) .error-summary-for-fixed-bias,
body:has(#circuit-emitter-bias:checked) .error-summary-for-fixed-bias,
body:has(#circuit-voltage-divider:checked) .error-summary-for-emitter-bias,
body:has(#circuit-fixed-bias:checked) .error-summary-for-emitter-bias {
  display: none;
}

/* Reset links */
.reset-link { display: none; }
.reset-link-for-voltage-divider { display: inline; }
body:has(#circuit-fixed-bias:checked) .reset-link-for-voltage-divider,
body:has(#circuit-emitter-bias:checked) .reset-link-for-voltage-divider { display: none; }
body:has(#circuit-fixed-bias:checked) .reset-link-for-fixed-bias { display: inline; }
body:has(#circuit-emitter-bias:checked) .reset-link-for-emitter-bias { display: inline; }
```

Add `.result-circuit` styling (muted, small, margin) and keep the existing table/status/cross-check styles.

- [ ] **Step 4: Run the app tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_app.py -q`

Expected: pass, including the CSS contract test.

- [ ] **Step 5: Commit**

```powershell
& "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe" add bjt_bias/static/style.css bjt_bias/tests/test_app.py
& "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe" commit -m "feat: switch bias fields and diagrams with CSS radio state"
```

---

### Task 4: README, full suite, and browser verification

**Files:**
- Modify: `bjt_bias/README.md`

**Interfaces:**
- Consumes: all previous tasks.
- Produces: user-facing documentation and a verified working app.

- [ ] **Step 1: Update the README**

Cover:

- Title/intro: Lab 03, three NPN bias circuits, CSS-only selection, no JavaScript.
- What it does: circuit picker, per-circuit fields, closed-form + nodal cross-check, region warnings.
- Setup/run/test commands unchanged.
- Model assumptions: fixed `VBE` and `β`, no Early effect, `VCE(sat)=0.2 V`, saturation labelled not re-solved, cutoff rule.
- Formulas: voltage divider, fixed bias, emitter bias, shared outputs, and the three nodal systems.
- Validation matrix by circuit and the shared default table.
- Worked examples for all three circuits with the value sets from the design (§8.3).
- CSS-only mechanism, `:has()` browser support, and the graceful degradation when it is unsupported.
- Project layout (unchanged file list) and a note that `bias.py` has no Flask dependency.
- Replace any "44 passed" claim with the actual full-suite count after Step 2.

- [ ] **Step 2: Run the full suite**

Run: `.\.venv\Scripts\python.exe -m pytest -q`

Expected: all tests pass. Record the count for the README.

- [ ] **Step 3: Verify in the browser**

Open `http://127.0.0.1:5000` (the development server is already running; otherwise `.\.venv\Scripts\python.exe app.py`). Check:

- Voltage divider: R1/R2/RC/RE visible; RB hidden; divider schematic visible.
- Fixed bias: RB/RC visible; R1/R2/RE hidden; fixed schematic visible; submitting shows `IC=3.606 mA`, `VCE=4.066 V`, forward active, cross-check agrees.
- Emitter bias: RB/RC/RE visible; R1/R2 hidden; emitter schematic visible; submitting shows `IC=3.133 mA`, `VCE=3.624 V`, forward active, cross-check agrees.
- Flip the radio after a submit: the old results, region badge, and reset link disappear and the matching placeholder appears.
- Trigger an error (VD `R1=0`), then flip to Fixed Bias: the R1 error and summary disappear; flipping back restores them.
- No JavaScript is required; the page works with the network disabled.

- [ ] **Step 4: Commit**

```powershell
& "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe" add bjt_bias/README.md
& "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe" commit -m "docs: document multi-circuit BJT bias app"
```

---

## Self-Review

**Spec coverage:** Circuit enum/validation (Task 1), three closed-form solvers (Task 1), three nodal solvers and analysis dispatch (Task 1), circuit metadata/routing (Task 2), picker/fields/diagrams/results/reset markup (Task 2), CSS-only visibility and stale-state hiding (Task 3), no-JS guard (Task 2), CSS contract (Task 3), README and browser verification (Task 4). The shared defaults, unknown GET/POST behavior, cutoff rules, and region thresholds are pinned in Task 1 and Task 2.

**Step scan:** Every test step names the test and its assertions; every implementation step names exact signatures, classes, selectors, or values. No step leaves a signature or selector to guess.

**Type consistency:** `CircuitType` values, `BiasInput` field order, `CIRCUIT_FIELDS`, `FieldSpec.css_class`, route context names, and HTML class suffixes are used consistently in Tasks 1–3. CSS suffixes use hyphens (`for-fixed-bias`, `results-for-fixed-bias`) while enum values use underscores; `css_name()` performs that conversion in one place and is registered as a Jinja global.

**Review Focus coverage:** Hidden stale values (Task 1 parse tests), stale UI after radio flip (Tasks 2–3), fixed-bias no-RE nodal path (Task 1 golden and nodal tests), fixed/emitter cutoff (Task 1 cutoff tests), and `:has()` degradation/no-JS (Task 2 no-JS test, Task 3 CSS contract, Task 4 browser check).

**Proportion:** The plan carries decisions (signatures, exact equations, class names, selectors, golden values) rather than full function bodies; the largest code blocks are the test fixtures and the CSS contract, both of which are the decisions.
