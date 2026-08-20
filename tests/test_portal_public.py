from datetime import datetime

from app.models.comercio import Comercio
from app.models.cliente import Cliente
from app.models.mascota import Mascota
from app.models.servicio import Servicio
from app.models.turno import Turno


def _seed_turno(db, *, fase=None, estado="PENDIENTE"):
    c = Comercio(id=1, nombre="Test", tipo_comercio="VETERINARIA", activo=True)
    db.merge(c)
    db.commit()

    cliente = Cliente(nombre="Juan Perez", comercio_id=1, telefono="1155551234")
    db.add(cliente)
    db.flush()

    mascota = Mascota(nombre="Luna", cliente_id=cliente.id, especie="Perro", raza="Caniche")
    db.add(mascota)
    db.flush()

    servicio = Servicio(nombre="Baño Completo", precio_base=5000.0, duracion_minutos=45)
    db.add(servicio)
    db.flush()

    turno = Turno(
        cliente_id=cliente.id,
        mascota_id=mascota.id,
        servicio_id=servicio.id,
        fecha_hora=datetime(2026, 8, 20, 10, 0),
        estado=estado,
        fase=fase,
    )
    db.add(turno)
    db.commit()
    db.refresh(turno)
    return turno


class TestPortalPublico:
    def test_portal_seguimiento_acceso_publico(self, client):
        resp = client.get("/portal/seguimiento/NOEXISTENTE")
        assert resp.status_code == 200

    def test_portal_seguimiento_codigo_inexistente(self, client):
        resp = client.get("/portal/seguimiento/NOEXISTENTE")
        assert resp.status_code == 200
        assert b"Codigo no encontrado" in resp.content

    def test_portal_seguimiento_con_turno(self, client):
        from tests.conftest import TestingSessionLocal
        db = TestingSessionLocal()
        try:
            turno = _seed_turno(db, fase="BAÑO")
            codigo = turno.codigo_seguimiento
        finally:
            db.close()

        resp = client.get(f"/portal/seguimiento/{codigo}")
        assert resp.status_code == 200
        assert b"Luna" in resp.content
        assert "Ba\u00f1o".encode("utf-8") in resp.content

    def test_portal_seguimiento_fase_espera(self, client):
        from tests.conftest import TestingSessionLocal
        db = TestingSessionLocal()
        try:
            turno = _seed_turno(db, fase="ESPERA")
            codigo = turno.codigo_seguimiento
        finally:
            db.close()

        resp = client.get(f"/portal/seguimiento/{codigo}")
        assert resp.status_code == 200
        assert b"Luna" in resp.content
        assert b"En Espera" in resp.content

    def test_portal_whatsapp_link(self, client):
        from tests.conftest import TestingSessionLocal
        db = TestingSessionLocal()
        try:
            turno = _seed_turno(db, fase="LISTO")
            codigo = turno.codigo_seguimiento
        finally:
            db.close()

        resp = client.get(f"/portal/seguimiento/{codigo}")
        assert resp.status_code == 200
        assert b"wa.me" in resp.content
        assert b"1155551234" in resp.content
