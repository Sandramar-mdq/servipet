from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.core.templating import get_templates
from app.database import get_db
from app.models.usuario import Usuario
from app.services.auth import create_access_token, verify_password

router = APIRouter(tags=["Login Staff"])
templates = get_templates()

ROLES_STAFF = ("ADMIN", "EMPLEADO")
COOKIE_MAX_AGE = 60 * 60 * 24 * 7


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "error": request.query_params.get("error"),
            "email": request.query_params.get("email", ""),
        },
    )


@router.post("/login")
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    email = email.strip()
    usuario = db.query(Usuario).filter(Usuario.email == email).first()

    if (
        not usuario
        or not usuario.activo
        or not verify_password(password, usuario.password_hash)
        or usuario.rol not in ROLES_STAFF
    ):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "error": "Email o contrasena incorrectos, o sin permisos de staff",
                "email": email,
            },
            status_code=401,
        )

    token = create_access_token(data={
        "sub": str(usuario.id),
        "rol": usuario.rol,
        "comercio_id": usuario.comercio_id,
    })

    response = RedirectResponse("/page/", status_code=303)
    response.set_cookie(
        key="access_token",
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=not settings.DEBUG,
    )
    return response
