from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.core.templating import get_templates
from app.database import get_db
from app.dependencies import COOKIE_SESION
from app.models.cliente import Cliente
from app.models.usuario import Usuario
from app.services.auth import create_access_token, verify_password
from app.services.auth_tokens import crear_token
from app.services.otp_service import crear_otp, validar_otp

router = APIRouter(prefix="/cliente", tags=["Cliente Auth"])
templates = get_templates()

COOKIE_MAX_AGE = 60 * 60 * 24 * 30


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="cliente/login.html",
        context={"error": request.query_params.get("error")},
    )


@router.post("/login")
def login_submit(
    telefono: str | None = Form(None),
    email: str | None = Form(None),
    password: str | None = Form(None),
    db: Session = Depends(get_db),
):
    # Canal email+password (usuarios con rol CLIENTE, mismos credenciales del
    # seed); coexiste con el OTP por telefono. El formulario envia un campo u
    # otro segun la pestana elegida.
    if email:
        return _login_password(email, password, db)

    telefono = (telefono or "").strip()
    cliente = (
        db.query(Cliente)
        .filter(Cliente.telefono == telefono, Cliente.activo == True)
        .first()
    )
    if not cliente:
        return RedirectResponse(
            "/cliente/login?" + urlencode({"error": "Telefono no registrado"}),
            status_code=303,
        )
    crear_otp(db, telefono)
    return RedirectResponse(
        "/cliente/verificar?" + urlencode({"telefono": telefono}),
        status_code=303,
    )


def _login_password(email: str, password: str, db: Session):
    """Session de cliente por email y contrasena.

    El rol debe ser CLIENTE (el staff entra por `/login`); ademas el usuario
    necesita una fila `Cliente` vinculada por `usuario_id`. En el exito se
    emiten las dos cookies: `cliente_session` para las paginas `/cliente/*` y
    `access_token` (JWT) para la API `/portal/*`.
    """
    usuario = (
        db.query(Usuario)
        .filter(
            Usuario.email == email.strip(),
            Usuario.rol == "CLIENTE",
            Usuario.activo == True,
        )
        .first()
    )
    if not usuario or not verify_password(password, usuario.password_hash):
        return RedirectResponse(
            "/cliente/login?" + urlencode({"error": "Email o contrasena incorrectos"}),
            status_code=303,
        )

    cliente = (
        db.query(Cliente)
        .filter(Cliente.usuario_id == usuario.id, Cliente.activo == True)
        .first()
    )
    if not cliente:
        return RedirectResponse(
            "/cliente/login?" + urlencode({"error": "No hay perfil de cliente vinculado"}),
            status_code=303,
        )

    token = create_access_token(data={
        "sub": str(usuario.id),
        "rol": usuario.rol,
        "comercio_id": usuario.comercio_id,
    })

    response = RedirectResponse("/cliente/dashboard", status_code=303)
    response.set_cookie(
        key="access_token",
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=not settings.DEBUG,
    )
    response.set_cookie(
        key=COOKIE_SESION,
        value=crear_token(cliente.id),
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/verificar", response_class=HTMLResponse)
def verificar_form(request: Request):
    telefono = request.query_params.get("telefono", "")
    if not telefono:
        return RedirectResponse("/cliente/login", status_code=303)
    return templates.TemplateResponse("cliente/verificar.html", {
        "request": request,
        "telefono": telefono,
        "error": request.query_params.get("error"),
    })


@router.post("/verificar")
def verificar_submit(
    telefono: str = Form(...),
    codigo: str = Form(...),
    db: Session = Depends(get_db),
):
    telefono = telefono.strip()
    valido, mensaje = validar_otp(db, telefono, codigo)
    if not valido:
        return RedirectResponse(
            "/cliente/verificar?" + urlencode({"telefono": telefono, "error": mensaje}),
            status_code=303,
        )
    cliente = (
        db.query(Cliente)
        .filter(Cliente.telefono == telefono, Cliente.activo == True)
        .first()
    )
    if not cliente:
        return RedirectResponse(
            "/cliente/login?" + urlencode({"error": "Telefono no registrado"}),
            status_code=303,
        )
    response = RedirectResponse("/cliente/dashboard", status_code=303)
    response.set_cookie(
        key=COOKIE_SESION,
        value=crear_token(cliente.id),
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return response


@router.get("/logout")
def logout():
    response = RedirectResponse("/cliente/login", status_code=303)
    response.delete_cookie(COOKIE_SESION)
    response.delete_cookie("access_token")
    return response
