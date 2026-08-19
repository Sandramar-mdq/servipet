from pydantic import BaseModel


class ProductoCreate(BaseModel):
    nombre: str
    descripcion: str | None = None
    precio_compra: float = 0.0
    precio_venta: float = 0.0
    stock_actual: int = 0
    stock_minimo: int = 0
    unidad_medida: str = "un"
    categoria: str = "GENERAL"


class ProductoUpdate(BaseModel):
    nombre: str | None = None
    descripcion: str | None = None
    precio_compra: float | None = None
    precio_venta: float | None = None
    stock_actual: int | None = None
    stock_minimo: int | None = None
    unidad_medida: str | None = None
    categoria: str | None = None
    activo: bool | None = None


class ProductoResponse(BaseModel):
    id: int
    comercio_id: int
    nombre: str
    descripcion: str | None = None
    precio_compra: float
    precio_venta: float
    stock_actual: int
    stock_minimo: int
    unidad_medida: str
    categoria: str
    activo: bool

    model_config = {"from_attributes": True}


class StockAjuste(BaseModel):
    cantidad: int
    motivo: str = "Ajuste manual"


class StockAjusteResponse(BaseModel):
    producto_id: int
    stock_anterior: int
    stock_nuevo: int
    ajuste: int
