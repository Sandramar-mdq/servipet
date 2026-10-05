# Informe Técnico Histórico de Arquitectura y Desarrollo: Proyecto Servipet v1.0

**Documento Ejecutivo de Ingeniería de Software y Trazabilidad Funcional**  
**Proyecto:** Servipet (Progressive Web App & Multi-Tenant Management Platform)  
**Fecha de Consolidación:** 5 de Octubre de 2026  
**Dirección de Desarrollo & Arquitectura:** Sandra L. Domínguez  
**Estado Final del Repositorio:** v1.0 (Completado, Desplegado, Auditado y Verificado — 481 Passed / 4 Xfailed / 0 Ruff Errors)

---

## 1. Resumen Ejecutivo de Arquitectura

**Servipet** nació y se consolidó como una solución SaaS de gestión integral para comercios del sector veterinario, peluquerías caninas, paseadores y guarderías de mascotas. Desarrollada bajo una arquitectura *monolítica modular cloud-native* orientada a entornos de alta disponibilidad, la plataforma combina la potencia de **FastAPI** en el backend con **PostgreSQL (Neon Cloud)** como motor de persistencia multitenant, un motor de plantillas **Jinja2** integrado con **Tailwind/Bootstrap**, capacidades **PWA (Progressive Web App)** con soporte offline, integración nativa de **Inteligencia Artificial Conversacional (Gemini API con Function Calling)** y un **Motor de Generación de Piezas Gráficas y Marketing B2B**.

El desarrollo se estructuró de manera rigurosa a lo largo de **13 etapas consecutivas de ingeniería**, alcanzando una cobertura de calidad mediante una suite de **485 pruebas de integración, unidad, seguridad RBAC y UI** (481 en verde y 4 xfail documentados), cumplimiento de estándares de accesibilidad **WCAG 2.1 Nivel AA**, cumplimiento de la **Ley 25.326 de Protección de Datos Personales (Argentina)**, pipeline automatizado de **CI/CD con GitHub Actions** y un esquema de despliegue continuo en la infraestructura cloud de **Render PaaS**.

---

## 2. Pila Tecnológica Consolidada (Tech Stack)

* **Lenguaje & Framework Core:** Python 3.11 / 3.12, FastAPI (Patrón *lifespan* `asynccontextmanager`), Uvicorn, Pydantic v2 / Pydantic-Settings (`@model_validator` Fail-Fast).
* **Persistencia & Multitenancy:** SQLAlchemy 2.0, PostgreSQL (Neon Cloud) y SQLite (desarrollo local), Alembic (migraciones de base de datos hasta la versión `0009_piezas_generadas`).
* **Seguridad & Autenticación:** OAuth2 con tokens JWT (módulo interno/staff), sesión basada en cookies/teléfono (Portal Cliente), hashing con `bcrypt`, matriz RBAC de 4 niveles (`SuperAdmin`, `Admin`, `Empleado`, `Cliente`) y verificación estricta de tenant (`_verificar_tenant`).
* **Frontend & Interfaz PWA:** Jinja2, HTML5 accesible, CSS Custom Properties (Skins dinámicos), JavaScript Vanilla asíncrono (IIFE/ServipetMarketing) y Service Workers (`servipet-v7`) para PWA.
* **Procesamiento de Imágenes & Documentos:** Pillow (diseño vectorial/raster de placas 1:1 y 9:16), fpdf2 (generación de carteles A4), ReportLab (reportes administrativos PDF) y OpenPyXL (exportación de planillas Excel).
* **Inteligencia Artificial:** SDK Oficial `google-genai` (Modelo `gemini-2.5-flash`) con arquitectura de *Function Calling / Tools* y fallbacks defensivos.
* **Notificaciones & Canales:** Arquitectura abstracta `NotificationProvider` para mensajería WhatsApp y enlaces de compartición directa.
* **Garantía de Calidad, Linters & CI/CD:** Pytest (485 tests totales: 481 verdes + 4 xfail), Linters (`ruff` 0 errores), scripts de smoke-test CLI (`verificar_rbac.py`), script de sembrado idempotente (`scripts/seed_alpha.py`), GitHub Actions y 2FA TOTP en plataforma.

---

## 3. Trazabilidad Histórica por Etapas de Desarrollo

### Etapa 1: Admin MVP (Núcleo Operativo Base)
* **Objetivo:** Definición de la entidad multitenant y modelos de gestión operativa primaria.
* **Hitos:** Creación de las tablas base para Clientes, Mascotas, Servicios y Atenciones. Implementación de controladores CRUD fundamentales, autenticación mediante JWT y aislamiento de datos por comercio.

### Etapa 2: Agenda, Programación y Gestión de Turnos
* **Objetivo:** Construcción del motor de reservas y gestión horaria.
* **Hitos:** Sistema de asignación de turnos con validación de superposición de horarios, lógica de slots disponibles y estados de atenciones en tiempo real.

### Etapa 3: Infraestructura Cloud, Persistencia Remota y PWA
* **Objetivo:** Preparación para producción y empaquetamiento PWA.
* **Hitos:** Despliegue inicial en **Render PaaS** vinculado a **PostgreSQL (Neon Cloud)** mediante SSL/HTTPS. Configuración de `manifest.json`, Service Workers para soporte offline y estrategia de caché estática.

### Etapa 4: Autenticación Dual, Multitenancy Estricto y Portal Cliente
* **Objetivo:** Segregación de accesos entre personal operativo y clientes finales.
* **Hitos:** Implementación del Portal Cliente con ingreso simplificado por número telefónico (`/cliente/login`). Aislamiento multi-tenant a nivel de consultas en SQLAlchemy impidiendo la filtración cruzada de datos entre comercios.

### Etapa 5: POS (Punto de Venta), Stock, Caja Diaria y Keep-Alive
* **Objetivo:** Módulo financiero y garantía de disponibilidad en la nube.
* **Hitos:** Integración de catálogo de productos (SKU, marca, proveedor, vencimiento), cobro mixto (servicios + productos), descuento de stock automatizado y arqueo de Caja Diaria. Creación del endpoint ultra-ligero `/api/v1/health` (~2 ms) vinculado a UptimeRobot para eliminar el *cold-start* del plan gratuito de Render.  
* **Cobertura de Pruebas:** 59/59 tests pasados.

### Etapa 6: Portal Público de Tracking (Seguimiento en Vivo)
* **Objetivo:** Visibilidad del estado del servicio para dueños de mascotas sin fricción de acceso.
* **Hitos:** Creación del endpoint público `GET /portal/seguimiento/{codigo_seguimiento}` indexado mediante hash/UUID único (evitando enumeración de IDs). Plantilla aislada `base_public.html` con estados de progreso del servicio (`ESPERA` → `BAÑO` → `CORTE` → `LISTO`) e integración directa a WhatsApp.  
* **Cobertura de Pruebas:** 64/64 tests pasados.

### Etapa 7: Comunidad Servipet (Red Social Opt-In Local)
* **Objetivo:** Módulo barrial y solidario para interacción entre usuarios.
* **Hitos:** Creación del feed comunitario (`/cliente/comunidad`) para publicar avisos de mascotas perdidas, adopciones, hallazgos y cumpleaños. Incorporación del parámetro `habilitar_red_comunitaria` mediante `PATCH /comercios/{id}/opt-in` para que cada negocio active o desactive la función. Panel de moderación administrativo.  
* **Cobertura de Pruebas:** 107/107 tests pasados.

### Etapa 8: Customización Visual, Skins y Accesibilidad WCAG 2.1 AA
* **Objetivo:** Personalización White-Label respetando normas internacionales de inclusión web.
* **Hitos:** 
  * Inyección de CSS Custom Properties (`--color-primario`, `--color-secundario`) mediante el `context_processor` `resolver_skin`.
  * Algoritmo matemático dinámico de luminancia sRGB (gamma 2.4) para selección de texto con ratio de contraste ≥ 4.5:1 (WCAG 2.1 AA).
  * Inclusión local de la fuente `OpenDyslexic.woff2` (100% offline PWA), selector de modos de alto contraste e iconografía obligatoria (`::before`) para daltonismo (WCAG 1.4.1).
  * Panel de administración `/admin/personalizacion` con vista previa en tiempo real (*Live Preview* en JS Vanilla).  
* **Cobertura de Pruebas:** 220/220 tests pasados.

### Etapa 9: Chatbot IA Conversacional (Gemini API & Function Calling)
* **Objetivo:** Asistente virtual inteligente contextualizado al comercio.
* **Hitos:** 
  * Servicio de IA (`app/services/ai_chat_service.py`) integrando el modelo `gemini-2.5-flash` con *System Prompts* dinámicos según el catálogo de la veterinaria/peluquería. Inyección automática del mensaje de bienvenida inicial.
  * *Function Calling / Tools* locales (`check_availability` y `get_appointment_status`) para consulta directa a PostgreSQL sin alucinaciones.
  * Inyección estricta del `comercio_id` desde el token/cookie autenticado (defensa contra manipulación multitenant) y fallbacks defensivos ante falta de clave API o errores HTTP 429.
  * Widget flotante en PWA accesible con compatibilidad `aria-live="polite"`.  
* **Cobertura de Pruebas:** 241/241 tests pasados.

### Etapa 10: Integraciones SaaS, Notificaciones, Reportes y CI/CD
* **Objetivo:** Cierre comercial, capacidad analítica y automatización DevOps.
* **Hitos:** 
  * Módulo de notificaciones vía `NotificationProvider` para envío automático de avisos de confirmación de turno y "Mascota Lista" por WhatsApp.
  * Generación de reportes administrativos en **PDF** (ReportLab) y planillas **Excel** (OpenPyXL) descargables desde `/admin/reportes`.
  * Pipeline de Integración Continua en `.github/workflows/ci.yml` ejecutando linters (`ruff`) y la batería de pruebas en entornos Python 3.11/3.12.
  * Habilitación de seguridad 2FA TOTP y resguardo total de credenciales.  
* **Cobertura de Pruebas:** 280/280 tests pasados.

### Etapa 11: Seguridad, Gobernanza y Marco Legal
* **Objetivo:** Consolidar el control de accesos por roles, la gobernanza del consentimiento legal y la documentación normativa de la versión Beta.
* **Hitos:** 
  * **Matriz RBAC de 4 niveles:** definición y validación estricta de accesos entre `SuperAdmin` (ADMIN global sin comercio), `Admin` del comercio, `Operador/Empleado` y `Cliente`.
  * **Marco legal Beta (`/legal/terminos-beta`):** plantilla *standalone* pública (`app/templates/legal/terminos_beta.html`) con los Términos del Servicio y Exención de Responsabilidad bajo la Ley 25.326.
  * **Consentimiento explícito (migración `0007_comercio_consentimiento_terminos`):** auditoría de consentimiento con fecha/hora UTC (`acepta_terminos_beta`, `terminos_aceptados_at`).  
* **Cobertura de Pruebas:** 313/313 tests pasados.

### Etapa 12: Módulo Solidario, Fidelización de Cumpleaños y Kit de Marketing B2B (Backend & PWA)
* **Objetivo:** Módulo de impacto comunitario y marketing multicanal de alto impacto visual reutilizando la información del sistema.
* **Hitos:**
  * **Backend & Motores de Renderizado Gráfico (`app/services/pieza_service.py`):** Cartel Solidario PDF (A4), Placa Digital Solidaria (9:16), Placa de Cumpleaños (1:1) y Kit B2B (1:1) con carga perezosa (*lazy import*) de `Pillow` y `fpdf2`.
  * **Persistencia & Idempotencia (Migración `0009_piezas_generadas`):** Restricción única compuesta `uq_pieza_generada_dedupe` con flag `forzar=1`.
  * **Interfaz de Usuario & PWA (`app/static/js/marketing_ui.js`):** Módulo IIFE global `window.ServipetMarketing`, widget de cumpleaños en Dashboard, kit B2B en `/page/marketing` y Service Worker actualizado a `servipet-v7`.
  * **Corrección de Bugs & Calidad:** Normalización ASCII en `Content-Disposition`, eliminación de clases hardcodeadas por variables CSS `var(--color-primario)` para accesibilidad WCAG 2.1 AA.  
* **Cobertura de Pruebas:** 443/443 tests pasados.

### Etapa 13: Despliegue en Producción, Hardening RBAC & Pruebas Alpha v1.0
* **Objetivo:** Blindaje de seguridad en endpoints, modernización de arquitectura FastAPI, sincronización remota de producción (Render + Neon) y suite de verificación Alpha.
* **Hitos:**
  * **Eliminación de Endpoints Inseguros:** Remoción total de `/crear-superadmin-temp` y del router completo `seed.py` para prevenir vulnerabilidades de elevación de privilegios en producción.
  * **Blindaje Multi-Tenant & RBAC (Ley 25.326):** Aplicación de `require_superadmin` en acciones globales, restricción estricta de `require_roles("ADMIN", "EMPLEADO")` con validación de tenant (`_verificar_tenant`) en `/comercios` y `/clientes`, y eliminación de la parametrización libre de `comercio_id` (forzando derivación directa desde el token JWT).
  * **Guarda Fail-Fast & Lifespan:** Decorador `@model_validator` en `app/config.py` que impide el arranque si `SECRET_KEY` conserva valores por defecto o `CORS_ORIGINS` está vacío. Migración del ciclo de vida de FastAPI a `lifespan` (`asynccontextmanager`).
  * **Sembrado Idempotente (`scripts/seed_alpha.py`):** Script CLI que lee credenciales exclusivamente desde variables de entorno (`ADMIN_EMAIL`, `ALPHA_ADMIN_EMAIL`, etc.), evita la duplicación de contraseñas con el patrón `_buscar_o_crear` y absorbe datasets de prueba tras el flag `SEED_ALPHA_DEMO=1`.
  * **Doble Matriz de Verificación & CI/CD:** Script `scripts/verificar_rbac.py` para smoke-tests en tiempo de despliegue y suite dedicada `tests/test_rbac_matrix.py`.  
* **Cobertura de Pruebas Final:** **485 tests totales (481 verdes + 4 xfail documentados para v1.1 — 0 errores en Ruff)**.

---

## 4. Matriz de Archivos Artefactos Principales del Sistema

```text
servipet/
├── .github/
│   └── workflows/
│       └── ci.yml                     # Pipeline de CI/CD GitHub Actions
├── alembic/
│   └── versions/                      # Migraciones de BD (0001 a 0009_piezas_generadas)
├── app/
│   ├── core/                          # Configuración, JWT, Hashing y Seguridad RBAC
│   ├── dependencies/                  # Guardas Auth, RBAC y Validación de Tenant (_verificar_tenant)
│   ├── models/                        # Entidades SQLAlchemy (Comercio, Turno, Producto, PiezaGenerada, etc.)
│   ├── schemas/                       # Validación de contratos Pydantic v2 y Config Fail-Fast
│   ├── services/                      # Lógica de Negocio, Piezas Gráficas (Pillow/fpdf2), AI Gemini y Notificaciones
│   ├── routers/                       # Controladores REST API (POS, Marketing, Chat, Reportes, Admin, Client)
│   ├── static/                        # Service Worker (v7), JS IIFE (marketing_ui.js), Fuentes OpenDyslexic, Skins
│   └── templates/                     # Vistas Jinja2 (Dashboard, Kit Marketing, Comunidad, Base, Legal)
├── scripts/
│   ├── seed_alpha.py                  # Sembrado idempotente de datos Alpha (sin credenciales hardcodeadas)
│   └── verificar_rbac.py              # CLI Smoke-Test de verificación RBAC en tiempo de deploy
├── tests/                             # Suite de 485 pruebas automáticas (Pytest / Backend, UI & Matriz RBAC)
├── render.yaml                        # Configuración de despliegue automatizado en Render PaaS
├── DEPLOYMENT.md                      # Manual técnico de despliegue en producción
├── iniciar_servipet.bat                # Script de arranque rápido local idempotente
└── requirements.txt                   # Insumos de dependencias fijadas de producción