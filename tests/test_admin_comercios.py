"""Tests del modulo SuperAdmin: gestion de comercios / tenants.

Valida el acceso exclusivo (rol ADMIN + comercio_id None), el listado con
metricas LEFT JOIN, el alta manual con su usuario ADMIN y el flujo de
impersonacion con retorno via /admin/salir-impersonacion.
"""

import pytest

from app.models.comercio import Comercio
from app.models.usuario import Usuario
from app.services.auth import hash_password
from tests.conftest import TestingSessionLocal

PANEL = "/admin/comercios"


@pytest.fixture(autouse=True)
def _comercios_usa_bd_de_pruebas(monkeypatch):
    """El context processor y los endpoints resuelven contra la BD de pruebas."""
    import app.database as database

    monkeypatch.setattr(database, "SessionLocal", TestingSessionLocal)


def _login_headers(client, email, password):
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
def superadmin_headers(client):
    db = TestingSessionLocal()
    try:
        db.add(Usuario(
            email="super@test.com",
            password_hash=hash_password("super123"),
            rol="ADMIN",
            comercio_id=None,
            activo=True,
        ))
        db.commit()
    finally:
        db.close()
    return _login_headers(client, "super@test.com", "super123")


@pytest.fixture
def empleado_headers(client, admin_user):
    db = TestingSessionLocal()
    try:
        db.add(Usuario(
            email="empleado@test.com",
            password_hash=hash_password("empleado123"),
            rol="EMPLEADO",
            comercio_id=1,
            activo=True,
        ))
        db.commit()
    finally:
        db.close()
    return _login_headers(client, "empleado@test.com", "empleado123")


def _cookie_token(resp) -> str | None:
    for parte in resp.headers.get("set-cookie", "").split(";"):
        parte = parte.strip()
        if parte.startswith("access_token="):
            return parte.split("=", 1)[1]
    return None


def _crear_comercio(nombre="Comercio Nuevo", email="nuevo@comercio.com", plan="PRO"):
    db = TestingSessionLocal()
    try:
        c = Comercio(nombre=nombre, email=email, plan=plan)
        db.add(c)
        db.commit()
        cid = c.id
    finally:
        db.close()
    return cid


class TestAccesoSuperAdmin:
    def test_anonimo_401(self, client):
        resp = client.get(PANEL)
        assert resp.status_code == 401

    def test_anonimo_post_401(self, client):
        resp = client.post(PANEL, data={"nombre": "X", "email": "x@x.com", "plan": "DEMO"})
        assert resp.status_code == 401

    def test_cliente_rol_403(self, client, auth_headers):
        resp = client.get(PANEL, headers=auth_headers)
        assert resp.status_code == 403

    def test_empleado_403(self, client, empleado_headers):
        resp = client.get(PANEL, headers=empleado_headers)
        assert resp.status_code == 403

    def test_admin_de_comercio_403(self, client, admin_headers):
        """El ADMIN de un comercio (comercio_id=1) no es SuperAdmin."""
        resp = client.get(PANEL, headers=admin_headers)
        assert resp.status_code == 403

    def test_admin_de_comercio_post_403(self, client, admin_headers):
        resp = client.post(
            PANEL,
            data={"nombre": "Otro", "email": "otro@comercio.com", "plan": "DEMO"},
            headers=admin_headers,
        )
        assert resp.status_code == 403


class TestListado:
    def test_superadmin_ver_panel(self, client, superadmin_headers, admin_user):
        resp = client.get(PANEL, headers=superadmin_headers)
        assert resp.status_code == 200
        assert "Gestion de Comercios" in resp.text
        assert "Comercio Test" in resp.text
        assert "Ingresar como Comercio" in resp.text
        assert "Nuevo Comercio" in resp.text
        assert "modal-comercio" in resp.text
        assert "input-nombre" in resp.text

    def test_lista_vacia(self, client, superadmin_headers):
        resp = client.get(PANEL, headers=superadmin_headers)
        assert resp.status_code == 200
        assert "No hay comercios" in resp.text

    def test_metricas_agregadas(self, client, superadmin_headers):
        db = TestingSessionLocal()
        try:
            c_mov = Comercio(nombre="Con Movimiento", email="con@mov.com", plan="ESTANDAR")
            db.add(c_mov)
            db.commit()
            cid = c_mov.id

            db.add_all([
                Usuario(email="u1@mov.com", password_hash="dh", rol="ADMIN", comercio_id=cid),
                Usuario(email="u2@mov.com", password_hash="dh", rol="EMPLEADO", comercio_id=cid),
            ])
            db.add(Comercio(nombre="Solo Nuevo", email="solo@nuevo.com", plan="DEMO"))
            db.commit()
        finally:
            db.close()

        resp = client.get(PANEL, headers=superadmin_headers)
        assert resp.status_code == 200
        fila_mov = resp.text.split("Con Movimiento")[1].split("</tr>")[0]
        fila_solo = resp.text.split("Solo Nuevo")[1].split("</tr>")[0]
        assert ">2</td>" in fila_mov   # 2 usuarios agregados por left join
        assert ">0</td>" in fila_solo  # comercio sin usuarios


class TestCrearComercio:
    def test_superadmin_crea_comercio_y_admin(self, client, superadmin_headers):
        resp = client.post(
            PANEL,
            data={
                "nombre": "Vet Central",
                "email": "admin@vetcentral.com",
                "plan": "PRO",
            },
            headers=superadmin_headers,
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert resp.headers["location"].startswith(PANEL + "?success=")

        db = TestingSessionLocal()
        try:
            comercio = db.query(Comercio).filter(Comercio.email == "admin@vetcentral.com").first()
            assert comercio is not None
            assert comercio.nombre == "Vet Central"
            assert comercio.plan == "PRO"
            assert comercio.estado == "ACTIVO"
            assert comercio.fecha_registro is not None
            admin = db.query(Usuario).filter(
                Usuario.email == "admin@vetcentral.com",
                Usuario.rol == "ADMIN",
            ).first()
            assert admin is not None
            assert admin.comercio_id == comercio.id
        finally:
            db.close()

    def test_nombre_vacio_redirige_error(self, client, superadmin_headers):
        resp = client.post(
            PANEL,
            data={"nombre": " ", "email": "a@b.com", "plan": "DEMO"},
            headers=superadmin_headers,
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert "error=" in resp.headers["location"]

    def test_email_duplicado_redirige_error(self, client, superadmin_headers):
        db = TestingSessionLocal()
        try:
            db.add(Usuario(
                email="dup@comercio.com",
                password_hash=hash_password("x"),
                rol="ADMIN",
                comercio_id=1,
                activo=True,
            ))
            db.commit()
        finally:
            db.close()
        resp = client.post(
            PANEL,
            data={"nombre": "Duplicado", "email": "dup@comercio.com", "plan": "DEMO"},
            headers=superadmin_headers,
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert "registrado" in resp.headers["location"]

    def test_plan_invalido_redirige_error(self, client, superadmin_headers):
        resp = client.post(
            PANEL,
            data={"nombre": "X", "email": "x@x.com", "plan": "PREMIUM"},
            headers=superadmin_headers,
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert "error=" in resp.headers["location"]


class TestImpersonacion:
    def test_impersonar_admin_ok(self, client, superadmin_headers, admin_user):
        resp = client.post(
            f"{PANEL}/1/impersonar",
            headers=superadmin_headers,
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert resp.headers["location"] == "/page/"
        token = _cookie_token(resp)
        assert token is not None
        client.cookies.set("access_token", token)

        pagina = client.get("/page/")
        assert pagina.status_code == 200
        assert "Vista rapida" in pagina.text
        assert "Comercio Test" in pagina.text

    def test_impersonado_no_es_superadmin(self, client, superadmin_headers, admin_user):
        resp = client.post(
            f"{PANEL}/1/impersonar",
            headers=superadmin_headers,
            follow_redirects=False,
        )
        token = _cookie_token(resp)
        assert token is not None
        client.cookies.set("access_token", token)
        ruta = client.get(PANEL)
        assert ruta.status_code == 403

    def test_impersonar_sin_admin_400(self, client, superadmin_headers):
        cid = _crear_comercio(nombre="Sin Admin")
        resp = client.post(
            f"{PANEL}/{cid}/impersonar",
            headers=superadmin_headers,
            follow_redirects=False,
        )
        assert resp.status_code == 400

    def test_impersonar_inexistente_404(self, client, superadmin_headers):
        resp = client.post(f"{PANEL}/999/impersonar", headers=superadmin_headers)
        assert resp.status_code == 404

    def test_salir_impersonacion_restaura_superadmin(self, client, superadmin_headers, admin_user):
        resp = client.post(
            f"{PANEL}/1/impersonar",
            headers=superadmin_headers,
            follow_redirects=False,
        )
        token = _cookie_token(resp)
        assert token is not None
        client.cookies.set("access_token", token)
        assert client.get("/page/").status_code == 200

        salida = client.post(
            "/admin/salir-impersonacion",
            follow_redirects=False,
        )
        assert salida.status_code == 303
        assert salida.headers["location"] == PANEL
        token_super = _cookie_token(salida)
        assert token_super is not None
        client.cookies.set("access_token", token_super)

        panel = client.get(PANEL)
        assert panel.status_code == 200
        assert "Gestion de Comercios" in panel.text

    def test_salir_sin_impersonacion_401(self, client):
        resp = client.post("/admin/salir-impersonacion")
        assert resp.status_code == 401