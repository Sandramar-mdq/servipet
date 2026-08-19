from pydantic import BaseModel


class DashboardResumen(BaseModel):
    fecha: str
    facturacion_servicios: float
    facturacion_productos: float
    facturacion_total: float
    cantidad_atenciones: int
    cantidad_ventas: int


class ServicioMetrica(BaseModel):
    servicio_id: int
    servicio_nombre: str
    cantidad: int


class HoraPico(BaseModel):
    hora: int
    cantidad_turnos: int


class ProductoVendido(BaseModel):
    producto_id: int
    producto_nombre: str
    cantidad_vendida: int
    total_facturado: float


class DashboardMetricas(BaseModel):
    periodo: str
    servicios_mas_pedidos: list[ServicioMetrica]
    horas_pico: list[HoraPico]
    productos_mas_vendidos: list[ProductoVendido]
