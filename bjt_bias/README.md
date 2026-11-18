# BJT DC Bias Calculator (ENG29 2121 — Lab 03)

A small Flask web app that solves the DC operating point of three NPN
common-emitter bias circuits:

- **Voltage Divider Bias**
- **Fixed Bias**
- **Emitter Bias**

The circuit is chosen with a radio group. The matching resistor inputs and
schematic switch instantly using CSS only — no JavaScript, no CDN, no build
step, no database. Every result is shown with an explicit unit, the app warns
when the transistor is not in forward-active mode, and the answer is
cross-checked against a second, independently coded calculation (nodal
analysis).

## What it does

- Lets the user choose the circuit with a radio group at the top of the
  Input Parameters panel.
- Shows only the resistors that circuit uses, plus the shared `VCC`, `β` and
  `VBE` fields.
- Accepts `VCC`, the circuit's resistors, `beta` (β) and `VBE`. Resistances
  are in kΩ, voltages in V.
- Computes `IB`, `IC`, `IE`, `VCE`, `VB`, `VC`, `VE`, plus the base source
  model values `VBB` and `RB`.
- Classifies the operating point as **Cut-off**, **Saturation**,
  **Near saturation** or **Forward active**, and warns when the active-region
  model is not valid.
- Solves the circuit a second time by nodal analysis, coded separately from
  the closed-form solution, and shows both with the absolute and relative
  difference for each quantity.
- Rejects invalid input with per-field messages and never returns a server
  error for bad input.

Server-rendered HTML, no JavaScript, no CDN, no build step, no database.

## Requirements

- **Python 3.12 or newer.** The original project targeted 3.12; the current
  suite was verified on 3.15.2.
- The packages in `requirements.txt`: `Flask>=3.0,<4` and `pytest>=8.0,<9`.
- A browser on the same machine.

## Setup

Run these commands from the `bjt_bias/` directory.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run

```powershell
.\.venv\Scripts\python.exe app.py
```

Then open <http://127.0.0.1:5000> in a browser.

The form is prefilled with the shared defaults below, so all three circuits
run immediately. Selecting a circuit only changes which fields and schematic
are shown; it does not change the numeric values.

Routes:

| Route | Method | Purpose |
| --- | --- | --- |
| `/` | GET | Render the input form. `/?circuit=<circuit>` pre-selects a radio; `/?blank=1` clears the numeric fields. |
| `/calculate` | POST | Validate the posted fields and render the results or the field errors on the same page. |

An unknown `circuit` on `GET` falls back to Voltage Divider Bias. An unknown
`circuit` on `POST` is a form error, not a server error. A `POST` with no
`circuit` field defaults to Voltage Divider Bias, preserving the original form
contract. Reset links use `/?blank=1&circuit=<circuit>`, so clearing values
keeps the selected circuit.

## Test

From `bjt_bias/`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: `80 passed`.

## Circuits

All resistances are in kΩ at the input edge and Ω internally. `VCC`, `VBE`
and `β` are shared. The transistor is an NPN in common-emitter configuration.

### Voltage divider bias

`R1` from `VCC` to the base, `R2` from base to ground, `RC` from `VCC` to the
collector, and `RE` from the emitter to ground. The base divider is replaced
by its Thevenin equivalent:

```
VBB = VCC * R2 / (R1 + R2)
RB  = R1 * R2 / (R1 + R2)
IB  = (VBB - VBE) / (RB + (beta + 1) * RE)
```

### Fixed bias

`RB` from `VCC` to the base, `RC` from `VCC` to the collector, and the emitter
grounded directly (`RE = 0`):

```
VBB = VCC
RB  = RB
IB  = (VCC - VBE) / RB
```

### Emitter bias

`RB` from `VCC` to the base, `RC` from `VCC` to the collector, and `RE` from
the emitter to ground:

```
VBB = VCC
RB  = RB
IB  = (VCC - VBE) / (RB + (beta + 1) * RE)
```

### Shared output equations

Once `IB` is known, for every circuit:

```
IC  = beta * IB
IE  = (beta + 1) * IB
VE  = IE * RE          (RE = 0 for fixed bias)
VB  = VE + VBE
VC  = VCC - IC * RC
VCE = VC - VE
```

## Model and assumptions

The model is deliberately simple and every assumption is stated here and in
the app:

- **Fixed `VBE`.** `VBE` is a constant input, not a solved quantity. It must
  be between 0.4 V and 0.9 V.
- **Constant `beta`.** The current gain is a constant input, not a function
  of collector current. It must be between 1 and 10000.
- **No Early effect.** Output resistance is ignored, so `IC` does not depend
  on `VCE`. There is no recombination detail and the resistors are ideal.
- **`VCE(sat) = 0.2 V` is a fixed constant**, not an input field.
- **Saturation is warned about, never re-solved.** When `VCE` falls to or
  below 0.2 V the active-region solution is an extrapolation, so the app
  labels the region, shows the warning, and displays the numbers anyway. It
  does not re-solve with a clamped `VCE`, and it does not switch to a
  saturation model.
- **The cross-check is a nodal analysis** of the same linear circuit,
  written independently of the closed-form algebra. The two results are
  compared at a **0.1 % relative tolerance**; a row also passes when its
  absolute difference is at most 1e-9 in SI units, which is the fallback for
  a quantity whose closed-form reference is effectively zero. The closed-form
  value is the reference and the nodal value is the candidate. Because both
  methods solve the same model exactly, agreement is expected down to
  floating-point noise; the 0.1 % threshold is loose enough to be meaningful
  and tight enough to catch a transcription error.
- **Cut-off is a result, not an input error.** If `VBB <= VBE` the transistor
  is off: `IB = IC = IE = 0`, `VE = 0`, `VB = VBB`, `VC = VCC`, `VCE = VCC`,
  and the cross-check is reported as not applicable. For fixed and emitter
  bias this condition reduces to `VCC <= VBE`.
- All internal arithmetic is in SI units (Ω, A, V). Conversion to kΩ, µA, mA
  and V happens only at the input and display edges.

## Input validation

Every field used by the selected circuit is required and must parse as a
finite number. Fields that the selected circuit does not use are not parsed
at all: they may be blank or contain stale text and cannot affect the result.

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

Range rules: `VCC > 0`; every used resistance `> 0 kΩ`;
`1 <= beta <= 10000`; `0.4 <= VBE <= 0.9 V`. All errors for the selected
circuit are reported together, and the submitted values are preserved in the
re-rendered form.

## Shared defaults

One default set serves all circuits. It was chosen so each circuit starts
forward active and so the original voltage-divider example remains the
prefilled demo.

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

Field order on the page is `VCC, R1, R2, RB, RC, RE, β, VBE`. All fields are
rendered on every page so the CSS can reveal them without a request.

## Nodal cross-check

With the unknown vector `x = [VB, VE, VC]`, each circuit builds its own
system `A x = b` from KCL and the `VBE` constraint. The closed-form current
equations are not reused.

### Voltage divider

```
Row 1 (KCL at base):     VB*(1/R1 + 1/R2) - VC/(beta*RC)
                         = VCC/R1 - VCC/(beta*RC)
Row 2 (KCL at emitter):  VE/RE + VC*(1 + 1/beta)/RC
                         = VCC*(1 + 1/beta)/RC
Row 3 (VBE):             VB - VE = VBE
```

### Fixed bias

```
Row 1 (KCL at base):     VB/RB - VC/(beta*RC) = VCC/RB - VCC/(beta*RC)
Row 2 (grounded emitter): VE = 0
Row 3 (VBE):             VB - VE = VBE
```

### Emitter bias

```
Row 1 (KCL at base):     VB/RB - VC/(beta*RC) = VCC/RB - VCC/(beta*RC)
Row 2 (KCL at emitter):  VE/RE + VC*(1 + 1/beta)/RC
                         = VCC*(1 + 1/beta)/RC
Row 3 (VBE):             VB - VE = VBE
```

Each system is solved with Gaussian elimination with partial pivoting. Then
the currents and `VCE` are recovered from the node voltages:

```
IC  = (VCC - VC) / RC
IB  = IC / beta
IE  = IB + IC
VCE = VC - VE
```

`IB`, `IC`, `IE`, `VCE`, `VB`, `VC` and `VE` are compared quantity by
quantity: both values, the absolute difference, the relative difference, and a
per-row pass/fail verdict at 0.1 % relative tolerance. The app also prints an
overall verdict.

## Region rules

The rules are applied in this order, using the closed-form result:

1. **Cut-off** if `VBB <= VBE`. `IB = IC = IE = 0`, `VE = 0`, `VB = VBB`,
   `VC = VCC`, `VCE = VCC`. The cross-check is not applicable.
2. **Saturation** if `VCE <= 0.2 V` (`VCE(sat)`). The numbers are shown, but
   the warning states that the active-region model is invalid and that the
   values are an extrapolation, not a physical operating point.
3. **Near saturation** if `0.2 V < VCE < 0.5 V`. A caution is shown.
4. **Forward active** otherwise (`VCE >= 0.5 V`).

## Worked examples

The values the app is prefilled with, and the golden test cases. The examples
are shown to more digits than the app's four-significant-figure display.

### Voltage divider (the original Lab 02 example)

```
VCC = 12 V, R1 = 47 kΩ, R2 = 10 kΩ, RC = 2.2 kΩ, RE = 0.47 kΩ,
beta = 150, VBE = 0.7 V
```

```
VBB = 2.105263 V   RB = 8.245614 kΩ
IB  = 17.7397 µA   IC = 2.66096 mA   IE = 2.67870 mA
VE  = 1.25899 V    VB = 1.95899 V    VC = 6.14589 V
VCE = 4.88690 V    -> forward active
```

### Fixed bias

```
VCC = 12 V, RB = 470 kΩ, RC = 2.2 kΩ, beta = 150, VBE = 0.7 V
```

```
IB  = 24.0426 µA   IC = 3.60638 mA   IE = 3.63043 mA
VE  = 0 V          VB = 0.7 V        VC = 4.06596 V
VCE = 4.06596 V    -> forward active
```

### Emitter bias

```
VCC = 12 V, RB = 470 kΩ, RC = 2.2 kΩ, RE = 0.47 kΩ,
beta = 150, VBE = 0.7 V
```

```
IB  = 20.8884 µA   IC = 3.13326 mA   IE = 3.15415 mA
VE  = 1.48245 V    VB = 2.18245 V    VC = 5.10683 V
VCE = 3.62438 V    -> forward active
```

In every case the nodal cross-check agrees with the closed-form solution on
every quantity, with differences at floating-point noise level and far inside
the 0.1 % tolerance.

## How the CSS-only switching works

All fields, schematics, headings and reset links for all three circuits are
present in the HTML on every page. After a POST the server renders only the
last submitted circuit's result block (or its error summary), plus a
placeholder for each other circuit. The radio group carries the selected
circuit.

CSS `:has()` rules keyed on the radio ids hide everything that does not match
the checked circuit:

```css
body:has(#circuit-fixed-bias:checked) .field:not(.for-all):not(.for-fixed-bias) {
  display: none;
}
```

The same mechanism:

- swaps the visible schematic and heading,
- hides stale results, the region badge and the error summary after the user
  flips the radio,
- shows the matching "Press Calculate DC Bias…" placeholder after a successful
  calculation (after a validation error the generic empty-state message stays
  visible while the error summary and its fields hide),
- shows only the reset link for the selected circuit.

The server dispatches on the posted `circuit` value, so routing and
calculation do not depend on CSS; only presentation does.

**Browser support.** `:has()` is supported by current Chrome, Edge, Safari
and Firefox. In a browser without `:has()` support, all fields stay visible
and the form still submits a valid circuit. The default rules keep the
voltage-divider schematic, heading and reset link on screen, so the drawing
may not match the selected circuit, but the server still calculates whichever
circuit was posted. The page needs no JavaScript.

## Project layout

```
bjt_bias/
  app.py              # create_app(); GET / ; POST /calculate ; dev main
  bias.py             # validation, closed-form solvers, nodal solvers, compare
  templates/
    index.html        # one page: picker, form, three schematics, results
  static/
    style.css         # plain CSS, no build step
    sut-logo.svg      # SUT watermark used by the header/background
  tests/
    test_bias.py      # validation, solving, classification, comparison
    test_app.py       # routes, rendering, escaping, CSS contract
  requirements.txt    # Flask and pytest with version bounds
  pytest.ini          # pythonpath = . ; testpaths = tests
  README.md           # this file
```

`bias.py` holds the engineering logic as pure functions and imports no
Flask. `app.py` is the Flask application factory; `create_app()` is exposed
so the tests can build an app instance, and the `__main__` block runs the
development server on <http://127.0.0.1:5000>.
