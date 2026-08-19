from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import require_roles
from app.models.usuario import Usuario
from app.models.venta import Venta
from app.schemas.venta import AnulacionResponse, VentaCreate, VentaResponse
from app.services.ventas import anular_venta, crear_venta

router = APIRouter(prefix="/ventas", tags=["Ventas"])


def _admin(user: Usuario = Depends(require_roles("ADMIN"))):
    return user


@router.get("/", response_model=list[VentaResponse])
def listar_ventas(
    fecha: str | None = None,
    medio_pago: str | None = None,
    db: Session = Depends(get_db),
    user: Usuario = Depends(_admin),
):
    query = db.query(Venta).filter(Venta.comercio_id == user.comercio_id)
    if fecha:
        try:
            f = date.fromisoformat(fecha)
            from datetime import datetime
            inicio = datetime.combine(f, datetime.min.time())
            fin = datetime.combine(f, datetime.max.time())
            query = query.filter(Venta.fecha >= inicio, Venta.fecha <= fin)
        except ValueError:
            pass
    if medio_pago:
        query = query.filter(Venta.medio_pago == medio_pago)
    return query.order_by(Venta.fecha.desc()).all()


@router.post("/", response_model=VentaResponse, status_code=201)
def crear_venta_endpoint(
    data: VentaCreate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(_admin),
):
    return crear_venta(db, data, usuario_id=user.id, comercio_id=user.comercio_id)


@router.get("/{venta_id}", response_model=VentaResponse)
def obtener_venta(
    venta_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(_admin),
):
    venta = db.query(Venta).filter(
        Venta.id == venta_id,
        Venta.comercio_id == user.comercio_id,
    ).first()
    if not venta:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    return venta


@router.post("/{venta_id}/anular", response_model=AnulacionResponse)
def anular_venta_endpoint(
    venta_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(_admin),
):
    venta = anular_venta(db, venta_id)
    return AnulacionResponse(
        venta_id=venta.id,
        estado=venta.estado,
        mensaje="Venta anulada y stock repuesto",
    )
