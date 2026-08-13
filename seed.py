"""Script de poblado de datos semilla (seed) para Servipet.

Uso:
    python seed.py              # crea lo que falte (idempotente)
    python seed.py --reset      # elimina los datos semilla y los recrea

Ejecutar desde la raíz del proyecto.
"""

import argparse
import sys
from datetime import date, datetime, time, timedelta

from app.database import SessionLocal, Base, engine
from app.models import AtencionHistorial, Cliente, Comercio, Mascota, Servicio, Turno

COMERCIO = {
    "nombre": "Servipet Centro",
    "direccion": "Av. Principal 123",
    "telefono": "1140000000",
    "email": "centro@servipet.com",
    "hora_apertura": "09:00",
    "hora_cierre": "18:00",
    "slot_minutos": 30,
}

SERVICIOS = [
    {
        "nombre": "Peluquería y Baño Completo",
        "descripcion": "Baño, secado, corte de pelo y cuidado de uñas",
        "precio_base": 8000.0,
        "duracion_minutos": 60,
    },
    {
        "nombre": "Consulta Veterinaria General",
        "descripcion": "Revisión general de salud de la mascota",
        "precio_base": 5000.0,
        "duracion_minutos": 30,
    },
    {
        "nombre": "Vacunación Antirrábica",
        "descripcion": "Aplicación de vacuna antirrábica anual",
        "precio_base": 3500.0,
        "duracion_minutos": 20,
    },
]

CLIENTES = [
    {
        "nombre": "María González",
        "telefono": "1122334455",
        "email": "maria.gonzalez@example.com",
        "notas": "Cliente semilla de prueba",
    },
    {
        "nombre": "Juan Pérez",
        "telefono": "1199887766",
        "email": "juan.perez@example.com",
        "notas": "Cliente semilla de prueba",
    },
]

MASCOTAS = [
    {
        "cliente_idx": 0,
        "nombre": "Rocky",
        "especie": "Perro",
        "raza": "Golden Retriever",
        "peso": 28.5,
        "edad": 4,
        "sexo": "Macho",
        "observaciones": "Muy activo",
        "alergias": None,
    },
    {
        "cliente_idx": 0,
        "nombre": "Luna",
        "especie": "Gato",
        "raza": "Persa",
        "peso": 4.2,
        "edad": 2,
        "sexo": "Hembra",
        "observaciones": None,
        "alergias": "Pulgas",
    },
    {
        "cliente_idx": 1,
        "nombre": "Toby",
        "especie": "Perro",
        "raza": "French Poodle",
        "peso": 6.8,
        "edad": 5,
        "sexo": "Macho",
        "observaciones": None,
        "alergias": None,
    },
]

# Turnos: estados Pendiente / Confirmado / Finalizado
TURNOS = [
    {
        "mascota_idx": 0,
        "servicio_nombre": "Consulta Veterinaria General",
        "cuando": "hoy",
        "hora": time(10, 0),
        "estado": "Confirmado",
    },
    {
        "mascota_idx": 2,
        "servicio_nombre": "Peluquería y Baño Completo",
        "cuando": "mañana",
        "hora": time(11, 0),
        "estado": "Pendiente",
    },
    {
        "mascota_idx": 1,
        "servicio_nombre": "Vacunación Antirrábica",
        "cuando": "pasado",
        "hora": time(15, 0),
        "estado": "Finalizado",
    },
]


ULTIMO_INICIO = time(17, 30)


def next_occurrence(hora: time, dias_atras: int = 0) -> datetime:
    """Próxima fecha a `hora`; para 'mañana' o 'pasado' usa offsets."""
    if dias_atras:
        base = date.today() + timedelta(days=dias_atras)
        return datetime.combine(base, hora)
    return _hoy_futuro(hora)


def _hoy_futuro(hora: time) -> datetime:
    """Hora fija hoy si aún es futura; si ya pasó, elige un slot hoy a ~90 min de ahora."""
    candidato = datetime.combine(date.today(), hora)
    if candidato > datetime.now():
        return candidato
    ahora = datetime.now()
    redondeo = (ahora + timedelta(minutes=90)).replace(minute=0, second=0, microsecond=0)
    tope_inicio = datetime.combine(date.today(), ULTIMO_INICIO)
    if redondeo <= tope_inicio:
        return redondeo
    return candidato + timedelta(days=1)


def _turno_fecha(spec: dict) -> datetime:
    if spec["cuando"] == "hoy":
        return next_occurrence(spec["hora"])
    if spec["cuando"] == "mañana":
        return next_occurrence(spec["hora"], dias_atras=1)
    if spec["cuando"] == "pasado":
        return next_occurrence(spec["hora"], dias_atras=-3)
    raise ValueError(f"cuando invalido: {spec['cuando']}")


def reset_semilla(db):
    """Elimina únicamente los registros semilla, en orden de FK."""
    clientes = db.query(Cliente).filter(Cliente.telefono.in_([c["telefono"] for c in CLIENTES])).all()
    cliente_ids = [c.id for c in clientes]
    mascotas = db.query(Mascota).filter(Mascota.cliente_id.in_(cliente_ids)).all() if cliente_ids else []
    mascota_ids = [m.id for m in mascotas]

    if mascota_ids:
        db.query(AtencionHistorial).filter(AtencionHistorial.mascota_id.in_(mascota_ids)).delete(synchronize_session=False)
    if cliente_ids:
        db.query(Turno).filter(Turno.cliente_id.in_(cliente_ids)).delete(synchronize_session=False)
    if mascota_ids:
        db.query(Mascota).filter(Mascota.id.in_(mascota_ids)).delete(synchronize_session=False)
    if cliente_ids:
        db.query(Cliente).filter(Cliente.id.in_(cliente_ids)).delete(synchronize_session=False)
    db.query(Servicio).filter(Servicio.nombre.in_([s["nombre"] for s in SERVICIOS])).delete(synchronize_session=False)
    db.query(Comercio).filter(Comercio.nombre == COMERCIO["nombre"]).delete(synchronize_session=False)
    db.commit()
    print(f"[RESET] Se eliminaron datos semilla previos "
          f"({len(cliente_ids)} clientes, {len(mascota_ids)} mascotas)")


def poblar(db, reset: bool = False) -> None:
    """Crea los datos semilla de forma idempotente. Si `reset=True`, los recrea."""
    if reset:
        reset_semilla(db)

    creados = {}
    saltados = {}

    def contador(entidad):
        return creados.setdefault(entidad, 0), saltados.setdefault(entidad, 0)

    # Comercio
    comercio = db.query(Comercio).filter(Comercio.nombre == COMERCIO["nombre"]).first()
    if not comercio:
        comercio = Comercio(**COMERCIO)
        db.add(comercio)
        db.flush()
        creados["Comercio"] = 1
    else:
        saltados["Comercio"] = 1

    # Servicios
    servicios_creados, servicios_saltados = contador("Servicios")
    servicios = {}
    for s in SERVICIOS:
        servicio = db.query(Servicio).filter(Servicio.nombre == s["nombre"]).first()
        if not servicio:
            servicio = Servicio(**s)
            db.add(servicio)
            db.flush()
            servicios_creados += 1
        else:
            servicios_saltados += 1
        servicios[s["nombre"]] = servicio
    creados["Servicios"], saltados["Servicios"] = servicios_creados, servicios_saltados

    # Clientes
    clientes_creados, clientes_saltados = contador("Clientes")
    clientes = {}
    for c in CLIENTES:
        cliente = db.query(Cliente).filter(Cliente.telefono == c["telefono"]).first()
        if not cliente:
            cliente = Cliente(comercio_id=comercio.id, **{k: v for k, v in c.items() if k != "notas"}, notas=c["notas"])
            db.add(cliente)
            db.flush()
            clientes_creados += 1
        else:
            clientes_saltados += 1
        clientes[c["telefono"]] = cliente
    creados["Clientes"], saltados["Clientes"] = clientes_creados, clientes_saltados

    # Mascotas
    mascotas_creadas, mascotas_saltadas = contador("Mascotas")
    mascotas = []
    for m in MASCOTAS:
        cliente = clientes[CLIENTES[m["cliente_idx"]]["telefono"]]
        mascota = (
            db.query(Mascota)
            .filter(Mascota.cliente_id == cliente.id, Mascota.nombre == m["nombre"])
            .first()
        )
        if not mascota:
            mascota = Mascota(cliente_id=cliente.id, **{k: v for k, v in m.items() if k != "cliente_idx"})
            db.add(mascota)
            db.flush()
            mascotas_creadas += 1
        else:
            mascotas_saltadas += 1
        mascotas.append(mascota)
    creados["Mascotas"], saltados["Mascotas"] = mascotas_creadas, mascotas_saltadas

    # Turnos
    turnos_creados, turnos_saltados = contador("Turnos")
    atenciones_creadas, atenciones_saltadas = contador("Atenciones")
    for t in TURNOS:
        cliente = clientes[CLIENTES[MASCOTAS[t["mascota_idx"]]["cliente_idx"]]["telefono"]]
        mascota = mascotas[t["mascota_idx"]]
        servicio = servicios[t["servicio_nombre"]]
        fecha_hora = _turno_fecha(t)

        turno = (
            db.query(Turno)
            .filter(
                Turno.cliente_id == cliente.id,
                Turno.mascota_id == mascota.id,
                Turno.servicio_id == servicio.id,
                Turno.fecha_hora == fecha_hora,
                Turno.estado == t["estado"],
            )
            .first()
        )
        if not turno:
            turno = Turno(
                cliente_id=cliente.id,
                mascota_id=mascota.id,
                servicio_id=servicio.id,
                fecha_hora=fecha_hora,
                duracion_minutos=servicio.duracion_minutos,
                estado=t["estado"],
                observaciones="Turno generado por seed",
            )
            db.add(turno)
            db.flush()
            turnos_creados += 1
        else:
            turnos_saltados += 1

        if t["estado"] == "Finalizado":
            atencion = (
                db.query(AtencionHistorial)
                .filter(
                    AtencionHistorial.mascota_id == mascota.id,
                    AtencionHistorial.servicio_id == servicio.id,
                    AtencionHistorial.fecha == fecha_hora,
                )
                .first()
            )
            if not atencion:
                atencion = AtencionHistorial(
                    mascota_id=mascota.id,
                    servicio_id=servicio.id,
                    fecha=fecha_hora,
                    observaciones="Atencion generada por seed",
                    monto_cobrado=servicio.precio_base,
                    medio_pago="efectivo",
                )
                db.add(atencion)
                atenciones_creadas += 1
            else:
                atenciones_saltadas += 1

    creados["Turnos"], saltados["Turnos"] = turnos_creados, turnos_saltados
    creados["Atenciones"], saltados["Atenciones"] = atenciones_creadas, atenciones_saltadas

    db.commit()

    # Resumen
    print("\n=== Resumen de seed ===")
    for entidad, total in [
        ("Comercio", 1),
        ("Servicios", len(SERVICIOS)),
        ("Clientes", len(CLIENTES)),
        ("Mascotas", len(MASCOTAS)),
        ("Turnos", len(TURNOS)),
        ("Atenciones", 1),
    ]:
        c = creados.get(entidad, 0)
        s = saltados.get(entidad, 0)
        estado = "creado" if c else "ya existia"
        print(f"  {entidad:<12} {c}/{total} {estado}{(' (' + str(s) + ' omitido/s)') if s and not c else ''}")

    print("\nSeed completado.")
    print("Clientes de prueba (login OTP):")
    for c in CLIENTES:
        print(f"  - {c['nombre']} / telefono {c['telefono']} (el codigo se imprime en consola del server)")


def main():
    parser = argparse.ArgumentParser(description="Poblar Servipet con datos semilla")
    parser.add_argument("--reset", action="store_true", help="Elimina los datos semilla y los recrea")
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        poblar(db, reset=args.reset)
    finally:
        db.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
