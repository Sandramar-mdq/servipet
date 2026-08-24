"""Tests del Modulo 8.1: skins, presets y variables CSS dinamicas."""

import re
from types import SimpleNamespace

import pytest

from app.core.skins_config import (
    HEX_COLOR_PATTERN,
    PRESET_DEFAULT,
    SKINS_PRESETS,
    resolver_skin,
)
from app.models.comercio import Comercio
from tests.conftest import TestingSessionLocal


def _crear_comercio(client, **overrides):
    payload = {"nombre": "Comercio Skin", **overrides}
    return client.post("/comercios/", json=payload)


@pytest.fixture(autouse=True)
def _skin_usa_bd_de_pruebas(monkeypatch):
    """El context processor resuelve contra la misma BD en memoria que los tests."""
    import app.database as database

    monkeypatch.setattr(database, "SessionLocal", TestingSessionLocal)


def _seed_comercio_skin(db, **overrides):
    datos = {
        "id": 1,
        "nombre": "Comercio Principal",
        "tipo_comercio": "VETERINARIA",
        "activo": True,
    }
    datos.update(overrides)
    comercio = Comercio(**datos)
    db.add(comercio)
    db.commit()
    db.refresh(comercio)
    return comercio


class TestDefaultsSkin:
    def test_defaults_al_crear_comercio_via_api(self, client):
        resp = _crear_comercio(client)
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["tema_preset"] == PRESET_DEFAULT
        assert data["color_primario"] == "#1E40AF"
        assert data["color_secundario"] == "#0D9488"
        assert data["logo_url"] is None
        assert data["banner_url"] is None
        assert data["a11y_modo"] == "normal"
        assert data["a11y_dyslexic"] is False

    def test_defaults_al_crear_comercio_via_orm(self, client):
        db = TestingSessionLocal()
        try:
            comercio = _seed_comercio_skin(db)
            assert comercio.tema_preset == PRESET_DEFAULT
            assert comercio.color_primario == "#1E40AF"
            assert comercio.color_secundario == "#0D9488"
            assert comercio.logo_url is None
            assert comercio.banner_url is None
            assert comercio.a11y_modo == "normal"
            assert comercio.a11y_dyslexic is False
        finally:
            db.close()


class TestValidacionColoresHex:
    @pytest.mark.parametrize("campo", ["color_primario", "color_secundario"])
    @pytest.mark.parametrize("color", ["blue", "#12345", "#1234567", "#GGGGGG", "1E40AF", "", "#abc"])
    def test_hex_invalido_rechazado_en_create(self, client, campo, color):
        resp = _crear_comercio(client, **{campo: color})
        assert resp.status_code == 422

    @pytest.mark.parametrize("campo", ["color_primario", "color_secundario"])
    def test_hex_invalido_rechazado_en_update(self, client, campo):
        resp = _crear_comercio(client)
        comercio_id = resp.json()["id"]
        resp = client.put(f"/comercios/{comercio_id}", json={campo: "rojo"})
        assert resp.status_code == 422

    def test_hex_valido_aceptado_y_persistido(self, client):
        resp = _crear_comercio(
            client, tema_preset="menta_vet", color_primario="#059669", color_secundario="#10B981"
        )
        assert resp.status_code == 201, resp.text
        comercio_id = resp.json()["id"]

        resp = client.get(f"/comercios/{comercio_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tema_preset"] == "menta_vet"
        assert data["color_primario"] == "#059669"
        assert data["color_secundario"] == "#10B981"

    def test_update_colores_validos_persisten(self, client):
        comercio_id = _crear_comercio(client).json()["id"]
        resp = client.put(
            f"/comercios/{comercio_id}",
            json={
                "tema_preset": "dark_mode",
                "color_primario": "#374151",
                "color_secundario": "#4B5563",
                "a11y_modo": "normal",
                "a11y_dyslexic": True,
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["tema_preset"] == "dark_mode"
        assert data["color_primario"] == "#374151"
        assert data["color_secundario"] == "#4B5563"
        assert data["a11y_dyslexic"] is True


class TestValidacionPreset:
    def test_preset_desconocido_rechazado_en_create(self, client):
        resp = _crear_comercio(client, tema_preset="neon_party")
        assert resp.status_code == 422

    def test_preset_desconocido_rechazado_en_update(self, client):
        comercio_id = _crear_comercio(client).json()["id"]
        resp = client.put(f"/comercios/{comercio_id}", json={"tema_preset": "no_existe"})
        assert resp.status_code == 422

    def test_todos_los_presets_del_catalogo_son_aceptados(self, client):
        for nombre in SKINS_PRESETS:
            resp = _crear_comercio(client, nombre=f"C {nombre}", tema_preset=nombre)
            assert resp.status_code == 201, f"Fallo preset {nombre}: {resp.text}"
            assert resp.json()["tema_preset"] == nombre


class TestCatalogoPresets:
    def test_preset_default_esta_en_el_catalogo(self):
        assert PRESET_DEFAULT in SKINS_PRESETS

    def test_colores_del_catalogo_son_hex_validos(self):
        patron = re.compile(HEX_COLOR_PATTERN)
        for nombre, preset in SKINS_PRESETS.items():
            for campo in ("color_primario", "color_secundario"):
                assert patron.match(preset[campo]), f"{nombre}.{campo} invalido: {preset[campo]}"

    def test_valores_de_spec(self):
        assert SKINS_PRESETS["clasico_paws"] == {
            "color_primario": "#1E40AF",
            "color_secundario": "#0D9488",
        }
        assert SKINS_PRESETS["menta_vet"] == {
            "color_primario": "#059669",
            "color_secundario": "#10B981",
        }
        assert SKINS_PRESETS["warm_pet"] == {
            "color_primario": "#D97706",
            "color_secundario": "#E11D48",
        }
        assert SKINS_PRESETS["dark_mode"] == {
            "color_primario": "#374151",
            "color_secundario": "#4B5563",
        }


class TestResolverSkin:
    def test_fallback_sin_comercio(self):
        skin = resolver_skin(None)
        assert skin == {
            "tema_preset": "clasico_paws",
            "color_primario": "#1E40AF",
            "color_secundario": "#0D9488",
            "texto_sobre_primario": "#FFFFFF",
            "texto_sobre_secundario": "#000000",
        }

    def test_preset_desconocido_cae_al_default(self):
        fake = SimpleNamespace(
            tema_preset="desconocido", color_primario="#123456", color_secundario="#654321"
        )
        skin = resolver_skin(fake)
        assert skin["tema_preset"] == "clasico_paws"
        assert skin["color_primario"] == "#123456"

    def test_color_invalido_persistido_usa_default(self):
        fake = SimpleNamespace(tema_preset="menta_vet", color_primario="roto", color_secundario=None)
        skin = resolver_skin(fake)
        assert skin["tema_preset"] == "menta_vet"
        assert skin["color_primario"] == "#1E40AF"
        assert skin["color_secundario"] == "#0D9488"


class TestInyeccionCssDinamica:
    def test_variables_css_custom_en_base_html(self, client):
        db = TestingSessionLocal()
        try:
            _seed_comercio_skin(
                db,
                tema_preset="menta_vet",
                color_primario="#059669",
                color_secundario="#10B981",
            )
        finally:
            db.close()

        resp = client.get("/page/")
        assert resp.status_code == 200
        assert "--color-primario: #059669" in resp.text
        assert "--color-secundario: #10B981" in resp.text

    def test_variables_css_fallback_sin_comercio_en_bd(self, client):
        resp = client.get("/page/")
        assert resp.status_code == 200
        assert "--color-primario: #1E40AF" in resp.text
        assert "--color-secundario: #0D9488" in resp.text

    def test_hook_a11y_en_body(self, client):
        db = TestingSessionLocal()
        try:
            _seed_comercio_skin(db, a11y_dyslexic=True)
        finally:
            db.close()

        resp = client.get("/page/")
        assert resp.status_code == 200
        assert "a11y-dyslexic" in resp.text
        assert 'data-a11y-modo="normal"' in resp.text

    def test_base_public_renderiza_variables_desde_comercio(self):
        from app.core.templating import get_templates

        comercio = SimpleNamespace(
            color_primario="#D97706",
            color_secundario="#E11D48",
            tema_preset="warm_pet",
            a11y_modo="normal",
            a11y_dyslexic=False,
        )
        templates = get_templates()
        plantilla = templates.env.from_string('{% extends "portal/base_public.html" %}')
        html = plantilla.render(
            {
                "request": None,
                "comercio": comercio,
                "skin": resolver_skin(comercio),
            }
        )
        assert "--color-primario: #D97706" in html
        assert "--color-secundario: #E11D48" in html
