"""etapa 9.1: chat_sesiones y chat_mensajes para el chatbot IA

Crea las tablas que persisten sesiones y mensajes de la conversacion
con el asistente virtual (Gemini API).

Migracion defensiva: segura sobre BDs donde app.main startup ya creo
las tablas via Base.metadata.create_all (entornos locales con reload).

Revision ID: 0004_chat_sesiones
Revises: 0003_skins_presets
Create Date: 2026-08-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_chat_sesiones"
down_revision: Union[str, None] = "0003_skins_presets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existe_tabla(nombre: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return nombre in inspector.get_table_names()


def upgrade() -> None:
    """Upgrade schema."""
    if not _existe_tabla("chat_sesiones"):
        op.create_table(
            "chat_sesiones",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("comercio_id", sa.Integer(), nullable=False),
            sa.Column("actor_tipo", sa.String(length=20), nullable=False),
            sa.Column("actor_id", sa.Integer(), nullable=False),
            sa.Column("creado_en", sa.DateTime(), nullable=False),
            sa.Column("ultimo_mensaje_en", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["comercio_id"], ["comercios.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_chat_sesiones_comercio_id", "chat_sesiones", ["comercio_id"]
        )

    if not _existe_tabla("chat_mensajes"):
        op.create_table(
            "chat_mensajes",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("sesion_id", sa.Integer(), nullable=False),
            sa.Column("rol", sa.String(length=10), nullable=False),
            sa.Column("contenido", sa.Text(), nullable=False),
            sa.Column("herramientas_usadas", sa.Text(), nullable=True),
            sa.Column("creado_en", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["sesion_id"], ["chat_sesiones.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_chat_mensajes_sesion_id", "chat_mensajes", ["sesion_id"])


def downgrade() -> None:
    """Downgrade schema."""
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("chat_mensajes"):
        op.drop_index("ix_chat_mensajes_sesion_id", table_name="chat_mensajes")
        op.drop_table("chat_mensajes")
    if inspector.has_table("chat_sesiones"):
        op.drop_index("ix_chat_sesiones_comercio_id", table_name="chat_sesiones")
        op.drop_table("chat_sesiones")
