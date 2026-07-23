from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, engine
from app.routers import comercios, clientes, mascotas, servicios, atenciones
from app.routers import pages

from app.models import Comercio, Cliente, Mascota, Servicio, AtencionHistorial  # noqa: F401


app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

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

app.include_router(comercios.router)
app.include_router(clientes.router)
app.include_router(mascotas.router)
app.include_router(servicios.router)
app.include_router(atenciones.router)
app.include_router(pages.router)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


@app.get("/")
def root():
    return RedirectResponse(url="/page/", status_code=302)
