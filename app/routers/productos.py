from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user, require_roles
from app.models.producto import Producto
from app.models.usuario import Usuario
from app.schemas.producto import (
    ProductoCreate,
    ProductoResponse,
    ProductoUpdate,
    StockAjuste,
    StockAjusteResponse,
)

router = APIRouter(prefix="/productos", tags=["Productos"])


def _admin(user: Usuario = Depends(require_roles("ADMIN"))):
    return user


@router.get("/", response_model=list[ProductoResponse])
def listar_productos(
    categoria: str | None = None,
    busqueda: str | None = None,
    db: Session = Depends(get_db),
    _user: Usuario = Depends(_admin),
):
    query = db.query(Producto).filter(Producto.activo == True)
    if categoria:
        query = query.filter(Producto.categoria == categoria)
    if busqueda:
        query = query.filter(Producto.nombre.ilike(f"%{busqueda}%"))
    return query.order_by(Producto.nombre.asc()).all()


@router.post("/", response_model=ProductoResponse, status_code=201)
def crear_producto(
    data: ProductoCreate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(_admin),
):
    producto = Producto(comercio_id=user.comercio_id, **data.model_dump())
    db.add(producto)
    db.commit()
    db.refresh(producto)
    return producto


@router.get("/{producto_id}", response_model=ProductoResponse)
def obtener_producto(
    producto_id: int,
    db: Session = Depends(get_db),
    _user: Usuario = Depends(_admin),
):
    producto = db.query(Producto).filter(Producto.id == producto_id).first()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return producto


@router.put("/{producto_id}", response_model=ProductoResponse)
def actualizar_producto(
    producto_id: int,
    data: ProductoUpdate,
    db: Session = Depends(get_db),
    _user: Usuario = Depends(_admin),
):
    producto = db.query(Producto).filter(Producto.id == producto_id).first()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(producto, key, value)
    db.commit()
    db.refresh(producto)
    return producto


@router.delete("/{producto_id}", status_code=204)
def eliminar_producto(
    producto_id: int,
    db: Session = Depends(get_db),
    _user: Usuario = Depends(_admin),
):
    producto = db.query(Producto).filter(Producto.id == producto_id).first()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    producto.activo = False
    db.commit()


@router.post("/{producto_id}/stock", response_model=StockAjusteResponse)
def ajustar_stock(
    producto_id: int,
    data: StockAjuste,
    db: Session = Depends(get_db),
    _user: Usuario = Depends(_admin),
):
    producto = db.query(Producto).filter(Producto.id == producto_id).first()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    anterior = producto.stock_actual
    producto.stock_actual += data.cantidad
    if producto.stock_actual < 0:
        raise HTTPException(status_code=400, detail="El stock no puede ser negativo")
    db.commit()
    return StockAjusteResponse(
        producto_id=producto.id,
        stock_anterior=anterior,
        stock_nuevo=producto.stock_actual,
        ajuste=data.cantidad,
    )
