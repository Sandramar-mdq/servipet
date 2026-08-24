"""etapa 8.1: skins, presets y accesibilidad por comercio

Agrega columnas de personalizacion visual (tema_preset, colores HEX,
logo_url, banner_url) y accesibilidad (a11y_modo, a11y_dyslexic) a la
tabla comercios, con server_default para backfill de registros existentes.
Migracion defensiva: segura sobre BDs ya migradas.

Revision ID: 0003_skins_presets
Revises: 0002_aviso_creado_por
Create Date: 2026-08-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_skins_presets"
down_revision: Union[str, None] = "0002_aviso_creado_por"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (nombre, tipo, server_default o None, nullable)
_COLUMNAS_SKIN = (
    ("tema_preset", sa.String(length=50), sa.text("'clasico_paws'"), False),
    ("color_primario", sa.String(length=7), sa.text("'#1E40AF'"), False),
    ("color_secundario", sa.String(length=7), sa.text("'#0D9488'"), False),
    ("logo_url", sa.String(length=255), None, True),
    ("banner_url", sa.String(length=255), None, True),
    ("a11y_modo", sa.String(length=50), sa.text("'normal'"), False),
    ("a11y_dyslexic", sa.Boolean(), sa.false(), False),
)


def _nombres_columnas(conn, tabla: str) -> set[str]:
    return {col["name"] for col in sa.inspect(conn).get_columns(tabla)}


def upgrade() -> None:
    conn = op.get_bind()
    tablas = set(sa.inspect(conn).get_table_names())

    if "comercios" not in tablas:
        return

    existentes = _nombres_columnas(conn, "comercios")
    pendientes = [c for c in _COLUMNAS_SKIN if c[0] not in existentes]
    if not pendientes:
        return

    with op.batch_alter_table("comercios") as batch_op:
        for nombre, tipo, server_default, nullable in pendientes:
            batch_op.add_column(
                sa.Column(nombre, tipo, nullable=nullable, server_default=server_default)
            )


def downgrade() -> None:
    conn = op.get_bind()
    tablas = set(sa.inspect(conn).get_table_names())

    if "comercios" not in tablas:
        return

    existentes = _nombres_columnas(conn, "comercios")
    presentes = [c[0] for c in reversed(_COLUMNAS_SKIN) if c[0] in existentes]
    if not presentes:
        return

    with op.batch_alter_table("comercios") as batch_op:
        for nombre in presentes:
            batch_op.drop_column(nombre)
