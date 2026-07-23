from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.cliente import Cliente
from app.models.mascota import Mascota
from app.models.servicio import Servicio
from app.models.atencion import AtencionHistorial

router = APIRouter(prefix="/page", tags=["Pages"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    stats = {
        "clientes": db.query(Cliente).count(),
        "mascotas": db.query(Mascota).count(),
        "servicios": db.query(Servicio).count(),
        "atenciones": db.query(AtencionHistorial).count(),
    }
    return templates.TemplateResponse("home.html", {"request": request, "stats": stats})


# ── Clientes ──────────────────────────────────────────────

@router.get("/clientes", response_class=HTMLResponse)
def page_clientes(request: Request, db: Session = Depends(get_db)):
    clientes = db.query(Cliente).all()
    return templates.TemplateResponse("clientes/listar.html", {"request": request, "clientes": clientes})


@router.get("/clientes/nuevo", response_class=HTMLResponse)
def page_cliente_nuevo(request: Request):
    return templates.TemplateResponse("clientes/form.html", {"request": request, "cliente": None})


@router.get("/clientes/{cliente_id}/editar", response_class=HTMLResponse)
def page_cliente_editar(cliente_id: int, request: Request, db: Session = Depends(get_db)):
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    return templates.TemplateResponse("clientes/form.html", {"request": request, "cliente": cliente})


@router.post("/clientes/nuevo")
def crear_cliente_form(
    nombre: str = Form(...),
    telefono: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    notas: Optional[str] = Form(None),
    foto_webp: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    cliente = Cliente(
        nombre=nombre, comercio_id=1,
        telefono=telefono, email=email,
        notas=notas, foto_webp=foto_webp,
    )
    db.add(cliente)
    db.commit()
    return RedirectResponse("/page/clientes", status_code=303)


@router.post("/clientes/{cliente_id}/editar")
def actualizar_cliente_form(
    cliente_id: int,
    nombre: str = Form(...),
    telefono: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    notas: Optional[str] = Form(None),
    foto_webp: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if cliente:
        cliente.nombre = nombre
        cliente.telefono = telefono
        cliente.email = email
        cliente.notas = notas
        cliente.foto_webp = foto_webp
        db.commit()
    return RedirectResponse("/page/clientes", status_code=303)


# ── Mascotas ──────────────────────────────────────────────

@router.get("/mascotas", response_class=HTMLResponse)
def page_mascotas(request: Request, db: Session = Depends(get_db)):
    mascotas_raw = db.query(Mascota).all()
    mascotas = []
    for m in mascotas_raw:
        cliente = db.query(Cliente).filter(Cliente.id == m.cliente_id).first()
        mascotas.append({
            "id": m.id, "nombre": m.nombre, "raza": m.raza,
            "sexo": m.sexo, "cliente_id": m.cliente_id,
            "cliente_nombre": cliente.nombre if cliente else "—",
        })
    return templates.TemplateResponse("mascotas/listar.html", {"request": request, "mascotas": mascotas})


@router.get("/mascotas/nuevo", response_class=HTMLResponse)
def page_mascota_nuevo(request: Request, db: Session = Depends(get_db)):
    clientes = db.query(Cliente).all()
    return templates.TemplateResponse("mascotas/form.html", {"request": request, "mascota": None, "clientes": clientes})


@router.get("/mascotas/{mascota_id}", response_class=HTMLResponse)
def page_mascota_detalle(mascota_id: int, request: Request, db: Session = Depends(get_db)):
    mascota = db.query(Mascota).filter(Mascota.id == mascota_id).first()
    if not mascota:
        return RedirectResponse("/page/mascotas", status_code=303)
    cliente = db.query(Cliente).filter(Cliente.id == mascota.cliente_id).first()
    atenciones_raw = (
        db.query(AtencionHistorial)
        .filter(AtencionHistorial.mascota_id == mascota_id)
        .order_by(AtencionHistorial.fecha.desc())
        .all()
    )
    atenciones = []
    for a in atenciones_raw:
        servicio = db.query(Servicio).filter(Servicio.id == a.servicio_id).first()
        atenciones.append({
            "id": a.id,
            "fecha": a.fecha.strftime("%d/%m/%Y %H:%M") if a.fecha else "—",
            "servicio_nombre": servicio.nombre if servicio else "—",
            "monto_cobrado": a.monto_cobrado,
            "medio_pago": a.medio_pago,
            "observaciones": a.observaciones,
        })
    return templates.TemplateResponse("mascotas/detalle.html", {
        "request": request,
        "mascota": mascota,
        "cliente": cliente,
        "atenciones": atenciones,
    })


@router.get("/mascotas/{mascota_id}/editar", response_class=HTMLResponse)
def page_mascota_editar(mascota_id: int, request: Request, db: Session = Depends(get_db)):
    mascota = db.query(Mascota).filter(Mascota.id == mascota_id).first()
    clientes = db.query(Cliente).all()
    return templates.TemplateResponse("mascotas/form.html", {"request": request, "mascota": mascota, "clientes": clientes})


@router.post("/mascotas/nuevo")
def crear_mascota_form(
    cliente_id: int = Form(...),
    nombre: str = Form(...),
    raza: Optional[str] = Form(None),
    peso: Optional[str] = Form(None),
    edad: Optional[str] = Form(None),
    sexo: Optional[str] = Form(None),
    observaciones: Optional[str] = Form(None),
    alergias: Optional[str] = Form(None),
    foto_webp: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    mascota = Mascota(
        cliente_id=cliente_id, nombre=nombre,
        raza=raza, peso=float(peso) if peso else None,
        edad=int(edad) if edad else None, sexo=sexo,
        observaciones=observaciones, alergias=alergias,
        foto_webp=foto_webp,
    )
    db.add(mascota)
    db.commit()
    return RedirectResponse("/page/mascotas", status_code=303)


@router.post("/mascotas/{mascota_id}/editar")
def actualizar_mascota_form(
    mascota_id: int,
    nombre: str = Form(...),
    raza: Optional[str] = Form(None),
    peso: Optional[str] = Form(None),
    edad: Optional[str] = Form(None),
    sexo: Optional[str] = Form(None),
    observaciones: Optional[str] = Form(None),
    alergias: Optional[str] = Form(None),
    foto_webp: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    mascota = db.query(Mascota).filter(Mascota.id == mascota_id).first()
    if mascota:
        mascota.nombre = nombre
        mascota.raza = raza
        mascota.peso = float(peso) if peso else None
        mascota.edad = int(edad) if edad else None
        mascota.sexo = sexo
        mascota.observaciones = observaciones
        mascota.alergias = alergias
        mascota.foto_webp = foto_webp
        db.commit()
    return RedirectResponse("/page/mascotas", status_code=303)


# ── Servicios ─────────────────────────────────────────────

@router.get("/servicios", response_class=HTMLResponse)
def page_servicios(request: Request, db: Session = Depends(get_db)):
    servicios = db.query(Servicio).all()
    return templates.TemplateResponse("servicios/listar.html", {"request": request, "servicios": servicios})


@router.get("/servicios/nuevo", response_class=HTMLResponse)
def page_servicio_nuevo(request: Request):
    return templates.TemplateResponse("servicios/form.html", {"request": request, "servicio": None})


@router.get("/servicios/{servicio_id}/editar", response_class=HTMLResponse)
def page_servicio_editar(servicio_id: int, request: Request, db: Session = Depends(get_db)):
    servicio = db.query(Servicio).filter(Servicio.id == servicio_id).first()
    return templates.TemplateResponse("servicios/form.html", {"request": request, "servicio": servicio})


@router.post("/servicios/nuevo")
def crear_servicio_form(
    nombre: str = Form(...),
    descripcion: Optional[str] = Form(None),
    precio_base: float = Form(0.0),
    db: Session = Depends(get_db),
):
    servicio = Servicio(nombre=nombre, descripcion=descripcion, precio_base=precio_base)
    db.add(servicio)
    db.commit()
    return RedirectResponse("/page/servicios", status_code=303)


@router.post("/servicios/{servicio_id}/editar")
def actualizar_servicio_form(
    servicio_id: int,
    nombre: str = Form(...),
    descripcion: Optional[str] = Form(None),
    precio_base: float = Form(0.0),
    db: Session = Depends(get_db),
):
    servicio = db.query(Servicio).filter(Servicio.id == servicio_id).first()
    if servicio:
        servicio.nombre = nombre
        servicio.descripcion = descripcion
        servicio.precio_base = precio_base
        db.commit()
    return RedirectResponse("/page/servicios", status_code=303)


# ── Atenciones ────────────────────────────────────────────

@router.get("/atenciones", response_class=HTMLResponse)
def page_atenciones(request: Request, db: Session = Depends(get_db)):
    atenciones_raw = db.query(AtencionHistorial).order_by(AtencionHistorial.fecha.desc()).all()
    atenciones = []
    for a in atenciones_raw:
        mascota = db.query(Mascota).filter(Mascota.id == a.mascota_id).first()
        servicio = db.query(Servicio).filter(Servicio.id == a.servicio_id).first()
        atenciones.append({
            "id": a.id, "fecha": a.fecha.strftime("%d/%m/%Y %H:%M") if a.fecha else "—",
            "mascota_nombre": mascota.nombre if mascota else "—",
            "servicio_nombre": servicio.nombre if servicio else "—",
            "monto_cobrado": a.monto_cobrado, "medio_pago": a.medio_pago,
        })
    return templates.TemplateResponse("atenciones/listar.html", {"request": request, "atenciones": atenciones})


@router.get("/atenciones/nuevo", response_class=HTMLResponse)
def page_atencion_nuevo(request: Request, db: Session = Depends(get_db)):
    mascotas_raw = db.query(Mascota).all()
    mascotas = []
    for m in mascotas_raw:
        cliente = db.query(Cliente).filter(Cliente.id == m.cliente_id).first()
        mascotas.append({"id": m.id, "nombre": m.nombre, "cliente_nombre": cliente.nombre if cliente else "—"})
    servicios = db.query(Servicio).all()
    return templates.TemplateResponse("atenciones/form.html", {"request": request, "atencion": None, "mascotas": mascotas, "servicios": servicios})


@router.get("/atenciones/{atencion_id}/editar", response_class=HTMLResponse)
def page_atencion_editar(atencion_id: int, request: Request, db: Session = Depends(get_db)):
    atencion = db.query(AtencionHistorial).filter(AtencionHistorial.id == atencion_id).first()
    fecha_str = atencion.fecha.strftime("%Y-%m-%dT%H:%M") if atencion and atencion.fecha else ""
    atencion_data = None
    if atencion:
        atencion_data = {
            "id": atencion.id, "mascota_id": atencion.mascota_id,
            "servicio_id": atencion.servicio_id, "fecha": fecha_str,
            "observaciones": atencion.observaciones, "monto_cobrado": atencion.monto_cobrado,
            "medio_pago": atencion.medio_pago,
            "foto_antes_webp": atencion.foto_antes_webp, "foto_despues_webp": atencion.foto_despues_webp,
        }
    mascotas_raw = db.query(Mascota).all()
    mascotas = []
    for m in mascotas_raw:
        cliente = db.query(Cliente).filter(Cliente.id == m.cliente_id).first()
        mascotas.append({"id": m.id, "nombre": m.nombre, "cliente_nombre": cliente.nombre if cliente else "—"})
    servicios = db.query(Servicio).all()
    return templates.TemplateResponse("atenciones/form.html", {"request": request, "atencion": atencion_data, "mascotas": mascotas, "servicios": servicios})


@router.post("/atenciones/nuevo")
def crear_atencion_form(
    mascota_id: int = Form(...),
    servicio_id: int = Form(...),
    fecha: Optional[str] = Form(None),
    observaciones: Optional[str] = Form(None),
    monto_cobrado: float = Form(0.0),
    medio_pago: str = Form("efectivo"),
    foto_antes_webp: Optional[str] = Form(None),
    foto_despues_webp: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    fecha_dt = datetime.fromisoformat(fecha) if fecha else datetime.now()
    atencion = AtencionHistorial(
        mascota_id=mascota_id, servicio_id=servicio_id, fecha=fecha_dt,
        observaciones=observaciones, monto_cobrado=monto_cobrado,
        medio_pago=medio_pago,
        foto_antes_webp=foto_antes_webp, foto_despues_webp=foto_despues_webp,
    )
    db.add(atencion)
    db.commit()
    return RedirectResponse("/page/atenciones", status_code=303)


@router.post("/atenciones/{atencion_id}/editar")
def actualizar_atencion_form(
    atencion_id: int,
    mascota_id: int = Form(...),
    servicio_id: int = Form(...),
    fecha: Optional[str] = Form(None),
    observaciones: Optional[str] = Form(None),
    monto_cobrado: float = Form(0.0),
    medio_pago: str = Form("efectivo"),
    foto_antes_webp: Optional[str] = Form(None),
    foto_despues_webp: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    atencion = db.query(AtencionHistorial).filter(AtencionHistorial.id == atencion_id).first()
    if atencion:
        atencion.mascota_id = mascota_id
        atencion.servicio_id = servicio_id
        atencion.fecha = datetime.fromisoformat(fecha) if fecha else atencion.fecha
        atencion.observaciones = observaciones
        atencion.monto_cobrado = monto_cobrado
        atencion.medio_pago = medio_pago
        atencion.foto_antes_webp = foto_antes_webp
        atencion.foto_despues_webp = foto_despues_webp
        db.commit()
    return RedirectResponse("/page/atenciones", status_code=303)
