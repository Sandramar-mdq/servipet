from pydantic import BaseModel


class ComercioCreate(BaseModel):
    nombre: str
    tipo_comercio: str = "MULTIRRUBRO"
    direccion: str | None = None
    telefono: str | None = None
    email: str | None = None
    logo_webp: str | None = None
    hora_apertura: str = "09:00"
    hora_cierre: str = "18:00"
    slot_minutos: int = 30
    activo: bool = True
    horas_limite_cancelacion: int = 24
    porcentaje_recargo_tardio: float = 0.0
    permite_autoreserva_publica: bool = True


class ComercioUpdate(BaseModel):
    nombre: str | None = None
    tipo_comercio: str | None = None
    direccion: str | None = None
    telefono: str | None = None
    email: str | None = None
    logo_webp: str | None = None
    hora_apertura: str | None = None
    hora_cierre: str | None = None
    slot_minutos: int | None = None
    activo: bool | None = None
    horas_limite_cancelacion: int | None = None
    porcentaje_recargo_tardio: float | None = None
    permite_autoreserva_publica: bool | None = None


class ComercioResponse(BaseModel):
    id: int
    nombre: str
    tipo_comercio: str
    direccion: str | None = None
    telefono: str | None = None
    email: str | None = None
    logo_webp: str | None = None
    hora_apertura: str
    hora_cierre: str
    slot_minutos: int
    activo: bool
    horas_limite_cancelacion: int
    porcentaje_recargo_tardio: float
    permite_autoreserva_publica: bool

    model_config = {"from_attributes": True}
