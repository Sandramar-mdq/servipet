from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import (
    get_current_user,
    require_roles,
    require_superadmin,
    verificar_tenant,
)
from app.models.comercio import Comercio
from app.models.usuario import Usuario
from app.schemas.comercio import ComercioCreate, ComercioOptInRequest, ComercioUpdate, ComercioResponse

router = APIRouter(prefix="/comercios", tags=["Comercios"])

# Permisos (Iteracion 3):
#
# - `GET /` y `POST /` son operaciones de plataforma: solo el SuperAdmin
#   (rol ADMIN con comercio_id None) lista o crea tenants.
# - `GET /{id}` y `PUT /{id}` son de comercio: staff del tenant, con
#   `verificar_tenant` para que un Admin/Empleado de A no lea ni edite B.
# - `DELETE /{id}` es de plataforma y queda en manos del SuperAdmin: borrar un
#   tenant (y en cascada sus clientes, mascotas y turnos) nunca es una decision
#   de un Admin de comercio.


@router.get("/", response_model=list[ComercioResponse], dependencies=[Depends(require_superadmin)])
def listar_comercios(db: Session = Depends(get_db)):
    return db.query(Comercio).all()


@router.post(
    "/",
    response_model=ComercioResponse,
    status_code=201,
    dependencies=[Depends(require_superadmin)],
)
def crear_comercio(data: ComercioCreate, db: Session = Depends(get_db)):
    comercio = Comercio(**data.model_dump())
    db.add(comercio)
    db.commit()
    db.refresh(comercio)
    return comercio


@router.get(
    "/{comercio_id}",
    response_model=ComercioResponse,
    dependencies=[Depends(require_roles("ADMIN", "EMPLEADO"))],
)
def obtener_comercio(
    comercio_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    verificar_tenant(current_user, comercio_id)
    comercio = db.query(Comercio).filter(Comercio.id == comercio_id).first()
    if not comercio:
        raise HTTPException(status_code=404, detail="Comercio no encontrado")
    return comercio


@router.put(
    "/{comercio_id}",
    response_model=ComercioResponse,
    dependencies=[Depends(require_roles("ADMIN"))],
)
def actualizar_comercio(
    comercio_id: int,
    data: ComercioUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    verificar_tenant(current_user, comercio_id)
    comercio = db.query(Comercio).filter(Comercio.id == comercio_id).first()
    if not comercio:
        raise HTTPException(status_code=404, detail="Comercio no encontrado")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(comercio, key, value)
    db.commit()
    db.refresh(comercio)
    return comercio


@router.delete("/{comercio_id}", status_code=204, dependencies=[Depends(require_superadmin)])
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
    current_user: Usuario = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
):
    """Activa/desactiva los modulos del comercio (solo ADMIN del comercio o global).

    Los tres flags tienen semantica patch: si vienen en `None` el flag existente
    queda intacto. Esto permite que la UI encienda un modulo sin pisar el estado
    de los demas.
    """
    verificar_tenant(current_user, comercio_id)

    comercio = db.query(Comercio).filter(Comercio.id == comercio_id).first()
    if not comercio:
        raise HTTPException(status_code=404, detail="Comercio no encontrado")

    if datos.habilitar_red_comunitaria is not None:
        comercio.habilitar_red_comunitaria = datos.habilitar_red_comunitaria
    if datos.habilitar_modulo_solidario is not None:
        comercio.habilitar_modulo_solidario = datos.habilitar_modulo_solidario
    if datos.habilitar_cumpleanos is not None:
        comercio.habilitar_cumpleanos = datos.habilitar_cumpleanos
    db.commit()
    db.refresh(comercio)
    return comercio