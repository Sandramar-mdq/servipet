from datetime import date, datetime, time, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.atencion import AtencionHistorial
from app.models.cliente import Cliente
from app.models.comercio import Comercio
from app.models.mascota import Mascota
from app.models.servicio import Servicio
from app.models.turno import Turno

APERTURA_DEFECTO = "09:00"
CIERRE_DEFECTO = "18:00"
SLOT_MINUTOS_DEFECTO = 30


def parse_hora(hora: str) -> time:
    h, m = hora.strip().split(":")
    return time(int(h), int(m))


def hora_mas(h: time, minutos: int) -> time:
    total = h.hour * 60 + h.minute + minutos
    return time(total // 60, total % 60)


def _es_rango_libre(start: datetime, end: datetime, ocupados: list[tuple[datetime, datetime]]) -> bool:
    for b_start, b_end in ocupados:
        if start < b_end and end > b_start:
            return False
    return True


def calcular_slots_disponibles(
    db: Session,
    comercio: Comercio | None,
    fecha: date,
    servicio: Servicio,
    comercio_id: int | None = None,
) -> list[str]:
    """Calcula slots libres para `fecha`/`servicio`.

    Si se pasa `comercio_id`, solo se consideran como bloqueantes los
    turnos/atenciones de ese tenant (aislamiento multitenant; sin el
    parametro se conserva el comportamiento historico global).
    """
    apertura = parse_hora(comercio.hora_apertura if comercio and comercio.hora_apertura else APERTURA_DEFECTO)
    cierre = parse_hora(comercio.hora_cierre if comercio and comercio.hora_cierre else CIERRE_DEFECTO)
    paso = (comercio.slot_minutos if comercio and comercio.slot_minutos else SLOT_MINUTOS_DEFECTO) or 30
    duracion = servicio.duracion_minutos or 30

    inicio_dia = datetime.combine(fecha, time.min)
    fin_dia = datetime.combine(fecha, time.max)

    ocupados: list[tuple[datetime, datetime]] = []
    turnos_query = db.query(Turno).filter(
        Turno.fecha_hora >= inicio_dia,
        Turno.fecha_hora <= fin_dia,
        Turno.estado.notin_(["CANCELADO", "CANCELADO_TARDIO"]),
    )
    if comercio_id is not None:
        turnos_query = (
            turnos_query.join(Cliente, Turno.cliente_id == Cliente.id)
            .filter(Cliente.comercio_id == comercio_id)
        )
    for t in turnos_query.all():
        dur = t.duracion_minutos or 30
        ocupados.append((t.fecha_hora, t.fecha_hora + timedelta(minutes=dur)))

    atenciones_query = db.query(AtencionHistorial).filter(
        AtencionHistorial.fecha >= inicio_dia, AtencionHistorial.fecha <= fin_dia
    )
    if comercio_id is not None:
        atenciones_query = (
            atenciones_query.join(Mascota, AtencionHistorial.mascota_id == Mascota.id)
            .join(Cliente, Mascota.cliente_id == Cliente.id)
            .filter(Cliente.comercio_id == comercio_id)
        )
    atenciones = atenciones_query.all()
    for a in atenciones:
        dur = a.servicio.duracion_minutos if a.servicio else 30
        ocupados.append((a.fecha, a.fecha + timedelta(minutes=dur)))

    ahora = datetime.now()
    slots: list[str] = []
    t = apertura
    while hora_mas(t, duracion) <= cierre:
        start = datetime.combine(fecha, t)
        end = start + timedelta(minutes=duracion)
        if fecha != date.today() or end > ahora:
            if _es_rango_libre(start, end, ocupados):
                slots.append(t.strftime("%H:%M"))
        t = hora_mas(t, paso)
    return slots


def crear_turno(
    db: Session,
    *,
    cliente_id: int,
    mascota_id: int,
    servicio_id: int,
    fecha_hora: datetime,
    observaciones: str | None = None,
) -> Turno:
    mascota = (
        db.query(Mascota)
        .filter(Mascota.id == mascota_id, Mascota.cliente_id == cliente_id, Mascota.activo == True)
        .first()
    )
    if not mascota:
        raise HTTPException(status_code=400, detail="Mascota invalida o no pertenece al cliente")

    servicio = db.query(Servicio).filter(Servicio.id == servicio_id).first()
    if not servicio:
        raise HTTPException(status_code=400, detail="Servicio inexistente")

    comercio = db.query(Comercio).filter(Comercio.id == mascota.cliente.comercio_id).first()
    if not comercio:
        raise HTTPException(status_code=400, detail="Comercio no encontrado")

    if not comercio.permite_autoreserva_publica:
        raise HTTPException(status_code=403, detail="Este comercio no permite autoreserva publica")

    fecha_solo = fecha_hora.date()
    hora_str = fecha_hora.strftime("%H:%M")
    slots = calcular_slots_disponibles(db, comercio, fecha_solo, servicio)
    if hora_str not in slots:
        raise HTTPException(status_code=409, detail="Ese horario ya no esta disponible")

    turno = Turno(
        cliente_id=cliente_id,
        mascota_id=mascota.id,
        servicio_id=servicio.id,
        fecha_hora=fecha_hora,
        duracion_minutos=servicio.duracion_minutos or 30,
        estado="PENDIENTE",
        observaciones=observaciones or None,
    )
    db.add(turno)
    db.commit()
    db.refresh(turno)
    return turno


def cancelar_turno(
    db: Session,
    *,
    turno_id: int,
    cliente_id: int,
) -> dict:
    turno = (
        db.query(Turno)
        .filter(Turno.id == turno_id)
        .first()
    )
    if not turno:
        raise HTTPException(status_code=404, detail="Turno no encontrado")

    if turno.cliente_id != cliente_id:
        raise HTTPException(status_code=403, detail="El turno no pertenece a este cliente")

    if turno.estado not in ("PENDIENTE", "CONFIRMADO"):
        raise HTTPException(status_code=400, detail="No se puede cancelar un turno en estado %s" % turno.estado)

    ahora = datetime.utcnow()
    horas_restantes = (turno.fecha_hora - ahora).total_seconds() / 3600

    comercio = None
    if turno.mascota and turno.mascota.cliente:
        comercio = db.query(Comercio).filter(Comercio.id == turno.mascota.cliente.comercio_id).first()

    limite = getattr(comercio, "horas_limite_cancelacion", 24) if comercio else 24
    recargo = getattr(comercio, "porcentaje_recargo_tardio", 0.0) if comercio else 0.0

    if horas_restantes >= limite:
        turno.estado = "CANCELADO"
        penalizacion = 0.0
        mensaje = "Turno cancelado exitosamente sin penalizacion"
    else:
        turno.estado = "CANCELADO_TARDIO"
        penalizacion = recargo
        mensaje = (
            "Turno cancelado con penalizacion: %.1f%% de recargo "
            "(limite: %d horas de anticipacion, restantes: %.1f horas)"
            % (recargo, limite, horas_restantes)
        )

    db.commit()
    return {
        "turno_id": turno.id,
        "estado": turno.estado,
        "horas_restantes": round(horas_restantes, 1),
        "penalizacion_porcentaje": penalizacion,
        "mensaje": mensaje,
    }
