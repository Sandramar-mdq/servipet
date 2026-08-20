from datetime import date

from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Producto(Base):
    __tablename__ = "productos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    comercio_id: Mapped[int] = mapped_column(Integer, ForeignKey("comercios.id"), nullable=False)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    precio_compra: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    precio_venta: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    stock_actual: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stock_minimo: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unidad_medida: Mapped[str] = mapped_column(String(20), nullable=False, default="UNIDAD")
    categoria: Mapped[str] = mapped_column(String(50), nullable=False, default="GENERAL")
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    codigo: Mapped[str | None] = mapped_column(String(50), index=True, nullable=True)
    imagen_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    marca: Mapped[str | None] = mapped_column(String(100), nullable=True)
    proveedor: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fecha_vencimiento: Mapped[date | None] = mapped_column(Date, nullable=True)

    detalles_venta: Mapped[list["VentaDetalle"]] = relationship("VentaDetalle", back_populates="producto")  # noqa: F821
