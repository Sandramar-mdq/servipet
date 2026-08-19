from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import require_roles
from app.models.caja import Caja
from app.models.caja_movimiento import CajaMovimiento
from app.models.usuario import Usuario
from app.schemas.caja import (
    CajaApertura,
    CajaCierre,
    CajaDetalleResponse,
    CajaMovimientoCreate,
    CajaMovimientoResponse,
    CajaResponse,
)
from app.services.caja import abrir_caja, cerrar_caja, registrar_movimiento

router = APIRouter(prefix="/caja", tags=["Caja"])


def _admin(user: Usuario = Depends(require_roles("ADMIN"))):
    return user


@router.post("/abrir", response_model=CajaResponse, status_code=201)
def abrir_caja_endpoint(
    data: CajaApertura,
    db: Session = Depends(get_db),
    user: Usuario = Depends(_admin),
):
    return abrir_caja(db, user.comercio_id, user.id, data.monto_inicial, data.notas)


@router.get("/actual", response_model=CajaResponse)
def caja_actual(
    db: Session = Depends(get_db),
    user: Usuario = Depends(_admin),
):
    caja = (
        db.query(Caja)
        .filter(Caja.comercio_id == user.comercio_id, Caja.estado == "ABIERTA")
        .first()
    )
    if not caja:
        raise HTTPException(status_code=404, detail="No hay caja abierta")
    return caja


@router.post("/movimiento", response_model=CajaMovimientoResponse, status_code=201)
def agregar_movimiento(
    data: CajaMovimientoCreate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(_admin),
):
    caja = (
        db.query(Caja)
        .filter(Caja.comercio_id == user.comercio_id, Caja.estado == "ABIERTA")
        .first()
    )
    if not caja:
        raise HTTPException(status_code=404, detail="No hay caja abierta")
    return registrar_movimiento(db, caja.id, data.tipo, data.monto, data.descripcion)


@router.post("/cerrar", response_model=CajaResponse)
def cerrar_caja_endpoint(
    data: CajaCierre,
    db: Session = Depends(get_db),
    user: Usuario = Depends(_admin),
):
    caja = (
        db.query(Caja)
        .filter(Caja.comercio_id == user.comercio_id, Caja.estado == "ABIERTA")
        .first()
    )
    if not caja:
        raise HTTPException(status_code=404, detail="No hay caja abierta")
    return cerrar_caja(db, caja.id, user.id, data.monto_final_real, data.notas)


@router.get("/historial", response_model=list[CajaResponse])
def historial_cajas(
    db: Session = Depends(get_db),
    user: Usuario = Depends(_admin),
):
    return (
        db.query(Caja)
        .filter(Caja.comercio_id == user.comercio_id)
        .order_by(Caja.fecha_apertura.desc())
        .all()
    )


@router.get("/{caja_id}", response_model=CajaDetalleResponse)
def detalle_caja(
    caja_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(_admin),
):
    caja = db.query(Caja).filter(
        Caja.id == caja_id,
        Caja.comercio_id == user.comercio_id,
    ).first()
    if not caja:
        raise HTTPException(status_code=404, detail="Caja no encontrada")

    movimientos = (
        db.query(CajaMovimiento)
        .filter(CajaMovimiento.caja_id == caja_id)
        .order_by(CajaMovimiento.creado_en.asc())
        .all()
    )

    total_ingresos = sum(m.monto for m in movimientos if m.tipo == "INGRESO")
    total_egresos = sum(m.monto for m in movimientos if m.tipo == "EGRESO")

    return CajaDetalleResponse(
        id=caja.id,
        comercio_id=caja.comercio_id,
        usuario_apertura_id=caja.usuario_apertura_id,
        usuario_cierre_id=caja.usuario_cierre_id,
        fecha_apertura=caja.fecha_apertura,
        fecha_cierre=caja.fecha_cierre,
        monto_inicial=caja.monto_inicial,
        monto_final_esperado=caja.monto_final_esperado,
        monto_final_real=caja.monto_final_real,
        estado=caja.estado,
        notas_apertura=caja.notas_apertura,
        notas_cierre=caja.notas_cierre,
        movimientos=[CajaMovimientoResponse.model_validate(m) for m in movimientos],
        total_ingresos=total_ingresos,
        total_egresos=total_egresos,
    )
