from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.core.templating import get_templates
from app.database import get_db
from app.models.turno import Turno

router = APIRouter(tags=["Portal Publico"])
templates = get_templates()

FASE_LABELS = {
    "ESPERA": "En Espera",
    "BAÑO": "En Baño",
    "CORTE": "En Corte",
    "LISTO": "Listo para Retirar",
}

FASE_COLORS = {
    "ESPERA": "bg-yellow-100 text-yellow-800 border-yellow-300",
    "BAÑO": "bg-blue-100 text-blue-800 border-blue-300",
    "CORTE": "bg-purple-100 text-purple-800 border-purple-300",
    "LISTO": "bg-emerald-100 text-emerald-800 border-emerald-300",
}

ESTADO_LABELS = {
    "PENDIENTE": "En Espera",
    "Pendiente": "En Espera",
    "CONFIRMADO": "Confirmado",
    "FINALIZADO": "Finalizado",
    "CANCELADO": "Cancelado",
    "CANCELADO_TARDIO": "Cancelado",
}

ESTADO_COLORS = {
    "PENDIENTE": "bg-yellow-100 text-yellow-800 border-yellow-300",
    "Pendiente": "bg-yellow-100 text-yellow-800 border-yellow-300",
    "CONFIRMADO": "bg-blue-100 text-blue-800 border-blue-300",
    "FINALIZADO": "bg-emerald-100 text-emerald-800 border-emerald-300",
    "CANCELADO": "bg-gray-100 text-gray-800 border-gray-300",
    "CANCELADO_TARDIO": "bg-gray-100 text-gray-800 border-gray-300",
}


@router.get("/portal/seguimiento/{codigo_seguimiento}", response_class=HTMLResponse)
def public_portal_seguimiento(
    codigo_seguimiento: str,
    request: Request,
    db: Session = Depends(get_db),
):
    turno = (
        db.query(Turno)
        .filter(Turno.codigo_seguimiento == codigo_seguimiento.upper())
        .first()
    )

    if not turno:
        return templates.TemplateResponse(
            request=request,
            name="portal/seguimiento.html",
            context={"encontrado": False, "codigo": codigo_seguimiento},
        )

    mascota = turno.mascota
    cliente = mascota.cliente if mascota else None
    servicio = turno.servicio

    if turno.fase and turno.fase in FASE_LABELS:
        fase_label = FASE_LABELS[turno.fase]
        fase_color = FASE_COLORS[turno.fase]
    else:
        fase_label = ESTADO_LABELS.get(turno.estado, turno.estado)
        fase_color = ESTADO_COLORS.get(turno.estado, "bg-gray-100 text-gray-800 border-gray-300")

    whatsapp_url = ""
    if cliente and cliente.telefono:
        telefono_limpio = cliente.telefono.replace(" ", "").replace("-", "").replace("+", "")
        whatsapp_url = f"https://wa.me/549{telefono_limpio}?text=Hola!+Quiero+saber+de+mi+mascota+{mascota.nombre if mascota else ''}"

    return templates.TemplateResponse(
        request=request,
        name="portal/seguimiento.html",
        context={
            "encontrado": True,
            "turno": turno,
            "mascota": mascota,
            "cliente": cliente,
            "servicio": servicio,
            "fase_label": fase_label,
            "fase_color": fase_color,
            "whatsapp_url": whatsapp_url,
        },
    )
