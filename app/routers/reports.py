"""Etapa 10.2 - Reportes exportables (PDF y Excel).

Endpoints de descarga bajo /reportes (solo ADMIN) y pagina de vista
previa /page/reportes.
"""

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from app.core.templating import get_templates
from app.database import get_db
from app.dependencies.auth import require_roles
from app.models.usuario import Usuario
from app.services import report_service

router = APIRouter(prefix="/reportes", tags=["Reportes"])
pages_router = APIRouter(prefix="/page", tags=["Reportes Pages"])
templates = get_templates()

PDF_MT = "application/pdf"
XLSX_MT = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _admin(user: Usuario = Depends(require_roles("ADMIN"))):
    return user


def _parse_fecha(valor: str | None) -> date | None:
    if not valor:
        return None
    try:
        return date.fromisoformat(valor)
    except ValueError:
        return None


def _descarga(contenido: bytes, media_type: str, filename: str) -> Response:
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=contenido, media_type=media_type, headers=headers)


# ── Caja Diaria ─────────────────────────────────────────────────┬──

@router.get("/caja/pdf")
def reporte_caja_pdf(
    fecha: str | None = None,
    caja_id: int | None = None,
    db: Session = Depends(get_db),
    user: Usuario = Depends(_admin),
):
    data = report_service.resumen_caja(db, user.comercio_id, fecha=_parse_fecha(fecha), caja_id=caja_id)
    return _descarga(
        report_service.pdf_reporte_caja(data),
        PDF_MT,
        f"reporte_caja_{data['fecha']}.pdf",
    )


@router.get("/caja/excel")
def reporte_caja_excel(
    fecha: str | None = None,
    caja_id: int | None = None,
    db: Session = Depends(get_db),
    user: Usuario = Depends(_admin),
):
    data = report_service.resumen_caja(db, user.comercio_id, fecha=_parse_fecha(fecha), caja_id=caja_id)
    return _descarga(
        report_service.xlsx_reporte_caja(data),
        XLSX_MT,
        f"reporte_caja_{data['fecha']}.xlsx",
    )


# ── Ventas POS ───────────────────────────────────────────────────

@router.get("/ventas/pdf")
def reporte_ventas_pdf(
    desde: str | None = None,
    hasta: str | None = None,
    db: Session = Depends(get_db),
    user: Usuario = Depends(_admin),
):
    data = report_service.reporte_ventas(db, user.comercio_id, *_rango(desde, hasta))
    return _descarga(
        report_service.pdf_reporte_ventas(data),
        PDF_MT,
        f"reporte_ventas_{data['desde']}_{data['hasta']}.pdf",
    )


@router.get("/ventas/excel")
def reporte_ventas_excel(
    desde: str | None = None,
    hasta: str | None = None,
    db: Session = Depends(get_db),
    user: Usuario = Depends(_admin),
):
    data = report_service.reporte_ventas(db, user.comercio_id, *_rango(desde, hasta))
    return _descarga(
        report_service.xlsx_reporte_ventas(data),
        XLSX_MT,
        f"reporte_ventas_{data['desde']}_{data['hasta']}.xlsx",
    )


# ── Metricas admin ───────────────────────────────────────────────

@router.get("/metricas/pdf")
def reporte_metricas_pdf(
    dias: int = 30,
    db: Session = Depends(get_db),
    user: Usuario = Depends(_admin),
):
    data = report_service.reporte_metricas(db, user.comercio_id, dias=dias)
    return _descarga(
        report_service.pdf_reporte_metricas(data),
        PDF_MT,
        f"reporte_metricas_{date.today().isoformat()}.pdf",
    )


@router.get("/metricas/excel")
def reporte_metricas_excel(
    dias: int = 30,
    db: Session = Depends(get_db),
    user: Usuario = Depends(_admin),
):
    data = report_service.reporte_metricas(db, user.comercio_id, dias=dias)
    return _descarga(
        report_service.xlsx_reporte_metricas(data),
        XLSX_MT,
        f"reporte_metricas_{date.today().isoformat()}.xlsx",
    )


# ── Vista previa HTML ────────────────────────────────────────────

def _rango(desde: str | None, hasta: str | None) -> tuple[date, date]:
    d = _parse_fecha(desde) or (date.today() - timedelta(days=30))
    h = _parse_fecha(hasta) or date.today()
    if d > h:
        d, h = h, d
    return d, h


@pages_router.get("/reportes", response_class=HTMLResponse)
def page_reportes(
    request: Request,
    tipo: str = "caja",
    fecha: str | None = None,
    desde: str | None = None,
    hasta: str | None = None,
    dias: int = 30,
    db: Session = Depends(get_db),
):
    comercio_id = 1
    data = None
    try:
        if tipo == "ventas":
            f_desde, f_hasta = _rango(desde, hasta)
            data = report_service.reporte_ventas(db, comercio_id, f_desde, f_hasta)
        elif tipo == "metricas":
            data = report_service.reporte_metricas(db, comercio_id, dias=dias)
        else:
            tipo = "caja"
            data = report_service.resumen_caja(db, comercio_id, fecha=_parse_fecha(fecha))
    except Exception:
        data = None

    hoy = date.today().isoformat()
    return templates.TemplateResponse(
        request=request,
        name="reportes/index.html",
        context={
            "tipo": tipo,
            "data": data,
            "fecha_filtro": fecha or hoy,
            "desde_filtro": desde or (date.today() - timedelta(days=30)).isoformat(),
            "hasta_filtro": hasta or hoy,
            "dias": dias,
            "generado_en": datetime.now().strftime("%d/%m/%Y %H:%M"),
        },
    )