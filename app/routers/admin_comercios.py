"""Panel SuperAdmin de gestion de Comercios / Tenants (modulo 11).

Acceso exclusivo para usuarios con rol ADMIN y comercio_id None (SuperAdmin).
Incluye: listado con metricas agregadas por LEFT OUTER JOIN, alta manual de
comercios con su usuario ADMIN, e impersonacion con token JWT adicional para
regresar sin perder la sesion SuperAdmin.
"""

import secrets
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.core.templating import get_templates
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.cliente import Cliente
from app.models.comercio import Comercio
from app.models.turno import Turno
from app.models.usuario import Usuario
from app.services.auth import create_access_token, decode_access_token, hash_password

router = APIRouter(prefix="/admin", tags=["Admin Comercios"])
templates = get_templates()

PLANES = ("DEMO", "ESTANDAR", "PRO")
ESTADOS = ("ACTIVO", "INACTIVO", "MOROSO")
COOKIE_MAX_AGE = 60 * 60 * 24 * 7


def require_superadmin(user: Usuario = Depends(get_current_user)) -> Usuario:
    """Solo el SuperAdmin global (ADMIN sin comercio asignado) pasa."""
    if user.rol != "ADMIN" or user.comercio_id is not None:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")
    return user


def require_impersonacion(request: Request) -> dict:
    """Devuelve el payload JWT solo si el token actual es de impersonacion."""
    token: str | None = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    if not token:
        token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="No autenticado")

    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Token invalido")

    if not payload.get("impersonando"):
        raise HTTPException(status_code=403, detail="Sin impersonacion activa")
    return payload


def _set_cookie(response: RedirectResponse, token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=not settings.DEBUG,
    )


@router.get("/comercios", response_class=HTMLResponse)
def pagina_comercios(
    request: Request,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_superadmin),  # noqa: ARG001
):
    """Lista de todos los tenants con metricas agregadas por left join."""
    filas = (
        db.query(
            Comercio,
            func.count(func.distinct(Usuario.id)).label("total_usuarios"),
            func.count(func.distinct(Turno.id)).label("total_turnos"),
        )
        .outerjoin(Usuario, Usuario.comercio_id == Comercio.id)
        .outerjoin(Cliente, Cliente.comercio_id == Comercio.id)
        .outerjoin(Turno, Turno.cliente_id == Cliente.id)
        .group_by(Comercio.id)
        .order_by(Comercio.id)
        .all()
    )
    comercios = [
        {
            "comercio": c,
            "total_usuarios": n_usuarios,
            "total_turnos": n_turnos,
        }
        for c, n_usuarios, n_turnos in filas
    ]
    return templates.TemplateResponse(
        request=request,
        name="admin/comercios.html",
        context={
            "comercios": comercios,
            "planes": PLANES,
            "success": request.query_params.get("success"),
            "error": request.query_params.get("error"),
        },
    )


@router.post("/comercios")
def crear_comercio(
    request: Request,
    nombre: str = Form(...),
    email: str = Form(...),
    plan: str = Form("DEMO"),
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_superadmin),  # noqa: ARG001
):
    """Alta manual de un comercio + su usuario ADMIN (password temporal)."""
    nombre = (nombre or "").strip()
    email = (email or "").strip().lower()
    plan = (plan or "").strip().upper()

    if not nombre:
        return RedirectResponse("/admin/comercios?error=" + quote("El nombre es obligatorio"), status_code=303)
    if "@" not in email or "." not in email:
        return RedirectResponse("/admin/comercios?error=" + quote("Email de admin invalido"), status_code=303)
    if plan not in PLANES:
        return RedirectResponse("/admin/comercios?error=" + quote("Plan invalido"), status_code=303)
    if db.query(Usuario).filter(Usuario.email == email).first():
        return RedirectResponse("/admin/comercios?error=" + quote("Ese email ya esta registrado"), status_code=303)

    password_temporal = secrets.token_urlsafe(8)

    comercio = Comercio(
        nombre=nombre,
        email=email,
        tipo_comercio="MULTIRRUBRO",
        plan=plan,
        estado="ACTIVO",
        activo=True,
    )
    db.add(comercio)
    db.flush()

    admin = Usuario(
        email=email,
        password_hash=hash_password(password_temporal),
        rol="ADMIN",
        comercio_id=comercio.id,
        activo=True,
    )
    db.add(admin)
    db.commit()

    detalle = f"Comercio {comercio.id} - {email} - Password temporal: {password_temporal}"
    return RedirectResponse("/admin/comercios?success=" + quote(detalle), status_code=303)


@router.post("/comercios/{comercio_id}/impersonar")
def impersonar_comercio(
    comercio_id: int,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_superadmin),
):
    """Entra como el ADMIN del comercio sin perder la sesion SuperAdmin."""
    comercio = db.query(Comercio).filter(Comercio.id == comercio_id).first()
    if not comercio:
        raise HTTPException(status_code=404, detail="Comercio no encontrado")

    admin = (
        db.query(Usuario)
        .filter(
            Usuario.comercio_id == comercio_id,
            Usuario.rol == "ADMIN",
            Usuario.activo == True,
        )
        .first()
    )
    if not admin:
        raise HTTPException(
            status_code=400,
            detail="El comercio no tiene un usuario ADMIN registrado",
        )

    token = create_access_token(
        data={
            "sub": str(admin.id),
            "rol": admin.rol,
            "comercio_id": admin.comercio_id,
            "impersonando": True,
            "impersonado_por": user.id,
            "comercio_nombre": comercio.nombre,
        }
    )
    response = RedirectResponse("/page/", status_code=303)
    _set_cookie(response, token)
    return response


@router.post("/salir-impersonacion")
def salir_impersonacion(
    payload: dict = Depends(require_impersonacion),
    db: Session = Depends(get_db),
):
    """Restaura la sesion del SuperAdmin original (claim impersonado_por)."""
    origen_id = payload.get("impersonado_por")
    superadmin = None
    if origen_id:
        superadmin = (
            db.query(Usuario)
            .filter(
                Usuario.id == int(origen_id),
                Usuario.activo == True,
            )
            .first()
        )
    if not superadmin or superadmin.rol != "ADMIN" or superadmin.comercio_id is not None:
        raise HTTPException(status_code=403, detail="Origen de impersonacion invalido")

    token = create_access_token(
        data={
            "sub": str(superadmin.id),
            "rol": superadmin.rol,
            "comercio_id": superadmin.comercio_id,
        }
    )
    response = RedirectResponse("/admin/comercios", status_code=303)
    _set_cookie(response, token)
    return response