"""Tests del Modulo 10.1: notificaciones whatsapp y webhooks.

Cubre:
- Motor de plantillas (app/core/templates_whatsapp.py).
- Servicio de notificaciones (app/services/notification_service.py) con
  mocks del HTTP externo (provider log y webhook).
- Integracion con BackgroundTasks en endpoints de turnos.
"""

from datetime import date, datetime, timedelta

import pytest

from app.config import settings
from app.core import templates_whatsapp
from app.models.cliente import Cliente
from app.models.comercio import Comercio
from app.models.mascota import Mascota
from app.models.notification import (
    ESTADO_FAILED,
    ESTADO_SENT,
    EVENTO_CANCELACION,
    EVENTO_CONFIRMATION,
    EVENTO_PET_READY,
    EVENTO_REMINDER,
    NotificationLog,
)
from app.models.servicio import Servicio
from app.models.turno import Turno
from app.services import notification_service
from app.services.notifier import notificar_cambio_estado_turno, notificar_reserva_creada
from tests.conftest import TestingSessionLocal

TELEFONO = "+5491123456789"


@pytest.fixture(autouse=True)
def _notificaciones_usa_bd_de_pruebas(monkeypatch):
    """El servicio abre su sesion via app.database.SessionLocal.

    Se apunta a la BD en memoria de pruebas para no tocar servipet.db ni
    realizar llamadas HTTP reales.
    """
    import app.database as database

    monkeypatch.setattr(database, "SessionLocal", TestingSessionLocal)


@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed_comercio(db) -> Comercio:
    comercio = db.get(Comercio, 1)
    if comercio is None:
        comercio = Comercio(
            id=1,
            nombre="Comercio Test",
            tipo_comercio="VETERINARIA",
            hora_apertura="09:00",
            hora_cierre="18:00",
            slot_minutos=30,
            activo=True,
        )
        db.add(comercio)
        db.flush()
    comercio.hora_apertura = "09:00"
    comercio.hora_cierre = "18:00"
    comercio.slot_minutos = 30
    return comercio


def _seed_turno(db, *, telefono=TELEFONO, estado="PENDIENTE") -> Turno:
    _seed_comercio(db)
    servicio = Servicio(nombre="Consulta", duracion_minutos=30)
    db.add(servicio)
    db.flush()
    cliente = Cliente(comercio_id=1, nombre="Ana", telefono=telefono)
    db.add(cliente)
    db.flush()
    mascota = Mascota(nombre="Rocky", cliente_id=cliente.id, especie="Perro")
    db.add(mascota)
    db.flush()
    turno = Turno(
        cliente_id=cliente.id,
        mascota_id=mascota.id,
        servicio_id=servicio.id,
        fecha_hora=datetime.now() + timedelta(days=1),
        duracion_minutos=30,
        estado=estado,
    )
    db.add(turno)
    db.commit()
    db.refresh(turno)
    return turno


# ---------------------------------------------------------------------------
# Motor de plantillas
# ---------------------------------------------------------------------------


class TestPlantillasWhatsApp:
    def test_confirmacion_confirmada(self):
        msg = templates_whatsapp.render(
            EVENTO_CONFIRMATION,
            {"cliente": "Ana", "mascota": "Rocky", "servicio": "Consulta",
             "fecha": "02/09/2026", "hora": "10:00", "confirmado": True},
        )
        assert "CONFIRMADO" in msg
        assert "Ana" in msg and "Rocky" in msg and "02/09/2026" in msg

    def test_confirmacion_reserva_solicitud(self):
        msg = templates_whatsapp.render(
            EVENTO_CONFIRMATION,
            {"cliente": "Ana", "mascota": "Rocky", "servicio": "Consulta",
             "fecha": "02/09/2026", "hora": "10:00", "confirmado": False},
        )
        assert "solicitud" in msg
        assert "CONFIRMADO" not in msg

    def test_pet_ready(self):
        msg = templates_whatsapp.render(EVENTO_PET_READY,
                                        {"cliente": "Ana", "mascota": "Rocky"})
        assert "Rocky" in msg
        assert "lista para retirar" in msg

    def test_reminder(self):
        msg = templates_whatsapp.render(
            EVENTO_REMINDER, {"cliente": "Ana", "mascota": "Rocky", "hora": "10:00"}
        )
        assert "recordamos" in msg

    def test_cancelacion(self):
        msg = templates_whatsapp.render(EVENTO_CANCELACION,
                                        {"cliente": "Ana", "mascota": "Max"})
        assert "CANCELADO" in msg

    def test_evento_desconocido_devuelve_vacio(self):
        assert templates_whatsapp.render("FLUJO_IMAGINARIO", {}) == ""

    def test_variables_faltantes_no_explotan(self):
        msg = templates_whatsapp.render(EVENTO_PET_READY, {})
        assert "{" not in msg and "}" not in msg

    def test_datos_turno_construye_variables(self, db):
        turno = _seed_turno(db)
        d = templates_whatsapp.datos_turno(turno)
        assert d["cliente"] == "Ana"
        assert d["mascota"] == "Rocky"
        assert d["servicio"] == "Consulta"
        assert d["comercio"] == "Comercio Test"
        assert d["fecha"] and d["hora"] and d["codigo"]


# ---------------------------------------------------------------------------
# Servicio de notificaciones
# ---------------------------------------------------------------------------


class TestServicioNotificaciones:
    def test_procesar_confirmacion_exitosa_con_provider_log(self, db):
        turno = _seed_turno(db)
        log = notification_service.procesar(turno.id, EVENTO_CONFIRMATION, confirmado=True)
        assert log is not None
        assert log.evento == EVENTO_CONFIRMATION
        assert log.estado == ESTADO_SENT
        assert log.destino == TELEFONO
        assert log.intentos == 1
        assert log.enviado_en is not None
        assert "CONFIRMADO" in log.mensaje

    def test_procesar_sin_telefono_termina_failed(self, db, monkeypatch):
        monkeypatch.setattr(notification_service, "_pausa_reintento", lambda intentos: None)
        turno = _seed_turno(db, telefono=None)
        log = notification_service.procesar(turno.id, EVENTO_CONFIRMATION)
        assert log is not None
        assert log.estado == ESTADO_FAILED
        assert log.intentos == log.max_intentos
        assert "destino" in (log.ultimo_error or "")

    def test_procesar_turno_inexistente_retorna_none(self, db):
        assert notification_service.procesar(999999, EVENTO_CONFIRMATION) is None

    def test_webhook_provider_envia_payload(self, db, monkeypatch):
        llamadas = []

        class _FakeResp:
            def raise_for_status(self):
                return None

        monkeypatch.setattr(settings, "NOTIFICATION_PROVIDER", "webhook")
        monkeypatch.setattr(settings, "NOTIFICATION_WEBHOOK_URL", "https://hook.test/wh")
        monkeypatch.setattr(
            notification_service,
            "_http_post",
            lambda url, *, json, timeout: (llamadas.append((url, json, timeout)), _FakeResp())[1],
        )

        turno = _seed_turno(db)
        log = notification_service.procesar(turno.id, EVENTO_PET_READY)
        assert log.estado == ESTADO_SENT
        assert len(llamadas) == 1
        url, payload, timeout = llamadas[0]
        assert url == "https://hook.test/wh"
        assert payload["destino"] == TELEFONO
        assert payload["evento"] == EVENTO_PET_READY
        assert payload["turno_id"] == turno.id
        assert "lista para retirar" in payload["mensaje"]
        assert timeout == 10

    def test_webhook_falla_hasta_failed_con_reintentos(self, db, monkeypatch):
        monkeypatch.setattr(settings, "NOTIFICATION_PROVIDER", "webhook")
        monkeypatch.setattr(settings, "NOTIFICATION_WEBHOOK_URL", "https://hook.test/wh")
        monkeypatch.setattr(settings, "NOTIFICATION_MAX_INTENTOS", 2)
        monkeypatch.setattr(notification_service, "_pausa_reintento", lambda intentos: None)

        def _boom(url, *, json, timeout):
            raise RuntimeError("timeout 504")

        monkeypatch.setattr(notification_service, "_http_post", _boom)

        turno = _seed_turno(db)
        log = notification_service.procesar(turno.id, EVENTO_PET_READY)
        assert log.estado == ESTADO_FAILED
        assert log.intentos == 2
        assert "504" in (log.ultimo_error or "")
        assert log.enviado_en is None

    def test_webhook_reintenta_y_termina_exitoso(self, db, monkeypatch):
        monkeypatch.setattr(settings, "NOTIFICATION_PROVIDER", "webhook")
        monkeypatch.setattr(settings, "NOTIFICATION_WEBHOOK_URL", "https://hook.test/wh")
        monkeypatch.setattr(settings, "NOTIFICATION_MAX_INTENTOS", 3)
        monkeypatch.setattr(notification_service, "_pausa_reintento", lambda intentos: None)

        contador = {"n": 0}

        class _FakeResp:
            def raise_for_status(self):
                return None

        def _flaky(url, *, json, timeout):
            contador["n"] += 1
            if contador["n"] == 1:
                raise RuntimeError("fallo primero")
            return _FakeResp()

        monkeypatch.setattr(notification_service, "_http_post", _flaky)

        turno = _seed_turno(db)
        log = notification_service.procesar(turno.id, EVENTO_PET_READY)
        assert log.estado == ESTADO_SENT
        assert log.intentos == 2
        assert contador["n"] == 2

    def test_enqueue_cambio_estado_confirmado(self, db):
        turno = _seed_turno(db)
        log = notification_service.enqueue_cambio_estado(turno.id, "CONFIRMADO")
        assert log is not None
        assert log.evento == EVENTO_CONFIRMATION
        assert "CONFIRMADO" in log.mensaje

    def test_enqueue_cambio_estado_cancelado(self, db):
        turno = _seed_turno(db)
        log = notification_service.enqueue_cambio_estado(turno.id, "CANCELADO")
        assert log is not None
        assert log.evento == EVENTO_CANCELACION
        assert "CANCELADO" in log.mensaje

    def test_enqueue_cambio_estado_ignora_otros_estados(self, db):
        turno = _seed_turno(db)
        assert notification_service.enqueue_cambio_estado(turno.id, "PENDIENTE") is None

    def test_notifier_legacy_delega_al_servicio(self, db):
        turno = _seed_turno(db)
        notificar_reserva_creada(turno)
        log = db.query(NotificationLog).first()
        assert log is not None
        assert log.evento == EVENTO_CONFIRMATION
        assert log.estado == ESTADO_SENT

    def test_notifier_legacy_cambio_estado_delega(self, db):
        turno = _seed_turno(db)
        notificar_cambio_estado_turno(turno, "Confirmado")
        log = db.query(NotificationLog).order_by(NotificationLog.id.desc()).first()
        assert log is not None
        assert log.evento == EVENTO_CONFIRMATION
        assert "CONFIRMADO" in log.mensaje


# ---------------------------------------------------------------------------
# Integracion con BackgroundTasks en los endpoints
# ---------------------------------------------------------------------------


class TestIntegracionEndpoints:
    def test_cambiar_estado_http_encola_confirmacion(self, client, db):
        turno = _seed_turno(db)
        resp = client.post(
            f"/page/turnos/{turno.id}/cambiar-estado",
            data={"estado": "CONFIRMADO"},
            follow_redirects=False,
        )
        assert resp.status_code == 303

        db.expire_all()
        turno_db = db.get(Turno, turno.id)
        assert turno_db.estado == "CONFIRMADO"

        logs = db.query(NotificationLog).order_by(NotificationLog.id.asc()).all()
        assert len(logs) == 1
        log = logs[0]
        assert log.turno_id == turno.id
        assert log.evento == EVENTO_CONFIRMATION
        assert log.estado == ESTADO_SENT
        assert log.destino == TELEFONO

    def test_fase_listo_http_envia_pet_ready(self, client, db):
        turno = _seed_turno(db)
        resp = client.post(f"/page/turnos/{turno.id}/fase", data={"fase": "LISTO"}, follow_redirects=False)
        assert resp.status_code == 303

        db.expire_all()
        turno_db = db.get(Turno, turno.id)
        assert turno_db.fase == "LISTO"

        log = db.query(NotificationLog).first()
        assert log is not None
        assert log.evento == EVENTO_PET_READY
        assert log.estado == ESTADO_SENT
        assert "lista para retirar" in log.mensaje

    def test_reserva_http_crea_notification(self, client):
        db = TestingSessionLocal()
        try:
            _seed_comercio(db)
            servicio = Servicio(nombre="Consulta 30", duracion_minutos=30)
            db.add(servicio)
            db.commit()
            db.refresh(servicio)
        finally:
            db.close()

        resp = client.post("/auth/register", json={
            "email": "cliente@test.com",
            "password": "clave123",
            "nombre": "Cliente Test",
            "telefono": TELEFONO,
        })
        assert resp.status_code == 201, resp.text

        login = client.post("/auth/login", json={
            "email": "cliente@test.com",
            "password": "clave123",
        })
        assert login.status_code == 200, login.text
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        masc = client.post("/portal/mascotas", headers=headers, json={
            "nombre": "Rocky",
            "especie": "Perro",
        })
        assert masc.status_code == 201, masc.text

        manana = (date.today() + timedelta(days=1)).isoformat()
        resp = client.post("/portal/reservar", headers=headers, json={
            "mascota_id": masc.json()["id"],
            "servicio_id": servicio.id,
            "fecha": manana,
            "hora": "10:00",
        })
        assert resp.status_code == 201, resp.text
        turno_id = resp.json()["id"]

        db = TestingSessionLocal()
        try:
            log = (
                db.query(NotificationLog)
                .filter(NotificationLog.turno_id == turno_id)
                .first()
            )
        finally:
            db.close()
        assert log is not None
        assert log.estado == ESTADO_SENT
        assert log.evento == EVENTO_CONFIRMATION
        assert "Rocky" in log.mensaje
        assert "solicitud" in log.mensaje