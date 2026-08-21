from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TipoAviso(str, Enum):
    PERDIDA = "PERDIDA"
    ENCONTRADA = "ENCONTRADA"
    ADOPCION = "ADOPCION"
    CUMPLEANOS = "CUMPLEAÑOS"
    AVISO_BARRIAL = "AVISO_BARRIAL"


class EstadoAviso(str, Enum):
    ACTIVO = "ACTIVO"
    RESUELTO = "RESUELTO"
    ARCHIVADO = "ARCHIVADO"


class TipoContacto(str, Enum):
    DIRECTO_WHATSAPP = "DIRECTO_WHATSAPP"
    VIA_COMERCIO = "VIA_COMERCIO"


def _valores(enum_cls: type[Enum]) -> list[str]:
    # Guardar en BD los valores del enum (no los nombres), necesario para
    # 'CUMPLEAÑOS' cuyo nombre de miembro no puede contener ñ.
    return [miembro.value for miembro in enum_cls]


def _ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


class AvisoComunitario(Base):
    __tablename__ = "aviso_comunitario"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    comercio_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("comercios.id"), nullable=False, index=True
    )
    cliente_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("clientes.id"), nullable=True
    )
    creado_por_usuario_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("usuarios.id"), nullable=True
    )
    tipo: Mapped[TipoAviso] = mapped_column(
        SAEnum(TipoAviso, name="tipo_aviso", native_enum=False, length=20,
               values_callable=_valores),
        nullable=False,
    )
    estado: Mapped[EstadoAviso] = mapped_column(
        SAEnum(EstadoAviso, name="estado_aviso", native_enum=False, length=20,
               values_callable=_valores),
        nullable=False,
        default=EstadoAviso.ACTIVO,
    )
    titulo: Mapped[str] = mapped_column(String(100), nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    foto_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    public_id_cloudinary: Mapped[str | None] = mapped_column(String(250), nullable=True)
    tipo_contacto: Mapped[TipoContacto] = mapped_column(
        SAEnum(TipoContacto, name="tipo_contacto", native_enum=False, length=30,
               values_callable=_valores),
        nullable=False,
        default=TipoContacto.VIA_COMERCIO,
    )
    telefono_contacto: Mapped[str | None] = mapped_column(String(30), nullable=True)
    fecha_publicacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_ahora_utc
    )
    fecha_expiracion: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- Relaciones ---
    comercio: Mapped["Comercio"] = relationship("Comercio", back_populates="avisos_comunitarios")  # noqa: F821
    cliente: Mapped["Cliente | None"] = relationship("Cliente")  # noqa: F821
