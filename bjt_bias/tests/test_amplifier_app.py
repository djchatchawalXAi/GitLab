"""Route and rendering tests for the Lab 04 amplifier workbench."""

import math
import re
from pathlib import Path

import pytest

import app as app_module
from app import create_app
import spice_engine as se

VALID = {
    "vcc": "12", "r1": "100", "r2": "22", "rc": "2.2", "re": "1",
    "rl": "10", "cin": "10", "cout": "10", "amp_mv": "10",
    "freq_hz": "1000", "ac_start": "1", "ac_stop": "1e9",
    "ac_ppd": "20", "tran_stop_ms": "5", "tran_step_us": "10",
}


@pytest.fixture
def client():
    flask_app = create_app()
    flask_app.config.update(TESTING=True)
    return flask_app.test_client()


def test_amplifier_form_renders_every_input_and_engine_badge(client):
    response = client.get("/amplifier")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Lab 04: BJT Amplifier Simulator" in body
    for name in VALID:
        assert f'name="{name}"' in body
    assert "Run SPICE Simulation" in body
    assert "ngspice" in body
    assert "DC Bias Parameters" in body
    assert "Signal, Load &amp; Analysis Parameters" in body
    assert "Analysis Mode" in body
    for mode in ("all", "dc", "ac", "tran"):
        assert f'id="view-{mode}"' in body
    assert "<script" not in body
    assert "onchange=" not in body


def test_amplifier_result_view_persists(client, monkeypatch):
    monkeypatch.setattr(
        app_module, "find_ngspice",
        lambda: se.EngineInfo(False, None, None, "ngspice not found; set NGSPICE_BIN."),
    )
    body = client.post(
        "/amplifier/simulate", data=dict(VALID, view="ac")
    ).get_data(as_text=True)
    assert re.search(r'id="view-ac"[^>]*checked', body)


def test_amplifier_unknown_view_falls_back_to_all(client):
    body = client.get("/amplifier?view=bogus").get_data(as_text=True)
    assert re.search(r'id="view-all"[^>]*checked', body)


def test_amplifier_page_is_reachable_from_lab_03(client):
    body = client.get("/").get_data(as_text=True)
    assert 'href="/amplifier"' in body
    assert "Lab 04 Amplifier" in body


def test_amplifier_validation_error_has_no_stale_results(client):
    response = client.post("/amplifier/simulate", data=dict(VALID, re="0"))
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "RE must be greater than 0." in body
    assert 'value="0"' in body
    assert "DC operating point" not in body
    assert "RUN OK" not in body


def _fake_result(*, clipped: bool):
    inp = se.parse_amplifier_input(VALID)
    dc = se.parse_op_table(
        ["vcc", "v(b)", "v(e)", "v(c)", "@q1[ic]", "@q1[ib]", "@q1[ie]"],
        [[12.0, 2.00367450, 1.33287974, 9.08721626,
          1.32403477e-3, 8.88736584e-6, -1.33292214e-3]],
    )
    ac = se.parse_ac_table(
        ["frequency", "real(v(out))", "imag(v(out))",
         "real(v(in))", "imag(v(in))"],
        [[10.0, 0.005 * math.cos(-2.5), 0.005 * math.sin(-2.5), 0.01, 0.0],
         [1000.0, 0.017657 * math.cos(-3.139), 0.017657 * math.sin(-3.139),
          0.01, 0.0],
         [1e7, 0.015 * math.cos(-4.0), 0.015 * math.sin(-4.0), 0.01, 0.0]],
        reference_hz=1000.0,
    )
    frequency = 1000.0
    tran_rows = []
    for index in range(400):
        time = index / (frequency * 100)
        vin = 0.010 * math.sin(2 * math.pi * frequency * time)
        wave = 0.018 * math.sin(2 * math.pi * frequency * time + math.pi)
        if clipped:
            wave = max(-0.012, min(0.012, wave))
        tran_rows.append([time, vin, wave])
    tran = se.parse_tran_table(
        ["time", "v(in)", "v(out)"], tran_rows,
        frequency_hz=frequency, tran_stop_ms=4.0,
    )
    analytical = se.analytical_reference(inp)
    provenance = se.Provenance(
        engine_path="C:/fake/ngspice_con.exe",
        engine_version="test",
        model_name=se.MODEL_NAME,
        model_source=se.MODEL_SOURCE,
        netlist=se.build_netlist(inp),
        command=("ngspice_con.exe", "-b", "ce.cir"),
        run_id="test-run",
        started_at_utc="2026-11-25T00:00:00+00:00",
        duration_ms=1.0,
        exit_code=0,
        log_tail="ok",
    )
    return se.SimulationResult(
        input=inp, dc=dc, ac=ac, tran=tran, analytical=analytical,
        comparison_rows=se.compare_models(analytical, dc),
        comparison_note=se.COMPARISON_NOTE, provenance=provenance,
    )


def test_amplifier_labels_analytical_and_spice_and_shows_clipping(client, monkeypatch):
    result = _fake_result(clipped=True)
    monkeypatch.setattr(
        app_module, "find_ngspice",
        lambda: se.EngineInfo(True, "C:/fake/ngspice_con.exe", "test", "ok"),
    )
    monkeypatch.setattr(app_module, "run_simulation", lambda *args, **kwargs: result)
    body = client.post("/amplifier/simulate", data=VALID).get_data(as_text=True)
    assert "Analytical Approximation" in body
    assert "SPICE Simulation" in body
    assert "clipping detected" in body
    assert "RUN OK" in body


@pytest.mark.parametrize("field,value", [
    ("freq_hz", "0"),
    ("ac_start", "0"),
    ("ac_stop", "0.001"),
])
def test_amplifier_invalid_frequency_is_form_error_not_500(client, field, value):
    response = client.post("/amplifier/simulate", data=dict(VALID, **{field: value}))
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Please fix the highlighted fields" in body
    assert "DC operating point" not in body
    assert "RUN OK" not in body


def test_amplifier_engine_unavailable_is_reported_honestly(client, monkeypatch):
    monkeypatch.setattr(
        app_module, "find_ngspice",
        lambda: se.EngineInfo(False, None, None, "ngspice not found; set NGSPICE_BIN."),
    )
    body = client.post("/amplifier/simulate", data=VALID).get_data(as_text=True)
    assert "RUN FAILED" in body
    assert "ngspice not found" in body
    assert "DC operating point" not in body


def test_amplifier_engine_failure_is_reported_without_fake_success(client, monkeypatch):
    def boom(*args, **kwargs):
        raise se.SpiceRunError("ngspice exited with code 1.", "fake log line")

    monkeypatch.setattr(
        app_module, "find_ngspice",
        lambda: se.EngineInfo(True, "C:/fake/ngspice_con.exe", "test", "ok"),
    )
    monkeypatch.setattr(app_module, "run_simulation", boom)
    body = client.post("/amplifier/simulate", data=VALID).get_data(as_text=True)
    assert "RUN FAILED" in body
    assert "exited with code 1" in body
    assert "fake log line" in body
    assert "RUN OK" not in body


requires_ngspice = pytest.mark.skipif(
    not se.find_ngspice().available,
    reason="ngspice executable not available in this environment",
)


@requires_ngspice
def test_amplifier_valid_post_renders_real_spice_sections(client):
    response = client.post("/amplifier/simulate", data=VALID)
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "RUN OK" in body
    assert "SPICE Simulation" in body
    assert "Analytical Approximation" in body
    assert ".op" in body
    assert ".ac" in body
    assert ".tran" in body
    assert "2N3904" in body
    assert "Q1 c b e Q2N3904" in body
    assert "Gain at 1000 Hz" in body
    assert "Low −3 dB cutoff" in body
    assert "phase inverted" in body
    assert "<svg class=\"plot-svg\"" in body
    assert "Frequency (Hz, log scale)" in body
    assert "Time (ms)" in body
    assert "<script" not in body


@requires_ngspice
def test_amplifier_re_change_updates_real_output(client):
    baseline = client.post("/amplifier/simulate", data=VALID).get_data(as_text=True)
    changed = client.post(
        "/amplifier/simulate", data=dict(VALID, re="0.47")).get_data(as_text=True)
    assert baseline != changed
    assert "RUN OK" in changed


def test_amplifier_css_contract():
    css = (Path(__file__).resolve().parent.parent / "static" / "style.css").read_text(
        encoding="utf-8")
    for token in (".amp-layout", ".engine-badge", ".metric-grid", ".plot-svg",
                  ".provenance", ".input-group", ".run-error"):
        assert token in css
    assert "<script" not in css
