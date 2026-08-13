import hmac

from app.config import settings


def _firma(payload: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), payload.encode(), "sha256").hexdigest()


def crear_token(cliente_id: int) -> str:
    payload = str(cliente_id)
    return f"{payload}.{_firma(payload)}"


def verificar_token(token: str) -> int | None:
    if not token or "." not in token:
        return None
    payload, firma = token.rsplit(".", 1)
    if not payload.isdigit():
        return None
    if not hmac.compare_digest(firma, _firma(payload)):
        return None
    return int(payload)
