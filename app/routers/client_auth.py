from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import COOKIE_SESION
from app.models.cliente import Cliente
from app.services.auth_tokens import crear_token
from app.services.otp_service import crear_otp, validar_otp

router = APIRouter(prefix="/cliente", tags=["Cliente Auth"])
templates = Jinja2Templates(directory="app/templates")

COOKIE_MAX_AGE = 60 * 60 * 24 * 30


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse("cliente/login.html", {
        "request": request,
        "error": request.query_params.get("error"),
    })


@router.post("/login")
def login_submit(
    telefono: str = Form(...),
    db: Session = Depends(get_db),
):
    telefono = telefono.strip()
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
    return response
