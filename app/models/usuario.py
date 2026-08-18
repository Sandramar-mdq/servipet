from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Usuario(Base):
    """Cuentas con acceso al sistema: Admin del comercio, Empleados y Clientes.

    - comercio_id es nullable para permitir superadmins o clientes globales.
    - rol valida entre: 'ADMIN', 'EMPLEADO', 'CLIENTE'.
    """
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    comercio_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("comercios.id"), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(50), index=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    rol: Mapped[str] = mapped_column(String(20), nullable=False, default="CLIENTE")
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    comercio: Mapped["Comercio | None"] = relationship("Comercio", back_populates="usuarios")  # noqa: F821
    cliente_profile: Mapped["Cliente | None"] = relationship("Cliente", back_populates="usuario")  # noqa: F821
