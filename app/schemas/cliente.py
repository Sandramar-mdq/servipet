from pydantic import BaseModel


class ClienteCreate(BaseModel):
    comercio_id: int
    nombre: str
    telefono: str | None = None
    email: str | None = None
    notas: str | None = None
    foto_webp: str | None = None


class ClienteUpdate(BaseModel):
    nombre: str | None = None
    telefono: str | None = None
    email: str | None = None
    notas: str | None = None
    foto_webp: str | None = None


class ClienteResponse(BaseModel):
    id: int
    comercio_id: int
    nombre: str
    telefono: str | None = None
    email: str | None = None
    notas: str | None = None
    foto_webp: str | None = None

    model_config = {"from_attributes": True}
