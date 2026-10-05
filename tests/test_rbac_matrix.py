"""Matriz RBAC de 4 niveles y aislamiento multi-tenant (Iteracion 3).

Cubre lo mismo que `scripts/verificar_rbac.py`, pero contra `TestClient` y con
la BD en memoria de `tests/conftest.py`, para que CI lo ejecute en cada push.

Los endpoints DIFERIDOS se marcan con `pytest.mark.xfail(strict=False)`: el
comportamiento actual (anonimo entra) queda documentado como fallido esperado,
de modo que la suite sigue verde pero el gap sigue visible. Cuando se le agregue
el guard, el xfail se convierte en XPASS y hay que sacarlo.
"""

import pytest

from app.models.cliente import Cliente
from app.models.comercio import Comercio
from app.models.usuario import Usuario
from app.services.auth import hash_password
from tests.conftest import TestingSessionLocal

ANON = "ANON"
SUPERADMIN = "SUPERADMIN"
ADMIN_COMERCIO = "ADMIN_COMERCIO"
EMPLEADO = "EMPLEADO"
CLIENTE = "CLIENTE"


def _login(client, email, password):
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
def niveles_sembrados():
    """Siembra en la BD en memoria los 4 niveles y un segundo tenant.

    `ADMIN_COMERCIO` y `EMPLEADO` pertenecen al comercio 1. `SUPERADMIN` tiene
    comercio_id None. `CLIENTE` necesita fila `Cliente` vinculada por
    `usuario_id` o `/portal/*` responde 404 (`app/routers/portal.py:35`).
    """
    db = TestingSessionLocal()
    try:
        # `conftest.admin_user` crea el comercio 1, pero esta fixture no depende
        # de ella: se siembra acá para que los tests sean autonomos.
        db.add(Comercio(
            id=1, nombre="Comercio Base", tipo_comercio="PELUQUERIA", activo=True,
            # Los opt-in en True replican COMERCIO_DATA de scripts/seed_alpha.py:
            # sin ellos el gate de modulo responde 403 y la matriz no puede
            # distinguir "sin permiso" de "modulo apagado".
            habilitar_red_comunitaria=True,
            habilitar_modulo_solidario=True,
            habilitar_cumpleanos=True,
        ))
        db.add_all([
            Usuario(
                email="matriz_super@test.com",
                password_hash=hash_password("super123"),
                rol="ADMIN", comercio_id=None, activo=True,
            ),
            Usuario(
                email="matriz_admin@test.com",
                password_hash=hash_password("admin123"),
                rol="ADMIN", comercio_id=1, activo=True,
            ),
            Usuario(
                email="matriz_empleado@test.com",
                password_hash=hash_password("empleado123"),
                rol="EMPLEADO", comercio_id=1, activo=True,
            ),
        ])
        cliente_usuario = Usuario(
            email="matriz_cliente@test.com",
            password_hash=hash_password("cliente123"),
            rol="CLIENTE", comercio_id=1, activo=True,
        )
        db.add(cliente_usuario)
        db.flush()
        db.add(Cliente(
            usuario_id=cliente_usuario.id, comercio_id=1,
            nombre="Cliente Matriz", email=cliente_usuario.email, activo=True,
        ))

        # Segundo tenant, para las pruebas de aislamiento.
        db.add(Comercio(id=2, nombre="Comercio Otro", tipo_comercio="PELUQUERIA", activo=True))
        db.commit()
    finally:
        db.close()


@pytest.fixture
def headers_4_niveles(client, niveles_sembrados):
    """Cabeceras JWT de los 4 niveles. Deja cookie jar con sesion del ultimo login."""
    return {
        SUPERADMIN: _login(client, "matriz_super@test.com", "super123"),
        ADMIN_COMERCIO: _login(client, "matriz_admin@test.com", "admin123"),
        EMPLEADO: _login(client, "matriz_empleado@test.com", "empleado123"),
        CLIENTE: _login(client, "matriz_cliente@test.com", "cliente123"),
    }


# ---------------------------------------------------------------------------
# Matriz (endpoint, metodo) -> {nivel: codigo esperado}
# ---------------------------------------------------------------------------

MATRIZ = [
    ("GET", "/api/v1/health", {
        ANON: 200, SUPERADMIN: 200, ADMIN_COMERCIO: 200, EMPLEADO: 200, CLIENTE: 200,
    }),
    # Las rutas POST de login quedan fuera de la matriz: sin body devuelven 422
    # (validacion de FastAPI) en vez del codigo de permisos. Ver clase
    # TestLoginNiveles mas abajo.
    ("GET", "/auth/me", {
        ANON: 401, SUPERADMIN: 200, ADMIN_COMERCIO: 200, EMPLEADO: 200, CLIENTE: 200,
    }),

    ("GET", "/admin/comercios", {
        ANON: 401, SUPERADMIN: 200, ADMIN_COMERCIO: 403, EMPLEADO: 403, CLIENTE: 403,
    }),
    ("GET", "/comercios/", {
        ANON: 401, SUPERADMIN: 200, ADMIN_COMERCIO: 403, EMPLEADO: 403, CLIENTE: 403,
    }),

    ("GET", "/clientes/", {
        ANON: 401, SUPERADMIN: 400, ADMIN_COMERCIO: 200, EMPLEADO: 200, CLIENTE: 403,
    }),
    ("GET", "/clientes/?comercio_id=2", {ADMIN_COMERCIO: 403, EMPLEADO: 403}),
    ("GET", "/ventas/", {
        ANON: 401, ADMIN_COMERCIO: 200, EMPLEADO: 403, CLIENTE: 403,
    }),
    ("GET", "/caja/actual", {
        # 404 y no 200: el comercio no tiene caja abierta. Lo que se prueba es
        # que el guard de rol responde antes de tocar la caja.
        ANON: 401, ADMIN_COMERCIO: 404, EMPLEADO: 403, CLIENTE: 403,
    }),
    ("GET", "/dashboard/resumen", {
        ANON: 401, ADMIN_COMERCIO: 200, EMPLEADO: 403, CLIENTE: 403,
    }),
    ("GET", "/productos/", {
        ANON: 401, ADMIN_COMERCIO: 200, EMPLEADO: 403, CLIENTE: 403,
    }),
    ("GET", "/reportes/caja/pdf", {
        ANON: 401, ADMIN_COMERCIO: 200, EMPLEADO: 403, CLIENTE: 403,
    }),

    ("GET", "/page/marketing", {
        ANON: 401, ADMIN_COMERCIO: 200, EMPLEADO: 200, CLIENTE: 403,
    }),
    ("GET", "/admin/personalizacion", {
        ANON: 401, ADMIN_COMERCIO: 200, EMPLEADO: 403, CLIENTE: 403,
    }),
    ("GET", "/api/v1/marketing/cumpleanos/proximos", {
        ANON: 401, SUPERADMIN: 400, ADMIN_COMERCIO: 200, EMPLEADO: 200, CLIENTE: 403,
    }),

    ("GET", "/portal/me", {
        ANON: 401, ADMIN_COMERCIO: 404, EMPLEADO: 403, CLIENTE: 200,
    }),
]


class TestMatrizRbac:
    @pytest.mark.parametrize("metodo,endpoint,esperados", MATRIZ)
    def test_celda_de_la_matriz(self, client, headers_4_niveles, metodo, endpoint, esperados):
        for nivel, esperado in esperados.items():
            if nivel == ANON:
                # TestClient mantiene un cookie jar: los logins de la fixture
                # dejarian una `access_token` pegada y el caso "anonimo" no lo
                # seria. `get_current_user` lee el header y despues la cookie.
                client.cookies.clear()
                resp = client.request(metodo, endpoint)
            else:
                resp = client.request(
                    metodo, endpoint, headers=headers_4_niveles[nivel]
                )
            assert resp.status_code == esperado, (
                f"{metodo} {endpoint} como {nivel}: {resp.status_code} != {esperado}"
            )


class TestLoginNiveles:
    """Los dos canales de login dan veredictos distintos para el mismo usuario.

    `POST /auth/login` (API) acepta CLIENTE; `POST /login` (formulario staff)
    lo rechaza con 401 porque `login.py:44` exige rol en ("ADMIN", "EMPLEADO").
    """

    def test_api_credenciales_invalidas_401(self, client, niveles_sembrados):
        client.cookies.clear()
        resp = client.post(
            "/auth/login", json={"email": "nadie@test.com", "password": "mal"}
        )
        assert resp.status_code == 401

    def test_api_login_ok_para_cliente(self, client, niveles_sembrados):
        client.cookies.clear()
        resp = client.post(
            "/auth/login", json={"email": "matriz_cliente@test.com", "password": "cliente123"}
        )
        assert resp.status_code == 200
        assert resp.json()["access_token"]

    def test_formulario_staff_rechaza_cliente(self, client, niveles_sembrados):
        client.cookies.clear()
        resp = client.post(
            "/login", data={"email": "matriz_cliente@test.com", "password": "cliente123"}
        )
        assert resp.status_code == 401

    def test_formulario_staff_acepta_admin(self, client, niveles_sembrados):
        client.cookies.clear()
        resp = client.post(
            "/login",
            data={"email": "matriz_admin@test.com", "password": "admin123"},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert resp.headers["location"] == "/page/"

    def test_formulario_staff_rechaza_contrasena_incorrecta(self, client, niveles_sembrados):
        client.cookies.clear()
        resp = client.post("/login", data={"email": "matriz_admin@test.com", "password": "mal"})
        assert resp.status_code == 401


class TestGuardsDePlataforma:
    def test_anonimo_no_crea_comercios(self, client):
        resp = client.post("/comercios/", json={"nombre": "Intruso"})
        assert resp.status_code == 401

    def test_admin_de_comercio_no_crea_comercios(self, client, headers_4_niveles):
        resp = client.post(
            "/comercios/", json={"nombre": "Intruso"}, headers=headers_4_niveles[ADMIN_COMERCIO]
        )
        assert resp.status_code == 403

    def test_admin_no_borra_su_propio_tenant(self, client, headers_4_niveles):
        """Borrar un comercio es autoridad de plataforma, no del Admin de ese comercio."""
        resp = client.delete("/comercios/1", headers=headers_4_niveles[ADMIN_COMERCIO])
        assert resp.status_code == 403

    def test_anonimo_no_borra_tenants(self, client):
        resp = client.delete("/comercios/1")
        assert resp.status_code == 401

    def test_superadmin_borra_comercio(self, client, headers_4_niveles):
        resp = client.delete("/comercios/2", headers=headers_4_niveles[SUPERADMIN])
        assert resp.status_code == 204

    def test_admin_no_actualiza_otro_comercio(self, client, headers_4_niveles):
        resp = client.put(
            "/comercios/2", json={"nombre": "Secuestrado"}, headers=headers_4_niveles[ADMIN_COMERCIO]
        )
        assert resp.status_code == 403

    def test_empleado_no_actualiza_comercio(self, client, headers_4_niveles):
        resp = client.put(
            "/comercios/1", json={"nombre": "No puede"}, headers=headers_4_niveles[EMPLEADO]
        )
        assert resp.status_code == 403


class TestAislamientoTenantClientes:
    """El agujero mas grave de la Iteracion 2: `GET /clientes/` sin auth y con
    `comercio_id` libre en el query string."""

    def test_anonimo_no_enumera_clientes(self, client):
        resp = client.get("/clientes/")
        assert resp.status_code == 401

    def test_anonimo_no_puede_forzar_comercio(self, client):
        resp = client.get("/clientes/?comercio_id=1")
        assert resp.status_code == 401

    def test_admin_solo_ve_su_tenant(self, client, headers_4_niveles):
        db = TestingSessionLocal()
        try:
            db.add(Cliente(comercio_id=2, nombre="Cliente Del Otro", activo=True))
            db.commit()
        finally:
            db.close()

        resp = client.get("/clientes/", headers=headers_4_niveles[ADMIN_COMERCIO])
        assert resp.status_code == 200
        nombres = [c["nombre"] for c in resp.json()]
        assert "Cliente Del Otro" not in nombres

    def test_admin_no_crea_cliente_en_otro_tenant(self, client, headers_4_niveles):
        """El `comercio_id` del body se fuerza desde el token: enviar 2 no alcanza."""
        resp = client.post(
            "/clientes/",
            json={"comercio_id": 2, "nombre": "Infiltrado"},
            headers=headers_4_niveles[ADMIN_COMERCIO],
        )
        assert resp.status_code == 201
        assert resp.json()["comercio_id"] == 1

    def test_admin_no_ve_cliente_de_otro_tenant(self, client, headers_4_niveles):
        db = TestingSessionLocal()
        try:
            otro = Cliente(comercio_id=2, nombre="Cliente Del Otro", activo=True)
            db.add(otro)
            db.commit()
            otro_id = otro.id
        finally:
            db.close()

        resp = client.get(f"/clientes/{otro_id}", headers=headers_4_niveles[ADMIN_COMERCIO])
        assert resp.status_code == 403

    def test_superadmin_necesita_comercio_explicito(self, client, headers_4_niveles):
        resp = client.get("/clientes/", headers=headers_4_niveles[SUPERADMIN])
        assert resp.status_code == 400
        assert "comercio_id" in resp.json()["detail"]

    def test_superadmin_puede_consultar_un_comercio(self, client, headers_4_niveles):
        resp = client.get("/clientes/?comercio_id=1", headers=headers_4_niveles[SUPERADMIN])
        assert resp.status_code == 200


class TestAislamientoTenantComercios:
    def test_admin_lectura_su_tenant(self, client, headers_4_niveles):
        resp = client.get("/comercios/1", headers=headers_4_niveles[ADMIN_COMERCIO])
        assert resp.status_code == 200

    def test_admin_lectura_otro_tenant_denegado(self, client, headers_4_niveles):
        resp = client.get("/comercios/2", headers=headers_4_niveles[ADMIN_COMERCIO])
        assert resp.status_code == 403

    def test_empleado_lectura_otro_tenant_denegado(self, client, headers_4_niveles):
        resp = client.get("/comercios/2", headers=headers_4_niveles[EMPLEADO])
        assert resp.status_code == 403

    def test_optin_de_otro_tenant_denegado(self, client, headers_4_niveles):
        resp = client.patch(
            "/comercios/2/opt-in",
            json={"habilitar_red_comunitaria": True},
            headers=headers_4_niveles[ADMIN_COMERCIO],
        )
        assert resp.status_code == 403


@pytest.mark.xfail(strict=False, reason="sin guard: app/routers/mascotas.py")
def test_diferido_mascotas_sin_guard(client):
    resp = client.get("/mascotas/")
    assert resp.status_code == 401


@pytest.mark.xfail(strict=False, reason="sin guard: app/routers/atenciones.py")
def test_diferido_atenciones_sin_guard(client):
    resp = client.get("/atenciones/")
    assert resp.status_code == 401


@pytest.mark.xfail(strict=False, reason="sin guard: app/routers/admin_turnos.py")
def test_diferido_turnos_sin_guard(client):
    resp = client.get("/page/turnos")
    assert resp.status_code == 401


@pytest.mark.xfail(strict=False, reason="sin guard y con comercio_id=1 fijo: reports.py")
def test_diferido_page_reportes_sin_guard(client):
    resp = client.get("/page/reportes")
    assert resp.status_code == 401