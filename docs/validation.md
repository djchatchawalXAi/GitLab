# Lab 04 — Browser Acceptance and Validation Record

**Project:** ENG29 2121 — BJT Common-Emitter Amplifier Simulator<br>
**Test date:** 2026-11-25 (current machine)<br>
**Original browser campaign:** 2026-11-24 (B1–B8 evidence)
**Status:** Python suite green; B1–B8 acceptance evidence PASS; Lab 03 preserved.

This file records what was executed against the real Flask app and a real
ngspice binary. The plots and tables come from ngspice output; no waveform or
result is mocked or hand-typed.

## Tested environment

| Item | Observed value |
| --- | --- |
| OS / shell | Windows, PowerShell |
| Test date | 2026-11-25 |
| Python | **3.15.2** |
| Virtual environment | `bjt_bias/.venv` |
| Flask | **3.1.3** |
| pytest | **8.4.2** |
| ngspice | **46** — `ngspice-46 : Circuit level simulation program`, KLU build |
| ngspice executable | `C:\Users\HP\AppData\Local\Temp\opencode\ngspice46\Spice64\bin\ngspice_con.exe` |
| System `PATH` | `ngspice` is **not** currently installed on `PATH`; the portable console build is selected with `NGSPICE_BIN` |
| BJT model | `Q2N3904` NPN Gummel-Poon (Fairchild/ON Semiconductor model card) |
| Node / Playwright | Not installed on the current machine. The original B1–B8 run used Node 24.14.0 and Playwright 1.65.1. |
| UI review | The original run used Impeccable 4.10.0. It is not installed on the current machine; the 2026-11-25 layout check used real Chromium measurements. |
| Browser automation for this record | Playwright **MCP is not configured**. The original B1–B8 evidence used the Playwright library; the current after-polish check used Chromium through the available browser tools. |

### Embedded BJT model card

The netlist embeds this explicit model card in `spice_engine.py`:

```spice
.model Q2N3904 NPN (IS=6.734f XTI=3 EG=1.11 VAF=74.03 BF=416.4
+ NE=1.259 ISE=6.734f IKF=66.78m XTB=1.5 BR=.7371 NC=2 ISC=0
+ IKR=0 RC=1 CJC=3.638p MJC=.3085 VJC=.75 FC=.5 CJE=4.493p
+ MJE=.2593 VJE=.75 TR=239.5n TF=301.2p ITF=.4 VTF=4 XTF=2 RB=10)
```

No instructor-supplied model file or starter netlist was present in the
repository. The student should confirm this card matches the course handout.

## Test and check results

| Check | Command / method | Result |
| --- | --- | --- |
| Full Python suite | `.\.venv\Scripts\python.exe -m pytest bjt_bias -q` | **128 passed** |
| Lab 03 suite | included above | **80 passed** (analytical modes unchanged) |
| Lab 04 suite | `test_spice_engine.py` + `test_amplifier_app.py` | **48 passed** (real ngspice tests included) |
| B1–B8 aggregate browser checks | original Playwright run and screenshot review | **22/22 PASS, 0 FAIL** |
| Browser console errors | original Playwright harness | none |
| After-polish desktop 1280 px | Chromium viewport check | `scrollWidth = 1280`, no overflow |
| After-polish mobile 390 px | Chromium viewport check | `scrollWidth = 390`, no overflow |
| Lab 03 mobile 390 px | Chromium viewport check | `scrollWidth = 375`, no overflow |

The after-polish captures are submitted separately as `06_ui_after_desktop.png`
and `07_ui_after_mobile.png`; they are not committed to this repository.

## Browser Acceptance Test — B1 to B8

Reference SPICE defaults: VCC 12 V, R1 100 kΩ, R2 22 kΩ, RC 2.2 kΩ,
RE 1 kΩ, RL 10 kΩ, Cin = Cout = 10 µF, source 10 mV peak / 1 kHz,
unbypassed RE, Q2N3904.

| Case ID | Method | Input | Expected | Observed | Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| **B1** | Real browser, Lab 03 `/` + `/calculate`, all three analytical modes | Voltage Divider: 12 / 47 / 10 / 2.2 / 0.47 kΩ, β150, VBE 0.7 V. Fixed: 12 / RB 470 / RC 2.2 kΩ. Emitter: 12 / RB 470 / RC 2.2 / RE 0.47 kΩ. | Forward active; closed-form and nodal agree; Lab 03 analytical results unchanged. | VD: IB 17.74 µA, IC 2.661 mA, VCE 4.887 V. Fixed: IB 24.04 µA, IC 3.606 mA, VCE 4.066 V. Emitter: IB 20.89 µA, IC 3.133 mA, VCE 3.624 V. All forward active; both solvers agree. | `b1-lab03-voltage-divider.png`, `b1-lab03-fixed-bias.png`, `b1-lab03-emitter-bias.png` (separate submission) | **PASS** |
| **B2** | Real ngspice `.op` through `/amplifier/simulate` | Reference CE defaults. | VB/VE/VC/VCE/IC from ngspice; model and run status visible. | VB 2.004 V, VE 1.333 V, VC 9.087 V, VCE 7.754 V, IC 1.324 mA, IB 8.887 µA, IE 1.333 mA; Forward active; engine `ngspice 46`, model `Q2N3904`, exit code 0. | `b2-ce-dc.png` (separate submission) | **PASS** |
| **B3** | Real browser, change RE only and re-run | RE 1 kΩ → 0.47 kΩ. | Operating point and/or gain must change from real output. | IC **1.324 → 2.507 mA**; gain **1.756× → 3.723×**. | `b3-re-change.png` (separate submission) | **PASS** |
| **B4** | Real ngspice `.ac dec 20 1 1e9`; server-rendered Bode SVG | Reference defaults; 1 Hz–1 GHz. | Magnitude and phase with Hz/dB/degree units; explicit Vin reference; honest cutoffs. | Gain at 1 kHz 1.756× (4.89 dB), phase −179.9°; fL **1.79 Hz**, fH **129 MHz**; 181 points; Vin reference = source node `in`, 0.01 V AC peak. | `b4-ac-bode.png` (separate submission) | **PASS** |
| **B5** | Real ngspice `.tran 10u 5m`; server-rendered waveform SVG | 10 mV peak, 1 kHz. | Time/Vin/Vout with units; measured amplitude; phase inversion. | Vin 10 mV peak, Vout 17.56 mV peak, gain 1.756×, phase −179.9°, badge “phase inverted”; distortion 0.29% (no clipping). | `b5-tran.png` (separate submission) | **PASS** |
| **B6** | Real browser, change source amplitude and frequency, re-run | 20 mV peak, 2 kHz, 5 µs max step. | Waveform and plot title must update dynamically. | Vin 20 mV, Vout 35.12 mV, still phase inverted; plot title reads “2000 Hz”; Vin/Vout both scale ≈2×. | `b6-amplitude-frequency.png` (separate submission) | **PASS** |
| **B7** | Real browser, invalid input and unavailable engine | RE = 0; and a second server with a bogus `NGSPICE_BIN`. | Per-field error; no run; no stale graphs or fake success. Bogus engine: clear engine-unavailable failure. | RE = 0: “RE must be greater than 0.”, no `RUN OK`, no DC table, no plot. Bogus engine: “ngspice unavailable”, `RUN FAILED`, no results table. | `b7-invalid-re.png`, `b7-engine-unavailable.png` (separate submission) | **PASS** |
| **B8** | Real browser at desktop 1280 px and mobile 390 px; Lab 03 mobile check | Results page after a real run; Lab 03 page at 390 px. | No clipping or horizontal overflow on controls, units, tables or plots; legible layout. | After polish: desktop `scrollWidth = 1280`; mobile `scrollWidth = 390`; Lab 03 mobile `scrollWidth = 375`; no out-of-bounds controls, tables or plots. | `06_ui_after_desktop.png`, `07_ui_after_mobile.png` (separate submission); original `b8-*.png` | **PASS** |

Machine-readable original run log: `b1-b8-results.json` (22 checks, all PASS).
The original B1–B7 evidence was captured on 2026-11-24; B8 was re-checked on
the refined UI on 2026-11-25. No B1–B8 case is marked NOT RUN.

## Analytical Approximation vs SPICE DC bias

The analytical column is the Lab 03 `bias.py` voltage-divider solver with
**β = 150**, **VBE = 0.700 V fixed**, and no Early effect. The SPICE column is
the real 2N3904 Gummel-Poon operating point from ngspice 46.

| Quantity | Analytical | SPICE | |Δ| | Δ% |
| --- | --- | --- | --- | --- |
| VB | 2.008 V | 2.004 V | 0.00408 V | 0.20% |
| VE | 1.308 V | 1.333 V | 0.02512 V | 1.92% |
| VC | 9.142 V | 9.087 V | 0.05477 V | 0.60% |
| VCE | 7.834 V | 7.754 V | 0.07989 V | 1.02% |
| IC | 1.299 mA | 1.324 mA | 24.94 µA | 1.92% |
| IB | 8.661 µA | 8.887 µA | 0.2267 µA | 2.62% |
| IE | 1.308 mA | 1.333 mA | 25.16 µA | 1.92% |

### Why the two columns differ

- **Early effect (base-width modulation).** The SPICE card has `VAF = 74.03`.
  `IC` therefore depends weakly on `VCE`; the Lab 03 analytical model has no
  Early effect and treats `IC = β·IB` exactly.
- **VBE variation.** SPICE computes the base-emitter voltage self-consistently
  from the Gummel-Poon model and the actual collector current. The analytical
  model fixes `VBE = 0.700 V`; at a slightly higher current, SPICE needs a
  slightly different VBE.
- **Base loading.** The analytical Thevenin model uses a constant β and a fixed
  VBE, then computes one base current. SPICE solves the divider and the
  transistor together, so the finite base current loads the R1/R2 divider
  self-consistently and the effective β at the operating point is about 149,
  not exactly 150.
- **Parasitic resistances and capacitances.** The model includes `RB = 10 Ω`,
  `RC = 1 Ω`, `CJE`, `CJC`, `TF` and `TR`. These affect the exact DC point and
  the AC/gain response but are absent from the simple analytical DC model.
- **Model source.** The 2N3904 card is a standard library model. A different
  course-approved card would shift the SPICE column; the analytical column
  would not change.

These are expected model differences, not solver disagreements.

## Known limitations

- **Model source:** the 2N3904 Gummel-Poon card is embedded in
  `spice_engine.py`; confirm it matches the course handout.
- **ngspice build warnings:** the console build prints “code model … couldn’t
  be loaded” because optional XSPICE libraries are absent. Runs still exit 0;
  the log excerpt filters those lines.
- **Single topology:** v1 netlists only the unbypassed-RE CE voltage divider.
  Lab 03 Fixed and Emitter analytical modes are preserved but are not netlisted.
- **Constant-β analytical reference:** `bias.py` is intentionally the simple
  Lab 03 model and is a reference, not ground truth.
- **−3 dB definition:** cutoffs are measured against the maximum gain in the
  sweep with log-frequency interpolation; cutoffs outside the sweep are
  reported as “not determined in sweep range”.
- **Phase axis:** AC phase is unwrapped for plotting and may exceed ±180°.
- **Transient phasor fit:** amplitude/phase are fitted over the last three
  source cycles; under-resolved timesteps are rejected by validation.
- **No JavaScript:** the plots are server-rendered SVG.
- **Screenshots:** capture PNGs are submitted separately and are not copied
  into this repository.
- **Playwright MCP:** unavailable in this environment; do not read this record
  as a claim of MCP execution.

## What the AI built vs. what the student should check

The implementation adds the safe ngspice adapter, server-rendered Bode and
transient SVGs, the `/amplifier` workbench, 48 Lab 04 tests, and the B1–B8
acceptance record, while preserving all 80 Lab 03 tests and analytical modes.
The student should confirm the 2N3904 card, re-derive the DC point and midband
gain by hand, compare with bench measurements, and re-run pytest with their own
ngspice installation.
