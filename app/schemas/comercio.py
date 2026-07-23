from pydantic import BaseModel


class ComercioCreate(BaseModel):
    nombre: str
    direccion: str | None = None
    telefono: str | None = None
    email: str | None = None
    logo_webp: str | None = None


class ComercioUpdate(BaseModel):
    nombre: str | None = None
    direccion: str | None = None
    telefono: str | None = None
    email: str | None = None
    logo_webp: str | None = None


class ComercioResponse(BaseModel):
    id: int
    nombre: str
    direccion: str | None = None
    telefono: str | None = None
    email: str | None = None
    logo_webp: str | None = None

    model_config = {"from_attributes": True}
