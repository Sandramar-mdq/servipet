"""Paginas HTML del Modulo de Marketing B2B (Etapa 12).

Hoy expone una sola vista: el Kit de Promociones, que arma la placa cuadrada
1:1 (`POST /api/v1/marketing/kit/promocion/placa.png`) desde el navegador.

El consumo de datos es por `fetch` contra la API existente: la pagina no toca
`marketing_service` ni `pieza_service`, de modo que la logica de negocio queda
en un solo lado. El HTML solo aporta el formulario y la vista previa.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from app.core.templating import get_templates
from app.dependencies.auth import require_roles
from app.models.usuario import Usuario

router = APIRouter(prefix="/page", tags=["Marketing UI"])
templates = get_templates()


@router.get("/marketing", response_class=HTMLResponse)
def pagina_kit_marketing(
    request: Request,
    current_user: Usuario = Depends(require_roles("ADMIN", "EMPLEADO")),
):
    """Kit de Marketing: genera una placa 1:1 por campana, sin limite de usos."""
    return templates.TemplateResponse(
        request=request,
        name="marketing/kit.html",
        context={
            "es_admin": current_user.rol == "ADMIN",
        },
    )
