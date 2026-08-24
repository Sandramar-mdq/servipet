from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Mensaje entrante del actor autenticado hacia el asistente IA."""

    mensaje: str = Field(min_length=1, max_length=2000)
    sesion_id: int | None = Field(
        default=None,
        description="Sesion existente; si se omite se crea una nueva",
    )


class ChatResponse(BaseModel):
    """Respuesta estructurada del asistente IA.

    - estado 'ok': respuesta generada por Gemini.
    - estado 'fallback': respuesta amable por error tecnico o falta de
      configuracion (GEMINI_API_KEY ausente).
    """

    sesion_id: int
    respuesta: str
    estado: Literal["ok", "fallback"] = "ok"
    herramientas_usadas: list[str] = Field(default_factory=list)
