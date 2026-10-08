"""Renderers de piezas visuales del modulo de Marketing B2B (Etapa 12).

Este modulo es una capa PUREA de presentacion: recibe `data: dict` y devuelve
`bytes`. No toca la base de datos, no importa FastAPI y no conoce el modelo
ORM. Toda la obtencion de datos vive en `app.services.marketing_service`.

Tres formatos generados:

- `pdf_cartel_solidario`  -> PDF A4 vertical (210x297 mm) via fpdf2.
- `png_placa_vertical`    -> placa digital 9:16 (1080x1920 px) via Pillow.
- `png_placa_cuadrada`    -> placa cuadrada 1:1 (1080x1080 px) via Pillow.

Decisiones tecnicas relevantes:

1. Motor PDF = fpdf2 (mismo stack que `app.services.report_service`). Se evita
   ReportLab/WeasyPrint: no son dependencias del proyecto y WeasyPrint requiere
   GTK/Pango nativos que no existen en el entorno de pruebas.
2. Las fuentes core de fpdf2 (helvetica) codifican con `latin-1`: los acentos
   ("Módulo", "Adopción") se imprimen sin problema, pero los caracteres
   tipograficos (em dash, comillas curvas) y los emojis (U+1F43E huella) estan
   fuera de rango y fpdf2 lanza `FPDFUnicodeEncodingException`. Por eso:
   a) la huella de la leyenda se dibuja como forma vectorial (`_huella_pdf`) en
      lugar de imprimirse como texto, y
   b) todo el texto pasa por `_pdf_seguro`, que traduce caracteres tipograficos
      a ASCII y descarta el resto fuera de latin-1.
3. Pillow se importa de forma perezosa dentro de las funciones, igual que `fpdf`
   en report_service, para que importar este modulo nunca falle aunque falte
   la libreria.
"""

from typing import Any

# Leyenda institucional commun a las piezas solidarias. El emoji huella se
# dibuja vectorialmente; esta constante es solo la parte textual.
LEYENDA_SOLIDARIO = "Generado con el Módulo Solidario de Servipet"
LEYENDA_KIT = "Generado con el Kit de Marketing de Servipet"

# Paletas de respaldo cuando el comercio no define color valido.
COLOR_PRIMARIO_DEFAULT = "#1E40AF"
COLOR_SECUNDARIO_DEFAULT = "#0D9488"

# Tamano de las piezas, en pixeles.
ANCHO_CUADRADO = 1080
ALTO_CUADRADO = 1080
ANCHO_VERTICAL = 1080
ALTO_VERTICAL = 1920

# Dimensiones de la foto dentro de la placa cuadrada 1:1.
FOTO_CUADRADO = 560


# --------------------------------------------------------------------------
# Helpers de color
# --------------------------------------------------------------------------

def _hex_a_rgb(valor: str | None, defecto: str) -> tuple[int, int, int]:
    """Convierte '#RRGGBB' a tupla RGB, con fallback seguro ante hex invalido."""
    if not valor or not isinstance(valor, str):
        valor = defecto
    limpio = valor.strip().lstrip("#")
    if len(limpio) == 3:
        limpio = "".join(c * 2 for c in limpio)
    try:
        if len(limpio) != 6:
            raise ValueError
        return (int(limpio[0:2], 16), int(limpio[2:4], 16), int(limpio[4:6], 16))
    except (ValueError, TypeError):
        limpio = defecto.lstrip("#")
        return (int(limpio[0:2], 16), int(limpio[2:4], 16), int(limpio[4:6], 16))


def _contraste(primario: tuple[int, int, int]) -> tuple[int, int, int]:
    """Devuelve blanco o negro segun la luminancia del fondo (WCAG)."""
    r, g, b = primario
    luminancia = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
    return (0, 0, 0) if luminancia > 0.6 else (255, 255, 255)


def _aclarar(rgb: tuple[int, int, int], factor: float = 0.55) -> tuple[int, int, int]:
    """Aclara un color mezclandolo con blanco (para fondos suaves)."""
    factor = max(0.0, min(1.0, factor))
    return tuple(int(c + (255 - c) * factor) for c in rgb)  # type: ignore[return-value]


def _oscurecer(rgb: tuple[int, int, int], factor: float = 0.3) -> tuple[int, int, int]:
    """Oscurece un color multiplicando cada canal por (1-factor)."""
    factor = max(0.0, min(1.0, factor))
    return tuple(int(c * (1 - factor)) for c in rgb)  # type: ignore[return-value]


# --------------------------------------------------------------------------
# Helpers de texto (Pillow)
# --------------------------------------------------------------------------

def _envolver_texto(texto: str, font, ancho_max: int, draw) -> list[str]:
    """Parte un texto en lineas que caben en `ancho_max` pixeles.

    Usa `draw.textlength` (arbol de medidas de Pillow) en vez de estimar el
    ancho por numero de caracteres, para que el ajuste sea exacto con la fuente
    realmente cargada.
    """
    palabras = str(texto or "").split()
    if not palabras:
        return []
    lineas: list[str] = []
    actual = palabras[0]
    for palabra in palabras[1:]:
        tentativa = f"{actual} {palabra}"
        if draw.textlength(tentativa, font=font) <= ancho_max:
            actual = tentativa
        else:
            lineas.append(actual)
            actual = palabra
    lineas.append(actual)
    return lineas


def _fuente(size: int, bold: bool = False):
    """Resuelve una fuente TrueType con cascada de respaldo portable.

    Orden: `SERVIPET_FUENTE_PATH` (TTF del despliegue, si se configuro) ->
    fuentes del sistema comunes -> `ImageFont.load_default(size=...)`, que en
    Pillow moderno ya devuelve una FreeTypeFont basica pero utilizable. Asi el
    render nunca depende de una fuente concreta del sistema operativo.
    """
    from PIL import ImageFont

    intentos: list[str] = []
    try:
        from app.config import settings

        if settings.SERVIPET_FUENTE_PATH:
            intentos.append(settings.SERVIPET_FUENTE_PATH)
    except Exception:  # pragma: no cover - la config no debe romper el render
        pass
    if bold:
        intentos += [
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
    intentos += [
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for ruta in intentos:
        try:
            return ImageFont.truetype(ruta, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default(size=size)


# --------------------------------------------------------------------------
# Huella vectorial (Pillow)
# --------------------------------------------------------------------------

def _dibujar_huella(draw, cx: float, cy: float, lado: float, color) -> None:
    """Dibuja una huella de pata centrada en (cx, cy) con `lado` de extent.

    Construye la forma clasica: un cojinete ovalado inferior y cuatro dedos
    ovalados mas pequenos en un arco sobre el. Todo con primitivas de Pillow,
    sin depender de ningun asset ni de una fuente de emoji.
    """
    s = lado
    # Cojinete (base de la huella): ovalo ancho y bajo.
    pad_w = s * 0.78
    pad_h = s * 0.62
    draw.ellipse(
        [cx - pad_w / 2, cy - pad_h / 2 + s * 0.12, cx + pad_w / 2, cy + pad_h / 2 + s * 0.12],
        fill=color,
    )
    # Cuatro dedos en arco: dos interiores mas grandes, dos exteriores algo menores.
    ancho_dedo = s * 0.24
    alto_dedo = s * 0.32
    dedos = [
        (-0.30, -0.26, 1.0),
        (-0.10, -0.40, 1.12),
        (0.12, -0.40, 1.12),
        (0.32, -0.24, 1.0),
    ]
    for fx, fy, escala in dedos:
        w = ancho_dedo * escala
        h = alto_dedo * escala
        x = cx + fx * s
        y = cy + fy * s
        draw.ellipse([x - w / 2, y - h / 2, x + w / 2, y + h / 2], fill=color)


# --------------------------------------------------------------------------
# Huella vectorial (fpdf2)
# --------------------------------------------------------------------------

def _huella_pdf(pdf, cx: float, cy: float, lado: float, rgb: tuple[int, int, int]) -> None:
    """Dibuja la huella vectorial en un PDF fpdf2.

    fpdf2 trabaja en milimetros y helvetica no puede codificar el emoji U+1F43E,
    asi que la huella del pie de leyenda se compone con `ellipse(..., style='F')`
    replicando la misma geometria que la version Pillow.
    """
    pdf.set_fill_color(*rgb)
    s = lado
    pad_w = s * 0.78
    pad_h = s * 0.62
    pdf.ellipse(
        cx - pad_w / 2,
        cy - pad_h / 2 + s * 0.12,
        pad_w,
        pad_h,
        style="F",
    )
    ancho_dedo = s * 0.24
    alto_dedo = s * 0.32
    dedos = [
        (-0.30, -0.26, 1.0),
        (-0.10, -0.40, 1.12),
        (0.12, -0.40, 1.12),
        (0.32, -0.24, 1.0),
    ]
    for fx, fy, escala in dedos:
        w = ancho_dedo * escala
        h = alto_dedo * escala
        pdf.ellipse(cx + fx * s - w / 2, cy + fy * s - h / 2, w, h, style="F")


# --------------------------------------------------------------------------
# Carga de imagenes (webp base64)
# --------------------------------------------------------------------------

def _webp_base64_a_png(base64_webp: str | None):
    """Convierte un webp base64 (sin prefijo data:) en una imagen RGB de Pillow.

    Las fotos del sistema se guardan como base64 de webp (generado en el
    navegador). Si el dato viene mal, vacio o en un formato no soportado,
    devuelve `None` para que el renderer caiga a un placeholder en vez de
    reventar la generacion de la pieza.
    """
    if not base64_webp:
        return None
    try:
        import base64
        import io

        from PIL import Image

        crudo = base64_webp.strip()
        # Tolera que venga con el prefijo data URL.
        if crudo.startswith("data:"):
            _, _, crudo = crudo.partition(",")
        datos = base64.b64decode(crudo, validate=True)
        img = Image.open(io.BytesIO(datos))
        img.load()
        return img.convert("RGB")
    except Exception:
        return None


def _encajar(imagen, ancho: int, alto: int):
    """Escala una imagen a (ancho, alto) cubriendo el lienzo y recortando el excedente.

    Mantiene la proporcion y recorta desde el centro, para que la foto de la
    mascota llene la placa sin deformarse.
    """
    from PIL import Image

    if imagen is None:
        return None
    objetivo_ratio = ancho / alto
    ratio = imagen.width / imagen.height
    if ratio > objetivo_ratio:
        # imagen mas ancha: se recorta por los lados
        nuevo_ancho = int(imagen.height * objetivo_ratio)
        izquierda = (imagen.width - nuevo_ancho) // 2
        caja = (izquierda, 0, izquierda + nuevo_ancho, imagen.height)
    else:
        # imagen mas alta: se recorta arriba/abajo
        nuevo_alto = int(imagen.width / objetivo_ratio)
        arriba = (imagen.height - nuevo_alto) // 2
        caja = (0, arriba, imagen.width, arriba + nuevo_alto)
    recortada = imagen.crop(caja)
    return recortada.resize((ancho, alto), Image.LANCZOS)


# --------------------------------------------------------------------------
# PDF A4 vertical (cartel solidario)
# --------------------------------------------------------------------------

def pdf_cartel_solidario(data: dict) -> bytes:
    """Genera el PDF A4 vertical (210x297 mm) del cartel de mascota perdida /
    adopcion / encontrada.

    Maquetacion: banda de color del comercio, foto de la mascota cuadrada,
    titulo grande, bloque de datos (raza/color, zona, telefono), y pie con la
    leyenda institutional y la huella vectorial.

    Todo el texto usa helvetica core (latin-1), que soporta los acentos del
    castellano. La huella del pie es vectorial, no texto.
    """
    from fpdf import FPDF

    ANCHO, ALTO = 210.0, 297.0
    MARGEN = 15.0
    util = ANCHO - 2 * MARGEN

    primario = _hex_a_rgb(data.get("color_primario"), COLOR_PRIMARIO_DEFAULT)
    secundario = _hex_a_rgb(data.get("color_secundario"), COLOR_SECUNDARIO_DEFAULT)
    texto_sobre_primario = _contraste(primario)

    pdf = FPDF(format="A4", orientation="P")
    pdf.set_title(str(data.get("titulo_principal") or "Cartel Solidario"))
    pdf.set_auto_page_break(auto=False)
    pdf.set_margins(MARGEN, MARGEN, MARGEN)
    pdf.add_page()

    # --- Cabecera a sangre ---
    pdf.set_fill_color(*primario)
    pdf.rect(0, 0, ANCHO, 42, style="F")
    pdf.set_text_color(*texto_sobre_primario)
    pdf.set_font("helvetica", "B", 16)
    pdf.set_xy(MARGEN, 12)
    pdf.cell(util, 9, _pdf_seguro(data.get("comercio_nombre", "Servipet"))[:30])
    pdf.set_font("helvetica", "", 10)
    tipo = data.get("comercio_tipo")
    if tipo:
        pdf.set_xy(MARGEN, 23)
        pdf.cell(util, 5, f"Comercio: {_pdf_seguro(tipo)}"[:40])
    telefono_com = data.get("comercio_telefono")
    if telefono_com:
        pdf.set_xy(MARGEN, 29)
        pdf.cell(util, 5, f"Tel: {_pdf_seguro(telefono_com)}"[:40])

    # --- Titulo principal ---
    pdf.set_text_color(*_oscurecer(primario, 0.15))
    pdf.set_font("helvetica", "B", 30)
    pdf.set_xy(MARGEN, 50)
    titulo = _pdf_seguro(data.get("titulo_principal", "MASCOTA PERDIDA"))
    pdf.multi_cell(util, 12, titulo, align="C")

    pdf.set_font("helvetica", "", 12)
    pdf.set_text_color(70, 70, 80)
    subtitulo = data.get("subtitulo")
    if subtitulo:
        pdf.set_xy(MARGEN, 66)
        pdf.multi_cell(util, 6, _pdf_seguro(subtitulo)[:90], align="C")

    # --- Foto de la mascota ---
    y_foto = 82.0
    lado_foto = 95.0
    x_foto = (ANCHO - lado_foto) / 2
    foto = _webp_base64_a_png(data.get("foto_webp"))
    if foto is not None:
        import io


        recortada = _encajar(foto, 720, 720)
        buf = io.BytesIO()
        recortada.save(buf, format="PNG")
        buf.seek(0)
        pdf.image(buf, x=x_foto, y=y_foto, w=lado_foto, h=lado_foto)
        pdf.set_draw_color(*primario)
        pdf.set_line_width(1.0)
        pdf.rect(x_foto, y_foto, lado_foto, lado_foto, style="D")
    else:
        # Placeholder cuando la mascota no tiene foto.
        pdf.set_fill_color(*_aclarar(primario, 0.82))
        pdf.rect(x_foto, y_foto, lado_foto, lado_foto, style="F")
        _huella_pdf(pdf, ANCHO / 2, y_foto + lado_foto / 2, 34, secundario)
        pdf.set_font("helvetica", "I", 10)
        pdf.set_text_color(120, 120, 130)
        pdf.set_xy(x_foto, y_foto + lado_foto / 2 + 22)
        pdf.cell(lado_foto, 6, "Sin foto", align="C")

    # --- Bloque de datos ---
    y = y_foto + lado_foto + 12
    pdf.set_font("helvetica", "B", 13)
    pdf.set_text_color(*_oscurecer(primario, 0.15))
    nombre = _pdf_seguro(data.get("mascota_nombre", ""))
    pdf.set_xy(MARGEN, y)
    pdf.cell(util, 8, nombre[:40], align="C")
    y += 11

    pdf.set_font("helvetica", "", 11)
    pdf.set_text_color(60, 60, 70)
    filas = [
        ("Raza / Color", data.get("mascota_raza_color")),
        ("Zona / Barrio", data.get("zona_barrio")),
        ("Contacto", data.get("telefono_contacto")),
    ]
    for etiqueta, valor in filas:
        if not valor:
            continue
        pdf.set_font("helvetica", "B", 10)
        pdf.set_xy(MARGEN, y)
        pdf.cell(40, 6, etiqueta)
        pdf.set_font("helvetica", "", 10)
        pdf.set_xy(MARGEN + 42, y)
        pdf.cell(util - 42, 6, _pdf_seguro(valor)[:48])
        y += 7

    # --- Descripcion libre ---
    descripcion = data.get("descripcion")
    if descripcion:
        y += 4
        pdf.set_font("helvetica", "I", 10)
        pdf.set_text_color(90, 90, 100)
        pdf.set_xy(MARGEN, y)
        pdf.multi_cell(util, 5, _pdf_seguro(descripcion)[:220])

    # --- Pie institucional con huella vectorial ---
    y_pie = ALTO - 32
    pdf.set_draw_color(*_aclarar(primario, 0.5))
    pdf.set_line_width(0.3)
    pdf.line(MARGEN, y_pie - 6, ANCHO - MARGEN, y_pie - 6)
    _huella_pdf(pdf, ANCHO / 2 - 30, y_pie + 6, 9, secundario)
    pdf.set_font("helvetica", "B", 9)
    pdf.set_text_color(*_oscurecer(primario, 0.1))
    pdf.set_xy(ANCHO / 2 - 22, y_pie + 2)
    pdf.multi_cell(util - 44, 5, LEYENDA_SOLIDARIO, align="C")
    generado = data.get("generado_en")
    if generado:
        pdf.set_font("helvetica", "", 8)
        pdf.set_text_color(120, 120, 130)
        pdf.set_xy(ANCHO / 2 - 22, y_pie + 14)
        pdf.cell(util - 44, 5, f"Emitido: {generado}"[:40], align="C")

    return bytes(pdf.output())


def _pdf_seguro(texto: Any) -> str:
    """Sanitiza texto destinado a las fuentes core de fpdf2.

    fpdf2 codifica el texto de las fuentes core con `latin-1` (NO cp1252), asi
    que los acentos del castellano (`á é í ó ú ñ ü`) se imprimen bien pero los
    caracteres tipograficos (em dash, comillas curvas, el signo euro) y los
    emojis quedan fuera de rango y abortan la generacion con
    `FPDFUnicodeEncodingException`.

    Este helper traduce los caracteres tipograficos mas comunes a su equivalente
    ASCII y luego descarta cualquier resto fuera de latin-1, de modo que el PDF
    nunca pueda fallar por el contenido de los datos del usuario.
    """
    if texto is None:
        return ""
    original = str(texto)
    for origen, destino in _SUSTITUCIONES_PDF.items():
        original = original.replace(origen, destino)
    return original.encode("latin-1", errors="replace").decode("latin-1")


# Caracteres tipograficos fuera de latin-1 traducidos a su equivalente ASCII.
_SUSTITUCIONES_PDF = {
    "—": "-",   # em dash
    "–": "-",   # en dash
    "“": '"',   # comilla izquierda
    "”": '"',   # comilla derecha
    "‘": "'",   # comilla simple izquierda
    "’": "'",   # comilla simple derecha
    "…": "...",  # elipsis
    "€": "EUR",
    "→": ">",
    "•": "-",
    "·": "-",
}


# --------------------------------------------------------------------------
# PNG 9:16 (placa vertical digital)
# --------------------------------------------------------------------------

def png_placa_vertical(data: dict) -> bytes:
    """Genera la placa digital vertical 9:16 (1080x1920 px) del cartel solidario.

    Es la version para redes / pantallas verticales: foto grande arriba, datos
    clave al centro y branding + leyenda abajo. Devuelve bytes PNG en memoria.
    """
    from PIL import Image, ImageDraw

    ancho, alto = ANCHO_VERTICAL, ALTO_VERTICAL
    primario = _hex_a_rgb(data.get("color_primario"), COLOR_PRIMARIO_DEFAULT)
    secundario = _hex_a_rgb(data.get("color_secundario"), COLOR_SECUNDARIO_DEFAULT)
    texto_sobre_primario = _contraste(primario)
    sobre_primario = _aclarar(primario, 0.86)

    lienzo = Image.new("RGB", (ancho, alto), sobre_primario)
    draw = ImageDraw.Draw(lienzo)

    # --- Franja superior de color con el titulo ---
    alto_franja = 300
    draw.rectangle([0, 0, ancho, alto_franja], fill=primario)
    f_titulo = _fuente(72, bold=True)
    f_sub = _fuente(34)
    titulo = str(data.get("titulo_principal", "MASCOTA PERDIDA"))
    lineas_titulo = _envolver_texto(titulo, f_titulo, ancho - 120, draw)[:2]
    y = 90 if len(lineas_titulo) > 1 else 120
    for linea in lineas_titulo:
        w = draw.textlength(linea, font=f_titulo)
        draw.text(((ancho - w) / 2, y), linea, font=f_titulo, fill=texto_sobre_primario)
        y += 88
    nombre = str(data.get("mascota_nombre", ""))
    if nombre:
        w = draw.textlength(nombre[:30], font=f_sub)
        draw.text(
            ((ancho - w) / 2, y + 6),
            nombre[:30],
            font=f_sub,
            fill=texto_sobre_primario,
        )

    # --- Foto cuadrada centrada ---
    lado = 720
    x_foto = (ancho - lado) // 2
    y_foto = alto_franja + 60
    foto = _webp_base64_a_png(data.get("foto_webp"))
    if foto is not None:
        recortada = _encajar(foto, lado, lado)
        lienzo.paste(recortada, (x_foto, y_foto))
        draw.rectangle([x_foto, y_foto, x_foto + lado, y_foto + lado], outline=primario, width=8)
    else:
        draw.rounded_rectangle(
            [x_foto, y_foto, x_foto + lado, y_foto + lado],
            radius=24,
            fill=_aclarar(primario, 0.55),
        )
        _dibujar_huella(draw, ancho / 2, y_foto + lado / 2, 150, texto_sobre_primario)

    # --- Datos clave ---
    y = y_foto + lado + 70
    f_dato_valor = _fuente(40)
    filas = [
        ("Raza / Color", data.get("mascota_raza_color")),
        ("Zona / Barrio", data.get("zona_barrio")),
        ("Contacto", data.get("telefono_contacto")),
    ]
    for etiqueta, valor in filas:
        if not valor:
            continue
        draw.text((60, y), etiqueta.upper(), font=_fuente(28), fill=secundario)
        draw.text((60, y + 40), str(valor)[:34], font=f_dato_valor, fill=(30, 30, 40))
        y += 110

    # --- Pie: huella + leyenda ---
    y_pie = alto - 150
    draw.rectangle([0, y_pie - 20, ancho, alto], fill=primario)
    _dibujar_huella(draw, ancho / 2, y_pie + 45, 60, texto_sobre_primario)
    f_leyenda = _fuente(34, bold=True)
    w = draw.textlength(LEYENDA_SOLIDARIO, font=f_leyenda)
    draw.text(
        ((ancho - w) / 2, y_pie + 95),
        LEYENDA_SOLIDARIO,
        font=f_leyenda,
        fill=texto_sobre_primario,
    )
    generado = data.get("generado_en")
    if generado:
        f_gen = _fuente(26)
        w = draw.textlength(f"Emitido: {generado}", font=f_gen)
        draw.text(
            ((ancho - w) / 2, y_pie + 140 - 12),
            f"Emitido: {generado}",
            font=f_gen,
            fill=texto_sobre_primario,
        )

    import io

    buf = io.BytesIO()
    lienzo.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# --------------------------------------------------------------------------
# PNG 1:1 (placa cuadrada - cumpleanos y kit B2B)
# --------------------------------------------------------------------------

def png_placa_cuadrada(data: dict) -> bytes:
    """Genera una placa cuadrada 1:1 (1080x1080 px) usada tanto para el
    cumpleanos de la mascota como para las promos del kit B2B.

    Layout: fondo de color del comercio, bloque de titulo arriba, beneficio
    destacado en el centro y branding del comercio abajo. Sin foto (o con foto
    pequena a la izquierda) segun `mostrar_foto`.
    """
    from PIL import Image, ImageDraw

    lado = ANCHO_CUADRADO
    usar_branding = data.get("usar_branding", True)
    if usar_branding:
        primario = _hex_a_rgb(data.get("color_primario"), COLOR_PRIMARIO_DEFAULT)
    else:
        primario = _hex_a_rgb(None, COLOR_PRIMARIO_DEFAULT)
    texto_sobre_primario = _contraste(primario)
    texto_oscuro = (25, 25, 35)

    fondo = _aclarar(primario, 0.9) if not usar_branding else _aclarar(primario, 0.75)
    lienzo = Image.new("RGB", (lado, lado), fondo)
    draw = ImageDraw.Draw(lienzo)

    mostrar_foto = bool(data.get("mostrar_foto")) and bool(data.get("foto_webp"))
    titulo = str(data.get("titulo", data.get("titulo_principal", "")))
    beneficio = str(data.get("beneficio", ""))
    subtitulo = str(data.get("subtitulo", ""))
    condiciones = str(data.get("condiciones", ""))

    # --- Marco de color ---
    draw.rectangle([0, 0, lado - 1, 150], fill=primario)
    draw.rectangle([0, lado - 130, lado - 1, lado - 1], fill=primario)

    # --- Titulo ---
    f_titulo = _fuente(66, bold=True)
    f_beneficio = _fuente(84, bold=True)
    f_sub = _fuente(36)
    f_condicion = _fuente(30)

    y = 40
    for linea in _envolver_texto(titulo, f_titulo, lado - 120, draw)[:2]:
        w = draw.textlength(linea, font=f_titulo)
        draw.text(((lado - w) / 2, y), linea, font=f_titulo, fill=texto_sobre_primario)
        y += 76

    # --- Zona central: beneficio o foto ---
    y_cuerpo = 200
    if mostrar_foto:
        lado_foto = FOTO_CUADRADO
        x_foto = (lado - lado_foto) // 2
        foto = _webp_base64_a_png(data.get("foto_webp"))
        recortada = _encajar(foto, lado_foto, lado_foto)
        if recortada is not None:
            # Redondeo de esquinas del recorte de foto.
            mask = Image.new("L", (lado_foto, lado_foto), 0)
            from PIL import ImageDraw as _ID

            _ID.Draw(mask).rounded_rectangle([0, 0, lado_foto, lado_foto], radius=32, fill=255)
            lienzo.paste(recortada, (x_foto, y_cuerpo), mask)
            y_texto = y_cuerpo + lado_foto + 30
        else:
            # Foto corrupta o no decodificable: se omite el recorte y el
            # texto arranca en la zona central (nunca `paste(None)`).
            y_texto = y_cuerpo
    else:
        y_texto = y_cuerpo

    # --- Beneficio destacado ---
    # `y_ben` se inicializa siempre: las secciones de subtitulo y condiciones
    # se posicionan respecto de el aunque no haya beneficio.
    y_ben = y_texto
    if beneficio:
        lineas_ben = _envolver_texto(beneficio, f_beneficio, lado - 100, draw)[:3]
        for linea in lineas_ben:
            w = draw.textlength(linea, font=f_beneficio)
            draw.text(((lado - w) / 2, y_ben), linea, font=f_beneficio, fill=primario)
            y_ben += 96

    # --- Subtitulo / condiciones ---
    if subtitulo:
        for linea in _envolver_texto(subtitulo, f_sub, lado - 100, draw)[:2]:
            w = draw.textlength(linea, font=f_sub)
            draw.text(((lado - w) / 2, y_ben + 10), linea, font=f_sub, fill=texto_oscuro)
            y_ben += 48

    if condiciones:
        for linea in _envolver_texto(f"Condiciones: {condiciones}", f_condicion, lado - 100, draw)[:2]:
            w = draw.textlength(linea, font=f_condicion)
            draw.text(
                ((lado - w) / 2, min(y_ben + 16, lado - 250)),
                linea,
                font=f_condicion,
                fill=(90, 90, 100),
            )
            y_ben += 42

    # --- Branding inferior + huella + leyenda ---
    y_pie = lado - 118
    comercio = str(data.get("comercio_nombre", ""))
    if comercio:
        f_com = _fuente(34, bold=True)
        w = draw.textlength(comercio[:40], font=f_com)
        draw.text(((lado - w) / 2, y_pie + 8), comercio[:40], font=f_com, fill=texto_sobre_primario)

    leyenda = str(data.get("leyenda") or LEYENDA_SOLIDARIO)
    f_leyenda = _fuente(24)
    w = draw.textlength(leyenda, font=f_leyenda)
    draw.text(((lado - w) / 2, y_pie + 60), leyenda, font=f_leyenda, fill=texto_sobre_primario)
    _dibujar_huella(draw, lado / 2, y_pie - 32, 52, texto_sobre_primario)

    import io

    buf = io.BytesIO()
    lienzo.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
