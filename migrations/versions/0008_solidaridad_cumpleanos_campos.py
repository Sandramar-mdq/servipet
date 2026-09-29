"""etapa 12.1: campos de solidario y fidelizacion en mascotas/clientes/comercios

Campos para los modulos de Marketing B2B de la Etapa 12:
- mascotas.fecha_nacimiento: base del calculo de cumpleanos (ventana de N dias).
- mascotas.fallecida: filtro ESTRICTO, una mascota fallecida nunca se incluye
  aunque siga con activo=True.
- mascotas.color: dato visible en los carteles.
- clientes.acepta_cumpleanos: consentimiento explicito del titular (dato sensible).
- clientes.zona_barrio: zona/barrio del domicilio, usado en el cartel solidario.
- comercios.habilitar_modulo_solidario: opt-in del modulo solidario.
- comercios.habilitar_cumpleanos: opt-in de la fidelizacion de cumpleanos.
- comercios.beneficio_cumpleanos: texto del beneficio configurable por el comercio.
- comercios.zona_barrio: zona/barrio del comercio, fallback del cartel.

Migracion defensiva: segura sobre BDs existentes creadas con create_all
(agrega las columnas solo si faltan) y compatible con SQLite (batch).

Revision ID: 0008_solidaridad_cumpleanos_campos
Revises: 0007_comercio_consentimiento_terminos
Create Date: 2026-09-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008_solidaridad_cumpleanos_campos"
down_revision: Union[str, None] = "0007_comercio_consentimiento_terminos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _nombres_tablas(conn) -> set[str]:
    return set(sa.inspect(conn).get_table_names())


def _nombres_columnas(conn, tabla: str) -> set[str]:
    return {col["name"] for col in sa.inspect(conn).get_columns(tabla)}


def _nombres_indices(conn, tabla: str) -> set[str]:
    return {idx["name"] for idx in sa.inspect(conn).get_indexes(tabla) if idx.get("name")}


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    tablas = _nombres_tablas(conn)

    # --- Mascotas ---
    if "mascotas" in tablas:
        actuales = _nombres_columnas(conn, "mascotas")
        if "fecha_nacimiento" not in actuales:
            with op.batch_alter_table("mascotas") as batch_op:
                batch_op.add_column(sa.Column("fecha_nacimiento", sa.Date(), nullable=True))
        if "fallecida" not in actuales:
            with op.batch_alter_table("mascotas") as batch_op:
                batch_op.add_column(
                    sa.Column(
                        "fallecida",
                        sa.Boolean(),
                        nullable=False,
                        server_default="0",
                    )
                )
        if "color" not in actuales:
            with op.batch_alter_table("mascotas") as batch_op:
                batch_op.add_column(sa.Column("color", sa.String(length=50), nullable=True))
        if "ix_mascotas_fecha_nacimiento" not in _nombres_indices(conn, "mascotas"):
            op.create_index(
                op.f("ix_mascotas_fecha_nacimiento"),
                "mascotas",
                ["fecha_nacimiento"],
                unique=False,
            )

    # --- Clientes ---
    if "clientes" in tablas:
        actuales = _nombres_columnas(conn, "clientes")
        if "zona_barrio" not in actuales:
            with op.batch_alter_table("clientes") as batch_op:
                batch_op.add_column(sa.Column("zona_barrio", sa.String(length=100), nullable=True))
        if "acepta_cumpleanos" not in actuales:
            with op.batch_alter_table("clientes") as batch_op:
                batch_op.add_column(
                    sa.Column(
                        "acepta_cumpleanos",
                        sa.Boolean(),
                        nullable=False,
                        server_default="0",
                    )
                )

    # --- Comercios ---
    if "comercios" in tablas:
        actuales = _nombres_columnas(conn, "comercios")
        if "habilitar_modulo_solidario" not in actuales:
            with op.batch_alter_table("comercios") as batch_op:
                batch_op.add_column(
                    sa.Column(
                        "habilitar_modulo_solidario",
                        sa.Boolean(),
                        nullable=False,
                        server_default="0",
                    )
                )
        if "zona_barrio" not in actuales:
            with op.batch_alter_table("comercios") as batch_op:
                batch_op.add_column(sa.Column("zona_barrio", sa.String(length=100), nullable=True))
        if "habilitar_cumpleanos" not in actuales:
            with op.batch_alter_table("comercios") as batch_op:
                batch_op.add_column(
                    sa.Column(
                        "habilitar_cumpleanos",
                        sa.Boolean(),
                        nullable=False,
                        server_default="0",
                    )
                )
        if "beneficio_cumpleanos" not in actuales:
            with op.batch_alter_table("comercios") as batch_op:
                batch_op.add_column(
                    sa.Column("beneficio_cumpleanos", sa.String(length=200), nullable=True)
                )


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    tablas = _nombres_tablas(conn)

    if "comercios" in tablas:
        actuales = _nombres_columnas(conn, "comercios")
        for columna in ("beneficio_cumpleanos", "habilitar_cumpleanos", "zona_barrio", "habilitar_modulo_solidario"):
            if columna in actuales:
                with op.batch_alter_table("comercios") as batch_op:
                    batch_op.drop_column(columna)

    if "clientes" in tablas:
        actuales = _nombres_columnas(conn, "clientes")
        for columna in ("acepta_cumpleanos", "zona_barrio"):
            if columna in actuales:
                with op.batch_alter_table("clientes") as batch_op:
                    batch_op.drop_column(columna)

    if "mascotas" in tablas:
        if "ix_mascotas_fecha_nacimiento" in _nombres_indices(conn, "mascotas"):
            op.drop_index(op.f("ix_mascotas_fecha_nacimiento"), table_name="mascotas")
        actuales = _nombres_columnas(conn, "mascotas")
        for columna in ("color", "fallecida", "fecha_nacimiento"):
            if columna in actuales:
                with op.batch_alter_table("mascotas") as batch_op:
                    batch_op.drop_column(columna)
