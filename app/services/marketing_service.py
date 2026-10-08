"""Capa de datos y orquestacion del modulo de Marketing B2B (Etapa 12).

Este modulo obtiene y prepara los datos que luego `app.services.pieza_service`
convierte en PDF/PNG. Responsabilidades:

1. `datos_cartel_solidario`  - arma el contenido del cartel de mascota
   perdida / adopcion / encontrada a partir de un `AvisoComunitario` existente.
2. `proximos_cumpleanos`     - lista los cumpleanos dentro de una ventana con el
   FILTRO ESTRICTO de mascotas activas y no fallecidas.
3. `datos_placa_cumpleanos`  - arma la placa cuadrada de cumpleanos.
4. `datos_promocion`         - arma la placa cuadrada del kit B2B.
5. `registrar_pieza` / `ya_registrado` - auditoria y anti-duplicado.

Convenciones de fecha:

- Los cumpleaños usan `date.today()` (fecha LOCAL) porque un cumpleaños es un
  evento del calendario local del comercio. El parametro `hoy` es inyectable
  para que los tests sean deterministas.
- La bitacora `PiezaGenerada.creado_at` usa UTC, igual que `AvisoComunitario`.
  No se mezclan las dos bases en la misma columna.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import extract
from sqlalchemy.orm import Session

from app.models.aviso_comunitario import AvisoComunitario, TipoAviso
from app.models.cliente import Cliente
from app.models.comercio import Comercio
from app.models.mascota import Mascota
from app.models.pieza_generada import (
    FormatoPieza,
    PiezaGenerada,
    ReferenciaPieza,
    TipoPieza,
)
from app.services.pieza_service import LEYENDA_KIT, LEYENDA_SOLIDARIO

# Titulo principal del cartel segun el tipo de aviso de la red comunitaria.
_TITULOS_AVISO = {
    TipoAviso.PERDIDA: "MASCOTA PERDIDA",
    TipoAviso.ENCONTRADA: "MASCOTA ENCONTRADA",
    TipoAviso.ADOPCION: "EN ADOPCIÓN",
    TipoAviso.CUMPLEANOS: "FELIZ CUMPLEAÑOS",
    TipoAviso.AVISO_BARRIAL: "AVISO SOLIDARIO",
}

# Beneficio por defecto si el comercio no configuro ninguno.
BENEFICIO_CUMPLEANOS_DEFAULT = "10% OFF en su baño de cumple"

NO_INFORMADO = "No informado"
ZONA_NO_CONFIRMADA = "Zona a confirmar"
CONTACTO_NO_CONFIRMADO = "Consultar en el comercio"


def _ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


def _fecha_hoy_texto() -> str:
    return date.today().strftime("%d/%m/%Y")


# --------------------------------------------------------------------------
# Aritmetica de cumpleanos
# --------------------------------------------------------------------------

def aniversario_en(fecha_nacimiento: date, anio: int) -> date:
    """Devuelve la fecha del aniversario de `fecha_nacimiento` para `anio`.

    Un cumpleanio nacido el 29 de febrero se celebra el 28 de febrero en los
    anios no bisiestos (convencion habitual en veterinarias y peluquerias).
    """
    try:
        return date(anio, fecha_nacimiento.month, fecha_nacimiento.day)
    except ValueError:
        return date(anio, 2, 28)


def proximo_aniversario(fecha_nacimiento: date, hoy: date) -> date:
    """Proximo aniversario a partir de `hoy`, incluyendo hoy mismo."""
    candidato = aniversario_en(fecha_nacimiento, hoy.year)
    if candidato < hoy:
        return aniversario_en(fecha_nacimiento, hoy.year + 1)
    return candidato


def anios_cumplidos(fecha_nacimiento: date, aniversario: date) -> int:
    """Edad que cumple en el aniversario (misma convencion 29-feb -> 28-feb)."""
    return aniversario.year - fecha_nacimiento.year


def edad_actual(fecha_nacimiento: date | None, hoy: date | None = None) -> int | None:
    """Edad en anios cumplidos a la fecha `hoy` (por defecto hoy local).

    Reutiliza la convencion de aniversarios del modulo de cumpleanos (29-feb ->
    28-feb), de modo que la edad mostrada y la que se festeja nunca se
    contradicen. Devuelve `None` si no hay fecha de nacimiento.
    """
    if fecha_nacimiento is None:
        return None
    hoy = hoy or date.today()
    if aniversario_en(fecha_nacimiento, hoy.year) <= hoy:
        return hoy.year - fecha_nacimiento.year
    return hoy.year - fecha_nacimiento.year - 1


def _dias_ventana(hoy: date, dias: int) -> list[date]:
    """Lista de fechas de la ventana [hoy, hoy + dias] inclusive."""
    return [hoy + timedelta(days=i) for i in range(dias + 1)]


# --------------------------------------------------------------------------
# Modulo solidario
# --------------------------------------------------------------------------

def _descripcion_por_defecto(tipo: TipoAviso) -> str:
    if tipo == TipoAviso.PERDIDA:
        return "Mascota perdida. Si la viste, avisanos por favor."
    if tipo == TipoAviso.ADOPCION:
        return "Mascota en busca de un hogar responsable."
    if tipo == TipoAviso.ENCONTRADA:
        return "Mascota encontrada. Comunicate para identificarla."
    return "Aviso de la red comunitaria de Servipet."


def datos_cartel_solidario(db: Session, aviso_id: int) -> dict:
    """Arma el contenido del cartel a partir de un `AvisoComunitario`.

    Fuente de datos de la foto: primero el `foto_url` de Cloudinary (no
    descargable en este scope, se ignora para el render) y despues el cliente
    relacionado, para aprovechar la `foto_webp` que el portal ya almacena.
    La resolucion de zona y telefono usa una cadena de fallbacks para que el
    cartel siempre tenga datos de contacto utiles.
    """
    aviso = db.query(AvisoComunitario).filter(AvisoComunitario.id == aviso_id).first()
    if not aviso:
        raise LookupError("Aviso no encontrado")

    comercio = db.query(Comercio).filter(Comercio.id == aviso.comercio_id).first()
    cliente = None
    mascota = None
    if aviso.cliente_id is not None:
        cliente = db.query(Cliente).filter(Cliente.id == aviso.cliente_id).first()
    if cliente is not None:
        mascota = (
            db.query(Mascota)
            .filter(Mascota.cliente_id == cliente.id, Mascota.activo == True)  # noqa: E712
            .order_by(Mascota.id.asc())
            .first()
        )

    # --- Zona / barrio: cliente -> comercio -> direccion -> placeholder ---
    zona = None
    if cliente is not None and cliente.zona_barrio:
        zona = cliente.zona_barrio
    elif comercio is not None and comercio.zona_barrio:
        zona = comercio.zona_barrio
    elif comercio is not None and comercio.direccion:
        zona = comercio.direccion
    zona = zona or ZONA_NO_CONFIRMADA

    # --- Telefono: contacto del aviso -> telefono del comercio ---
    telefono = None
    if aviso.telefono_contacto:
        telefono = aviso.telefono_contacto
    elif comercio is not None and comercio.telefono:
        telefono = comercio.telefono
    telefono = telefono or CONTACTO_NO_CONFIRMADO

    # --- Raza / color de la mascota ---
    raza_color = NO_INFORMADO
    if mascota is not None:
        partes = [p for p in (mascota.raza, mascota.color) if p]
        if partes:
            raza_color = " / ".join(partes)

    titulo = _TITULOS_AVISO.get(aviso.tipo, "AVISO SOLIDARIO")

    return {
        "titulo_principal": titulo,
        "subtitulo": aviso.titulo,
        "descripcion": aviso.descripcion or _descripcion_por_defecto(aviso.tipo),
        "mascota_nombre": mascota.nombre if mascota is not None else (aviso.titulo or "Mascota"),
        "mascota_raza_color": raza_color,
        "zona_barrio": zona,
        "telefono_contacto": telefono,
        "comercio_nombre": comercio.nombre if comercio is not None else "Servipet",
        "comercio_tipo": comercio.tipo_comercio if comercio is not None else None,
        "comercio_telefono": comercio.telefono if comercio is not None else None,
        "color_primario": comercio.color_primario if comercio is not None else None,
        "color_secundario": comercio.color_secundario if comercio is not None else None,
        "foto_webp": mascota.foto_webp if mascota is not None else None,
        "generado_en": _fecha_hoy_texto(),
        "leyenda": LEYENDA_SOLIDARIO,
    }


# --------------------------------------------------------------------------
# Fidelizacion cumpleaños (dato sensible, opt-in)
# --------------------------------------------------------------------------

def proximos_cumpleanos(
    db: Session,
    comercio_id: int,
    dias: int = 7,
    hoy: date | None = None,
) -> dict:
    """Lista los cumpleanos de los proximos `dias` dias (ventana inclusiva).

    FILTRO ESTRICTO e innegociable, aplicado en el propio ORM:

    - `Cliente.acepta_cumpleanos == True`  -> consentimiento explicito del
      titular, porque la fecha de nacimiento es un dato sensible.
    - `Mascota.activo == True`             -> la ficha esta vigente.
    - `Mascota.fallecida == False`          -> una mascota fallecida nunca se
      incluye, aunque su ficha siga activa.
    - `Mascota.fecha_nacimiento IS NOT NULL`.

    La ventana se resuelve en Python sobre el dia/mes del aniversario, y no
    con un rango de fechas SQL, para que el salto de fin de año funcione: el 28
    de diciembre un cumpleanos del 5 de enero esta a 8 dias, no a 364.
    """
    hoy = hoy or date.today()
    ventana = _dias_ventana(hoy, dias)
    limite = ventana[-1]

    meses = {f.month for f in ventana}
    dias_mes = {f.day for f in ventana}

    query = (
        db.query(Mascota)
        .join(Cliente, Cliente.id == Mascota.cliente_id)
        .filter(
            Cliente.comercio_id == comercio_id,
            Cliente.activo == True,  # noqa: E712
            Cliente.acepta_cumpleanos == True,  # noqa: E712
            Mascota.activo == True,  # noqa: E712
            Mascota.fallecida == False,  # noqa: E712
            Mascota.fecha_nacimiento.isnot(None),
        )
    )

    # Achicado en BD por mes/dia presentes en la ventana. `extract` se traduce
    # a strftime en SQLite y a EXTRACT en Postgres.
    try:
        query = query.filter(
            extract("month", Mascota.fecha_nacimiento).in_(meses),
            extract("day", Mascota.fecha_nacimiento).in_(dias_mes),
        )
    except Exception:
        # Dialectos sin soporte de extract (ej. Turso): el filtro de ventana
        # se aplica igual en Python sobre el conjunto completo.
        pass

    ya_enviados = {
        fila.referencia_id
        for fila in db.query(PiezaGenerada)
        .filter(
            PiezaGenerada.comercio_id == comercio_id,
            PiezaGenerada.tipo == TipoPieza.CUMPLEANOS,
            PiezaGenerada.formato == FormatoPieza.PNG_1X1,
            PiezaGenerada.anio == hoy.year,
        )
        .all()
    }

    items: list[dict[str, Any]] = []
    for mascota in query.all():
        proximo = proximo_aniversario(mascota.fecha_nacimiento, hoy)
        if proximo > limite:
            continue
        comercio = db.query(Comercio).filter(Comercio.id == comercio_id).first()
        beneficio = None
        if comercio is not None:
            beneficio = comercio.beneficio_cumpleanos
        cliente = mascota.cliente
        items.append(
            {
                "mascota_id": mascota.id,
                "cliente_id": mascota.cliente_id,
                "cliente_nombre": cliente.nombre if cliente is not None else "—",
                "cliente_telefono": cliente.telefono if cliente is not None else None,
                "nombre": mascota.nombre,
                "especie": mascota.especie,
                "raza": mascota.raza,
                "color": mascota.color,
                "fecha_nacimiento": mascota.fecha_nacimiento,
                "anios": anios_cumplidos(mascota.fecha_nacimiento, proximo),
                "dias_para": (proximo - hoy).days,
                "ya_enviado": mascota.id in ya_enviados,
                "beneficio": beneficio or BENEFICIO_CUMPLEANOS_DEFAULT,
                "comercio_nombre": comercio.nombre if comercio is not None else "Servipet",
                "foto_webp": mascota.foto_webp,
            }
        )

    items.sort(key=lambda i: (i["dias_para"], i["nombre"]))

    comercio = db.query(Comercio).filter(Comercio.id == comercio_id).first()
    beneficio_default = None
    if comercio is not None:
        beneficio_default = comercio.beneficio_cumpleanos or BENEFICIO_CUMPLEANOS_DEFAULT

    return {
        "dias": dias,
        "total": len(items),
        "beneficio_default": beneficio_default,
        "items": items,
    }


def datos_placa_cumpleanos(
    db: Session,
    mascota_id: int,
    beneficio_override: str | None = None,
) -> dict:
    """Arma la placa cuadrada 1:1 de cumpleanos de una mascota.

    Aplica el mismo filtro estricto que `proximos_cumpleanos`: si la mascota no
    esta activa, no esta viva, o su cliente no dio consentimiento, la funcion
    lanza LookupError y el router responde 404.
    """
    mascota = db.query(Mascota).filter(Mascota.id == mascota_id).first()
    if mascota is None:
        raise LookupError("Mascota no encontrada")

    cliente = db.query(Cliente).filter(Cliente.id == mascota.cliente_id).first()
    if cliente is None or not cliente.activo or not cliente.acepta_cumpleanos:
        raise LookupError("Mascota no encontrada")
    if not mascota.activo or mascota.fallecida:
        raise LookupError("Mascota no encontrada")

    comercio = db.query(Comercio).filter(Comercio.id == cliente.comercio_id).first()
    beneficio = beneficio_override
    if not beneficio and comercio is not None:
        beneficio = comercio.beneficio_cumpleanos
    beneficio = beneficio or BENEFICIO_CUMPLEANOS_DEFAULT

    hoy = date.today()
    proximo = proximo_aniversario(mascota.fecha_nacimiento, hoy) if mascota.fecha_nacimiento else None
    anios = anios_cumplidos(mascota.fecha_nacimiento, proximo) if proximo else None

    if proximo is not None and proximo == hoy:
        antiguedad = "¡Hoy es su cumpleaños!"
    elif proximo is not None:
        antiguedad = f"Cumple en {(proximo - hoy).days} dias"
    else:
        antiguedad = "Cumpleanos"

    titulo = f"FELIZ CUMPLEAÑOS, {mascota.nombre}"

    return {
        "titulo": titulo,
        "titulo_principal": titulo,
        "beneficio": beneficio,
        "subtitulo": antiguedad,
        "condiciones": f"Vigente el {proximo.strftime('%d/%m/%Y')}" if proximo else None,
        "mascota_nombre": mascota.nombre,
        "raza": mascota.raza,
        "color": mascota.color,
        "anios": anios,
        "mostrar_foto": bool(mascota.foto_webp),
        "foto_webp": mascota.foto_webp,
        "usar_branding": True,
        "comercio_nombre": comercio.nombre if comercio is not None else "Servipet",
        "color_primario": comercio.color_primario if comercio is not None else None,
        "color_secundario": comercio.color_secundario if comercio is not None else None,
        "generado_en": _fecha_hoy_texto(),
        "leyenda": LEYENDA_SOLIDARIO,
        "anio": hoy.year,
    }


# --------------------------------------------------------------------------
# Kit Marketing B2B
# --------------------------------------------------------------------------

def datos_promocion(datos: dict, comercio: Comercio | None) -> dict:
    """Arma la placa cuadrada 1:1 de una promocion rapida del kit B2B.

    `datos` es un `PromocionCreate` ya validado por Pydantic. El branding del
    comercio (nombre, logo, colores) se aplica salvo que el comercio pida lo
    contrario con `usar_branding=False`.
    """
    usar_branding = bool(datos.get("usar_branding", True)) and comercio is not None

    # Los colores del request pisan los del branding del comercio, asi el
    # comercio puede hacer una campana con su propia paleta puntual. Sin
    # branding solo aplican si el request los trae explicitos.
    color_primario = datos.get("color_primario")
    color_secundario = datos.get("color_secundario")
    if usar_branding and comercio is not None:
        color_primario = color_primario or comercio.color_primario
        color_secundario = color_secundario or comercio.color_secundario

    return {
        "titulo": datos.get("titulo", ""),
        "titulo_principal": datos.get("titulo", ""),
        "beneficio": datos.get("beneficio_texto") or datos.get("descuento") or "",
        "descuento": datos.get("descuento"),
        "condiciones": datos.get("condiciones"),
        "subtitulo": "",
        "mostrar_foto": False,
        "foto_webp": None,
        "usar_branding": usar_branding,
        "comercio_nombre": comercio.nombre if (usar_branding and comercio) else None,
        "color_primario": color_primario,
        "color_secundario": color_secundario,
        "generado_en": _fecha_hoy_texto(),
        "leyenda": LEYENDA_KIT,
    }


def nombre_archivo_promocion(titulo: str) -> str:
    """Normaliza un titulo a un slug ASCII seguro para `Content-Disposition`.

    Las cabeceras HTTP viajan en latin-1, asi que un slug con acentos o simbolos
    (ej. "baño") romperia la respuesta. Se descomponen los caracteres Unicode
    para eliminar los diacriticos y se descarta todo lo que no sea alfanumerico
    ASCII.
    """
    import unicodedata

    descompuesto = unicodedata.normalize("NFKD", str(titulo or ""))
    sin_acentos = "".join(c for c in descompuesto if not unicodedata.combining(c))
    limpio = "".join(c if c.isascii() and c.isalnum() else "-" for c in sin_acentos.lower())
    limpio = "-".join(p for p in limpio.split("-") if p)
    return (limpio[:40] or "promo") + ".png"


# --------------------------------------------------------------------------
# Auditoria y anti-duplicado
# --------------------------------------------------------------------------

def ya_registrado(
    db: Session,
    comercio_id: int,
    tipo: TipoPieza,
    formato: FormatoPieza,
    referencia_id: int,
    anio: int | None,
) -> bool:
    """True si ya se genero esa pieza para esa referencia en ese anio."""
    if referencia_id is None:
        return False
    return (
        db.query(PiezaGenerada)
        .filter(
            PiezaGenerada.comercio_id == comercio_id,
            PiezaGenerada.tipo == tipo,
            PiezaGenerada.formato == formato,
            PiezaGenerada.referencia_id == referencia_id,
            PiezaGenerada.anio == anio,
        )
        .first()
        is not None
    )


def registrar_pieza(
    db: Session,
    *,
    comercio_id: int,
    tipo: TipoPieza,
    formato: FormatoPieza,
    referencia_tipo: ReferenciaPieza | None,
    referencia_id: int | None,
    anio: int | None,
    nombre_archivo: str,
    beneficio: str | None = None,
    usuario_id: int | None = None,
) -> PiezaGenerada:
    """Persiste la auditoria de una pieza generada y devuelve la fila.

    `PiezasGeneradas` tiene una restriccion de unicidad por
    (comercio, tipo, formato, referencia, anio), asi que esta operacion es un
    upsert: si la pieza ya estaba registrada (por ejemplo cuando el endpoint se
    llama con `forzar=1`) se actualizan los campos en lugar de insertar un
    duplicado que violaria el indice.
    """
    beneficio_txt = (beneficio or "").strip()
    if len(beneficio_txt) > 200:
        beneficio_txt = beneficio_txt[:200]

    existente = None
    if referencia_id is not None:
        existente = (
            db.query(PiezaGenerada)
            .filter(
                PiezaGenerada.comercio_id == comercio_id,
                PiezaGenerada.tipo == tipo,
                PiezaGenerada.formato == formato,
                PiezaGenerada.referencia_id == referencia_id,
                PiezaGenerada.anio == anio,
            )
            .first()
        )

    if existente is not None:
        existente.referencia_tipo = referencia_tipo
        existente.beneficio = beneficio_txt or None
        existente.nombre_archivo = nombre_archivo[:120]
        existente.creado_por_usuario_id = usuario_id
        existente.creado_at = _ahora_utc()
        db.commit()
        db.refresh(existente)
        return existente

    pieza = PiezaGenerada(
        comercio_id=comercio_id,
        tipo=tipo,
        formato=formato,
        referencia_tipo=referencia_tipo,
        referencia_id=referencia_id,
        anio=anio,
        beneficio=beneficio_txt or None,
        nombre_archivo=nombre_archivo[:120],
        creado_por_usuario_id=usuario_id,
        creado_at=_ahora_utc(),
    )
    db.add(pieza)
    db.commit()
    db.refresh(pieza)
    return pieza
