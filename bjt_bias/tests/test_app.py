import pytest

from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_get_form_shows_all_fields_with_units(client):
    response = client.get("/")
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    for name in ("vcc", "r1", "r2", "rc", "re", "beta", "vbe"):
        assert f'name="{name}"' in body
    assert "kΩ" in body
    assert "VBE" in body


def test_reset_link_renders_a_blank_form(client):
    body = client.get("/?blank=1").get_data(as_text=True)
    assert 'value=""' in body


VALID = {
    "vcc": "12", "r1": "47", "r2": "10", "rc": "2.2",
    "re": "0.47", "beta": "150", "vbe": "0.7",
}


def test_valid_post_shows_results_and_cross_check(client):
    response = client.post("/calculate", data=VALID)
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Forward active" in body
    assert "17.74" in body
    assert "2.661" in body
    assert "4.887" in body
    assert "Thevenin" in body and "Nodal" in body
    assert "agree" in body.lower()


def test_invalid_post_returns_form_with_errors(client):
    response = client.post("/calculate", data=dict(VALID, r1="0"))
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "greater than 0" in body
    assert 'value="0"' in body
    assert "Operating point" not in body


def test_missing_or_empty_body_does_not_500(client):
    assert client.post("/calculate", data={}).status_code == 200
    assert client.post("/calculate").status_code == 200


def test_markup_is_escaped(client):
    response = client.post("/calculate", data=dict(VALID, vcc="<script>alert(1)</script>"))
    body = response.get_data(as_text=True)
    assert "&lt;script&gt;" in body
    assert "<script>alert(1)</script>" not in body


def test_saturation_page_is_not_labelled_forward_active(client):
    response = client.post("/calculate", data=dict(VALID, r1="22", r2="47", re="0.1"))
    body = response.get_data(as_text=True)
    assert "Saturation" in body
    assert "Forward active" not in body
    assert "extrapolation" in body.lower()
