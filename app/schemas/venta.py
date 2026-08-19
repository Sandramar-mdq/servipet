from datetime import datetime

from pydantic import BaseModel


class VentaDetalleCreate(BaseModel):
    tipo: str = "PRODUCTO"
    producto_id: int | None = None
    servicio_id: int | None = None
    cantidad: int = 1
    precio_unitario: float


class VentaCreate(BaseModel):
    cliente_id: int | None = None
    medio_pago: str = "efectivo"
    descuento: float = 0.0
    notas: str | None = None
    detalles: list[VentaDetalleCreate]


class VentaDetalleResponse(BaseModel):
    id: int
    tipo: str
    producto_id: int | None = None
    servicio_id: int | None = None
    cantidad: int
    precio_unitario: float
    subtotal: float

    model_config = {"from_attributes": True}


class VentaResponse(BaseModel):
    id: int
    comercio_id: int
    cliente_id: int | None = None
    usuario_id: int
    caja_id: int | None = None
    fecha: datetime
    medio_pago: str
    subtotal: float
    descuento: float
    total: float
    estado: str
    notas: str | None = None
    detalles: list[VentaDetalleResponse] = []

    model_config = {"from_attributes": True}


class AnulacionResponse(BaseModel):
    venta_id: int
    estado: str
    mensaje: str
