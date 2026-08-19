from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Venta(Base):
    __tablename__ = "ventas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    comercio_id: Mapped[int] = mapped_column(Integer, ForeignKey("comercios.id"), nullable=False)
    cliente_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("clientes.id"), nullable=True)
    usuario_id: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id"), nullable=False)
    caja_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("cajas.id"), nullable=True)
    fecha: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    medio_pago: Mapped[str] = mapped_column(String(20), nullable=False, default="efectivo")
    subtotal: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    descuento: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="COBRADA")
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)

    detalles: Mapped[list["VentaDetalle"]] = relationship("VentaDetalle", back_populates="venta", cascade="all, delete-orphan")  # noqa: F821
    caja: Mapped["Caja | None"] = relationship("Caja", back_populates="ventas")  # noqa: F821
