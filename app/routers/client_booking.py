from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_client
from app.models.atencion import AtencionHistorial
from app.models.cliente import Cliente
from app.models.mascota import Mascota
from app.models.servicio import Servicio
from app.models.turno import Turno
from app.services.notifier import notificar_reserva_creada
from app.services.turnos import calcular_slots_disponibles, parse_hora

API_ROUTER = APIRouter(prefix="/api/client", tags=["Cliente Booking API"])
BOOKING_ROUTER = APIRouter(prefix="/cliente", tags=["Cliente Booking"])
templates = Jinja2Templates(directory="app/templates")


@API_ROUTER.get("/slots-disponibles")
def slots_disponibles(
    fecha: str,
    servicio_id: int,
    request: Request,
    cliente: Cliente = Depends(get_current_client),
    db: Session = Depends(get_db),
):
    try:
        fecha_dt = date.fromisoformat(fecha)
    except ValueError:
        return {"fecha": fecha, "servicio_id": servicio_id, "slots": [], "error": "Fecha invalida"}
    servicio = db.query(Servicio).filter(Servicio.id == servicio_id).first()
    if not servicio:
        return {"fecha": fecha, "servicio_id": servicio_id, "slots": [], "error": "Servicio inexistente"}
    from app.models.comercio import Comercio
    comercio = db.query(Comercio).order_by(Comercio.id.asc()).first()
    slots = calcular_slots_disponibles(db, comercio, fecha_dt, servicio)
    return {
        "fecha": fecha,
        "servicio_id": servicio.id,
        "servicio_nombre": servicio.nombre,
        "duracion_minutos": servicio.duracion_minutos or 30,
        "slots": slots,
    }


@BOOKING_ROUTER.get("/reservar", response_class=HTMLResponse)
def reservar_form(
    request: Request,
    cliente: Cliente = Depends(get_current_client),
    db: Session = Depends(get_db),
):
    mascotas = (
        db.query(Mascota)
        .filter(Mascota.cliente_id == cliente.id, Mascota.activo == True)
        .order_by(Mascota.nombre.asc())
        .all()
    )
    servicios = db.query(Servicio).order_by(Servicio.nombre.asc()).all()
    return templates.TemplateResponse("cliente/reservar.html", {
        "request": request,
        "cliente": cliente,
        "mascotas": mascotas,
        "servicios": servicios,
        "today": date.today().isoformat(),
        "error": request.query_params.get("error"),
    })


@BOOKING_ROUTER.post("/reservar")
def reservar_submit(
    request: Request,
    mascota_id: int = Form(...),
    servicio_id: int = Form(...),
    fecha: str = Form(...),
    hora: str = Form(...),
    observaciones: str | None = Form(None),
    cliente: Cliente = Depends(get_current_client),
    db: Session = Depends(get_db),
):
    mascota = (
        db.query(Mascota)
        .filter(Mascota.id == mascota_id, Mascota.cliente_id == cliente.id, Mascota.activo == True)
        .first()
    )
    servicio = db.query(Servicio).filter(Servicio.id == servicio_id).first()
    if not mascota:
        return RedirectResponse("/cliente/reservar?error=Mascota invalida", status_code=303)
    if not servicio:
        return RedirectResponse("/cliente/reservar?error=Servicio invalido", status_code=303)

    try:
        fecha_dt = date.fromisoformat(fecha)
        hora_dt = parse_hora(hora)
    except ValueError:
        return RedirectResponse("/cliente/reservar?error=Fecha u horario invalido", status_code=303)

    if fecha_dt < date.today():
        return RedirectResponse("/cliente/reservar?error=La fecha elegida ya paso", status_code=303)

    from app.models.comercio import Comercio
    comercio = db.query(Comercio).order_by(Comercio.id.asc()).first()
    slots = calcular_slots_disponibles(db, comercio, fecha_dt, servicio)
    if hora not in slots:
        return RedirectResponse(
            "/cliente/reservar?error=Ese horario ya no esta disponible, elegi otro",
            status_code=303,
        )

    turno = Turno(
        cliente_id=cliente.id,
        mascota_id=mascota.id,
        servicio_id=servicio.id,
        fecha_hora=datetime.combine(fecha_dt, hora_dt),
        duracion_minutos=servicio.duracion_minutos or 30,
        estado="Pendiente",
        observaciones=observaciones or None,
    )
    db.add(turno)
    db.commit()
    db.refresh(turno)
    notificar_reserva_creada(turno)
    return RedirectResponse(f"/cliente/turnos/{turno.id}", status_code=303)


@BOOKING_ROUTER.get("/turnos", response_class=HTMLResponse)
def listar_turnos(
    request: Request,
    cliente: Cliente = Depends(get_current_client),
    db: Session = Depends(get_db),
):
    turnos = (
        db.query(Turno)
        .filter(Turno.cliente_id == cliente.id)
        .order_by(Turno.fecha_hora.desc())
        .all()
    )
    ahora = datetime.now()
    proximos = [t for t in turnos if t.fecha_hora >= ahora and t.estado in ("Pendiente", "Confirmado")]
    proximos_ids = {t.id for t in proximos}
    anteriores = [t for t in turnos if t.id not in proximos_ids]
    proximos.sort(key=lambda t: t.fecha_hora)
    anteriores.sort(key=lambda t: t.fecha_hora, reverse=True)
    return templates.TemplateResponse("cliente/turnos.html", {
        "request": request,
        "cliente": cliente,
        "proximos": proximos,
        "anteriores": anteriores,
        "success": request.query_params.get("success"),
    })


@BOOKING_ROUTER.get("/turnos/{turno_id}", response_class=HTMLResponse)
def detalle_turno(
    turno_id: int,
    request: Request,
    cliente: Cliente = Depends(get_current_client),
    db: Session = Depends(get_db),
):
    turno = (
        db.query(Turno)
        .filter(Turno.id == turno_id, Turno.cliente_id == cliente.id)
        .first()
    )
    if not turno:
        return RedirectResponse("/cliente/turnos", status_code=303)
    return templates.TemplateResponse("cliente/turno_confirmado.html", {
        "request": request,
        "cliente": cliente,
        "turno": turno,
    })
