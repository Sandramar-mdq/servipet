"""API REST de la Red Comunitaria Servipet (Etapa 7.2).

- Feed publico paginado por comercio (con Opt-In y reglas de privacidad).
- Creacion de avisos con subida opcional de imagen a Cloudinary.
- Cambio de estado y borrado con control de pertenencia.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user, require_roles
from app.dependencies.client import get_current_client
from app.models.aviso_comunitario import (
    AvisoComunitario,
    EstadoAviso,
    TipoAviso,
    TipoContacto,
)
from app.models.comercio import Comercio
from app.models.usuario import Usuario
from app.schemas.aviso_comunitario import (
    AvisoCambioEstadoRequest,
    AvisoComunitarioCreate,
    AvisoComunitarioResponse,
    FeedAvisosResponse,
)
from app.services import cloudinary_service

logger = logging.getLogger("servipet.comunidad")

router = APIRouter(prefix="/api/v1/comunidad", tags=["Comunidad"])


# --- Autenticacion dual: usuario (JWT) o cliente (sesion PWA) ---

def _obtener_actor(request: Request, db: Session = Depends(get_db)):
    """Retorna ('usuario', Usuario) o ('cliente', Cliente); 401 si ninguno."""
    try:
        return ("usuario", get_current_user(request, db))
    except HTTPException:
        pass
    try:
        return ("cliente", get_current_client(request, db))
    except HTTPException:
        raise HTTPException(status_code=401, detail="No autenticado")


# --- Helpers ---

def _comercio_con_optin(db: Session, comercio_id: int) -> Comercio:
    comercio = db.query(Comercio).filter(Comercio.id == comercio_id).first()
    if not comercio:
        raise HTTPException(status_code=404, detail="Comercio no encontrado")
    if not comercio.habilitar_red_comunitaria:
        raise HTTPException(
            status_code=403,
            detail="La red comunitaria está deshabilitada para este comercio",
        )
    return comercio


def _respuesta_publica(aviso: AvisoComunitario) -> AvisoComunitarioResponse:
    """Aplica privacidad: el telefono solo se expone si el contacto es directo."""
    respuesta = AvisoComunitarioResponse.model_validate(aviso)
    if aviso.tipo_contacto != TipoContacto.DIRECTO_WHATSAPP:
        respuesta.telefono_contacto = None
    return respuesta


def _verificar_pertenencia(actor, aviso: AvisoComunitario) -> None:
    clase, obj = actor
    autorizado = False
    if clase == "usuario":
        es_staff = obj.rol in ("ADMIN", "EMPLEADO") and obj.comercio_id == aviso.comercio_id
        es_creador = aviso.creado_por_usuario_id is not None and aviso.creado_por_usuario_id == obj.id
        autorizado = es_staff or es_creador
    else:
        autorizado = aviso.cliente_id is not None and aviso.cliente_id == obj.id
    if not autorizado:
        raise HTTPException(status_code=403, detail="No tenés permisos sobre este aviso")


# --- Feed publico ---

@router.get("/{comercio_id}/avisos", response_model=FeedAvisosResponse)
def listar_avisos(
    comercio_id: int,
    tipo: TipoAviso | None = None,
    estado: EstadoAviso | None = EstadoAviso.ACTIVO,
    limit: int = Query(default=10, ge=1, le=20),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    _comercio_con_optin(db, comercio_id)

    query = db.query(AvisoComunitario).filter(AvisoComunitario.comercio_id == comercio_id)
    if tipo is not None:
        query = query.filter(AvisoComunitario.tipo == tipo)
    if estado is not None:
        query = query.filter(AvisoComunitario.estado == estado)

    total = query.count()
    avisos = (
        query.order_by(AvisoComunitario.fecha_publicacion.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [_respuesta_publica(aviso) for aviso in avisos],
    }


# --- Listado para moderacion (staff) ---

@router.get("/admin/{comercio_id}/avisos", response_model=FeedAvisosResponse)
def listar_avisos_admin(
    comercio_id: int,
    tipo: TipoAviso | None = None,
    estado: EstadoAviso | None = None,
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    current_user: Usuario = Depends(require_roles("ADMIN", "EMPLEADO")),
    db: Session = Depends(get_db),
):
    """Listado de moderacion: sin gate de opt-in, todos los estados y sin
    mascara de privacidad (el staff necesita ver el telefono del autor)."""
    if current_user.comercio_id is not None and current_user.comercio_id != comercio_id:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")

    query = db.query(AvisoComunitario).filter(AvisoComunitario.comercio_id == comercio_id)
    if tipo is not None:
        query = query.filter(AvisoComunitario.tipo == tipo)
    if estado is not None:
        query = query.filter(AvisoComunitario.estado == estado)

    total = query.count()
    avisos = (
        query.order_by(AvisoComunitario.fecha_publicacion.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {"total": total, "limit": limit, "offset": offset, "items": avisos}


# --- Crear aviso ---

@router.post("/{comercio_id}/avisos", response_model=AvisoComunitarioResponse, status_code=201)
async def crear_aviso(
    comercio_id: int,
    tipo: TipoAviso = Form(...),
    titulo: str = Form(..., max_length=100),
    descripcion: str = Form(...),
    tipo_contacto: TipoContacto = Form(default=TipoContacto.VIA_COMERCIO),
    telefono_contacto: str | None = Form(default=None),
    fecha_expiracion: datetime | None = Form(default=None),
    imagen: UploadFile | None = File(default=None),
    actor=Depends(_obtener_actor),
    db: Session = Depends(get_db),
):
    _comercio_con_optin(db, comercio_id)

    clase_actor, obj = actor
    cliente_id = None
    creado_por_usuario_id = None
    if clase_actor == "usuario":
        creado_por_usuario_id = obj.id
        if obj.rol == "CLIENTE" and obj.cliente_profile is not None:
            cliente_id = obj.cliente_profile.id
    else:
        cliente_id = obj.id

    # Reutiliza las validaciones del schema (ej. WhatsApp exige telefono).
    try:
        datos = AvisoComunitarioCreate(
            comercio_id=comercio_id,
            cliente_id=cliente_id,
            tipo=tipo,
            titulo=titulo,
            descripcion=descripcion,
            tipo_contacto=tipo_contacto,
            telefono_contacto=telefono_contacto,
            fecha_expiracion=fecha_expiracion,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    foto_url = None
    public_id_cloudinary = None
    if imagen is not None and imagen.filename:
        if imagen.content_type and not imagen.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="El archivo debe ser una imagen")
        contenido = await imagen.read()
        if not contenido:
            raise HTTPException(status_code=400, detail="El archivo de imagen está vacío")
        resultado = cloudinary_service.upload_image(contenido)
        foto_url = resultado["secure_url"]
        public_id_cloudinary = resultado["public_id"]

    aviso = AvisoComunitario(
        comercio_id=comercio_id,
        cliente_id=datos.cliente_id,
        creado_por_usuario_id=creado_por_usuario_id,
        tipo=datos.tipo,
        estado=EstadoAviso.ACTIVO,
        titulo=datos.titulo,
        descripcion=datos.descripcion,
        foto_url=foto_url,
        public_id_cloudinary=public_id_cloudinary,
        tipo_contacto=datos.tipo_contacto,
        telefono_contacto=datos.telefono_contacto,
        fecha_expiracion=datos.fecha_expiracion,
    )
    db.add(aviso)
    db.commit()
    db.refresh(aviso)
    return aviso


# --- Cambio de estado ---

@router.patch("/avisos/{aviso_id}/estado", response_model=AvisoComunitarioResponse)
def cambiar_estado(
    aviso_id: int,
    datos: AvisoCambioEstadoRequest,
    actor=Depends(_obtener_actor),
    db: Session = Depends(get_db),
):
    aviso = db.query(AvisoComunitario).filter(AvisoComunitario.id == aviso_id).first()
    if not aviso:
        raise HTTPException(status_code=404, detail="Aviso no encontrado")
    _verificar_pertenencia(actor, aviso)

    aviso.estado = datos.estado
    db.commit()
    db.refresh(aviso)
    return aviso


# --- Borrado ---

@router.delete("/avisos/{aviso_id}", status_code=204)
def eliminar_aviso(
    aviso_id: int,
    actor=Depends(_obtener_actor),
    db: Session = Depends(get_db),
):
    aviso = db.query(AvisoComunitario).filter(AvisoComunitario.id == aviso_id).first()
    if not aviso:
        raise HTTPException(status_code=404, detail="Aviso no encontrado")
    _verificar_pertenencia(actor, aviso)

    if aviso.public_id_cloudinary:
        if not cloudinary_service.delete_image(aviso.public_id_cloudinary):
            logger.warning(
                "No se pudo borrar la imagen en Cloudinary (public_id=%s); se elimina el aviso igual",
                aviso.public_id_cloudinary,
            )

    db.delete(aviso)
    db.commit()
