class TestRegister:
    def test_register_success(self, client):
        resp = client.post("/auth/register", json={
            "email": "nuevo@test.com",
            "password": "pass123",
            "nombre": "Nuevo Usuario",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "nuevo@test.com"
        assert data["rol"] == "CLIENTE"
        assert data["activo"] is True
        assert "id" in data

    def test_register_duplicate_email(self, client, registered_user):
        resp = client.post("/auth/register", json={
            "email": "test@test.com",
            "password": "other123",
            "nombre": "Duplicado",
        })
        assert resp.status_code == 400
        assert "email ya esta registrado" in resp.json()["detail"]

    def test_register_requires_email_or_phone(self, client):
        resp = client.post("/auth/register", json={
            "password": "pass123",
            "nombre": "Sin Contacto",
        })
        assert resp.status_code == 400


class TestLogin:
    def test_login_success(self, client, registered_user):
        resp = client.post("/auth/login", json={
            "email": "test@test.com",
            "password": "test123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["usuario"]["email"] == "test@test.com"

    def test_login_wrong_password(self, client, registered_user):
        resp = client.post("/auth/login", json={
            "email": "test@test.com",
            "password": "wrongpass",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post("/auth/login", json={
            "email": "noexiste@test.com",
            "password": "pass123",
        })
        assert resp.status_code == 401


class TestMe:
    def test_me_authenticated(self, client, auth_headers):
        resp = client.get("/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "test@test.com"
        assert data["rol"] == "CLIENTE"

    def test_me_unauthenticated(self, client):
        resp = client.get("/auth/me")
        assert resp.status_code == 401

    def test_me_invalid_token(self, client):
        resp = client.get("/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
        assert resp.status_code == 401
