"""etapa 10.1: notification_log para notificaciones whatsapp y webhooks

Registra cada envio de notificacion de turnos (reserva, confirmacion,
recordatorio, mascota lista, cancelacion) con estado PENDING/SENT/FAILED,
contador de reintentos y proximo intento programado.

Migracion defensiva: segura sobre BDs donde app.main startup ya creo
la tabla via Base.metadata.create_all (entornos locales con reload).

Revision ID: 0005_notification_log
Revises: 0004_chat_sesiones
Create Date: 2026-09-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_notification_log"
down_revision: Union[str, None] = "0004_chat_sesiones"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existe_tabla(nombre: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return nombre in inspector.get_table_names()


def upgrade() -> None:
    """Upgrade schema."""
    if not _existe_tabla("notification_log"):
        op.create_table(
            "notification_log",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("turno_id", sa.Integer(), nullable=True),
            sa.Column("evento", sa.String(length=20), nullable=False),
            sa.Column("canal", sa.String(length=20), nullable=False),
            sa.Column("destino", sa.String(length=30), nullable=True),
            sa.Column("estado", sa.String(length=20), nullable=False),
            sa.Column("mensaje", sa.Text(), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=True),
            sa.Column("intentos", sa.Integer(), nullable=False),
            sa.Column("max_intentos", sa.Integer(), nullable=False),
            sa.Column("proximo_intento_en", sa.DateTime(), nullable=True),
            sa.Column("ultimo_error", sa.Text(), nullable=True),
            sa.Column("creado_en", sa.DateTime(), nullable=False),
            sa.Column("enviado_en", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["turno_id"], ["turnos.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_notification_log_turno_id", "notification_log", ["turno_id"]
        )
        op.create_index(
            "ix_notification_log_estado", "notification_log", ["estado"]
        )


def downgrade() -> None:
    """Downgrade schema."""
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("notification_log"):
        op.drop_index("ix_notification_log_estado", table_name="notification_log")
        op.drop_index("ix_notification_log_turno_id", table_name="notification_log")
        op.drop_table("notification_log")