from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.mascota import Mascota
from app.schemas.mascota import MascotaCreate, MascotaUpdate, MascotaResponse

router = APIRouter(prefix="/mascotas", tags=["Mascotas"])


@router.get("/", response_model=list[MascotaResponse])
def listar_mascotas(cliente_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(Mascota)
    if cliente_id is not None:
        query = query.filter(Mascota.cliente_id == cliente_id)
    return query.all()


@router.post("/", response_model=MascotaResponse, status_code=201)
def crear_mascota(data: MascotaCreate, db: Session = Depends(get_db)):
    mascota = Mascota(**data.model_dump())
    db.add(mascota)
    db.commit()
    db.refresh(mascota)
    return mascota


@router.get("/{mascota_id}", response_model=MascotaResponse)
def obtener_mascota(mascota_id: int, db: Session = Depends(get_db)):
    mascota = db.query(Mascota).filter(Mascota.id == mascota_id).first()
    if not mascota:
        raise HTTPException(status_code=404, detail="Mascota no encontrada")
    return mascota


@router.put("/{mascota_id}", response_model=MascotaResponse)
def actualizar_mascota(mascota_id: int, data: MascotaUpdate, db: Session = Depends(get_db)):
    mascota = db.query(Mascota).filter(Mascota.id == mascota_id).first()
    if not mascota:
        raise HTTPException(status_code=404, detail="Mascota no encontrada")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(mascota, key, value)
    db.commit()
    db.refresh(mascota)
    return mascota


@router.delete("/{mascota_id}", status_code=204)
def eliminar_mascota(mascota_id: int, db: Session = Depends(get_db)):
    mascota = db.query(Mascota).filter(Mascota.id == mascota_id).first()
    if not mascota:
        raise HTTPException(status_code=404, detail="Mascota no encontrada")
    mascota.activo = False
    db.commit()
