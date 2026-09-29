from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TipoPieza(str, Enum):
    CARTEL_SOLIDARIO = "CARTEL_SOLIDARIO"
    CUMPLEANOS = "CUMPLEANOS"
    PROMOCION = "PROMOCION"


class FormatoPieza(str, Enum):
    PDF_A4 = "PDF_A4"
    PNG_1X1 = "PNG_1X1"
    PNG_9X16 = "PNG_9X16"


class ReferenciaPieza(str, Enum):
    AVISO = "AVISO"
    MASCOTA = "MASCOTA"
    PROMOCION = "PROMOCION"


def _valores(enum_cls: type[Enum]) -> list[str]:
    # Guardar en BD los valores del enum (no los nombres).
    return [miembro.value for miembro in enum_cls]


def _ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


class PiezaGenerada(Base):
    """Auditoria de las piezas visuales generadas por el modulo de Marketing.

    Sirve como bitacora de que se genero/envio un cartel, una placa de cumpleanos
    o una pieza de kit B2B, y como mecanismo anti-duplicado.

    La restricion `uq_pieza_generada_dedupe` cubre (comercio, tipo, referencia,
    formato, anio). Nota importante: en SQLite y Postgres los NULL no colisionan
    dentro de un indice unico, por lo que el dedupe solo es efectivo cuando
    `referencia_id` y `anio` informed (caso CUMPLEANOS, que es el que lo necesita).
    Para piezas sin referencia (PROMOCION) la auditoria es puramente informativo.
    """

    __tablename__ = "piezas_generadas"
    __table_args__ = (
        UniqueConstraint(
            "comercio_id",
            "tipo",
            "referencia_tipo",
            "referencia_id",
            "formato",
            "anio",
            name="uq_pieza_generada_dedupe",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    comercio_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("comercios.id"), nullable=False, index=True
    )
    tipo: Mapped[TipoPieza] = mapped_column(
        SAEnum(
            TipoPieza,
            name="tipo_pieza",
            native_enum=False,
            length=20,
            values_callable=_valores,
        ),
        nullable=False,
    )
    formato: Mapped[FormatoPieza] = mapped_column(
        SAEnum(
            FormatoPieza,
            name="formato_pieza",
            native_enum=False,
            length=20,
            values_callable=_valores,
        ),
        nullable=False,
    )
    referencia_tipo: Mapped[ReferenciaPieza | None] = mapped_column(
        SAEnum(
            ReferenciaPieza,
            name="referencia_pieza",
            native_enum=False,
            length=20,
            values_callable=_valores,
        ),
        nullable=True,
    )
    referencia_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    anio: Mapped[int | None] = mapped_column(SmallInteger, nullable=True, index=True)
    beneficio: Mapped[str | None] = mapped_column(String(200), nullable=True)
    nombre_archivo: Mapped[str] = mapped_column(String(120), nullable=False)
    creado_por_usuario_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("usuarios.id"), nullable=True
    )
    creado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_ahora_utc, index=True
    )

    comercio: Mapped["Comercio"] = relationship(  # noqa: F821
        "Comercio", back_populates="piezas_generadas"
    )
