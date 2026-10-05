"""Tests del Modulo Solidario (Etapa 12): cartel PDF A4 y placa digital 9:16.

Cubre RBAC (ADMIN / EMPLEADO), aislamiento multi-tenant, opt-in del comercio,
validacion de la descarga binaria y la auditoria anti-duplicado.
"""

import io

import pytest
from PIL import Image

from app.models.aviso_comunitario import AvisoComunitario, TipoAviso
from app.models.cliente import Cliente
from app.models.comercio import Comercio
from app.models.mascota import Mascota
from app.models.pieza_generada import FormatoPieza, PiezaGenerada, TipoPieza
from app.models.usuario import Usuario
from app.services.auth import hash_password
from tests.conftest import TestingSessionLocal

BASE = "/api/v1/marketing/solidaridad/avisos"

CARTEL = f"{BASE}/1/cartel.pdf"
PLACA = f"{BASE}/1/placa-vertical.png"


def _db():
    return TestingSessionLocal()


def _activar_optin(db, comercio_id=1, solidario=True):
    comercio = db.query(Comercio).filter(Comercio.id == comercio_id).first()
    assert comercio is not None, f"el comercio {comercio_id} debe existir antes del opt-in"
    comercio.habilitar_modulo_solidario = solidario
    db.commit()
    return comercio


def _crear_comercio(db, comercio_id, nombre="Otro Comercio", tipo="PELUQUERIA"):
    comercio = Comercio(
        id=comercio_id, nombre=nombre, tipo_comercio=tipo, activo=True
    )
    db.add(comercio)
    db.commit()
    return comercio


def _crear_aviso(db, comercio_id=1, cliente_id=1, tipo=TipoAviso.PERDIDA, con_mascota=True):
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if cliente is None:
        cliente = Cliente(id=cliente_id, comercio_id=comercio_id, nombre="Ana", activo=True)
        db.add(cliente)
    if con_mascota and not db.query(Mascota).filter(Mascota.cliente_id == cliente_id).first():
        db.add(
            Mascota(
                cliente_id=cliente_id,
                nombre="Luna",
                especie="Canino",
                raza="Mixed",
                color="Canela",
                activo=True,
                fallecida=False,
            )
        )
    aviso = AvisoComunitario(
        comercio_id=comercio_id,
        cliente_id=cliente_id,
        tipo=tipo,
        titulo="Se perdio en Palermo",
        descripcion="Responde a su nombre, tiene collar azul",
        telefono_contacto="11-1234-5678",
    )
    db.add(aviso)
    db.commit()
    return aviso


def _crear_empleado(db, email, comercio_id, rol="EMPLEADO"):
    usuario = Usuario(
        email=email,
        password_hash=hash_password("test123"),
        rol=rol,
        comercio_id=comercio_id,
        activo=True,
    )
    db.add(usuario)
    db.commit()
    return usuario


def _login(client, email, password="test123"):
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
def entorno_solidario(admin_headers):
    """Comercio 1 con opt-in activo, cliente con mascota y un aviso perdido."""
    db = _db()
    try:
        _activar_optin(db, 1, True)
        _crear_aviso(db, 1, 1)
    finally:
        db.close()
    return admin_headers


class TestAccesoYReglas:
    def test_cartel_requiere_auth(self, client):
        assert client.get(CARTEL).status_code == 401

    def test_placa_requiere_auth(self, client):
        assert client.get(PLACA).status_code == 401

    def test_requiere_optin_del_comercio(self, client, admin_headers):
        db = _db()
        try:
            _crear_aviso(db, 1, 1)
            _activar_optin(db, 1, False)
        finally:
            db.close()

        resp = client.get(CARTEL, headers=admin_headers)
        assert resp.status_code == 403
        assert "solidario" in resp.json()["detail"].lower()

    def test_empleado_puede_generar(self, client, admin_headers):
        db = _db()
        try:
            _activar_optin(db, 1, True)
            _crear_aviso(db, 1, 1)
            _crear_empleado(db, "empleado@test.com", 1)
        finally:
            db.close()

        headers = _login(client, "empleado@test.com")
        assert client.get(CARTEL, headers=headers).status_code == 200
        assert client.get(PLACA, headers=headers).status_code == 200

    def test_empleado_de_otro_comercio_rechazado(self, client, admin_headers):
        db = _db()
        try:
            _activar_optin(db, 1, True)
            _crear_aviso(db, 1, 1)
            _crear_comercio(db, 2)
            _activar_optin(db, 2, True)
            _crear_empleado(db, "ajeno@test.com", 2)
        finally:
            db.close()

        headers = _login(client, "ajeno@test.com")
        resp = client.get(CARTEL, headers=headers)
        assert resp.status_code == 403
        assert "Permisos insuficientes" in resp.json()["detail"]

    def test_aviso_inexistente(self, client, admin_headers):
        resp = client.get(f"{BASE}/9999/cartel.pdf", headers=admin_headers)
        assert resp.status_code == 404

    def test_cliente_sin_mascota_usa_placeholders(self, client, admin_headers):
        """Un aviso sin mascota no debe romper: cae al lugar del comercio."""
        db = _db()
        try:
            _activar_optin(db, 1, True)
            _crear_aviso(db, 1, 1, con_mascota=False)
        finally:
            db.close()

        resp = client.get(CARTEL, headers=admin_headers)
        assert resp.status_code == 200
        assert resp.content.startswith(b"%PDF")

    @pytest.mark.parametrize("tipo", [TipoAviso.PERDIDA, TipoAviso.ADOPCION, TipoAviso.ENCONTRADA])
    def test_todos_los_tipos_solidarios(self, client, admin_headers, tipo):
        db = _db()
        try:
            _activar_optin(db, 1, True)
            _crear_aviso(db, 1, 1, tipo=tipo)
        finally:
            db.close()

        assert client.get(CARTEL, headers=admin_headers).status_code == 200


class TestCartelPdf:
    def test_descarga_pdf_valido(self, client, entorno_solidario):
        resp = client.get(CARTEL, headers=entorno_solidario)
        assert resp.status_code == 200, resp.text
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content.startswith(b"%PDF-")
        assert resp.content.rstrip().endswith(b"%%EOF")

    def test_content_disposition_attachment(self, client, entorno_solidario):
        resp = client.get(CARTEL, headers=entorno_solidario)
        disposition = resp.headers["content-disposition"]
        assert disposition.startswith("attachment;")
        assert "cartel_1.pdf" in disposition

    def test_pdf_tiene_una_sola_pagina(self, client, entorno_solidario):
        """A4 vertical: una unica pagina, sin desborde a una segunda."""
        contenido = client.get(CARTEL, headers=entorno_solidario).content
        assert contenido.count(b"/Type /Page\n") + contenido.count(b"/Type /Page ") >= 1
        assert b"/Count 1" in contenido

    def test_acentos_no_rompen_el_pdf(self, client, entorno_solidario):
        """Regresion: fpdf2 usa latin-1, no cp1252, con las fuentes core.

        El texto del PDF va comprimido con Flate, asi que no se puede buscar la
        palabra en los bytes crudos. Lo que se verifica es que la generacion
        no aborta y que el sanitizado deja todo el texto dentro de latin-1.
        """
        resp = client.get(CARTEL, headers=entorno_solidario)
        assert resp.status_code == 200
        assert resp.content.startswith(b"%PDF-")

        from app.services.pieza_service import _pdf_seguro

        muestra = "FELIZ CUMPLEAÑOS, Luna — ¡10% OFF! “Oferta” 🐾 ü €"
        limpio = _pdf_seguro(muestra)
        limpio.encode("latin-1")  # no debe lanzar
        assert "Ñ" in limpio, "los acentos del castellano se conservan"
        assert "-" in limpio and '"' in limpio, "la tipografia se traduce a ASCII"
        assert "🐾" not in limpio
        assert "EUR" in limpio

    @pytest.mark.parametrize(
        "texto",
        ["Cumpleaños", "Ñandú", "a—b", "€10", "🐾", "", None, "texto normal"],
    )
    def test_pdf_seguro_siempre_codificable(self, texto):
        from app.services.pieza_service import _pdf_seguro

        salida = _pdf_seguro(texto)
        assert isinstance(salida, str)
        salida.encode("latin-1")


class TestPlacaVertical:
    def test_descarga_png_9x16(self, client, entorno_solidario):
        resp = client.get(PLACA, headers=entorno_solidario)
        assert resp.status_code == 200, resp.text
        assert resp.headers["content-type"] == "image/png"
        assert resp.content.startswith(b"\x89PNG\r\n\x1a\n")

        imagen = Image.open(io.BytesIO(resp.content))
        assert imagen.size == (1080, 1920)
        assert imagen.mode == "RGB"

    def test_nombre_archivo_placa(self, client, entorno_solidario):
        resp = client.get(PLACA, headers=entorno_solidario)
        assert "placa_9x16_1.png" in resp.headers["content-disposition"]


class TestAuditoria:
    def test_registra_la_pieza_generada(self, client, entorno_solidario):
        assert client.get(CARTEL, headers=entorno_solidario).status_code == 200

        db = _db()
        try:
            pieza = (
                db.query(PiezaGenerada)
                .filter(
                    PiezaGenerada.tipo == TipoPieza.CARTEL_SOLIDARIO,
                    PiezaGenerada.formato == FormatoPieza.PDF_A4,
                )
                .first()
            )
            assert pieza is not None
            assert pieza.comercio_id == 1
            assert pieza.referencia_tipo == "AVISO"
            assert pieza.referencia_id == 1
            assert pieza.nombre_archivo == "cartel_1.pdf"
        finally:
            db.close()

    def test_segunda_generacion_da_409(self, client, entorno_solidario):
        assert client.get(CARTEL, headers=entorno_solidario).status_code == 200
        resp = client.get(CARTEL, headers=entorno_solidario)
        assert resp.status_code == 409
        assert "ya fue generado" in resp.json()["detail"]

    def test_forzar_permite_regenerar(self, client, entorno_solidario):
        assert client.get(CARTEL, headers=entorno_solidario).status_code == 200
        resp = client.get(f"{CARTEL}?forzar=1", headers=entorno_solidario)
        assert resp.status_code == 200
        assert resp.content.startswith(b"%PDF-")

        db = _db()
        try:
            total = (
                db.query(PiezaGenerada)
                .filter(PiezaGenerada.tipo == TipoPieza.CARTEL_SOLIDARIO)
                .count()
            )
            assert total == 1, "forzar debe actualizar, no duplicar (upsert)"
        finally:
            db.close()

    def test_formatos_distintos_no_se_bloquean(self, client, entorno_solidario):
        """El PDF y el PNG 9:16 son piezas distintas: no se estorban entre si."""
        assert client.get(CARTEL, headers=entorno_solidario).status_code == 200
        assert client.get(PLACA, headers=entorno_solidario).status_code == 200
        assert client.get(CARTEL, headers=entorno_solidario).status_code == 409

    def test_pieza_de_otro_comercio_no_choca(self, client, admin_headers):
        """La unicidad incluye comercio_id: dos comercios pueden generar la misma."""
        db = _db()
        try:
            _activar_optin(db, 1, True)
            _crear_aviso(db, 1, 1)
            _crear_comercio(db, 2, nombre="Otro")
            _activar_optin(db, 2, True)
            _crear_aviso(db, 2, 2)
            _crear_empleado(db, "otro2@test.com", 2)
        finally:
            db.close()

        headers_admin = _login(client, "admin@test.com", "admin123")
        headers_otro = _login(client, "otro2@test.com")

        assert client.get(CARTEL, headers=headers_admin).status_code == 200
        assert client.get(f"{BASE}/2/cartel.pdf", headers=headers_otro).status_code == 200
