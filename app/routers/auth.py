from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.cliente import Cliente
from app.models.usuario import Usuario
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.usuario import UsuarioResponse
from app.services.auth import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["Autenticación"])


@router.post("/register", response_model=UsuarioResponse, status_code=201)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    if not data.email and not data.telefono:
        raise HTTPException(status_code=400, detail="Se requiere email o telefono")

    if data.email:
        existing = db.query(Usuario).filter(Usuario.email == data.email).first()
        if existing:
            raise HTTPException(status_code=400, detail="El email ya esta registrado")

    if data.telefono:
        existing = db.query(Usuario).filter(Usuario.telefono == data.telefono).first()
        if existing:
            raise HTTPException(status_code=400, detail="El telefono ya esta registrado")

    usuario = Usuario(
        email=data.email,
        telefono=data.telefono,
        password_hash=hash_password(data.password),
        rol="CLIENTE",
        comercio_id=1,
        activo=True,
    )
    db.add(usuario)
    db.flush()

    cliente = Cliente(
        comercio_id=1,
        usuario_id=usuario.id,
        nombre=data.nombre,
        email=data.email,
        telefono=data.telefono,
        activo=True,
    )
    db.add(cliente)
    db.commit()
    db.refresh(usuario)
    return usuario


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, response: Response, db: Session = Depends(get_db)):
    if not data.email and not data.telefono:
        raise HTTPException(status_code=400, detail="Se requiere email o telefono")

    query = db.query(Usuario)
    if data.email:
        usuario = query.filter(Usuario.email == data.email).first()
    else:
        usuario = query.filter(Usuario.telefono == data.telefono).first()

    if not usuario or not verify_password(data.password, usuario.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    if not usuario.activo:
        raise HTTPException(status_code=401, detail="Cuenta desactivada")

    token = create_access_token(data={
        "sub": str(usuario.id),
        "rol": usuario.rol,
        "comercio_id": usuario.comercio_id,
    })

    response.set_cookie(
        key="access_token",
        value=token,
        max_age=60 * 60 * 24 * 7,
        httponly=True,
        samesite="lax",
        secure=not (True),  # TODO: usar settings.DEBUG en prod
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        usuario=UsuarioResponse.model_validate(usuario).model_dump(),
    )


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    return {"detail": "Sesion cerrada"}


@router.get("/me", response_model=UsuarioResponse)
def me(current_user: Usuario = Depends(get_current_user)):
    return current_user
