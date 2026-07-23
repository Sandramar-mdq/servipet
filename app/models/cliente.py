from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    comercio_id: Mapped[int] = mapped_column(Integer, ForeignKey("comercios.id"), nullable=False)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    telefono: Mapped[str] = mapped_column(String(30), nullable=True)
    email: Mapped[str] = mapped_column(String(150), nullable=True)
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
    foto_webp: Mapped[str | None] = mapped_column(Text, nullable=True)

    comercio: Mapped["Comercio"] = relationship("Comercio", back_populates="clientes")  # noqa: F821
    mascotas: Mapped[list["Mascota"]] = relationship("Mascota", back_populates="cliente")  # noqa: F821
