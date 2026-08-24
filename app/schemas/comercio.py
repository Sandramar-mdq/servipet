from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from app.core.skins_config import A11Y_MODOS, HEX_COLOR_PATTERN, SKINS_PRESETS

HexColor = Annotated[str, Field(pattern=HEX_COLOR_PATTERN)]


class ComercioBase(BaseModel):
    """Campos de apariencia/skin compartidos por Create/Update/Response."""

    tema_preset: str = "clasico_paws"
    color_primario: HexColor = "#1E40AF"
    color_secundario: HexColor = "#0D9488"
    logo_url: str | None = None
    banner_url: str | None = None
    a11y_modo: str = "normal"
    a11y_dyslexic: bool = False

    @field_validator("tema_preset")
    @classmethod
    def _preset_valido(cls, v: str | None) -> str | None:
        if v is not None and v not in SKINS_PRESETS:
            raise ValueError(
                f"Preset desconocido '{v}'. Valores válidos: {', '.join(sorted(SKINS_PRESETS))}"
            )
        return v

    @field_validator("a11y_modo")
    @classmethod
    def _modo_a11y_valido(cls, v: str | None) -> str | None:
        if v is not None and v not in A11Y_MODOS:
            raise ValueError(
                f"Modo a11y desconocido '{v}'. Valores válidos: {', '.join(A11Y_MODOS)}"
            )
        return v


class ComercioOptInRequest(BaseModel):
    habilitar_red_comunitaria: bool


class ComercioCreate(ComercioBase):
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
    habilitar_red_comunitaria: bool = False


class ComercioUpdate(ComercioBase):
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
    habilitar_red_comunitaria: bool | None = None


class ComercioResponse(ComercioBase):
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
    habilitar_red_comunitaria: bool = False

    model_config = {"from_attributes": True}
