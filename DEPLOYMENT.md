# Despliegue de Servipet (Render / Koyeb + PostgreSQL o Turso)

Guía breve para publicar Servipet en un hosting gratuito. Al terminar tendrás la app en
`https://<tu-app>.onrender.com` (o `*.koyeb.app`) conectada a una base de datos administrada.

---

## 1. Preparación del repositorio (GitHub)

1. Subí el proyecto a GitHub:
   ```bash
   git init
   git add .
   git commit -m "Servipet listo para despliegue"
   git branch -M main
   git remote add origin https://github.com/TU_USUARIO/servipet.git
   git push -u origin main
   ```
2. No subas secretos: `.env` está en `.gitignore`. Todos los secretos se configuran como
   variables de entorno en el hosting.

---

## 2. Base de datos (elegí una)

### Opción A — PostgreSQL (recomendada, gratuita)
- **Neon** o **Supabase**: creá un proyecto y copiá la *connection string* tipo
  `postgresql://usuario:password@host:5432/db` (o `postgres://...`, la app lo corrige sola).
- **Render PostgreSQL**: podés crearla desde el propio Render (plan free).

### Opción B — Turso (SQLite persistente)
- Instalá el CLI de Turso, creá la base y obtené `DATABASE_URL` (tipo `libsql://...`) y el token:
  ```bash
  turso auth login
  turso db create servipet
  turso db show --url servipet        # -> DATABASE_URL
  turso db tokens create servipet     # -> TURSO_AUTH_TOKEN
  ```
- **Importante:** el dialecto de Turso requiere el paquete `sqlalchemy-libsql`
  (experimental, solo Linux/macOS). En el build command del hosting usá:
  `pip install -r requirements.txt -r requirements-turso.txt`.

---

## 3. Variables de entorno

`Settings` (`app/config.py`) valida la configuración al arrancar: **si `DEBUG=false` y falta
`SECRET_KEY` o `CORS_ORIGINS`, la aplicación no levanta**. Es a propósito, para que un deploy no
pueda terminar firmando JWT con la clave de desarrollo que vive en el repo.

| Variable | Obligatoria | Descripción | Ejemplo |
|---|---|---|---|
| `DATABASE_URL` | sí | Connection string de PostgreSQL o Turso (o SQLite local por defecto) | `postgresql://...` / `libsql://...` |
| `DEBUG` | sí | `false` en producción. `true` habilita `allow_origins=["*"]` y salta las validaciones | `false` |
| `SECRET_KEY` | sí si `DEBUG=false` | Clave para firmar tokens de sesión. Generala con `python -c "import secrets; print(secrets.token_hex(32))"`. Rotarla invalida los tokens emitidos | `f4a1...` (64 hex) |
| `CORS_ORIGINS` | sí si `DEBUG=false` | Orígenes permitidos separados por coma. El front se sirve desde la misma app, así que alcanza el propio dominio | `https://tu-app.onrender.com` |
| `ADMIN_EMAIL` | no | Email del SuperAdmin inicial. Lo lee `scripts/seed_alpha.py`, no `Settings` | `admin@tuapp.com` |
| `ADMIN_PASSWORD` | no | Password del SuperAdmin inicial (mismo script, máx. 72 bytes) | `...` |
| `ALPHA_ADMIN_EMAIL` / `ALPHA_ADMIN_PASSWORD` | no | Admin del comercio base. Sin defaults: si falta, el seed aborta | `admin@huellas.com` |
| `ALPHA_EMPLEADO_EMAIL` / `ALPHA_EMPLEADO_PASSWORD` | no | Empleado (staff) del comercio base | `empleado@huellas.com` |
| `ALPHA_CLIENTE_EMAIL` / `ALPHA_CLIENTE_PASSWORD` | no | Cliente del comercio base (crea además su fila `Cliente`) | `cliente@ejemplo.com` |
| `SEED_ALPHA_DEMO` | no | `1` siembra además servicios, clientes, mascotas y turnos. Apagado por defecto para no meter agenda de prueba en producción | `1` |
| `NOTIFICATION_PROVIDER` | no | `log` (mock, por defecto) o `twilio` o `webhook` | `log` |
| `TWILIO_ACCOUNT_SID` | si `twilio` | SID de Twilio | `AC...` |
| `TWILIO_AUTH_TOKEN` | si `twilio` | Token de Twilio | `...` |
| `TWILIO_FROM` | si `twilio` | Remitente WhatsApp/SMS | `whatsapp:+1415523886` |
| `TURSO_AUTH_TOKEN` | solo Turso | Token de Turso | `...` |

`render.yaml` ya declara `DATABASE_URL`, `SECRET_KEY`, `ADMIN_*` y los tres pares `ALPHA_*` como
`sync: false`: hay que cargarlas a mano en el dashboard de Render antes del primer deploy.

### Datos iniciales

Después del primer deploy, corré el seed **una sola vez** desde una shell del hosting
(o desde tu máquina apuntando `DATABASE_URL` a la BD de producción):

```bash
python scripts/seed_alpha.py
```

Crea el comercio base "Peluqueria Canina Huellas" y los 4 niveles de la jerarquía RBAC
(SuperAdmin, Admin de Comercio, Empleado, Cliente). El quinto nivel —anónimo— no tiene
registro en la BD: es la ausencia de sesión.

El script es **idempotente**: se puede correr en cada redeploy sin duplicar filas ni pisar
`password_hash`. Aborta con `SystemExit` si falta alguna de las 8 variables de credenciales,
si dos niveles comparten email, o si un password supera los 72 bytes de bcrypt.

### Verificación RBAC

```bash
BASE_URL=https://tu-app.onrender.com python scripts/verificar_rbac.py
```

Login automático con las mismas variables del seed, recorre la matriz de endpoints y sale
con código 1 si algún nivel recibe un código HTTP distinto al esperado. Lista aparte los
endpoints que siguen sin guard (`/mascotas/`, `/atenciones/`, `/page/turnos`,
`/page/reportes`): están documentados como faltantes, no cuentan como fallo.

---

## 4. Despliegue

### Render
1. **New → Web Service**, conectá tu repo de GitHub.
2. Runtime: **Python**. En *Settings*:
   - **Build Command**: `python -m pip install --upgrade pip && pip install -r requirements.txt`
     (si usás Turso: agregá `-r requirements-turso.txt`).
   - **Start Command**: se toma del `Procfile` (`uvicorn app.main:app --host 0.0.0.0 --port $PORT`)
   - **Pre-Deploy Command**: `python init_db.py && python -m alembic upgrade head`
3. En **Environment**, cargá `DATABASE_URL`, `SECRET_KEY`, `CORS_ORIGINS`, `ADMIN_EMAIL` y
   `ADMIN_PASSWORD` (tabla de la sección 3). Sin `SECRET_KEY` y `CORS_ORIGINS` el deploy falla
   al arrancar, a propósito.
4. **Deploy**. El archivo `render.yaml` incluido ya configura esto; si lo preferís,
   usalo con **New → Blueprint**.

### Koyeb
1. **Create App** → conectá el repo (o usá Git).
2. Build: **Buildpack**, Run Command:
   ```
   uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```
3. Agregá las variables de entorno de la tabla anterior.
4. Antes del primer deploy, ejecutá un one-off:
   ```
   python init_db.py && python -m alembic upgrade head
   ```

> **Por qué `init_db.py` va antes que Alembic**: las migraciones son incrementales. Las cuatro
> que crean tablas (`0001`, `0004`, `0005`, `0009`) tienen claves foráneas a `comercios`,
> `clientes`, `usuarios` y `turnos`, y ninguna migración crea esas tablas base: eso lo hace
> `Base.metadata.create_all`. Sin `init_db.py` primero, `alembic upgrade head` falla en la
> revisión `0001` sobre una base vacía.

---

## 5. Verificación post-despliegue

- `https://tu-app/api/v1/health` → `{"status":"ok","app":"Servipet"}`. Es el `healthCheckPath`
  de `render.yaml`: devuelve un dict literal, sin I/O ni acceso a la BD.
- Apertura `https://tu-app/` → redirige al panel admin (`/page/`).
- `https://tu-app/cliente/login` → portal de clientes (entran por OTP; el código se imprime
  en los logs del servidor). El `Usuario` con rol `CLIENTE` del seed usa `/portal/`, que
  va por JWT: `/login` (formulario staff) rechaza `CLIENTE` con 401 a propósito.
- El Service Worker y el manifest PWA funcionan porque el hosting entrega HTTPS.
- Matriz RBAC de los 4 niveles y aislamiento multi-tenant:
  ```
  BASE_URL=https://tu-app.onrender.com python scripts/verificar_rbac.py
  ```
- Para confirmar que Alembic quedó alineado con los modelos:
  ```
  python -m alembic current   # 0009_piezas_generadas (head)
  python -m alembic check     # No new upgrade operations detected
  ```

### Endpoints pendientes de cerrar

`verificar_rbac.py` y `tests/test_rbac_matrix.py` marcan estos cuatro como diferidos:
el anónimo todavía los alcanza y el dato es de tenant.

| Endpoint | Router | Problema |
|---|---|---|
| `GET /mascotas/` | `app/routers/mascotas.py` | sin guard |
| `GET /atenciones/` | `app/routers/atenciones.py` | sin guard |
| `GET /page/turnos` | `app/routers/admin_turnos.py` | sin guard ni filtro por `Turno` |
| `GET /page/reportes` | `app/routers/reports.py:149` | sin guard y con `comercio_id = 1` fijo |

Cuando se les agregue el guard, hay que sacar el `xfail` correspondiente de
`tests/test_rbac_matrix.py` (pasará a XPASS mientras siga el `strict=False`).

---

## 6. Volver a desarrollo local

Todo sigue funcionando sin cambios: sin `DATABASE_URL` el fallback es `sqlite:///./servipet.db`.
Si tenés `.env` con `DATABASE_URL`, borralo o dejalo con la URL SQLite.

```bash
python init_db.py --seed   # datos de arranque generales
python scripts/seed_alpha.py   # comercio base + jerarquia RBAC de 4 niveles
python -m uvicorn app.main:app --reload --port 8001
```

`scripts/seed_alpha.py` es el único seed de RBAC. Necesita las 8 variables
`ADMIN_*` / `ALPHA_ADMIN_*` / `ALPHA_EMPLEADO_*` / `ALPHA_CLIENTE_*` en el entorno
(o en `.env`); sin ellas aborta sin tocar la base.
