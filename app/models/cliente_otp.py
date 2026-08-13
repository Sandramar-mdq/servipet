from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ClienteOTP(Base):
    __tablename__ = "cliente_otp"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    codigo_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    expira_en: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    usado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
