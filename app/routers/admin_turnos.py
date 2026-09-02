from datetime import date, datetime, time

from fastapi import APIRouter, BackgroundTasks, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.templating import get_templates
from app.database import get_db
from app.models.atencion import AtencionHistorial
from app.models.turno import Turno
from app.services import notification_service

router = APIRouter(prefix="/page", tags=["Admin Turnos"])
templates = get_templates()

ESTADOS = ["PENDIENTE", "CONFIRMADO", "CANCELADO", "CANCELADO_TARDIO", "FINALIZADO"]
FASES = ["ESPERA", "BAÑO", "CORTE", "LISTO"]
MEDIOS_PAGO = ["efectivo", "transferencia", "debito", "credito", "qr"]


def _fecha_filtro(fecha: str | None) -> str:
    if not fecha:
        return date.today().isoformat()
    try:
        date.fromisoformat(fecha)
        return fecha
    except ValueError:
        return date.today().isoformat()


@router.get("/turnos", response_class=HTMLResponse)
def agenda_turnos(
    request: Request,
    estado: str | None = None,
    fecha: str | None = None,
    db: Session = Depends(get_db),
):
    fecha_seleccionada = _fecha_filtro(fecha)
    fecha_dt = date.fromisoformat(fecha_seleccionada)
    inicio_dia = datetime.combine(fecha_dt, time.min)
    fin_dia = datetime.combine(fecha_dt, time.max)

    query = db.query(Turno).filter(
        Turno.fecha_hora >= inicio_dia,
        Turno.fecha_hora <= fin_dia,
    )
    estado_seleccionado = ""
    if estado and estado != "todos" and estado in ESTADOS:
        query = query.filter(Turno.estado == estado)
        estado_seleccionado = estado
    turnos = query.order_by(Turno.fecha_hora.asc()).all()

    return templates.TemplateResponse("turnos/listar.html", {
        "request": request,
        "turnos": turnos,
        "estados": ESTADOS,
        "fecha_seleccionada": fecha_seleccionada,
        "estado_seleccionado": estado_seleccionado,
        "success": request.query_params.get("success"),
        "error": request.query_params.get("error"),
    })


@router.post("/turnos/{turno_id}/cambiar-estado")
def cambiar_estado_turno(
    turno_id: int,
    background_tasks: BackgroundTasks,
    estado: str = Form(...),
    fecha: str | None = Form(None),
    estado_filtro: str | None = Form(None),
    db: Session = Depends(get_db),
):
    turno = db.query(Turno).filter(Turno.id == turno_id).first()
    if not turno:
        return RedirectResponse("/page/turnos?error=Turno inexistente", status_code=303)
    if estado not in ESTADOS:
        return RedirectResponse("/page/turnos?error=Estado invalido", status_code=303)
    if estado == "FINALIZADO" and turno.estado in ("CANCELADO", "CANCELADO_TARDIO"):
        return RedirectResponse("/page/turnos?error=No se puede finalizar un turno cancelado", status_code=303)

    turno.estado = estado
    db.commit()
    background_tasks.add_task(notification_service.enqueue_cambio_estado, turno.id, estado)
    qs = _query_params(fecha, estado_filtro)
    return RedirectResponse(f"/page/turnos?{qs}success=Estado actualizado a {estado}", status_code=303)


@router.post("/turnos/{turno_id}/completar")
def completar_turno(
    turno_id: int,
    cliente_id: int = Form(...),
    mascota_id: int = Form(...),
    servicio_id: int = Form(...),
    monto_cobrado: float = Form(0.0),
    medio_pago: str = Form("efectivo"),
    observaciones: str | None = Form(None),
    fecha: str | None = Form(None),
    estado_filtro: str | None = Form(None),
    db: Session = Depends(get_db),
):
    turno = db.query(Turno).filter(Turno.id == turno_id).first()
    if not turno:
        return RedirectResponse("/page/turnos?error=Turno inexistente", status_code=303)
    if turno.estado == "FINALIZADO":
        return RedirectResponse("/page/turnos?error=El turno ya fue finalizado", status_code=303)
    if turno.estado in ("CANCELADO", "CANCELADO_TARDIO"):
        return RedirectResponse("/page/turnos?error=No se puede completar un turno cancelado", status_code=303)
    if (turno.cliente_id, turno.mascota_id, turno.servicio_id) != (cliente_id, mascota_id, servicio_id):
        return RedirectResponse("/page/turnos?error=Datos del turno inconsistentes", status_code=303)
    if medio_pago not in MEDIOS_PAGO:
        medio_pago = "efectivo"

    atencion = AtencionHistorial(
        mascota_id=turno.mascota_id,
        servicio_id=turno.servicio_id,
        turno_id=turno.id,
        fecha=turno.fecha_hora,
        observaciones=observaciones or None,
        monto_cobrado=monto_cobrado,
        medio_pago=medio_pago,
    )
    turno.estado = "FINALIZADO"
    db.add(atencion)
    db.commit()

    qs = _query_params(fecha, estado_filtro)
    return RedirectResponse(f"/page/turnos?{qs}success=Atencion registrada y turno finalizado", status_code=303)


@router.post("/turnos/{turno_id}/fase")
def cambiar_fase_turno(
    turno_id: int,
    background_tasks: BackgroundTasks,
    fase: str = Form(...),
    fecha: str | None = Form(None),
    estado_filtro: str | None = Form(None),
    db: Session = Depends(get_db),
):
    turno = db.query(Turno).filter(Turno.id == turno_id).first()
    if not turno:
        return RedirectResponse("/page/turnos?error=Turno inexistente", status_code=303)
    fase_norm = (fase or "").upper()
    if fase_norm not in FASES:
        return RedirectResponse("/page/turnos?error=Fase invalida", status_code=303)

    turno.fase = fase_norm
    db.commit()
    if fase_norm == "LISTO":
        background_tasks.add_task(notification_service.enqueue_pet_ready, turno.id)

    qs = _query_params(fecha, estado_filtro)
    return RedirectResponse(f"/page/turnos?{qs}success=Fase actualizada a {fase_norm}", status_code=303)


def _query_params(fecha: str | None, estado_filtro: str | None) -> str:
    params = []
    if fecha:
        params.append(f"fecha={fecha}")
    if estado_filtro and estado_filtro != "todos":
        params.append(f"estado={estado_filtro}")
    return "&".join(params) + ("&" if params else "")
