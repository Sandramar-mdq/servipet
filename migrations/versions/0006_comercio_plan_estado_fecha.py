"""modulo SuperAdmin: plan, estado y fecha_registro en comercios

Campos de gestion de tenancy necesarios para el panel /admin/comercios:
- plan: DEMO | ESTANDAR | PRO
- estado: ACTIVO | INACTIVO | MOROSO
- fecha_registro: fecha de alta del comercio

Migracion defensiva: segura sobre BDs existentes creadas con create_all
(agrega las columnas solo si faltan) y compatible con SQLite (batch).

Revision ID: 0006_comercio_plan_estado_fecha
Revises: 0005_notification_log
Create Date: 2026-09-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_comercio_plan_estado_fecha"
down_revision: Union[str, None] = "0005_notification_log"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _nombres_columnas(conn, tabla: str) -> set[str]:
    return {col["name"] for col in sa.inspect(conn).get_columns(tabla)}


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    if "comercios" not in sa.inspect(conn).get_table_names():
        return

    actuales = _nombres_columnas(conn, "comercios")

    if "plan" not in actuales:
        with op.batch_alter_table("comercios") as batch_op:
            batch_op.add_column(
                sa.Column("plan", sa.String(length=20), nullable=False, server_default="DEMO")
            )

    if "estado" not in actuales:
        with op.batch_alter_table("comercios") as batch_op:
            batch_op.add_column(
                sa.Column("estado", sa.String(length=20), nullable=False, server_default="ACTIVO")
            )

    if "fecha_registro" not in actuales:
        with op.batch_alter_table("comercios") as batch_op:
            batch_op.add_column(
                sa.Column("fecha_registro", sa.DateTime(), nullable=False, server_default=sa.func.now())
            )


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    if "comercios" not in sa.inspect(conn).get_table_names():
        return

    actuales = _nombres_columnas(conn, "comercios")

    if "fecha_registro" in actuales:
        with op.batch_alter_table("comercios") as batch_op:
            batch_op.drop_column("fecha_registro")

    if "estado" in actuales:
        with op.batch_alter_table("comercios") as batch_op:
            batch_op.drop_column("estado")

    if "plan" in actuales:
        with op.batch_alter_table("comercios") as batch_op:
            batch_op.drop_column("plan")