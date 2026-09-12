from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Valores válidos para tipo_comercio (documentados, no enforced por BD):
# 'VETERINARIA', 'PELUQUERIA', 'GUARDERIA', 'PASEADOR', 'MULTIRRUBRO'


class Comercio(Base):
    __tablename__ = "comercios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    tipo_comercio: Mapped[str] = mapped_column(String(20), nullable=False, default="MULTIRRUBRO")
    direccion: Mapped[str] = mapped_column(String(250), nullable=True)
    telefono: Mapped[str] = mapped_column(String(30), nullable=True)
    email: Mapped[str] = mapped_column(String(150), nullable=True)
    logo_webp: Mapped[str | None] = mapped_column(Text, nullable=True)
    hora_apertura: Mapped[str] = mapped_column(String(5), nullable=False, default="09:00")
    hora_cierre: Mapped[str] = mapped_column(String(5), nullable=False, default="18:00")
    slot_minutos: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # --- Administracion / tenancy (modulo SuperAdmin) ---
    plan: Mapped[str] = mapped_column(
        String(20), nullable=False, default="DEMO", server_default="DEMO"
    )
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ACTIVO", server_default="ACTIVO"
    )
    fecha_registro: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # --- Políticas de cancelación y negocio ---
    horas_limite_cancelacion: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    porcentaje_recargo_tardio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    permite_autoreserva_publica: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # --- Red comunitaria (opt-in) ---
    habilitar_red_comunitaria: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # --- Skins / apariencia (Etapa 8.1) ---
    tema_preset: Mapped[str] = mapped_column(String(50), nullable=False, default="clasico_paws")
    color_primario: Mapped[str] = mapped_column(String(7), nullable=False, default="#1E40AF")
    color_secundario: Mapped[str] = mapped_column(String(7), nullable=False, default="#0D9488")
    logo_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    banner_url: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # --- Accesibilidad (a11y) ---
    a11y_modo: Mapped[str] = mapped_column(String(50), nullable=False, default="normal")
    a11y_dyslexic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # --- Consentimiento Terminos Beta (Tarea 11.2.2) ---
    acepta_terminos_beta: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    terminos_aceptados_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # --- Relaciones ---
    clientes: Mapped[list["Cliente"]] = relationship("Cliente", back_populates="comercio")  # noqa: F821
    usuarios: Mapped[list["Usuario"]] = relationship("Usuario", back_populates="comercio")  # noqa: F821
    avisos_comunitarios: Mapped[list["AvisoComunitario"]] = relationship(  # noqa: F821
        "AvisoComunitario", back_populates="comercio"
    )
