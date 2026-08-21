from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.comercio import Comercio
from app.models.usuario import Usuario
from app.schemas.comercio import ComercioCreate, ComercioOptInRequest, ComercioUpdate, ComercioResponse

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


@router.patch("/{comercio_id}/opt-in", response_model=ComercioResponse)
def configurar_opt_in_red_comunitaria(
    comercio_id: int,
    datos: ComercioOptInRequest,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Activa/desactiva la red comunitaria (solo ADMIN del comercio o global)."""
    if current_user.rol != "ADMIN":
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    if current_user.comercio_id is not None and current_user.comercio_id != comercio_id:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")

    comercio = db.query(Comercio).filter(Comercio.id == comercio_id).first()
    if not comercio:
        raise HTTPException(status_code=404, detail="Comercio no encontrado")

    comercio.habilitar_red_comunitaria = datos.habilitar_red_comunitaria
    db.commit()
    db.refresh(comercio)
    return comercio
