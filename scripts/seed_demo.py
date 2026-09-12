"""Script de poblado del Tenant Demo 'Peluqueria Canina Huellas' para Servipet.

Crea (si no existen): comercio, usuario operador demo, 3 clientes con mascotas,
3 turnos del dia con diferentes estados, y atenciones historial con montos.

Uso:
    python scripts/seed_demo.py

Credenciales del operador demo: se toman de DEMO_EMAIL / DEMO_PASSWORD si
estan definidas; si no, se usan los valores por defecto (demo@servipet.com /
demo123). No interfiere con las variables ADMIN_EMAIL / ADMIN_PASSWORD.

Ejecutar desde la raiz del proyecto. Idempotente.
"""

import getpass
import os
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import Base, SessionLocal, engine
from app.models import (  # noqa: F401 — registra todos los modelos en metadata
    AtencionHistorial,
    Cliente,
    Comercio,
    Mascota,
    Servicio,
    Turno,
    Usuario,
)
from app.services.auth import hash_password

# ---------------------------------------------------------------------------
# Constantes del tenant demo
# ---------------------------------------------------------------------------

COMERCIO_NOMBRE = "Peluqueria Canina Huellas"

COMERCIO_DATA = {
    "tipo_comercio": "PELUQUERIA",
    "direccion": "Av. de los Huellones 123",
    "telefono": "1144005500",
    "email": "info@huellas.com",
    "hora_apertura": "09:00",
    "hora_cierre": "18:00",
    "slot_minutos": 60,
    "activo": True,
    "permite_autoreserva_publica": True,
}

DEMO_EMAIL_DEFECTO = "demo@servipet.com"
DEMO_PASSWORD_DEFECTO = "demo123"

SERVICIOS_DATA = [
    {
        "nombre": "Baño y Corte Completo",
        "descripcion": "Baño, secado, corte de pelo y cortado de uñas",
        "precio_base": 7500.0,
        "duracion_minutos": 60,
    },
    {
        "nombre": "Corte de Uñas y Limpieza de Oidos",
        "descripcion": "Corte de uñas, limpieza de oidos y cepillado basico",
        "precio_base": 3000.0,
        "duracion_minutos": 30,
    },
]

CLIENTES_DATA = [
    {
        "nombre": "Carolina Ruiz",
        "telefono": "1133001111",
        "email": "carolina.ruiz@example.com",
        "notas": "Cliente habitual, pide baño hipoalergenico",
        "mascotas": [
            {"nombre": "Luna", "especie": "Perro", "raza": "Caniche", "peso": 8.5, "sexo": "Hembra"},
        ],
    },
    {
        "nombre": "Martin Sosa",
        "telefono": "1166002222",
        "email": "martin.sosa@example.com",
        "notas": "Trae a sus dos perros juntos",
        "mascotas": [
            {"nombre": "Toby", "especie": "Perro", "raza": "Golden Retriever", "peso": 30.0, "sexo": "Macho"},
            {"nombre": "Mora", "especie": "Perro", "raza": "Border Collie", "peso": 18.0, "sexo": "Hembra"},
        ],
    },
    {
        "nombre": "Lucia Gomez",
        "telefono": "1199003333",
        "email": "lucia.gomez@example.com",
        "notas": "Gato con problemas de piel, requiere cuidado especial",
        "mascotas": [
            {"nombre": "Mishi", "especie": "Gato", "raza": "Persa", "peso": 5.0, "sexo": "Hembra"},
        ],
    },
]

# Turnos: el turno 1 y 2 obtienen AtencionHistorial (monto cobrado); el 3 no.
TURNOS_DATA = [
    {
        "cliente_idx": 0,
        "mascota_idx": 0,
        "servicio_idx": 0,
        "hora": time(10, 0),
        "estado": "Finalizado",
        "crea_atencion": True,
    },
    {
        "cliente_idx": 1,
        "mascota_idx": 0,
        "servicio_idx": 0,
        "hora": time(12, 0),
        "estado": "Confirmado",
        "crea_atencion": True,
    },
    {
        "cliente_idx": 2,
        "mascota_idx": 0,
        "servicio_idx": 1,
        "hora": time(15, 0),
        "estado": "Pendiente",
        "crea_atencion": False,
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _buscar_o_crear(session, modelo, criterios, atributos):
    """Busca un registro por `criterios` (dict) y lo crea con ambos si no existe."""
    obj = session.query(modelo).filter_by(**criterios).first()
    if obj:
        return obj, False
    obj = modelo(**{**criterios, **atributos})
    session.add(obj)
    session.flush()
    return obj, True


def main() -> None:
    email = os.environ.get("DEMO_EMAIL", DEMO_EMAIL_DEFECTO)
    password = os.environ.get("DEMO_PASSWORD", DEMO_PASSWORD_DEFECTO)

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # ── Comercio demo ────────────────────────────────────────────────
        comercio, creado = _buscar_o_crear(
            db,
            Comercio,
            {"nombre": COMERCIO_NOMBRE},
            COMERCIO_DATA,
        )

        # ── Usuario operador demo ────────────────────────────────────────
        operador, operador_creado = _buscar_o_crear(
            db,
            Usuario,
            {"email": email},
            {
                "password_hash": hash_password(password),
                "rol": "ADMIN",
                "comercio_id": comercio.id,
                "activo": True,
            },
        )

        # ── Servicios (globales) ─────────────────────────────────────────
        servicios = {}
        for s_data in SERVICIOS_DATA:
            servicio, svc_creado = _buscar_o_crear(
                db, Servicio, {"nombre": s_data["nombre"]}, s_data
            )
            servicios[s_data["nombre"]] = servicio

        servicio_nombres = [s["nombre"] for s in SERVICIOS_DATA]

        # ── Clientes y mascotas ──────────────────────────────────────────
        clientes = []
        mascotas_por_cliente = []

        for c_data in CLIENTES_DATA:
            cliente, cli_creado = _buscar_o_crear(
                db,
                Cliente,
                {
                    "email": c_data["email"],
                    "comercio_id": comercio.id,
                },
                {
                    "nombre": c_data["nombre"],
                    "telefono": c_data["telefono"],
                    "notas": c_data["notas"],
                    "activo": True,
                },
            )
            clientes.append(cliente)

            mascotas = []
            for m_data in c_data["mascotas"]:
                mascota, masc_creado = _buscar_o_crear(
                    db,
                    Mascota,
                    {"nombre": m_data["nombre"], "cliente_id": cliente.id},
                    {
                        "especie": m_data["especie"],
                        "raza": m_data["raza"],
                        "peso": m_data["peso"],
                        "sexo": m_data["sexo"],
                        "activo": True,
                    },
                )
                mascotas.append(mascota)
            mascotas_por_cliente.append(mascotas)

        # ── Turnos del dia ───────────────────────────────────────────────
        hoy = date.today()

        for t_data in TURNOS_DATA:
            cliente = clientes[t_data["cliente_idx"]]
            mascota = mascotas_por_cliente[t_data["cliente_idx"]][t_data["mascota_idx"]]
            servicio = servicios[servicio_nombres[t_data["servicio_idx"]]]
            fecha_hora = datetime.combine(hoy, t_data["hora"])

            turno_existente = (
                db.query(Turno)
                .filter(
                    Turno.cliente_id == cliente.id,
                    Turno.mascota_id == mascota.id,
                    Turno.servicio_id == servicio.id,
                    Turno.fecha_hora == fecha_hora,
                )
                .first()
            )
            if turno_existente:
                continue

            turno = Turno(
                cliente_id=cliente.id,
                mascota_id=mascota.id,
                servicio_id=servicio.id,
                fecha_hora=fecha_hora,
                duracion_minutos=servicio.duracion_minutos,
                estado=t_data["estado"],
            )
            db.add(turno)
            db.flush()

            if t_data["crea_atencion"]:
                atencion = AtencionHistorial(
                    mascota_id=mascota.id,
                    servicio_id=servicio.id,
                    turno_id=turno.id,
                    fecha=fecha_hora,
                    monto_cobrado=servicio.precio_base,
                    medio_pago="efectivo",
                )
                db.add(atencion)

        db.commit()
        print("Datos de Demo Hub cargados con exito")

    finally:
        db.close()


if __name__ == "__main__":
    main()
