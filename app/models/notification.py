from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

ESTADO_PENDING = "PENDING"
ESTADO_SENT = "SENT"
ESTADO_FAILED = "FAILED"

EVENTO_CONFIRMATION = "CONFIRMATION"
EVENTO_REMINDER = "REMINDER"
EVENTO_PET_READY = "PET_READY"
EVENTO_CANCELACION = "CANCELACION"

ESTADOS = {ESTADO_PENDING, ESTADO_SENT, ESTADO_FAILED}


class NotificationLog(Base):
    """Registro de cada envio de notificacion (WhatsApp / webhook).

    Persiste el intento: evento que lo genero, destino, estado del envio
    (PENDING/SENT/FAILED), mensaje renderizado y el contador de reintentos.
    """

    __tablename__ = "notification_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    turno_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("turnos.id"), nullable=True, index=True
    )
    evento: Mapped[str] = mapped_column(String(20), nullable=False)
    canal: Mapped[str] = mapped_column(String(20), nullable=False, default="whatsapp")
    destino: Mapped[str | None] = mapped_column(String(30), nullable=True)
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ESTADO_PENDING, index=True
    )
    mensaje: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_intentos: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    proximo_intento_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ultimo_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    enviado_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    turno: Mapped["Turno | None"] = relationship("Turno")  # noqa: F821