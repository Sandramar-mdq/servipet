from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session


def _custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = FastAPI.openapi(self=app)
    schema.setdefault("components", {}).setdefault("securitySchemes", {})["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "Ingresa el access_token devuelto por /auth/login",
    }
    schema["security"] = [{"BearerAuth": []}]
    app.openapi_schema = schema
    return schema

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.routers import comercios, clientes, mascotas, servicios, atenciones
from app.routers import client, client_auth, client_booking, admin_turnos
from app.routers import auth, pages, portal
from app.routers import health, public_portal, seed, productos, ventas, caja, dashboard
from app.routers import comunidad
from app.routers import admin as admin_pages

from app.models import Comercio, Usuario, Cliente, ClienteOTP, Mascota, Servicio, AtencionHistorial, Turno  # noqa: F401


def init_db_seeding() -> None:
    """Inserta datos semilla idempotentes durante el arranque.

    - Verifica si existe Comercio con id=1; si no, lo crea con valores por defecto.
    - La sesión se cierra siempre en finally para no bloquear el startup.
    - Cualquier error de BD se traga para no impedir el arranque en Render.
    """
    db: Session = SessionLocal()
    try:
        from app.models.comercio import Comercio as ComercioModel  # import local evita circular
        exists = db.query(ComercioModel).filter(ComercioModel.id == 1).first()
        if not exists:
            seed = ComercioModel(
                id=1,
                nombre="Comercio Principal / Demo",
                tipo_comercio="MULTIRRUBRO",
                activo=True,
            )
            db.add(seed)
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)
app.openapi = _custom_openapi

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def method_override(request: Request, call_next):
    if request.method == "POST":
        body = await request.body()

        if b"_method" in body:
            from urllib.parse import parse_qs
            parsed = parse_qs(body.decode())
            method_values = parsed.get("_method", [])
            if method_values and method_values[0].upper() == "DELETE":
                scope = request.scope
                scope["method"] = "DELETE"
                filtered_pairs = [
                    (k, v[0]) for k, v in parsed.items() if k != "_method"
                ]
                filtered_body = "&".join(
                    f"{k}={v}" for k, v in filtered_pairs
                ).encode()

                async def _receive():
                    return {"type": "http.request", "body": filtered_body}

                scope["_receive"] = _receive
                return await call_next(request)

        async def _receive():
            return {"type": "http.request", "body": body}

        request.scope["_receive"] = _receive

    return await call_next(request)


app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(seed.router)
app.include_router(health.router)
app.include_router(public_portal.router)
app.include_router(comercios.router)
app.include_router(clientes.router)
app.include_router(mascotas.router)
app.include_router(servicios.router)
app.include_router(atenciones.router)
app.include_router(client.router)
app.include_router(client_auth.router)
app.include_router(client_booking.API_ROUTER)
app.include_router(client_booking.BOOKING_ROUTER)
app.include_router(admin_turnos.router)
app.include_router(auth.router)
app.include_router(portal.router)
app.include_router(pages.router)
app.include_router(productos.router)
app.include_router(ventas.router)
app.include_router(caja.router)
app.include_router(dashboard.router)
app.include_router(comunidad.router)
app.include_router(admin_pages.router)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    init_db_seeding()


@app.get("/")
def root():
    return RedirectResponse(url="/page/", status_code=302)
