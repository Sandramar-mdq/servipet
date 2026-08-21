from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator

from app.models.aviso_comunitario import EstadoAviso, TipoAviso, TipoContacto


class AvisoComunitarioBase(BaseModel):
    tipo: TipoAviso
    titulo: str
    descripcion: str
    foto_url: str | None = None
    public_id_cloudinary: str | None = None
    estado: EstadoAviso = EstadoAviso.ACTIVO
    tipo_contacto: TipoContacto = TipoContacto.VIA_COMERCIO
    telefono_contacto: str | None = None
    fecha_expiracion: datetime | None = None


class AvisoComunitarioCreate(AvisoComunitarioBase):
    comercio_id: int
    cliente_id: int | None = None

    @model_validator(mode="after")
    def validar_telefono_si_whatsapp(self):
        if self.tipo_contacto == TipoContacto.DIRECTO_WHATSAPP:
            if not self.telefono_contacto or not self.telefono_contacto.strip():
                raise ValueError(
                    "telefono_contacto es obligatorio cuando tipo_contacto es DIRECTO_WHATSAPP"
                )
        return self


class AvisoComunitarioUpdate(BaseModel):
    titulo: str | None = None
    descripcion: str | None = None
    foto_url: str | None = None
    estado: EstadoAviso | None = None
    tipo_contacto: TipoContacto | None = None
    telefono_contacto: str | None = None
    fecha_expiracion: datetime | None = None


class AvisoCambioEstadoRequest(BaseModel):
    estado: EstadoAviso


class AvisoComunitarioResponse(AvisoComunitarioBase):
    id: int
    comercio_id: int
    cliente_id: int | None = None
    creado_por_usuario_id: int | None = None
    fecha_publicacion: datetime

    model_config = ConfigDict(from_attributes=True)


class FeedAvisosResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[AvisoComunitarioResponse]
