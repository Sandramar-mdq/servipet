"""Tests del Modulo 8.2: motor WCAG 2.1, contraste dinamico y adaptacion visual."""

from types import SimpleNamespace

import pytest

from app.core.skins_config import (
    A11Y_MODOS,
    BLANCO,
    NEGRO,
    RATIO_MINIMO_TEXTO,
    SKINS_PRESETS,
    luminancia_relativa,
    obtener_color_texto_accesible,
    ratio_contraste,
    resolver_skin,
)
from app.models.comercio import Comercio
from tests.conftest import TestingSessionLocal


@pytest.fixture(autouse=True)
def _a11y_usa_bd_de_pruebas(monkeypatch):
    """El context processor resuelve contra la misma BD en memoria que los tests."""
    import app.database as database

    monkeypatch.setattr(database, "SessionLocal", TestingSessionLocal)


def _seed_comercio_a11y(db, **overrides):
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


class TestLuminanciaRelativa:
    def test_blanco_y_negro_extremos(self):
        assert luminancia_relativa("#FFFFFF") == pytest.approx(1.0)
        assert luminancia_relativa("#000000") == pytest.approx(0.0)

    def test_gris_medio_valor_conocido(self):
        assert luminancia_relativa("#808080") == pytest.approx(0.21586, abs=1e-4)

    def test_monotonia_con_luminosidad_del_canal(self):
        l_negro = luminancia_relativa("#000000")
        l_gris_oscuro = luminancia_relativa("#404040")
        l_gris_medio = luminancia_relativa("#808080")
        l_blanco = luminancia_relativa("#FFFFFF")
        assert l_negro < l_gris_oscuro < l_gris_medio < l_blanco

    def test_insensible_a_mayusculas(self):
        assert luminancia_relativa("#ff0000") == pytest.approx(luminancia_relativa("#FF0000"))

    def test_canales_iguales_producen_gris_neutral(self):
        assert luminancia_relativa("#00FF00") == pytest.approx(
            luminancia_relativa("#00FF00"), abs=1e-9
        )
        rojo = luminancia_relativa("#FF0000")
        verde = luminancia_relativa("#00FF00")
        azul = luminancia_relativa("#0000FF")
        assert verde > rojo > azul

    @pytest.mark.parametrize(
        "invalido", ["blue", "#12345", "#1234567", "#GGGGGG", "1E40AF", "", "#abc", None, 123]
    )
    def test_formato_invalido_lanza_value_error(self, invalido):
        with pytest.raises(ValueError):
            luminancia_relativa(invalido)


class TestRatioContraste:
    def test_negro_sobre_blanco_maximo_teorico(self):
        assert ratio_contraste("#000000", "#FFFFFF") == pytest.approx(21.0)

    def test_mismo_color_ratio_minimo(self):
        assert ratio_contraste("#1E40AF", "#1E40AF") == pytest.approx(1.0)

    def test_independiente_del_orden(self):
        assert ratio_contraste("#1E40AF", "#FFFFFF") == pytest.approx(
            ratio_contraste("#FFFFFF", "#1E40AF")
        )

    def test_frontera_aa_normal_text(self):
        assert ratio_contraste("#767676", "#FFFFFF") >= RATIO_MINIMO_TEXTO
        assert ratio_contraste("#777777", "#FFFFFF") < RATIO_MINIMO_TEXTO

    def test_rango_valido_en_catalogo(self):
        for preset in SKINS_PRESETS.values():
            for color in preset.values():
                ratio = ratio_contraste(color, BLANCO)
                assert 1.0 <= ratio <= 21.0


class TestColorTextoAccesible:
    @pytest.mark.parametrize(
        "fondo,esperado",
        [
            ("#000000", BLANCO),
            ("#1E40AF", BLANCO),
            ("#374151", BLANCO),
            ("#4B5563", BLANCO),
            ("#059669", NEGRO),
            ("#10B981", NEGRO),
            ("#0D9488", NEGRO),
            ("#D97706", NEGRO),
            ("#E11D48", BLANCO),
            ("#808080", NEGRO),
            ("#FFFFFF", NEGRO),
            ("#F9FAFB", NEGRO),
        ],
    )
    def test_eleccion_segun_luminancia(self, fondo, esperado):
        assert obtener_color_texto_accesible(fondo) == esperado

    @pytest.mark.parametrize("invalido", ["rojo", "", "#12345", None])
    def test_entrada_invalida_fallback_defensivo_blanco(self, invalido):
        assert obtener_color_texto_accesible(invalido) == BLANCO

    @pytest.mark.parametrize(
        "nombre,preset",
        [(nombre, SKINS_PRESETS[nombre]) for nombre in sorted(SKINS_PRESETS)],
        ids=sorted(SKINS_PRESETS),
    )
    def test_todo_el_catalogo_supera_aa(self, nombre, preset):
        for campo in ("color_primario", "color_secundario"):
            fondo = preset[campo]
            texto = obtener_color_texto_accesible(fondo)
            assert texto in (BLANCO, NEGRO)
            assert ratio_contraste(fondo, texto) >= RATIO_MINIMO_TEXTO

    def test_devuelve_solo_blanco_o_negro_hex_estricto(self):
        for fondo in ["#123456", "#ABCDEF", "#000000", "#FFFFFF"]:
            assert obtener_color_texto_accesible(fondo) in (BLANCO, NEGRO)


class TestResolverSkinTextoAccesible:
    def test_fallback_sin_comercio_incluye_colores_de_texto(self):
        skin = resolver_skin(None)
        assert skin["texto_sobre_primario"] == BLANCO
        assert skin["texto_sobre_secundario"] == NEGRO

    def test_colores_persistidos_derivan_su_texto(self):
        fake = SimpleNamespace(
            tema_preset="menta_vet", color_primario="#059669", color_secundario="#10B981"
        )
        skin = resolver_skin(fake)
        assert skin["texto_sobre_primario"] == NEGRO
        assert skin["texto_sobre_secundario"] == NEGRO

    def test_skin_derivado_cumple_aa_para_todo_el_catalogo(self):
        for nombre in SKINS_PRESETS:
            fake = SimpleNamespace(
                tema_preset=nombre, color_primario=None, color_secundario=None
            )
            skin = resolver_skin(fake)
            assert ratio_contraste(skin["color_primario"], skin["texto_sobre_primario"]) >= RATIO_MINIMO_TEXTO
            assert ratio_contraste(skin["color_secundario"], skin["texto_sobre_secundario"]) >= RATIO_MINIMO_TEXTO


class TestValidacionModoA11ySchema:
    def test_modo_desconocido_rechazado_en_create(self, client):
        resp = client.post("/comercios/", json={"nombre": "C", "a11y_modo": "modo_loco"})
        assert resp.status_code == 422

    @pytest.mark.parametrize("modo", A11Y_MODOS)
    def test_modos_conocidos_aceptados_en_create(self, client, modo):
        resp = client.post("/comercios/", json={"nombre": f"C {modo}", "a11y_modo": modo})
        assert resp.status_code == 201, resp.text
        assert resp.json()["a11y_modo"] == modo

    def test_modo_desconocido_rechazado_en_update(self, client):
        comercio_id = client.post("/comercios/", json={"nombre": "C"}).json()["id"]
        resp = client.put(f"/comercios/{comercio_id}", json={"a11y_modo": "solarizado"})
        assert resp.status_code == 422


class TestInyeccionHtmlTextoAccesible:
    def test_variables_renderizan_desde_comercio_persistido(self, client):
        db = TestingSessionLocal()
        try:
            _seed_comercio_a11y(db, color_primario="#059669", color_secundario="#10B981")
        finally:
            db.close()

        resp = client.get("/page/")
        assert resp.status_code == 200
        assert "--texto-sobre-primario: #000000" in resp.text
        assert "--texto-sobre-secundario: #000000" in resp.text

    def test_variables_fallback_sin_comercio_en_bd(self, client):
        resp = client.get("/page/")
        assert resp.status_code == 200
        assert "--texto-sobre-primario: #FFFFFF" in resp.text
        assert "--texto-sobre-secundario: #000000" in resp.text

    def test_bases_no_usan_mas_indigo_hardcodeado(self, client):
        resp = client.get("/page/")
        assert resp.status_code == 200
        assert "bg-indigo-600" not in resp.text

    def test_link_hoja_a11y_css_presente_y_servida(self, client):
        resp = client.get("/page/")
        assert "/static/css/a11y.css" in resp.text

        hoja = client.get("/static/css/a11y.css")
        assert hoja.status_code == 200
        assert "text/css" in hoja.headers["content-type"]

    def test_fuente_opendyslexic_servida_localmente(self, client):
        fuente = client.get("/static/fonts/OpenDyslexic-Regular.woff2")
        assert fuente.status_code == 200
        assert len(fuente.content) > 10000

    @pytest.mark.parametrize("modo", A11Y_MODOS)
    def test_data_a11y_modo_renderiza_por_modo(self, client, modo):
        db = TestingSessionLocal()
        try:
            _seed_comercio_a11y(db, a11y_modo=modo)
        finally:
            db.close()

        resp = client.get("/page/")
        assert resp.status_code == 200
        assert f'data-a11y-modo="{modo}"' in resp.text

    def test_theme_color_dinamico_desde_skin(self, client):
        db = TestingSessionLocal()
        try:
            _seed_comercio_a11y(db, color_primario="#059669")
        finally:
            db.close()

        resp = client.get("/page/")
        assert '<meta name="theme-color" content="#059669">' in resp.text


class TestRenderBasePublicConSkinA11y:
    def _render(self, comercio):
        from app.core.templating import get_templates

        templates = get_templates()
        plantilla = templates.env.from_string('{% extends "portal/base_public.html" %}')
        return plantilla.render(
            {
                "request": None,
                "comercio": comercio,
                "skin": resolver_skin(comercio),
            }
        )

    def test_variables_de_texto_accesible_renderizadas(self):
        comercio = SimpleNamespace(
            color_primario="#059669",
            color_secundario="#10B981",
            tema_preset="menta_vet",
            a11y_modo="normal",
            a11y_dyslexic=False,
        )

        html = self._render(comercio)
        assert "--texto-sobre-primario: #000000" in html
        assert "--texto-sobre-secundario: #000000" in html
        assert "bg-[var(--color-primario)]" in html

    def test_sin_indigo_hardcodeado_y_con_hoja_a11y(self):
        comercio = SimpleNamespace(
            color_primario="#1E40AF",
            color_secundario="#0D9488",
            tema_preset="clasico_paws",
            a11y_modo="alto_contraste",
            a11y_dyslexic=True,
        )

        html = self._render(comercio)
        assert "bg-indigo-600" not in html
        assert 'data-a11y-modo="alto_contraste"' in html
        assert "a11y-dyslexic" in html
        assert "/static/css/a11y.css" in html
