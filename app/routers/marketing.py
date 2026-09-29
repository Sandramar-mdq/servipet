"""API del Modulo Solidario, Fidelizacion y Kit de Marketing B2B (Etapa 12).

Tres bloques de endpoints bajo `/api/v1/marketing`:

1. `/solidaridad`  - cartel PDF A4 y placa digital 9:16 para avisos de mascota
   perdida / adopcion / encontrada de la red comunitaria.
2. `/cumpleanos`   - listado de proximos cumpleanos (dato sensible, opt-in) y
   placa cuadrada 1:1 con beneficio configurable, con control anti-duplicado.
3. `/kit`          - generador de placas cuadradas 1:1 para promociones rapidas.

RBAC (mapeo de roles del proyecto):

- SuperAdmin -> `rol == "ADMIN"` con `comercio_id is None`: acceso transversal.
- Admin      -> `rol == "ADMIN"` con comercio asignado.
- Staff      -> `rol == "EMPLEADO"`.

El aislamiento multi-tenant se valida con `_verificar_tenant`, que replica el
patron de `app.routers.comunidad`: un SuperAdmin (comercio_id None) pasa, un
empleado de otro comercio recibe 403.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.downloads import descarga_archivo
from app.database import get_db
from app.dependencies.auth import require_roles
from app.models.comercio import Comercio
from app.models.mascota import Mascota
from app.models.pieza_generada import FormatoPieza, TipoPieza
from app.models.usuario import Usuario
from app.schemas.solidaridad import (
    ConfigCumpleanosResponse,
    ConfigCumpleanosUpdate,
    ProximosCumpleanosResponse,
    PromocionCreate,
)
from app.services import marketing_service, pieza_service

logger = logging.getLogger("servipet.marketing")

router = APIRouter(prefix="/api/v1/marketing", tags=["Marketing B2B"])

PDF_MT = "application/pdf"
PNG_MT = "image/png"


# --- Dependencias de acceso ---

def _staff(user: Usuario = Depends(require_roles("ADMIN", "EMPLEADO"))) -> Usuario:
    return user


def _admin(user: Usuario = Depends(require_roles("ADMIN"))) -> Usuario:
    return user


def _verificar_tenant(user: Usuario, comercio_id: int) -> None:
    """Impide que un Admin/Empleado acceda a piezas de otro comercio.

    Un SuperAdmin tiene `comercio_id is None` y por lo tanto pasa la validacion.
    """
    if user.comercio_id is not None and user.comercio_id != comercio_id:
        raise HTTPException(status_code=403, detail="Permisos insuficientes")


def _optin(db: Session, comercio_id: int, atributo: str, mensaje: str) -> Comercio:
    """Carga el comercio exigiendo el opt-in del modulo indicado."""
    comercio = db.query(Comercio).filter(Comercio.id == comercio_id).first()
    if not comercio:
        raise HTTPException(status_code=404, detail="Comercio no encontrado")
    if not getattr(comercio, atributo, False):
        raise HTTPException(status_code=403, detail=mensaje)
    return comercio


def _bloquear_duplicado(ya_registrado: bool, forzar: bool, mensaje: str) -> None:
    if ya_registrado and not forzar:
        raise HTTPException(status_code=409, detail=mensaje)


# ==========================================================================
# 1. Modulo solidario
# ==========================================================================

def _contexto_cartel(db: Session, aviso_id: int, user: Usuario) -> tuple[dict, int]:
    """Carga los datos del cartel aplicando RBAC, tenant y opt-in en un punto."""
    from app.models.aviso_comunitario import AvisoComunitario

    aviso = db.query(AvisoComunitario).filter(AvisoComunitario.id == aviso_id).first()
    if not aviso:
        raise HTTPException(status_code=404, detail="Aviso no encontrado")

    _verificar_tenant(user, aviso.comercio_id)
    _optin(
        db,
        aviso.comercio_id,
        "habilitar_modulo_solidario",
        "El módulo solidario está deshabilitado para este comercio",
    )

    try:
        data = marketing_service.datos_cartel_solidario(db, aviso_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Aviso no encontrado")
    return data, aviso.comercio_id


@router.get(
    "/solidaridad/avisos/{aviso_id}/cartel.pdf",
    summary="Cartel PDF A4 vertical de mascota perdida / adopcion",
)
def generar_cartel_pdf(
    aviso_id: int,
    forzar: bool = Query(default=False, description="Regenera aunque ya exista la pieza"),
    db: Session = Depends(get_db),
    user: Usuario = Depends(_staff),
):
    data, comercio_id = _contexto_cartel(db, aviso_id, user)

    _bloquear_duplicado(
        marketing_service.ya_registrado(
            db, comercio_id, TipoPieza.CARTEL_SOLIDARIO, FormatoPieza.PDF_A4, aviso_id, None
        ),
        forzar,
        "El cartel ya fue generado para este aviso; usá forzar=1 para regenerarlo",
    )

    contenido = pieza_service.pdf_cartel_solidario(data)
    nombre = f"cartel_{aviso_id}.pdf"
    marketing_service.registrar_pieza(
        db,
        comercio_id=comercio_id,
        tipo=TipoPieza.CARTEL_SOLIDARIO,
        formato=FormatoPieza.PDF_A4,
        referencia_tipo="AVISO",
        referencia_id=aviso_id,
        anio=None,
        nombre_archivo=nombre,
        usuario_id=user.id,
    )
    return descarga_archivo(contenido, PDF_MT, nombre)


@router.get(
    "/solidaridad/avisos/{aviso_id}/placa-vertical.png",
    summary="Placa digital vertical 9:16 (1080x1920) del cartel",
)
def generar_placa_vertical(
    aviso_id: int,
    forzar: bool = Query(default=False, description="Regenera aunque ya exista la pieza"),
    db: Session = Depends(get_db),
    user: Usuario = Depends(_staff),
):
    data, comercio_id = _contexto_cartel(db, aviso_id, user)

    _bloquear_duplicado(
        marketing_service.ya_registrado(
            db, comercio_id, TipoPieza.CARTEL_SOLIDARIO, FormatoPieza.PNG_9X16, aviso_id, None
        ),
        forzar,
        "La placa ya fue generada para este aviso; usá forzar=1 para regenerarla",
    )

    contenido = pieza_service.png_placa_vertical(data)
    nombre = f"placa_9x16_{aviso_id}.png"
    marketing_service.registrar_pieza(
        db,
        comercio_id=comercio_id,
        tipo=TipoPieza.CARTEL_SOLIDARIO,
        formato=FormatoPieza.PNG_9X16,
        referencia_tipo="AVISO",
        referencia_id=aviso_id,
        anio=None,
        nombre_archivo=nombre,
        usuario_id=user.id,
    )
    return descarga_archivo(contenido, PNG_MT, nombre)


# ==========================================================================
# 2. Fidelizacion cumpleaños (opt-in)
# ==========================================================================

@router.get(
    "/cumpleanos/proximos",
    response_model=ProximosCumpleanosResponse,
    summary="Proximos cumpleanos dentro de la ventana (solo mascotas activas y vivas)",
)
def listar_proximos_cumpleanos(
    dias: int = Query(default=7, ge=1, le=31, description="Ventana en dias, inclusiva"),
    db: Session = Depends(get_db),
    user: Usuario = Depends(_staff),
):
    """Lista los cumpleanos de la ventana.

    El tenant se toma del usuariostaff, salvo que sea SuperAdmin, en cuyo caso
    se puede consultar el comercio objetivo con `comercio_id`.
    """
    comercio_id = user.comercio_id
    if comercio_id is None:
        raise HTTPException(
            status_code=400,
            detail="Indicá el comercio con comercio_id=ID (requerido para SuperAdmin)",
        )

    _optin(
        db,
        comercio_id,
        "habilitar_cumpleanos",
        "El módulo de cumpleaños está deshabilitado para este comercio",
    )
    return marketing_service.proximos_cumpleanos(db, comercio_id=comercio_id, dias=dias)


@router.get(
    "/cumpleanos/mascotas/{mascota_id}/placa.png",
    summary="Placa cuadrada 1:1 (1080x1080) de cumpleanos",
)
def generar_placa_cumpleanos(
    mascota_id: int,
    beneficio: str | None = Query(default=None, max_length=200),
    forzar: bool = Query(default=False, description="Regenera aunque ya se envio este anio"),
    db: Session = Depends(get_db),
    user: Usuario = Depends(_staff),
):
    """Genera la placa de cumpleanos y registra el envio para evitar duplicados
    en el mismo anio."""
    mascota = db.query(Mascota).filter(Mascota.id == mascota_id).first()
    if not mascota:
        raise HTTPException(status_code=404, detail="Mascota no encontrada")

    cliente = mascota.cliente
    comercio_id = cliente.comercio_id if cliente is not None else None
    if comercio_id is None:
        raise HTTPException(status_code=404, detail="Mascota sin comercio asignado")

    _verificar_tenant(user, comercio_id)
    _optin(
        db,
        comercio_id,
        "habilitar_cumpleanos",
        "El módulo de cumpleaños está deshabilitado para este comercio",
    )

    try:
        data = marketing_service.datos_placa_cumpleanos(
            db, mascota_id, beneficio_override=beneficio
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Mascota no encontrada")

    anio = data["anio"]
    _bloquear_duplicado(
        marketing_service.ya_registrado(
            db, comercio_id, TipoPieza.CUMPLEANOS, FormatoPieza.PNG_1X1, mascota_id, anio
        ),
        forzar,
        f"La placa de cumpleaños de {data['mascota_nombre']} ya se generó este año; "
        "usá forzar=1 para regenerarla",
    )

    contenido = pieza_service.png_placa_cuadrada(data)
    nombre = f"cumpleanos_{mascota_id}_{anio}.png"
    marketing_service.registrar_pieza(
        db,
        comercio_id=comercio_id,
        tipo=TipoPieza.CUMPLEANOS,
        formato=FormatoPieza.PNG_1X1,
        referencia_tipo="MASCOTA",
        referencia_id=mascota_id,
        anio=anio,
        nombre_archivo=nombre,
        beneficio=data.get("beneficio"),
        usuario_id=user.id,
    )
    return descarga_archivo(contenido, PNG_MT, nombre)


@router.get(
    "/cumpleanos/config",
    response_model=ConfigCumpleanosResponse,
    summary="Configuracion de cumpleanos del comercio",
)
def obtener_config_cumpleanos(
    db: Session = Depends(get_db),
    user: Usuario = Depends(_staff),
):
    comercio_id = user.comercio_id
    if comercio_id is None:
        raise HTTPException(
            status_code=400,
            detail="Indicá el comercio con comercio_id=ID (requerido para SuperAdmin)",
        )
    comercio = db.query(Comercio).filter(Comercio.id == comercio_id).first()
    if not comercio:
        raise HTTPException(status_code=404, detail="Comercio no encontrado")

    from app.models.cliente import Cliente

    consentidos = (
        db.query(Cliente).filter(Cliente.comercio_id == comercio_id, Cliente.acepta_cumpleanos == True)  # noqa: E712
        .count()
    )
    return ConfigCumpleanosResponse(
        comercio_id=comercio_id,
        comercio_nombre=comercio.nombre,
        habilitar=comercio.habilitar_cumpleanos,
        beneficio=comercio.beneficio_cumpleanos or marketing_service.BENEFICIO_CUMPLEANOS_DEFAULT,
        clientes_consentidos=consentidos,
    )


@router.put(
    "/cumpleanos/config",
    response_model=ConfigCumpleanosResponse,
    summary="Actualiza el opt-in y el beneficio de cumpleanos (solo Admin)",
)
def actualizar_config_cumpleanos(
    datos: ConfigCumpleanosUpdate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(_admin),
):
    comercio_id = user.comercio_id
    if comercio_id is None:
        raise HTTPException(
            status_code=400,
            detail="Indicá el comercio con comercio_id=ID (requerido para SuperAdmin)",
        )
    comercio = db.query(Comercio).filter(Comercio.id == comercio_id).first()
    if not comercio:
        raise HTTPException(status_code=404, detail="Comercio no encontrado")

    if datos.habilitar is not None:
        comercio.habilitar_cumpleanos = datos.habilitar
    if datos.beneficio is not None:
        comercio.beneficio_cumpleanos = datos.beneficio or None
    db.commit()
    db.refresh(comercio)

    from app.models.cliente import Cliente

    consentidos = (
        db.query(Cliente).filter(Cliente.comercio_id == comercio_id, Cliente.acepta_cumpleanos == True)  # noqa: E712
        .count()
    )
    return ConfigCumpleanosResponse(
        comercio_id=comercio_id,
        comercio_nombre=comercio.nombre,
        habilitar=comercio.habilitar_cumpleanos,
        beneficio=comercio.beneficio_cumpleanos or marketing_service.BENEFICIO_CUMPLEANOS_DEFAULT,
        clientes_consentidos=consentidos,
    )


# ==========================================================================
# 3. Kit Marketing B2B
# ==========================================================================

@router.post(
    "/kit/promocion/placa.png",
    summary="Placa cuadrada 1:1 (1080x1080) para una promocion rapida",
)
def generar_placa_promocion(
    datos: PromocionCreate,
    db: Session = Depends(get_db),
    user: Usuario = Depends(_staff),
):
    """Genera la placa cuadrada de una promocion.

    El endpoint es stateless por defecto: no deja registro salvo que se pida
    explicitamente con `registrar=true`, para que el comercio pueda producir
    tantas variantes de una campana como necesite.
    """
    comercio_id = user.comercio_id
    comercio = None
    if comercio_id is not None:
        _verificar_tenant(user, comercio_id)
        comercio = db.query(Comercio).filter(Comercio.id == comercio_id).first()
    elif user.rol != "ADMIN":
        raise HTTPException(status_code=403, detail="Permisos insuficientes")

    data = marketing_service.datos_promocion(datos.model_dump(), comercio)
    contenido = pieza_service.png_placa_cuadrada(data)
    nombre = marketing_service.nombre_archivo_promocion(datos.titulo)

    if datos.registrar and comercio is not None:
        marketing_service.registrar_pieza(
            db,
            comercio_id=comercio.id,
            tipo=TipoPieza.PROMOCION,
            formato=FormatoPieza.PNG_1X1,
            referencia_tipo=None,
            referencia_id=None,
            anio=None,
            nombre_archivo=nombre,
            beneficio=data.get("beneficio") or None,
            usuario_id=user.id,
        )
    return descarga_archivo(contenido, PNG_MT, nombre)
