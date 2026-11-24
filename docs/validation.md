# Lab 04 — Validation Record (BJT Amplifier Simulator v1)

This file records what was actually executed for ENG29 2121 Lab 04, against
the real Flask app and a real ngspice binary. It is evidence, not a design
document. Nothing here is a mocked waveform or a hand-typed result.

## Tested environment

| Item | Observed value |
| --- | --- |
| OS / shell | Windows, PowerShell |
| Python | 3.12.7 (`C:\Program Files\Python312\python.exe`) |
| Virtual environment | `bjt_bias/.venv` |
| Flask | 3.1.3 |
| pytest | 8.4.2 |
| ngspice | **46** (`Spice64/VERSION` = `46`), Schemline-IC `ngspice-46-win64.zip` console build |
| ngspice executable | `...\Spice64\bin\ngspice_con.exe`, selected with `NGSPICE_BIN` |
| BJT model | `Q2N3904` NPN Gummel-Poon, `BF=416.4`, `VAF=74.03`, `RB=10`, `RC=1`, `CJE=4.493p`, `CJC=3.638p`, `TF=301.2p`, `TR=239.5n` |
| Node | 24.14.0 |
| Browser automation | Playwright **1.65.1**, bundled Chromium |
| UI review | Impeccable 4.10.0, installed project-scope in `.opencode/` |

### Playwright MCP status (honest note)

**Playwright MCP was not available in this environment.** No MCP resources
were registered (`tools.opencode.list_mcp_resources` returned an empty list),
and no Playwright MCP server was configured. Rather than claim MCP runs that
did not happen, the B1–B8 cases were executed with the **real Playwright
1.65.1 library** driving bundled Chromium, using the same
navigate → fill/select → click → read DOM → compare → screenshot sequence.
The script is reproducible: `scripts/verify_lab04.mjs`.

The distinction matters and is stated plainly: these are **real browser runs,
not MCP runs**. Every PASS below was produced by an actual Chromium navigation
against `http://127.0.0.1:5000` (working ngspice) or `http://127.0.0.1:5001`
(deliberately broken `NGSPICE_BIN`).

## Test and check results

| Check | Command | Result |
| --- | --- | --- |
| Full Python suite | `.\.venv\Scripts\python.exe -m pytest bjt_bias -q` | **119 passed** |
| Lab 03 suite only | included above | 80 passed (unchanged) |
| Lab 04 suite only | `test_spice_engine.py` + `test_amplifier_app.py` | 39 passed |
| Browser cases | `node scripts/verify_lab04.mjs` | **22/22 PASS, 0 FAIL** |
| Browser console errors | captured by the Playwright harness | none |

## B1–B8 evidence table

Reference defaults for all SPICE cases: VCC 12 V, R1 100 kΩ, R2 22 kΩ,
RC 2.2 kΩ, RE 1 kΩ, RL 10 kΩ, Cin = Cout = 10 µF, source 10 mV peak / 1 kHz,
unbypassed RE.

| Case | Method | Input | Expected / reference | Observed | Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| **B1** | Real browser, Lab 03 `/` + `/calculate` | Voltage Divider: 12 / 47 / 10 / 2.2 / 0.47 kΩ, β150, VBE 0.7 | Forward active; closed-form and nodal agree; analytical values unchanged | IB 17.74 µA, IC 2.661 mA, VCE 4.887 V, Forward active, closed-form + nodal agree | `docs/captures/b1-lab03-voltage-divider.png` | **PASS** |
| **B1** | Real browser | Fixed Bias: 12 / RB 470 / RC 2.2 kΩ, β150, VBE 0.7 | Forward active, both solvers agree | IB 24.04 µA, IC 3.606 mA, VCE 4.066 V, Forward active | `docs/captures/b1-lab03-fixed-bias.png` | **PASS** |
| **B1** | Real browser | Emitter Bias: 12 / RB 470 / RC 2.2 / RE 0.47 kΩ, β150, VBE 0.7 | Forward active, both solvers agree | IB 20.89 µA, IC 3.133 mA, VCE 3.624 V, Forward active | `docs/captures/b1-lab03-emitter-bias.png` | **PASS** |
| **B2** | Real ngspice `.op` through `/amplifier/simulate` | Reference CE defaults | VB/VE/VC/VCE/IC from solver, model + run status visible | VB 2.004 V, VE 1.333 V, VC 9.087 V, VCE 7.754 V, IC 1.324 mA, IB 8.887 µA, IE 1.333 mA, Forward active; engine `ngspice 46`, model `Q2N3904`, exit code 0 | `docs/captures/b2-ce-dc.png` | **PASS** |
| **B3** | Real browser, change RE only and re-run | RE 1 kΩ → 0.47 kΩ | Operating point and/or gain must change from real output | IC **1.324 → 2.507 mA**, gain **1.756× → 3.723×** | `docs/captures/b3-re-change.png` | **PASS** |
| **B4** | Real ngspice `.ac dec 20 1 1e9`, Bode rendered as server-side SVG | Reference defaults, 1 Hz–1 GHz | Magnitude + phase with Hz/dB/degree units and explicit Vin reference; honest cutoffs | Gain at 1 kHz 1.756× (4.89 dB), phase −179.9°; fL **1.79 Hz**, fH **129 MHz**; 181 points; Vin reference shown as source node `in`, 0.01 V AC peak | `docs/captures/b4-ac-bode.png` | **PASS** |
| **B5** | Real ngspice `.tran 10u 5m`, waveform rendered as SVG | 10 mV peak, 1 kHz | Time/Vin/Vout with units, measured amplitude, phase inversion | Vin 10 mV peak, Vout 17.56 mV peak, gain 1.756×, phase −179.9°, badge “phase inverted” | `docs/captures/b5-tran.png` | **PASS** |
| **B6** | Real browser, change source amplitude + frequency, re-run | 20 mV peak, 2 kHz, 5 µs max step | Waveform must update dynamically | Vin 20 mV, Vout 35.12 mV, still phase inverted; plot title reads “2000 Hz”; Vin/Vout both scale ~2× | `docs/captures/b6-amplitude-frequency.png` | **PASS** |
| **B7a** | Real browser, invalid input | RE = 0 | Per-field error, no run, no stale graphs, no fake success | “RE must be greater than 0.” shown; no `RUN OK`; no DC table from a previous run; no new simulation | `docs/captures/b7-invalid-re.png` | **PASS** |
| **B7b** | Real browser against server with bogus `NGSPICE_BIN` | Any valid form | Engine badge shows unavailable; run fails clearly; no fake success | Badge “ngspice unavailable”; `RUN FAILED` with ngspice diagnostic; no `RUN OK`; no results table | `docs/captures/b7-engine-unavailable.png` | **PASS** |
| **B8a** | Real browser at 1280×900 | Results page after a real run | No horizontal overflow, controls and charts legible | `scrollWidth` 1280 = viewport 1280; all panels and both Bode plots visible | `docs/captures/b8-desktop-1280.png` | **PASS** |
| **B8b** | Real browser at 390×844 | Results page after a real run | No horizontal overflow, key controls reachable | `scrollWidth` 390 = viewport 390; VCC field `x=53 w=226`; submit button `w=310`; power plots scroll inside their card | `docs/captures/b8-mobile-390.png` | **PASS** |
| **B8c** | Real browser at 390×844 | Lab 03 page | Mobile layout still works | `scrollWidth` 390 = viewport 390 | `docs/captures/b8-mobile-lab03.png` | **PASS** |

Machine-readable run log: `docs/captures/b1-b8-results.json` (22 items, all
`PASS`, 0 `FAIL`).

**NOT RUN:** none of B1–B8 was skipped. Each case above was executed in a real
browser. Playwright **MCP** itself was not available, as explained above; the
cases were run with the Playwright library instead.

## Analytical reference vs. SPICE (B2 detail)

The analytical column is the existing `bias.py` Voltage Divider solver,
relabelled **Analytical reference** and run with the Lab 03 default β = 150,
VBE = 0.700 V, no Early effect. The SPICE column is the 2N3904 Gummel-Poon
operating point from real ngspice 46.

| Quantity | Analytical | SPICE | |Δ| | Δ% |
| --- | --- | --- | --- | --- |
| VB | 2.008 V | 2.004 V | 0.00408 V | 0.20% |
| VE | 1.308 V | 1.333 V | 0.02512 V | 1.92% |
| VC | 9.142 V | 9.087 V | 0.05477 V | 0.60% |
| VCE | 7.834 V | 7.754 V | 0.07989 V | 1.02% |
| IC | 1.299 mA | 1.324 mA | 24.94 µA | 1.92% |
| IB | 8.661 µA | 8.887 µA | 0.2267 µA | 2.62% |
| IE | 1.308 mA | 1.333 mA | 25.16 µA | 1.92% |

The SPICE card's effective β at this point is about 149, close to the
analytical 150; the remaining differences come from the Gummel-Poon model
(Early effect `VAF=74.03`, parasitic `RB`/`RC`, junction capacitances) and
from the constant-VBE approximation in `bias.py`. These are expected model
differences, not solver disagreements, and the UI says so in place.

## UI review (Impeccable)

Impeccable 4.10.0 was installed project-scope (`npx impeccable install
--providers=opencode --scope=project --project -y`) and the detector was run
on `amplifier.html` + `style.css`.

Two findings remain, both reviewed and judged **false positives**:

1. `flat-type-hierarchy` — the detector cannot resolve the Jinja stylesheet
   `<link href="{{ url_for(...) }}">`, so it assumes browser-default 16 px for
   every role. In the rendered page the hierarchy is real (h1 1.5 rem, panel
   headings, 0.7–1.05 rem metric labels) and was checked in the screenshots.
2. `side-tab` on `.app-header::before` — a pre-existing Lab 03 top stripe,
   intentionally left untouched to avoid regressing the Lab 03 design.

Polish applied during this lab, confined to templates/CSS and formatting
helpers (no physics or simulation logic):

- schematic labels repositioned so `VCC`, `RC`, `Cout` and the rails do not
  collide; verified in `docs/captures/b8-schematic-closeup.png`;
- Bode phase unwrapped so a real −180° crossing does not draw a false vertical
  line; phase axis is now data-driven;
- “nice” tick values on linear axes instead of raw fractions;
- legend width fits the longest series label;
- analytical column uses β = 150 for a fairer comparison, and the note states
  both β values plus the effective SPICE β;
- µA formatting for small currents;
- badges read “ngspice 46 ready” and “RUN OK · ngspice 46”;
- mobile plots scroll horizontally inside their card instead of clipping the
  axes, while the page itself never overflows.

## Known limitations

- **Model source:** no instructor-supplied model file or starter netlist was
  present in the repository. The standard 2N3904 Gummel-Poon card is embedded
  in `spice_engine.py` and named in the UI; the student should confirm it
  matches the course model.
- **ngspice build warnings:** the console build prints “code model … couldn’t
  be loaded” because XSPICE code-model libraries are absent from this package.
  The run still exits 0 and the ordinary BJT analyses are valid; those lines
  are filtered from the log tail shown in the UI.
- **Single topology:** v1 simulates only the unbypassed-RE CE voltage divider.
  Lab 03's Fixed and Emitter analytical modes are unchanged but are not
  netlisted.
- **Constant-β analytical reference:** `bias.py` is intentionally the simple
  Lab 03 model. It is shown as a reference, not as ground truth.
- **−3 dB definition:** cutoffs are measured against the maximum gain in the
  sweep, with log-frequency interpolation; if a cutoff lies outside the sweep
  the UI reports “not determined in sweep range” instead of inventing a value.
- **Phase axis:** the AC phase is unwrapped for plotting, so it can exceed
  ±180° at the extremes; this is deliberate and stated by the axis labels.
- **Transient phasor fit:** amplitude/phase are fitted over the last three
  source cycles of the real waveform, so an under-resolved transient step is
  rejected at validation time (≥20 samples per cycle, ≥100 points).
- **No JavaScript:** plots are server-rendered SVG; the page keeps the Lab 03
  no-JS contract.
- **Playwright MCP:** unavailable here; browser evidence came from the
  Playwright library. Do not read this file as a claim of MCP execution.

## What the AI built vs. what the student should check

The AI added a safe ngspice adapter, server-rendered Bode/transient SVG plots,
the `/amplifier` UI, 39 tests, and the B1–B8 browser evidence, while leaving
all Lab 02/03 code and 80 tests intact. The student should independently
confirm the 2N3904 model matches the course handout, verify the DC and gain
numbers against their own hand analysis and bench measurements, and re-run
`pytest` plus `scripts/verify_lab04.mjs` on their machine with their own
ngspice install.
