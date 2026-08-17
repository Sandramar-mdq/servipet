from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_client
from app.models.cliente import Cliente
from app.models.mascota import Mascota
from app.models.atencion import AtencionHistorial

router = APIRouter(prefix="/cliente", tags=["Cliente Portal"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, cliente: Cliente = Depends(get_current_client), db: Session = Depends(get_db)):
    mascotas = (
        db.query(Mascota)
        .filter(Mascota.cliente_id == cliente.id, Mascota.activo == True)
        .all()
    )
    mascota_ids = [m.id for m in mascotas]
    atenciones = []
    total_atenciones = 0
    if mascota_ids:
        total_atenciones = (
            db.query(AtencionHistorial)
            .filter(AtencionHistorial.mascota_id.in_(mascota_ids))
            .count()
        )
        atenciones = (
            db.query(AtencionHistorial)
            .filter(AtencionHistorial.mascota_id.in_(mascota_ids))
            .order_by(AtencionHistorial.fecha.desc())
            .limit(5)
            .all()
        )
    return templates.TemplateResponse(
        request: request,
        name="cliente/dashboard.html",
        context={        
            "cliente": cliente,
            "mascotas": mascotas,
            "atenciones": atenciones,
            "total_atenciones": total_atenciones,
        },
    )


@router.get("/mascotas", response_class=HTMLResponse)
def listar_mascotas(request: Request, cliente: Cliente = Depends(get_current_client), db: Session = Depends(get_db)):
    mascotas = (
        db.query(Mascota)
        .filter(Mascota.cliente_id == cliente.id, Mascota.activo == True)
        .order_by(Mascota.nombre.asc())
        .all()
    )
    return templates.TemplateResponse(
        request=request,
        name="cliente/mascotas.html",
        context={
            "cliente": cliente,
            "mascotas": mascotas,
        },
    )


@router.get("/historial", response_class=HTMLResponse)
def historial(request: Request, cliente: Cliente = Depends(get_current_client), db: Session = Depends(get_db)):
    mascota_ids = [
        m.id
        for m in db.query(Mascota)
        .filter(Mascota.cliente_id == cliente.id, Mascota.activo == True)
        .all()
    ]
    atenciones = []
    if mascota_ids:
        atenciones = (
            db.query(AtencionHistorial)
            .filter(AtencionHistorial.mascota_id.in_(mascota_ids))
            .order_by(AtencionHistorial.fecha.desc())
            .all()
        )
    return templates.TemplateResponse(
        request=request,
        name="cliente/historial.html",
        context={
            "cliente": cliente,
            "atenciones": atenciones,
        },
    )


@router.get("/panel")
def panel_redirect():
    return RedirectResponse("/cliente/dashboard", status_code=301)
