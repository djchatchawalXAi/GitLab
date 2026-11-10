# BJT Common-Emitter DC Bias Calculator (ENG29 2121)

A small Flask web app that solves the DC operating point of an NPN
voltage-divider common-emitter bias circuit, shows every result with an
explicit unit, warns when the transistor is not in forward-active mode, and
cross-checks the answer against a second, independently coded calculation
(nodal analysis).

## What it does

- Accepts seven inputs: `VCC`, `R1`, `R2`, `RC`, `RE`, `beta` (β) and `VBE`.
  Resistances are in kΩ, voltages in V.
- Computes `IB`, `IC`, `IE`, `VCE`, `VB`, `VC`, `VE`, plus the base Thevenin
  model `VBB` and `RB`.
- Classifies the operating point as **Cut-off**, **Saturation**,
  **Near saturation** or **Forward active**, and warns when the active-region
  model is not valid.
- Solves the circuit a second time by nodal analysis, coded separately from
  the Thevenin solution, and shows both with the absolute and relative
  difference for each quantity.
- Rejects invalid input with per-field messages and never returns a server
  error for bad input.

Server-rendered HTML, no JavaScript, no CDN, no build step, no database.

## Requirements

- **Python 3.12** (developed and tested on 3.12.7).
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

The form is prefilled with the worked example below, so the demo runs
immediately. `Reset` (the `/?blank=1` link) clears the fields.

Routes:

| Route | Method | Purpose |
| --- | --- | --- |
| `/` | GET | Render the input form. `/?blank=1` renders it empty. |
| `/calculate` | POST | Validate the posted fields and render the results or the field errors on the same page. |

## Test

From `bjt_bias/`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: `44 passed`.

## Model and assumptions

The circuit is the standard NPN voltage-divider bias: `R1` from `VCC` to the
base, `R2` from base to ground, `RC` from `VCC` to the collector, and `RE`
from the emitter to ground.

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
  written independently of the Thevenin algebra. The two results are compared
  at a **0.1 % relative tolerance**; a row also passes when its absolute
  difference is at most 1e-9 in SI units, which is the fallback for a
  quantity whose Thevenin reference is effectively zero. The Thevenin value
  is the reference and the nodal value is the candidate. Because both methods
  solve the same model exactly, agreement is expected down to floating-point
  noise; the 0.1 % threshold is loose enough to be meaningful and tight
  enough to catch a transcription error.
- **Cut-off is a result, not an input error.** If `VBB <= VBE` the transistor
  is off: `IB = IC = IE = 0`, `VE = 0`, `VB = VBB`, `VC = VCC`, `VCE = VCC`,
  and the cross-check is reported as not applicable.
- All internal arithmetic is in SI units (Ω, A, V). Conversion to kΩ, µA, mA
  and V happens only at the input and display edges.

Input validation: every field is required and must parse as a finite
number; `VCC > 0`; `R1`, `R2`, `RC`, `RE > 0` kΩ; `1 <= beta <= 10000`;
`0.4 <= VBE <= 0.9` V. All field errors are reported together, and the
submitted values are preserved in the re-rendered form.

## Formulas

### Method 1 — Thevenin equivalent of the base divider (primary)

```
VBB = VCC * R2 / (R1 + R2)
RB  = R1 * R2 / (R1 + R2)

IB  = (VBB - VBE) / (RB + (beta + 1) * RE)
IC  = beta * IB
IE  = (beta + 1) * IB

VE  = IE * RE
VB  = VE + VBE
VC  = VCC - IC * RC
VCE = VC - VE
```

### Method 2 — nodal analysis (independent cross-check)

With `IC = (VCC - VC) / RC`, `IB = IC / beta` and `IE = VE / RE`, the unknown
vector is `x = [VB, VE, VC]` and the system `A x = b` is

```
Row 1 (KCL at base):      VB * (1/R1 + 1/R2) - VC / (beta * RC)
                          = VCC/R1 - VCC/(beta * RC)
Row 2 (KCL at emitter):   VE/RE + VC * (1 + 1/beta) / RC
                          = VCC * (1 + 1/beta) / RC
Row 3 (VBE constraint):   VB - VE = VBE
```

It is solved with Gaussian elimination with partial pivoting, then `IB`,
`IC`, `IE` and `VCE` are recovered from the solution. The solution path
shares none of the Thevenin algebra — it rebuilds its own equations from the
resistor values — and the only thing it takes from the Thevenin side is the
`VBB` and `RB` values that are reported alongside the results.

### Comparison

`IB`, `IC`, `IE`, `VCE`, `VB`, `VC` and `VE` are compared quantity by
quantity: both values, the absolute difference, the relative difference, and
a per-row pass/fail verdict at 0.1 % relative tolerance. The app also prints
an overall verdict.

## Region rules

The rules are applied in this order, using the Thevenin result:

1. **Cut-off** if `VBB <= VBE`. `IB = IC = IE = 0`, `VE = 0`, `VB = VBB`,
   `VC = VCC`, `VCE = VCC`. The cross-check is not applicable.
2. **Saturation** if `VCE <= 0.2 V` (`VCE(sat)`). The numbers are shown, but
   the warning states that the active-region model is invalid and that the
   values are an extrapolation, not a physical operating point.
3. **Near saturation** if `0.2 V < VCE < 0.5 V`. A caution is shown.
4. **Forward active** otherwise (`VCE >= 0.5 V`).

## Worked example

The values the app is prefilled with, and the golden test case:

```
VCC = 12 V, R1 = 47 kΩ, R2 = 10 kΩ, RC = 2.2 kΩ, RE = 0.47 kΩ,
beta = 150, VBE = 0.7 V
```

Results:

```
VBB = 2.105263 V   RB = 8.245614 kΩ
IB  = 17.7397 µA   IC = 2.66096 mA   IE = 2.67870 mA
VE  = 1.25899 V    VB = 1.95899 V    VC = 6.14589 V
VCE = 4.88690 V    -> forward active
```

The nodal cross-check agrees with the Thevenin solution on every quantity
(differences at the level of ~1e-16 relative, far inside the 0.1 %
tolerance).

## Project layout

```
bjt_bias/
  app.py              # create_app(); GET / ; POST /calculate ; dev main
  bias.py             # validation, Thevenin solve, nodal solve, compare
  templates/
    index.html        # one page: form, results, warnings, cross-check
  static/
    style.css         # plain CSS, no build step
  tests/
    test_bias.py      # validation, solving, classification, comparison
    test_app.py       # routes, rendering, escaping
  requirements.txt    # Flask and pytest with version bounds
  pytest.ini          # pythonpath = . ; testpaths = tests
  README.md           # this file
```

`bias.py` holds the engineering logic as pure functions and imports no
Flask. `app.py` is the Flask application factory; `create_app()` is exposed
so the tests can build an app instance, and the `__main__` block runs the
development server on <http://127.0.0.1:5000>.
