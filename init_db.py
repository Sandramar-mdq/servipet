"""Inicializacion de la base de datos para produccion (o local).

Uso:
    python init_db.py            # crea las tablas si no existen (idempotente)
    python init_db.py --seed     # ademas puebla los datos semilla

Ejecutar desde la raiz del proyecto. El primer despliegue en Render/Koyeb
puede invocarlo via preDeployCommand (ver render.yaml y DEPLOYMENT.md).
"""

import argparse

from app.database import Base, SessionLocal, engine
from app.models import (  # noqa: F401  (registra todos los modelos en metadata)
    AtencionHistorial,
    Cliente,
    ClienteOTP,
    Comercio,
    Mascota,
    Servicio,
    Turno,
)


def main():
    parser = argparse.ArgumentParser(description="Crear tablas y opcionalmente sembrar datos")
    parser.add_argument("--seed", action="store_true", help="Poblar datos semilla tras crear tablas")
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    print("Tablas creadas/verificadas correctamente.")

    if args.seed:
        from seed import poblar

        db = SessionLocal()
        try:
            poblar(db)
        finally:
            db.close()


if __name__ == "__main__":
    main()
