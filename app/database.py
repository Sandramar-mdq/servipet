from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


def _normalizar_url(url: str) -> str:
    """Ajusta prefijos de URL segun el proveedor de hosting/BD.

    - Render / Neon / Supabase pueden inyectar `postgres://` (valido para
      Django) pero SQLAlchemy requiere `postgresql://`.
    - Turso expone `libsql://` y se traduce al dialecto `sqlite+libsql`.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url


def _url_turso(url: str) -> str:
    # libsql://host -> sqlite+libsql://host?secure=true
    if "?" not in url:
        url = f"{url}?secure=true"
    else:
        url = f"{url}&secure=true"
    return f"sqlite+{url}"


connect_args = {}
database_url = _normalizar_url(settings.DATABASE_URL)

if database_url.startswith("libsql://"):
    database_url = _url_turso(database_url)
    if settings.TURSO_AUTH_TOKEN:
        connect_args["auth_token"] = settings.TURSO_AUTH_TOKEN
elif database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
