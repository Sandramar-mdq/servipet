from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.cliente import Cliente
from app.services.auth_tokens import verificar_token

COOKIE_SESION = "cliente_session"


def get_current_client(request: Request, db: Session = Depends(get_db)) -> Cliente:
    token = request.cookies.get(COOKIE_SESION)
    cliente_id = verificar_token(token) if token else None
    if cliente_id is None:
        raise HTTPException(status_code=401, detail="No autenticado")
    cliente = (
        db.query(Cliente)
        .filter(Cliente.id == cliente_id, Cliente.activo == True)
        .first()
    )
    if not cliente:
        raise HTTPException(status_code=401, detail="Cliente no valido")
    return cliente
