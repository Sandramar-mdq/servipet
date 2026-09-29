"""Tests de la capa de UI del Modulo Solidario / Cumpleanos / Kit (Etapa 12).

Verifica que las paginas y templates nuevos rendericen los puntos de entrada de
la API (`/api/v1/marketing`) y que la navegacion no rompa las reglas de skin
del proyecto.
"""

import pytest
from datetime import date

from app.models.cliente import Cliente
from app.models.comercio import Comercio
from app.models.mascota import Mascota
from app.models.usuario import Usuario
from app.services.auth import hash_password
from tests.conftest import TestingSessionLocal

KIT = "/page/marketing"
DASHBOARD = "/page/dashboard"
MODERACION = "/admin/comunidad"
PERSONALIZACION = "/admin/personalizacion"

HELPERS_JS = "/static/js/marketing_ui.js"


def _tag_input(html, element_id):
    """Devuelve el tag <input> completo: Jinja deja `checked` en la linea siguiente."""
    inicio = html.index(f'id="{element_id}"')
    return html[inicio:html.index(">", inicio)]


@pytest.fixture(autouse=True)
def _usa_bd_de_pruebas(monkeypatch):
    """El context processor y las rutas de pagina resuelven contra la BD de tests."""
    import app.database as database

    monkeypatch.setattr(database, "SessionLocal", TestingSessionLocal)


@pytest.fixture
def empleado_headers(client, admin_user):
    db = TestingSessionLocal()
    try:
        db.add(Usuario(
            email="empleado_ui@test.com",
            password_hash=hash_password("empleado123"),
            rol="EMPLEADO",
            comercio_id=1,
            activo=True,
        ))
        db.commit()
    finally:
        db.close()

    resp = client.post("/auth/login", json={"email": "empleado_ui@test.com", "password": "empleado123"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _comercio(**flags):
    db = TestingSessionLocal()
    try:
        comercio = db.query(Comercio).filter(Comercio.id == 1).first()
        for nombre, valor in flags.items():
            setattr(comercio, nombre, valor)
        db.commit()
    finally:
        db.close()


def _mascota_con_nacimiento(cliente_id=None, nombre="Rocky"):
    """Crea la ficha completa (Cliente + Mascota) porque la pagina exige ambos."""
    db = TestingSessionLocal()
    try:
        if cliente_id is None:
            cliente = Cliente(nombre="Duenio de " + nombre, comercio_id=1, activo=True)
            db.add(cliente)
            db.commit()
            cliente_id = cliente.id

        mascota = Mascota(
            nombre=nombre,
            especie="Perro",
            raza="Mestizo",
            cliente_id=cliente_id,
            fecha_nacimiento=date(2021, 5, 4),
            activo=True,
            fallecida=False,
        )
        db.add(mascota)
        db.commit()
        return mascota.id
    finally:
        db.close()


class TestPaginaKitMarketing:
    def test_anonimo_401(self, client):
        assert client.get(KIT).status_code == 401

    def test_cliente_403(self, client, auth_headers):
        assert client.get(KIT, headers=auth_headers).status_code == 403

    def test_empleado_tiene_acceso(self, client, empleado_headers):
        resp = client.get(KIT, headers=empleado_headers)
        assert resp.status_code == 200, resp.text
        assert 'id="form-kit"' in resp.text

    def test_formulario_expone_los_campos_del_schema(self, client, admin_headers):
        resp = client.get(KIT, headers=admin_headers)
        assert resp.status_code == 200, resp.text
        for campo in (
            'id="kit-titulo"',
            'id="kit-beneficio"',
            'id="kit-descuento"',
            'id="kit-condiciones"',
            'id="kit-usar-branding"',
            'id="kit-registrar"',
            'id="kit-color-primario"',
            'id="kit-color-secundario"',
        ):
            assert campo in resp.text, campo

    def test_limites_del_schema_reflejados_en_el_html(self, client, admin_headers):
        resp = client.get(KIT, headers=admin_headers)
        assert 'maxlength="60"' in resp.text   # titulo
        assert 'maxlength="80"' in resp.text   # beneficio_texto
        assert 'maxlength="40"' in resp.text   # descuento
        assert 'maxlength="200"' in resp.text  # condiciones

    def test_carga_el_helper_y_el_script_del_kit(self, client, admin_headers):
        resp = client.get(KIT, headers=admin_headers)
        assert HELPERS_JS in resp.text
        assert "/static/js/marketing_kit.js" in resp.text
        assert 'id="kit-preview"' in resp.text

    def test_enlace_en_navegacion(self, client, admin_headers):
        resp = client.get(KIT, headers=admin_headers)
        assert resp.text.count('href="/page/marketing"') >= 2  # desktop + movil


class TestWidgetCumpleanosDashboard:
    def test_widget_presente(self, client, admin_headers):
        resp = client.get(DASHBOARD, headers=admin_headers)
        assert resp.status_code == 200, resp.text
        assert 'id="widget-cumpleanos"' in resp.text
        assert 'id="cumple-lista"' in resp.text
        assert 'id="cumple-deshabilitado"' in resp.text
        assert "/static/js/marketing_dashboard.js" in resp.text
        assert HELPERS_JS in resp.text

    def test_ventana_configurable_por_el_template(self, client, admin_headers):
        resp = client.get(DASHBOARD, headers=admin_headers)
        assert 'id="cumpleanos-data"' in resp.text
        assert 'data-dias="7"' in resp.text

    def test_enlace_al_kit_desde_el_dashboard(self, client, admin_headers):
        resp = client.get(DASHBOARD, headers=admin_headers)
        assert 'href="/page/marketing"' in resp.text


class TestFichaMascota:
    def test_boton_oculto_sin_optin(self, client, admin_headers):
        id_mascota = _mascota_con_nacimiento()
        resp = client.get(f"/page/mascotas/{id_mascota}", headers=admin_headers)
        assert resp.status_code == 200, resp.text
        assert "btn-placa-cumpleanos" not in resp.text
        assert "marketing_mascota.js" not in resp.text

    def test_boton_visible_con_optin_y_nacimiento(self, client, admin_headers):
        id_mascota = _mascota_con_nacimiento()
        _comercio(habilitar_cumpleanos=True)

        resp = client.get(f"/page/mascotas/{id_mascota}", headers=admin_headers)
        assert resp.status_code == 200, resp.text
        assert "btn-placa-cumpleanos" in resp.text
        assert "/static/js/marketing_mascota.js" in resp.text
        assert HELPERS_JS in resp.text

    def test_boton_oculto_sin_fecha_de_nacimiento(self, client, admin_headers):
        _comercio(habilitar_cumpleanos=True)
        db = TestingSessionLocal()
        try:
            cliente = Cliente(nombre="Sin Fecha", comercio_id=1, activo=True)
            db.add(cliente)
            db.commit()
            mascota = Mascota(nombre="Sin Cumple", especie="Gato", raza="Criollo",
                              cliente_id=cliente.id, activo=True, fallecida=False)
            db.add(mascota)
            db.commit()
            id_mascota = mascota.id
        finally:
            db.close()

        resp = client.get(f"/page/mascotas/{id_mascota}", headers=admin_headers)
        assert resp.status_code == 200, resp.text
        assert "btn-placa-cumpleanos" not in resp.text


class TestModeracionComunidad:
    def test_aviso_de_modulo_desactivado(self, client, admin_headers):
        resp = client.get(MODERACION, headers=admin_headers)
        assert resp.status_code == 200, resp.text
        assert "Modulo Solidario desactivado" in resp.text
        assert "data-solidario-activo=\"false\"" in resp.text

    def test_sin_aviso_cuando_el_optin_esta_activo(self, client, admin_headers):
        _comercio(habilitar_modulo_solidario=True)
        resp = client.get(MODERACION, headers=admin_headers)
        assert resp.status_code == 200, resp.text
        assert "Modulo Solidario desactivado" not in resp.text
        assert 'data-solidario-activo="true"' in resp.text

    def test_carga_el_helper_antes_del_script_de_moderacion(self, client, admin_headers):
        resp = client.get(MODERACION, headers=admin_headers)
        assert HELPERS_JS in resp.text
        assert resp.text.index(HELPERS_JS) < resp.text.index("/static/js/comunidad_admin.js")

    def test_empleado_ve_el_aviso_de_configuracion(self, client, empleado_headers):
        resp = client.get(MODERACION, headers=empleado_headers)
        assert resp.status_code == 200, resp.text
        assert "Solo un administrador puede activarlo." in resp.text


class TestPanelModulos:
    def test_switches_presentes(self, client, admin_headers):
        resp = client.get(PERSONALIZACION, headers=admin_headers)
        assert resp.status_code == 200, resp.text
        assert 'id="modulos"' in resp.text
        assert 'id="switch-solidario"' in resp.text
        assert 'id="switch-cumpleanos"' in resp.text
        assert "/static/js/marketing_optin.js" in resp.text
        assert HELPERS_JS in resp.text

    def test_switches_reflejan_el_estado_guardado(self, client, admin_headers):
        _comercio(habilitar_modulo_solidario=True, habilitar_cumpleanos=True)
        html = client.get(PERSONALIZACION, headers=admin_headers).text

        for switch in ("switch-solidario", "switch-cumpleanos"):
            assert "checked" in _tag_input(html, switch), switch

    def test_switches_sin_optin_no_marcados(self, client, admin_headers):
        html = client.get(PERSONALIZACION, headers=admin_headers).text

        for switch in ("switch-solidario", "switch-cumpleanos"):
            assert "checked" not in _tag_input(html, switch), switch

    def test_ancla_modulos_es_enlazable(self, client, admin_headers):
        resp = client.get(MODERACION, headers=admin_headers)
        assert "/admin/personalizacion#modulos" in resp.text


class TestRegresionDeSkin:
    def test_home_no_usa_indigo_hardcodeado(self, client):
        """Invariante de tests/test_a11y.py: la home no debe volver a indigo."""
        resp = client.get("/page/")
        assert resp.status_code == 200
        assert "bg-indigo-600" not in resp.text
