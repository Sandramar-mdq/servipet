import logging
import sys

from app.config import settings

logger = logging.getLogger("servipet.notifier")

if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_handler)
    logger.propagate = False
logger.setLevel(logging.INFO)


class LoggerProvider:
    """Proveedor de simulacion: registra el destino y el mensaje en consola."""

    def send(self, telefono: str, mensaje: str) -> None:
        logger.info("[Notificacion] Para: %s | Mensaje: %s", telefono, mensaje)


class TwilioProvider:
    """Proveedor real (WhatsApp/SMS via Twilio). Fallback a log si falta config/libreria."""

    def __init__(self) -> None:
        self._client = None
        self._from = settings.TWILIO_FROM
        self._sid = settings.TWILIO_ACCOUNT_SID
        self._token = settings.TWILIO_AUTH_TOKEN

    def _get_client(self):
        if self._client is None:
            if not (self._sid and self._token):
                raise RuntimeError("Twilio requiere TWILIO_ACCOUNT_SID y TWILIO_AUTH_TOKEN")
            try:
                from twilio.rest import Client
            except ImportError:
                raise RuntimeError("La libreria 'twilio' no esta instalada")
            self._client = Client(self._sid, self._token)
        return self._client

    def send(self, telefono: str, mensaje: str) -> None:
        if not self._from:
            raise RuntimeError("Twilio requiere TWILIO_FROM")
        destino = telefono if telefono.startswith("whatsapp:") else f"whatsapp:+{telefono}"
        from_tw = self._from if self._from.startswith("whatsapp:") else f"whatsapp:{self._from}"
        self._get_client().messages.create(from_=from_tw, body=mensaje, to=destino)


def _get_provider():
    provider = (settings.NOTIFICATION_PROVIDER or "log").strip().lower()
    if provider == "twilio":
        return TwilioProvider()
    return LoggerProvider()


def _enviar(telefono: str, mensaje: str) -> None:
    if not telefono:
        logger.warning("[Notificacion] Sin telefono de destino, no se envia mensaje")
        return
    try:
        _get_provider().send(telefono, mensaje)
    except Exception:
        logger.exception("[Notificacion] Fallo el envio a %s", telefono)


def _datos_turno(turno) -> tuple:
    fecha = turno.fecha_hora.strftime("%d/%m/%Y")
    hora = turno.fecha_hora.strftime("%H:%M")
    return {
        "cliente": turno.cliente.nombre,
        "mascota": turno.mascota.nombre,
        "servicio": turno.servicio.nombre,
        "fecha": fecha,
        "hora": hora,
    }


def _mensaje_reserva(turno) -> str:
    d = _datos_turno(turno)
    return (
        f"¡Hola {d['cliente']}! Recibimos tu solicitud de turno para "
        f"{d['mascota']} ({d['servicio']}) el día {d['fecha']} a las {d['hora']} hs. "
        "Te avisaremos cuando sea confirmado por el comercio."
    )


def _mensaje_confirmado(turno) -> str:
    d = _datos_turno(turno)
    return (
        f"¡Buenas noticias {d['cliente']}! Tu turno para {d['mascota']} ({d['servicio']}) "
        f"el {d['fecha']} a las {d['hora']} hs ha sido CONFIRMADO. ¡Te esperamos!"
    )


def _mensaje_cancelado(turno) -> str:
    d = _datos_turno(turno)
    return (
        f"Hola {d['cliente']}, te informamos que tu turno para {d['mascota']} ({d['servicio']}) "
        f"el {d['fecha']} a las {d['hora']} hs ha sido CANCELADO. "
        "Comunícate con el comercio para más información."
    )


def notificar_reserva_creada(turno) -> None:
    telefono = turno.cliente.telefono or ""
    _enviar(telefono, _mensaje_reserva(turno))


def notificar_cambio_estado_turno(turno, nuevo_estado: str) -> None:
    telefono = turno.cliente.telefono or ""
    if nuevo_estado == "Confirmado":
        _enviar(telefono, _mensaje_confirmado(turno))
    elif nuevo_estado == "Cancelado":
        _enviar(telefono, _mensaje_cancelado(turno))
