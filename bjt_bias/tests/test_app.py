import re

import pytest

from app import create_app


VALID_VD = {"circuit": "voltage_divider", "vcc": "12", "r1": "47", "r2": "10",
            "rc": "2.2", "re": "0.47", "beta": "150", "vbe": "0.7"}
VALID_FIXED = {"circuit": "fixed_bias", "vcc": "12", "rb": "470",
               "rc": "2.2", "beta": "150", "vbe": "0.7"}
VALID_EMITTER = {"circuit": "emitter_bias", "vcc": "12", "rb": "470", "rc": "2.2",
                 "re": "0.47", "beta": "150", "vbe": "0.7"}


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def _tag(body, attribute, value):
    pattern = rf'<input[^>]*{attribute}="{re.escape(value)}"[^>]*>'
    match = re.search(pattern, body)
    assert match is not None, f"no input with {attribute}={value!r}"
    return match.group(0)


def test_get_form_shows_all_fields_and_picker(client):
    response = client.get("/")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    for name in ("vcc", "r1", "r2", "rb", "rc", "re", "beta", "vbe"):
        assert f'name="{name}"' in body
    for circuit in ("voltage-divider", "fixed-bias", "emitter-bias"):
        assert f'id="circuit-{circuit}"' in body
    assert "kΩ" in body
    assert "VBE" in body
    for css_class in ("for-voltage-divider", "for-fixed-bias", "for-emitter-bias"):
        assert css_class in body


def test_default_circuit_is_voltage_divider(client):
    body = client.get("/").get_data(as_text=True)
    assert 'id="circuit-voltage-divider"' in body
    assert "checked" in _tag(body, "id", "circuit-voltage-divider")
    assert "checked" not in _tag(body, "id", "circuit-fixed-bias")


def test_query_selects_circuit_without_changing_defaults(client):
    body = client.get("/?circuit=fixed_bias").get_data(as_text=True)
    assert "checked" in _tag(body, "id", "circuit-fixed-bias")
    assert "checked" not in _tag(body, "id", "circuit-voltage-divider")
    assert 'value="470"' in _tag(body, "name", "rb")
    assert 'value="2.2"' in _tag(body, "name", "rc")


def test_unknown_query_circuit_falls_back(client):
    response = client.get("/?circuit=bogus")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "checked" in _tag(body, "id", "circuit-voltage-divider")


def test_reset_links_keep_each_circuit(client):
    body = client.get("/?circuit=emitter_bias").get_data(as_text=True)
    assert "blank=1" in body
    assert "circuit=emitter_bias" in body
    assert body.count("reset-link-for-") == 3


def test_reset_link_renders_a_blank_form(client):
    body = client.get("/?blank=1").get_data(as_text=True)
    assert 'value=""' in body


@pytest.mark.parametrize(
    ("payload", "caption", "ib", "ic", "vce"),
    [
        (VALID_VD, "Results for Voltage Divider Bias", "17.74", "2.661", "4.887"),
        (VALID_FIXED, "Results for Fixed Bias", "24.04", "3.606", "4.066"),
        (VALID_EMITTER, "Results for Emitter Bias", "20.89", "3.133", "3.624"),
    ],
)
def test_valid_post_each_circuit(client, payload, caption, ib, ic, vce):
    response = client.post("/calculate", data=payload)
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert caption in body
    assert "Forward active" in body
    assert ib in body
    assert ic in body
    assert vce in body
    assert "Closed-form" in body
    assert "Nodal" in body
    assert "agree" in body


@pytest.mark.parametrize(
    ("payload", "field", "message", "submitted"),
    [
        (dict(VALID_VD, r1="0"), "r1", "R1 must be greater than 0.", "0"),
        (dict(VALID_FIXED, rb="abc"), "rb", "RB must be a number.", "abc"),
        (dict(VALID_EMITTER, re="0"), "re", "RE must be greater than 0.", "0"),
    ],
)
def test_invalid_post_per_circuit(client, payload, field, message, submitted):
    response = client.post("/calculate", data=payload)
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert message in body
    assert f'value="{submitted}"' in _tag(body, "name", field)
    assert "Operating point" not in body


def test_unknown_circuit_post_is_form_error(client):
    response = client.post("/calculate", data=dict(VALID_VD, circuit="bogus"))
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Choose a valid circuit type" in body


def test_missing_or_empty_body_does_not_500(client):
    assert client.post("/calculate", data={}).status_code == 200
    assert client.post("/calculate").status_code == 200


def test_markup_is_escaped(client):
    response = client.post(
        "/calculate", data=dict(VALID_VD, vcc="<script>alert(1)</script>")
    )
    body = response.get_data(as_text=True)
    assert "&lt;script&gt;" in body
    assert "<script>alert(1)</script>" not in body


@pytest.mark.parametrize(
    "payload",
    [
        dict(VALID_FIXED, rb="47"),
        dict(VALID_EMITTER, rb="47", re="0.47"),
    ],
)
def test_saturation_page_is_not_labelled_forward_active(client, payload):
    body = client.post("/calculate", data=payload).get_data(as_text=True)
    assert "Saturation" in body
    assert "extrapolation" in body
    assert "Forward active" not in body


def test_results_markup_is_tagged_for_css(client):
    body = client.post("/calculate", data=VALID_VD).get_data(as_text=True)
    assert "results-for-voltage-divider" in body
    assert "results-placeholder-for-fixed-bias" in body
    assert "results-placeholder-for-emitter-bias" in body
    for circuit in ("voltage-divider", "fixed-bias", "emitter-bias"):
        assert f"reset-link-for-{circuit}" in body


def test_page_has_no_javascript(client):
    body = client.get("/").get_data(as_text=True)
    assert "<script" not in body
    assert "onchange=" not in body
    assert "onclick=" not in body
    assert "onsubmit=" not in body
