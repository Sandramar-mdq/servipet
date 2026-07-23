from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AtencionHistorial(Base):
    __tablename__ = "atencion_historial"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mascota_id: Mapped[int] = mapped_column(Integer, ForeignKey("mascotas.id"), nullable=False)
    servicio_id: Mapped[int] = mapped_column(Integer, ForeignKey("servicios.id"), nullable=False)
    fecha: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)
    monto_cobrado: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    medio_pago: Mapped[str] = mapped_column(String(20), nullable=False, default="efectivo")
    foto_antes_webp: Mapped[str | None] = mapped_column(Text, nullable=True)
    foto_despues_webp: Mapped[str | None] = mapped_column(Text, nullable=True)

    mascota: Mapped["Mascota"] = relationship("Mascota", back_populates="atenciones")  # noqa: F821
    servicio: Mapped["Servicio"] = relationship("Servicio", back_populates="atenciones")  # noqa: F821
