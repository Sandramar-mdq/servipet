"""Servicio de almacenamiento de imagenes en Cloudinary.

Abstrae la subida/borrado de fotos de la red comunitaria (avisos).
Las credenciales se leen de variables de entorno via app.config.settings:
    CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET
"""

import logging

import cloudinary
import cloudinary.api  # noqa: F401  (parte del SDK)
import cloudinary.uploader
from fastapi import HTTPException

from app.config import settings

logger = logging.getLogger("servipet.cloudinary")

_configurado = False


def _configurar() -> None:
    """Configura el SDK una sola vez (lazy). Falla si faltan credenciales."""
    global _configurado
    if _configurado:
        return
    if not (settings.CLOUDINARY_CLOUD_NAME and settings.CLOUDINARY_API_KEY and settings.CLOUDINARY_API_SECRET):
        raise RuntimeError(
            "Cloudinary requiere CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY y CLOUDINARY_API_SECRET"
        )
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True,
    )
    _configurado = True


def cloudinary_disponible() -> bool:
    """True si hay credenciales configuradas (para validar el opt-in del comercio)."""
    return bool(
        settings.CLOUDINARY_CLOUD_NAME and settings.CLOUDINARY_API_KEY and settings.CLOUDINARY_API_SECRET
    )


def upload_image(file_bytes: bytes, folder: str = "servipet/avisos") -> dict:
    """Sube una imagen y retorna {"secure_url": str, "public_id": str}.

    Lanza HTTPException 400 si la subida falla o no hay credenciales.
    """
    try:
        _configurar()
        resultado = cloudinary.uploader.upload(file_bytes, folder=folder)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Fallo la subida de imagen a Cloudinary (carpeta=%s)", folder)
        raise HTTPException(status_code=400, detail="No se pudo subir la imagen")
    return {
        "secure_url": resultado["secure_url"],
        "public_id": resultado["public_id"],
    }


def delete_image(public_id: str) -> bool:
    """Elimina un asset de Cloudinary. Retorna True si se elimino correctamente."""
    if not public_id:
        return False
    try:
        _configurar()
        resultado = cloudinary.uploader.destroy(public_id)
    except Exception:
        logger.exception("Fallo el borrado de imagen en Cloudinary (public_id=%s)", public_id)
        return False
    return resultado.get("result") == "ok"
