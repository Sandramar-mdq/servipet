# Informe Técnico Histórico de Arquitectura y Desarrollo: Proyecto Servipet v1.0

**Documento Ejecutivo de Ingeniería de Software y Trazabilidad Funcional**  
**Proyecto:** Servipet (Progressive Web App & Multi-Tenant Management Platform)  
**Fecha de Consolidación:** 2 de Septiembre de 2026  
**Dirección de Desarrollo & Arquitectura:** Sandra L. Domínguez  
**Estado Final del Repositorio:** v1.0 (Completado y Verificado — 280/280 Tests Aprobados en Verde)

---

## 1. Resumen Ejecutivo de Arquitectura

**Servipet** nació y se consolidó como una solución SaaS de gestión integral para comercios del sector veterinario, peluquerías caninas, paseadores y guarderías de mascotas. Desarrollada bajo una arquitectura *monolítica modular cloud-native* orientada a entornos de alta disponibilidad, la plataforma combina la potencia de **FastAPI** en el backend con **PostgreSQL (Neon)** como motor de persistencia multitenant, un motor de plantillas **Jinja2** integrado con **Tailwind/Bootstrap**, capacidades **PWA (Progressive Web App)** con soporte offline y la integración nativa de **Inteligencia Artificial Conversacional (Gemini API con Function Calling)**.

El desarrollo se estructuró de manera rigurosa a lo largo de **10 etapas consecutivas de ingeniería**, alcanzando una cobertura de calidad del 100% mediante una suite de **280 pruebas de integración y unidad**, cumplimiento de estándares de accesibilidad **WCAG 2.1 Nivel AA**, pipeline automatizado de **CI/CD con GitHub Actions** y un esquema de despliegue continuo en la infraestructura cloud de **Render**.

---

## 2. Pila Tecnológica Consolidada (Tech Stack)

* **Lenguaje & Framework Core:** Python 3.11 / 3.12, FastAPI, Uvicorn, Pydantic v2.
* **Persistencia & Multitenancy:** SQLAlchemy 2.0, PostgreSQL (Neon Cloud) y SQLite (desarrollo local), Alembic (migraciones de base de datos).
* **Seguridad & Autenticación:** OAuth2 con tokens JWT (módulo interno/staff), sesión basada en cookies/teléfono (Portal Cliente) y hashing con `bcrypt`.
* **Frontend & Interfaz:** Jinja2, HTML5 accesible, CSS Custom Properties (Skins dinámicos), JavaScript Vanilla asíncrono y Serviceworkers para PWA.
* **Inteligencia Artificial:** SDK Oficial `google-genai` (Modelo `gemini-2.5-flash`) con arquitectura de *Function Calling / Tools* y fallbacks defensivos.
* **Documentos & Notificaciones:** ReportLab (generación de PDF), OpenPyXL (exportación de planillas Excel) y arquitectura abstracta `NotificationProvider` para mensajería WhatsApp.
* **Garantía de Calidad & CI/CD:** Pytest (280 tests integrales), Linters (`ruff`), GitHub Actions (`.github/workflows/ci.yml`) y 2FA TOTP en plataforma.

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
* **Hitos:** Despliegue inicial en **Render PaaS** vinculado a **PostgreSQL (Neon Cloud)** mediante SSL/HTTPS. Configuración de `manifest.json`, Service Workers (`sw.js`) para soporte offline y estrategia de caché estática.

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
* **Cobertura de Pruebas:** 107/107 tests pasados (versión `v0.7.0`).

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
  * Servicio de IA (`app/services/ai_chat_service.py`) integrando el modelo `gemini-2.5-flash` con *System Prompts* dinámicos según el catálogo de la veterinaria/peluquería.
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
* **Cobertura de Pruebas Final:** **280/280 tests pasados (100% verde)**.

---

## 4. Matriz de Archivos Artefactos Principales del Sistema

```text
servipet/
├── .github/
│   └── workflows/
│       └── ci.yml                     # Pipeline de CI/CD GitHub Actions
├── alembic/
│   └── versions/                      # Historial de migraciones idénticas de BD
├── app/
│   ├── core/                          # Configuración, JWT, Hashing y Seguridad
│   ├── models/                        # Entidades SQLAlchemy (Comercio, Turno, Producto, Chat, etc.)
│   ├── schemas/                       # Validación de contratos Pydantic v2
│   ├── services/                      # Lógica de Negocio, Reportes, IA Gemini y Notificaciones
│   ├── routers/                       # Controladores REST API (POS, Chat, Reportes, Admin, Client)
│   ├── static/                        # Recursos PWA, Fuentes OpenDyslexic, JS Vanilla, CSS Skins
│   └── templates/                     # Vistas Jinja2 (Base, Public, Client, Admin, Components)
├── tests/                             # Suite de 280 pruebas automáticas (Pytest)
├── iniciar_servipet.bat                # Script de arranque rápido idempotente
└── requirements.txt                   # Insumos de dependencias de producción

---

## 5. Dictamen Técnico Final

El proyecto **Servipet v1.0** se encuentra **técnicamente completado, auditado y listo para explotación comercial o presentación corporativa**. Posee una base de código robusta, mantenible, testeada de extremo a extremo y adaptada a las máximas exigencias del mercado SaaS actual.