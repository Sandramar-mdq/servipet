from datetime import datetime

from pydantic import BaseModel


class UsuarioCreate(BaseModel):
    comercio_id: int | None = None
    email: str | None = None
    telefono: str | None = None
    password: str
    rol: str = "CLIENTE"


class UsuarioUpdate(BaseModel):
    email: str | None = None
    telefono: str | None = None
    rol: str | None = None
    activo: bool | None = None


class UsuarioResponse(BaseModel):
    id: int
    comercio_id: int | None = None
    email: str | None = None
    telefono: str | None = None
    rol: str
    activo: bool
    fecha_creacion: datetime

    model_config = {"from_attributes": True}
