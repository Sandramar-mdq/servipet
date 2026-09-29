from datetime import date

from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Mascota(Base):
    __tablename__ = "mascotas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(Integer, ForeignKey("clientes.id"), nullable=False)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    especie: Mapped[str | None] = mapped_column(String(50), nullable=True)
    raza: Mapped[str] = mapped_column(String(100), nullable=True)
    color: Mapped[str | None] = mapped_column(String(50), nullable=True)
    peso: Mapped[float | None] = mapped_column(Float, nullable=True)
    edad: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sexo: Mapped[str] = mapped_column(String(10), nullable=True)
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)
    alergias: Mapped[str | None] = mapped_column(Text, nullable=True)
    foto_webp: Mapped[str | None] = mapped_column(Text, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fallecida: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    fecha_nacimiento: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)

    cliente: Mapped["Cliente"] = relationship("Cliente", back_populates="mascotas")  # noqa: F821
    atenciones: Mapped[list["AtencionHistorial"]] = relationship("AtencionHistorial", back_populates="mascota")  # noqa: F821
    turnos: Mapped[list["Turno"]] = relationship("Turno", back_populates="mascota")  # noqa: F821
