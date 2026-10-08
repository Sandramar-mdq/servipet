"""Login del portal de clientes: email+password y OTP por telefono.

Cubre el canal que complementa al OTP: un usuario con rol CLIENTE y su perfil
`Cliente` vinculado entran con email/password desde `/cliente/login` (o el
alias publico `/portal/login`). El staff sigue entrando por `/login`; aca un
rol ADMIN debe ser rechazado sin cookie de sesion.
"""

from app.dependencies.client import COOKIE_SESION
from app.models.cliente import Cliente
from app.models.comercio import Comercio
from app.models.usuario import Usuario
from app.services.auth import hash_password

from tests.conftest import TestingSessionLocal


def _sembrar_usuario_cliente(
    email="cliente@test.com",
    telefono="1133112233",
    password="cliente123",
    crear_perfil=True,
):
    db = TestingSessionLocal()
    try:
        db.add(Comercio(id=1, nombre="Comercio Test", tipo_comercio="PELUQUERIA", activo=True))
        db.flush()
        usuario = Usuario(
            email=email,
            password_hash=hash_password(password),
            rol="CLIENTE",
            comercio_id=1,
            activo=True,
        )
        db.add(usuario)
        db.flush()
        if crear_perfil:
            db.add(Cliente(
                comercio_id=1,
                usuario_id=usuario.id,
                nombre="Cliente Test",
                telefono=telefono,
                email=email,
                activo=True,
            ))
        db.commit()
        return usuario.id
    finally:
        db.close()


def _sembrar_staff():
    db = TestingSessionLocal()
    try:
        db.add(Comercio(id=1, nombre="Comercio Test", tipo_comercio="PELUQUERIA", activo=True))
        db.add(Usuario(
            email="staff@test.com",
            password_hash=hash_password("staff123"),
            rol="ADMIN",
            comercio_id=1,
            activo=True,
        ))
        db.commit()
    finally:
        db.close()


class TestLoginEmailPassword:
    def test_get_login_muestra_las_dos_pestanas(self, client):
        resp = client.get("/cliente/login")
        assert resp.status_code == 200
        assert "form-password" in resp.text
        assert "form-telefono" in resp.text
        assert "Email y contrasena" in resp.text

    def test_login_ok_setea_ambas_cookies(self, client):
        _sembrar_usuario_cliente()
        resp = client.post(
            "/cliente/login",
            data={"email": "cliente@test.com", "password": "cliente123"},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert resp.headers["location"] == "/cliente/dashboard"
        assert client.cookies.get(COOKIE_SESION)
        assert client.cookies.get("access_token")

    def test_password_incorrecta_redirige_con_error(self, client):
        _sembrar_usuario_cliente()
        resp = client.post(
            "/cliente/login",
            data={"email": "cliente@test.com", "password": "mal"},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert "error" in resp.headers["location"]
        assert not client.cookies.get(COOKIE_SESION)

    def test_email_inexistente_redirige_con_error(self, client):
        _sembrar_usuario_cliente()
        resp = client.post(
            "/cliente/login",
            data={"email": "nadie@test.com", "password": "cliente123"},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert "error" in resp.headers["location"]

    def test_staff_no_entra_por_portal_clientes(self, client):
        _sembrar_staff()
        resp = client.post(
            "/cliente/login",
            data={"email": "staff@test.com", "password": "staff123"},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert "error" in resp.headers["location"]
        assert not client.cookies.get(COOKIE_SESION)
        assert not client.cookies.get("access_token")

    def test_cliente_sin_perfil_no_obtiene_sesion(self, client):
        _sembrar_usuario_cliente(email="sinperfil@test.com", crear_perfil=False)
        resp = client.post(
            "/cliente/login",
            data={"email": "sinperfil@test.com", "password": "cliente123"},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert "error" in resp.headers["location"]
        assert not client.cookies.get(COOKIE_SESION)

    def test_logout_limpia_ambas_cookies(self, client):
        _sembrar_usuario_cliente()
        client.post(
            "/cliente/login",
            data={"email": "cliente@test.com", "password": "cliente123"},
            follow_redirects=False,
        )
        assert client.cookies.get(COOKIE_SESION)
        resp = client.get("/cliente/logout", follow_redirects=False)
        assert resp.status_code == 303
        assert not client.cookies.get(COOKIE_SESION)
        assert not client.cookies.get("access_token")


class TestLoginOtp:
    def test_telefono_sigue_generando_otp(self, client):
        _sembrar_usuario_cliente()
        resp = client.post(
            "/cliente/login",
            data={"telefono": "1133112233"},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert resp.headers["location"].startswith("/cliente/verificar?telefono=")


class TestPortalLoginAlias:
    def test_get_portal_login_publico(self, client):
        resp = client.get("/portal/login")
        assert resp.status_code == 200
        assert "form-password" in resp.text