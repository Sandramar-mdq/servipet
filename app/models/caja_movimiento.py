from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CajaMovimiento(Base):
    __tablename__ = "caja_movimientos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    caja_id: Mapped[int] = mapped_column(Integer, ForeignKey("cajas.id"), nullable=False)
    tipo: Mapped[str] = mapped_column(String(10), nullable=False, default="INGRESO")
    monto: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    descripcion: Mapped[str] = mapped_column(String(200), nullable=False)
    venta_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("ventas.id"), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    caja: Mapped["Caja"] = relationship("Caja", back_populates="movimientos")  # noqa: F821
