"""Servicio de IA conversacional con Gemini API (Etapa 9.1).

Arquitectura:
- El prompt del sistema se construye dinamicamente con los datos del
  tenant actual (horarios, servicios, precios, politicas).
- Function calling con dos tools de solo lectura:
    * check_availability: slots libres para un servicio/fecha.
    * get_appointment_status: turnos del actor autenticado.
- Aislamiento multitenant: comercio_id SIEMPRE proviene del actor
  autenticado resuelto en el router; nunca del body ni de los argumentos
  que "decide" el modelo.
- Errores de la API (timeout, cuota, red) no rompen la UX: se retorna
  una respuesta amable con estado='fallback'.
"""

import json
import logging
from datetime import date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.models.chat import ChatMensaje, ChatSesion
from app.models.cliente import Cliente
from app.models.comercio import Comercio
from app.models.servicio import Servicio
from app.models.turno import Turno
from app.services.turnos import calcular_slots_disponibles

try:  # SDK opcional en runtime; sin key el endpoint funciona en modo fallback
    from google import genai
    from google.genai import types as genai_types
except ImportError:  # pragma: no cover - solo si falta instalar requirements
    genai = None
    genai_types = None

logger = logging.getLogger("servipet.ai_chat")

MAX_TOOL_ITERACIONES = 3
MAX_HISTORIAL_MENSAJES = 20
MAX_DIAS_FUTURO = 60
ESTADOS_CANCELADOS = ("CANCELADO", "CANCELADO_TARDIO")

FALLBACK_ERROR = (
    "Perdon, estoy teniendo problemas tecnicos para conectarme en este momento. "
    "Por favor intenta de nuevo en unos minutos."
)
FALLBACK_SIN_CONFIG = (
    "El asistente virtual todavia no esta configurado para este comercio. "
    "Podes consultar disponibilidad y turnos desde la aplicacion web."
)

DIAS_SEMANA = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]


# ---------------------------------------------------------------------------
# Cliente / config de la API de Gemini
# ---------------------------------------------------------------------------

def _cliente_ia():
    """Retorna un cliente de Gemini o None si no hay SDK/key configurada."""
    if genai is None or not settings.GEMINI_API_KEY:
        return None
    try:
        return genai.Client(
            api_key=settings.GEMINI_API_KEY,
            http_options={"timeout": settings.GEMINI_TIMEOUT_S * 1000},
        )
    except Exception:  # pragma: no cover - firmas distintas entre versiones
        logger.exception("No se pudo crear el cliente de Gemini")
        return None


def _declaraciones_tools():
    """Herramientas de function calling expuestas al modelo."""
    T = genai_types.Type
    return [
        genai_types.Tool(
            function_declarations=[
                genai_types.FunctionDeclaration(
                    name="check_availability",
                    description=(
                        "Consulta los horarios disponibles para un servicio en una fecha. "
                        "Usala siempre antes de afirmar si hay lugar."
                    ),
                    parameters=genai_types.Schema(
                        type=T.OBJECT,
                        properties={
                            "fecha": genai_types.Schema(
                                type=T.STRING,
                                description="Fecha a consultar en formato YYYY-MM-DD",
                            ),
                            "nombre_servicio": genai_types.Schema(
                                type=T.STRING,
                                description="Nombre exacto o parcial del servicio",
                            ),
                        },
                        required=["fecha"],
                    ),
                ),
                genai_types.FunctionDeclaration(
                    name="get_appointment_status",
                    description=(
                        "Devuelve los proximos turnos del usuario actual (y el ultimo "
                        "turno realizado). No recibe parametros: el alcance lo define "
                        "la sesion autenticada."
                    ),
                    parameters=genai_types.Schema(type=T.OBJECT, properties={}),
                ),
            ]
        )
    ]


# ---------------------------------------------------------------------------
# Prompt dinamico con datos del tenant
# ---------------------------------------------------------------------------

def construir_prompt(comercio: Comercio, servicios: list[Servicio]) -> str:
    """Construye el system instruction con datos reales del comercio."""
    ahora = datetime.now()
    lineas = [
        f"Sos el asistente virtual de '{comercio.nombre}' "
        f"({comercio.tipo_comercio.lower()}).",
        f"Fecha y hora actual: {ahora.strftime('%Y-%m-%d %H:%M')} "
        f"({DIAS_SEMANA[ahora.weekday()]}).",
        (
            f"Horario de atencion: {comercio.hora_apertura} a {comercio.hora_cierre}, "
            f"con turnos cada {comercio.slot_minutos} minutos."
        ),
        "",
        "Servicios disponibles:",
    ]
    for s in servicios:
        precio = f"${s.precio_base:,.0f}".replace(",", ".")
        lineas.append(f"- {s.nombre}: {precio} ({s.duracion_minutos} minutos)")
    politica = (
        f"Politica de cancelacion: sin penalizacion hasta "
        f"{comercio.horas_limite_cancelacion} horas antes del turno"
    )
    if comercio.porcentaje_recargo_tardio:
        politica += (
            f"; luego aplica un recargo del {comercio.porcentaje_recargo_tardio:g}%."
        )
    else:
        politica += "."
    lineas += [
        "",
        politica,
        (
            "Autoreserva desde la web: "
            + ("habilitada." if comercio.permite_autoreserva_publica else "deshabilitada.")
        ),
        "",
        "Reglas obligatorias:",
        "- Respondes en espanol rioplatense, cordial, breve y claro.",
        "- Nunca inventes disponibilidad ni precios: usa check_availability.",
        "- Para conocer los turnos del usuario usa get_appointment_status.",
        "- Solo hablas de este negocio y de los datos del usuario actual; jamas "
        "menciones informacion de otros clientes.",
        "- Para reservar, reprogramar o cancelar un turno deriva al usuario a la "
        "seccion 'Mis Turnos' de la aplicacion web.",
        "- Si algo no esta en tus datos o herramientas, decilo honestamente.",
    ]
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# Ejecucion de tools (aislamiento multitenant forzado)
# ---------------------------------------------------------------------------

def _listar_servicios(db: Session) -> list[Servicio]:
    """Catalogo de servicios visible para el chatbot.

    Nota: la tabla servicios es global (sin comercio_id); el tenant se
    aplica sobre turnos/clientes, que es donde vive el dato sensible.
    """
    return db.query(Servicio).order_by(Servicio.nombre).all()


def _check_availability(db: Session, comercio_id: int, args: dict) -> dict:
    fecha_raw = str(args.get("fecha") or "").strip()
    try:
        fecha = date.fromisoformat(fecha_raw)
    except ValueError:
        return {"error": "Formato de fecha invalido; se espera YYYY-MM-DD"}

    hoy = date.today()
    if fecha < hoy:
        return {"error": "La fecha ya paso; consultame desde hoy en adelante"}
    if fecha > hoy + timedelta(days=MAX_DIAS_FUTURO):
        return {"error": f"Solo puedo consultar hasta {MAX_DIAS_FUTURO} dias en el futuro"}

    servicios = _listar_servicios(db)
    nombre_pedido = str(args.get("nombre_servicio") or "").strip().lower()
    if not nombre_pedido:
        return {
            "error": "Falta indicar el servicio",
            "servicios_disponibles": [s.nombre for s in servicios],
        }
    servicio = next((s for s in servicios if s.nombre.lower() == nombre_pedido), None)
    if servicio is None:
        servicio = next((s for s in servicios if nombre_pedido in s.nombre.lower()), None)
    if servicio is None:
        return {
            "error": "No encuentro ese servicio",
            "servicios_disponibles": [s.nombre for s in servicios],
        }

    comercio = db.get(Comercio, comercio_id)
    slots = calcular_slots_disponibles(db, comercio, fecha, servicio, comercio_id=comercio_id)
    return {
        "fecha": fecha.isoformat(),
        "servicio": servicio.nombre,
        "precio_base": servicio.precio_base,
        "duracion_minutos": servicio.duracion_minutos,
        "horarios_disponibles": slots,
        "cantidad_disponible": len(slots),
    }


def _serializar_turno(t: Turno) -> dict:
    return {
        "fecha_hora": t.fecha_hora.strftime("%Y-%m-%d %H:%M"),
        "servicio": t.servicio.nombre if t.servicio else None,
        "mascota": t.mascota.nombre if t.mascota else None,
        "estado": (t.estado or "").upper(),
        "duracion_minutos": t.duracion_minutos,
    }


def _get_appointment_status(db: Session, comercio_id: int, actor_tipo: str, actor_id: int) -> dict:
    ahora = datetime.now()

    base = (
        db.query(Turno)
        .join(Cliente, Turno.cliente_id == Cliente.id)
        .options(joinedload(Turno.servicio), joinedload(Turno.mascota))
        .filter(Cliente.comercio_id == comercio_id, ~Turno.estado.in_(ESTADOS_CANCELADOS))
    )
    if actor_tipo == "cliente":
        base = base.filter(Cliente.id == actor_id)

    proximos = base.filter(Turno.fecha_hora >= ahora).order_by(Turno.fecha_hora.asc()).limit(5).all()

    respuesta: dict = {"proximos_turnos": [_serializar_turno(t) for t in proximos]}

    if actor_tipo == "cliente":
        ultimo = (
            db.query(Turno)
            .join(Cliente, Turno.cliente_id == Cliente.id)
            .options(joinedload(Turno.servicio), joinedload(Turno.mascota))
            .filter(
                Cliente.id == actor_id,
                Cliente.comercio_id == comercio_id,
                Turno.fecha_hora < ahora,
            )
            .order_by(Turno.fecha_hora.desc())
            .first()
        )
        if ultimo:
            respuesta["ultimo_turno"] = _serializar_turno(ultimo)

    return respuesta


def ejecutar_tool(db: Session, *, comercio_id: int, actor_tipo: str, actor_id: int, nombre: str, args: dict) -> dict:
    """Despacha una tool; cualquier error interno vuelve como dict legible por el modelo."""
    try:
        if nombre == "check_availability":
            return _check_availability(db, comercio_id, args)
        if nombre == "get_appointment_status":
            return _get_appointment_status(db, comercio_id, actor_tipo, actor_id)
        return {"error": f"Herramienta desconocida: {nombre}"}
    except Exception as exc:
        logger.exception("Error ejecutando tool '%s'", nombre)
        return {"error": f"No se pudo completar la consulta: {exc}"}


# ---------------------------------------------------------------------------
# Conversacion con Gemini (loop de function calling)
# ---------------------------------------------------------------------------

def _config_generacion(prompt: str):
    return genai_types.GenerateContentConfig(
        system_instruction=prompt,
        temperature=0.4,
        max_output_tokens=512,
        tools=_declaraciones_tools(),
    )


def _historial_a_contents(sesion: ChatSesion, mensaje_nuevo: str) -> list:
    T = genai_types
    contents: list = []
    historial = sorted(sesion.mensajes, key=lambda m: m.id)[-MAX_HISTORIAL_MENSAJES:]
    for m in historial:
        if m.rol not in ("user", "model") or not m.contenido:
            continue
        contents.append(T.Content(role=m.rol, parts=[T.Part(text=m.contenido)]))
    contents.append(T.Content(role="user", parts=[T.Part(text=mensaje_nuevo)]))
    return contents


def _texto_de_respuesta(response) -> str | None:
    try:
        texto = response.text
    except Exception:
        return None
    texto = (texto or "").strip()
    return texto or None


def _conversar(
    db: Session,
    cliente_ia,
    *,
    comercio_id: int,
    actor_tipo: str,
    actor_id: int,
    model_name: str,
    contents: list,
    prompt: str,
) -> tuple[str, list[str]]:
    """Loop de function calling. Lanza excepciones ante fallos de API."""
    herramientas_usadas: list[str] = []
    for _ in range(MAX_TOOL_ITERACIONES + 1):
        response = cliente_ia.models.generate_content(
            model=model_name,
            contents=contents,
            config=_config_generacion(prompt),
        )

        llamadas = list(getattr(response, "function_calls", None) or [])
        if llamadas:
            if response.candidates:
                contents.append(response.candidates[0].content)
            partes = []
            for llamada in llamadas:
                herramientas_usadas.append(llamada.name)
                resultado = ejecutar_tool(
                    db,
                    comercio_id=comercio_id,
                    actor_tipo=actor_tipo,
                    actor_id=actor_id,
                    nombre=llamada.name,
                    args=dict(llamada.args or {}),
                )
                partes.append(
                    genai_types.Part(
                        function_response=genai_types.FunctionResponse(
                            name=llamada.name, response=resultado
                        )
                    )
                )
            contents.append(genai_types.Content(role="user", parts=partes))
            continue

        texto = _texto_de_respuesta(response)
        if texto:
            return texto, herramientas_usadas
        break
    raise RuntimeError("Gemini no devolvio una respuesta util")


# ---------------------------------------------------------------------------
# Sesion y punto de entrada
# ---------------------------------------------------------------------------

def resolver_sesion(
    db: Session,
    *,
    comercio_id: int,
    actor_tipo: str,
    actor_id: int,
    sesion_id: int | None,
) -> ChatSesion:
    """Recupera la sesion si pertenece al tenant/actor; si no, crea una nueva."""
    if sesion_id is not None:
        sesion = db.get(ChatSesion, sesion_id)
        if not sesion:
            raise HTTPException(status_code=404, detail="Sesion de chat no encontrada")
        if (
            sesion.comercio_id != comercio_id
            or sesion.actor_tipo != actor_tipo
            or sesion.actor_id != actor_id
        ):
            raise HTTPException(
                status_code=403,
                detail="La sesion de chat no pertenece al usuario actual",
            )
        return sesion

    sesion = ChatSesion(comercio_id=comercio_id, actor_tipo=actor_tipo, actor_id=actor_id)
    db.add(sesion)
    db.flush()
    return sesion


def generar_respuesta(
    db: Session,
    *,
    comercio: Comercio,
    actor_tipo: str,
    actor_id: int,
    sesion_id: int | None,
    mensaje: str,
) -> dict:
    """Orquesta: sesion -> prompt dinamico -> conversacion -> persistencia."""
    sesion = resolver_sesion(
        db,
        comercio_id=comercio.id,
        actor_tipo=actor_tipo,
        actor_id=actor_id,
        sesion_id=sesion_id,
    )

    cliente_ia = _cliente_ia()
    if cliente_ia is None:
        respuesta, estado, herramientas = FALLBACK_SIN_CONFIG, "fallback", []
    else:
        servicios = _listar_servicios(db)
        prompt = construir_prompt(comercio, servicios)
        contents = _historial_a_contents(sesion, mensaje)
        try:
            texto, herramientas = _conversar(
                db,
                cliente_ia,
                comercio_id=comercio.id,
                actor_tipo=actor_tipo,
                actor_id=actor_id,
                model_name=settings.GEMINI_MODEL,
                contents=contents,
                prompt=prompt,
            )
            if texto:
                respuesta, estado = texto, "ok"
            else:
                respuesta, estado = FALLBACK_ERROR, "fallback"
        except Exception:
            logger.exception("Fallo la conversacion con Gemini")
            respuesta, estado, herramientas = FALLBACK_ERROR, "fallback", []

    sesion.ultimo_mensaje_en = datetime.utcnow()
    sesion.mensajes.append(ChatMensaje(rol="user", contenido=mensaje))
    sesion.mensajes.append(
        ChatMensaje(
            rol="model",
            contenido=respuesta,
            herramientas_usadas=json.dumps(herramientas) if herramientas else None,
        )
    )
    db.commit()

    return {
        "sesion_id": sesion.id,
        "respuesta": respuesta,
        "estado": estado,
        "herramientas_usadas": herramientas,
    }
