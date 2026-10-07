"""Validaciones defensivas sobre las migraciones de Alembic."""

import pathlib

import pytest


MIGRATIONS_DIR = pathlib.Path(__file__).resolve().parents[1] / "migrations" / "versions"


@pytest.mark.parametrize(
    "filename",
    sorted(MIGRATIONS_DIR.glob("*.py")),
)
def test_revision_id_no_excede_largo_de_alembic_version(filename: pathlib.Path) -> None:
    """Alembic version_num es VARCHAR(32). Postgres trunca ids mas largos.

    SQLite no valida el ancho, por lo que este bug solo aparece en Neon/Postgres.
    Ver alembic/ddl/impl.py:169 (String(32)).
    """

    contenido = filename.read_text(encoding="utf-8")
    for linea in contenido.splitlines():
        if linea.startswith("revision"):
            _, valor = linea.split("=", 1)
            revision = valor.strip().strip('"').strip("'")
            break
    else:
        pytest.fail(f"No se encontro 'revision' en {filename}")

    assert len(revision) <= 32, (
        f"El revision id '{revision}' en {filename.name} supera 32 caracteres. "
        "Acortar el nombre o cambiar la longitud de alembic_version.version_num."
    )
