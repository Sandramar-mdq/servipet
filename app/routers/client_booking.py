from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_client
from app.models.atencion import AtencionHistorial
from app.models.cliente import Cliente
from app.models.comercio import Comercio
from app.models.mascota import Mascota
from app.models.servicio import Servicio
from app.models.turno import Turno
from app.services.notifier import notificar_reserva_creada

API_ROUTER = APIRouter(prefix="/api/client", tags=["Cliente Booking API"])
BOOKING_ROUTER = APIRouter(prefix="/cliente", tags=["Cliente Booking"])
templates = Jinja2Templates(directory="app/templates")

APERTURA_DEFECTO = "09:00"
CIERRE_DEFECTO = "18:00"
SLOT_MINUTOS_DEFECTO = 30


def _parse_hora(hora: str) -> time:
    h, m = hora.split(":")
    return time(int(h), int(m))


def _es_rango_libre(start: datetime, end: datetime, ocupados: list[tuple[datetime, datetime]]) -> bool:
    for b_start, b_end in ocupados:
        if start < b_end and end > b_start:
            return False
    return True


def _slots_disponibles(db: Session, fecha: date, servicio: Servicio) -> list[str]:
    comercio = db.query(Comercio).order_by(Comercio.id.asc()).first()
    apertura = _parse_hora(comercio.hora_apertura if comercio and comercio.hora_apertura else APERTURA_DEFECTO)
    cierre = _parse_hora(comercio.hora_cierre if comercio and comercio.hora_cierre else CIERRE_DEFECTO)
    paso = (comercio.slot_minutos if comercio and comercio.slot_minutos else SLOT_MINUTOS_DEFECTO) or 30
    duracion = servicio.duracion_minutos or 30

    inicio_dia = datetime.combine(fecha, time.min)
    fin_dia = datetime.combine(fecha, time.max)

    ocupados: list[tuple[datetime, datetime]] = []
    turnos = (
        db.query(Turno)
        .filter(
            Turno.fecha_hora >= inicio_dia,
            Turno.fecha_hora <= fin_dia,
            Turno.estado != "Cancelado",
        )
        .all()
    )
    for t in turnos:
        dur = t.duracion_minutos or 30
        ocupados.append((t.fecha_hora, t.fecha_hora + timedelta(minutes=dur)))

    atenciones = (
        db.query(AtencionHistorial)
        .filter(AtencionHistorial.fecha >= inicio_dia, AtencionHistorial.fecha <= fin_dia)
        .all()
    )
    for a in atenciones:
        dur = a.servicio.duracion_minutos if a.servicio else 30
        ocupados.append((a.fecha, a.fecha + timedelta(minutes=dur)))

    ahora = datetime.now()
    slots: list[str] = []
    t = apertura
    while _hora_mas(t, duracion) <= cierre:
        start = datetime.combine(fecha, t)
        end = start + timedelta(minutes=duracion)
        if fecha != date.today() or end > ahora:
            if _es_rango_libre(start, end, ocupados):
                slots.append(t.strftime("%H:%M"))
        t = _hora_mas(t, paso)
    return slots


def _hora_mas(h: time, minutos: int) -> time:
    total = h.hour * 60 + h.minute + minutos
    return time(total // 60, total % 60)


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
    slots = _slots_disponibles(db, fecha_dt, servicio)
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
        hora_dt = _parse_hora(hora)
    except ValueError:
        return RedirectResponse("/cliente/reservar?error=Fecha u horario invalido", status_code=303)

    if fecha_dt < date.today():
        return RedirectResponse("/cliente/reservar?error=La fecha elegida ya paso", status_code=303)

    slots = _slots_disponibles(db, fecha_dt, servicio)
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
