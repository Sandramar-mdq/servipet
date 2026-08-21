"""etapa 7.2: autor del aviso comunitario

Agrega creado_por_usuario_id a aviso_comunitario (nullable, FK usuarios.id).
Migracion defensiva: segura sobre BDs ya migradas.

Revision ID: 0002_aviso_creado_por
Revises: 0001_red_comunitaria
Create Date: 2026-08-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_aviso_creado_por"
down_revision: Union[str, None] = "0001_red_comunitaria"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _nombres_columnas(conn, tabla: str) -> set[str]:
    return {col["name"] for col in sa.inspect(conn).get_columns(tabla)}


def upgrade() -> None:
    conn = op.get_bind()
    tablas = set(sa.inspect(conn).get_table_names())

    if "aviso_comunitario" in tablas and "creado_por_usuario_id" not in _nombres_columnas(conn, "aviso_comunitario"):
        with op.batch_alter_table("aviso_comunitario") as batch_op:
            batch_op.add_column(
                sa.Column("creado_por_usuario_id", sa.Integer(), nullable=True)
            )
            batch_op.create_foreign_key(
                "fk_aviso_comunitario_creado_por_usuario",
                "usuarios",
                ["creado_por_usuario_id"],
                ["id"],
            )


def downgrade() -> None:
    conn = op.get_bind()
    tablas = set(sa.inspect(conn).get_table_names())

    if "aviso_comunitario" in tablas and "creado_por_usuario_id" in _nombres_columnas(conn, "aviso_comunitario"):
        with op.batch_alter_table("aviso_comunitario") as batch_op:
            batch_op.drop_constraint(
                "fk_aviso_comunitario_creado_por_usuario", type_="foreignkey"
            )
            batch_op.drop_column("creado_por_usuario_id")
