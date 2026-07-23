from pydantic import BaseModel


class MascotaCreate(BaseModel):
    cliente_id: int
    nombre: str
    raza: str | None = None
    peso: float | None = None
    edad: int | None = None
    sexo: str | None = None
    observaciones: str | None = None
    alergias: str | None = None
    foto_webp: str | None = None


class MascotaUpdate(BaseModel):
    nombre: str | None = None
    raza: str | None = None
    peso: float | None = None
    edad: int | None = None
    sexo: str | None = None
    observaciones: str | None = None
    alergias: str | None = None
    foto_webp: str | None = None


class MascotaResponse(BaseModel):
    id: int
    cliente_id: int
    nombre: str
    raza: str | None = None
    peso: float | None = None
    edad: int | None = None
    sexo: str | None = None
    observaciones: str | None = None
    alergias: str | None = None
    foto_webp: str | None = None

    model_config = {"from_attributes": True}
