# ENG29 2121 Lab 04 — BJT Common-Emitter Amplifier Simulator

A Flask lab application for the **BJT common-emitter amplifier**. The main
Lab 04 workbench runs a real ngspice DC operating point (`.op`), AC sweep
(`.ac`) and transient analysis (`.tran`) for the reference CE voltage-divider
amplifier, then renders the results as tables and server-side SVG Bode and
waveform plots.

The original **Lab 03 DC bias calculator** remains available at `/` and is
unchanged: it solves **Voltage Divider Bias**, **Fixed Bias** and **Emitter
Bias** analytically and cross-checks each result with nodal analysis. The
Lab 04 page is at `/amplifier` and requires ngspice.

The Lab 03 circuit is chosen with a radio group. The matching resistor inputs and
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

- **Python 3.12 or newer.** This machine was verified with **Python 3.15.2**.
- The packages in `requirements.txt`: `Flask>=3.0,<4` and `pytest>=8.0,<9`.
- A browser on the same machine.
- **ngspice (Lab 04 only).** Verified with **ngspice 46**, console build
  (`ngspice_con.exe`). The GUI build also works. Install it and put its `bin`
  directory on `PATH` (recommended), or set `NGSPICE_BIN` to the executable
  path. Without ngspice the Lab 03 page still works; the Lab 04 page shows an
  honest “ngspice unavailable” badge and a clear error instead of fake results.
- **Node 20+ (optional, for the B1–B8 browser harness only).** The harness
  uses Playwright 1.65.1 and bundled Chromium. Node/npm are not required for
  the Flask app or pytest suite.

## Setup

Run these commands from the `bjt_bias/` directory.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### ngspice setup (Lab 04)

1. Download and extract the ngspice 46 Windows console build so that
   `ngspice_con.exe` exists under a `Spice64\bin\` directory.
2. Add that `bin` directory to the **System/User PATH**. For a user-level
   install, run PowerShell once:

```powershell
$ngspiceBin = "C:\Spice64\bin"   # change to the extracted bin directory
[Environment]::SetEnvironmentVariable(
  "Path",
  [Environment]::GetEnvironmentVariable("Path", "User") + ";$ngspiceBin",
  "User"
)
```

3. Open a new terminal and verify the executable is discoverable:

```powershell
ngspice_con --version
```

If you do not want to change `PATH`, set `NGSPICE_BIN` for the server process
instead (the executable path or its containing directory both work):

```powershell
$env:NGSPICE_BIN = "C:\Spice64\bin\ngspice_con.exe"
```

On this machine the verified portable executable is outside the repository at
`C:\Users\HP\AppData\Local\Temp\opencode\ngspice46\Spice64\bin\ngspice_con.exe`;
system-wide `ngspice` is not currently on `PATH`. The adapter also checks
`PATH`, `C:\Spice64\bin\` and common `Program Files` locations. It never
invents a version: it reads `Spice64/VERSION` when present and otherwise asks
the executable with `--version`.

The console build prints harmless “code model … couldn’t be loaded” warnings
because its optional XSPICE libraries are absent. Runs still exit 0; those
lines are filtered from the log excerpt shown in the UI.

## Run

From `bjt_bias/`:

```powershell
.\.venv\Scripts\python.exe -m flask --app app run
```

Then open <http://127.0.0.1:5000>. The Lab 03 analytical bias page is at `/`;
the Lab 04 amplifier simulator is at `/amplifier`.

The Lab 03 form is prefilled with the shared defaults below, so all three
circuits run immediately. Selecting a circuit only changes which fields and
schematic are shown; it does not change the numeric values.

### Using the Lab 04 DC, AC and Transient modes

Open <http://127.0.0.1:5000/amplifier>, keep or edit the CE-stage values, and
press **Run SPICE Simulation**. One real ngspice job produces all three
analyses. Use the **Analysis Mode** selector to choose which result sections
are shown:

- **DC bias** — `.op`: VB, VE, VC, VCE, IB, IC, IE and the operating region,
  plus the **Analytical Approximation** comparison.
- **AC Bode** — `.ac`: frequency points, gain in dB and V/V, phase, and the
  −3 dB cutoffs.
- **Transient** — `.tran`: time-domain Vin/Vout, measured gain, phase
  inversion, distortion and clipping indication.
- **All results** — show DC, AC and transient together.

The selector only filters the displayed result sections; it does not change
the ngspice analyses or the Lab 03 analytical modes. The Lab 03 page continues
to show its own **Analytical Approximation** results independently.

Routes:

| Route | Method | Purpose |
| --- | --- | --- |
| `/` | GET | Render the input form. `/?circuit=<circuit>` pre-selects a radio; `/?blank=1` clears the numeric fields. |
| `/calculate` | POST | Validate the posted fields and render the results or the field errors on the same page. |
| `/amplifier` | GET | Render the Lab 04 amplifier workbench. `?blank=1` clears it. |
| `/amplifier/simulate` | POST | Validate the amplifier form, run one real ngspice job, and render the DC/AC/transient results or a clear error. |

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

Expected: **128 passed** (80 Lab 03 + 48 Lab 04). The Lab 04 integration
tests skip themselves with a clear reason when no ngspice executable is
available, so the analytical Lab 03 suite still runs on a machine without
ngspice.

## Lab 04 — amplifier simulator

### Circuit and defaults

One reference topology, the common-emitter voltage divider with an
**unbypassed** emitter resistor:

| Element | Default |
| --- | --- |
| VCC | 12 V |
| R1 / R2 | 100 kΩ / 22 kΩ |
| RC / RE / RL | 2.2 kΩ / 1 kΩ / 10 kΩ |
| Cin / Cout | 10 µF / 10 µF |
| Source | 10 mV peak sine, 1 kHz |
| Transistor | `Q2N3904` NPN Gummel-Poon |

### What a run returns

- **DC operating point (`.op`):** VB, VE, VC, VCE, IC, IB, IE and the circuit
  state (Forward active / Near saturation / Saturation). Currents are reported
  as magnitudes from ngspice device vectors, and the UI states that SPICE's
  internal emitter-current sign is negative. A separate **Analytical
  Approximation** table compares `bias.py` (β = 150, VBE = 0.700 V, no Early
  effect) with the **SPICE Simulation** quantity by quantity.
- **AC small-signal (`.ac`):** frequency points, per-point gain in both dB and
  V/V, and phase in degrees against a log frequency axis, with the Vin
  reference stated explicitly. The −3 dB cutoffs are measured from the sweep;
  when one lies outside the sweep the UI says “not determined in sweep range”.
- **Transient (`.tran`):** real time-domain Vin and Vout waveforms, measured
  peak amplitudes, gain, phase difference, an explicit inverted / not inverted
  verdict, and a distortion/clipping check. When the output is overdriven the
  page reports “clipping detected” and shows the measured THD proxy.

The default AC sweep is 1 Hz to 1 GHz with 20 points per decade so both the
low and high −3 dB corners are inside the sweep. Phase is unwrapped for
plotting, so a genuine −180° crossing is not drawn as a false wrap line.

### Provenance and safety

Every run gets its own temporary working directory and is executed with
`subprocess.run([...])`, never `shell=True`, under a timeout. Inputs are
validated before a netlist is generated (positive component values, frequency
and sweep/time-step constraints, `RE > 0`, at least one decade of AC sweep).
The result carries the engine path, version, model name/source, netlist,
command, run ID, start time, duration and exit code. Missing engine, non-zero
exit, empty output, timeout and invalid input each produce a distinct error;
none of them leave a stale graph or a fake success badge behind.

### Analytical Approximation vs. SPICE Simulation

The Lab 03 models (Fixed, Emitter, Voltage Divider) are unchanged and remain
clearly labelled **Analytical Approximation**. The Lab 04 results are labelled
**SPICE Simulation**, so the two sources are never mixed. Only the Voltage
Divider solver is used for the Lab 04 comparison, and only for the DC operating
point. See
[`../docs/validation.md`](../docs/validation.md) for the measured comparison,
model differences and limitations.

### Browser verification (B1–B8)

The harness lives at [`../scripts/verify_lab04.mjs`](../scripts/verify_lab04.mjs)
and expects the app on port 5000 plus a second instance with a broken
`NGSPICE_BIN` on port 5001:

```powershell
# terminal 1 — working engine
$env:NGSPICE_BIN = "...\ngspice_con.exe"
.\bjt_bias\.venv\Scripts\python.exe -c "from app import create_app; create_app().run(port=5000)"

# terminal 2 — unavailable engine
$env:NGSPICE_BIN = "...\does-not-exist\ngspice_con.exe"
.\bjt_bias\.venv\Scripts\python.exe -c "from app import create_app; create_app().run(port=5001)"

# terminal 3
npm install playwright@1.65.1
npx playwright install chromium
node scripts/verify_lab04.mjs docs/captures
```

**Playwright MCP was not available in the verification environment.** The
cases were therefore executed with the real Playwright 1.65.1 library and
bundled Chromium, not with an MCP server; this is stated again in
`docs/validation.md`. Results: **22/22 PASS, 0 FAIL**, no console errors.
Screenshots and the machine-readable log are in `docs/captures/`.

### UI review

Impeccable 4.10.0 was installed project-scope with
`npx impeccable install --providers=opencode --scope=project --project -y`
and used to review the workbench at 1280 px and 390 px. Two detector findings
remain and were judged false positives: a flat-type-hierarchy warning because
the Jinja `<link>` cannot be resolved by the detector, and a side-tab warning
on the pre-existing Lab 03 header stripe. Both are documented in
`docs/validation.md`; the Lab 03 design was not changed to silence them.

### How the AI change was checked

- Full suite: **128 passed** (80 Lab 03 tests untouched + 48 Lab 04),
  including real ngspice-46 `.op`, `.ac`, `.tran` and overdrive/clipping runs.
- Real Chromium: **22/22 B1–B8 checks PASS**, including a real `.op`, `.ac`
  and `.tran` run, a RE change, an amplitude/frequency change, RE = 0
  validation, a missing-engine server, and 1280/390 px layouts.
- `git status` was audited before committing; `.venv/`, `.env`, API keys and
  per-run ngspice artifacts are not tracked.

### What the student should verify

The AI wrote the adapter, SVG plotting, UI, tests and validation record. The
student should confirm the embedded 2N3904 card matches the course model,
re-derive the DC point and midband gain by hand, compare against bench
measurements, and re-run `pytest` plus `scripts/verify_lab04.mjs` on their own
machine and ngspice install. The full evidence table is in
[`../docs/validation.md`](../docs/validation.md).


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
  app.py              # create_app(); Lab 03 routes + /amplifier routes
  bias.py             # validation, closed-form solvers, nodal solvers, compare
  spice_engine.py     # Lab 04 validation, netlist, ngspice runner, parsers
  plots.py            # server-rendered SVG Bode and transient charts
  templates/
    index.html        # Lab 03: picker, form, three schematics, results
    amplifier.html    # Lab 04: grouped inputs, DC/AC/transient results
  static/
    style.css         # plain CSS, no build step (Lab 03 + Lab 04 sections)
    sut-logo.svg      # SUT watermark used by the header/background
  tests/
    test_bias.py      # validation, solving, classification, comparison
    test_app.py       # routes, rendering, escaping, CSS contract
    test_spice_engine.py  # validation, netlist, parsers, real ngspice runs
    test_amplifier_app.py # amplifier routes, error states, no-JS contract
  requirements.txt    # Flask and pytest with version bounds
  pytest.ini          # pythonpath = . ; testpaths = tests
  README.md           # this file

docs/
  validation.md       # Lab 04 B1-B8 evidence, model, limitations
  captures/           # B1-B8 screenshots and b1-b8-results.json

scripts/
  verify_lab04.mjs    # Playwright B1-B8 harness
```

`bias.py` holds the engineering logic as pure functions and imports no
Flask. `app.py` is the Flask application factory; `create_app()` is exposed
so the tests can build an app instance, and the `__main__` block runs the
development server on <http://127.0.0.1:5000>.
