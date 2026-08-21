"""Panel de moderacion de la Red Comunitaria (Etapa 7.4).

Acceso restringido a roles ADMIN y EMPLEADO del comercio.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import require_roles
from app.models.comercio import Comercio
from app.models.usuario import Usuario

router = APIRouter(prefix="/admin", tags=["Admin"])
templates = Jinja2Templates(directory="app/templates")


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
