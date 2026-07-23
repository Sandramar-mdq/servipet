from pydantic import BaseModel


class ServicioCreate(BaseModel):
    nombre: str
    descripcion: str | None = None
    precio_base: float = 0.0


class ServicioUpdate(BaseModel):
    nombre: str | None = None
    descripcion: str | None = None
    precio_base: float | None = None


class ServicioResponse(BaseModel):
    id: int
    nombre: str
    descripcion: str | None = None
    precio_base: float

    model_config = {"from_attributes": True}
