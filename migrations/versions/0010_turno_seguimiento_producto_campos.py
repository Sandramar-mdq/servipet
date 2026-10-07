"""etapa 12.3: columnas faltantes en turnos y productos (drift de create_all)

Las tablas base (turnos, productos) las crea Base.metadata.create_all al
arrancar y este NUNCA agrega columnas a tablas ya existentes. La BD de
produccion quedo creada con un modelo viejo, asi que los endpoints que
referencian Turno.codigo_seguimiento (portal de seguimiento, agenda de
turnos) o Producto.codigo (stock) fallan con 500 (UndefinedColumn).

Esta migracion alinea el esquema con los modelos:
- turnos.codigo_seguimiento: String(20) NOT NULL UNIQUE (backfill con un
  token hex de 4 bytes, igual que app/models/turno.py::_generar_codigo_seguimiento).
- turnos.fase: String(20) nullable (fase ESPERA/BAÑO/CORTE/LISTO).
- productos.codigo / imagen_url / marca / proveedor: String nullable.
- productos.fecha_vencimiento: Date nullable.

Migracion defensiva: agrega cada columna solo si falta y es compatible con
SQLite (batch, como las 0006/0007/0008).

Revision ID: 0010_completar_turnos_productos
Revises: 0009_piezas_generadas
Create Date: 2026-10-07
"""

import secrets
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
# Maximo 32 caracteres: alembic_version.version_num es VARCHAR(32) y Postgres
# truncaria un id mas largo (tests/test_migrations.py lo valida).
revision: str = "0010_completar_turnos_productos"
down_revision: Union[str, None] = "0009_piezas_generadas"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _nombres_tablas(conn) -> set[str]:
    return set(sa.inspect(conn).get_table_names())


def _nombres_columnas(conn, tabla: str) -> set[str]:
    return {col["name"] for col in sa.inspect(conn).get_columns(tabla)}


def _nombres_indices(conn, tabla: str) -> set[str]:
    return {idx["name"] for idx in sa.inspect(conn).get_indexes(tabla) if idx.get("name")}


def _codigos_unicos(conn, cantidad: int) -> list[str]:
    """Tokens hex de 4 bytes (8 chars) que no colisionan con los existentes."""
    existentes = {
        r[0]
        for r in conn.execute(
            sa.text("SELECT codigo_seguimiento FROM turnos WHERE codigo_seguimiento IS NOT NULL")
        )
    }
    codigos: list[str] = []
    while len(codigos) < cantidad:
        nuevo = secrets.token_hex(4).upper()
        if nuevo not in existentes:
            existentes.add(nuevo)
            codigos.append(nuevo)
    return codigos


def _agregar_turnos(conn) -> None:
    actuales = _nombres_columnas(conn, "turnos")
    indices = _nombres_indices(conn, "turnos")

    if "fase" not in actuales:
        with op.batch_alter_table("turnos") as batch_op:
            batch_op.add_column(sa.Column("fase", sa.String(length=20), nullable=True))

    if "codigo_seguimiento" not in actuales:
        # 1) Agregar nullable para poder backfillear filas existentes.
        with op.batch_alter_table("turnos") as batch_op:
            batch_op.add_column(
                sa.Column("codigo_seguimiento", sa.String(length=20), nullable=True)
            )
        # 2) Backfill: cada turno ya creado recibe un codigo unico.
        ids = [r[0] for r in conn.execute(sa.text("SELECT id FROM turnos ORDER BY id"))]
        if ids:
            codigos = _codigos_unicos(conn, len(ids))
            conn.execute(
                sa.text("UPDATE turnos SET codigo_seguimiento = :codigo WHERE id = :id"),
                [{"codigo": c, "id": rid} for c, rid in zip(codigos, ids)],
            )
        # 3) NOT NULL (sin server_default: el default lo pone el modelo en Python).
        with op.batch_alter_table("turnos") as batch_op:
            batch_op.alter_column(
                "codigo_seguimiento",
                existing_type=sa.String(length=20),
                nullable=False,
            )
        # 4) Indice UNIQUE (el modelo usa index=True + unique=True).
        if "ix_turnos_codigo_seguimiento" not in indices:
            op.create_index(
                op.f("ix_turnos_codigo_seguimiento"),
                "turnos",
                ["codigo_seguimiento"],
                unique=True,
            )


def _agregar_productos(conn) -> None:
    actuales = _nombres_columnas(conn, "productos")
    indices = _nombres_indices(conn, "productos")

    columnas = [
        ("codigo", sa.String(length=50), True),
        ("imagen_url", sa.String(length=255), True),
        ("marca", sa.String(length=100), True),
        ("proveedor", sa.String(length=100), True),
        ("fecha_vencimiento", sa.Date(), True),
    ]
    for nombre, tipo, nullable in columnas:
        if nombre not in actuales:
            with op.batch_alter_table("productos") as batch_op:
                batch_op.add_column(sa.Column(nombre, tipo, nullable=nullable))

    if "ix_productos_codigo" not in indices and "codigo" in _nombres_columnas(conn, "productos"):
        op.create_index(
            op.f("ix_productos_codigo"),
            "productos",
            ["codigo"],
            unique=False,
        )


def _quitar_productos(conn) -> None:
    actuales = _nombres_columnas(conn, "productos")
    for nombre in ("fecha_vencimiento", "proveedor", "marca", "imagen_url", "codigo"):
        if nombre in actuales:
            with op.batch_alter_table("productos") as batch_op:
                batch_op.drop_column(nombre)


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    tablas = _nombres_tablas(conn)

    if "turnos" in tablas:
        _agregar_turnos(conn)
    if "productos" in tablas:
        _agregar_productos(conn)


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    tablas = _nombres_tablas(conn)

    if "productos" in tablas:
        if "ix_productos_codigo" in _nombres_indices(conn, "productos"):
            op.drop_index(op.f("ix_productos_codigo"), table_name="productos")
        _quitar_productos(conn)

    if "turnos" in tablas:
        if "ix_turnos_codigo_seguimiento" in _nombres_indices(conn, "turnos"):
            op.drop_index(op.f("ix_turnos_codigo_seguimiento"), table_name="turnos")
        actuales = _nombres_columnas(conn, "turnos")
        for nombre in ("codigo_seguimiento", "fase"):
            if nombre in actuales:
                with op.batch_alter_table("turnos") as batch_op:
                    batch_op.drop_column(nombre)