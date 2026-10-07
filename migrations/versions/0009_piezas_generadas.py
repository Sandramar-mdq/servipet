"""etapa 12.2: bitacora de piezas generadas (auditoria + anti-duplicado)

Tabla `piezas_generadas`: registra cada cartel, placa de cumpleanos o pieza del
kit B2B que el sistema genero. La restricion uq_pieza_generada_dedupe sobre
(comercio_id, tipo, referencia_tipo, referencia_id, formato, anio) impide generar
dos veces la misma pieza para la misma referencia en el mismo anio.

Migracion defensiva: segura sobre BDs existentes creadas con create_all
(crea la tabla solo si falta) y compatible con SQLite (batch).

Revision ID: 0009_piezas_generadas
Revises: 0008_solidaridad_cumpleanos
Create Date: 2026-09-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009_piezas_generadas"
down_revision: Union[str, None] = "0008_solidaridad_cumpleanos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _nombres_tablas(conn) -> set[str]:
    return set(sa.inspect(conn).get_table_names())


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    if "piezas_generadas" in _nombres_tablas(conn):
        return

    op.create_table(
        "piezas_generadas",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("comercio_id", sa.Integer(), nullable=False),
        sa.Column(
            "tipo",
            sa.Enum(
                "CARTEL_SOLIDARIO", "CUMPLEANOS", "PROMOCION",
                name="tipo_pieza", native_enum=False, length=20,
            ),
            nullable=False,
        ),
        sa.Column(
            "formato",
            sa.Enum(
                "PDF_A4", "PNG_1X1", "PNG_9X16",
                name="formato_pieza", native_enum=False, length=20,
            ),
            nullable=False,
        ),
        sa.Column(
            "referencia_tipo",
            sa.Enum(
                "AVISO", "MASCOTA", "PROMOCION",
                name="referencia_pieza", native_enum=False, length=20,
            ),
            nullable=True,
        ),
        sa.Column("referencia_id", sa.Integer(), nullable=True),
        sa.Column("anio", sa.SmallInteger(), nullable=True),
        sa.Column("beneficio", sa.String(length=200), nullable=True),
        sa.Column("nombre_archivo", sa.String(length=120), nullable=False),
        sa.Column("creado_por_usuario_id", sa.Integer(), nullable=True),
        sa.Column("creado_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["comercio_id"], ["comercios.id"]),
        sa.ForeignKeyConstraint(["creado_por_usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "comercio_id",
            "tipo",
            "referencia_tipo",
            "referencia_id",
            "formato",
            "anio",
            name="uq_pieza_generada_dedupe",
        ),
    )
    op.create_index(
        op.f("ix_piezas_generadas_comercio_id"),
        "piezas_generadas",
        ["comercio_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_piezas_generadas_anio"),
        "piezas_generadas",
        ["anio"],
        unique=False,
    )
    op.create_index(
        op.f("ix_piezas_generadas_creado_at"),
        "piezas_generadas",
        ["creado_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    if "piezas_generadas" not in _nombres_tablas(conn):
        return

    for nombre in (
        "ix_piezas_generadas_creado_at",
        "ix_piezas_generadas_anio",
        "ix_piezas_generadas_comercio_id",
    ):
        op.drop_index(op.f(nombre), table_name="piezas_generadas")
    op.drop_table("piezas_generadas")
