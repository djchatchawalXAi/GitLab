"""Safe ngspice adapter for the Lab 04 common-emitter amplifier workbench.

This module is pure Python: it does not import Flask.  Every ngspice run is
isolated in a fresh temporary directory, invoked with an argument list (never
a shell), bounded by a timeout, and parsed from real wrdata CSV files.
"""

from __future__ import annotations

import glob
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Sequence

from bias import (Analysis, BiasInput, CircuitType, ValidationError, analyze)

MODEL_NAME = "Q2N3904"
MODEL_BF = 416.4
ANALYTICAL_BETA = 150.0
MODEL_VBE_V = 0.7
MODEL_SOURCE = (
    "Standard 2N3904 NPN Gummel-Poon card (Fairchild/ON Semiconductor, as "
    "shipped in ngspice example libraries). No instructor starter model file "
    "was present in this repository."
)
MODEL_CARD = (
    ".model Q2N3904 NPN (IS=6.734f XTI=3 EG=1.11 VAF=74.03 BF=416.4 "
    "NE=1.259 ISE=6.734f IKF=66.78m XTB=1.5 BR=.7371 NC=2 ISC=0 IKR=0 "
    "RC=1 CJC=3.638p MJC=.3085 VJC=.75 FC=.5 CJE=4.493p MJE=.2593 VJE=.75 "
    "TR=239.5n TF=301.2p ITF=.4 VTF=4 XTF=2 RB=10)"
)

VCE_SAT_V = 0.2
VCE_NEAR_SAT_V = 0.5
DEFAULT_TIMEOUT_S = 30.0


class SpiceError(RuntimeError):
    """Base class for a simulation that could not produce usable results."""

    def __init__(self, message: str, log_tail: str = "") -> None:
        self.message = message
        self.log_tail = log_tail
        super().__init__(message)


class EngineUnavailable(SpiceError):
    """Raised when no ngspice executable can be found."""


class SpiceRunError(SpiceError):
    """Raised when ngspice exits abnormally or produces no usable output."""


class SpiceTimeout(SpiceError):
    """Raised when ngspice exceeds the wall-clock timeout."""


@dataclass(frozen=True)
class AmplifierField:
    """One input on the Lab 04 form."""

    name: str
    label: str
    unit: str
    default: str
    group: str
    hint: str


AMPLIFIER_FIELDS: tuple[AmplifierField, ...] = (
    AmplifierField("vcc", "VCC", "V", "12", "Device & supply", "Supply rail"),
    AmplifierField("r1", "R1", "kΩ", "100", "Device & supply", "Upper divider"),
    AmplifierField("r2", "R2", "kΩ", "22", "Device & supply", "Lower divider"),
    AmplifierField("rc", "RC", "kΩ", "2.2", "Device & supply", "Collector load"),
    AmplifierField("re", "RE", "kΩ", "1", "Device & supply",
                   "Emitter degeneration (unbypassed)"),
    AmplifierField("rl", "RL", "kΩ", "10", "Device & supply", "Load resistor"),
    AmplifierField("cin", "Cin", "µF", "10", "Coupling & load",
                   "Input coupling capacitor"),
    AmplifierField("cout", "Cout", "µF", "10", "Coupling & load",
                   "Output coupling capacitor"),
    AmplifierField("amp_mv", "Vin", "mV peak", "10", "Source",
                   "Sine amplitude (peak)"),
    AmplifierField("freq_hz", "f", "Hz", "1000", "Source",
                   "Sine frequency"),
    AmplifierField("ac_start", "AC start", "Hz", "1", "Analysis sweep",
                   "Bode sweep start"),
    AmplifierField("ac_stop", "AC stop", "Hz", "1e9", "Analysis sweep",
                   "Bode sweep stop"),
    AmplifierField("ac_ppd", "AC points", "pts/dec", "20", "Analysis sweep",
                   "Points per decade"),
    AmplifierField("tran_stop_ms", "t stop", "ms", "5", "Transient",
                   "Transient stop time"),
    AmplifierField("tran_step_us", "t step", "µs", "10", "Transient",
                   "Maximum timestep"),
)
AMPLIFIER_DEFAULTS = {field.name: field.default for field in AMPLIFIER_FIELDS}
FIELD_LABELS = {field.name: field.label for field in AMPLIFIER_FIELDS}


@dataclass(frozen=True)
class AmplifierInput:
    """Validated Lab 04 inputs, in engineering edge units."""

    vcc_v: float
    r1_kohm: float
    r2_kohm: float
    rc_kohm: float
    re_kohm: float
    rl_kohm: float
    cin_uf: float
    cout_uf: float
    source_amplitude_mv: float
    source_frequency_hz: float
    ac_start_hz: float
    ac_stop_hz: float
    ac_points_per_decade: int
    tran_stop_ms: float
    tran_step_us: float


@dataclass(frozen=True)
class EngineInfo:
    """Availability and identity of the ngspice executable."""

    available: bool
    path: str | None
    version: str | None
    detail: str

    @property
    def label(self) -> str:
        if not self.available:
            return "ngspice unavailable"
        version = f" {self.version}" if self.version else ""
        return f"ngspice{version} ready"


@dataclass(frozen=True)
class DcPoint:
    """SPICE DC operating point; currents are reported as magnitudes."""

    vb_v: float
    ve_v: float
    vc_v: float
    vce_v: float
    ic_a: float
    ib_a: float
    ie_a: float
    state: str


@dataclass(frozen=True)
class AcCurve:
    """AC sweep measured from real/imaginary ngspice vectors."""

    frequencies_hz: tuple[float, ...]
    gain_db: tuple[float, ...]
    gain_vv: tuple[float, ...]
    phase_deg: tuple[float, ...]
    vin_reference_v: float
    reference_frequency_hz: float
    reference_gain: float
    reference_gain_db: float
    reference_phase_deg: float
    max_gain_db: float
    f_low_3db_hz: float | None
    f_high_3db_hz: float | None
    cutoff_note: str


@dataclass(frozen=True)
class TranCurve:
    """Transient waveform and its measured phasors."""

    time_ms: tuple[float, ...]
    vin_mv: tuple[float, ...]
    vout_mv: tuple[float, ...]
    vin_amplitude_mv: float
    vout_amplitude_mv: float
    gain: float
    phase_diff_deg: float
    inverted: bool
    clipped: bool
    distortion_pct: float
    clipping_note: str
    measured_frequency_hz: float
    note: str


@dataclass(frozen=True)
class ModelComparisonRow:
    """One quantity compared between the analytical reference and SPICE."""

    key: str
    unit: str
    analytical: float
    spice: float
    abs_diff: float
    rel_diff: float


@dataclass(frozen=True)
class Provenance:
    """Metadata that lets a reader reproduce and audit one run."""

    engine_path: str
    engine_version: str | None
    model_name: str
    model_source: str
    netlist: str
    command: tuple[str, ...]
    run_id: str
    started_at_utc: str
    duration_ms: float
    exit_code: int
    log_tail: str


@dataclass(frozen=True)
class SimulationResult:
    """Complete, auditable result of one ngspice simulation."""

    input: AmplifierInput
    dc: DcPoint
    ac: AcCurve
    tran: TranCurve
    analytical: Analysis
    comparison_rows: tuple[ModelComparisonRow, ...]
    comparison_note: str
    provenance: Provenance


def _read_number(raw: dict[str, str], key: str) -> float | None:
    text = str(raw.get(key, "")).strip()
    try:
        value = float(text)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def _positive(errors: dict[str, str], numbers: dict[str, float],
              raw: dict[str, str], key: str, maximum: float) -> None:
    value = _read_number(raw, key)
    if value is None:
        errors[key] = f"{FIELD_LABELS[key]} must be a number."
    elif value <= 0:
        errors[key] = f"{FIELD_LABELS[key]} must be greater than 0."
    elif value > maximum:
        errors[key] = f"{FIELD_LABELS[key]} must be at most {maximum:g}."
    else:
        numbers[key] = value


def parse_amplifier_input(raw: dict[str, str]) -> AmplifierInput:
    """Validate the Lab 04 form and return SI-friendly edge units."""
    errors: dict[str, str] = {}
    numbers: dict[str, float] = {}

    for key in ("vcc", "r1", "r2", "rc", "re", "rl"):
        _positive(errors, numbers, raw, key, 1e6)
    for key in ("cin", "cout"):
        _positive(errors, numbers, raw, key, 1e6)
    _positive(errors, numbers, raw, "amp_mv", 1000.0)

    frequency = _read_number(raw, "freq_hz")
    if frequency is None:
        errors["freq_hz"] = "f must be a number."
    elif not 1.0 <= frequency <= 1e6:
        errors["freq_hz"] = "f must be between 1 Hz and 1e6 Hz."
    else:
        numbers["freq_hz"] = frequency

    start = _read_number(raw, "ac_start")
    stop = _read_number(raw, "ac_stop")
    if start is None:
        errors["ac_start"] = "AC start must be a number."
    elif not 0.01 <= start <= 1e9:
        errors["ac_start"] = "AC start must be between 0.01 Hz and 1e9 Hz."
    else:
        numbers["ac_start"] = start
    if stop is None:
        errors["ac_stop"] = "AC stop must be a number."
    elif not 0.01 <= stop <= 1e9:
        errors["ac_stop"] = "AC stop must be between 0.01 Hz and 1e9 Hz."
    elif "ac_start" in numbers and stop <= numbers["ac_start"] * 10:
        errors["ac_stop"] = "AC stop must be at least one decade above AC start."
    else:
        numbers["ac_stop"] = stop

    ppd = _read_number(raw, "ac_ppd")
    if ppd is None or ppd != int(ppd):
        errors["ac_ppd"] = "AC points must be a whole number."
    elif not 1 <= ppd <= 1000:
        errors["ac_ppd"] = "AC points must be between 1 and 1000."
    else:
        numbers["ac_ppd"] = float(int(ppd))

    stop_ms = _read_number(raw, "tran_stop_ms")
    if stop_ms is None:
        errors["tran_stop_ms"] = "t stop must be a number."
    elif not 0.01 <= stop_ms <= 1000:
        errors["tran_stop_ms"] = "t stop must be between 0.01 ms and 1000 ms."
    else:
        numbers["tran_stop_ms"] = stop_ms

    step_us = _read_number(raw, "tran_step_us")
    if step_us is None:
        errors["tran_step_us"] = "t step must be a number."
    elif not 0.0001 <= step_us <= 1000:
        errors["tran_step_us"] = "t step must be between 0.0001 µs and 1000 µs."
    else:
        numbers["tran_step_us"] = step_us

    if "freq_hz" in numbers and "tran_step_us" in numbers:
        if numbers["tran_step_us"] > 1e6 / (numbers["freq_hz"] * 20):
            errors["tran_step_us"] = (
                "t step must give at least 20 samples per source cycle.")
    if "tran_stop_ms" in numbers and "tran_step_us" in numbers:
        if numbers["tran_stop_ms"] * 1000 / numbers["tran_step_us"] < 100:
            errors["tran_step_us"] = (
                "t step is too large for the requested stop time (need >= 100 points).")

    if errors:
        raise ValidationError(errors)
    return AmplifierInput(
        vcc_v=numbers["vcc"],
        r1_kohm=numbers["r1"],
        r2_kohm=numbers["r2"],
        rc_kohm=numbers["rc"],
        re_kohm=numbers["re"],
        rl_kohm=numbers["rl"],
        cin_uf=numbers["cin"],
        cout_uf=numbers["cout"],
        source_amplitude_mv=numbers["amp_mv"],
        source_frequency_hz=numbers["freq_hz"],
        ac_start_hz=numbers["ac_start"],
        ac_stop_hz=numbers["ac_stop"],
        ac_points_per_decade=int(numbers["ac_ppd"]),
        tran_stop_ms=numbers["tran_stop_ms"],
        tran_step_us=numbers["tran_step_us"],
    )


def _num(value: float) -> str:
    return f"{value:.12g}"


def build_netlist(inp: AmplifierInput) -> str:
    """Build a deterministic CE voltage-divider netlist from validated inputs."""
    amplitude_v = inp.source_amplitude_mv / 1000.0
    return "\n".join((
        "* Lab 04 CE voltage-divider amplifier - unbypassed RE",
        f"* model: {MODEL_NAME} Gummel-Poon - generated by bjt_bias.spice_engine",
        f"VCC vcc 0 DC {_num(inp.vcc_v)}",
        f"VIN in 0 DC 0 AC {_num(amplitude_v)} "
        f"SIN(0 {_num(amplitude_v)} {_num(inp.source_frequency_hz)})",
        f"R1 vcc b {_num(inp.r1_kohm)}k",
        f"R2 b 0 {_num(inp.r2_kohm)}k",
        f"RC vcc c {_num(inp.rc_kohm)}k",
        f"RE e 0 {_num(inp.re_kohm)}k",
        f"CIN in b {_num(inp.cin_uf)}u",
        f"COUT c out {_num(inp.cout_uf)}u",
        f"RL out 0 {_num(inp.rl_kohm)}k",
        f"Q1 c b e {MODEL_NAME}",
        MODEL_CARD,
        ".control",
        "op",
        "set wr_vecnames",
        "set wr_singlescale",
        "wrdata op.csv v(b) v(e) v(c) @q1[ic] @q1[ib] @q1[ie]",
        f"ac dec {inp.ac_points_per_decade} {_num(inp.ac_start_hz)} "
        f"{_num(inp.ac_stop_hz)}",
        "wrdata ac.csv real(v(out)) imag(v(out)) real(v(in)) imag(v(in))",
        f"tran {_num(inp.tran_step_us)}u {_num(inp.tran_stop_ms)}m",
        "wrdata tran.csv v(in) v(out)",
        ".endc",
        ".end",
        "",
    ))


def _version_from_install(path: Path) -> str | None:
    for candidate in (path.parent / "VERSION", path.parent.parent / "VERSION"):
        try:
            if candidate.is_file():
                text = candidate.read_text(encoding="utf-8", errors="replace").strip()
                if text:
                    return text.splitlines()[0].strip()
        except OSError:
            continue
    return None


def _version_from_binary(path: Path) -> str | None:
    """Ask the executable for its version when no VERSION file is installed."""
    try:
        completed = subprocess.run(
            [str(path), "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    output = "\n".join(part for part in (completed.stdout, completed.stderr)
                       if part)
    match = re.search(r"ngspice[- ](\d+(?:\.\d+)*)", output, re.IGNORECASE)
    return match.group(1) if match else None


@lru_cache(maxsize=8)
def _cached_version(path: str) -> str | None:
    return _version_from_install(Path(path)) or _version_from_binary(Path(path))


def find_ngspice() -> EngineInfo:
    """Locate ngspice without guessing: env var, PATH, then common installs."""
    candidates: list[Path] = []
    configured = os.environ.get("NGSPICE_BIN", "").strip()
    if configured:
        configured_path = Path(configured)
        if configured_path.is_dir():
            candidates.extend((configured_path / "ngspice_con.exe",
                               configured_path / "ngspice.exe"))
        else:
            candidates.append(configured_path)
    for name in ("ngspice_con", "ngspice", "ngspice_con.exe", "ngspice.exe"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    candidates.extend((
        Path(r"C:\Spice64\bin\ngspice_con.exe"),
        Path(r"C:\Spice64\bin\ngspice.exe"),
    ))
    for pattern in (r"C:\Program Files\ngspice*\bin\ngspice_con.exe",
                    r"C:\Program Files\ngspice*\bin\ngspice.exe",
                    str(Path.home() / "AppData/Local/Programs/ngspice/bin/ngspice_con.exe")):
        candidates.extend(Path(p) for p in sorted(glob.glob(pattern)) if p)

    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        if candidate.is_file():
            version = _cached_version(str(candidate))
            return EngineInfo(True, str(candidate), version,
                              f"Found ngspice at {candidate}.")
    if configured:
        detail = (f"NGSPICE_BIN is set to {configured!r} but no executable was "
                  "found there. Set NGSPICE_BIN to ngspice_con.exe.")
    else:
        detail = ("ngspice was not found in PATH or a common install location. "
                  "Install ngspice and/or set NGSPICE_BIN to ngspice_con.exe.")
    return EngineInfo(False, None, None, detail)


def read_wrdata(path: Path) -> tuple[list[str], list[list[float]]]:
    """Read an ngspice wrdata file into (headers, numeric rows)."""
    if not path.is_file() or path.stat().st_size == 0:
        raise SpiceRunError(f"ngspice did not create {path.name}.")
    lines = [line.split() for line in path.read_text(
        encoding="utf-8", errors="replace").splitlines() if line.strip()]
    if len(lines) < 2:
        raise SpiceRunError(f"ngspice produced no data rows in {path.name}.")
    headers = lines[0]
    rows: list[list[float]] = []
    for raw_row in lines[1:]:
        try:
            rows.append([float(token) for token in raw_row])
        except ValueError as error:
            raise SpiceRunError(
                f"Could not parse a numeric row in {path.name}.") from error
    return headers, rows


def _column(headers: Sequence[str], name: str) -> int:
    lowered = [header.strip().lower() for header in headers]
    try:
        return lowered.index(name.lower())
    except ValueError as error:
        raise SpiceRunError(f"ngspice output is missing the {name!r} column.") from error


def _value(row: Sequence[float], index: int) -> float:
    if index >= len(row):
        raise SpiceRunError("ngspice output row is shorter than its header.")
    return float(row[index])


def _state(vce_v: float) -> str:
    if vce_v <= VCE_SAT_V:
        return "Saturation"
    if vce_v < VCE_NEAR_SAT_V:
        return "Near saturation"
    return "Forward active"


def parse_op_table(headers: Sequence[str], rows: Sequence[Sequence[float]]) -> DcPoint:
    """Parse the .op wrdata table."""
    if not rows:
        raise SpiceRunError("ngspice returned an empty operating point.")
    vb = _value(rows[0], _column(headers, "v(b)"))
    ve = _value(rows[0], _column(headers, "v(e)"))
    vc = _value(rows[0], _column(headers, "v(c)"))
    ic = abs(_value(rows[0], _column(headers, "@q1[ic]")))
    ib = abs(_value(rows[0], _column(headers, "@q1[ib]")))
    ie = abs(_value(rows[0], _column(headers, "@q1[ie]")))
    vce = vc - ve
    return DcPoint(vb_v=vb, ve_v=ve, vc_v=vc, vce_v=vce,
                   ic_a=ic, ib_a=ib, ie_a=ie, state=_state(vce))


def _log_interp(f0: float, g0: float, f1: float, g1: float,
                target: float) -> float:
    if g1 == g0:
        return f0
    fraction = (target - g0) / (g1 - g0)
    return math.exp(math.log(f0) + fraction * (math.log(f1) - math.log(f0)))


def parse_ac_table(headers: Sequence[str], rows: Sequence[Sequence[float]],
                   reference_hz: float) -> AcCurve:
    """Parse complex AC vectors and measure gain, phase and -3 dB cutoffs."""
    if len(rows) < 2:
        raise SpiceRunError("ngspice returned too few AC points.")
    f_index = _column(headers, "frequency")
    vr_index = _column(headers, "real(v(out))")
    vi_index = _column(headers, "imag(v(out))")
    ir_index = _column(headers, "real(v(in))")
    ii_index = _column(headers, "imag(v(in))")

    frequencies: list[float] = []
    gains_db: list[float] = []
    gains_vv: list[float] = []
    raw_phases: list[float] = []
    vin_values: list[float] = []
    for row in rows:
        frequency = _value(row, f_index)
        vr, vi = _value(row, vr_index), _value(row, vi_index)
        ir, ii = _value(row, ir_index), _value(row, ii_index)
        vin_magnitude = math.hypot(ir, ii)
        if frequency <= 0 or vin_magnitude <= 0:
            continue
        gain = math.hypot(vr, vi) / vin_magnitude
        phase = math.degrees(math.atan2(vi, vr) - math.atan2(ii, ir))
        phase = (phase + 180.0) % 360.0 - 180.0
        frequencies.append(frequency)
        gains_db.append(20.0 * math.log10(gain) if gain > 0 else -300.0)
        gains_vv.append(gain)
        raw_phases.append(phase)
        vin_values.append(vin_magnitude)
    if len(frequencies) < 2:
        raise SpiceRunError("ngspice returned no usable AC points.")

    # Unwrap the phase so a -180 -> +180 crossing does not draw a false
    # vertical line through the Bode plot.
    phases: list[float] = [raw_phases[0]]
    previous_raw = raw_phases[0]
    for raw in raw_phases[1:]:
        delta = raw - previous_raw
        while delta > 180.0:
            delta -= 360.0
        while delta < -180.0:
            delta += 360.0
        phases.append(phases[-1] + delta)
        previous_raw = raw

    reference_index = min(range(len(frequencies)),
                          key=lambda index: abs(math.log(frequencies[index] /
                                                         reference_hz)))
    reference_gain = 10.0 ** (gains_db[reference_index] / 20.0)
    max_gain_db = max(gains_db)
    threshold = max_gain_db - 3.0

    f_low = None
    for index in range(1, len(gains_db)):
        if gains_db[index] >= threshold and gains_db[index - 1] < threshold:
            f_low = _log_interp(frequencies[index - 1], gains_db[index - 1],
                                frequencies[index], gains_db[index], threshold)
            break
    f_high = None
    for index in range(len(gains_db) - 2, -1, -1):
        if gains_db[index] >= threshold and gains_db[index + 1] < threshold:
            f_high = _log_interp(frequencies[index], gains_db[index],
                                 frequencies[index + 1], gains_db[index + 1],
                                 threshold)
            break

    notes: list[str] = []
    if f_low is None:
        notes.append("Low -3 dB cutoff is below the sweep start; not determined "
                     "in sweep range.")
    if f_high is None:
        notes.append("High -3 dB cutoff is above the sweep stop; not determined "
                     "in sweep range.")
    if not notes:
        notes.append("Both -3 dB cutoffs lie inside the sweep range.")

    return AcCurve(
        frequencies_hz=tuple(frequencies),
        gain_db=tuple(gains_db),
        gain_vv=tuple(gains_vv),
        phase_deg=tuple(phases),
        vin_reference_v=vin_values[reference_index],
        reference_frequency_hz=reference_hz,
        reference_gain=reference_gain,
        reference_gain_db=gains_db[reference_index],
        reference_phase_deg=phases[reference_index],
        max_gain_db=max_gain_db,
        f_low_3db_hz=f_low,
        f_high_3db_hz=f_high,
        cutoff_note=" ".join(notes),
    )


def _phasor(times: Sequence[float], values: Sequence[float],
            frequency_hz: float) -> tuple[float, float]:
    """Least-squares sine/cosine fit; returns (amplitude, phase radians)."""
    omega = 2.0 * math.pi * frequency_hz
    s = [math.sin(omega * time) for time in times]
    c = [math.cos(omega * time) for time in times]
    sss = sum(value * value for value in s)
    ccc = sum(value * value for value in c)
    scc = sum(si * ci for si, ci in zip(s, c))
    xs = sum(value * si for value, si in zip(values, s))
    xc = sum(value * ci for value, ci in zip(values, c))
    determinant = sss * ccc - scc * scc
    if abs(determinant) < 1e-18:
        raise SpiceRunError("Could not fit the transient phasor (singular fit).")
    sine = (xs * ccc - xc * scc) / determinant
    cosine = (xc * sss - xs * scc) / determinant
    return math.hypot(sine, cosine), math.atan2(cosine, sine)


def parse_tran_table(headers: Sequence[str], rows: Sequence[Sequence[float]],
                     frequency_hz: float, tran_stop_ms: float) -> TranCurve:
    """Parse the .tran wrdata table and measure the source-frequency phasors."""
    if len(rows) < 20:
        raise SpiceRunError("ngspice returned too few transient points.")
    t_index = _column(headers, "time")
    vin_index = _column(headers, "v(in)")
    vout_index = _column(headers, "v(out)")
    times = [_value(row, t_index) for row in rows]
    vin = [_value(row, vin_index) for row in rows]
    vout = [_value(row, vout_index) for row in rows]

    window_s = min(3.0 / frequency_hz, max(times[-1] - times[0], 0.0))
    if window_s <= 0:
        raise SpiceRunError("ngspice returned a non-positive transient span.")
    start_time = times[-1] - window_s
    indices = [index for index, time in enumerate(times) if time >= start_time]
    if len(indices) < 8:
        indices = list(range(max(0, len(times) - 8), len(times)))
    fit_times = [times[index] for index in indices]
    fit_vin = [vin[index] for index in indices]
    fit_vout = [vout[index] for index in indices]
    vin_mean = sum(fit_vin) / len(fit_vin)
    vout_mean = sum(fit_vout) / len(fit_vout)
    vin_amplitude, vin_phase = _phasor(
        fit_times, [value - vin_mean for value in fit_vin], frequency_hz)
    vout_amplitude, vout_phase = _phasor(
        fit_times, [value - vout_mean for value in fit_vout], frequency_hz)
    phase_diff = math.degrees(vout_phase - vin_phase)
    phase_diff = (phase_diff + 180.0) % 360.0 - 180.0
    gain = vout_amplitude / vin_amplitude if vin_amplitude else 0.0
    inverted = abs(abs(phase_diff) - 180.0) <= 45.0

    omega = 2.0 * math.pi * frequency_hz
    fitted = [vout_amplitude * math.sin(omega * time + vout_phase)
              for time in fit_times]
    residual_rms = math.sqrt(
        sum((value - fit) ** 2 for value, fit in zip(fit_vout, fitted))
        / len(fit_vout))
    fundamental_rms = vout_amplitude / math.sqrt(2.0)
    distortion_pct = (100.0 * residual_rms / fundamental_rms
                      if fundamental_rms > 0 else 0.0)
    clipped = distortion_pct >= 5.0
    clipping_note = (
        "Clipping or strong distortion detected; reduce the source amplitude."
        if clipped else
        "No clipping detected in the steady-state window."
    )
    return TranCurve(
        time_ms=tuple(time * 1000.0 for time in times),
        vin_mv=tuple(value * 1000.0 for value in vin),
        vout_mv=tuple(value * 1000.0 for value in vout),
        vin_amplitude_mv=vin_amplitude * 1000.0,
        vout_amplitude_mv=vout_amplitude * 1000.0,
        gain=gain,
        phase_diff_deg=phase_diff,
        inverted=inverted,
        clipped=clipped,
        distortion_pct=distortion_pct,
        clipping_note=clipping_note,
        measured_frequency_hz=frequency_hz,
        note=(f"Phasors fitted at {frequency_hz:g} Hz over the last "
              f"{window_s * 1000.0:.3g} ms of the real ngspice waveform."),
    )


def _clean_log(text: str, limit: int = 30) -> str:
    lines = [line for line in text.splitlines()
             if line.strip()
             and not line.startswith("Error opening code model")
             and not line.startswith("Error: Library lib/ngspice")
             and not line.startswith("Warning: code models")
             and not line.startswith("    Any of the following steps")]
    return "\n".join(lines[-limit:])


def analytical_reference(inp: AmplifierInput) -> Analysis:
    """Run the existing Lab 03 voltage-divider solver with model-matched beta."""
    bias_input = BiasInput(
        circuit=CircuitType.VOLTAGE_DIVIDER,
        vcc_v=inp.vcc_v,
        r1_kohm=inp.r1_kohm,
        r2_kohm=inp.r2_kohm,
        rb_kohm=None,
        rc_kohm=inp.rc_kohm,
        re_kohm=inp.re_kohm,
        beta=ANALYTICAL_BETA,
        vbe_v=MODEL_VBE_V,
    )
    return analyze(bias_input)


_COMPARED = (("vb", "V", "vb_v"), ("ve", "V", "ve_v"), ("vc", "V", "vc_v"),
             ("vce", "V", "vce_v"), ("ic", "A", "ic_a"),
             ("ib", "A", "ib_a"), ("ie", "A", "ie_a"))


def compare_models(analytical: Analysis, spice: DcPoint) -> tuple[ModelComparisonRow, ...]:
    """Compare the analytical reference with SPICE quantity by quantity."""
    rows = []
    for key, unit, attribute in _COMPARED:
        reference = getattr(analytical.point, attribute)
        candidate = getattr(spice, attribute)
        difference = abs(candidate - reference)
        relative = (difference / abs(reference)) if reference else math.inf
        rows.append(ModelComparisonRow(key=key, unit=unit,
                                       analytical=reference, spice=candidate,
                                       abs_diff=difference, rel_diff=relative))
    return tuple(rows)


COMPARISON_NOTE = (
    "Analytical reference: bias.py with constant β={beta:g}, VBE=0.700 V and no "
    "Early effect. SPICE: 2N3904 Gummel-Poon card (BF={model_bf:g}, VAF=74.03 V, "
    "parasitic resistances, junction capacitances); its effective β at this "
    "operating point is {effective_beta:.0f}. Differences are expected model "
    "differences, not solver errors."
)


def _comparison_note(dc: DcPoint) -> str:
    effective_beta = dc.ic_a / dc.ib_a if dc.ib_a else 0.0
    return COMPARISON_NOTE.format(beta=ANALYTICAL_BETA, model_bf=MODEL_BF,
                                  effective_beta=effective_beta)


def run_simulation(inp: AmplifierInput, *, engine: EngineInfo | None = None,
                   timeout: float = DEFAULT_TIMEOUT_S) -> SimulationResult:
    """Run one isolated ngspice job and return parsed, provenance-tagged data."""
    engine = engine or find_ngspice()
    if not engine.available or not engine.path:
        raise EngineUnavailable(engine.detail)

    netlist = build_netlist(inp)
    run_dir = Path(tempfile.mkdtemp(prefix="bjt_spice_"))
    started = time.perf_counter()
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    command = (engine.path, "-b", "-o", str(run_dir / "run.log"),
               str(run_dir / "ce.cir"))
    log_text = ""
    try:
        (run_dir / "ce.cir").write_text(netlist, encoding="ascii")
        try:
            completed = subprocess.run(
                list(command),
                cwd=run_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise SpiceTimeout(
                f"ngspice did not finish within {timeout:g} s.", log_text) from error
        except FileNotFoundError as error:
            raise EngineUnavailable(
                f"ngspice executable disappeared: {engine.path}") from error

        log_path = run_dir / "run.log"
        if log_path.is_file():
            log_text = log_path.read_text(encoding="utf-8", errors="replace")
        if not log_text:
            log_text = "\n".join(part for part in (completed.stdout,
                                                   completed.stderr) if part)
        log_tail = _clean_log(log_text)

        if completed.returncode != 0:
            raise SpiceRunError(
                f"ngspice exited with code {completed.returncode}.", log_tail)

        try:
            op_headers, op_rows = read_wrdata(run_dir / "op.csv")
            ac_headers, ac_rows = read_wrdata(run_dir / "ac.csv")
            tran_headers, tran_rows = read_wrdata(run_dir / "tran.csv")
            dc = parse_op_table(op_headers, op_rows)
            ac = parse_ac_table(ac_headers, ac_rows, inp.source_frequency_hz)
            tran = parse_tran_table(tran_headers, tran_rows,
                                    inp.source_frequency_hz, inp.tran_stop_ms)
        except SpiceRunError as error:
            if not error.log_tail:
                raise SpiceRunError(error.message, log_tail) from error
            raise

        analytical = analytical_reference(inp)
        comparison = compare_models(analytical, dc)
        duration_ms = (time.perf_counter() - started) * 1000.0
        provenance = Provenance(
            engine_path=engine.path,
            engine_version=engine.version,
            model_name=MODEL_NAME,
            model_source=MODEL_SOURCE,
            netlist=netlist,
            command=tuple(str(part) for part in command),
            run_id=run_dir.name,
            started_at_utc=started_at,
            duration_ms=duration_ms,
            exit_code=completed.returncode,
            log_tail=log_tail,
        )
        return SimulationResult(input=inp, dc=dc, ac=ac, tran=tran,
                                analytical=analytical,
                                comparison_rows=comparison,
                                comparison_note=_comparison_note(dc),
                                provenance=provenance)
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)
