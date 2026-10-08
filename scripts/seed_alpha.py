"""Seed Alpha: crea el tenant base y la jerarquia RBAC de 4 niveles de Servipet.

Reemplaza a `scripts/seed_demo.py` (absorbe su dataset operativo, que ahora es
opcional) y a `scripts/create_superadmin.py` (caso particular del nivel 1).

Niveles que siembra
-------------------
1. SuperAdmin      -> rol "ADMIN" con comercio_id=None. Acceso transversal.
2. Admin de Comercio -> rol "ADMIN" asignado al comercio base.
3. Empleado (staff) -> rol "EMPLEADO" asignado al comercio base.
4. Cliente         -> rol "CLIENTE" asignado al comercio base + fila `Cliente`
                      vinculada por `usuario_id`.
5. Anonimo         -> sin sesion. NO se siembra: no existe fila en la BD.

Idempotencia
------------
Todo se resuelve con `_buscar_o_crear`, que busca por clave natural y solo
inserta. En los `Usuario` la clave es el `email` (`unique=True, index=True` en
`app/models/usuario.py`). El helper NUNCA actualiza una fila existente, asi que
correr el script N veces en redeploys no duplica registros ni pisa `password_hash`
con un hash nuevo. Para rotar una clave hay que hacerlo a mano.

Credenciales
------------
Se leen EXCLUSIVAMENTE de variables de entorno. No hay defaults ni valores
hardcodeados: si falta alguna, el script aborta con `SystemExit`.

    ADMIN_EMAIL / ADMIN_PASSWORD            SuperAdmin
    ALPHA_ADMIN_EMAIL / ALPHA_ADMIN_PASSWORD    Admin de Comercio
    ALPHA_EMPLEADO_EMAIL / ALPHA_EMPLEADO_PASSWORD    Empleado
    ALPHA_CLIENTE_EMAIL / ALPHA_CLIENTE_PASSWORD    Cliente
    ALPHA_CLIENTE_NOMBRE                  Nombre del perfil Cliente (opcional)
    ALPHA_CLIENTE_TELEFONO                Telefono del perfil Cliente (opcional,
                                         habilita el ingreso por codigo SMS/OTP)

Opcionales:
    SEED_ALPHA_DEMO=1    ademas siembra servicios, clientes, mascotas y turnos
                         (el dataset que vivia en seed_demo.py). Apagado por
                         defecto para no meter agenda de prueba en produccion.

Uso:
    python scripts/seed_alpha.py
    SEED_ALPHA_DEMO=1 python scripts/seed_alpha.py

Ejecutar desde la raiz del proyecto.
"""

import os
import sys
from datetime import date, datetime, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import Base, SessionLocal, engine
from app.models import (  # noqa: F401 - registra todos los modelos en metadata
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
# Constantes
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
    "plan": "PRO",
    "estado": "ACTIVO",
    "permite_autoreserva_publica": True,
    # Los tres opt-in quedan encendidos a proposito: sin ellos los endpoints de
    # la red comunitaria y de marketing responden 403 por modulo (no por RBAC) y
    # la matriz de `scripts/verificar_rbac.py` no puede distinguir los dos casos.
    "habilitar_red_comunitaria": True,
    "habilitar_modulo_solidario": True,
    "habilitar_cumpleanos": True,
    "acepta_terminos_beta": True,
}

# (prefijo de env, rol, nombre legible)
NIVELES = (
    ("ADMIN", "ADMIN", "SuperAdmin"),
    ("ALPHA_ADMIN", "ADMIN", "Admin de Comercio"),
    ("ALPHA_EMPLEADO", "EMPLEADO", "Empleado (staff)"),
    ("ALPHA_CLIENTE", "CLIENTE", "Cliente"),
)

# bcrypt trunca (o, desde 5.0, rechaza) el input pasado 72 bytes. Validamos
# antes de hashear para fallar con un mensaje util en vez de un ValueError.
MAX_BYTES_PASSWORD = 72

SERVICIOS_DATA = [
    {
        "nombre": "Bano y Corte Completo",
        "descripcion": "Bano, secado, corte de pelo y cortado de unas",
        "precio_base": 7500.0,
        "duracion_minutos": 60,
    },
    {
        "nombre": "Corte de Unas y Limpieza de Oidos",
        "descripcion": "Corte de unas, limpieza de oidos y cepillado basico",
        "precio_base": 3000.0,
        "duracion_minutos": 30,
    },
]

CLIENTES_DATA = [
    {
        "nombre": "Carolina Ruiz",
        "telefono": "1133001111",
        "email": "carolina.ruiz@example.com",
        "notas": "Cliente habitual, pide bano hipoalergenico",
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
            {"nombre": "Mishi", "especie": "Gato", "raza": "Persa", "peso": 5.0,
             "sexo": "Hembra", "fecha_nacimiento": date(2022, 4, 18)},
        ],
    },
    {
        "nombre": "Maria Lopez",
        "telefono": "1122334455",
        "email": "maria.lopez@example.com",
        "notas": "Perro ansioso en la peluqueria, pide turno temprano",
        "mascotas": [
            {"nombre": "Rocky", "especie": "Perro", "raza": "Labrador", "peso": 25.0,
             "sexo": "Macho", "fecha_nacimiento": date(2023, 5, 10)},
            {"nombre": "Simba", "especie": "Gato", "raza": "Comun Europeo", "peso": 4.5,
             "sexo": "Macho", "fecha_nacimiento": date(2022, 1, 20)},
        ],
    },
    {
        "nombre": "Juan Perez",
        "telefono": "1177889900",
        "email": "juan.perez@example.com",
        "notas": "Prefiere turnos a la manana; autorizo cumpleanios",
        "acepta_cumpleanos": True,
        "mascotas": [
            {"nombre": "Max", "especie": "Perro", "raza": "Bulldog Frances", "peso": 12.0,
             "sexo": "Macho", "fecha_nacimiento": date(2021, 9, 14)},
        ],
    },
    {
        "nombre": "Sofia Alvarez",
        "telefono": "1188996677",
        "email": "sofia.alvarez@example.com",
        "notas": "Cliente nueva, mascota rescatada; autorizo cumpleanios",
        "acepta_cumpleanos": True,
        "mascotas": [
            {"nombre": "Nala", "especie": "Perro", "raza": "Mestiza", "peso": 22.0,
             "sexo": "Hembra", "fecha_nacimiento": date(2020, 3, 30)},
        ],
    },
    {
        "nombre": "Pedro Gutierrez",
        "telefono": "1155667788",
        "email": "pedro.gutierrez@example.com",
        "notas": "Trae gato y caniche toy",
        "mascotas": [
            {"nombre": "Peluche", "especie": "Gato", "raza": "Siames", "peso": 4.0,
             "sexo": "Macho", "fecha_nacimiento": date(2024, 7, 19)},
            {"nombre": "Kiwi", "especie": "Perro", "raza": "Caniche Toy", "peso": 3.5,
             "sexo": "Hembra", "fecha_nacimiento": date(2023, 11, 2)},
        ],
    },
]

# El turno 1 y 2 generan AtencionHistorial (monto cobrado); el resto no.
# Los indices referencian CLIENTES_DATA (0..6) y su lista de mascotas.
TURNOS_DATA = [
    {"cliente_idx": 0, "mascota_idx": 0, "servicio_idx": 0, "hora": time(10, 0),
     "estado": "Finalizado", "crea_atencion": True},
    {"cliente_idx": 1, "mascota_idx": 0, "servicio_idx": 0, "hora": time(12, 0),
     "estado": "Confirmado", "crea_atencion": True},
    {"cliente_idx": 2, "mascota_idx": 0, "servicio_idx": 1, "hora": time(15, 0),
     "estado": "Pendiente", "crea_atencion": False},
    {"cliente_idx": 3, "mascota_idx": 0, "servicio_idx": 0, "hora": time(11, 0),
     "estado": "Confirmado", "crea_atencion": False},
    {"cliente_idx": 4, "mascota_idx": 0, "servicio_idx": 1, "hora": time(14, 0),
     "estado": "Pendiente", "crea_atencion": False},
]


# ---------------------------------------------------------------------------
# Credenciales
# ---------------------------------------------------------------------------


def _credencial(prefijo: str) -> tuple[str, str]:
    """Lee <PREFIJO>_EMAIL / <PREFIJO>_PASSWORD del entorno.

    No hay fallback a input(), getpass ni valores por defecto: un seed que
    arranca con una password inventada es peor que un seed que no arranca.
    """
    email = (os.environ.get(f"{prefijo}_EMAIL") or "").strip()
    password = os.environ.get(f"{prefijo}_PASSWORD") or ""

    faltantes = [
        var
        for var, valor in ((f"{prefijo}_EMAIL", email), (f"{prefijo}_PASSWORD", password))
        if not valor
    ]
    if faltantes:
        raise SystemExit(
            "Error: faltan variables de entorno para "
            f"{prefijo}: {', '.join(faltantes)}. Definelas en .env o en el "
            "proveedor de hosting antes de correr el seed."
        )

    if "@" not in email:
        raise SystemExit(f"Error: {prefijo}_EMAIL no parece un email valido: {email!r}")

    if len(password.encode("utf-8")) > MAX_BYTES_PASSWORD:
        raise SystemExit(
            f"Error: {prefijo}_PASSWORD supera los {MAX_BYTES_PASSWORD} bytes que "
            "acepta bcrypt. Usa una clave mas corta."
        )

    return email, password


def _validar_emails_distintos(credenciales: dict[str, tuple[str, str]]) -> None:
    vistos: dict[str, str] = {}
    for prefijo, (email, _) in credenciales.items():
        clave = email.lower()
        if clave in vistos:
            raise SystemExit(
                f"Error: {prefijo}_EMAIL y {vistos[clave]}_EMAIL son el mismo "
                f"({email}). Cada nivel necesita un email propio."
            )
        vistos[clave] = prefijo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _buscar_o_crear(session, modelo, criterios, atributos):
    """Busca un registro por `criterios` y lo crea si no existe.

    Devuelve (obj, creado). Si el registro ya existe se devuelve tal cual: no se
    tocan atributos, en particular `password_hash`.
    """
    obj = session.query(modelo).filter_by(**criterios).first()
    if obj:
        return obj, False
    obj = modelo(**{**criterios, **atributos})
    session.add(obj)
    session.flush()
    return obj, True


def _crear_usuario(session, email, password, rol, comercio_id):
    usuario, creado = _buscar_o_crear(
        session,
        Usuario,
        {"email": email},
        {
            "password_hash": hash_password(password),
            "rol": rol,
            "comercio_id": comercio_id,
            "activo": True,
        },
    )
    return usuario, creado


# ---------------------------------------------------------------------------
# Seeds
# ---------------------------------------------------------------------------


def _seed_demo(session, comercio) -> list[str]:
    """Dataset operativo absorbido de seed_demo.py (solo con SEED_ALPHA_DEMO=1)."""
    notas = []

    servicios = []
    for s_data in SERVICIOS_DATA:
        servicio, _ = _buscar_o_crear(session, Servicio, {"nombre": s_data["nombre"]}, s_data)
        servicios.append(servicio)

    clientes = []
    mascotas_por_cliente = []
    for c_data in CLIENTES_DATA:
        cliente, _ = _buscar_o_crear(
            session,
            Cliente,
            {"email": c_data["email"], "comercio_id": comercio.id},
            {
                "nombre": c_data["nombre"],
                "telefono": c_data["telefono"],
                "notas": c_data["notas"],
                "acepta_cumpleanos": c_data.get("acepta_cumpleanos", False),
                "activo": True,
            },
        )
        clientes.append(cliente)

        mascotas = []
        for m_data in c_data["mascotas"]:
            mascota, _ = _buscar_o_crear(
                session,
                Mascota,
                {"nombre": m_data["nombre"], "cliente_id": cliente.id},
                {**m_data, "activo": True},
            )
            mascotas.append(mascota)
        mascotas_por_cliente.append(mascotas)

    hoy = date.today()
    for t_data in TURNOS_DATA:
        cliente = clientes[t_data["cliente_idx"]]
        mascota = mascotas_por_cliente[t_data["cliente_idx"]][t_data["mascota_idx"]]
        servicio = servicios[t_data["servicio_idx"]]
        fecha_hora = datetime.combine(hoy, t_data["hora"])

        existente = (
            session.query(Turno)
            .filter(
                Turno.cliente_id == cliente.id,
                Turno.mascota_id == mascota.id,
                Turno.servicio_id == servicio.id,
                Turno.fecha_hora == fecha_hora,
            )
            .first()
        )
        if existente:
            continue

        turno = Turno(
            cliente_id=cliente.id,
            mascota_id=mascota.id,
            servicio_id=servicio.id,
            fecha_hora=fecha_hora,
            duracion_minutos=servicio.duracion_minutos,
            estado=t_data["estado"],
        )
        session.add(turno)
        session.flush()

        if t_data["crea_atencion"]:
            session.add(
                AtencionHistorial(
                    mascota_id=mascota.id,
                    servicio_id=servicio.id,
                    turno_id=turno.id,
                    fecha=fecha_hora,
                    monto_cobrado=servicio.precio_base,
                    medio_pago="efectivo",
                )
            )

    notas.append("dataset demo (servicios, clientes, mascotas, turnos)")
    return notas


def main() -> None:
    credenciales = {prefijo: _credencial(prefijo) for prefijo, _, _ in NIVELES}
    _validar_emails_distintos(credenciales)

    Base.metadata.create_all(bind=engine)

    session = SessionLocal()
    try:
        comercio, comercio_creado = _buscar_o_crear(
            session, Comercio, {"nombre": COMERCIO_NOMBRE}, COMERCIO_DATA
        )
        comercio_id = comercio.id

        filas = []
        for prefijo, rol, etiqueta in NIVELES:
            email, password = credenciales[prefijo]
            # El SuperAdmin es el unico nivel sin comercio: es lo que
            # `require_superadmin` (app/dependencies/auth.py) verifica para dar
            # acceso transversal.
            comercio_id_usuario = None if prefijo == "ADMIN" else comercio_id
            usuario, creado = _crear_usuario(
                session, email, password, rol, comercio_id_usuario
            )
            filas.append((etiqueta, rol, comercio_id_usuario, creado))

            # El nivel Cliente necesita fila `Cliente`: `Usuario` no tiene columna
            # de nombre y `portal._require_cliente` devuelve 404 sin `cliente_profile`.
            if prefijo == "ALPHA_CLIENTE":
                _buscar_o_crear(
                    session,
                    Cliente,
                    {"usuario_id": usuario.id},
                    {
                        "nombre": os.environ.get("ALPHA_CLIENTE_NOMBRE", "Cliente Alpha"),
                        "telefono": os.environ.get("ALPHA_CLIENTE_TELEFONO", ""),
                        "email": email,
                        "comercio_id": comercio_id,
                        "activo": True,
                    },
                )

        extra = []
        if os.environ.get("SEED_ALPHA_DEMO") == "1":
            extra = _seed_demo(session, comercio)

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    print(
        f"Comercio: {COMERCIO_NOMBRE} (id={comercio_id}) "
        f"[{'creado' if comercio_creado else 'ya existia'}]"
    )
    print()
    print(f"{'nivel':<22}{'rol':<10}{'comercio_id':<14}{'estado'}")
    print("-" * 64)
    for etiqueta, rol, comercio_id_usuario, creado in filas:
        cid = comercio_id_usuario if comercio_id_usuario is not None else "NULL (global)"
        print(f"{etiqueta:<22}{rol:<10}{str(cid):<14}{'creado' if creado else 'ya existia'}")
    if extra:
        print()
        print("Extra: " + ", ".join(extra))
    print()
    print("Anonimo: sin sesion, sin registro en la BD.")
    print("Seed Alpha OK.")


if __name__ == "__main__":
    main()