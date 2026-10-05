# AGENTS.md

## Project

- **servipet** — FastAPI + SQLAlchemy 2.0 (`Mapped`/`mapped_column`) + Alembic + Jinja2 (portales HTML) + Pydantic-settings.
- BDs soportadas: SQLite (dev/test), Postgres y Turso (libsql). `app/database.py` normaliza la URL.
- Etapas 1-12 completadas (auth JWT, multitenancy, turnos, caja, dashboard, comunidad, skins/a11y, chat IA, notificaciones, reportes, marketing B2B). Iteracion 3 completada (seed Alpha RBAC, guards criticos de aislamiento tenant, matriz RBAC).

## Setup

- Dependencias en `requirements.txt` (sin pin exacto). Instalar con `python -m pip install -r requirements.txt`.
- No hay `pyproject.toml` ni linter configurado; `.gitignore` sugiere Ruff como intención.
- Tests: `python -m pytest tests` (suite actual: 485 tests = 443 previos + 42 de `tests/test_rbac_matrix.py`, ~6.5 min; 4 aparecen como `xfail`, son endpoints diferidos a proposito). `tests/conftest.py` usa SQLite en memoria (StaticPool) y sobreescribe `get_db`. Fixtures compartidos: `admin_headers`, `superadmin_headers` (rol ADMIN con `comercio_id=None`), `registered_user`, `auth_headers`.
- Migraciones: `alembic upgrade head` (script_location = `migrations/`). El startup también ejecuta `Base.metadata.create_all`, por eso las migraciones son defensivas (`_existe_tabla`).
- `alembic check` debe reportar "No new upgrade operations detected": las migraciones están escritas a mano y tienen que coincidir con los modelos.

## Conventions

- Modelos con SQLAlchemy 2.0 `Mapped`/`mapped_column`, `datetime.now` para defaults en la mayoría; registrarlos en `app/models/__init__.py`.
- Endpoints REST bajo `/api/v1` para `/health`, `/chat`, `/comunidad` y `/marketing`; el resto de los recursos cuelga de prefijos sin version (`/ventas`, `/caja`, `/reportes`, `/productos`, `/comercios`, `/clientes`, `/page`, `/admin`). Páginas admin bajo `/page`, portales cliente bajo `/portal`, `/cliente`. Templates Jinja2 vía `app/core/templating.py::get_templates()`.
- Guards de auth (Iteracion 3): todo reusable vive en `app/dependencies/auth.py` — `get_current_user`, `require_roles(*roles)`, `require_superadmin` (rol ADMIN **y** `comercio_id is None`) y `verificar_tenant(user, comercio_id)` (403 si `user.comercio_id` no es None y difiere del recurso; el SuperAdmin pasa siempre). No reimplementar esas condiciones inline en un router.
- Aislamiento tenant: el `comercio_id` efectivo sale **siempre** del token, nunca del body ni de un query param libre. `/comercios/` y `/comercios/{id}`(DELETE) son de plataforma (`require_superadmin`); `/clientes/` acepta `comercio_id` por query solo para el SuperAdmin y responde 400 si lo omite.
- Seed (Iteracion 3): `scripts/seed_alpha.py` es el unico seed. Reemplaza a `seed_demo.py` y `create_superadmin.py`. Credenciales **solo** por `os.environ` (`ADMIN_*`, `ALPHA_ADMIN_*`, `ALPHA_EMPLEADO_*`, `ALPHA_CLIENTE_*`), sin defaults ni prompt: si falta una, `SystemExit` antes de tocar la BD. Idempotente via `_buscar_o_crear` (clave natural `email` en `Usuario`), que **nunca** actualiza una fila existente, asi que un redeploy no pisa `password_hash`. Maximo 72 bytes por password (limite de bcrypt 5).
- El rol CLIENTE necesita **dos** filas: `Usuario(rol="CLIENTE")` y un `Cliente` vinculado por `usuario_id`. `Usuario` no tiene columna de nombre (el nombre vive en `Cliente.nombre`) y `portal._require_cliente` responde **404** sin `cliente_profile`.
- Matriz RBAC (Iteracion 3): `tests/test_rbac_matrix.py` (suite, con `xfail` para los endpoints diferidos) y `scripts/verificar_rbac.py` (smoke HTTP contra el deploy, sale con codigo 1). Al agregar un endpoint a `/comercios`, `/clientes` o cualquier router con datos de tenant, agregar su fila a `MATRIZ`.
- Endpoints diferidos, sin guard y con el anonimo entrando (documentados a proposito, `xfail` en la suite): `/mascotas/`, `/atenciones/`, `/page/turnos`, `/page/reportes` (ademas con `comercio_id=1` fijo en `reports.py:159`). Cerrarlos es trabajo pendiente; no contarlos como cubiertos.
- Reportes PDF/Excel: `app/routers/reports.py::/page/reportes` esta **sin guard** y con `comercio_id = 1` hardcodeado. `app/routers/client.py::/cliente/comunidad` idem. Si se tocan, resolver el tenant desde `current_user`.
- Servicios de lógica de negocio en `app/services/*`.
- Notificaciones (módulo 10.1): ir por `app/services/notification_service.py` (registra `NotificationLog` y soporta provider `log`/`twilio`/`webhook`). `app/services/notifier.py` conserva su API pública delegando al servicio.
- Reportes (módulo 10.2): `app/services/report_service.py` (datos planos + renderers PDF con fpdf2 y Excel con openpyxl). Endpoints de descarga en `app/routers/reports.py` bajo `/reportes` (solo ADMIN); vista previa en `/page/reportes`. fpdf2 y openpyxl son dependencias requeridas por la importación del router en `main.py`.
- Marketing B2B (etapa 12): renderer de piezas en `app/services/pieza_service.py` (imports de `fpdf`/`Pillow` **dentro** de las funciones, nunca a nivel de módulo) y armado de datos/auditoría en `app/services/marketing_service.py`. Endpoints en `app/routers/marketing.py` bajo `/api/v1/marketing`. Schema en `app/schemas/solidaridad.py`. Descarga binaria compartida en `app/core/downloads.py`.
- UI de Marketing (etapa 12): todo el front es JS vanilla en IIFE bajo `window.ServipetMarketing` (`app/static/js/marketing_ui.js`). Las páginas de negocio van en `app/routers/marketing_pages.py` (`/page/marketing`, staff `ADMIN`/`EMPLEADO`); Solidario se integra en `/admin/comunidad` porque la API opera sobre `aviso_id`, no sobre mascota.
- Marketing nunca hardcodea color: todo CSS de estos módulos usa `var(--color-primario)` / `var(--texto-sobre-primario)`. Un `bg-indigo-600` en `/page/` rompe `tests/test_a11y.py`.
- Fechas de negocio: caja, ventas y movimientos usan `datetime.now` (hora local) a propósito, porque los reportes de "caja diaria" filtran con `date.today()`. No volver a `datetime.utcnow` en `app/models/caja.py`, `app/models/venta.py`, `app/models/caja_movimiento.py` ni `app/services/caja.py`, o los reportes se rompen entre las 21:00 y las 24:00 de Argentina.
- PDF: las fuentes core de fpdf2 codifican en `latin-1` (no cp1252). Todo texto de usuario al PDF pasa por `pieza_service._pdf_seguro`, que traduce em dash, comillas curvas, euro, etc. y descarta lo que quede fuera de rango. Los PNG no tienen ese límite.
- Slugs de `Content-Disposition`: deben ser ASCII. `marketing_service.nombre_archivo_promocion` descompone Unicode y quita diacriticos; las cabeceras HTTP son latin-1 y un "ñ" rompe la respuesta.
- Anti-duplicado: `piezas_generadas` tiene `uq_pieza_generada_dedupe` sobre (comercio_id, tipo, referencia_tipo, referencia_id, formato, anio). `marketing_service.registrar_pieza` es un **upsert**, nunca un insert a secas; los endpoints devuelven 409 con `ya_registrado(...)` y aceptan `forzar=1` para regenerar.
- Texto plano, sin emojis salvo pedido explícito. Docstrings y comentarios en español, sin acentos en código (coherente con el repo).
- Jinja: un `{% set %}` dentro de `{% block content %}` **no** es visible en `{% block scripts %}` de la misma plantilla. Repetir la condición en cada bloque en vez de confiar en el `set`.
- Tests nuevos: mockear llamadas externas (ej. `monkeypatch` sobre `httpx.post` o `_http_post`) y apuntar `app.database.SessionLocal` a `TestingSessionLocal`.
- Tests de UI: no poner datos dinámicos en atributos globales de `base.html` (ej. `data-comercio-nombre` en `<body>`). `tests/test_admin_comercios.py` hace `split()` sobre el nombre de un comercio y el markup extra rompe el parsing. Los `data-*` van en el div del componente.