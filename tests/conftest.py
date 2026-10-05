import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
# La app corre con DEBUG=false en los tests, y Settings._validar_configuracion
# se niega a arrancar si CORS_ORIGINS queda vacio en ese modo. Se declara un
# origen dummy para ejercitar el camino de produccion.
os.environ["CORS_ORIGINS"] = "http://testserver"

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.comercio import Comercio  # noqa: E402
from app.models.usuario import Usuario  # noqa: E402
from app.services.auth import hash_password  # noqa: E402

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@pytest.fixture(autouse=True)
def setup_and_teardown():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


def _seed_comercio(db):
    c = Comercio(id=1, nombre="Comercio Test", tipo_comercio="VETERINARIA", activo=True)
    db.add(c)
    db.commit()
    return c


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin_user(client):
    db = TestingSessionLocal()
    _seed_comercio(db)
    admin = Usuario(
        email="admin@test.com",
        password_hash=hash_password("admin123"),
        rol="ADMIN",
        comercio_id=1,
        activo=True,
    )
    db.add(admin)
    db.commit()
    db.close()

    resp = client.post("/auth/login", json={
        "email": "admin@test.com",
        "password": "admin123",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.fixture
def admin_headers(admin_user):
    return {"Authorization": f"Bearer {admin_user['access_token']}"}


@pytest.fixture
def superadmin_user(client):
    """SuperAdmin global: rol ADMIN con comercio_id None.

    Necesario para las operaciones de plataforma (`GET/POST /comercios/`,
    `DELETE /comercios/{id}`), que a partir de la Iteracion 3 exigen
    `require_superadmin` y no cualquier Admin de comercio.
    """
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

    resp = client.post("/auth/login", json={
        "email": "super@test.com",
        "password": "super123",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.fixture
def superadmin_headers(superadmin_user):
    return {"Authorization": f"Bearer {superadmin_user['access_token']}"}


@pytest.fixture
def registered_user(client):
    resp = client.post("/auth/register", json={
        "email": "test@test.com",
        "password": "test123",
        "nombre": "Usuario Test",
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
def auth_token(client, registered_user):
    resp = client.post("/auth/login", json={
        "email": "test@test.com",
        "password": "test123",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}
