"""Tests del modulo de chat IA (Etapas 9.1 y 9.3): /api/v1/chat."""

import json
from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from google.genai import types as genai_types

from app.config import settings
from app.dependencies.client import COOKIE_SESION
from app.main import app
from app.models.chat import ChatMensaje, ChatSesion
from app.models.cliente import Cliente
from app.models.comercio import Comercio
from app.models.mascota import Mascota
from app.models.servicio import Servicio
from app.models.turno import Turno
from app.models.usuario import Usuario
from app.services import ai_chat_service
from app.services.auth_tokens import crear_token

URL_CHAT = "/api/v1/chat"
FECHA_MANANA = date.today() + timedelta(days=1)
HORA_10 = datetime.strptime("10:00", "%H:%M").time()


@pytest.fixture
def db():
    from tests.conftest import TestingSessionLocal

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def sin_credenciales_gemini(monkeypatch):
    """Etapa 9.3: suite hermetica, nunca usa red ni API key real."""
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)


def _seed_escenario(db):
    """Dos comercios, un servicio global y clientes/turnos por tenant.

    El comercio 1 puede ya existir porque el fixture admin_user lo crea;
    en ese caso se reutilizan sus ids y se ajustan los datos usados aqui.
    """
    comercio_1 = db.get(Comercio, 1)
    if comercio_1 is None:
        comercio_1 = Comercio(
            id=1,
            nombre="Vet Norte",
            tipo_comercio="VETERINARIA",
            activo=True,
        )
        db.add(comercio_1)
    comercio_1.nombre = "Vet Norte"
    comercio_1.hora_apertura = "09:00"
    comercio_1.hora_cierre = "18:00"
    comercio_1.slot_minutos = 30

    if db.get(Comercio, 2) is None:
        db.add(
            Comercio(
                id=2,
                nombre="Pet Sur",
                tipo_comercio="PELUQUERIA",
                hora_apertura="09:00",
                hora_cierre="18:00",
                slot_minutos=30,
                activo=True,
            )
        )
    db.flush()

    servicio = Servicio(
        nombre="Consulta Veterinaria General",
        descripcion="Revision general",
        precio_base=5000.0,
        duracion_minutos=60,
    )
    db.add(servicio)
    db.flush()

    cliente_a = Cliente(comercio_id=1, nombre="Ana")
    cliente_c = Cliente(comercio_id=1, nombre="Caro")
    cliente_b = Cliente(comercio_id=2, nombre="Beto")
    db.add_all([cliente_a, cliente_c, cliente_b])
    db.flush()

    mascota_a = Mascota(nombre="Rocky", cliente_id=cliente_a.id, especie="Perro")
    mascota_b = Mascota(nombre="Luna", cliente_id=cliente_b.id, especie="Gato")
    db.add_all([mascota_a, mascota_b])
    db.flush()

    # Turno de Ana (tenant 1) manana 10:00 -> bloquea ese slot solo para tenant 1
    db.add(
        Turno(
            cliente_id=cliente_a.id,
            mascota_id=mascota_a.id,
            servicio_id=servicio.id,
            fecha_hora=datetime.combine(FECHA_MANANA, HORA_10),
            duracion_minutos=60,
            estado="PENDIENTE",
        )
    )
    # Turno finalizado de Beto (tenant 2), ayer
    db.add(
        Turno(
            cliente_id=cliente_b.id,
            mascota_id=mascota_b.id,
            servicio_id=servicio.id,
            fecha_hora=datetime.now() - timedelta(days=1),
            duracion_minutos=60,
            estado="Finalizado",
        )
    )
    db.commit()
    return {
        "servicio": servicio,
        "cliente_a": cliente_a,
        "cliente_c": cliente_c,
        "cliente_b": cliente_b,
        "mascota_b": mascota_b,
    }


# ---------------------------------------------------------------------------
# Autenticacion y fallbacks
# ---------------------------------------------------------------------------

def test_chat_requiere_autenticacion(client):
    resp = client.post(URL_CHAT, json={"mensaje": "hola"})
    assert resp.status_code == 401


def test_mensaje_vacio_rechazado(client, admin_headers):
    resp = client.post(URL_CHAT, json={"mensaje": ""}, headers=admin_headers)
    assert resp.status_code == 422


def test_fallback_sin_api_key(client, admin_headers, monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)
    resp = client.post(URL_CHAT, json={"mensaje": "hay turnos?"}, headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["estado"] == "fallback"
    assert body["herramientas_usadas"] == []
    assert body["sesion_id"] >= 1


# ---------------------------------------------------------------------------
# Tools: aislamiento multitenant
# ---------------------------------------------------------------------------

def _tool_disponibilidad(db, comercio_id, datos):
    return ai_chat_service.ejecutar_tool(
        db,
        comercio_id=comercio_id,
        actor_tipo="usuario",
        actor_id=1,
        nombre="check_availability",
        args={
            "fecha": FECHA_MANANA.isoformat(),
            "nombre_servicio": datos["servicio"].nombre,
        },
    )


def test_check_availability_aisla_turnos_por_tenant(db):
    datos = _seed_escenario(db)

    resultado_1 = _tool_disponibilidad(db, 1, datos)
    resultado_2 = _tool_disponibilidad(db, 2, datos)

    assert "error" not in resultado_1, resultado_1
    assert "10:00" not in resultado_1["horarios_disponibles"]
    assert "09:00" in resultado_1["horarios_disponibles"]

    assert "error" not in resultado_2, resultado_2
    assert "10:00" in resultado_2["horarios_disponibles"]
    assert resultado_2["precio_base"] == 5000.0


def test_check_availability_validaciones(db):
    datos = _seed_escenario(db)

    pasado = ai_chat_service.ejecutar_tool(
        db,
        comercio_id=1,
        actor_tipo="usuario",
        actor_id=1,
        nombre="check_availability",
        args={"fecha": "1999-01-01", "nombre_servicio": datos["servicio"].nombre},
    )
    assert "error" in pasado

    sin_servicio = ai_chat_service.ejecutar_tool(
        db,
        comercio_id=1,
        actor_tipo="usuario",
        actor_id=1,
        nombre="check_availability",
        args={"fecha": FECHA_MANANA.isoformat()},
    )
    assert "servicios_disponibles" in sin_servicio


def test_get_appointment_status_scope_de_cliente(db):
    datos = _seed_escenario(db)

    propio = ai_chat_service.ejecutar_tool(
        db,
        comercio_id=1,
        actor_tipo="cliente",
        actor_id=datos["cliente_a"].id,
        nombre="get_appointment_status",
        args={},
    )
    assert len(propio["proximos_turnos"]) == 1
    assert propio["proximos_turnos"][0]["estado"] == "PENDIENTE"

    ajeno = ai_chat_service.ejecutar_tool(
        db,
        comercio_id=1,
        actor_tipo="cliente",
        actor_id=datos["cliente_c"].id,
        nombre="get_appointment_status",
        args={},
    )
    assert ajeno["proximos_turnos"] == []
    assert "ultimo_turno" not in ajeno

    beto = ai_chat_service.ejecutar_tool(
        db,
        comercio_id=2,
        actor_tipo="cliente",
        actor_id=datos["cliente_b"].id,
        nombre="get_appointment_status",
        args={},
    )
    assert len(beto["proximos_turnos"]) == 0
    assert beto["ultimo_turno"]["estado"] == "FINALIZADO"


# ---------------------------------------------------------------------------
# Prompt dinamico
# ---------------------------------------------------------------------------

def test_prompt_incluye_datos_del_tenant(db):
    datos = _seed_escenario(db)
    comercio = db.get(Comercio, 1)
    prompt = ai_chat_service.construir_prompt(comercio, [datos["servicio"]])

    assert "Vet Norte" in prompt
    assert "09:00 a 18:00" in prompt
    assert "Consulta Veterinaria General" in prompt
    assert "5000" in prompt.replace(",", "").replace(".", "")
    assert "check_availability" in prompt


# ---------------------------------------------------------------------------
# Fakes del SDK de Gemini (Etapa 9.3: snapshot por ronda + candidatos reales)
# ---------------------------------------------------------------------------

class _FakeRespuesta:
    def __init__(self, texto=None, llamadas=None, candidatos=None):
        self.texto_interno = texto
        self.function_calls = llamadas or []
        self.candidates = candidatos or []

    @property
    def text(self):
        if self.texto_interno is None:
            raise ValueError("sin texto")
        return self.texto_interno


class _FakeLlamada:
    def __init__(self, name, args=None):
        self.name = name
        self.args = args or {}


class _FakeIA:
    """Simula google.genai.Client.models.generate_content.

    - respuestas acepta _FakeRespuesta o Exception (se lanza al llegar).
    - recibidas[i] guarda {"model", "contents" (copia superficial), "config"}
      tal como estaban en la ronda i, para poder asertar sobre el historial.
    """

    def __init__(self, respuestas):
        self.respuestas = list(respuestas)
        self.recibidas = []
        self.models = self

    @staticmethod
    def _snapshot(kwargs):
        return {
            "model": kwargs.get("model"),
            "contents": list(kwargs.get("contents") or []),
            "config": kwargs.get("config"),
        }

    def generate_content(self, **kwargs):
        self.recibidas.append(self._snapshot(kwargs))
        item = self.respuestas.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class _FakeIABucle(_FakeIA):
    """Devuelve siempre la misma respuesta; sirve para probar el tope del loop."""

    def __init__(self, respuesta):
        super().__init__([])
        self.respuesta = respuesta

    def generate_content(self, **kwargs):
        self.recibidas.append(self._snapshot(kwargs))
        return self.respuesta


def _respuestas_de_herramientas(ronda):
    """Dict {nombre_tool: response} que el servicio envio al modelo en esa ronda."""
    salida = {}
    for part in ronda["contents"][-1].parts:
        if part.function_response is not None:
            salida[part.function_response.name] = dict(part.function_response.response)
    return salida


# ---------------------------------------------------------------------------
# Endpoint con Gemini simulado
# ---------------------------------------------------------------------------


def test_camino_feliz_con_gemini_mockeado(client, admin_headers, monkeypatch, db):
    datos = _seed_escenario(db)
    fake = _FakeIA([_FakeRespuesta(texto="Hola! Si tenemos turnos disponibles.")])
    monkeypatch.setattr(ai_chat_service, "_cliente_ia", lambda: fake)

    resp = client.post(
        URL_CHAT,
        json={"mensaje": "Hay turnos manana?"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["estado"] == "ok"
    assert "disponibles" in body["respuesta"]
    assert body["herramientas_usadas"] == []

    mensajes = (
        db.query(ChatMensaje)
        .filter(ChatMensaje.sesion_id == body["sesion_id"])
        .order_by(ChatMensaje.id)
        .all()
    )
    assert [m.rol for m in mensajes] == ["user", "model"]


def test_loop_function_calling_ejecuta_tools(client, admin_headers, monkeypatch, db):
    datos = _seed_escenario(db)
    fake = _FakeIA(
        [
            _FakeRespuesta(
                llamadas=[
                    _FakeLlamada(
                        "check_availability",
                        {"fecha": FECHA_MANANA.isoformat(), "nombre_servicio": "Consulta"},
                    ),
                    _FakeLlamada("get_appointment_status"),
                ]
            ),
            _FakeRespuesta(texto="A las 11:00 hay lugar."),
        ]
    )
    monkeypatch.setattr(ai_chat_service, "_cliente_ia", lambda: fake)

    resp = client.post(
        URL_CHAT,
        json={"mensaje": "Que horarios hay manana para consulta?"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["estado"] == "ok"
    assert sorted(body["herramientas_usadas"]) == [
        "check_availability",
        "get_appointment_status",
    ]

    model_msg = (
        db.query(ChatMensaje)
        .filter(ChatMensaje.sesion_id == body["sesion_id"], ChatMensaje.rol == "model")
        .one()
    )
    assert "check_availability" in model_msg.herramientas_usadas


def test_error_de_api_retorna_fallback(client, admin_headers, monkeypatch, db):
    _seed_escenario(db)

    def _romper(**kwargs):
        raise TimeoutError("simulado")

    fake = _FakeIA([])
    fake.generate_content = _romper
    monkeypatch.setattr(ai_chat_service, "_cliente_ia", lambda: fake)

    resp = client.post(URL_CHAT, json={"mensaje": "hola"}, headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["estado"] == "fallback"
    assert body["respuesta"] == ai_chat_service.FALLBACK_ERROR


def test_sesion_se_reusa_y_la_ajena_se_rechaza(client, admin_headers, db):
    _seed_escenario(db)

    sesion_ajena = ChatSesion(comercio_id=1, actor_tipo="cliente", actor_id=999)
    db.add(sesion_ajena)
    db.commit()

    resp_ajena = client.post(
        URL_CHAT,
        json={"mensaje": "hola", "sesion_id": sesion_ajena.id},
        headers=admin_headers,
    )
    assert resp_ajena.status_code == 403

    resp_inexistente = client.post(
        URL_CHAT,
        json={"mensaje": "hola", "sesion_id": 987654},
        headers=admin_headers,
    )
    assert resp_inexistente.status_code == 404

    r1 = client.post(URL_CHAT, json={"mensaje": "uno"}, headers=admin_headers)
    assert r1.status_code == 200
    sid = r1.json()["sesion_id"]

    r2 = client.post(
        URL_CHAT,
        json={"mensaje": "dos", "sesion_id": sid},
        headers=admin_headers,
    )
    assert r2.status_code == 200
    assert r2.json()["sesion_id"] == sid

    total = (
        db.query(ChatMensaje)
        .filter(ChatMensaje.sesion_id == sid, ChatMensaje.rol == "user")
        .count()
    )
    assert total == 2


# ---------------------------------------------------------------------------
# Etapa 9.3 - Loop de function calling: casos de borde
# ---------------------------------------------------------------------------

def test_loop_limita_iteraciones_y_cae_en_fallback(client, admin_headers, monkeypatch, db):
    _seed_escenario(db)
    llamada = _FakeLlamada(
        "check_availability",
        {"fecha": FECHA_MANANA.isoformat(), "nombre_servicio": "Consulta"},
    )
    fake = _FakeIABucle(_FakeRespuesta(llamadas=[llamada]))
    monkeypatch.setattr(ai_chat_service, "_cliente_ia", lambda: fake)

    resp = client.post(URL_CHAT, json={"mensaje": "turnos?"}, headers=admin_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["estado"] == "fallback"
    assert body["respuesta"] == ai_chat_service.FALLBACK_ERROR
    assert len(fake.recibidas) == ai_chat_service.MAX_TOOL_ITERACIONES + 1


def test_tool_desconocida_no_rompe_el_loop(client, admin_headers, monkeypatch, db):
    _seed_escenario(db)
    fake = _FakeIA(
        [
            _FakeRespuesta(llamadas=[_FakeLlamada("clima_actual", {})]),
            _FakeRespuesta(texto="No manejo el clima, pero puedo ver turnos."),
        ]
    )
    monkeypatch.setattr(ai_chat_service, "_cliente_ia", lambda: fake)

    resp = client.post(URL_CHAT, json={"mensaje": "va a llover?"}, headers=admin_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["estado"] == "ok"
    assert body["herramientas_usadas"] == ["clima_actual"]

    enviadas = _respuestas_de_herramientas(fake.recibidas[1])
    assert enviadas["clima_actual"] == {"error": "Herramienta desconocida: clima_actual"}


def test_args_invalidos_envian_error_legible_al_modelo(client, admin_headers, monkeypatch, db):
    datos = _seed_escenario(db)
    fake = _FakeIA(
        [
            _FakeRespuesta(
                llamadas=[
                    _FakeLlamada(
                        "check_availability",
                        {
                            "fecha": "31/12/2026",
                            "nombre_servicio": datos["servicio"].nombre,
                        },
                    )
                ]
            ),
            _FakeRespuesta(texto="La fecha no se entiende."),
        ]
    )
    monkeypatch.setattr(ai_chat_service, "_cliente_ia", lambda: fake)

    resp = client.post(
        URL_CHAT,
        json={"mensaje": "hay lugar el 31/12/2026?"},
        headers=admin_headers,
    )

    assert resp.status_code == 200
    assert resp.json()["estado"] == "ok"

    enviada = _respuestas_de_herramientas(fake.recibidas[1])["check_availability"]
    assert "error" in enviada
    assert "YYYY-MM-DD" in enviada["error"]


def test_candidates_del_modelo_se_adjuntan_al_historial(client, admin_headers, monkeypatch, db):
    datos = _seed_escenario(db)
    contenido_modelo = genai_types.Content(
        role="model",
        parts=[
            genai_types.Part(
                function_call=genai_types.FunctionCall(
                    name="check_availability",
                    args={"fecha": FECHA_MANANA.isoformat()},
                )
            )
        ],
    )
    primera = _FakeRespuesta(
        llamadas=[
            _FakeLlamada(
                "check_availability",
                {
                    "fecha": FECHA_MANANA.isoformat(),
                    "nombre_servicio": datos["servicio"].nombre,
                },
            )
        ],
        candidatos=[genai_types.Candidate(content=contenido_modelo)],
    )
    fake = _FakeIA([primera, _FakeRespuesta(texto="A las 09:00 hay lugar.")])
    monkeypatch.setattr(ai_chat_service, "_cliente_ia", lambda: fake)

    resp = client.post(URL_CHAT, json={"mensaje": "horarios?"}, headers=admin_headers)

    assert resp.status_code == 200
    assert resp.json()["estado"] == "ok"

    segunda_ronda = fake.recibidas[1]["contents"]
    assert any(c is contenido_modelo for c in segunda_ronda)
    assert _respuestas_de_herramientas(fake.recibidas[1])


# ---------------------------------------------------------------------------
# Etapa 9.3 - Manejo defensivo de fallas
# ---------------------------------------------------------------------------

class _FakeAPIError(Exception):
    """Imita google.genai.errors.APIError sin depender del SDK real."""


def test_apierror_generico_da_fallback_200(client, admin_headers, monkeypatch, db):
    _seed_escenario(db)
    fake = _FakeIA([_FakeAPIError("503 upstream")])
    monkeypatch.setattr(ai_chat_service, "_cliente_ia", lambda: fake)

    resp = client.post(URL_CHAT, json={"mensaje": "hola"}, headers=admin_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["estado"] == "fallback"
    assert body["respuesta"] == ai_chat_service.FALLBACK_ERROR


def test_error_en_segunda_ronda_tras_tool_da_fallback(client, admin_headers, monkeypatch, db):
    datos = _seed_escenario(db)
    fake = _FakeIA(
        [
            _FakeRespuesta(
                llamadas=[
                    _FakeLlamada(
                        "check_availability",
                        {
                            "fecha": FECHA_MANANA.isoformat(),
                            "nombre_servicio": datos["servicio"].nombre,
                        },
                    )
                ]
            ),
            TimeoutError("ronda 2 simulada"),
        ]
    )
    monkeypatch.setattr(ai_chat_service, "_cliente_ia", lambda: fake)

    resp = client.post(URL_CHAT, json={"mensaje": "turnos manana?"}, headers=admin_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["estado"] == "fallback"
    # Comportamiento actual documentado en Etapa 9.3: un fallo posterior a una
    # tool exitosa descarta las herramientas ya ejecutadas.
    assert body["herramientas_usadas"] == []
    assert len(fake.recibidas) == 2


def test_respuesta_bloqueada_sin_texto_ni_tools_da_fallback(client, admin_headers, monkeypatch, db):
    _seed_escenario(db)
    fake = _FakeIA([_FakeRespuesta()])
    monkeypatch.setattr(ai_chat_service, "_cliente_ia", lambda: fake)

    resp = client.post(URL_CHAT, json={"mensaje": "hola"}, headers=admin_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["estado"] == "fallback"
    assert body["respuesta"] == ai_chat_service.FALLBACK_ERROR

    model_msg = (
        db.query(ChatMensaje)
        .filter(ChatMensaje.sesion_id == body["sesion_id"], ChatMensaje.rol == "model")
        .one()
    )
    assert model_msg.contenido == ai_chat_service.FALLBACK_ERROR


# ---------------------------------------------------------------------------
# Etapa 9.3 - Persistencia de sesion y mensajes
# ---------------------------------------------------------------------------

def test_persistencia_completa_de_sesion_y_mensajes(client, admin_headers, monkeypatch, db):
    datos = _seed_escenario(db)
    holder = {"fake": None}
    monkeypatch.setattr(ai_chat_service, "_cliente_ia", lambda: holder["fake"])

    holder["fake"] = _FakeIA(
        [
            _FakeRespuesta(
                llamadas=[
                    _FakeLlamada(
                        "check_availability",
                        {
                            "fecha": FECHA_MANANA.isoformat(),
                            "nombre_servicio": datos["servicio"].nombre,
                        },
                    )
                ]
            ),
            _FakeRespuesta(texto="A las 11:00 hay lugar."),
        ]
    )
    r1 = client.post(URL_CHAT, json={"mensaje": "primera"}, headers=admin_headers)
    assert r1.status_code == 200
    sid = r1.json()["sesion_id"]

    sesion = db.get(ChatSesion, sid)
    admin_user = db.query(Usuario).filter(Usuario.comercio_id == 1).first()
    assert sesion.comercio_id == 1
    assert sesion.actor_tipo == "usuario"
    assert sesion.actor_id == admin_user.id

    mensajes = (
        db.query(ChatMensaje)
        .filter(ChatMensaje.sesion_id == sid)
        .order_by(ChatMensaje.id)
        .all()
    )
    assert [m.rol for m in mensajes] == ["user", "model"]
    assert json.loads(mensajes[1].herramientas_usadas) == ["check_availability"]
    assert mensajes[0].herramientas_usadas is None

    holder["fake"] = _FakeIA([_FakeRespuesta(texto="Listo.")])
    r2 = client.post(
        URL_CHAT,
        json={"mensaje": "segunda", "sesion_id": sid},
        headers=admin_headers,
    )
    assert r2.status_code == 200
    assert r2.json()["sesion_id"] == sid

    fake_2 = holder["fake"]
    roles_enviados = [c.role for c in fake_2.recibidas[0]["contents"]]
    assert roles_enviados == ["user", "model", "user"]

    mensajes = (
        db.query(ChatMensaje)
        .filter(ChatMensaje.sesion_id == sid)
        .order_by(ChatMensaje.id)
        .all()
    )
    assert [m.rol for m in mensajes] == ["user", "model", "user", "model"]
    assert mensajes[-1].herramientas_usadas is None

    sesion = db.get(ChatSesion, sid)
    assert sesion.ultimo_mensaje_en >= sesion.creado_en


# ---------------------------------------------------------------------------
# Etapa 9.3 - Sesiones multitenant y actor cliente PWA
# ---------------------------------------------------------------------------

def test_sesion_cross_tenant_rechazada_403(client, admin_headers, db):
    _seed_escenario(db)
    sesion_sur = ChatSesion(comercio_id=2, actor_tipo="usuario", actor_id=99)
    db.add(sesion_sur)
    db.commit()

    resp = client.post(
        URL_CHAT,
        json={"mensaje": "hola", "sesion_id": sesion_sur.id},
        headers=admin_headers,
    )
    assert resp.status_code == 403


def test_cliente_pwa_chatea_y_su_sesion_queda_acotada(client, admin_headers, monkeypatch, db):
    datos = _seed_escenario(db)
    cliente_a = datos["cliente_a"]

    fake = _FakeIA([_FakeRespuesta(texto="Hola Ana, como puedo ayudarte?")])
    monkeypatch.setattr(ai_chat_service, "_cliente_ia", lambda: fake)

    # El fixture client ya trae el JWT de admin en la cookie jar (login real
    # en admin_user); se usa una instancia limpia para el actor cliente.
    cliente_http = TestClient(app)
    cliente_http.cookies.set(COOKIE_SESION, crear_token(cliente_a.id))
    resp = cliente_http.post(URL_CHAT, json={"mensaje": "hola"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["estado"] == "ok"

    sesion = db.get(ChatSesion, body["sesion_id"])
    assert sesion.comercio_id == cliente_a.comercio_id
    assert sesion.actor_tipo == "cliente"
    assert sesion.actor_id == cliente_a.id

    resp_admin = client.post(
        URL_CHAT,
        json={"mensaje": "hola", "sesion_id": body["sesion_id"]},
        headers=admin_headers,
    )
    assert resp_admin.status_code == 403
