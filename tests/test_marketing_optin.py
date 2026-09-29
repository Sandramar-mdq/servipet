"""Tests del opt-in de los modulos de Marketing (Etapa 12).

El endpoint `PATCH /comercios/{id}/opt-in` es la unica via de UI para activar
el Modulo Solidario y la Fidelizacion de Cumpleanos: sin el, ambos grupos de
endpoints de `/api/v1/marketing` responden 403 de forma permanente.
"""

import pytest

from app.models.comercio import Comercio
from app.models.usuario import Usuario
from app.services.auth import hash_password
from tests.conftest import TestingSessionLocal

OPTIN = "/comercios/1/opt-in"


def _empleado_headers(client):
    db = TestingSessionLocal()
    try:
        db.add(Usuario(
            email="empleado_optin@test.com",
            password_hash=hash_password("empleado123"),
            rol="EMPLEADO",
            comercio_id=1,
            activo=True,
        ))
        db.commit()
    finally:
        db.close()

    resp = client.post("/auth/login", json={"email": "empleado_optin@test.com", "password": "empleado123"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
def empleado_headers(client):
    return _empleado_headers(client)


def _comercio():
    db = TestingSessionLocal()
    try:
        return db.query(Comercio).filter(Comercio.id == 1).first()
    finally:
        db.close()


def _patch(client, headers, **flags):
    datos = {"habilitar_red_comunitaria": True}
    datos.update(flags)
    return client.patch(OPTIN, headers=headers, json=datos)


class TestAcceso:
    def test_anonimo_401(self, client):
        resp = client.patch(OPTIN, json={"habilitar_red_comunitaria": True})
        assert resp.status_code == 401

    def test_cliente_403(self, client, auth_headers):
        resp = _patch(client, auth_headers, habilitar_modulo_solidario=True)
        assert resp.status_code == 403

    def test_empleado_403(self, client, empleado_headers):
        resp = _patch(client, empleado_headers, habilitar_modulo_solidario=True)
        assert resp.status_code == 403


class TestActivacionModulos:
    def test_activa_modulo_solidario(self, client, admin_headers):
        resp = _patch(client, admin_headers, habilitar_modulo_solidario=True)
        assert resp.status_code == 200, resp.text
        assert resp.json()["habilitar_modulo_solidario"] is True
        assert _comercio().habilitar_modulo_solidario is True

    def test_activa_cumpleanos(self, client, admin_headers):
        resp = _patch(client, admin_headers, habilitar_cumpleanos=True)
        assert resp.status_code == 200, resp.text
        assert resp.json()["habilitar_cumpleanos"] is True
        assert _comercio().habilitar_cumpleanos is True

    def test_desactiva_cumpleanos(self, client, admin_headers):
        _patch(client, admin_headers, habilitar_cumpleanos=True)
        resp = _patch(client, admin_headers, habilitar_cumpleanos=False)
        assert resp.status_code == 200, resp.text
        assert _comercio().habilitar_cumpleanos is False

    def test_omitir_flags_no_pisa_el_estado(self, client, admin_headers):
        _patch(client, admin_headers, habilitar_modulo_solidario=True, habilitar_cumpleanos=True)

        resp = client.patch(
            OPTIN,
            headers=admin_headers,
            json={"habilitar_red_comunitaria": True},
        )
        assert resp.status_code == 200, resp.text

        comercio = _comercio()
        assert comercio.habilitar_modulo_solidario is True
        assert comercio.habilitar_cumpleanos is True

    def test_toggle_solidario_no_pisa_cumpleanos(self, client, admin_headers):
        _patch(client, admin_headers, habilitar_cumpleanos=True)
        _patch(client, admin_headers, habilitar_modulo_solidario=True)

        comercio = _comercio()
        assert comercio.habilitar_modulo_solidario is True
        assert comercio.habilitar_cumpleanos is True

    def test_defaults_en_false(self, client, admin_headers):
        assert _comercio().habilitar_modulo_solidario is False
        assert _comercio().habilitar_cumpleanos is False


class TestDesbloqueoDeMarketing:
    def test_optin_habilita_cartel_solidario(self, client, admin_headers):
        """Con el modulo activo, el cartel deja de responder 403 por opt-in."""
        from app.models.aviso_comunitario import AvisoComunitario
        from app.models.cliente import Cliente
        from app.models.mascota import Mascota

        db = TestingSessionLocal()
        try:
            db.add(Cliente(nombre="Ana Diaz", comercio_id=1, activo=True))
            db.commit()
            cliente = db.query(Cliente).filter(Cliente.nombre == "Ana Diaz").first()
            db.add(Mascota(nombre="Rocky", especie="Perro", raza="Mestizo",
                           cliente_id=cliente.id, activo=True, fallecida=False))
            db.add(AvisoComunitario(
                comercio_id=1,
                cliente_id=cliente.id,
                tipo="PERDIDA",
                titulo="Perro perdido",
                descripcion="Se escapo del parque",
            ))
            db.commit()
        finally:
            db.close()

        resp = _patch(client, admin_headers, habilitar_modulo_solidario=True)
        assert resp.status_code == 200, resp.text

        db = TestingSessionLocal()
        try:
            aviso_id = db.query(AvisoComunitario).first().id
        finally:
            db.close()

        cartel = client.get(
            f"/api/v1/marketing/solidaridad/avisos/{aviso_id}/cartel.pdf",
            headers=admin_headers,
        )
        assert cartel.status_code == 200, cartel.text
        assert cartel.headers["content-type"] == "application/pdf"

    def test_optin_habilita_listado_cumpleanos(self, client, admin_headers):
        resp = _patch(client, admin_headers, habilitar_cumpleanos=True)
        assert resp.status_code == 200, resp.text

        listado = client.get("/api/v1/marketing/cumpleanos/proximos", headers=admin_headers)
        assert listado.status_code == 200, listado.text
        assert listado.json()["items"] == []
