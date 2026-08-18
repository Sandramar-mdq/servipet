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

    Busca el token prioritariamente en la cookie ``access_token`` y
    secundariamente en el header ``Authorization: Bearer <token>``.
    """
    token: str | None = request.cookies.get("access_token")

    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]

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
