"""Tests del Modulo 8.3: panel white-label de branding y accesibilidad."""

import pytest

from app.models.usuario import Usuario
from app.services.auth import hash_password
from tests.conftest import TestingSessionLocal

PANEL = "/admin/personalizacion"


@pytest.fixture(autouse=True)
def _branding_usa_bd_de_pruebas(monkeypatch):
    """El context processor y los endpoints resuelven contra la BD de pruebas."""
    import app.database as database

    monkeypatch.setattr(database, "SessionLocal", TestingSessionLocal)


def _login_headers(client, email, password="empleado123"):
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
def empleado_headers(client, admin_user):
    db = TestingSessionLocal()
    try:
        db.add(Usuario(
            email="empleado@test.com",
            password_hash=hash_password("empleado123"),
            rol="EMPLEADO",
            comercio_id=1,
            activo=True,
        ))
        db.commit()
    finally:
        db.close()
    return _login_headers(client, "empleado@test.com")


def _obtener_comercio():
    from app.models.comercio import Comercio

    db = TestingSessionLocal()
    try:
        return db.query(Comercio).filter(Comercio.id == 1).first()
    finally:
        db.close()


def _post_panel(client, headers, **overrides):
    datos = {
        "tema_preset": "clasico_paws",
        "color_primario": "#B45309",
        "color_secundario": "#BE123C",
        "logo_url": "",
        "banner_url": "",
        "a11y_modo": "normal",
    }
    datos.update(overrides)
    return client.post(PANEL, data=datos, headers=headers, follow_redirects=False)


class TestAccesoPanel:
    def test_anonimo_401(self, client):
        resp = client.get(PANEL)
        assert resp.status_code == 401

    def test_cliente_rol_403(self, client, auth_headers):
        resp = client.get(PANEL, headers=auth_headers)
        assert resp.status_code == 403

    def test_empleado_get_403(self, client, empleado_headers):
        resp = client.get(PANEL, headers=empleado_headers)
        assert resp.status_code == 403

    def test_empleado_post_403(self, client, empleado_headers):
        resp = _post_panel(client, empleado_headers)
        assert resp.status_code == 403

    def test_admin_ve_panel_completo(self, client, admin_headers):
        resp = client.get(PANEL, headers=admin_headers)
        assert resp.status_code == 200
        assert "form-personalizacion" in resp.text
        assert "branding-data" in resp.text
        assert "picker-primario" in resp.text
        assert "picker-secundario" in resp.text
        assert "select-a11y-modo" in resp.text
        assert "switch-dyslexic" in resp.text
        assert "panel-preview" in resp.text
        assert "/static/js/branding_preview.js" in resp.text

    def test_catalogo_presets_renderizado_en_cards(self, client, admin_headers):
        from app.core.skins_config import SKINS_PRESETS

        resp = client.get(PANEL, headers=admin_headers)
        for nombre, preset in SKINS_PRESETS.items():
            assert f'value="{nombre}"' in resp.text
            assert f'background: {preset["color_primario"]}' in resp.text

    def test_valores_actuales_del_comercio_en_formulario(self, client, admin_headers):
        resp = client.get(PANEL, headers=admin_headers)
        assert resp.status_code == 200
        assert 'value="#1e40af"' in resp.text
        assert 'value="#1E40AF"' in resp.text
        assert 'checked' in resp.text


class TestAccesoPost:
    def test_anonimo_post_401(self, client):
        resp = _post_panel(client, {})
        assert resp.status_code == 401

    def test_cliente_post_403(self, client, auth_headers):
        resp = _post_panel(client, auth_headers)
        assert resp.status_code == 403


class TestPostPersistencia:
    def test_guardado_valido_persiste_todo(self, client, admin_headers):
        resp = _post_panel(
            client,
            admin_headers,
            tema_preset="warm_pet",
            a11y_modo="daltonismo",
            a11y_dyslexic="on",
            logo_url="https://cdn.example.com/logo.webp",
        )
        assert resp.status_code == 303
        assert resp.headers["location"].startswith(PANEL)
        assert "success" in resp.headers["location"]

        comercio = _obtener_comercio()
        assert comercio.tema_preset == "warm_pet"
        assert comercio.color_primario == "#B45309"
        assert comercio.color_secundario == "#BE123C"
        assert comercio.a11y_modo == "daltonismo"
        assert comercio.a11y_dyslexic is True
        assert comercio.logo_url == "https://cdn.example.com/logo.webp"

    def test_checkbox_ausente_guarda_false(self, client, admin_headers):
        resp = _post_panel(client, admin_headers)
        assert resp.status_code == 303
        assert _obtener_comercio().a11y_dyslexic is False

    def test_logo_vacio_se_guarda_como_none(self, client, admin_headers):
        _post_panel(client, admin_headers, logo_url="https://viejo.com/l.png")
        resp = _post_panel(client, admin_headers, logo_url="")
        assert resp.status_code == 303
        assert _obtener_comercio().logo_url is None

    def test_panel_refleja_valores_guardados(self, client, admin_headers):
        _post_panel(
            client,
            admin_headers,
            color_primario="#B45309",
            color_secundario="#BE123C",
            tema_preset="warm_pet",
            a11y_dyslexic="on",
        )
        resp = client.get(PANEL, headers=admin_headers)
        assert resp.status_code == 200
        assert 'value="#b45309"' in resp.text
        assert 'value="#B45309"' in resp.text
        assert "warm_pet" in resp.text

    @pytest.mark.parametrize(
        "overrides",
        [
            {"color_primario": "azul"},
            {"color_primario": "#12345"},
            {"color_secundario": "#GGGGGG"},
            {"tema_preset": "neon_party"},
            {"a11y_modo": "solarizado"},
        ],
    )
    def test_datos_invalidos_redirigen_con_error_sin_persistir(
        self, client, admin_headers, overrides
    ):
        resp = _post_panel(client, admin_headers, **overrides)
        assert resp.status_code == 303
        assert "error=" in resp.headers["location"]

        comercio = _obtener_comercio()
        assert comercio.color_primario == "#1E40AF"
        assert comercio.color_secundario == "#0D9488"
        assert comercio.tema_preset == "clasico_paws"


class TestIntegracionPaginasPublicas:
    def test_cambio_desde_panel_se_refleja_en_pagina_publica(self, client, admin_headers):
        resp = _post_panel(
            client,
            admin_headers,
            tema_preset="menta_vet",
            color_primario="#059669",
            color_secundario="#10B981",
        )
        assert resp.status_code == 303

        pagina = client.get("/page/")
        assert pagina.status_code == 200
        assert "--color-primario: #059669" in pagina.text
        assert "--color-secundario: #10B981" in pagina.text
        assert "--texto-sobre-primario: #000000" in pagina.text
        assert "--texto-sobre-secundario: #000000" in pagina.text
        assert '<meta name="theme-color" content="#059669">' in pagina.text
        assert "bg-indigo-600" not in pagina.text

    def test_modos_a11y_del_panel_llegan_al_html_publico(self, client, admin_headers):
        resp = _post_panel(
            client,
            admin_headers,
            a11y_modo="alto_contraste",
            a11y_dyslexic="on",
        )
        assert resp.status_code == 303

        pagina = client.get("/page/")
        assert pagina.status_code == 200
        assert 'data-a11y-modo="alto_contraste"' in pagina.text
        assert "a11y-dyslexic" in pagina.text

    def test_colores_con_texto_blanco_calculan_correctamente(self, client, admin_headers):
        resp = _post_panel(client, admin_headers, color_primario="#1E40AF")
        assert resp.status_code == 303

        pagina = client.get("/page/")
        assert "--texto-sobre-primario: #FFFFFF" in pagina.text
