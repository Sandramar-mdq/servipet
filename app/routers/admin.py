"""Panel de moderacion de la Red Comunitaria (Etapa 7.4) y panel
white-label de branding/accesibilidad (Etapa 8.3).

Acceso restringido segun rol del comercio.
"""

import json
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.skins_config import A11Y_MODOS, SKINS_PRESETS, resolver_skin
from app.core.templating import get_templates
from app.database import get_db
from app.dependencies.auth import require_roles
from app.models.comercio import Comercio
from app.models.usuario import Usuario
from app.schemas.comercio import ComercioUpdate

router = APIRouter(prefix="/admin", tags=["Admin"])
templates = get_templates()


@router.get("/comunidad", response_class=HTMLResponse)
def pagina_comunidad_admin(
    request: Request,
    current_user: Usuario = Depends(require_roles("ADMIN", "EMPLEADO")),
    db: Session = Depends(get_db),
):
    comercio_id = current_user.comercio_id or 1
    comercio = db.query(Comercio).filter(Comercio.id == comercio_id).first()
    return templates.TemplateResponse(
        request=request,
        name="admin/comunidad_admin.html",
        context={
            "comercio": comercio,
            "es_admin": current_user.rol == "ADMIN",
        },
    )


@router.get("/personalizacion", response_class=HTMLResponse)
def pagina_personalizacion(
    request: Request,
    current_user: Usuario = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
):
    """Panel white-label: presets, colores libres y opciones de accesibilidad."""
    comercio_id = current_user.comercio_id or 1
    comercio = db.query(Comercio).filter(Comercio.id == comercio_id).first()
    return templates.TemplateResponse(
        request=request,
        name="admin/personalizacion.html",
        context={
            "comercio": comercio,
            "presets": SKINS_PRESETS,
            "a11y_modos": A11Y_MODOS,
            "skin": resolver_skin(comercio),
            "presets_json": json.dumps(SKINS_PRESETS),
            "success": request.query_params.get("success"),
            "error": request.query_params.get("error"),
        },
    )


_MENSAJES_VALIDACION = {
    "tema_preset": "Preset desconocido",
    "color_primario": "Color primario invalido (se espera #RRGGBB)",
    "color_secundario": "Color secundario invalido (se espera #RRGGBB)",
    "a11y_modo": "Modo de accesibilidad desconocido",
}


@router.post("/personalizacion", response_class=HTMLResponse)
def guardar_personalizacion(
    request: Request,
    current_user: Usuario = Depends(require_roles("ADMIN")),
    db: Session = Depends(get_db),
    tema_preset: str = Form(...),
    color_primario: str = Form(...),
    color_secundario: str = Form(...),
    logo_url: str = Form(""),
    banner_url: str = Form(""),
    a11y_modo: str = Form(...),
    a11y_dyslexic: str = Form(None),  # noqa: ARG001 (checkbox HTML: 'on' o ausente)
):
    """Valida el formulario con ComercioUpdate y persiste la configuracion.

    Ante datos invalidos redirige con mensaje de error sin tocar la BD.
    """
    comercio_id = current_user.comercio_id or 1
    comercio = db.query(Comercio).filter(Comercio.id == comercio_id).first()

    try:
        datos = ComercioUpdate(
            tema_preset=tema_preset,
            color_primario=color_primario.strip().upper(),
            color_secundario=color_secundario.strip().upper(),
            logo_url=logo_url.strip() or None,
            banner_url=banner_url.strip() or None,
            a11y_modo=a11y_modo,
            a11y_dyslexic=(a11y_dyslexic or "").lower() in ("on", "true", "1"),
        )
    except ValidationError as exc:
        campo = exc.errors()[0].get("loc", ("formulario",))[-1]
        mensaje = _MENSAJES_VALIDACION.get(campo, "Datos del formulario invalidos")
        return RedirectResponse(
            f"/admin/personalizacion?error={quote(mensaje)}", status_code=303
        )

    if comercio is None:
        comercio = Comercio(id=comercio_id, nombre="Servipet")
        db.add(comercio)

    for key, value in datos.model_dump(exclude_unset=True).items():
        setattr(comercio, key, value)
    db.commit()

    return RedirectResponse(
        "/admin/personalizacion?success=Personalizacion%20actualizada", status_code=303
    )
