# BJT Common-Emitter DC Bias Web App — Design

- Course: ENG29 2121
- Date: 2026-11-10
- Status: awaiting approval
- Repository: `github.com/djchatchawalXAi/GitLab`, branch `main`
- App location: `bjt_bias/` (new, self-contained; existing lab files untouched)

## 1. Intent and why

A short lab needs a working Flask application that computes the DC operating
point of an NPN voltage-divider common-emitter bias circuit, shows it with
units, warns when the transistor is not in forward-active mode, and compares
the result against an independently coded calculation.

The pedagogical point of the independent calculation is corroboration: two
different formulations of the same circuit must agree. It is not a second
guess or an approximation.

## 2. Scope

### Goals
- Accept VCC, R1, R2, RC, RE, beta, VBE.
- Compute IB, IC, IE, VCE, VB, VC, VE and VBB, RB.
- Show every result with an explicit unit.
- Reject invalid input with per-field messages; never 500 on bad input.
- Classify the region (cutoff / forward active / near saturation /
  saturation) and warn when the active-region model is invalid.
- Compute the operating point a second time by nodal analysis, coded
  separately from the Thevenin solution, and show both with a difference.
- Separate engineering logic, routes, templates, CSS and tests.
- Run on localhost and be committed to GitHub on 2026-11-10.

### Non-goals
- AC, small-signal, transient or frequency analysis.
- Load-line plotting or graphs.
- Circuit editor, schematic image, or component picker.
- FET or other transistor types.
- Database, authentication, deployment, CI.
- Newton/iterative solution of the Ebers-Moll equation.
- User-selectable VCE(sat).

### Anti-goals
- A result page that hides a numeric edge case behind an HTTP 500.
- A "cross-check" that reuses the Thevenin algebra and therefore always
  agrees by construction.
- Presenting a saturated extrapolation as a physical operating point.

## 3. Circuit and model

NPN, common emitter, voltage-divider bias:

```
VCC ──┬── R1 ──┬── RC ──┬── collector
      │        │        │
      │        base     │
      │        │        │
      │        R2       │
      │        │        │
      │       GND       │
      │                 │
      └── RE ── emitter ┘
              │
             GND
```

Assumptions, all stated in the UI and README:

- Forward-active model: VBE is the given constant, beta is constant.
- No Early effect, no recombination detail, ideal resistors.
- VCE(sat) is a fixed 0.2 V constant, not an input.
- Resistances are entered in kΩ; VCC and VBE in V; currents displayed in
  µA (IB) and mA (IC, IE).

### Primary calculation — Thevenin equivalent

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

### Independent calculation — nodal analysis

Solve the linear system `A x = b` with `x = [VB, VE, VC]`, using Gaussian
elimination with partial pivoting. The solve algebra is independent: this code
path does not reuse the Thevenin current/voltage equations. `solve_nodal` calls
`thevenin_model` only to populate the displayed VBB and RB, which are not
compared.

With `IC = (VCC - VC) / RC`, `IB = IC / beta`, `IE = VE / RE`:

```
Row 1 (KCL at base):     VB*(1/R1 + 1/R2) - VC/(beta*RC)
                         = VCC/R1 - VCC/(beta*RC)
Row 2 (KCL at emitter):  VE/RE + VC*(1 + 1/beta)/RC
                         = VCC*(1 + 1/beta)/RC
Row 3 (VBE constraint):  VB - VE = VBE
```

Recover IB, IC, IE and VCE from the solution. All internal arithmetic is in
SI units (Ω, A, V); conversion happens only at the input and display edges.

### Comparison

Compare IB, IC, IE, VCE, VB, VC, VE from both methods. Show each quantity,
both values, the absolute difference and the relative difference, and a
pass/fail verdict at 0.1 % relative tolerance (falling back to an absolute
tolerance of 1e-9 in SI units when the Thevenin reference is ~0; this is
stricter than the display units). The Thevenin value is the reference; the
nodal value is the candidate. Because both methods solve the
same linear model exactly, agreement is expected to be at floating-point
noise; the 0.1 % threshold is deliberately loose enough to be meaningful
and tight enough to catch a transcription error. A unit test feeds a 1 %
perturbation to the comparator to prove it reports disagreement.

## 4. Region classification

Order matters; classification happens before display, using the Thevenin
result (the nodal result must agree with it anyway).

1. **Cutoff** if `VBB <= VBE`. Return IB = IC = IE = 0, VE = 0, VB = VBB,
   VC = VCC, VCE = VCC. Do not run the nodal solve; show the cross-check as
   "not applicable — cutoff".
2. Otherwise solve. **Saturation warning** if `VCE <= 0.2 V`: display the
   numbers but label them "saturation — active-region model invalid; these
   values are an extrapolation, not a physical operating point". Do not
   re-solve with a clamped VCE.
3. **Near saturation caution** if `0.2 V < VCE < 0.5 V`.
4. Otherwise **forward active**.

## 5. Validation

Invalid input re-renders the form with HTTP 200, a per-field message, the
submitted values preserved, and no result tables.

- Every field required and parseable as a finite float; reject blank,
  non-numeric, NaN and infinity.
- `VCC > 0`.
- `R1, R2, RC, RE > 0` (kΩ).
- `1 <= beta <= 10000`.
- `0.4 <= VBE <= 0.9` (V).
- `VBB <= VBE` is not an input error; it is a cutoff result with a warning.
- `VBE >= VCC` is not an input error; it naturally yields cutoff.

## 6. UI

One server-rendered page, works offline, no CDN, no JavaScript.

- Input form: seven labelled fields with units in the labels; prefilled with
  the worked example below so the demo runs immediately; a "Reset" link to
  the bare form.
- Result area: a region badge (text, not colour alone), the operating-point
  table (IB, IC, IE, VCE, VB, VC, VE) with units, and a compact model line
  showing VBB and RB.
- Cross-check area: the comparison table and verdict.
- Error area: field messages next to the fields plus a summary.
- Plain CSS, readable on a laptop, no build step.

Worked example (also the golden test):

```
VCC = 12 V, R1 = 47 kΩ, R2 = 10 kΩ, RC = 2.2 kΩ, RE = 0.47 kΩ,
beta = 150, VBE = 0.7 V

VBB = 2.105263 V   RB = 8.245614 kΩ
IB  = 17.7397 µA   IC = 2.66096 mA   IE = 2.67870 mA
VE  = 1.25899 V    VB = 1.95899 V    VC = 6.14589 V
VCE = 4.88690 V    -> forward active
```

## 7. Structure

```
bjt_bias/
  app.py              # create_app(); GET / ; POST /calculate ; dev main
  bias.py             # validation, Thevenin solve, nodal solve, compare
  templates/
    index.html
  static/
    style.css
  tests/
    test_bias.py
    test_app.py
  requirements.txt    # Flask and pytest with sane version bounds
  README.md           # run, test, assumptions, formulas, example
```

- `app.py` exposes `create_app()` so tests can build an app instance; a
  module-level `if __name__ == "__main__"` runs the dev server on
  `http://127.0.0.1:5000`.
- `bias.py` has no Flask import and no I/O. Suggested public surface:
  `BiasInput`, `BiasResult`, `ValidationError`, `analyze(values)`,
  `solve_thevenin(inp)`, `solve_nodal(inp)`, `compare(a, b)`.
- Routes: `GET /` renders the form; `POST /calculate` validates and renders
  results or errors on the same page. A 400 is not used for form errors.
- No globals, no database, no session state.

## 8. Tests

`tests/test_bias.py`

- Golden worked example above, asserted to 1e-6 relative.
- Independent method agrees with Thevenin across a parametrised grid of
  valid inputs, including low beta and large RB.
- Comparator reports disagreement for an injected 1 % error.
- Cutoff case (`R1 = 47 kΩ, R2 = 1 kΩ` → VBB < 0.7 V): zero currents,
  VCE = VCC, no nodal comparison.
- Saturation case: badge and warning text present, numbers still returned.
- Near-saturation case: caution, not saturation.
- Table-driven validation: blank, "abc", 0, negative, NaN, inf, beta = 0,
  beta = 20000, VBE = 0.3, VBE = 1.2.

`tests/test_app.py`

- `GET /` returns 200 with all seven fields and their units.
- Valid `POST /calculate` returns 200 and shows both method tables, the
  region, and the agreement verdict.
- Invalid `POST` returns 200 with field errors, no result table, and the
  submitted value preserved.
- A missing form key and an empty body produce errors, not a 500.

## 9. Definition of done

- `python -m venv .venv`; install `requirements.txt`; `pytest -q` all green,
  output shown.
- `python app.py` serves the demo on localhost:5000; the worked example
  renders forward-active with a passing cross-check.
- README documents install, run, test, assumptions, formulas and the
  fixed VCE(sat) choice.
- Commit containing only the new `bjt_bias/` app (plus this design doc) on
  `main`, pushed to `origin`; `git status` clean.

## 10. Constraints and risks

- Flask and pytest are not installed; installation needs network access.
- Git exists at `%LOCALAPPDATA%\Programs\Git\cmd\git.exe` but is not on
  PATH; commands use the full path.
- GitHub credentials may prompt on push.
- The existing `electrical.py`, `test_electrical.py` and README belong to an
  unrelated lab and are not modified.
- A saturated extrapolation is easy to misread; the badge and warning are
  part of the deliverable, not decoration.

## 11. Left to the builder

- Exact HTML layout, class names and CSS.
- Number formatting helper and significant-figure policy.
- Whether VBB/RB are shown in one line or two.
- Test names and organisation within the two test files.
- Whether the example values are prefilled or loaded by a link.
