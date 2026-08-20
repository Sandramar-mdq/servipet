"""Script rápido para insertar un turno ficticio de prueba en el portal público.

Uso:  python seed_test_turno.py
"""
from datetime import datetime, timedelta

from app.database import SessionLocal, Base, engine
from app.models.comercio import Comercio
from app.models.cliente import Cliente
from app.models.mascota import Mascota
from app.models.servicio import Servicio
from app.models.turno import Turno

Base.metadata.create_all(bind=engine)
db = SessionLocal()

try:
    db.merge(Comercio(id=1, nombre="Comercio Demo", tipo_comercio="VETERINARIA", activo=True))
    db.commit()

    if not db.query(Cliente).filter(Cliente.nombre == "Maria Lopez").first():
        cliente = Cliente(nombre="Maria Lopez", comercio_id=1, telefono="1166667777")
        db.add(cliente)
        db.flush()
    else:
        cliente = db.query(Cliente).filter(Cliente.nombre == "Maria Lopez").first()

    if not db.query(Mascota).filter(Mascota.nombre == "Toby").first():
        mascota = Mascota(nombre="Toby", cliente_id=cliente.id, especie="Perro", raza="Labrador", foto_webp=None)
        db.add(mascota)
        db.flush()
    else:
        mascota = db.query(Mascota).filter(Mascota.nombre == "Toby").first()

    if not db.query(Servicio).filter(Servicio.nombre == "Baño y Corte").first():
        servicio = Servicio(nombre="Baño y Corte", precio_base=4500.0, duracion_minutos=60)
        db.add(servicio)
        db.flush()
    else:
        servicio = db.query(Servicio).filter(Servicio.nombre == "Baño y Corte").first()

    turno = Turno(
        cliente_id=cliente.id,
        mascota_id=mascota.id,
        servicio_id=servicio.id,
        fecha_hora=datetime.now() + timedelta(hours=2),
        duracion_minutos=60,
        estado="PENDIENTE",
        fase="BAÑO",
        codigo_seguimiento="TEST1234",
    )
    db.add(turno)
    db.commit()

    print("OK — Turno de prueba creado:")
    print(f"   Mascota:   {mascota.nombre}")
    print(f"   Servicio:  {servicio.nombre}")
    print(f"   Fase:      {turno.fase}")
    print(f"   Codigo:    {turno.codigo_seguimiento}")
    print(f"   URL:       http://127.0.0.1:8000/portal/seguimiento/{turno.codigo_seguimiento}")
finally:
    db.close()
