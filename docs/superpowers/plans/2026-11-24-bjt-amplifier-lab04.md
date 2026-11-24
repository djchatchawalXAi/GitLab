# Lab 04 — BJT Amplifier Simulator Implementation Plan

**Goal:** Add a real-ngspice CE voltage-divider amplifier workbench to the existing Lab 03 Flask app without changing any Lab 02/03 behaviour.

**Architecture:** New `spice_engine.py` (validation, netlist, subprocess, parsing) + `plots.py` (server-side SVG) + `amplifier.html` route pair. Existing `/` and `/calculate` remain untouched. No JavaScript.

**Tech Stack:** Python 3.12, Flask 3.1, pytest 8.4, ngspice 46 console build, Playwright 1.65.

**Spec:** user request in session (Lab 04 workflow), `docs/superpowers/specs/2026-11-17-bjt-bias-multi-circuit-design.md` for Lab 03 constraints.

## Global Constraints
- Never delete/rename existing Lab 02/03 files or change existing analytical results.
- `shell=True` is forbidden; ngspice always via `subprocess.run([...])` with timeout.
- Every run gets its own temporary working directory, cleaned after parsing.
- SPICE output is labelled separately from Analytical Reference.
- No fake waveforms: transient/Bode data comes from ngspice CSV only.
- Never claim PASS for a case not actually executed.

## Tasks
1. `tests/test_spice_engine.py` — validation, netlist, parsers, engine discovery, integration (skipped if no ngspice).
2. `spice_engine.py` — implement to green.
3. `tests/test_amplifier_app.py` — routes, error states, no-JS, provenance.
4. `plots.py` + `templates/amplifier.html` + CSS + `/amplifier` routes.
5. Run Lab 03 suite (must stay 80 passed) and Lab 04 suite.
6. Impeccable install + UI critique/polish.
7. Playwright B1–B8 script, screenshots into `docs/captures/`.
8. `docs/validation.md`, README Lab 04 section, git status/diff audit, commit.
