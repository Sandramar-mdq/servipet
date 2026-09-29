"""Tests del Modulo de Cumpleanos / Fidelizacion (Etapa 12).

El foco es el filtro estricto: solo entran mascotas activas y vivas, de clientes
activos que dieron consentimiento, dentro de una ventana inclusiva. Ademas cubre
el opt-in del comercio, el beneficio configurable, la placa 1:1 y el control
anti-duplicado por anio.
"""

import io
from datetime import date, timedelta

import pytest
from PIL import Image

from app.models.cliente import Cliente
from app.models.comercio import Comercio
from app.models.mascota import Mascota
from app.models.pieza_generada import FormatoPieza, PiezaGenerada, TipoPieza
from app.models.usuario import Usuario
from app.services import marketing_service
from app.services.auth import hash_password
from tests.conftest import TestingSessionLocal

BASE = "/api/v1/marketing/cumpleanos"
HOY = date.today()


def _db():
    return TestingSessionLocal()


def _activar_optin(db, beneficio="10% OFF"):
    comercio = db.query(Comercio).filter(Comercio.id == 1).first()
    comercio.habilitar_cumpleanos = True
    comercio.beneficio_cumpleanos = beneficio
    db.commit()
    return comercio


def _crear_cliente(db, nombre, acepta=True, activo=True, cliente_id=None):
    cliente = Cliente(
        nombre=nombre,
        comercio_id=1,
        activo=activo,
        acepta_cumpleanos=acepta,
        zona_barrio="Palermo",
    )
    if cliente_id is not None:
        cliente.id = cliente_id
    db.add(cliente)
    db.commit()
    return cliente


def _crear_mascota(db, cliente_id, nombre, dias=3, activa=True, fallecida=False, con_fecha=True):
    mascota = Mascota(
        cliente_id=cliente_id,
        nombre=nombre,
        especie="Canino",
        raza="Mixed",
        color="Canela",
        activo=activa,
        fallecida=fallecida,
        fecha_nacimiento=(HOY - timedelta(days=365 * 4)).replace(
            month=((HOY + timedelta(days=dias)).month),
            day=((HOY + timedelta(days=dias)).day),
        ) if con_fecha else None,
    )
    db.add(mascota)
    db.commit()
    return mascota


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


@pytest.fixture
def optin(admin_headers):
    db = _db()
    try:
        _activar_optin(db)
    finally:
        db.close()
    return admin_headers


# --------------------------------------------------------------------------
# Aritmetica de aniversarios (sin BD)
# --------------------------------------------------------------------------

class TestAritmeticaAniversarios:
    @pytest.mark.parametrize(
        "nacimiento,hoy,esperado_prox,esperados_anios",
        [
            # (fecha_nacimiento, hoy, proximo_aniversario, anios_cumplidos)
            (date(2020, 3, 10), date(2026, 3, 10), date(2026, 3, 10), 6),  # hoy es el cumple
            (date(2020, 6, 1), date(2026, 3, 28), date(2026, 6, 1), 6),  # falta
            (date(2019, 1, 15), date(2026, 3, 28), date(2027, 1, 15), 8),  # ya paso
            (date(2019, 1, 5), date(2026, 12, 28), date(2027, 1, 5), 8),  # cruce de anio
            (date(2020, 2, 29), date(2026, 2, 28), date(2026, 2, 28), 6),  # bisiesto -> 28/02
            (date(2020, 2, 29), date(2028, 2, 28), date(2028, 2, 29), 8),  # anio bisiesto
        ],
    )
    def test_proximo_y_anios(self, nacimiento, hoy, esperado_prox, esperados_anios):
        prox = marketing_service.proximo_aniversario(nacimiento, hoy)
        assert prox == esperado_prox
        assert marketing_service.anios_cumplidos(nacimiento, prox) == esperados_anios

    def test_dias_para_cumple_es_exacto(self):
        """El contador de dias del listado coincide con la fecha calculada."""
        hoy = date(2026, 12, 28)
        prox = marketing_service.proximo_aniversario(date(2019, 1, 4), hoy)
        assert prox == date(2027, 1, 4)
        assert (prox - hoy).days == 7

    def test_bisiesto_nacido_el_29_convierte_en_28(self):
        hoy = date(2026, 3, 1)
        prox = marketing_service.proximo_aniversario(date(2020, 2, 29), hoy)
        assert prox == date(2027, 2, 28)
        assert marketing_service.anios_cumplidos(date(2020, 2, 29), prox) == 7


# --------------------------------------------------------------------------
# Filtro estricto del listado
# --------------------------------------------------------------------------

class TestListadoProximos:
    def test_requiere_auth(self, client):
        assert client.get(f"{BASE}/proximos").status_code == 401

    def test_requiere_optin(self, client, admin_headers):
        db = _db()
        try:
            _crear_cliente(db, "Ana")
            _crear_mascota(db, 1, "Luna")
        finally:
            db.close()

        resp = client.get(f"{BASE}/proximos", headers=admin_headers)
        assert resp.status_code == 403
        assert "cumplea" in resp.json()["detail"].lower()

    def test_lista_solo_lo_permitido(self, client, optin):
        """Un unico caso valido entre seis candidatos descartados."""
        db = _db()
        try:
            ok = _crear_cliente(db, "Ana", acepta=True)
            _crear_mascota(db, ok.id, "Luna", dias=3)

            _crear_mascota(db, ok.id, "MuyLejos", dias=30)  # fuera de ventana
            _crear_mascota(db, ok.id, "SinFecha", con_fecha=False)  # sin fecha
            _crear_mascota(db, ok.id, "Inactiva", dias=2, activa=False)  # mascota inactiva
            _crear_mascota(db, ok.id, "Fallecida", dias=2, fallecida=True)  # fallecida

            sin_consent = _crear_cliente(db, "Beto", acepta=False)
            _crear_mascota(db, sin_consent.id, "Roco", dias=1)

            cliente_inactivo = _crear_cliente(db, "Caro", acepta=True, activo=False)
            _crear_mascota(db, cliente_inactivo.id, "Toby", dias=1)
        finally:
            db.close()

        resp = client.get(f"{BASE}/proximos?dias=7", headers=optin)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        nombres = [i["nombre"] for i in body["items"]]
        assert nombres == ["Luna"]
        assert body["total"] == 1

    def test_ventana_inclusiva_ambos_extremos(self, client, optin):
        """Con dias=1 entran el cumple de hoy y el de manana, no el de pasado."""
        db = _db()
        try:
            cliente = _crear_cliente(db, "Ana")
            _crear_mascota(db, cliente.id, "Hoy", dias=0)
            _crear_mascota(db, cliente.id, "Manana", dias=1)
            _crear_mascota(db, cliente.id, "Pasado", dias=-1)
        finally:
            db.close()

        resp = client.get(f"{BASE}/proximos?dias=1", headers=optin)
        nombres = sorted(i["nombre"] for i in resp.json()["items"])
        assert nombres == ["Hoy", "Manana"]

    def test_ordenado_por_proximidad(self, client, optin):
        db = _db()
        try:
            cliente = _crear_cliente(db, "Ana")
            _crear_mascota(db, cliente.id, "Lejos", dias=5)
            _crear_mascota(db, cliente.id, "Cerca", dias=1)
            _crear_mascota(db, cliente.id, "Medio", dias=3)
        finally:
            db.close()

        resp = client.get(f"{BASE}/proximos?dias=7", headers=optin)
        assert [i["nombre"] for i in resp.json()["items"]] == ["Cerca", "Medio", "Lejos"]

    def test_otro_comercio_no_aparece(self, client, optin):
        """Aislamiento multi-tenant del listado."""
        db = _db()
        try:
            cliente = _crear_cliente(db, "Ana")
            _crear_mascota(db, cliente.id, "Luna", dias=1)

            db.add(Comercio(id=2, nombre="Otro", tipo_comercio="PELUQUERIA", activo=True))
            ajena = Cliente(
                nombre="Ajena", comercio_id=2, activo=True, acepta_cumpleanos=True
            )
            db.add(ajena)
            db.commit()
            _crear_mascota(db, ajena.id, "Intrusa", dias=1)
        finally:
            db.close()

        resp = client.get(f"{BASE}/proximos", headers=optin)
        nombres = [i["nombre"] for i in resp.json()["items"]]
        assert nombres == ["Luna"]

    def test_devuelve_beneficio_del_comercio(self, client, admin_headers):
        db = _db()
        try:
            _activar_optin(db, beneficio="15% en la segunda visita")
        finally:
            db.close()

        resp = client.get(f"{BASE}/proximos", headers=admin_headers)
        assert resp.json()["beneficio_default"] == "15% en la segunda visita"

    def test_beneficio_por_defecto_si_no_configurado(self, client, optin):
        db = _db()
        try:
            comercio = db.query(Comercio).filter(Comercio.id == 1).first()
            comercio.beneficio_cumpleanos = None
            db.commit()
        finally:
            db.close()

        resp = client.get(f"{BASE}/proximos", headers=optin)
        assert resp.json()["beneficio_default"]

    @pytest.mark.parametrize("dias", [0, 32, -1])
    def test_ventana_invalida(self, client, optin, dias):
        assert client.get(f"{BASE}/proximos?dias={dias}", headers=optin).status_code == 422

    def test_ya_enviado_tras_generar_placa(self, client, optin):
        db = _db()
        try:
            cliente = _crear_cliente(db, "Ana")
            mascota = _crear_mascota(db, cliente.id, "Luna", dias=2)
            mascota_id = mascota.id
        finally:
            db.close()

        assert client.get(f"{BASE}/proximos", headers=optin).json()["items"][0]["ya_enviado"] is False

        resp = client.get(f"{BASE}/mascotas/{mascota_id}/placa.png", headers=optin)
        assert resp.status_code == 200

        despues = client.get(f"{BASE}/proximos", headers=optin).json()["items"][0]
        assert despues["ya_enviado"] is True


# --------------------------------------------------------------------------
# Placa cuadrada 1:1
# --------------------------------------------------------------------------

class TestPlacaCumpleanos:
    def test_requiere_auth(self, client):
        assert client.get(f"{BASE}/mascotas/1/placa.png").status_code == 401

    def test_requiere_optin(self, client, admin_headers):
        db = _db()
        try:
            cliente = _crear_cliente(db, "Ana")
            _crear_mascota(db, cliente.id, "Luna", dias=1)
        finally:
            db.close()

        resp = client.get(f"{BASE}/mascotas/1/placa.png", headers=admin_headers)
        assert resp.status_code == 403

    def test_mascota_inexistente(self, client, optin):
        assert client.get(f"{BASE}/mascotas/9999/placa.png", headers=optin).status_code == 404

    def test_mascota_fallecida_no_tiene_placa(self, client, optin):
        """Se respeta el mismo filtro estricto que en el listado."""
        db = _db()
        try:
            cliente = _crear_cliente(db, "Ana")
            mascota = _crear_mascota(db, cliente.id, "Luna", dias=1, fallecida=True)
            mascota_id = mascota.id
        finally:
            db.close()

        resp = client.get(f"{BASE}/mascotas/{mascota_id}/placa.png", headers=optin)
        assert resp.status_code == 404

    def test_cliente_sin_consentimiento_no_tiene_placa(self, client, optin):
        db = _db()
        try:
            cliente = _crear_cliente(db, "Beto", acepta=False)
            mascota = _crear_mascota(db, cliente.id, "Roco", dias=1)
            mascota_id = mascota.id
        finally:
            db.close()

        assert client.get(f"{BASE}/mascotas/{mascota_id}/placa.png", headers=optin).status_code == 404

    def test_descarga_png_1x1(self, client, optin):
        db = _db()
        try:
            cliente = _crear_cliente(db, "Ana")
            mascota = _crear_mascota(db, cliente.id, "Luna", dias=0)
            mascota_id = mascota.id
        finally:
            db.close()

        resp = client.get(f"{BASE}/mascotas/{mascota_id}/placa.png", headers=optin)
        assert resp.status_code == 200, resp.text
        assert resp.headers["content-type"] == "image/png"
        assert resp.content.startswith(b"\x89PNG\r\n\x1a\n")

        imagen = Image.open(io.BytesIO(resp.content))
        assert imagen.size == (1080, 1080)
        assert imagen.mode == "RGB"

    def test_nombre_archivo_incluye_anio(self, client, optin):
        db = _db()
        try:
            cliente = _crear_cliente(db, "Ana")
            mascota = _crear_mascota(db, cliente.id, "Luna", dias=0)
            mascota_id = mascota.id
        finally:
            db.close()

        resp = client.get(f"{BASE}/mascotas/{mascota_id}/placa.png", headers=optin)
        assert f"cumpleanos_{mascota_id}_{HOY.year}.png" in resp.headers["content-disposition"]

    def test_beneficio_override(self, client, optin):
        """El beneficio por query prima sobre el configurado en el comercio."""
        db = _db()
        try:
            cliente = _crear_cliente(db, "Ana")
            _crear_mascota(db, cliente.id, "Luna", dias=0)
        finally:
            db.close()

        db = _db()
        try:
            data = marketing_service.datos_placa_cumpleanos(
                db, 1, beneficio_override="Baño gratis"
            )
        finally:
            db.close()
        assert data["beneficio"] == "Baño gratis"

    def test_beneficio_por_defecto_del_comercio(self, client, optin):
        db = _db()
        try:
            cliente = _crear_cliente(db, "Ana")
            mascota = _crear_mascota(db, cliente.id, "Luna", dias=0)
            data = marketing_service.datos_placa_cumpleanos(db, mascota.id)
        finally:
            db.close()
        assert data["beneficio"] == "10% OFF"

    def test_titulo_con_nombre_de_mascota(self, client, optin):
        db = _db()
        try:
            cliente = _crear_cliente(db, "Ana")
            mascota = _crear_mascota(db, cliente.id, "Luna", dias=0)
            data = marketing_service.datos_placa_cumpleanos(db, mascota.id)
        finally:
            db.close()

        assert "Luna" in data["titulo"]
        assert "CUMPLEAÑOS" in data["titulo"].upper()

    def test_empleado_puede_generar(self, client, optin):
        db = _db()
        try:
            _crear_cliente(db, "Ana")
            _crear_mascota(db, 1, "Luna", dias=1)
            _crear_empleado(db, "empleado@test.com", 1)
        finally:
            db.close()

        headers = _login(client, "empleado@test.com")
        assert client.get(f"{BASE}/mascotas/1/placa.png", headers=headers).status_code == 200

    def test_empleado_de_otro_comercio_rechazado(self, client, optin):
        """El aislamiento se comprueba sobre una mascota que si existe."""
        db = _db()
        try:
            cliente = _crear_cliente(db, "Ana")
            _crear_mascota(db, cliente.id, "Luna", dias=1)
            db.add(Comercio(id=2, nombre="Otro", tipo_comercio="PELUQUERIA", activo=True))
            _crear_empleado(db, "ajeno@test.com", 2)
        finally:
            db.close()

        headers = _login(client, "ajeno@test.com")
        resp = client.get(f"{BASE}/mascotas/1/placa.png", headers=headers)
        assert resp.status_code == 403
        assert "Permisos insuficientes" in resp.json()["detail"]


# --------------------------------------------------------------------------
# Anti-duplicado por anio
# --------------------------------------------------------------------------

class TestAntiDuplicado:
    def test_segunda_placa_del_anio_da_409(self, client, optin):
        db = _db()
        try:
            cliente = _crear_cliente(db, "Ana")
            mascota = _crear_mascota(db, cliente.id, "Luna", dias=1)
            mascota_id = mascota.id
        finally:
            db.close()

        assert client.get(f"{BASE}/mascotas/{mascota_id}/placa.png", headers=optin).status_code == 200
        resp = client.get(f"{BASE}/mascotas/{mascota_id}/placa.png", headers=optin)
        assert resp.status_code == 409
        assert "forzar=1" in resp.json()["detail"]

    def test_forzar_permite_regenerar(self, client, optin):
        db = _db()
        try:
            cliente = _crear_cliente(db, "Ana")
            mascota = _crear_mascota(db, cliente.id, "Luna", dias=1)
            mascota_id = mascota.id
        finally:
            db.close()

        url = f"{BASE}/mascotas/{mascota_id}/placa.png"
        assert client.get(url, headers=optin).status_code == 200
        assert client.get(f"{url}?forzar=1", headers=optin).status_code == 200

        db = _db()
        try:
            piezas = (
                db.query(PiezaGenerada)
                .filter(PiezaGenerada.tipo == TipoPieza.CUMPLEANOS)
                .all()
            )
            assert len(piezas) == 1
            assert piezas[0].anio == HOY.year
            assert piezas[0].referencia_tipo == "MASCOTA"
            assert piezas[0].beneficio == "10% OFF"
        finally:
            db.close()

    def test_otro_anio_se_puede_generar(self, client, optin):
        """La deduplicacion es por (referencia, anio): al ano que viene se repite."""
        db = _db()
        try:
            cliente = _crear_cliente(db, "Ana")
            mascota = _crear_mascota(db, cliente.id, "Luna", dias=1)
            mascota_id = mascota.id
        finally:
            db.close()

        url = f"{BASE}/mascotas/{mascota_id}/placa.png"
        assert client.get(url, headers=optin).status_code == 200

        db = _db()
        try:
            assert marketing_service.ya_registrado(
                db, 1, TipoPieza.CUMPLEANOS, FormatoPieza.PNG_1X1, mascota_id, HOY.year
            )
            assert not marketing_service.ya_registrado(
                db, 1, TipoPieza.CUMPLEANOS, FormatoPieza.PNG_1X1, mascota_id, HOY.year + 1
            )
        finally:
            db.close()

        # El mismo endpoint, con el anio ya registrado, vuelve a 409.
        assert client.get(url, headers=optin).status_code == 409

    def test_otra_mascota_no_se_bloquea(self, client, optin):
        db = _db()
        try:
            cliente = _crear_cliente(db, "Ana")
            a = _crear_mascota(db, cliente.id, "Luna", dias=1)
            b = _crear_mascota(db, cliente.id, "Toby", dias=2)
            a_id, b_id = a.id, b.id
        finally:
            db.close()

        assert client.get(f"{BASE}/mascotas/{a_id}/placa.png", headers=optin).status_code == 200
        assert client.get(f"{BASE}/mascotas/{b_id}/placa.png", headers=optin).status_code == 200


# --------------------------------------------------------------------------
# Configuracion del modulo
# --------------------------------------------------------------------------

class TestConfiguracion:
    def test_get_requiere_auth(self, client):
        assert client.get(f"{BASE}/config").status_code == 401

    def test_get_devuelve_config(self, client, optin):
        resp = client.get(f"{BASE}/config", headers=optin)
        assert resp.status_code == 200
        body = resp.json()
        assert body["comercio_id"] == 1
        assert body["habilitar"] is True
        assert body["beneficio"] == "10% OFF"

    def test_put_actualiza_beneficio(self, client, optin):
        resp = client.put(
            f"{BASE}/config", headers=optin, json={"beneficio": "20% OFF"}
        )
        assert resp.status_code == 200
        assert resp.json()["beneficio"] == "20% OFF"

        db = _db()
        try:
            comercio = db.query(Comercio).filter(Comercio.id == 1).first()
            assert comercio.beneficio_cumpleanos == "20% OFF"
        finally:
            db.close()

    def test_put_actualiza_optin(self, client, optin):
        resp = client.put(f"{BASE}/config", headers=optin, json={"habilitar": False})
        assert resp.status_code == 200
        assert resp.json()["habilitar"] is False

        # Con el modulo apagado, el listado se bloquea.
        assert client.get(f"{BASE}/proximos", headers=optin).status_code == 403

    def test_put_requiere_admin(self, client, optin):
        db = _db()
        try:
            _crear_empleado(db, "empleado@test.com", 1)
        finally:
            db.close()

        headers = _login(client, "empleado@test.com")
        resp = client.put(f"{BASE}/config", headers=headers, json={"beneficio": "99% OFF"})
        assert resp.status_code == 403

    def test_put_cuenta_clientes_consentidos(self, client, optin):
        db = _db()
        try:
            _crear_cliente(db, "Ana", acepta=True)
            _crear_cliente(db, "Beto", acepta=False)
        finally:
            db.close()

        resp = client.put(f"{BASE}/config", headers=optin, json={"beneficio": "5% OFF"})
        assert resp.json()["clientes_consentidos"] == 1

    def test_beneficio_se_refleja_en_el_listado(self, client, optin):
        resp = client.put(f"{BASE}/config", headers=optin, json={"beneficio": "30% OFF"})
        assert resp.status_code == 200

        listado = client.get(f"{BASE}/proximos", headers=optin)
        assert listado.json()["beneficio_default"] == "30% OFF"

    def test_beneficio_vacio_usa_default(self, client, optin):
        resp = client.put(f"{BASE}/config", headers=optin, json={"beneficio": ""})
        assert resp.status_code == 200
        assert resp.json()["beneficio"]
