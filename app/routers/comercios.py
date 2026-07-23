from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.comercio import Comercio
from app.schemas.comercio import ComercioCreate, ComercioUpdate, ComercioResponse

router = APIRouter(prefix="/comercios", tags=["Comercios"])


@router.get("/", response_model=list[ComercioResponse])
def listar_comercios(db: Session = Depends(get_db)):
    return db.query(Comercio).all()


@router.post("/", response_model=ComercioResponse, status_code=201)
def crear_comercio(data: ComercioCreate, db: Session = Depends(get_db)):
    comercio = Comercio(**data.model_dump())
    db.add(comercio)
    db.commit()
    db.refresh(comercio)
    return comercio


@router.get("/{comercio_id}", response_model=ComercioResponse)
def obtener_comercio(comercio_id: int, db: Session = Depends(get_db)):
    comercio = db.query(Comercio).filter(Comercio.id == comercio_id).first()
    if not comercio:
        raise HTTPException(status_code=404, detail="Comercio no encontrado")
    return comercio


@router.put("/{comercio_id}", response_model=ComercioResponse)
def actualizar_comercio(comercio_id: int, data: ComercioUpdate, db: Session = Depends(get_db)):
    comercio = db.query(Comercio).filter(Comercio.id == comercio_id).first()
    if not comercio:
        raise HTTPException(status_code=404, detail="Comercio no encontrado")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(comercio, key, value)
    db.commit()
    db.refresh(comercio)
    return comercio


@router.delete("/{comercio_id}", status_code=204)
def eliminar_comercio(comercio_id: int, db: Session = Depends(get_db)):
    comercio = db.query(Comercio).filter(Comercio.id == comercio_id).first()
    if not comercio:
        raise HTTPException(status_code=404, detail="Comercio no encontrado")
    db.delete(comercio)
    db.commit()
