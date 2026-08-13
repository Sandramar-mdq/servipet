from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Comercio(Base):
    __tablename__ = "comercios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    direccion: Mapped[str] = mapped_column(String(250), nullable=True)
    telefono: Mapped[str] = mapped_column(String(30), nullable=True)
    email: Mapped[str] = mapped_column(String(150), nullable=True)
    logo_webp: Mapped[str | None] = mapped_column(Text, nullable=True)
    hora_apertura: Mapped[str] = mapped_column(String(5), nullable=False, default="09:00")
    hora_cierre: Mapped[str] = mapped_column(String(5), nullable=False, default="18:00")
    slot_minutos: Mapped[int] = mapped_column(Integer, nullable=False, default=30)

    clientes: Mapped[list["Cliente"]] = relationship("Cliente", back_populates="comercio")  # noqa: F821
