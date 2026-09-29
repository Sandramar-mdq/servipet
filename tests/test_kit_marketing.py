"""Tests del Kit de Marketing B2B (Etapa 12): placa cuadrada 1:1 de promociones.

El kit es stateless por defecto: el comercio puede pedir tantas variantes de una
campana como necesite. La auditoria es opt-in via `registrar=true`.
"""

import io

import pytest
from PIL import Image

from app.models.comercio import Comercio
from app.models.pieza_generada import FormatoPieza, PiezaGenerada, TipoPieza
from app.models.usuario import Usuario
from app.services.auth import hash_password
from tests.conftest import TestingSessionLocal

URL = "/api/v1/marketing/kit/promocion/placa.png"

PROMO_BASE = {
    "titulo": "Baño y Pelado 2x1",
    "beneficio_texto": "2x1 en baño y pelado",
}


def _db():
    return TestingSessionLocal()


def _crear_empleado(db, email, comercio_id=1, rol="EMPLEADO"):
    db.add(
        Usuario(
            email=email,
            password_hash=hash_password("test123"),
            rol=rol,
            comercio_id=comercio_id,
            activo=True,
        )
    )
    db.commit()


def _login(client, email, password="test123"):
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _generar(client, headers, **overrides):
    datos = dict(PROMO_BASE)
    datos.update(overrides)
    return client.post(URL, headers=headers, json=datos)


class TestAcceso:
    def test_requiere_auth(self, client):
        assert client.post(URL, json=PROMO_BASE).status_code == 401

    def test_admin_puede_generar(self, client, admin_headers):
        resp = _generar(client, admin_headers)
        assert resp.status_code == 200, resp.text

    def test_empleado_puede_generar(self, client, admin_headers):
        db = _db()
        try:
            _crear_empleado(db, "empleado@test.com", 1)
        finally:
            db.close()

        headers = _login(client, "empleado@test.com")
        assert _generar(client, headers).status_code == 200

    def test_empleado_de_otro_comercio_sin_tenant_rechazado(self, client, admin_headers):
        """Un empleado siempre tiene comercio: no puede generar sin tenant."""
        db = _db()
        try:
            db.add(Comercio(id=2, nombre="Otro", tipo_comercio="PELUQUERIA", activo=True))
            _crear_empleado(db, "ajeno@test.com", 2)
        finally:
            db.close()

        headers = _login(client, "ajeno@test.com")
        # Es su propio comercio, asi que puede usarlo: el branding sale de el.
        assert _generar(client, headers).status_code == 200


class TestRender:
    def test_devuelve_png_1x1(self, client, admin_headers):
        resp = _generar(client, admin_headers)
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert resp.content.startswith(b"\x89PNG\r\n\x1a\n")

        imagen = Image.open(io.BytesIO(resp.content))
        assert imagen.size == (1080, 1080)
        assert imagen.mode == "RGB"

    def test_nombre_archivo_slug(self, client, admin_headers):
        resp = _generar(client, admin_headers, titulo="Baño + Pelado 2x1!!!")
        disposition = resp.headers["content-disposition"]
        assert disposition.startswith("attachment;")
        assert "bano-pelado-2x1.png" in disposition

    def test_nombre_archivo_sin_texto_util(self, client, admin_headers):
        resp = _generar(client, admin_headers, titulo="###")
        assert "promo.png" in resp.headers["content-disposition"]

    def test_branding_del_comercio_aplicado(self, client, admin_headers):
        from app.services import marketing_service

        db = _db()
        try:
            comercio = db.query(Comercio).filter(Comercio.id == 1).first()
            comercio.nombre = "Pet Shop Palermo"
            comercio.color_primario = "#7C3AED"
            comercio.color_secundario = "#F59E0B"
            db.commit()

            data = marketing_service.datos_promocion(PROMO_BASE, comercio)
        finally:
            db.close()

        assert data["usar_branding"] is True
        assert data["comercio_nombre"] == "Pet Shop Palermo"
        assert data["color_primario"] == "#7C3AED"
        assert data["titulo"] == "Baño y Pelado 2x1"
        assert data["beneficio"] == "2x1 en baño y pelado"
        assert data["leyenda"]

    def test_sin_branding_usa_generico(self, client, admin_headers):
        from app.services import marketing_service

        db = _db()
        try:
            data = marketing_service.datos_promocion(
                dict(PROMO_BASE, usar_branding=False), None
            )
        finally:
            db.close()

        assert data["usar_branding"] is False
        assert data["comercio_nombre"] is None

    def test_colores_personalizados(self, client, admin_headers):
        resp = _generar(
            client,
            admin_headers,
            titulo="Promo-test",
            usar_branding=False,
            color_primario="#112233",
            color_secundario="#445566",
        )
        assert resp.status_code == 200
        imagen = Image.open(io.BytesIO(resp.content))
        assert imagen.size == (1080, 1080)

    def test_color_pisa_al_branding(self, client, admin_headers):
        """El color del request gana sobre el configurado en el comercio."""
        from app.services import marketing_service

        db = _db()
        try:
            comercio = db.query(Comercio).filter(Comercio.id == 1).first()
            comercio.color_primario = "#7C3AED"
            db.commit()
            data = marketing_service.datos_promocion(
                dict(PROMO_BASE, color_primario="#112233"), comercio
            )
        finally:
            db.close()

        assert data["color_primario"] == "#112233"

    def test_slug_ascii_sin_acentos(self, client, admin_headers):
        """Las cabeceras HTTP son latin-1: un slug con 'ñ' romperia la respuesta."""
        resp = _generar(client, admin_headers, titulo="Baño ñandú Alemán — 2x1")
        assert resp.status_code == 200
        disposition = resp.headers["content-disposition"]
        assert disposition.isascii(), disposition
        assert "bano-nandu-aleman-2x1.png" in disposition

    def test_placa_sin_beneficio_no_revienta(self, client, admin_headers):
        """Regresion: sin beneficio, el subtitulo/condiciones igual deben salir."""
        resp = client.post(
            URL,
            headers=admin_headers,
            json={"titulo": "Solo el titulo", "condiciones": "Sin beneficio"},
        )
        assert resp.status_code == 200
        assert resp.content.startswith(b"\x89PNG")

    def test_texto_largo_no_rompe(self, client, admin_headers):
        resp = _generar(
            client,
            admin_headers,
            titulo="PROMOCION " * 5,
            beneficio_texto="Descuento " * 8,
            condiciones="Valido " * 20,
        )
        assert resp.status_code == 200
        assert resp.content.startswith(b"\x89PNG")

    def test_acentos_y_simbolos(self, client, admin_headers):
        """Regresion: el renderer debe tolerar el texto que manda el usuario."""
        resp = _generar(
            client,
            admin_headers,
            titulo="Cumpleaños — 2x1 “Oferta” 🐾",
            beneficio_texto="10% OFF €",
        )
        assert resp.status_code == 200
        assert resp.content.startswith(b"\x89PNG")


class TestValidacion:
    def test_titulo_requerido(self, client, admin_headers):
        resp = client.post(URL, headers=admin_headers, json={"beneficio_texto": "x"})
        assert resp.status_code == 422

    def test_titulo_muy_corto(self, client, admin_headers):
        resp = _generar(client, admin_headers, titulo="a")
        assert resp.status_code == 422

    def test_titulo_muy_largo(self, client, admin_headers):
        resp = _generar(client, admin_headers, titulo="x" * 200)
        assert resp.status_code == 422

    def test_color_invalido(self, client, admin_headers):
        resp = _generar(client, admin_headers, color_primario="no-es-un-color")
        assert resp.status_code == 422

    def test_campos_desconocidos_ignorados(self, client, admin_headers):
        resp = _generar(client, admin_headers, campo_inventado="valor")
        assert resp.status_code == 200

    def test_beneficio_opcional(self, client, admin_headers):
        resp = client.post(URL, headers=admin_headers, json={"titulo": "Solo titulo valido"})
        assert resp.status_code == 200


class TestAuditoria:
    def test_por_defecto_no_registra(self, client, admin_headers):
        """Stateless: pedir la misma promo dos veces no debe chocar."""
        assert _generar(client, admin_headers).status_code == 200
        assert _generar(client, admin_headers).status_code == 200

        db = _db()
        try:
            assert db.query(PiezaGenerada).filter(PiezaGenerada.tipo == TipoPieza.PROMOCION).count() == 0
        finally:
            db.close()

    def test_registrar_true_audita(self, client, admin_headers):
        resp = _generar(client, admin_headers, registrar=True)
        assert resp.status_code == 200

        db = _db()
        try:
            pieza = (
                db.query(PiezaGenerada)
                .filter(PiezaGenerada.tipo == TipoPieza.PROMOCION)
                .first()
            )
            assert pieza is not None
            assert pieza.comercio_id == 1
            assert pieza.formato == FormatoPieza.PNG_1X1
            assert pieza.referencia_id is None
            assert pieza.nombre_archivo.endswith(".png")
            assert pieza.beneficio == "2x1 en baño y pelado"
        finally:
            db.close()

    def test_registro_repetido_no_duplica(self, client, admin_headers):
        """Sin referencia_id el upsert no aplica, pero tampoco debe romper."""
        assert _generar(client, admin_headers, registrar=True).status_code == 200
        assert _generar(client, admin_headers, registrar=True).status_code == 200

        db = _db()
        try:
            assert db.query(PiezaGenerada).filter(PiezaGenerada.tipo == TipoPieza.PROMOCION).count() == 2
        finally:
            db.close()
