"""etapa 7.1: red comunitaria (opt-in en comercios + avisos comunitarios)

Migracion defensiva: segura sobre BDs existentes creadas con create_all
(agrega la columna/tabla solo si falta).

Revision ID: 0001_red_comunitaria
Revises:
Create Date: 2026-08-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_red_comunitaria"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _nombres_tablas(conn) -> set[str]:
    return set(sa.inspect(conn).get_table_names())


def _nombres_columnas(conn, tabla: str) -> set[str]:
    return {col["name"] for col in sa.inspect(conn).get_columns(tabla)}


def upgrade() -> None:
    conn = op.get_bind()
    tablas = _nombres_tablas(conn)

    # --- Opt-in de red comunitaria en comercios ---
    if "comercios" in tablas and "habilitar_red_comunitaria" not in _nombres_columnas(conn, "comercios"):
        with op.batch_alter_table("comercios") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "habilitar_red_comunitaria",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                )
            )

    # --- Tabla de avisos comunitarios ---
    if "aviso_comunitario" not in tablas:
        op.create_table(
            "aviso_comunitario",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("comercio_id", sa.Integer(), nullable=False),
            sa.Column("cliente_id", sa.Integer(), nullable=True),
            sa.Column(
                "tipo",
                sa.Enum(
                    "PERDIDA", "ENCONTRADA", "ADOPCION", "CUMPLEAÑOS", "AVISO_BARRIAL",
                    name="tipo_aviso", native_enum=False, length=20,
                ),
                nullable=False,
            ),
            sa.Column(
                "estado",
                sa.Enum("ACTIVO", "RESUELTO", "ARCHIVADO", name="estado_aviso",
                        native_enum=False, length=20),
                nullable=False,
            ),
            sa.Column("titulo", sa.String(length=100), nullable=False),
            sa.Column("descripcion", sa.Text(), nullable=False),
            sa.Column("foto_url", sa.String(length=500), nullable=True),
            sa.Column("public_id_cloudinary", sa.String(length=250), nullable=True),
            sa.Column(
                "tipo_contacto",
                sa.Enum("DIRECTO_WHATSAPP", "VIA_COMERCIO", name="tipo_contacto",
                        native_enum=False, length=30),
                nullable=False,
            ),
            sa.Column("telefono_contacto", sa.String(length=30), nullable=True),
            sa.Column("fecha_publicacion", sa.DateTime(timezone=True), nullable=False),
            sa.Column("fecha_expiracion", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["cliente_id"], ["clientes.id"]),
            sa.ForeignKeyConstraint(["comercio_id"], ["comercios.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_aviso_comunitario_comercio_id"),
            "aviso_comunitario",
            ["comercio_id"],
            unique=False,
        )


def downgrade() -> None:
    conn = op.get_bind()
    tablas = _nombres_tablas(conn)

    if "aviso_comunitario" in tablas:
        op.drop_index(op.f("ix_aviso_comunitario_comercio_id"), table_name="aviso_comunitario")
        op.drop_table("aviso_comunitario")

    if "comercios" in tablas and "habilitar_red_comunitaria" in _nombres_columnas(conn, "comercios"):
        with op.batch_alter_table("comercios") as batch_op:
            batch_op.drop_column("habilitar_red_comunitaria")
