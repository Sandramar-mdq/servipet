from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.caja import Caja
from app.models.caja_movimiento import CajaMovimiento


def abrir_caja(
    db: Session,
    comercio_id: int,
    usuario_id: int,
    monto_inicial: float,
    notas: str | None = None,
) -> Caja:
    abierta = (
        db.query(Caja)
        .filter(Caja.comercio_id == comercio_id, Caja.estado == "ABIERTA")
        .first()
    )
    if abierta:
        raise HTTPException(status_code=400, detail="Ya hay una caja abierta. Cierrala antes de abrir otra.")

    caja = Caja(
        comercio_id=comercio_id,
        usuario_apertura_id=usuario_id,
        monto_inicial=monto_inicial,
        notas_apertura=notas,
        estado="ABIERTA",
        fecha_apertura=datetime.utcnow(),
    )
    db.add(caja)
    db.commit()
    db.refresh(caja)
    return caja


def registrar_movimiento(
    db: Session,
    caja_id: int,
    tipo: str,
    monto: float,
    descripcion: str,
    venta_id: int | None = None,
) -> CajaMovimiento:
    caja = db.query(Caja).filter(Caja.id == caja_id).first()
    if not caja:
        raise HTTPException(status_code=404, detail="Caja no encontrada")
    if caja.estado != "ABIERTA":
        raise HTTPException(status_code=400, detail="La caja no esta abierta")
    if tipo not in ("INGRESO", "EGRESO"):
        raise HTTPException(status_code=400, detail="Tipo debe ser INGRESO o EGRESO")

    mov = CajaMovimiento(
        caja_id=caja_id,
        tipo=tipo,
        monto=monto,
        descripcion=descripcion,
        venta_id=venta_id,
    )
    db.add(mov)
    db.commit()
    db.refresh(mov)
    return mov


def cerrar_caja(
    db: Session,
    caja_id: int,
    usuario_id: int,
    monto_final_real: float,
    notas: str | None = None,
) -> Caja:
    caja = db.query(Caja).filter(Caja.id == caja_id).first()
    if not caja:
        raise HTTPException(status_code=404, detail="Caja no encontrada")
    if caja.estado != "ABIERTA":
        raise HTTPException(status_code=400, detail="La caja ya esta cerrada")

    ingresos = sum(
        m.monto for m in db.query(CajaMovimiento)
        .filter(CajaMovimiento.caja_id == caja_id, CajaMovimiento.tipo == "INGRESO")
        .all()
    )
    egresos = sum(
        m.monto for m in db.query(CajaMovimiento)
        .filter(CajaMovimiento.caja_id == caja_id, CajaMovimiento.tipo == "EGRESO")
        .all()
    )

    caja.monto_final_esperado = caja.monto_inicial + ingresos - egresos
    caja.monto_final_real = monto_final_real
    caja.usuario_cierre_id = usuario_id
    caja.fecha_cierre = datetime.utcnow()
    caja.notas_cierre = notas
    caja.estado = "CERRADA"

    db.commit()
    db.refresh(caja)
    return caja
