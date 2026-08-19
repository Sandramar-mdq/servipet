from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class VentaDetalle(Base):
    __tablename__ = "venta_detalles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    venta_id: Mapped[int] = mapped_column(Integer, ForeignKey("ventas.id"), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False, default="PRODUCTO")
    producto_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("productos.id"), nullable=True)
    servicio_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("servicios.id"), nullable=True)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    precio_unitario: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    subtotal: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    venta: Mapped["Venta"] = relationship("Venta", back_populates="detalles")  # noqa: F821
    producto: Mapped["Producto | None"] = relationship("Producto", back_populates="detalles_venta")  # noqa: F821
