"""Fábrica compartida de Jinja2Templates para Servipet.

Todos los routers deben obtener su instancia via get_templates() para que
el objeto `comercio` (con su skin: tema_preset, colores HEX y accesibilidad)
esté disponible en cualquier template, alimentando las Custom Properties
CSS definidas en base.html / base_public.html.
"""

from types import SimpleNamespace

from fastapi.templating import Jinja2Templates

COMERCIO_DEFAULT_ID = 1


def _comercio_skin_context(request):  # noqa: ARG001 (firma requerida por Starlette)
    """Context processor: inyecta `comercio` y `skin` en todo template.

    Resuelve el comercio del tenant a partir del JWT de la sesion (cookie o
    Bearer); si no hay token o no trae `comercio_id` (p.ej. anonimo o
    SuperAdmin), cae al comercio principal (id=1). Ante cualquier error de BD o
    comercio inexistente, entrega un fallback con los valores del preset por
    defecto (clasico_paws), de modo que los templates nunca rompan.

    Precedencia: Starlette aplica los context processors al final, por lo que
    este valor pisa un `comercio` pasado explícitamente por un endpoint.
    """
    from app.core.skins_config import A11Y_MODO_DEFAULT, resolver_skin
    from app.database import SessionLocal
    from app.models.comercio import Comercio

    payload = _payload_del_token(request)
    comercio_id = COMERCIO_DEFAULT_ID
    if payload and isinstance(payload.get("comercio_id"), int):
        comercio_id = payload["comercio_id"]

    comercio = None
    try:
        db = SessionLocal()
        try:
            comercio = db.query(Comercio).filter(Comercio.id == comercio_id).first()
        finally:
            db.close()
    except Exception:
        comercio = None

    skin = resolver_skin(comercio)

    if comercio is None:
        comercio = SimpleNamespace(
            id=comercio_id,
            nombre="Servipet",
            telefono=None,
            logo_webp=None,
            habilitar_red_comunitaria=False,
            habilitar_modulo_solidario=False,
            habilitar_cumpleanos=False,
            beneficio_cumpleanos=None,
            tema_preset=skin["tema_preset"],
            color_primario=skin["color_primario"],
            color_secundario=skin["color_secundario"],
            a11y_modo=A11Y_MODO_DEFAULT,
            a11y_dyslexic=False,
        )

    contexto = {"comercio": comercio, "skin": skin}
    contexto.update(_flags_auth_context(request))
    return contexto


def _payload_del_token(request) -> dict | None:
    """Decodifica el JWT del request (Bearer o cookie) o `None` si no hay."""
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    if not token:
        token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        from app.services.auth import decode_access_token
    except Exception:  # pragma: no cover - import defensivo
        return None
    try:
        return decode_access_token(token)
    except Exception:
        return None


def _flags_auth_context(request) -> dict:
    """Inyecta flags de sesion desde el JWT (cookie o Bearer) sin tocar BD.

    - es_superadmin: rol ADMIN con comercio_id None.
    - es_impersonacion / impersonacion_nombre: claim del token impersonado.
    - usuario: SimpleNamespace con la propiedad `rol` del token (None si no hay sesion).
    """
    payload = _payload_del_token(request)
    if payload is None:
        return _flags_vacios()

    es_superadmin = (
        payload.get("rol") == "ADMIN" and payload.get("comercio_id") is None
    )
    es_impersonacion = payload.get("impersonando") is True
    impersonacion_nombre = payload.get("comercio_nombre")
    usuario = None
    if payload.get("rol"):
        usuario = SimpleNamespace(rol=payload.get("rol"))

    return {
        "es_superadmin": es_superadmin,
        "es_impersonacion": es_impersonacion,
        "impersonacion_nombre": impersonacion_nombre,
        "usuario": usuario,
    }


def _flags_vacios() -> dict:
    return {
        "es_superadmin": False,
        "es_impersonacion": False,
        "impersonacion_nombre": None,
        "usuario": None,
    }


def get_templates() -> Jinja2Templates:
    """Instancia de Jinja2Templates con contexto global de skin."""
    return Jinja2Templates(
        directory="app/templates",
        context_processors=[_comercio_skin_context],
    )
