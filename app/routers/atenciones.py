from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.atencion import AtencionHistorial
from app.schemas.atencion import AtencionCreate, AtencionUpdate, AtencionResponse

router = APIRouter(prefix="/atenciones", tags=["Atenciones"])


@router.get("/", response_model=list[AtencionResponse])
def listar_atenciones(mascota_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(AtencionHistorial)
    if mascota_id is not None:
        query = query.filter(AtencionHistorial.mascota_id == mascota_id)
    return query.order_by(AtencionHistorial.fecha.desc()).all()


@router.post("/", response_model=AtencionResponse, status_code=201)
def crear_atencion(data: AtencionCreate, db: Session = Depends(get_db)):
    atencion = AtencionHistorial(**data.model_dump())
    db.add(atencion)
    db.commit()
    db.refresh(atencion)
    return atencion


@router.get("/{atencion_id}", response_model=AtencionResponse)
def obtener_atencion(atencion_id: int, db: Session = Depends(get_db)):
    atencion = db.query(AtencionHistorial).filter(AtencionHistorial.id == atencion_id).first()
    if not atencion:
        raise HTTPException(status_code=404, detail="Atencion no encontrada")
    return atencion


@router.put("/{atencion_id}", response_model=AtencionResponse)
def actualizar_atencion(atencion_id: int, data: AtencionUpdate, db: Session = Depends(get_db)):
    atencion = db.query(AtencionHistorial).filter(AtencionHistorial.id == atencion_id).first()
    if not atencion:
        raise HTTPException(status_code=404, detail="Atencion no encontrada")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(atencion, key, value)
    db.commit()
    db.refresh(atencion)
    return atencion


@router.delete("/{atencion_id}", status_code=204)
def eliminar_atencion(atencion_id: int, db: Session = Depends(get_db)):
    atencion = db.query(AtencionHistorial).filter(AtencionHistorial.id == atencion_id).first()
    if not atencion:
        raise HTTPException(status_code=404, detail="Atencion no encontrada")
    db.delete(atencion)
    db.commit()
