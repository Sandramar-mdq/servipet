from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Mascota(Base):
    __tablename__ = "mascotas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(Integer, ForeignKey("clientes.id"), nullable=False)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    raza: Mapped[str] = mapped_column(String(100), nullable=True)
    peso: Mapped[float | None] = mapped_column(Float, nullable=True)
    edad: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sexo: Mapped[str] = mapped_column(String(10), nullable=True)
    observaciones: Mapped[str | None] = mapped_column(Text, nullable=True)
    alergias: Mapped[str | None] = mapped_column(Text, nullable=True)
    foto_webp: Mapped[str | None] = mapped_column(Text, nullable=True)

    cliente: Mapped["Cliente"] = relationship("Cliente", back_populates="mascotas")  # noqa: F821
    atenciones: Mapped[list["AtencionHistorial"]] = relationship("AtencionHistorial", back_populates="mascota")  # noqa: F821
