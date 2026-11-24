"""Route and rendering tests for the Lab 04 amplifier workbench."""

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
    assert "<script" not in body
    assert "onchange=" not in body


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
    assert "SPICE .op" in body
    assert "SPICE .ac" in body
    assert "SPICE .tran" in body
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
