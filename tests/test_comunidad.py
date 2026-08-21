"""Tests del modulo Comunidad Servipet (Etapas 7.2 y 7.3)."""

import io

from app.dependencies import COOKIE_SESION
from app.models.cliente import Cliente
from app.services.auth_tokens import crear_token
from tests.conftest import TestingSessionLocal


BASE = "/api/v1/comunidad"


def _activar_optin(client, admin_headers, comercio_id=1):
    resp = client.patch(
        f"/comercios/{comercio_id}/opt-in",
        headers=admin_headers,
        json={"habilitar_red_comunitaria": True},
    )
    assert resp.status_code == 200, resp.text
    return resp


def _crear_comercio_sin_optin(client):
    """Crea un comercio nuevo (sin red comunitaria) via API publica."""
    resp = client.post("/comercios/", json={"nombre": "Comercio Sin Red"})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _crear_aviso(client, headers, **overrides):
    datos = {
        "tipo": "PERDIDA",
        "titulo": "Gato perdido",
        "descripcion": "Se busco en todo el barrio",
    }
    datos.update(overrides)
    return client.post(f"{BASE}/1/avisos", headers=headers, data=datos)


def _registrar_segundo_cliente(client):
    resp = client.post("/auth/register", json={
        "email": "otro@test.com",
        "password": "test123",
        "nombre": "Otro Cliente",
    })
    assert resp.status_code == 201, resp.text
    login = client.post("/auth/login", json={
        "email": "otro@test.com",
        "password": "test123",
    })
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


class TestOptInComercio:
    def test_optin_requiere_auth(self, client):
        resp = client.patch("/comercios/1/opt-in", json={"habilitar_red_comunitaria": True})
        assert resp.status_code == 401

    def test_optin_requiere_admin(self, client, auth_headers):
        resp = client.patch(
            "/comercios/1/opt-in",
            headers=auth_headers,
            json={"habilitar_red_comunitaria": True},
        )
        assert resp.status_code == 403

    def test_activar_y_desactivar_optin(self, client, admin_headers):
        resp = _activar_optin(client, admin_headers)
        assert resp.json()["habilitar_red_comunitaria"] is True

        resp = client.patch(
            "/comercios/1/opt-in",
            headers=admin_headers,
            json={"habilitar_red_comunitaria": False},
        )
        assert resp.status_code == 200
        assert resp.json()["habilitar_red_comunitaria"] is False

    def test_optin_comercio_inexistente(self, client, admin_headers):
        # El admin de otro comercio no puede configurar un comercio ajeno (403
        # antes que 404 para no filtrar existencia).
        resp = client.patch(
            "/comercios/999/opt-in",
            headers=admin_headers,
            json={"habilitar_red_comunitaria": True},
        )
        assert resp.status_code == 403


class TestFeedPublico:
    def test_feed_comercio_inexistente(self, client):
        resp = client.get(f"{BASE}/999/avisos")
        assert resp.status_code == 404

    def test_feed_sin_optin_devuelve_403(self, client):
        comercio_id = _crear_comercio_sin_optin(client)
        resp = client.get(f"{BASE}/{comercio_id}/avisos")
        assert resp.status_code == 403
        assert "deshabilitada" in resp.json()["detail"]

    def test_feed_paginacion_y_filtro_tipo(self, client, admin_headers):
        _activar_optin(client, admin_headers)
        _crear_aviso(client, admin_headers, titulo="Aviso PERDIDA 1")
        _crear_aviso(client, admin_headers, titulo="Aviso PERDIDA 2")
        _crear_aviso(client, admin_headers, tipo="ADOPCION", titulo="Cachorros en adopcion")

        resp = client.get(f"{BASE}/1/avisos")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert data["limit"] == 10
        assert data["offset"] == 0
        assert len(data["items"]) == 3

        # Paginado
        resp = client.get(f"{BASE}/1/avisos?limit=2&offset=0")
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 2
        resp = client.get(f"{BASE}/1/avisos?limit=2&offset=2")
        data = resp.json()
        assert len(data["items"]) == 1

        # Filtro por tipo
        resp = client.get(f"{BASE}/1/avisos?tipo=PERDIDA")
        data = resp.json()
        assert data["total"] == 2
        assert all(a["tipo"] == "PERDIDA" for a in data["items"])

    def test_feed_filtro_estado(self, client, admin_headers):
        _activar_optin(client, admin_headers)
        r = _crear_aviso(client, admin_headers, titulo="Para resolver")
        aviso_id = r.json()["id"]

        resp = client.get(f"{BASE}/1/avisos?estado=RESUELTO")
        assert resp.json()["total"] == 0

        client.patch(
            f"{BASE}/avisos/{aviso_id}/estado",
            headers=admin_headers,
            json={"estado": "RESUELTO"},
        )
        resp = client.get(f"{BASE}/1/avisos?estado=RESUELTO")
        assert resp.json()["total"] == 1

    def test_feed_limit_fuera_de_rango(self, client, admin_headers):
        _activar_optin(client, admin_headers)
        resp = client.get(f"{BASE}/1/avisos?limit=50")
        assert resp.status_code == 422

    def test_feed_privacidad_telefono(self, client, admin_headers):
        _activar_optin(client, admin_headers)
        _crear_aviso(client, admin_headers, titulo="Via comercio", telefono_contacto="5491100000000")
        _crear_aviso(
            client,
            admin_headers,
            titulo="Directo whatsapp",
            tipo_contacto="DIRECTO_WHATSAPP",
            telefono_contacto="5491111111111",
        )

        resp = client.get(f"{BASE}/1/avisos")
        items = {a["titulo"]: a for a in resp.json()["items"]}
        assert items["Via comercio"]["telefono_contacto"] is None
        assert items["Directo whatsapp"]["telefono_contacto"] == "5491111111111"


class TestCrearAviso:
    def test_crear_requiere_auth(self, client, admin_headers):
        _activar_optin(client, admin_headers)
        client.cookies.clear()  # simula un visitante sin sesion ni token
        resp = client.post(f"{BASE}/1/avisos", data={
            "tipo": "PERDIDA",
            "titulo": "Sin auth",
            "descripcion": "Debe fallar",
        })
        assert resp.status_code == 401

    def test_crear_sin_optin_devuelve_403(self, client, admin_headers):
        resp = _crear_aviso(client, admin_headers)
        assert resp.status_code == 403

    def test_crear_exitoso_como_admin(self, client, admin_headers):
        _activar_optin(client, admin_headers)
        resp = _crear_aviso(client, admin_headers)
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["tipo"] == "PERDIDA"
        assert data["estado"] == "ACTIVO"
        assert data["tipo_contacto"] == "VIA_COMERCIO"
        assert data["creado_por_usuario_id"] is not None
        assert data["cliente_id"] is None
        assert data["foto_url"] is None

    def test_crear_como_cliente(self, client, admin_headers, auth_headers):
        _activar_optin(client, admin_headers)
        resp = _crear_aviso(client, auth_headers, titulo="Aviso de cliente")
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["cliente_id"] is not None
        assert data["creado_por_usuario_id"] is not None

    def test_crear_whatsapp_sin_telefono_falla(self, client, admin_headers):
        _activar_optin(client, admin_headers)
        resp = _crear_aviso(
            client,
            admin_headers,
            tipo_contacto="DIRECTO_WHATSAPP",
        )
        assert resp.status_code == 422

    def test_crear_con_imagen(self, client, admin_headers, monkeypatch):
        _activar_optin(client, admin_headers)

        def fake_upload(file_bytes, folder="servipet/avisos"):
            assert isinstance(file_bytes, bytes) and file_bytes
            return {
                "secure_url": "https://res.cloudinary.com/demo/foto.jpg",
                "public_id": "servipet/avisos/foto",
            }

        monkeypatch.setattr("app.routers.comunidad.cloudinary_service.upload_image", fake_upload)

        resp = client.post(
            f"{BASE}/1/avisos",
            headers=admin_headers,
            data={
                "tipo": "ENCONTRADA",
                "titulo": "Perro encontrado",
                "descripcion": "Con collar azul",
            },
            files={"imagen": ("foto.png", io.BytesIO(b"fake-image-bytes"), "image/png")},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["foto_url"] == "https://res.cloudinary.com/demo/foto.jpg"
        assert data["public_id_cloudinary"] == "servipet/avisos/foto"

    def test_crear_con_archivo_no_imagen_falla(self, client, admin_headers):
        _activar_optin(client, admin_headers)
        resp = client.post(
            f"{BASE}/1/avisos",
            headers=admin_headers,
            data={"tipo": "PERDIDA", "titulo": "T", "descripcion": "D"},
            files={"imagen": ("doc.pdf", io.BytesIO(b"%PDF"), "application/pdf")},
        )
        assert resp.status_code == 400


class TestCambioEstado:
    def test_patch_resuelto_como_admin(self, client, admin_headers):
        _activar_optin(client, admin_headers)
        aviso_id = _crear_aviso(client, admin_headers).json()["id"]

        resp = client.patch(
            f"{BASE}/avisos/{aviso_id}/estado",
            headers=admin_headers,
            json={"estado": "RESUELTO"},
        )
        assert resp.status_code == 200
        assert resp.json()["estado"] == "RESUELTO"

    def test_patch_estado_invalido(self, client, admin_headers):
        _activar_optin(client, admin_headers)
        aviso_id = _crear_aviso(client, admin_headers).json()["id"]
        resp = client.patch(
            f"{BASE}/avisos/{aviso_id}/estado",
            headers=admin_headers,
            json={"estado": "VENCIDO"},
        )
        assert resp.status_code == 422

    def test_patch_aviso_inexistente(self, client, admin_headers):
        _activar_optin(client, admin_headers)
        resp = client.patch(
            f"{BASE}/avisos/9999/estado",
            headers=admin_headers,
            json={"estado": "ARCHIVADO"},
        )
        assert resp.status_code == 404

    def test_patch_por_cliente_creador(self, client, admin_headers, auth_headers):
        _activar_optin(client, admin_headers)
        aviso_id = _crear_aviso(client, auth_headers).json()["id"]

        resp = client.patch(
            f"{BASE}/avisos/{aviso_id}/estado",
            headers=auth_headers,
            json={"estado": "RESUELTO"},
        )
        assert resp.status_code == 200
        assert resp.json()["estado"] == "RESUELTO"

    def test_patch_por_otro_cliente_denegado(self, client, admin_headers, auth_headers):
        _activar_optin(client, admin_headers)
        aviso_id = _crear_aviso(client, auth_headers).json()["id"]
        otros_headers = _registrar_segundo_cliente(client)

        resp = client.patch(
            f"{BASE}/avisos/{aviso_id}/estado",
            headers=otros_headers,
            json={"estado": "ARCHIVADO"},
        )
        assert resp.status_code == 403


class TestEliminarAviso:
    def test_delete_como_admin(self, client, admin_headers):
        _activar_optin(client, admin_headers)
        aviso_id = _crear_aviso(client, admin_headers).json()["id"]

        resp = client.delete(f"{BASE}/avisos/{aviso_id}", headers=admin_headers)
        assert resp.status_code == 204

        resp = client.get(f"{BASE}/1/avisos")
        assert resp.json()["total"] == 0

    def test_delete_con_imagen_borra_en_cloudinary(self, client, admin_headers, monkeypatch):
        _activar_optin(client, admin_headers)

        monkeypatch.setattr(
            "app.routers.comunidad.cloudinary_service.upload_image",
            lambda file_bytes, folder="servipet/avisos": {
                "secure_url": "https://res.cloudinary.com/demo/foto.jpg",
                "public_id": "servipet/avisos/foto",
            },
        )
        llamadas = []
        monkeypatch.setattr(
            "app.routers.comunidad.cloudinary_service.delete_image",
            lambda public_id: llamadas.append(public_id) or True,
        )

        aviso_id = client.post(
            f"{BASE}/1/avisos",
            headers=admin_headers,
            data={"tipo": "PERDIDA", "titulo": "Con foto", "descripcion": "D"},
            files={"imagen": ("foto.png", io.BytesIO(b"bytes"), "image/png")},
        ).json()["id"]

        resp = client.delete(f"{BASE}/avisos/{aviso_id}", headers=admin_headers)
        assert resp.status_code == 204
        assert llamadas == ["servipet/avisos/foto"]

    def test_delete_por_cliente_creador(self, client, admin_headers, auth_headers):
        _activar_optin(client, admin_headers)
        aviso_id = _crear_aviso(client, auth_headers).json()["id"]

        resp = client.delete(f"{BASE}/avisos/{aviso_id}", headers=auth_headers)
        assert resp.status_code == 204

    def test_delete_por_otro_cliente_denegado(self, client, admin_headers, auth_headers):
        _activar_optin(client, admin_headers)
        aviso_id = _crear_aviso(client, auth_headers).json()["id"]
        otros_headers = _registrar_segundo_cliente(client)

        resp = client.delete(f"{BASE}/avisos/{aviso_id}", headers=otros_headers)
        assert resp.status_code == 403

    def test_delete_aviso_inexistente(self, client, admin_headers):
        _activar_optin(client, admin_headers)
        resp = client.delete(f"{BASE}/avisos/9999", headers=admin_headers)
        assert resp.status_code == 404


class TestPaginaComunidad:
    """Vista PWA /cliente/comunidad (Etapa 7.3)."""

    def _crear_cliente_db(self):
        db = TestingSessionLocal()
        cliente = Cliente(comercio_id=1, nombre="Cliente PWA", activo=True)
        db.add(cliente)
        db.commit()
        db.refresh(cliente)
        cliente_id = cliente.id
        db.close()
        return cliente_id

    def test_pagina_publica_anonima(self, client):
        resp = client.get("/cliente/comunidad")
        assert resp.status_code == 200
        assert "Comunidad" in resp.text
        # CTA de login para anonimos
        assert "/cliente/login" in resp.text

    def test_pagina_con_sesion_cliente(self, client):
        cliente_id = self._crear_cliente_db()
        client.cookies.set(COOKIE_SESION, crear_token(cliente_id))
        resp = client.get("/cliente/comunidad")
        assert resp.status_code == 200
        # El actor se inyecta como JSON en el data-attribute
        assert '"tipo": "cliente"' in resp.text
        # Con sesion se muestra el boton de nuevo aviso
        assert "btn-nuevo-aviso" in resp.text

    def test_pagina_con_sesion_staff(self, client, admin_headers):
        # admin_headers deja cookie access_token; el staff es reconocido
        resp = client.get("/cliente/comunidad")
        assert resp.status_code == 200
        assert '"es_staff": true' in resp.text


# --- Etapa 7.4: Panel de moderacion admin ---

def _crear_empleado_headers(client):
    """Crea un EMPLEADO del comercio 1 y retorna sus headers Bearer."""
    from app.models.usuario import Usuario
    from app.services.auth import hash_password

    db = TestingSessionLocal()
    db.add(Usuario(
        email="empleado@test.com",
        password_hash=hash_password("emple123"),
        rol="EMPLEADO",
        comercio_id=1,
        activo=True,
    ))
    db.commit()
    db.close()
    login = client.post("/auth/login", json={
        "email": "empleado@test.com",
        "password": "emple123",
    })
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


class TestListadoAdmin:
    def test_requiere_auth(self, client):
        resp = client.get(f"{BASE}/admin/1/avisos")
        assert resp.status_code == 401

    def test_cliente_rol_denegado(self, client, admin_headers, auth_headers):
        resp = client.get(f"{BASE}/admin/1/avisos", headers=auth_headers)
        assert resp.status_code == 403

    def test_otro_comercio_denegado(self, client, admin_headers):
        otro_id = _crear_comercio_sin_optin(client)
        resp = client.get(f"{BASE}/admin/{otro_id}/avisos", headers=admin_headers)
        assert resp.status_code == 403

    def test_funciona_con_optin_apagado(self, client, admin_headers):
        # Se crean avisos con la red activa y luego se apaga el opt-in:
        # el feed publico da 403 pero el panel debe poder listar igual.
        _activar_optin(client, admin_headers)
        _crear_aviso(client, admin_headers, titulo="Aviso pre-apagado")
        client.patch(
            "/comercios/1/opt-in",
            headers=admin_headers,
            json={"habilitar_red_comunitaria": False},
        )

        assert client.get(f"{BASE}/1/avisos").status_code == 403

        resp = client.get(f"{BASE}/admin/1/avisos", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_lista_todos_los_estados_y_filtra(self, client, admin_headers):
        _activar_optin(client, admin_headers)
        a1 = _crear_aviso(client, admin_headers, titulo="Uno").json()["id"]
        a2 = _crear_aviso(client, admin_headers, titulo="Dos").json()["id"]
        client.patch(f"{BASE}/avisos/{a1}/estado", headers=admin_headers, json={"estado": "ARCHIVADO"})
        client.patch(f"{BASE}/avisos/{a2}/estado", headers=admin_headers, json={"estado": "RESUELTO"})

        todos = client.get(f"{BASE}/admin/1/avisos", headers=admin_headers).json()
        assert todos["total"] == 2

        archivados = client.get(
            f"{BASE}/admin/1/avisos?estado=ARCHIVADO", headers=admin_headers
        ).json()
        assert archivados["total"] == 1
        assert archivados["items"][0]["titulo"] == "Uno"

    def test_telefono_visible_para_staff(self, client, admin_headers):
        # En el feed publico el telefono VIA_COMERCIO se enmascara;
        # en el listado de moderacion el staff lo ve completo.
        _activar_optin(client, admin_headers)
        _crear_aviso(client, admin_headers, titulo="Con telefono", telefono_contacto="5491177776666")

        publico = client.get(f"{BASE}/1/avisos").json()
        assert publico["items"][0]["telefono_contacto"] is None

        admin = client.get(f"{BASE}/admin/1/avisos", headers=admin_headers).json()
        assert admin["items"][0]["telefono_contacto"] == "5491177776666"


class TestModeracionEmpleado:
    def test_empleado_no_puede_toggle_optin(self, client, admin_headers):
        empleado_headers = _crear_empleado_headers(client)
        resp = client.patch(
            "/comercios/1/opt-in",
            headers=empleado_headers,
            json={"habilitar_red_comunitaria": True},
        )
        assert resp.status_code == 403

    def test_empleado_archiva_aviso_de_cliente(self, client, admin_headers, auth_headers):
        empleado_headers = _crear_empleado_headers(client)
        _activar_optin(client, admin_headers)
        aviso_id = _crear_aviso(client, auth_headers, titulo="De un cliente").json()["id"]

        resp = client.patch(
            f"{BASE}/avisos/{aviso_id}/estado",
            headers=empleado_headers,
            json={"estado": "ARCHIVADO"},
        )
        assert resp.status_code == 200
        assert resp.json()["estado"] == "ARCHIVADO"

    def test_empleado_elimina_aviso_de_cliente(self, client, admin_headers, auth_headers):
        empleado_headers = _crear_empleado_headers(client)
        _activar_optin(client, admin_headers)
        aviso_id = _crear_aviso(client, auth_headers, titulo="A borrar").json()["id"]

        resp = client.delete(f"{BASE}/avisos/{aviso_id}", headers=empleado_headers)
        assert resp.status_code == 204


class TestPaginaAdminComunidad:
    def test_anonimo_401(self, client):
        resp = client.get("/admin/comunidad")
        assert resp.status_code == 401

    def test_cliente_rol_403(self, client, auth_headers):
        resp = client.get("/admin/comunidad", headers=auth_headers)
        assert resp.status_code == 403

    def test_admin_ve_panel(self, client, admin_headers):
        resp = client.get("/admin/comunidad", headers=admin_headers)
        assert resp.status_code == 200
        assert "comunidad-admin-data" in resp.text
        assert "switch-optin" in resp.text
        assert 'data-es-admin="true"' in resp.text

    def test_empleado_ve_switch_deshabilitado(self, client, admin_headers):
        empleado_headers = _crear_empleado_headers(client)
        resp = client.get("/admin/comunidad", headers=empleado_headers)
        assert resp.status_code == 200
        assert 'data-es-admin="false"' in resp.text
        assert "disabled" in resp.text
