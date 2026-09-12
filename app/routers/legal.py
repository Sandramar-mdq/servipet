"""Paginas legales publicas de Servipet (Tarea 11.2.1).

Vista standalone de Terminos del Servicio y Exencion de Responsabilidad
para la version Beta. No requiere autenticacion ni contexto de comercio.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.core.templating import get_templates

router = APIRouter(prefix="/legal", tags=["Legal"])
templates = get_templates()


@router.get("/terminos-beta", response_class=HTMLResponse)
def terminos_beta(request: Request):
    """Terminos del Servicio y Exencion de Responsabilidad de la version Beta."""
    return templates.TemplateResponse(
        request=request,
        name="legal/terminos_beta.html",
        context={},
    )