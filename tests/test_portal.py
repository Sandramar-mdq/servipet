class TestPortalMe:
    def test_portal_me_authenticated(self, client, auth_headers):
        resp = client.get("/portal/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["nombre"] == "Usuario Test"
        assert "mascotas" in data

    def test_portal_me_no_auth(self, client):
        resp = client.get("/portal/me")
        assert resp.status_code == 401


class TestPortalMascotas:
    def test_listar_mascotas_empty(self, client, auth_headers):
        resp = client.get("/portal/mascotas", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_crear_mascota(self, client, auth_headers):
        resp = client.post("/portal/mascotas", headers=auth_headers, json={
            "nombre": "Max",
            "especie": "Perro",
            "raza": "Labrador",
            "peso": 25.0,
            "edad": 3,
            "sexo": "Macho",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["nombre"] == "Max"
        assert data["especie"] == "Perro"
        assert data["activo"] is True

    def test_listar_mascotas_after_create(self, client, auth_headers):
        client.post("/portal/mascotas", headers=auth_headers, json={
            "nombre": "Luna",
            "especie": "Gato",
        })
        resp = client.get("/portal/mascotas", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["nombre"] == "Luna"

    def test_crear_mascota_no_auth(self, client):
        resp = client.post("/portal/mascotas", json={"nombre": "Test"})
        assert resp.status_code == 401


class TestPortalServicios:
    def test_listar_servicios(self, client, auth_headers):
        resp = client.get("/portal/servicios", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_listar_servicios_no_auth(self, client):
        resp = client.get("/portal/servicios")
        assert resp.status_code == 401


class TestPortalHistorial:
    def test_historial_mascota_not_found(self, client, auth_headers):
        resp = client.get("/portal/mascotas/999/historial", headers=auth_headers)
        assert resp.status_code == 404
