"""Catálogo de presets de apariencia (skins) y motor WCAG 2.1 de Servipet.

Cada preset define colores en formato HEX estricto (#RRGGBB) que alimentan
las Custom Properties CSS (--color-primario / --color-secundario) inyectadas
en los templates base via context processor. El motor WCAG calcula la
luminancia relativa de cada color para derivar el color de texto accesible
(--texto-sobre-primario / --texto-sobre-secundario) garantizando ratio >= 4.5:1.
"""

import re
from typing import Any

HEX_COLOR_PATTERN = r"^#[0-9A-Fa-f]{6}$"
_HEX_COLOR_RE = re.compile(HEX_COLOR_PATTERN)

PRESET_DEFAULT = "clasico_paws"

BLANCO = "#FFFFFF"
NEGRO = "#000000"

RATIO_MINIMO_TEXTO = 4.5

A11Y_MODO_DEFAULT = "normal"
A11Y_MODOS = ("normal", "alto_contraste", "daltonismo")

SKINS_PRESETS: dict[str, dict[str, str]] = {
    "clasico_paws": {"color_primario": "#1E40AF", "color_secundario": "#0D9488"},
    "menta_vet": {"color_primario": "#059669", "color_secundario": "#10B981"},
    "warm_pet": {"color_primario": "#D97706", "color_secundario": "#E11D48"},
    "dark_mode": {"color_primario": "#374151", "color_secundario": "#4B5563"},
}


def es_hex_valido(valor: object) -> bool:
    """True si valor es un color HEX estricto de 7 caracteres (#RRGGBB)."""
    return isinstance(valor, str) and _HEX_COLOR_RE.match(valor) is not None


def _hex_a_rgb(valor: object) -> tuple[int, int, int]:
    """Convierte #RRGGBB a tupla (r, g, b). ValueError si el formato es inválido."""
    if not es_hex_valido(valor):
        raise ValueError(f"Color HEX invalido: {valor!r}. Se espera formato #RRGGBB.")
    return (int(valor[1:3], 16), int(valor[3:5], 16), int(valor[5:7], 16))


def _canal_lineal(canal_srgb: float) -> float:
    """Expande un canal sRGB [0, 1] a su valor lineal según WCAG 2.1."""
    if canal_srgb <= 0.03928:
        return canal_srgb / 12.92
    return ((canal_srgb + 0.055) / 1.055) ** 2.4


def luminancia_relativa(hex_color: str) -> float:
    """Luminancia relativa WCAG 2.1: L = 0.2126R + 0.7152G + 0.0722B.

    Devuelve un valor en [0.0, 1.0]; 0.0 para negro puro y 1.0 para blanco.
    Lanza ValueError si el color no respeta el formato #RRGGBB.
    """
    r, g, b = _hex_a_rgb(hex_color)
    return (
        0.2126 * _canal_lineal(r / 255)
        + 0.7152 * _canal_lineal(g / 255)
        + 0.0722 * _canal_lineal(b / 255)
    )


def ratio_contraste(hex_a: str, hex_b: str) -> float:
    """Ratio de contraste WCAG 2.1 entre dos colores (rango 1.0 a 21.0).

    Es independiente del orden de los argumentos: siempre se divide la
    luminancia del color más claro por la del más oscuro (+ 0.05).
    """
    l_a = luminancia_relativa(hex_a)
    l_b = luminancia_relativa(hex_b)
    clara = max(l_a, l_b)
    oscura = min(l_a, l_b)
    return (clara + 0.05) / (oscura + 0.05)


def obtener_color_texto_accesible(hex_fondo: object) -> str:
    """Devuelve '#FFFFFF' o '#000000' asegurando ratio >= 4.5:1 sobre hex_fondo.

    Se elige el candidato que maximiza el ratio; para cualquier #RRGGBB
    válido el punto de cruce teórico (~4.58:1) garantiza el mínimo AA.
    Ante entrada inválida se aplica fallback defensivo a blanco (#FFFFFF),
    consistente con la tolerancia de resolver_skin.
    """
    try:
        l_fondo = luminancia_relativa(hex_fondo)
    except ValueError:
        return BLANCO

    ratio_blanco = 1.05 / (l_fondo + 0.05)
    ratio_negro = (l_fondo + 0.05) / 0.05
    return BLANCO if ratio_blanco >= ratio_negro else NEGRO


def resolver_skin(comercio: Any | None = None) -> dict[str, str]:
    """Devuelve los valores efectivos de skin para un comercio.

    Fallback defensivo: si no hay comercio, el preset es desconocido o los
    colores persistidos son inválidos, se usan los del preset por defecto.
    Los colores guardados en el comercio tienen prioridad sobre el preset.
    Deriva además el color de texto accesible (WCAG 2.1, ratio >= 4.5:1)
    para cada color del skin.
    """
    skin = {"tema_preset": PRESET_DEFAULT, **SKINS_PRESETS[PRESET_DEFAULT]}

    if comercio is None:
        return _con_texto_accesible(skin)

    tema = getattr(comercio, "tema_preset", None)
    if tema in SKINS_PRESETS:
        skin["tema_preset"] = tema

    for campo in ("color_primario", "color_secundario"):
        valor = getattr(comercio, campo, None)
        if es_hex_valido(valor):
            skin[campo] = valor

    return _con_texto_accesible(skin)


def _con_texto_accesible(skin: dict[str, str]) -> dict[str, str]:
    """Agrega texto_sobre_primario / texto_sobre_secundario al skin."""
    skin["texto_sobre_primario"] = obtener_color_texto_accesible(skin["color_primario"])
    skin["texto_sobre_secundario"] = obtener_color_texto_accesible(skin["color_secundario"])
    return skin
