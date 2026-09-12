"""consentimiento explicito de Terminos Beta en comercios

Campos de auditoria del consentimiento de la version Beta (Tarea 11.2.2):
- acepta_terminos_beta: indica que el comercio acepto los Terminos del
  Servicio y Exencion de Responsabilidad al registrarse.
- terminos_aceptados_at: fecha/hora UTC exacta del consentimiento.

Migracion defensiva: segura sobre BDs existentes creadas con create_all
(agrega las columnas solo si faltan) y compatible con SQLite (batch).

Revision ID: 0007_comercio_consentimiento_terminos
Revises: 0006_comercio_plan_estado_fecha
Create Date: 2026-09-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_comercio_consentimiento_terminos"
down_revision: Union[str, None] = "0006_comercio_plan_estado_fecha"
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

    if "acepta_terminos_beta" not in actuales:
        with op.batch_alter_table("comercios") as batch_op:
            batch_op.add_column(
                sa.Column("acepta_terminos_beta", sa.Boolean(), nullable=False, server_default="0")
            )

    if "terminos_aceptados_at" not in actuales:
        with op.batch_alter_table("comercios") as batch_op:
            batch_op.add_column(sa.Column("terminos_aceptados_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    if "comercios" not in sa.inspect(conn).get_table_names():
        return

    actuales = _nombres_columnas(conn, "comercios")

    if "terminos_aceptados_at" in actuales:
        with op.batch_alter_table("comercios") as batch_op:
            batch_op.drop_column("terminos_aceptados_at")

    if "acepta_terminos_beta" in actuales:
        with op.batch_alter_table("comercios") as batch_op:
            batch_op.drop_column("acepta_terminos_beta")