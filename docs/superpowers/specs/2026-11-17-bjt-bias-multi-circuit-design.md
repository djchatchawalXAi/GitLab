# BJT DC Bias Web App — Multi-Circuit Support (Lab 03) — Design

- Course: ENG29 2121
- Date: 2026-11-17
- Status: awaiting approval
- App location: `bjt_bias/` (extends the Lab 02 app in place)
- Supersedes: `2026-11-10-bjt-ce-bias-webapp-design.md` for the parts this
  document changes; the Lab 02 document stays as the record of the original
  voltage-divider build.

## 1. Intent and why

Lab 02 solved one NPN bias circuit (voltage divider). Lab 03 asks students to
compare three DC bias circuits. The app must let the user choose the circuit,
show only the resistors that circuit uses, draw the matching schematic, and
solve with that circuit's equations — while keeping the existing SUT
orange/gold, three-column look and the no-JavaScript, no-build-step promise.

The pedagogical point is unchanged: the closed-form result is the reference
and an independently written nodal solution is the cross-check. Adding two
more circuits must not turn the cross-check into the same algebra twice.

## 2. Goals

- Choose **Voltage Divider Bias**, **Fixed Bias**, or **Emitter Bias** with a
  radio group in the Input Parameters panel.
- Show only the relevant resistor inputs, using CSS only:
  - Voltage divider: `R1`, `R2`, `RC`, `RE`
  - Fixed bias: `RB`, `RC`
  - Emitter bias: `RB`, `RC`, `RE`
  - Shared in every circuit: `VCC`, `β`, `VBE`
- Parse and validate only the fields the selected circuit uses.
- Solve each circuit with its own closed-form equation.
- Cross-check each circuit with its own nodal system, built from KCL rather
  than from the closed-form result.
- Switch the schematic live, before submission, so the drawing matches the
  selected radio.
- Keep the existing region classification, warnings, per-field validation,
  unit handling, SUT styling, and three-column layout.
- Keep the page free of JavaScript.

## 3. Non-goals

- No AC, small-signal, transient, load-line, or frequency analysis.
- No four-resistor bias, collector-feedback bias, or FET circuits.
- No user-selectable `VCE(sat)`.
- No database, authentication, session state, deployment, or CI.
- No JavaScript, CDN, bundler, or CSS framework.
- No re-solving a saturated circuit with a clamped `VCE`.

## 4. Anti-goals

- A circuit selector that only relabels the page but still runs the
  voltage-divider equations.
- A cross-check that copies values from the closed-form solve and therefore
  always agrees by construction.
- A hidden input whose value silently changes the selected circuit's result.
- A layout that breaks the three-column desktop arrangement or the
  orange/gold identity.

## 5. Approaches considered

### A. Pure CSS radio state with `:has()` — chosen

All fields for all three circuits are always in the HTML. Radio inputs carry
the circuit state. `body:has(#circuit-…:checked)` selectors hide the fields,
headings, and schematics that do not match, and reveal the ones that do. The
server reads the posted radio value and dispatches to the matching solver.

- **Wins:** no JavaScript, instant switching, works offline, hidden fields
  keep their values when the user toggles back, one page, no new dependency.
- **Costs:** the HTML contains every field and schematic, and browsers without
  `:has()` show everything (graceful degradation: the server still calculates
  whichever circuit was posted).

### B. Small vanilla JavaScript toggle — rejected

Less markup and simpler selectors, but the page would now require JavaScript
and would contradict the Lab 02 constraint and README promise.

### C. Server round-trip on selection — rejected

A "Load circuit" button would need a submit/reload per change, which is not
the requested dynamic behaviour and adds a route just for selecting a circuit.

## 6. Circuit models

All resistances are in kΩ at the input edge and Ω internally. `VCC`, `VBE`,
`β` are shared. `VCE(sat) = 0.2 V` stays a constant.

### 6.1 Voltage divider bias (unchanged model)

```
VBB = VCC * R2 / (R1 + R2)
RB  = R1 * R2 / (R1 + R2)
IB  = (VBB - VBE) / (RB + (beta + 1) * RE)
```

### 6.2 Fixed bias

The base is fed from `VCC` through `RB`; the emitter is grounded, so `RE = 0`.

```
VBB = VCC
RB  = RB
IB  = (VCC - VBE) / RB
```

This is the same base-loop equation with `RE = 0`, but it is coded as its own
function so the equation shown to students is the fixed-bias equation.

### 6.3 Emitter bias

The base is fed from `VCC` through `RB`, and the emitter has `RE`.

```
VBB = VCC
RB  = RB
IB  = (VCC - VBE) / (RB + (beta + 1) * RE)
```

### 6.4 Shared output equations

For all three circuits, once `IB` is known:

```
IC  = beta * IB
IE  = (beta + 1) * IB
VE  = IE * RE          (RE = 0 for fixed bias)
VB  = VE + VBE
VC  = VCC - IC * RC
VCE = VC - VE
```

`OperatingPoint` keeps its current fields. `vbb_v` and `rb_ohm` carry the base
source model:

- voltage divider: the Thevenin values `VBB` and `RB`
- fixed bias: `VBB = VCC`, `RB = RB` (in Ω)
- emitter bias: `VBB = VCC`, `RB = RB` (in Ω)

### 6.5 Cutoff rule

Cutoff when `VBB <= VBE`, which is the existing rule. For fixed and emitter
bias this reduces to `VCC <= VBE`. In cutoff:

```
IB = IC = IE = 0, VE = 0, VB = VBB, VC = VCC, VCE = VCC
```

and the cross-check is not applicable, exactly as in Lab 02.

### 6.6 Region classification

Unchanged and applied in this order:

1. Cutoff: `VBB <= VBE`.
2. Saturation: `VCE <= 0.2 V`, with the existing extrapolation warning.
3. Near saturation: `0.2 V < VCE < 0.5 V`.
4. Forward active: otherwise.

## 7. Independent nodal cross-check

Unknown vector `x = [VB, VE, VC]`. The systems below are written from KCL and
the `VBE` constraint; the closed-form current equations are not reused.

### Voltage divider

```
Row 1 (KCL at base):     VB*(1/R1 + 1/R2) - VC/(beta*RC) = VCC/R1 - VCC/(beta*RC)
Row 2 (KCL at emitter):  VE/RE + VC*(1 + 1/beta)/RC       = VCC*(1 + 1/beta)/RC
Row 3 (VBE):             VB - VE                          = VBE
```

### Fixed bias

```
Row 1 (KCL at base):     VB/RB - VC/(beta*RC) = VCC/RB - VCC/(beta*RC)
Row 2 (emitter grounded): VE                  = 0
Row 3 (VBE):             VB - VE              = VBE
```

### Emitter bias

```
Row 1 (KCL at base):     VB/RB - VC/(beta*RC) = VCC/RB - VCC/(beta*RC)
Row 2 (KCL at emitter):  VE/RE + VC*(1 + 1/beta)/RC = VCC*(1 + 1/beta)/RC
Row 3 (VBE):             VB - VE              = VBE
```

Each system is solved by the existing Gaussian elimination with partial
pivoting. Then:

```
IC  = (VCC - VC) / RC
IB  = IC / beta
IE  = IB + IC
VCE = VC - VE
```

The comparison remains quantity by quantity at 0.1 % relative tolerance with
the 1e-9 SI absolute fallback. The closed-form value is the reference and the
nodal value is the candidate. The UI labels the columns **Closed-form** and
**Nodal** because "Thevenin" is only accurate for the divider circuit.

## 8. Input, validation, and defaults

### 8.1 Circuit type

- Enum `CircuitType(str, Enum)`:
  `VOLTAGE_DIVIDER = "voltage_divider"`, `FIXED_BIAS = "fixed_bias"`,
  `EMITTER_BIAS = "emitter_bias"`.
- GET `/` defaults to voltage divider.
- `GET /?circuit=<unknown>` silently falls back to voltage divider; a query
  string is not submitted form data and must not produce an error page.
- A POST with no `circuit` key defaults to voltage divider, preserving the
  Lab 02 form contract.
- An unknown `circuit` value in a POST is a form error ("Choose a valid
  circuit type"), not a 500.
- One shared helper, `resolve_circuit(value, *, strict)`, is used by both
  routes: lenient on GET (fallback to the default), strict on POST (raise
  `ValidationError({"circuit": ...})`).

### 8.2 Fields per circuit

| Field | Voltage divider | Fixed bias | Emitter bias |
| --- | --- | --- | --- |
| `VCC` | required | required | required |
| `R1` | required | ignored | ignored |
| `R2` | required | ignored | ignored |
| `RB` | ignored | required | required |
| `RC` | required | required | required |
| `RE` | required | ignored | required |
| `β` | required | required | required |
| `VBE` | required | required | required |

Ignored fields are neither required nor parsed for range errors. They may be
blank or contain stale text; they cannot affect the selected circuit's result.

Range rules are unchanged: `VCC > 0`; every used resistance `> 0 kΩ`;
`1 <= β <= 10000`; `0.4 V <= VBE <= 0.9 V`. All errors for the selected
circuit are reported together, and submitted values are preserved.

### 8.3 Shared defaults and prefills

One `FIELD_DEFAULTS` set serves all circuits, because every field is in one
form and must keep the same value when the radio changes without a request:

| Field | Default |
| --- | --- |
| `VCC` | 12 V |
| `R1` | 47 kΩ |
| `R2` | 10 kΩ |
| `RB` | 470 kΩ |
| `RC` | 2.2 kΩ |
| `RE` | 0.47 kΩ |
| `β` | 150 |
| `VBE` | 0.7 V |

The set was chosen so all three circuits start forward active, and so the
existing Lab 02 divider example stays the prefilled demo. `?circuit=X` only
checks the radio; it does not change numeric values. `?blank=1` clears every
numeric field, and `?blank=1&circuit=X` clears them with circuit X selected.

Per-circuit worked examples (the divider and fixed-bias examples are the
prefilled values; the emitter example uses the same shared defaults so the
demo is consistent):

- **Voltage divider (unchanged Lab 02 example):**
  `VCC=12, R1=47, R2=10, RC=2.2, RE=0.47, β=150, VBE=0.7`
  → forward active, `VCE = 4.8869 V`.
- **Fixed bias:**
  `VCC=12, RB=470, RC=2.2, β=150, VBE=0.7`
  → `IB = 24.0426 µA`, `IC = 3.60638 mA`, `IE = 3.63043 mA`,
  `VC = VCE = 4.06596 V`, `VB = 0.7 V`, `VE = 0 V`; forward active.
- **Emitter bias:**
  `VCC=12, RB=470, RC=2.2, RE=0.47, β=150, VBE=0.7`
  → `IB = 20.8884 µA`, `IC = 3.13326 mA`, `IE = 3.15415 mA`,
  `VE = 1.48245 V`, `VB = 2.18245 V`, `VC = 5.10683 V`,
  `VCE = 3.62438 V`; forward active.

All seven resistor fields plus the shared fields are rendered on every page so
the CSS can reveal them without a request. Field order is
`VCC, R1, R2, RB, RC, RE, β, VBE`, which keeps the visible order sensible for
each circuit. Fields not submitted in a POST are re-rendered with their
defaults, so toggling circuits after a validation error shows usable values.

## 9. UI and CSS-only behaviour

### 9.1 Circuit picker

A `fieldset.circuit-picker` with a `legend` and three radio labels at the top
of the Input Parameters panel:

```
( ) Voltage Divider Bias   ( ) Fixed Bias   ( ) Emitter Bias
```

Radio inputs use stable ids and values:
`circuit-voltage-divider`, `circuit-fixed-bias`, `circuit-emitter-bias`.
The selected radio is `checked` server-side from the submitted/queried
circuit, so a POST round-trip keeps the selection.

### 9.2 Field visibility

Each `.field` gets one or both of the classes `for-voltage-divider`,
`for-fixed-bias`, `for-emitter-bias`, or `for-all` for shared fields
(`VCC`, `RC`, `β`, `VBE`).

```css
body:has(#circuit-voltage-divider:checked) .field:not(.for-all):not(.for-voltage-divider),
body:has(#circuit-fixed-bias:checked)      .field:not(.for-all):not(.for-fixed-bias),
body:has(#circuit-emitter-bias:checked)    .field:not(.for-all):not(.for-emitter-bias) {
  display: none;
}
```

Without `:has()` support no field is hidden and no behaviour is lost on the
server; the page degrades to showing all inputs.

### 9.3 Schematic

The circuit panel contains three `<figure>` elements in the DOM:

- `.diagram-voltage-divider` — the existing schematic, unchanged.
- `.diagram-fixed-bias` — `VCC` rail, `RB` from `VCC` to base, `RC` from `VCC`
  to collector, NPN emitter directly to ground.
- `.diagram-emitter-bias` — `VCC` rail, `RB` from `VCC` to base, `RC` to
  collector, `RE` from emitter to ground.

All reuse the existing wire, zigzag, transistor, node, arrow, `.designator`
and `.sub` styles. Default display is voltage divider; `body:has(...)` rules
swap the visible figure. The panel heading has three spans (one per circuit)
toggled by the same radio state, so it reads
"Circuit: Voltage Divider Bias", "Circuit: Fixed Bias", or
"Circuit: Emitter Bias".

Schematic value labels read from the preserved form values:
`R1/R2` for the divider, `RB` for fixed/emitter, `RC`/`RE` where present.

### 9.4 Results, errors, and the radio after a POST

The server renders only the selected circuit's result after a POST, tagged
with that circuit:

- `.results-for-voltage-divider`, `.results-for-fixed-bias`, or
  `.results-for-emitter-bias` around the table, status, and cross-check.
- `.error-summary-for-<circuit>` on the error summary.
- A per-circuit placeholder, `.results-placeholder-for-<circuit>`, that says
  "Press Calculate DC Bias to solve the … circuit."

CSS `:has()` rules keep these in step with the radio, using the same mechanism
as the fields:

- When the checked radio matches the last submitted circuit, show its results
  (or its error summary) and hide the placeholders.
- When the user flips to a different circuit, hide the stale results and error
  summary and show that circuit's placeholder. The previous numeric values
  stay in the form, so the student can calculate the new circuit immediately.
- When no calculation has run yet, only the generic empty-state message is
  shown.

This prevents a divider result or a "fix R1" error from sitting under a Fixed
Bias selection. It needs no extra route or request.

The results panel keeps the region badge, the seven-quantity table, the model
line, the status warning, and the cross-check. The model line reads
"Thevenin base model" for the divider and "Base source model" for fixed and
emitter bias. A caption names the circuit the displayed result belongs to.

### 9.5 Reset

Three reset links are rendered, one per circuit, each
`/?blank=1&circuit=<circuit>`. The same `:has()` rules show only the link for
the checked circuit, so clearing values never silently switches the user back
to the divider.

### 9.6 Styling

The radio group uses the existing palette: `--gold-soft` / `--gold` for the
selected option, `--teal` accent, `--line` borders, `--navy` labels. The
three-column grid (`.layout`) and responsive breakpoints are untouched.

## 10. Code structure

### `bias.py`

- `CircuitType` enum.
- `BiasInput` gains `circuit` and optional circuit-specific resistors:
  `circuit, vcc_v, r1_kohm, r2_kohm, rb_kohm, rc_kohm, re_kohm, beta, vbe_v`.
  Unused resistors are `None`.
- `CIRCUIT_FIELDS: dict[CircuitType, tuple[str, ...]]` drives validation.
- `parse_input(raw)` determines the circuit, validates only its fields, and
  raises `ValidationError` with per-field messages (plus `circuit` for an
  unknown value).
- `solve_voltage_divider`, `solve_fixed_bias`, `solve_emitter_bias` — explicit
  closed-form paths sharing only `_point_from_ib`.
- `solve_nodal_voltage_divider`, `solve_nodal_fixed_bias`,
  `solve_nodal_emitter_bias`, each building its own `A` and `b`; shared
  `_solve_linear_3x3`.
- `analyze(inp)` dispatches on `inp.circuit`, applies the cutoff rule, then
  classifies and compares.
- `compare` and `classify` unchanged.

`bias.py` keeps importing no Flask and doing no I/O.

### `app.py`

- `CircuitType` imported from `bias`. `resolve_circuit(value, *, strict)` is a
  small app helper (lenient for GET, strict for POST).
- `CIRCUIT_LABELS`, `FieldSpec` metadata (name, label, unit, default, circuit
  classes), and `FIELD_DEFAULTS`.
- `create_app()`:
  - `GET /` resolves `circuit` leniently, reads `blank`, and renders all
    fields, all three diagrams, and all three reset links.
  - `POST /calculate` resolves `circuit` strictly and parses the raw form;
    on success it renders `analyze(inp)` tagged with the result's circuit, and
    on failure the tagged error summary plus preserved values.
- `format_quantity` unchanged.

### `templates/index.html`

- Circuit radio group.
- All seven resistor fields plus shared fields, each with visibility classes
  and a default value.
- Three schematics and three heading spans.
- Results tagged per circuit, per-circuit placeholders, a tagged error
  summary, and three reset links.
- Results with active-circuit caption and Closed-form/Nodal labels.
- No `<script>` element and no inline event handlers.

### `static/style.css`

- `.circuit-picker` styles.
- Field, diagram, heading, result, error-summary, placeholder, and reset-link
  visibility rules using `:has()`.
- Small additions for the result caption; no layout rewrite.

### `tests/`

- `test_bias.py` updated for the new `BiasInput`, plus per-circuit golden
  values, validation, cutoff, classification, and nodal agreement.
- `test_app.py` updated for radios, all-circuit markup, per-circuit POST
  results, defaults, reset link, and a no-JavaScript guard.

### `README.md`

Updated to describe Lab 03, the three circuits, per-circuit equations,
validation matrix, examples, and the CSS-only switching mechanism.

## 11. Test plan

- Parse/validate each circuit: required fields succeed; missing required field
  errors; ignored fields are ignored even when blank or invalid text.
- Golden values for all three circuits at 1e-6 relative, including the
  emitter example built from the shared defaults.
- Nodal agreement for a parametrised grid across all three circuits.
- Comparator still detects an injected 1 % error.
- Cutoff for each circuit (`VBB <= VBE`; fixed/emitter use `VCC <= VBE`).
- Saturation and near-saturation for fixed and emitter circuits as well as the
  divider.
- Region boundaries unchanged.
- App: GET shows three radios and all fields/diagrams; default is voltage
  divider; `?circuit=fixed_bias` checks the right radio without changing the
  shared numeric defaults; `?circuit=<unknown>` falls back to the divider.
- App: POST each circuit returns the right caption, result values, and the
  selected circuit's semantics.
- App: invalid input per circuit returns 200, preserves values, and shows
  errors; empty body does not 500; unknown POST circuit returns a form error.
- App: the page contains tagged result blocks, per-circuit placeholders, a
  tagged error summary, and three reset links, so the stale-state CSS has the
  markup it needs.
- App: markup is escaped.
- App: no `<script>` tag and no inline `on*=` handler appears in the page.
- CSS contract: `style.css` contains `:has(` rules keyed on all three radio
  ids for fields, diagrams, headings, results, error summary, placeholders,
  and reset links, so the CSS-only switching cannot silently disappear.
- Manual browser check: toggle radios and confirm fields, heading, and
  schematic swap before submit; submit each circuit and confirm results.

## 12. Definition of done

- `pytest -q` green (existing suite plus the new cases).
- `python app.py` serves the page; all three circuits can be selected and
  calculated; the schematic and fields switch without a reload.
- No JavaScript is shipped.
- SUT orange/gold theme and the three-column desktop layout are visually
  unchanged apart from the new picker.
- README reflects Lab 03 and the three circuits.

## 13. Risks and mitigations

- **`:has()` support.** Modern Chrome, Edge, Safari, and Firefox support it.
  Without it, all fields stay visible and the server still routes correctly;
  the feature degrades but does not error.
- **Hidden stale inputs.** Only the selected circuit's fields are parsed, so
  stale text in hidden fields cannot affect the result. A test covers this.
- **Class/enum drift.** The field visibility class and the enum value must
  match (`for-fixed-bias` ↔ `fixed_bias`). The CSS contract test and app tests
  cover it.
- **Equation duplication.** Fixed and emitter bias share the base-loop shape
  but are kept as named functions so each equation is explicit and teachable;
  the shared output helper is limited to the output relations.

## 14. Left to the builder

- Exact SVG geometry for the two new schematics, within the existing
  440×430 viewBox and symbol styles.
- Exact wording and spacing of the radio group and result caption.
- Whether the circuit picker is a vertical stack or a three-across row at
  desktop widths (must remain usable at 460 px).
- Test names and parametrisation details.
