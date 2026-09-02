# AGENTS.md

## Project

- **servipet** — FastAPI + SQLAlchemy 2.0 (`Mapped`/`mapped_column`) + Alembic + Jinja2 (portales HTML) + Pydantic-settings.
- BDs soportadas: SQLite (dev/test), Postgres y Turso (libsql). `app/database.py` normaliza la URL.
- Etapas 1-10 completadas (auth JWT, multitenancy, turnos, caja, dashboard, comunidad, skins/a11y, chat IA, notificaciones).

## Setup

- Dependencias en `requirements.txt` (sin pin exacto). Instalar con `python -m pip install -r requirements.txt`.
- No hay `pyproject.toml` ni linter configurado; `.gitignore` sugiere Ruff como intención.
- Tests: `python -m pytest tests` (suite actual: 280 tests, ~3 min). `tests/conftest.py` usa SQLite en memoria (StaticPool) y sobreescribe `get_db`.
- Migraciones: `alembic upgrade head` (script_location = `migrations/`). El startup también ejecuta `Base.metadata.create_all`, por eso las migraciones son defensivas (`_existe_tabla`).

## Conventions

- Modelos con SQLAlchemy 2.0 `Mapped`/`mapped_column`, `datetime.utcnow` para defaults en la mayoría; registrarlos en `app/models/__init__.py`.
- Endpoints REST bajo `/api/v1`, páginas admin bajo `/page`, portales cliente bajo `/portal`, `/cliente`. Templates Jinja2 vía `app/core/templating.py::get_templates()`.
- Servicios de lógica de negocio en `app/services/*`.
- Notificaciones (módulo 10.1): ir por `app/services/notification_service.py` (registra `NotificationLog` y soporta provider `log`/`twilio`/`webhook`). `app/services/notifier.py` conserva su API pública delegando al servicio.
- Reportes (módulo 10.2): `app/services/report_service.py` (datos planos + renderers PDF con fpdf2 y Excel con openpyxl). Endpoints de descarga en `app/routers/reports.py` bajo `/reportes` (solo ADMIN); vista previa en `/page/reportes`. fpdf2 y openpyxl son dependencias requeridas por la importación del router en `main.py`.
- Texto plano, sin emojis salvo pedido explícito. Docstrings y comentarios en español, sin acentos en código (coherente con el repo).
- Tests nuevos: mockear llamadas externas (ej. `monkeypatch` sobre `httpx.post` o `_http_post`) y apuntar `app.database.SessionLocal` a `TestingSessionLocal`.