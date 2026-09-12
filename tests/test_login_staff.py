from tests.conftest import TestingSessionLocal

from app.models.usuario import Usuario
from app.services.auth import hash_password


def _seed_usuario(rol):
    db = TestingSessionLocal()
    db.add(Usuario(
        email=f"{rol.lower()}@test.com",
        password_hash=hash_password("secret123"),
        rol=rol,
        comercio_id=1,
        activo=True,
    ))
    db.commit()
    db.close()


class TestLoginPage:
    def test_get_login_muestra_formulario(self, client):
        resp = client.get("/login")
        assert resp.status_code == 200
        assert "Iniciar Sesion" in resp.text
        assert 'name="email"' in resp.text
        assert 'name="password"' in resp.text

    def test_get_root_redirige_a_page(self, client):
        resp = client.get("/", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["location"] == "/page/"


class TestLoginSubmit:
    def test_login_valido_redirige_a_page(self, client):
        _seed_usuario("ADMIN")
        resp = client.post("/login", data={
            "email": "admin@test.com",
            "password": "secret123",
        }, follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/page/"
        assert "access_token" in resp.headers.get("set-cookie", "")

    def test_login_contrasena_incorrecta_muestra_error(self, client):
        _seed_usuario("ADMIN")
        resp = client.post("/login", data={
            "email": "admin@test.com",
            "password": "mal",
        })
        assert resp.status_code == 401
        assert "incorrectos" in resp.text

    def test_login_usuario_inexistente_muestra_error(self, client):
        resp = client.post("/login", data={
            "email": "noexiste@test.com",
            "password": "cualquiera",
        })
        assert resp.status_code == 401
        assert "incorrectos" in resp.text

    def test_login_rechaza_rol_cliente(self, client):
        _seed_usuario("CLIENTE")
        resp = client.post("/login", data={
            "email": "cliente@test.com",
            "password": "secret123",
        }, follow_redirects=False)
        assert resp.status_code == 401
        assert "incorrectos" in resp.text
        assert "set-cookie" not in resp.headers


class TestRedirectNoAutenticado:
    def test_navegador_admin_302_a_login(self, client):
        resp = client.get(
            "/admin/personalizacion",
            headers={"Accept": "text/html"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert resp.headers["location"] == "/login"

    def test_api_admin_mantiene_401(self, client):
        resp = client.get("/admin/personalizacion")
        assert resp.status_code == 401
        assert resp.json() == {"detail": "No autenticado"}
