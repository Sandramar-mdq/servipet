from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user, require_roles, verificar_tenant
from app.models.cliente import Cliente
from app.models.usuario import Usuario
from app.schemas.cliente import ClienteCreate, ClienteUpdate, ClienteResponse

router = APIRouter(prefix="/clientes", tags=["Clientes"])

# Permisos (Iteracion 3):
#
# Antes este router no tenia NINGUN guard y `GET /clientes/` aceptaba un
# `comercio_id` opcional en el query string, de modo que un anonimo podia
# enumerar la base de clientes de cualquier tenant. Ahora:
#
# - El `comercio_id` del query string solo lo puede usar el SuperAdmin
#   (`comercio_id is None` en su token). Para un Admin/Empleado se ignora y
#   manda el del token; si viene uno distinto, 403.
# - Un SuperAdmin sin `comercio_id` explicito recibe 400 en vez de la base
#   completa de clientes de todos los tenants.
# - El `comercio_id` del body nunca se trusts: se fuerza desde el token.
# - Los endpoints por id validan que el Cliente pertenezca al tenant del token.


def _resolver_comercio_consulta(
    current_user: Usuario,
    comercio_id: int | None,
) -> int:
    """Devuelve el comercio_id efectivo y valida que el usuario pueda verlo."""
    if current_user.comercio_id is None:
        if comercio_id is None:
            raise HTTPException(
                status_code=400,
                detail="Indicá el comercio con comercio_id=ID (requerido para SuperAdmin)",
            )
        return comercio_id

    if comercio_id is not None and comercio_id != current_user.comercio_id:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    return current_user.comercio_id


@router.get(
    "/",
    response_model=list[ClienteResponse],
    dependencies=[Depends(require_roles("ADMIN", "EMPLEADO"))],
)
def listar_clientes(
    comercio_id: int | None = Query(default=None),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    efectivo = _resolver_comercio_consulta(current_user, comercio_id)
    return db.query(Cliente).filter(Cliente.comercio_id == efectivo).all()


@router.post(
    "/",
    response_model=ClienteResponse,
    status_code=201,
    dependencies=[Depends(require_roles("ADMIN", "EMPLEADO"))],
)
def crear_cliente(
    data: ClienteCreate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """El comercio sale siempre del token, nunca del body."""
    if current_user.comercio_id is None:
        raise HTTPException(
            status_code=400,
            detail="El SuperAdmin no crea clientes directamente: usar /admin/comercios",
        )
    datos = data.model_dump()
    datos["comercio_id"] = current_user.comercio_id
    cliente = Cliente(**datos)
    db.add(cliente)
    db.commit()
    db.refresh(cliente)
    return cliente


def _cliente_del_tenant(cliente_id: int, current_user: Usuario, db: Session) -> Cliente:
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    verificar_tenant(current_user, cliente.comercio_id)
    return cliente


@router.get(
    "/{cliente_id}",
    response_model=ClienteResponse,
    dependencies=[Depends(require_roles("ADMIN", "EMPLEADO"))],
)
def obtener_cliente(
    cliente_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _cliente_del_tenant(cliente_id, current_user, db)


@router.put(
    "/{cliente_id}",
    response_model=ClienteResponse,
    dependencies=[Depends(require_roles("ADMIN"))],
)
def actualizar_cliente(
    cliente_id: int,
    data: ClienteUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cliente = _cliente_del_tenant(cliente_id, current_user, db)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(cliente, key, value)
    db.commit()
    db.refresh(cliente)
    return cliente


@router.delete(
    "/{cliente_id}",
    status_code=204,
    dependencies=[Depends(require_roles("ADMIN"))],
)
def eliminar_cliente(
    cliente_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cliente = _cliente_del_tenant(cliente_id, current_user, db)
    cliente.activo = False
    db.commit()