from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.cliente import Cliente
from app.models.mascota import Mascota
from app.models.servicio import Servicio
from app.models.turno import Turno

router = APIRouter(tags=["Seed"])


@router.get("/seed/turno-test")
def seed_turno_test(db: Session = Depends(get_db)):
    cliente = db.query(Cliente).filter(Cliente.nombre == "Maria Lopez").first()
    if not cliente:
        cliente = Cliente(nombre="Maria Lopez", comercio_id=1, telefono="1166667777")
        db.add(cliente)
        db.flush()

    mascota = db.query(Mascota).filter(Mascota.nombre == "Toby").first()
    if not mascota:
        mascota = Mascota(nombre="Toby", cliente_id=cliente.id, especie="Perro", raza="Labrador")
        db.add(mascota)
        db.flush()

    servicio = db.query(Servicio).filter(Servicio.nombre == "Baño y Corte").first()
    if not servicio:
        servicio = Servicio(nombre="Baño y Corte", precio_base=4500.0, duracion_minutos=60)
        db.add(servicio)
        db.flush()

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

    return {
        "ok": True,
        "codigo": turno.codigo_seguimiento,
        "url": f"/portal/seguimiento/{turno.codigo_seguimiento}",
    }
