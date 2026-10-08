from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.pieza_generada import FormatoPieza, TipoPieza


# --- Kit Marketing B2B ---

_HEX6 = r"^#[0-9A-Fa-f]{6}$"


class PromocionCreate(BaseModel):
    titulo: str = Field(min_length=3, max_length=60)
    descuento: str | None = Field(default=None, max_length=40)
    condiciones: str | None = Field(default=None, max_length=200)
    beneficio_texto: str | None = Field(default=None, max_length=80)
    usar_branding: bool = True
    registrar: bool = False
    color_primario: str | None = Field(default=None, max_length=7)
    color_secundario: str | None = Field(default=None, max_length=7)

    @field_validator("color_primario", "color_secundario")
    @classmethod
    def _validar_hex(cls, valor: str | None) -> str | None:
        """Los colores van como `#RRGGBB`; cualquier otra cosa es un 422."""
        import re

        if valor is None or valor == "":
            return None
        if not re.match(_HEX6, valor):
            raise ValueError("El color debe tener formato #RRGGBB")
        return valor.upper()


# --- Fidelizacion cumpleaños ---

class ConfigCumpleanosUpdate(BaseModel):
    habilitar: bool | None = None
    beneficio: str | None = Field(default=None, max_length=200)


class ConfigCumpleanosResponse(BaseModel):
    comercio_id: int
    comercio_nombre: str
    habilitar: bool
    beneficio: str | None = None
    clientes_consentidos: int


class CumpleanosItem(BaseModel):
    mascota_id: int
    cliente_id: int
    cliente_nombre: str
    cliente_telefono: str | None = None
    nombre: str
    especie: str | None = None
    raza: str | None = None
    color: str | None = None
    fecha_nacimiento: date
    anios: int
    dias_para: int
    ya_enviado: bool
    beneficio: str
    comercio_nombre: str
    foto_webp: str | None = None


class ProximosCumpleanosResponse(BaseModel):
    dias: int
    total: int
    beneficio_default: str | None = None
    items: list[CumpleanosItem] = []


# --- Auditoria de piezas ---

class PiezaGeneradaResponse(BaseModel):
    id: int
    comercio_id: int
    tipo: TipoPieza
    formato: FormatoPieza
    referencia_tipo: str | None = None
    referencia_id: int | None = None
    anio: int | None = None
    beneficio: str | None = None
    nombre_archivo: str
    creado_at: datetime

    model_config = ConfigDict(from_attributes=True)
