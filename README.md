<div align="center">

# 🐾 Servipet

**Sistema de gestión local para veterinarias y peluquerías caninas**

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat&logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-3-003B57?style=flat&logo=sqlite&logoColor=white)
![Tailwind](https://img.shields.io/badge/Tailwind_CSS-3-06B6D4?style=flat&logo=tailwindcss&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

</div>

---

## 📋 Descripción

**Servipet** es una aplicación web local diseñada para veterinarias, peluquerías caninas y comercios de mascotas. Permite gestionar clientes, mascotas, servicios y el historial de atenciones de forma rápida e intuitiva, con interfaz responsive optimizada para uso en celular y escritorio.

---

## ✨ Características principales

| Característica | Descripción |
|---|---|
| 🧑‍🤝‍🧑 **Gestión de Clientes** | Alta, baja lógica (soft delete), edición y ficha detallada |
| 🐕 **Gestión de Mascotas** | Registro con datos veterinarios, ficha individual con historial |
| 💇 **Gestión de Servicios** | Catálogo de servicios con precios base |
| 📋 **Registro de Atenciones** | Historial completo por mascota con monto, medio de pago y fotos |
| 📄 **Fichas Individuales** | Vista detallada de clientes y mascotas con estadísticas |
| 🗑️ **Soft Delete** | Eliminación lógica: los registros se desactivan, no se borran |
| 🔍 **Buscador en tiempo real** | Filtrado dinámico en todos los listados |
| 📱 **Mobile Friendly** | Diseño responsive con PWA instalable |
| 🎨 **UI con Tailwind CSS** | Interfaz moderna con badges, sombras y tipografía cuidada |

---

## 🛠️ Tecnologías utilizadas

- **Backend:** Python 3.10+, FastAPI, SQLAlchemy (ORM), Pydantic
- **Base de datos:** SQLite
- **Templates:** Jinja2
- **Estilos:** Tailwind CSS (via CDN)
- **Servidor:** Uvicorn

---

## 📦 Requisitos previos

- Python 3.10 o superior
- pip
- Git

---

## 🚀 Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/Sandramar-mdq/servipet.git
cd servipet
```

### 2. Crear entorno virtual

```bash
python -m venv .venv
```

Activar el entorno:

```bash
# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno (opcional)

```bash
copy .env.example .env
```

Por defecto usa SQLite local (`servipet.db`), no se requiere configuración adicional.

---

## ▶️ Ejecutar el servidor

### Opción 1: Directo por terminal

```bash
python -m uvicorn app.main:app --reload --port 8001
```

### Opción 2: Script batch (Windows)

Doble clic en `iniciar_servipet.bat` — inicia el servidor en el puerto **8001**.

### Acceso

Abrí tu navegador en:

```
http://localhost:8001
```

La API docs (Swagger) está disponible en:

```
http://localhost:8001/docs
```

---

## 📁 Estructura del proyecto

```
servipet/
├── app/
│   ├── models/             # Modelos SQLAlchemy (Cliente, Mascota, Servicio, etc.)
│   ├── schemas/            # Schemas Pydantic para validación
│   ├── routers/            # Rutas API + rutas de páginas (pages.py)
│   ├── templates/          # Templates Jinja2 (HTML)
│   │   ├── clientes/
│   │   ├── mascotas/
│   │   ├── servicios/
│   │   └── atenciones/
│   ├── static/             # Assets estáticos (SW, manifest, icons)
│   ├── config.py           # Configuración con pydantic-settings
│   ├── database.py         # Engine y sesión de SQLAlchemy
│   └── main.py             # Punto de entrada de FastAPI
├── iniciar_servipet.bat    # Script de inicio rápido (Windows)
├── requirements.txt        # Dependencias Python
├── .env.example            # Ejemplo de variables de entorno
└── README.md
```

---

## 📄 Licencia

Este proyecto es de uso interno / educativo.

---

<div align="center">

Hecho con ❤️ para el cuidado de mascotas

</div>
