from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Servicio(Base):
    __tablename__ = "servicios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    precio_base: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    atenciones: Mapped[list["AtencionHistorial"]] = relationship("AtencionHistorial", back_populates="servicio")  # noqa: F821
