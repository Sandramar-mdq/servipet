from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Turno(Base):
    __tablename__ = "turnos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(Integer, ForeignKey("clientes.id"), nullable=False)
    mascota_id: Mapped[int] = mapped_column(Integer, ForeignKey("mascotas.id"), nullable=False)
    servicio_id: Mapped[int] = mapped_column(Integer, ForeignKey("servicios.id"), nullable=False)
    fecha_hora: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duracion_minutos: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="Pendiente")
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    cliente: Mapped["Cliente"] = relationship("Cliente", back_populates="turnos")  # noqa: F821
    mascota: Mapped["Mascota"] = relationship("Mascota", back_populates="turnos")  # noqa: F821
    servicio: Mapped["Servicio"] = relationship("Servicio", back_populates="turnos")  # noqa: F821
    atencion: Mapped["AtencionHistorial | None"] = relationship("AtencionHistorial", back_populates="turno", uselist=False)  # noqa: F821
