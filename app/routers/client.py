from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.templating import get_templates
from app.database import get_db
from app.dependencies import get_current_client
from app.dependencies.auth import get_current_user
from app.models.cliente import Cliente
from app.models.comercio import Comercio
from app.models.mascota import Mascota
from app.models.atencion import AtencionHistorial

router = APIRouter(prefix="/cliente", tags=["Cliente Portal"])
templates = get_templates()


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
        request=request,
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


@router.get("/comunidad", response_class=HTMLResponse)
def pagina_comunidad(request: Request, db: Session = Depends(get_db)):
    """Feed comunitario de la PWA. Publico: identifica al actor si hay sesion.

    - Cliente PWA (cookie cliente_session) o staff (cookie/JWT access_token).
    - Anonimo: ve el feed con CTA para iniciar sesion.
    """
    actor = {"tipo": None, "cliente_id": None, "usuario_id": None, "es_staff": False}
    comercio_id = 1

    try:
        cliente = get_current_client(request, db)
        actor["tipo"] = "cliente"
        actor["cliente_id"] = cliente.id
        comercio_id = cliente.comercio_id or 1
    except HTTPException:
        try:
            usuario = get_current_user(request, db)
            actor["tipo"] = "usuario"
            actor["usuario_id"] = usuario.id
            actor["es_staff"] = usuario.rol in ("ADMIN", "EMPLEADO")
            comercio_id = usuario.comercio_id or 1
        except HTTPException:
            pass

    comercio = None
    try:
        comercio = db.query(Comercio).filter(Comercio.id == comercio_id).first()
    except Exception:
        # BD recien inicializada o esquema desactualizado: no romper la pagina.
        db.rollback()
        comercio = None

    if comercio is None:
        # Fallback amable para que la plantilla renderice igual;
        # el feed de JS mostrara su empty state si el comercio no existe.
        comercio = SimpleNamespace(
            id=comercio_id,
            nombre="Servipet",
            telefono="",
            habilitar_red_comunitaria=False,
        )

    return templates.TemplateResponse(
        request=request,
        name="cliente/comunidad.html",
        context={
            "comercio": comercio,
            "actor": actor,
        },
    )
