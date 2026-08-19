from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Caja(Base):
    __tablename__ = "cajas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    comercio_id: Mapped[int] = mapped_column(Integer, ForeignKey("comercios.id"), nullable=False)
    usuario_apertura_id: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id"), nullable=False)
    usuario_cierre_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("usuarios.id"), nullable=True)
    fecha_apertura: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    fecha_cierre: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    monto_inicial: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    monto_final_esperado: Mapped[float | None] = mapped_column(Float, nullable=True)
    monto_final_real: Mapped[float | None] = mapped_column(Float, nullable=True)
    estado: Mapped[str] = mapped_column(String(10), nullable=False, default="ABIERTA")
    notas_apertura: Mapped[str | None] = mapped_column(Text, nullable=True)
    notas_cierre: Mapped[str | None] = mapped_column(Text, nullable=True)

    movimientos: Mapped[list["CajaMovimiento"]] = relationship("CajaMovimiento", back_populates="caja", cascade="all, delete-orphan")  # noqa: F821
    ventas: Mapped[list["Venta"]] = relationship("Venta", back_populates="caja")  # noqa: F821
