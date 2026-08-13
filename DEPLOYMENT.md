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

| Variable | Descripción | Ejemplo |
|---|---|---|
| `DATABASE_URL` | Connection string de PostgreSQL o Turso (o SQLite local por defecto) | `postgresql://...` / `libsql://...` |
| `SECRET_KEY` | Clave para firmar tokens de sesión. Generá una con: `python -c "import secrets; print(secrets.token_hex(32))"` | `f4a1...` (64 hex) |
| `NOTIFICATION_PROVIDER` | `log` (mock, por defecto) o `twilio` | `log` |
| `TWILIO_ACCOUNT_SID` | SID de Twilio (solo si `NOTIFICATION_PROVIDER=twilio`) | `AC...` |
| `TWILIO_AUTH_TOKEN` | Token de Twilio | `...` |
| `TWILIO_FROM` | Remitente WhatsApp/SMS | `whatsapp:+14155238886` |
| `TURSO_AUTH_TOKEN` | Token de Turso (solo opción B) | `...` |
| `DEBUG` | Dejarlo en `false` en producción | `false` |

---

## 4. Despliegue

### Render
1. **New → Web Service**, conectá tu repo de GitHub.
2. Runtime: **Python**. En *Settings*:
   - **Build Command**: `pip install -r requirements.txt`
     (si usás Turso: `pip install -r requirements.txt -r requirements-turso.txt`)
   - **Start Command**: se toma del `Procfile` (`uvicorn app.main:app --host 0.0.0.0 --port $PORT`)
   - **Pre-Deploy Command** (crea las tablas; agrega `--seed` solo en el primer deploy):
     `python init_db.py` — o `python init_db.py --seed` la primera vez.
3. En **Environment**, cargá las variables de la tabla anterior (`DATABASE_URL`, `SECRET_KEY`, etc.).
4. **Deploy**. El archivo `render.yaml` incluido ya configura todo esto; si lo preferís,
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
   python init_db.py --seed
   ```
   (o que el Run Command inicial haga `python init_db.py --seed && uvicorn ...`).

> Nota: `app.main` ya ejecuta `Base.metadata.create_all` al arrancar, así que las tablas se
> crean solas aunque omitas el pre-deploy. El `init_db.py` es útil para el seed del primer deploy.

---

## 5. Verificación post-despliegue

- Apertura `https://tu-app/` → redirige al panel admin (`/page/`).
- `https://tu-app/cliente/login` → portal de clientes (los clientes semilla entran por OTP;
  el código se imprime en los logs del servidor).
- El Service Worker y el manifest PWA funcionan porque el hosting entrega HTTPS.

---

## 6. Volver a desarrollo local

Todo sigue funcionando sin cambios: sin `DATABASE_URL` el fallback es `sqlite:///./servipet.db`.
Si tenés `.env` con `DATABASE_URL`, borralo o dejalo con la URL SQLite.

```bash
python init_db.py --seed   # o: python seed.py
python -m uvicorn app.main:app --reload --port 8001
```
