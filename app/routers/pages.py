import json
from datetime import date, datetime, time
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.atencion import AtencionHistorial
from app.models.caja import Caja
from app.models.caja_movimiento import CajaMovimiento
from app.models.cliente import Cliente
from app.models.mascota import Mascota
from app.models.producto import Producto
from app.models.servicio import Servicio
from app.models.turno import Turno
from app.models.venta import Venta
from app.services.caja import abrir_caja, cerrar_caja, registrar_movimiento
from app.services.dashboard import metricas, resumen_dia
from app.services.ventas import crear_venta as crear_venta_svc

router = APIRouter(prefix="/page", tags=["Pages"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    hoy_inicio = datetime.combine(date.today(), time.min)
    hoy_fin = datetime.combine(date.today(), time.max)
    stats = {
        "clientes": db.query(Cliente).filter(Cliente.activo == True).count(),
        "mascotas": db.query(Mascota).filter(Mascota.activo == True).count(),
        "servicios": db.query(Servicio).count(),
        "atenciones": db.query(AtencionHistorial).count(),
        "turnos_pendientes_hoy": (
            db.query(Turno)
            .filter(Turno.estado == "Pendiente", Turno.fecha_hora >= hoy_inicio, Turno.fecha_hora <= hoy_fin)
            .count()
        ),
    }
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={"stats": stats}
    )


# ── Clientes ──────────────────────────────────────────────

@router.get("/clientes", response_class=HTMLResponse)
def page_clientes(request: Request, db: Session = Depends(get_db)):
    clientes = db.query(Cliente).filter(Cliente.activo == True).all()
    return templates.TemplateResponse(
        request=request,
        name="clientes/listar.html",
        context={"clientes": clientes}
    )


@router.get("/clientes/nuevo", response_class=HTMLResponse)
def page_cliente_nuevo(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="clientes/form.html",
        context={"cliente": None}
    )


@router.get("/clientes/{cliente_id}", response_class=HTMLResponse)
def page_cliente_detalle(cliente_id: int, request: Request, db: Session = Depends(get_db)):
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id, Cliente.activo == True).first()
    if not cliente:
        return RedirectResponse("/page/clientes", status_code=303)
    mascotas = db.query(Mascota).filter(Mascota.cliente_id == cliente_id, Mascota.activo == True).all()
    mascotas_data = []
    total_gastado = 0.0
    for m in mascotas:
        atenciones_m = (
            db.query(AtencionHistorial)
            .filter(AtencionHistorial.mascota_id == m.id)
            .order_by(AtencionHistorial.fecha.desc())
            .all()
        )
        subtotal = sum(a.monto_cobrado for a in atenciones_m)
        total_gastado += subtotal
        ultima_atencion = atenciones_m[0] if atenciones_m else None
        mascotas_data.append({
            "id": m.id,
            "nombre": m.nombre,
            "especie": m.especie,
            "raza": m.raza,
            "sexo": m.sexo,
            "peso": m.peso,
            "edad": m.edad,
            "foto_webp": m.foto_webp,
            "total_atenciones": len(atenciones_m),
            "total_gastado": subtotal,
            "ultima_fecha": (
                ultima_atencion.fecha.strftime("%d/%m/%Y") if ultima_atencion and ultima_atencion.fecha else "—"
            ),
        })
    return templates.TemplateResponse(
        request=request,
        name="clientes/detalle.html",
        context={
            "request": request,
            "cliente": cliente,
            "mascotas": mascotas_data,
            "total_gastado": total_gastado,
            "total_mascotas": len(mascotas),
        },
    )


@router.get("/clientes/{cliente_id}/editar", response_class=HTMLResponse)
def page_cliente_editar(cliente_id: int, request: Request, db: Session = Depends(get_db)):
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    return templates.TemplateResponse(
        request=request,
        name="clientes/form.html",
        context={"cliente": cliente}
    )


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


@router.post("/clientes/{cliente_id}/eliminar")
def eliminar_cliente_form(cliente_id: int, db: Session = Depends(get_db)):
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if cliente:
        cliente.activo = False
        db.commit()
    return RedirectResponse("/page/clientes", status_code=303)


# ── Mascotas ──────────────────────────────────────────────

@router.get("/mascotas", response_class=HTMLResponse)
def page_mascotas(request: Request, db: Session = Depends(get_db)):
    mascotas_raw = db.query(Mascota).filter(Mascota.activo == True).all()
    mascotas = []
    for m in mascotas_raw:
        cliente = db.query(Cliente).filter(Cliente.id == m.cliente_id).first()
        mascotas.append({
            "id": m.id, "nombre": m.nombre, "especie": m.especie, "raza": m.raza,
            "sexo": m.sexo, "cliente_id": m.cliente_id,
            "cliente_nombre": cliente.nombre if cliente else "—",
        })
    return templates.TemplateResponse(
        request=request,
        name="mascotas/listar.html",
        context={"mascotas": mascotas}
    )


@router.get("/mascotas/nuevo", response_class=HTMLResponse)
def page_mascota_nuevo(request: Request, db: Session = Depends(get_db)):
    clientes = db.query(Cliente).filter(Cliente.activo == True).all()
    return templates.TemplateResponse(
        request=request,
        name="mascotas/form.html",
        context={
            "mascota": None, 
            "clientes": clientes,
        },
    )


@router.get("/mascotas/{mascota_id}", response_class=HTMLResponse)
def page_mascota_detalle(mascota_id: int, request: Request, db: Session = Depends(get_db)):
    mascota = db.query(Mascota).filter(Mascota.id == mascota_id, Mascota.activo == True).first()
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
    return templates.TemplateResponse(
        request=request,
        name="mascotas/detalle.html", 
        context={
            "mascota": mascota,
            "cliente": cliente,
            "atenciones": atenciones,
        },
    )


@router.get("/mascotas/{mascota_id}/editar", response_class=HTMLResponse)
def page_mascota_editar(mascota_id: int, request: Request, db: Session = Depends(get_db)):
    mascota = db.query(Mascota).filter(Mascota.id == mascota_id).first()
    clientes = db.query(Cliente).filter(Cliente.activo == True).all()
    return templates.TemplateResponse(
        request=request,
        name="mascotas/form.html",
        context={
            "mascota": mascota, 
            "clientes": clientes,
        },
    )


@router.post("/mascotas/nuevo")
def crear_mascota_form(
    cliente_id: int = Form(...),
    nombre: str = Form(...),
    especie: Optional[str] = Form(None),
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
        especie=especie, raza=raza, peso=float(peso) if peso else None,
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
    especie: Optional[str] = Form(None),
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
        mascota.especie = especie
        mascota.raza = raza
        mascota.peso = float(peso) if peso else None
        mascota.edad = int(edad) if edad else None
        mascota.sexo = sexo
        mascota.observaciones = observaciones
        mascota.alergias = alergias
        mascota.foto_webp = foto_webp
        db.commit()
    return RedirectResponse("/page/mascotas", status_code=303)


@router.post("/mascotas/{mascota_id}/eliminar")
def eliminar_mascota_form(mascota_id: int, db: Session = Depends(get_db)):
    mascota = db.query(Mascota).filter(Mascota.id == mascota_id).first()
    if mascota:
        mascota.activo = False
        db.commit()
    return RedirectResponse("/page/mascotas", status_code=303)


# ── Servicios ─────────────────────────────────────────────

@router.get("/servicios", response_class=HTMLResponse)
def page_servicios(request: Request, db: Session = Depends(get_db)):
    servicios = db.query(Servicio).all()
    return templates.TemplateResponse(
        request=request,
        name="servicios/listar.html",
        context={"servicios": servicios}
    )


@router.get("/servicios/nuevo", response_class=HTMLResponse)
def page_servicio_nuevo(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="servicios/form.html",
        context={"servicio": None}
    )


@router.get("/servicios/{servicio_id}/editar", response_class=HTMLResponse)
def page_servicio_editar(servicio_id: int, request: Request, db: Session = Depends(get_db)):
    servicio = db.query(Servicio).filter(Servicio.id == servicio_id).first()
    return templates.TemplateResponse(
        request=request,
        name="servicios/form.html",
        context={"servicio": servicio}
    )


@router.post("/servicios/nuevo")
def crear_servicio_form(
    nombre: str = Form(...),
    descripcion: Optional[str] = Form(None),
    precio_base: float = Form(0.0),
    duracion_minutos: int = Form(30),
    db: Session = Depends(get_db),
):
    servicio = Servicio(nombre=nombre, descripcion=descripcion, precio_base=precio_base, duracion_minutos=duracion_minutos)
    db.add(servicio)
    db.commit()
    return RedirectResponse("/page/servicios", status_code=303)


@router.post("/servicios/{servicio_id}/editar")
def actualizar_servicio_form(
    servicio_id: int,
    nombre: str = Form(...),
    descripcion: Optional[str] = Form(None),
    precio_base: float = Form(0.0),
    duracion_minutos: int = Form(30),
    db: Session = Depends(get_db),
):
    servicio = db.query(Servicio).filter(Servicio.id == servicio_id).first()
    if servicio:
        servicio.nombre = nombre
        servicio.descripcion = descripcion
        servicio.precio_base = precio_base
        servicio.duracion_minutos = duracion_minutos
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
    return templates.TemplateResponse(
        request=request,
        name="atenciones/listar.html",
        context={"atenciones": atenciones}
    )


@router.get("/atenciones/nuevo", response_class=HTMLResponse)
def page_atencion_nuevo(request: Request, db: Session = Depends(get_db)):
    mascotas_raw = db.query(Mascota).filter(Mascota.activo == True).all()
    mascotas = []
    for m in mascotas_raw:
        cliente = db.query(Cliente).filter(Cliente.id == m.cliente_id).first()
        mascotas.append({"id": m.id, "nombre": m.nombre, "cliente_nombre": cliente.nombre if cliente else "—"})
    servicios = db.query(Servicio).all()
    return templates.TemplateResponse(
        request=request,
        name="atenciones/form.html",
        context={
            "atencion": None,
            "mascotas": mascotas,
            "servicios": servicios
        },
    )


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
    mascotas_raw = db.query(Mascota).filter(Mascota.activo == True).all()
    mascotas = []
    for m in mascotas_raw:
        cliente = db.query(Cliente).filter(Cliente.id == m.cliente_id).first()
        mascotas.append({"id": m.id, "nombre": m.nombre, "cliente_nombre": cliente.nombre if cliente else "—"})
    servicios = db.query(Servicio).all()
    return templates.TemplateResponse(
        request=request,
        name="atenciones/form.html",
        context={
            "atencion": atencion_data,
            "mascotas": mascotas,
            "servicios": servicios
        },
    )


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


# ── Productos / Stock ─────────────────────────────────────

@router.get("/productos", response_class=HTMLResponse)
def page_productos(
    request: Request,
    categoria: str | None = None,
    busqueda: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Producto).filter(Producto.activo == True)
    if categoria:
        query = query.filter(Producto.categoria == categoria)
    if busqueda:
        query = query.filter(Producto.nombre.ilike(f"%{busqueda}%"))
    productos = query.order_by(Producto.nombre.asc()).all()
    categorias_raw = db.query(Producto.categoria).filter(Producto.activo == True).distinct().all()
    categorias = sorted([c[0] for c in categorias_raw if c[0]])
    return templates.TemplateResponse(
        request=request,
        name="productos/listar.html",
        context={
            "productos": productos,
            "categorias": categorias,
            "categoria_actual": categoria or "",
            "busqueda": busqueda or "",
        },
    )


@router.get("/productos/nuevo", response_class=HTMLResponse)
def page_producto_nuevo(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="productos/form.html",
        context={"producto": None},
    )


@router.get("/productos/{producto_id}/editar", response_class=HTMLResponse)
def page_producto_editar(producto_id: int, request: Request, db: Session = Depends(get_db)):
    producto = db.query(Producto).filter(Producto.id == producto_id).first()
    if not producto:
        return RedirectResponse("/page/productos", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="productos/form.html",
        context={"producto": producto},
    )


@router.post("/productos/nuevo")
def crear_producto_form(
    nombre: str = Form(...),
    descripcion: Optional[str] = Form(None),
    precio_compra: float = Form(0.0),
    precio_venta: float = Form(0.0),
    stock_actual: int = Form(0),
    stock_minimo: int = Form(0),
    unidad_medida: str = Form("un"),
    categoria: str = Form("GENERAL"),
    db: Session = Depends(get_db),
):
    producto = Producto(
        comercio_id=1, nombre=nombre, descripcion=descripcion,
        precio_compra=precio_compra, precio_venta=precio_venta,
        stock_actual=stock_actual, stock_minimo=stock_minimo,
        unidad_medida=unidad_medida, categoria=categoria,
    )
    db.add(producto)
    db.commit()
    return RedirectResponse("/page/productos", status_code=303)


@router.post("/productos/{producto_id}/editar")
def actualizar_producto_form(
    producto_id: int,
    nombre: str = Form(...),
    descripcion: Optional[str] = Form(None),
    precio_compra: float = Form(0.0),
    precio_venta: float = Form(0.0),
    stock_actual: int = Form(0),
    stock_minimo: int = Form(0),
    unidad_medida: str = Form("un"),
    categoria: str = Form("GENERAL"),
    db: Session = Depends(get_db),
):
    producto = db.query(Producto).filter(Producto.id == producto_id).first()
    if producto:
        producto.nombre = nombre
        producto.descripcion = descripcion
        producto.precio_compra = precio_compra
        producto.precio_venta = precio_venta
        producto.stock_actual = stock_actual
        producto.stock_minimo = stock_minimo
        producto.unidad_medida = unidad_medida
        producto.categoria = categoria
        db.commit()
    return RedirectResponse("/page/productos", status_code=303)


@router.post("/productos/{producto_id}/stock")
def ajustar_stock_form(
    producto_id: int,
    cantidad: int = Form(...),
    db: Session = Depends(get_db),
):
    producto = db.query(Producto).filter(Producto.id == producto_id).first()
    if producto:
        nuevo = producto.stock_actual + cantidad
        if nuevo >= 0:
            producto.stock_actual = nuevo
            db.commit()
    return RedirectResponse("/page/productos", status_code=303)


# ── POS / Punto de Venta ──────────────────────────────────

@router.get("/pos", response_class=HTMLResponse)
def page_pos(request: Request, db: Session = Depends(get_db)):
    productos = db.query(Producto).filter(Producto.activo == True, Producto.stock_actual > 0).order_by(Producto.nombre.asc()).all()
    servicios = db.query(Servicio).all()
    clientes = db.query(Cliente).filter(Cliente.activo == True).order_by(Cliente.nombre.asc()).all()
    caja_actual = (
        db.query(Caja)
        .filter(Caja.estado == "ABIERTA")
        .order_by(Caja.fecha_apertura.desc())
        .first()
    )
    return templates.TemplateResponse(
        request=request,
        name="pos/index.html",
        context={
            "productos": productos,
            "servicios": servicios,
            "clientes": clientes,
            "caja_actual": caja_actual,
        },
    )


@router.post("/pos/crear")
def crear_venta_form(
    cliente_id: Optional[int] = Form(None),
    medio_pago: str = Form("efectivo"),
    descuento: float = Form(0.0),
    notas: Optional[str] = Form(None),
    detalles_json: str = Form("[]"),
    redirect_to: str = Form("/page/pos"),
    db: Session = Depends(get_db),
):
    try:
        detalles_raw = json.loads(detalles_json)
    except json.JSONDecodeError:
        return RedirectResponse("/page/pos?error=Datos invalidos", status_code=303)

    from app.schemas.venta import VentaCreate, VentaDetalleCreate

    detalles = []
    for d in detalles_raw:
        detalles.append(VentaDetalleCreate(
            tipo=d.get("tipo", "PRODUCTO"),
            producto_id=d.get("producto_id"),
            servicio_id=d.get("servicio_id"),
            cantidad=d.get("cantidad", 1),
            precio_unitario=d.get("precio_unitario", 0.0),
        ))

    venta_data = VentaCreate(
        cliente_id=cliente_id,
        medio_pago=medio_pago,
        descuento=descuento,
        notas=notas,
        detalles=detalles,
    )

    try:
        crear_venta_svc(db, venta_data, usuario_id=1, comercio_id=1)
    except Exception:
        return RedirectResponse("/page/pos?error=Error al crear la venta", status_code=303)

    return RedirectResponse(redirect_to + "?success=Venta registrada", status_code=303)


# ── Caja Diaria ───────────────────────────────────────────

@router.get("/caja", response_class=HTMLResponse)
def page_caja(request: Request, db: Session = Depends(get_db)):
    caja_actual = (
        db.query(Caja)
        .filter(Caja.estado == "ABIERTA")
        .order_by(Caja.fecha_apertura.desc())
        .first()
    )
    movimientos = []
    total_ingresos = 0.0
    total_egresos = 0.0
    if caja_actual:
        movimientos_raw = (
            db.query(CajaMovimiento)
            .filter(CajaMovimiento.caja_id == caja_actual.id)
            .order_by(CajaMovimiento.creado_en.desc())
            .all()
        )
        movimientos = movimientos_raw
        total_ingresos = sum(m.monto for m in movimientos_raw if m.tipo == "INGRESO")
        total_egresos = sum(m.monto for m in movimientos_raw if m.tipo == "EGRESO")

    historial = (
        db.query(Caja)
        .filter(Caja.estado == "CERRADA")
        .order_by(Caja.fecha_apertura.desc())
        .limit(30)
        .all()
    )
    return templates.TemplateResponse(
        request=request,
        name="caja/index.html",
        context={
            "caja_actual": caja_actual,
            "movimientos": movimientos,
            "total_ingresos": total_ingresos,
            "total_egresos": total_egresos,
            "historial": historial,
        },
    )


@router.post("/caja/abrir")
def abrir_caja_form(
    monto_inicial: float = Form(0.0),
    notas: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    try:
        abrir_caja(db, comercio_id=1, usuario_id=1, monto_inicial=monto_inicial, notas=notas)
        return RedirectResponse("/page/caja?success=Caja abierta", status_code=303)
    except Exception as e:
        msg = str(e.detail) if hasattr(e, "detail") else str(e)
        return RedirectResponse(f"/page/caja?error={msg}", status_code=303)


@router.post("/caja/movimiento")
def registrar_movimiento_form(
    tipo: str = Form("INGRESO"),
    monto: float = Form(0.0),
    descripcion: str = Form(""),
    db: Session = Depends(get_db),
):
    caja = db.query(Caja).filter(Caja.estado == "ABIERTA").first()
    if not caja:
        return RedirectResponse("/page/caja?error=No hay caja abierta", status_code=303)
    try:
        registrar_movimiento(db, caja.id, tipo, monto, descripcion)
        return RedirectResponse("/page/caja?success=Movimiento registrado", status_code=303)
    except Exception as e:
        msg = str(e.detail) if hasattr(e, "detail") else str(e)
        return RedirectResponse(f"/page/caja?error={msg}", status_code=303)


@router.post("/caja/cerrar")
def cerrar_caja_form(
    monto_final_real: float = Form(0.0),
    notas: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    caja = db.query(Caja).filter(Caja.estado == "ABIERTA").first()
    if not caja:
        return RedirectResponse("/page/caja?error=No hay caja abierta", status_code=303)
    try:
        cerrar_caja(db, caja.id, usuario_id=1, monto_final_real=monto_final_real, notas=notas)
        return RedirectResponse("/page/caja?success=Caja cerrada", status_code=303)
    except Exception as e:
        msg = str(e.detail) if hasattr(e, "detail") else str(e)
        return RedirectResponse(f"/page/caja?error={msg}", status_code=303)


# ── Dashboard Métricas ────────────────────────────────────

@router.get("/dashboard", response_class=HTMLResponse)
def page_dashboard(
    request: Request,
    fecha: str | None = None,
    dias: int = 30,
    db: Session = Depends(get_db),
):
    f = None
    if fecha:
        try:
            f = date.fromisoformat(fecha)
        except ValueError:
            pass
    resumen = resumen_dia(db, comercio_id=1, fecha=f)
    met = metricas(db, comercio_id=1, dias=dias)
    return templates.TemplateResponse(
        request=request,
        name="dashboard/index.html",
        context={
            "resumen": resumen,
            "metricas": met,
            "fecha_filtro": fecha or date.today().isoformat(),
            "dias": dias,
        },
    )
