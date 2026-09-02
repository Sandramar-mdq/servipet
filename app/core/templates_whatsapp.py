"""Motor de plantillas de texto para notificaciones WhatsApp.

Genera mensajes llano-texto (sin HTML, formato amigable para WhatsApp)
soportando variables por evento: {cliente}, {mascota}, {servicio},
{fecha}, {hora}, {comercio} y {codigo}.

Los eventos viven en app.models.notification para que tanto el modelo
NotificationLog como este motor compartan las mismas constantes.
"""

from app.models.notification import (
    EVENTO_CANCELACION,
    EVENTO_CONFIRMATION,
    EVENTO_PET_READY,
    EVENTO_REMINDER,
)

TEXTOS_WHATSAPP: dict[str, str] = {
    EVENTO_REMINDER: (
        "Hola {cliente}, te recordamos tu turno de {mascota} ({servicio}) "
        "el {fecha} a las {hora} hs. ¡Te esperamos!"
    ),
    EVENTO_PET_READY: (
        "¡Hola {cliente}! Tu mascota {mascota} ya está lista para retirar "
        "({servicio}). ¡Te esperamos en {comercio}!"
    ),
    EVENTO_CANCELACION: (
        "Hola {cliente}, te informamos que tu turno para {mascota} ({servicio}) "
        "el {fecha} a las {hora} hs ha sido CANCELADO. "
        "Comunícate con el comercio para más información."
    ),
}

_VALORES_DEFAULT = {
    "cliente": "",
    "mascota": "",
    "servicio": "",
    "fecha": "",
    "hora": "",
    "comercio": "Servipet",
    "codigo": "",
}


def _plantilla_confirmacion(confirmado: bool) -> str:
    if confirmado:
        return (
            "¡Buenas noticias {cliente}! Tu turno para {mascota} ({servicio}) "
            "el {fecha} a las {hora} hs ha sido CONFIRMADO. ¡Te esperamos!"
        )
    return (
        "¡Hola {cliente}! Recibimos tu solicitud de turno para {mascota} "
        "({servicio}) el día {fecha} a las {hora} hs. "
        "Te avisaremos cuando sea confirmado por el comercio."
    )


def render(evento: str, datos: dict | None = None) -> str:
    """Renderiza el mensaje para `evento` interpolando `datos` (dict).

    Ante eventos no soportados o variables faltantes no lanza excepcion:
    usa valores por defecto vacios para no romper el envio.
    """
    base = dict(_VALORES_DEFAULT)
    if datos:
        base.update({k: v for k, v in datos.items() if v is not None})

    if evento == EVENTO_CONFIRMATION:
        plantilla = _plantilla_confirmacion(bool(base.get("confirmado")))
    else:
        plantilla = TEXTOS_WHATSAPP.get(evento)
        if plantilla is None:
            return ""

    return plantilla.format(**base)


def _nombre(obj, attr: str) -> str:
    return str(getattr(obj, attr, "") or "")


def datos_turno(turno) -> dict:
    """Extrae las variables de plantilla a partir de un `Turno`."""
    cliente = turno.cliente if turno.cliente else None
    mascota = turno.mascota if turno.mascota else None
    servicio = turno.servicio if turno.servicio else None

    comercio = None
    if cliente is not None and getattr(cliente, "comercio", None):
        comercio = cliente.comercio
    elif mascota is not None and mascota.cliente and mascota.cliente.comercio:
        comercio = mascota.cliente.comercio

    fecha_hora = turno.fecha_hora
    return {
        "cliente": _nombre(cliente, "nombre"),
        "mascota": _nombre(mascota, "nombre"),
        "servicio": _nombre(servicio, "nombre"),
        "fecha": fecha_hora.strftime("%d/%m/%Y") if fecha_hora else "",
        "hora": fecha_hora.strftime("%H:%M") if fecha_hora else "",
        "comercio": _nombre(comercio, "nombre") or _VALORES_DEFAULT["comercio"],
        "codigo": getattr(turno, "codigo_seguimiento", "") or "",
    }