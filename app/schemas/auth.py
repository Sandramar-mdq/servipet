from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str | None = None
    telefono: str | None = None
    password: str


class RegisterRequest(BaseModel):
    email: str | None = None
    telefono: str | None = None
    password: str
    nombre: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: dict
