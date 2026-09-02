"""Servicio de notificaciones de turnos (WhatsApp / webhook).

Desacopla la logica de envio del resto de la app:

- Proveedor seleccionado por `settings.NOTIFICATION_PROVIDER`:
  `webhook` (POST HTTP via httpx) o los proveedores historicos de
  `app.services.notifier` (`log` / `twilio`).
- Persiste cada envio en `NotificationLog` con estados PENDING/SENT/FAILED,
  contador de reintentos y motivo del ultimo error.
- Cada `procesar()` abre una sesion propia (via app.database.SessionLocal)
  para poder ejecutarse desde BackgroundTasks una vez la respuesta del API
  ya salio (la sesion del request queda cerrada en ese momento).
"""

import logging
import time
from datetime import datetime

from app.config import settings
from app.core.templates_whatsapp import datos_turno, render
from app.models.notification import (
    ESTADO_FAILED,
    ESTADO_PENDING,
    ESTADO_SENT,
    EVENTO_CANCELACION,
    EVENTO_CONFIRMATION,
    EVENTO_PET_READY,
    EVENTO_REMINDER,
    NotificationLog,
)
from app.models.turno import Turno

logger = logging.getLogger("servipet.notification")


def _crear_sesion():
    # Import local: permite al test suite reemplazar SessionLocal
    # (monkeypatch) apuntando a la base en memoria de pruebas.
    from app.database import SessionLocal

    return SessionLocal()


def _http_post(url, *, json, timeout):
    import httpx

    resp = httpx.post(url, json=json, timeout=timeout)
    resp.raise_for_status()
    return resp


class WebhookProvider:
    """Envia la notificacion a un webhook HTTP externo."""

    def send(self, destino: str, mensaje: str, evento: str, turno_id: int) -> None:
        url = (settings.NOTIFICATION_WEBHOOK_URL or "").strip()
        if not url:
            raise RuntimeError("Webhook requiere NOTIFICATION_WEBHOOK_URL")
        _http_post(
            url,
            json={
                "destino": destino,
                "mensaje": mensaje,
                "evento": evento,
                "turno_id": turno_id,
            },
            timeout=settings.NOTIFICATION_WEBHOOK_TIMEOUT_S,
        )


def _obtener_provider():
    provider = (settings.NOTIFICATION_PROVIDER or "log").strip().lower()
    if provider == "webhook":
        return WebhookProvider()
    from app.services.notifier import _get_provider

    return _get_provider()


def _enviar(destino: str, mensaje: str, evento: str, turno_id: int) -> None:
    if not destino:
        raise RuntimeError("Sin telefono de destino")
    provider = _obtener_provider()
    if isinstance(provider, WebhookProvider):
        provider.send(destino, mensaje, evento, turno_id)
    else:
        provider.send(destino, mensaje)


def _pausa_reintento(intentos: int) -> None:
    time.sleep(0.1 * intentos)


def _enviar_con_reintentos(db, log: NotificationLog, *, destino, mensaje, evento, turno_id) -> bool:
    while log.intentos < log.max_intentos:
        log.intentos += 1
        try:
            _enviar(destino, mensaje, evento, turno_id)
            log.estado = ESTADO_SENT
            log.enviado_en = datetime.utcnow()
            log.ultimo_error = None
            db.commit()
            return True
        except Exception as exc:  # noqa: BLE001 (falla cualquier provider)
            log.ultimo_error = str(exc)
            log.estado = ESTADO_PENDING if log.intentos < log.max_intentos else ESTADO_FAILED
            db.commit()
            if log.intentos < log.max_intentos:
                _pausa_reintento(log.intentos)
    return False


def procesar(turno_id: int, evento: str, *, confirmado: bool = False) -> NotificationLog | None:
    """Registra y envia la notificacion del turno (con reintentos)."""
    db = _crear_sesion()
    try:
        turno = db.query(Turno).filter(Turno.id == turno_id).first()
        if not turno:
            logger.warning("Notification: turno %s inexistente", turno_id)
            return None

        datos = datos_turno(turno)
        datos["confirmado"] = confirmado
        mensaje = render(evento, datos)
        if not mensaje:
            logger.warning("Notification: evento %s sin plantilla", evento)
            return None

        destino = ""
        if turno.cliente is not None:
            destino = turno.cliente.telefono or ""

        log = NotificationLog(
            turno_id=turno.id,
            evento=evento,
            canal="whatsapp",
            destino=destino,
            estado=ESTADO_PENDING,
            mensaje=mensaje,
            max_intentos=settings.NOTIFICATION_MAX_INTENTOS,
        )
        db.add(log)
        db.commit()
        db.refresh(log)

        _enviar_con_reintentos(
            db,
            log,
            destino=destino,
            mensaje=mensaje,
            evento=evento,
            turno_id=turno.id,
        )
        db.refresh(log)
        return log
    except Exception:  # noqa: BLE001
        logger.exception("Notification: error al procesar turno %s", turno_id)
        return None
    finally:
        db.close()


def enqueue_reserva(turno_id: int) -> NotificationLog | None:
    return procesar(turno_id, EVENTO_CONFIRMATION, confirmado=False)


def enqueue_cambio_estado(turno_id: int, estado: str) -> NotificationLog | None:
    estado_norm = (estado or "").upper()
    if estado_norm == "CONFIRMADO":
        return procesar(turno_id, EVENTO_CONFIRMATION, confirmado=True)
    if estado_norm in ("CANCELADO", "CANCELADO_TARDIO"):
        return procesar(turno_id, EVENTO_CANCELACION)
    return None


def enqueue_pet_ready(turno_id: int) -> NotificationLog | None:
    return procesar(turno_id, EVENTO_PET_READY)


def enqueue_recordatorio(turno_id: int) -> NotificationLog | None:
    return procesar(turno_id, EVENTO_REMINDER)