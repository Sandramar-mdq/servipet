from datetime import datetime

from pydantic import BaseModel


class AtencionCreate(BaseModel):
    mascota_id: int
    servicio_id: int
    fecha: datetime | None = None
    observaciones: str | None = None
    monto_cobrado: float = 0.0
    medio_pago: str = "efectivo"
    foto_antes_webp: str | None = None
    foto_despues_webp: str | None = None


class AtencionUpdate(BaseModel):
    servicio_id: int | None = None
    fecha: datetime | None = None
    observaciones: str | None = None
    monto_cobrado: float | None = None
    medio_pago: str | None = None
    foto_antes_webp: str | None = None
    foto_despues_webp: str | None = None


class AtencionResponse(BaseModel):
    id: int
    mascota_id: int
    servicio_id: int
    fecha: datetime
    observaciones: str | None = None
    monto_cobrado: float
    medio_pago: str
    foto_antes_webp: str | None = None
    foto_despues_webp: str | None = None

    model_config = {"from_attributes": True}
