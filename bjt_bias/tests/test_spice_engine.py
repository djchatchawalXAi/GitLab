"""Tests for the Lab 04 ngspice adapter (validation, netlist, parsing)."""

import math
from pathlib import Path

import pytest

from bias import ValidationError
import spice_engine as se

VALID = {
    "vcc": "12", "r1": "100", "r2": "22", "rc": "2.2", "re": "1",
    "rl": "10", "cin": "10", "cout": "10", "amp_mv": "10",
    "freq_hz": "1000", "ac_start": "1", "ac_stop": "1e9",
    "ac_ppd": "20", "tran_stop_ms": "5", "tran_step_us": "10",
}


def test_parse_reference_defaults():
    inp = se.parse_amplifier_input(VALID)
    assert inp.vcc_v == 12.0
    assert inp.r1_kohm == 100.0
    assert inp.r2_kohm == 22.0
    assert inp.rc_kohm == 2.2
    assert inp.re_kohm == 1.0
    assert inp.rl_kohm == 10.0
    assert inp.cin_uf == 10.0
    assert inp.cout_uf == 10.0
    assert inp.source_amplitude_mv == 10.0
    assert inp.source_frequency_hz == 1000.0


def test_re_zero_is_rejected_before_any_simulation():
    with pytest.raises(ValidationError) as info:
        se.parse_amplifier_input(dict(VALID, re="0"))
    assert info.value.errors["re"] == "RE must be greater than 0."


@pytest.mark.parametrize("field", ["vcc", "r1", "r2", "rc", "rl", "cin", "cout"])
def test_non_positive_component_values_are_rejected(field):
    with pytest.raises(ValidationError) as info:
        se.parse_amplifier_input(dict(VALID, **{field: "-1"}))
    assert field in info.value.errors


@pytest.mark.parametrize("field", ["amp_mv", "freq_hz", "ac_start", "ac_stop",
                                   "ac_ppd", "tran_stop_ms", "tran_step_us"])
def test_missing_numeric_fields_are_rejected(field):
    raw = dict(VALID)
    raw.pop(field)
    with pytest.raises(ValidationError) as info:
        se.parse_amplifier_input(raw)
    assert field in info.value.errors


def test_frequency_outside_range_is_rejected():
    with pytest.raises(ValidationError) as info:
        se.parse_amplifier_input(dict(VALID, freq_hz="2e6"))
    assert "freq_hz" in info.value.errors


def test_ac_stop_must_exceed_start():
    with pytest.raises(ValidationError) as info:
        se.parse_amplifier_input(dict(VALID, ac_start="1000", ac_stop="100"))
    assert "ac_stop" in info.value.errors


def test_transient_step_must_resolve_source_period():
    with pytest.raises(ValidationError) as info:
        se.parse_amplifier_input(dict(VALID, freq_hz="1000", tran_step_us="200"))
    assert "tran_step_us" in info.value.errors


def test_build_netlist_contains_the_reference_circuit_and_model():
    netlist = se.build_netlist(se.parse_amplifier_input(VALID))
    for token in ("VCC vcc 0", "VIN in 0", "R1 vcc b", "R2 b 0", "RC vcc c",
                  "RE e 0", "CIN in b", "COUT c out", "RL out 0",
                  "Q1 c b e Q2N3904", ".model Q2N3904 NPN", ".control",
                  "op", "ac dec 20 1 1000000000", "tran 10u 5m",
                  "wrdata op.csv", "wrdata ac.csv", "wrdata tran.csv"):
        assert token in netlist


def test_netlist_never_uses_shell_and_has_no_user_text_injection():
    source = Path(se.__file__).read_text(encoding="utf-8")
    assert "shell=True" not in source
    assert "os.system" not in source
    netlist = se.build_netlist(se.parse_amplifier_input(dict(VALID, re="1")))
    assert ";" not in netlist


def test_parse_op_table_computes_vce_and_magnitudes():
    headers = ["vcc", "v(b)", "v(e)", "v(c)", "@q1[ic]", "@q1[ib]", "@q1[ie]"]
    rows = [[12.0, 2.00367450, 1.33287974, 9.08721626,
             1.32403477e-3, 8.88736584e-6, -1.33292214e-3]]
    dc = se.parse_op_table(headers, rows)
    assert dc.vb_v == pytest.approx(2.00367450)
    assert dc.ve_v == pytest.approx(1.33287974)
    assert dc.vc_v == pytest.approx(9.08721626)
    assert dc.vce_v == pytest.approx(9.08721626 - 1.33287974)
    assert dc.ic_a == pytest.approx(1.32403477e-3)
    assert dc.ib_a == pytest.approx(8.88736584e-6)
    assert dc.ie_a == pytest.approx(1.33292214e-3)
    assert dc.state == "Forward active"


def test_parse_ac_table_measures_gain_phase_and_cutoffs():
    headers = ["frequency", "real(v(out))", "imag(v(out))",
               "real(v(in))", "imag(v(in))"]
    rows = []
    for frequency, magnitude, phase_deg in (
        (1.0, 0.5, -120.0),
        (10.0, 1.0, -150.0),
        (1000.0, 1.7657, -179.87),
        (1e6, 1.7, -200.0),
        (1e8, 1.5, -240.0),
    ):
        phase = math.radians(phase_deg)
        rows.append([frequency,
                     magnitude * 0.01 * math.cos(phase),
                     magnitude * 0.01 * math.sin(phase),
                     0.01, 0.0])
    ac = se.parse_ac_table(headers, rows, reference_hz=1000.0)
    assert ac.reference_gain == pytest.approx(1.7657, rel=1e-4)
    assert ac.reference_gain_db == pytest.approx(20 * math.log10(1.7657), rel=1e-4)
    assert ac.reference_phase_deg == pytest.approx(-179.87, abs=0.01)
    assert ac.max_gain_db == pytest.approx(20 * math.log10(1.7657), rel=1e-4)
    assert ac.f_low_3db_hz == pytest.approx(60.96, rel=1e-2)
    assert ac.f_high_3db_hz is None
    assert "above the sweep stop" in ac.cutoff_note


def test_parse_ac_table_reports_cutoff_outside_sweep():
    headers = ["frequency", "real(v(out))", "imag(v(out))",
               "real(v(in))", "imag(v(in))"]
    rows = [[1.0, 0.009, 0.0, 0.01, 0.0], [10.0, 0.01, 0.0, 0.01, 0.0]]
    ac = se.parse_ac_table(headers, rows, reference_hz=1.0)
    assert ac.f_low_3db_hz is None
    assert ac.f_high_3db_hz is None
    assert "below the sweep start" in ac.cutoff_note
    assert "above the sweep stop" in ac.cutoff_note


def test_parse_tran_table_recovers_amplitude_and_inversion():
    headers = ["time", "v(in)", "v(out)"]
    frequency = 1000.0
    rows = []
    samples = 400
    for index in range(samples):
        time = index / (frequency * 100)
        vin = 0.010 * math.sin(2 * math.pi * frequency * time)
        vout = 0.018 * math.sin(2 * math.pi * frequency * time + math.pi)
        rows.append([time, vin, vout])
    tran = se.parse_tran_table(headers, rows, frequency_hz=frequency,
                               tran_stop_ms=4.0)
    assert tran.vin_amplitude_mv == pytest.approx(10.0, rel=1e-3)
    assert tran.vout_amplitude_mv == pytest.approx(18.0, rel=1e-3)
    assert tran.gain == pytest.approx(1.8, rel=1e-3)
    assert abs(abs(tran.phase_diff_deg) - 180.0) < 1.0
    assert tran.inverted is True


def test_engine_info_reports_availability_honestly():
    info = se.find_ngspice()
    assert isinstance(info.available, bool)
    if info.available:
        assert info.path
        assert Path(info.path).is_file()
    else:
        assert "NGSPICE_BIN" in info.detail


def test_run_simulation_refuses_unavailable_engine():
    inp = se.parse_amplifier_input(VALID)
    info = se.EngineInfo(available=False, path=None, version=None,
                         detail="ngspice not found; set NGSPICE_BIN.")
    with pytest.raises(se.EngineUnavailable):
        se.run_simulation(inp, engine=info)


requires_ngspice = pytest.mark.skipif(
    not se.find_ngspice().available,
    reason="ngspice executable not available in this environment",
)


@requires_ngspice
def test_real_ngspice_reference_operating_point():
    result = se.run_simulation(se.parse_amplifier_input(VALID), timeout=60)
    dc = result.dc
    assert 1.8 < dc.vb_v < 2.3
    assert 1.2 < dc.ve_v < 1.6
    assert 8.5 < dc.vc_v < 9.4
    assert 7.0 < dc.vce_v < 8.2
    assert 1.1e-3 < dc.ic_a < 1.6e-3
    assert dc.state == "Forward active"
    assert result.provenance.engine_version
    assert "Q2N3904" in result.provenance.model_name


@requires_ngspice
def test_real_ngspice_ac_gain_and_transient_are_measured():
    result = se.run_simulation(se.parse_amplifier_input(VALID), timeout=60)
    assert 1.4 < result.ac.reference_gain < 2.2
    assert abs(abs(result.ac.reference_phase_deg) - 180.0) < 20.0
    assert result.ac.f_low_3db_hz is not None
    assert result.ac.f_high_3db_hz is not None
    assert 8.0 < result.tran.vin_amplitude_mv < 12.0
    assert 12.0 < result.tran.vout_amplitude_mv < 24.0
    assert result.tran.inverted is True
    assert len(result.ac.frequencies_hz) > 100
    assert len(result.tran.time_ms) > 400


@requires_ngspice
def test_real_ngspice_re_change_moves_the_operating_point():
    baseline = se.run_simulation(se.parse_amplifier_input(VALID), timeout=60)
    changed = se.run_simulation(
        se.parse_amplifier_input(dict(VALID, re="0.47")), timeout=60)
    assert changed.dc.ve_v < baseline.dc.ve_v
    assert changed.dc.ic_a > baseline.dc.ic_a
    assert abs(changed.ac.reference_gain - baseline.ac.reference_gain) > 0.05


@requires_ngspice
def test_real_ngspice_amplitude_change_scales_the_waveform():
    baseline = se.run_simulation(se.parse_amplifier_input(VALID), timeout=60)
    louder = se.run_simulation(
        se.parse_amplifier_input(dict(VALID, amp_mv="20")), timeout=60)
    assert louder.tran.vin_amplitude_mv == pytest.approx(
        2 * baseline.tran.vin_amplitude_mv, rel=0.05)
    assert louder.tran.vout_amplitude_mv == pytest.approx(
        2 * baseline.tran.vout_amplitude_mv, rel=0.05)
