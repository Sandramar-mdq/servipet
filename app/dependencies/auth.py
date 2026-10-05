from typing import Callable

import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.usuario import Usuario
from app.services.auth import decode_access_token


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> Usuario:
    """Extrae y valida el JWT del usuario actual.

    Busca el token prioritariamente en el header ``Authorization: Bearer <token>``
    y secundariamente en la cookie ``access_token`` (portales web).
    """
    token: str | None = None

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]

    if not token:
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(status_code=401, detail="No autenticado")

    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token invalido")

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Token invalido")

    usuario = (
        db.query(Usuario)
        .filter(Usuario.id == int(user_id), Usuario.activo == True)
        .first()
    )
    if not usuario:
        raise HTTPException(status_code=401, detail="Usuario no valido")
    return usuario


def require_roles(*roles_permitidos: str) -> Callable:
    """Fábrica de dependencias que valida el rol del usuario actual.

    Uso::

        @router.get("/admin-only", dependencies=[Depends(require_roles("ADMIN"))])
        def admin_view(current_user: Usuario = Depends(get_current_user)):
            ...
    """

    def _check(current_user: Usuario = Depends(get_current_user)) -> Usuario:
        if current_user.rol not in roles_permitidos:
            raise HTTPException(status_code=403, detail="Permisos insuficientes")
        return current_user

    return _check


def require_superadmin(user: Usuario = Depends(get_current_user)) -> Usuario:
    """Solo el SuperAdmin global (ADMIN sin comercio asignado) pasa.

    El proyecto no tiene un rol "SUPERADMIN": es la convencion
    ``rol == "ADMIN" and comercio_id is None`` (``Usuario.comercio_id`` es
    nullable justamente para esto).
    """
    if user.rol != "ADMIN" or user.comercio_id is not None:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    return user


def verificar_tenant(user: Usuario, comercio_id: int) -> None:
    """Impide que un Admin/Empleado acceda a datos de otro comercio.

    Levanta 403 si el usuario tiene comercio asignado y no coincide con el
    recurso. Un SuperAdmin (``comercio_id is None``) pasa siempre: su acceso
    transversal es intencional.

    Reemplaza la copia local que vivia en ``app.routers.marketing._verificar_tenant``.
    """
    if user.comercio_id is not None and user.comercio_id != comercio_id:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
