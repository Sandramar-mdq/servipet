from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.atencion import AtencionHistorial
from app.models.servicio import Servicio
from app.models.turno import Turno
from app.models.venta import Venta
from app.models.venta_detalle import VentaDetalle
from app.models.producto import Producto


def resumen_dia(db: Session, comercio_id: int, fecha: date | None = None) -> dict:
    if fecha is None:
        fecha = date.today()

    inicio = datetime.combine(fecha, datetime.min.time())
    fin = datetime.combine(fecha, datetime.max.time())

    fact_servicios = (
        db.query(func.coalesce(func.sum(AtencionHistorial.monto_cobrado), 0.0))
        .filter(
            AtencionHistorial.fecha >= inicio,
            AtencionHistorial.fecha <= fin,
        )
        .scalar()
    )

    ventas_dia = (
        db.query(Venta)
        .filter(
            Venta.comercio_id == comercio_id,
            Venta.fecha >= inicio,
            Venta.fecha <= fin,
            Venta.estado == "COBRADA",
        )
        .all()
    )

    fact_productos = sum(
        sum(d.subtotal for d in v.detalles if d.tipo == "PRODUCTO")
        for v in ventas_dia
    )
    fact_total_svc = sum(
        sum(d.subtotal for d in v.detalles if d.tipo == "SERVICIO")
        for v in ventas_dia
    )

    cant_atenciones = (
        db.query(func.count(AtencionHistorial.id))
        .filter(
            AtencionHistorial.fecha >= inicio,
            AtencionHistorial.fecha <= fin,
        )
        .scalar()
    )

    return {
        "fecha": fecha.isoformat(),
        "facturacion_servicios": float(fact_servicios) + fact_total_svc,
        "facturacion_productos": float(fact_productos),
        "facturacion_total": float(fact_servicios) + fact_total_svc + fact_productos,
        "cantidad_atenciones": cant_atenciones,
        "cantidad_ventas": len(ventas_dia),
    }


def metricas(db: Session, comercio_id: int, dias: int = 30) -> dict:
    desde = datetime.combine(date.today() - timedelta(days=dias), datetime.min.time())

    servicios_top = (
        db.query(
            Turno.servicio_id,
            Servicio.nombre,
            func.count(Turno.id).label("cnt"),
        )
        .join(Servicio, Servicio.id == Turno.servicio_id)
        .filter(Turno.fecha_hora >= desde)
        .group_by(Turno.servicio_id, Servicio.nombre)
        .order_by(func.count(Turno.id).desc())
        .limit(5)
        .all()
    )

    horas_pico = (
        db.query(
            func.strftime("%H", Turno.fecha_hora).label("hora"),
            func.count(Turno.id).label("cnt"),
        )
        .filter(Turno.fecha_hora >= desde)
        .group_by("hora")
        .order_by(func.count(Turno.id).desc())
        .limit(5)
        .all()
    )

    productos_top = (
        db.query(
            VentaDetalle.producto_id,
            Producto.nombre,
            func.sum(VentaDetalle.cantidad).label("qty"),
            func.sum(VentaDetalle.subtotal).label("total"),
        )
        .join(Producto, Producto.id == VentaDetalle.producto_id)
        .join(Venta, Venta.id == VentaDetalle.venta_id)
        .filter(
            Venta.fecha >= desde,
            Venta.estado == "COBRADA",
            VentaDetalle.tipo == "PRODUCTO",
        )
        .group_by(VentaDetalle.producto_id, Producto.nombre)
        .order_by(func.sum(VentaDetalle.cantidad).desc())
        .limit(5)
        .all()
    )

    return {
        "periodo": f"ultimos {dias} dias",
        "servicios_mas_pedidos": [
            {"servicio_id": s[0], "servicio_nombre": s[1], "cantidad": s[2]}
            for s in servicios_top
        ],
        "horas_pico": [
            {"hora": int(h[0]), "cantidad_turnos": h[1]}
            for h in horas_pico
        ],
        "productos_mas_vendidos": [
            {
                "producto_id": p[0],
                "producto_nombre": p[1],
                "cantidad_vendida": int(p[2]),
                "total_facturado": float(p[3]),
            }
            for p in productos_top
        ],
    }
