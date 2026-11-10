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
