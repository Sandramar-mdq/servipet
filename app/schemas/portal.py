from pydantic import BaseModel


class PortalMascotaCreate(BaseModel):
    nombre: str
    especie: str | None = None
    raza: str | None = None
    peso: float | None = None
    edad: int | None = None
    sexo: str | None = None
    observaciones: str | None = None
    alergias: str | None = None


class PortalMascotaResponse(BaseModel):
    id: int
    nombre: str
    especie: str | None = None
    raza: str | None = None
    peso: float | None = None
    edad: int | None = None
    sexo: str | None = None
    observaciones: str | None = None
    alergias: str | None = None
    activo: bool

    model_config = {"from_attributes": True}


class PortalPerfilResponse(BaseModel):
    id: int
    nombre: str
    telefono: str | None = None
    email: str | None = None
    mascotas: list[PortalMascotaResponse] = []

    model_config = {"from_attributes": True}


class PortalServicioResponse(BaseModel):
    id: int
    nombre: str
    descripcion: str | None = None
    precio_base: float
    duracion_minutos: int

    model_config = {"from_attributes": True}


class PortalDisponibilidadResponse(BaseModel):
    fecha: str
    servicio_id: int
    servicio_nombre: str
    duracion_minutos: int
    slots: list[str]


class PortalReservarRequest(BaseModel):
    mascota_id: int
    servicio_id: int
    fecha: str
    hora: str
    observaciones: str | None = None


class PortalTurnoResponse(BaseModel):
    id: int
    mascota_id: int
    servicio_id: int
    servicio_nombre: str = ""
    fecha_hora: str
    duracion_minutos: int
    estado: str
    observaciones: str | None = None

    model_config = {"from_attributes": True}


class PortalAtencionResponse(BaseModel):
    id: int
    servicio_nombre: str = ""
    fecha: str
    observaciones: str | None = None
    monto_cobrado: float

    model_config = {"from_attributes": True}


class PortalCancelarResponse(BaseModel):
    turno_id: int
    estado: str
    horas_restantes: float
    penalizacion_porcentaje: float
    mensaje: str
