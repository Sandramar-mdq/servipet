"""Registra el usuario SuperAdmin inicial en la base de datos de Servipet.

Representacion del SuperAdmin: rol="ADMIN" con comercio_id=None (ADMIN global
sin comercio asociado, segun la docstring del modelo Usuario).

Credenciales: se toman de las variables de entorno ADMIN_EMAIL / ADMIN_PASSWORD
si estan definidas (tambien via .env); si no, se solicitan de forma
interactiva por consola (email con input, password con getpass).

Uso:
    python scripts/create_superadmin.py

Ejecutar desde la raiz del proyecto.
"""

import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.models import Usuario
from app.services.auth import hash_password


def obtener_credenciales() -> tuple[str, str]:
    """Devuelve (email, password). Prioriza variables de entorno sobre el prompt."""
    email = os.environ.get("ADMIN_EMAIL")
    password = os.environ.get("ADMIN_PASSWORD")
    if email and password:
        return email.strip(), password

    if not email:
        email = input("Email del SuperAdmin: ").strip()
    if not password:
        password = getpass.getpass("Password del SuperAdmin: ")

    if not email:
        raise SystemExit("Error: el email no puede estar vacio.")
    if not password:
        raise SystemExit("Error: el password no puede estar vacio.")
    return email, password


def main() -> None:
    email, password = obtener_credenciales()

    from app.database import Base, engine

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        existente = db.query(Usuario).filter(Usuario.email == email).first()
        if existente:
            print(f"El email '{email}' ya existe en la base de datos. No se realizaron cambios.")
            return

        usuario = Usuario(
            email=email,
            password_hash=hash_password(password),
            rol="ADMIN",
            comercio_id=None,
            activo=True,
        )
        db.add(usuario)
        db.commit()
        print("SuperAdmin creado con exito")
    finally:
        db.close()


if __name__ == "__main__":
    main()
