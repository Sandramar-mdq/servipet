"""Endpoint de chat con el asistente IA (Etapa 9.1).

POST /api/v1/chat
- Autenticacion dual: usuario (JWT Bearer/cookie) o cliente (sesion PWA).
- El tenant (comercio_id) se resuelve SOLO desde el actor autenticado.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.client import get_current_client
from app.models.comercio import Comercio
from app.schemas.chat import ChatRequest, ChatResponse
from app.services import ai_chat_service

logger = logging.getLogger("servipet.chat")

router = APIRouter(prefix="/api/v1", tags=["Chat"])


def _obtener_actor(request: Request, db: Session):
    """Retorna ('usuario', Usuario) o ('cliente', Cliente); 401 si ninguno."""
    try:
        return "usuario", get_current_user(request, db)
    except HTTPException:
        pass
    try:
        return "cliente", get_current_client(request, db)
    except HTTPException:
        raise HTTPException(status_code=401, detail="No autenticado")


@router.post("/chat", response_model=ChatResponse)
def chatear(payload: ChatRequest, request: Request, db: Session = Depends(get_db)):
    tipo, actor = _obtener_actor(request, db)

    comercio_id = actor.comercio_id
    if comercio_id is None:
        raise HTTPException(
            status_code=403,
            detail="El usuario no tiene un comercio asociado",
        )
    comercio = db.get(Comercio, comercio_id)
    if not comercio:
        raise HTTPException(status_code=404, detail="Comercio no encontrado")

    resultado = ai_chat_service.generar_respuesta(
        db,
        comercio=comercio,
        actor_tipo=tipo,
        actor_id=actor.id,
        sesion_id=payload.sesion_id,
        mensaje=payload.mensaje.strip(),
    )
    logger.info(
        "Chat sesion=%s tipo=%s actor=%s estado=%s tools=%s",
        resultado["sesion_id"], tipo, actor.id,
        resultado["estado"], resultado["herramientas_usadas"],
    )
    return ChatResponse(**resultado)
