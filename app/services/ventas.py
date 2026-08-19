from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.producto import Producto
from app.models.servicio import Servicio
from app.models.venta import Venta
from app.models.venta_detalle import VentaDetalle
from app.schemas.venta import VentaCreate


def crear_venta(db: Session, data: VentaCreate, usuario_id: int, comercio_id: int) -> Venta:
    if not data.detalles:
        raise HTTPException(status_code=400, detail="La venta debe tener al menos un item")

    venta = Venta(
        comercio_id=comercio_id,
        cliente_id=data.cliente_id,
        usuario_id=usuario_id,
        medio_pago=data.medio_pago,
        descuento=data.descuento,
        notas=data.notas,
        estado="COBRADA",
    )
    db.add(venta)
    db.flush()

    subtotal_total = 0.0

    for det in data.detalles:
        if det.tipo == "PRODUCTO":
            if not det.producto_id:
                raise HTTPException(status_code=400, detail="producto_id requerido para items de tipo PRODUCTO")
            producto = db.query(Producto).filter(Producto.id == det.producto_id).first()
            if not producto:
                raise HTTPException(status_code=404, detail=f"Producto {det.producto_id} no encontrado")
            if producto.stock_actual < det.cantidad:
                raise HTTPException(status_code=400, detail=f"Stock insuficiente para '{producto.nombre}': disponible {producto.stock_actual}, solicitado {det.cantidad}")
            producto.stock_actual -= det.cantidad
            subtotal_item = det.precio_unitario * det.cantidad
        elif det.tipo == "SERVICIO":
            if not det.servicio_id:
                raise HTTPException(status_code=400, detail="servicio_id requerido para items de tipo SERVICIO")
            servicio = db.query(Servicio).filter(Servicio.id == det.servicio_id).first()
            if not servicio:
                raise HTTPException(status_code=404, detail=f"Servicio {det.servicio_id} no encontrado")
            subtotal_item = det.precio_unitario * det.cantidad
        else:
            raise HTTPException(status_code=400, detail=f"Tipo de item invalido: {det.tipo}")

        detalle = VentaDetalle(
            venta_id=venta.id,
            tipo=det.tipo,
            producto_id=det.producto_id,
            servicio_id=det.servicio_id,
            cantidad=det.cantidad,
            precio_unitario=det.precio_unitario,
            subtotal=subtotal_item,
        )
        db.add(detalle)
        subtotal_total += subtotal_item

    venta.subtotal = subtotal_total
    venta.total = subtotal_total - data.descuento

    db.commit()
    db.refresh(venta)
    return venta


def anular_venta(db: Session, venta_id: int) -> Venta:
    venta = db.query(Venta).filter(Venta.id == venta_id).first()
    if not venta:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    if venta.estado == "ANULADA":
        raise HTTPException(status_code=400, detail="La venta ya esta anulada")

    for det in venta.detalles:
        if det.tipo == "PRODUCTO" and det.producto_id:
            producto = db.query(Producto).filter(Producto.id == det.producto_id).first()
            if producto:
                producto.stock_actual += det.cantidad

    venta.estado = "ANULADA"
    db.commit()
    db.refresh(venta)
    return venta
