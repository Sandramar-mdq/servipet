from datetime import datetime

from pydantic import BaseModel


class CajaApertura(BaseModel):
    monto_inicial: float
    notas: str | None = None


class CajaCierre(BaseModel):
    monto_final_real: float
    notas: str | None = None


class CajaMovimientoCreate(BaseModel):
    tipo: str
    monto: float
    descripcion: str


class CajaMovimientoResponse(BaseModel):
    id: int
    caja_id: int
    tipo: str
    monto: float
    descripcion: str
    venta_id: int | None = None
    creado_en: datetime

    model_config = {"from_attributes": True}


class CajaResponse(BaseModel):
    id: int
    comercio_id: int
    usuario_apertura_id: int
    usuario_cierre_id: int | None = None
    fecha_apertura: datetime
    fecha_cierre: datetime | None = None
    monto_inicial: float
    monto_final_esperado: float | None = None
    monto_final_real: float | None = None
    estado: str
    notas_apertura: str | None = None
    notas_cierre: str | None = None

    model_config = {"from_attributes": True}


class CajaDetalleResponse(CajaResponse):
    movimientos: list[CajaMovimientoResponse] = []
    total_ingresos: float = 0.0
    total_egresos: float = 0.0
