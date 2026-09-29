from datetime import date

from pydantic import BaseModel


class MascotaCreate(BaseModel):
    cliente_id: int
    nombre: str
    especie: str | None = None
    raza: str | None = None
    color: str | None = None
    peso: float | None = None
    edad: int | None = None
    sexo: str | None = None
    observaciones: str | None = None
    alergias: str | None = None
    foto_webp: str | None = None
    fecha_nacimiento: date | None = None
    fallecida: bool = False


class MascotaUpdate(BaseModel):
    nombre: str | None = None
    especie: str | None = None
    raza: str | None = None
    color: str | None = None
    peso: float | None = None
    edad: int | None = None
    sexo: str | None = None
    observaciones: str | None = None
    alergias: str | None = None
    foto_webp: str | None = None
    fecha_nacimiento: date | None = None
    fallecida: bool | None = None


class MascotaResponse(BaseModel):
    id: int
    cliente_id: int
    nombre: str
    especie: str | None = None
    raza: str | None = None
    color: str | None = None
    peso: float | None = None
    edad: int | None = None
    sexo: str | None = None
    observaciones: str | None = None
    alergias: str | None = None
    foto_webp: str | None = None
    fecha_nacimiento: date | None = None
    fallecida: bool = False
    activo: bool = True

    model_config = {"from_attributes": True}
