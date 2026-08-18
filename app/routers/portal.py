from datetime import date, datetime, time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.atencion import AtencionHistorial
from app.models.comercio import Comercio
from app.models.mascota import Mascota
from app.models.servicio import Servicio
from app.models.turno import Turno
from app.models.usuario import Usuario
from app.schemas.portal import (
    PortalAtencionResponse,
    PortalCancelarResponse,
    PortalDisponibilidadResponse,
    PortalMascotaCreate,
    PortalMascotaResponse,
    PortalPerfilResponse,
    PortalReservarRequest,
    PortalServicioResponse,
    PortalTurnoResponse,
)
from app.services.notifier import notificar_reserva_creada
from app.services.turnos import cancelar_turno, calcular_slots_disponibles, crear_turno

router = APIRouter(prefix="/portal", tags=["Portal Cliente"])


def _require_cliente(user: Usuario = Depends(get_current_user)):
    if user.rol not in ("CLIENTE", "ADMIN"):
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    if not user.cliente_profile:
        raise HTTPException(status_code=404, detail="No se encontro perfil de cliente vinculado")
    return user


def _turno_response(turno: Turno) -> PortalTurnoResponse:
    return PortalTurnoResponse(
        id=turno.id,
        mascota_id=turno.mascota_id,
        servicio_id=turno.servicio_id,
        servicio_nombre=turno.servicio.nombre if turno.servicio else "",
        fecha_hora=turno.fecha_hora.isoformat(),
        duracion_minutos=turno.duracion_minutos,
        estado=turno.estado,
        observaciones=turno.observaciones,
    )


def _atencion_response(atencion: AtencionHistorial) -> PortalAtencionResponse:
    return PortalAtencionResponse(
        id=atencion.id,
        servicio_nombre=atencion.servicio.nombre if atencion.servicio else "",
        fecha=atencion.fecha.isoformat(),
        observaciones=atencion.observaciones,
        monto_cobrado=atencion.monto_cobrado,
    )


# --- Mi Perfil y Mascotas ---

@router.get("/me", response_model=PortalPerfilResponse)
def mi_perfil(usuario: Usuario = Depends(_require_cliente)):
    cliente = usuario.cliente_profile
    mascotas = (
        [m for m in cliente.mascotas if m.activo]
        if cliente.mascotas
        else []
    )
    return PortalPerfilResponse(
        id=cliente.id,
        nombre=cliente.nombre,
        telefono=cliente.telefono,
        email=cliente.email,
        mascotas=[PortalMascotaResponse.model_validate(m) for m in mascotas],
    )


@router.get("/mascotas", response_model=list[PortalMascotaResponse])
def listar_mascotas(usuario: Usuario = Depends(_require_cliente)):
    cliente = usuario.cliente_profile
    mascotas = [m for m in cliente.mascotas if m.activo] if cliente.mascotas else []
    return mascotas


@router.post("/mascotas", response_model=PortalMascotaResponse, status_code=201)
def crear_mascota(
    data: PortalMascotaCreate,
    usuario: Usuario = Depends(_require_cliente),
    db: Session = Depends(get_db),
):
    cliente = usuario.cliente_profile
    mascota = Mascota(
        cliente_id=cliente.id,
        nombre=data.nombre,
        especie=data.especie,
        raza=data.raza,
        peso=data.peso,
        edad=data.edad,
        sexo=data.sexo,
        observaciones=data.observaciones,
        alergias=data.alergias,
        activo=True,
    )
    db.add(mascota)
    db.commit()
    db.refresh(mascota)
    return mascota


@router.get("/mascotas/{mascota_id}/historial", response_model=list[PortalAtencionResponse])
def historial_mascota(
    mascota_id: int,
    usuario: Usuario = Depends(_require_cliente),
    db: Session = Depends(get_db),
):
    cliente = usuario.cliente_profile
    mascota = (
        db.query(Mascota)
        .filter(Mascota.id == mascota_id, Mascota.cliente_id == cliente.id, Mascota.activo == True)
        .first()
    )
    if not mascota:
        raise HTTPException(status_code=404, detail="Mascota no encontrada")
    atenciones = (
        db.query(AtencionHistorial)
        .filter(AtencionHistorial.mascota_id == mascota_id)
        .order_by(AtencionHistorial.fecha.desc())
        .all()
    )
    return [_atencion_response(a) for a in atenciones]


# --- Servicios y Disponibilidad ---

@router.get("/servicios", response_model=list[PortalServicioResponse])
def listar_servicios(
    usuario: Usuario = Depends(_require_cliente),
    db: Session = Depends(get_db),
):
    cliente = usuario.cliente_profile
    comercio = db.query(Comercio).filter(Comercio.id == cliente.comercio_id).first()
    if not comercio:
        return []
    servicios = db.query(Servicio).order_by(Servicio.nombre.asc()).all()
    return servicios


@router.get("/disponibilidad", response_model=PortalDisponibilidadResponse)
def disponibilidad(
    fecha: str,
    servicio_id: int,
    usuario: Usuario = Depends(_require_cliente),
    db: Session = Depends(get_db),
):
    try:
        fecha_dt = date.fromisoformat(fecha)
    except ValueError:
        raise HTTPException(status_code=400, detail="Fecha invalida (usar YYYY-MM-DD)")

    servicio = db.query(Servicio).filter(Servicio.id == servicio_id).first()
    if not servicio:
        raise HTTPException(status_code=404, detail="Servicio inexistente")

    cliente = usuario.cliente_profile
    comercio = db.query(Comercio).filter(Comercio.id == cliente.comercio_id).first()

    slots = calcular_slots_disponibles(db, comercio, fecha_dt, servicio)
    return PortalDisponibilidadResponse(
        fecha=fecha,
        servicio_id=servicio.id,
        servicio_nombre=servicio.nombre,
        duracion_minutos=servicio.duracion_minutos or 30,
        slots=slots,
    )


# --- Reserva ---

@router.post("/reservar", response_model=PortalTurnoResponse, status_code=201)
def reservar_turno(
    data: PortalReservarRequest,
    usuario: Usuario = Depends(_require_cliente),
    db: Session = Depends(get_db),
):
    cliente = usuario.cliente_profile

    try:
        fecha_dt = date.fromisoformat(data.fecha)
        h, m = data.hora.strip().split(":")
        hora_dt = time(int(h), int(m))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Fecha u horario invalido")

    if fecha_dt < date.today():
        raise HTTPException(status_code=400, detail="La fecha elegida ya paso")

    fecha_hora = datetime.combine(fecha_dt, hora_dt)
    turno = crear_turno(
        db,
        cliente_id=cliente.id,
        mascota_id=data.mascota_id,
        servicio_id=data.servicio_id,
        fecha_hora=fecha_hora,
        observaciones=data.observaciones,
    )

    db.refresh(turno)
    notificar_reserva_creada(turno)
    return _turno_response(turno)


# --- Turnos del cliente ---

@router.get("/turnos", response_model=list[PortalTurnoResponse])
def listar_turnos(
    usuario: Usuario = Depends(_require_cliente),
    db: Session = Depends(get_db),
):
    cliente = usuario.cliente_profile
    turnos = (
        db.query(Turno)
        .filter(Turno.cliente_id == cliente.id)
        .order_by(Turno.fecha_hora.desc())
        .all()
    )
    return [_turno_response(t) for t in turnos]


# --- Cancelación con política ---

@router.post("/turnos/{turno_id}/cancelar", response_model=PortalCancelarResponse)
def cancelar(
    turno_id: int,
    usuario: Usuario = Depends(_require_cliente),
    db: Session = Depends(get_db),
):
    cliente = usuario.cliente_profile
    resultado = cancelar_turno(db, turno_id=turno_id, cliente_id=cliente.id)
    return PortalCancelarResponse(**resultado)
