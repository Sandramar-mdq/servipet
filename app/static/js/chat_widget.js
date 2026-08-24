/* Widget Flotante de Chat IA - Servipet (Etapa 9.2).
 * Vanilla JS, sin dependencias. Convierte con POST /api/v1/chat
 * usando la cookie de sesion (cliente PWA o JWT usuario).
 */
(function () {
    'use strict';

    var LAUNCHER = document.getElementById('servipet-chat-launcher');
    var PANEL = document.getElementById('servipet-chat-panel');
    if (!LAUNCHER || !PANEL) return;

    var MENSAJES = document.getElementById('servipet-chat-mensajes');
    var TYPING = document.getElementById('servipet-chat-typing');
    var FORM = document.getElementById('servipet-chat-form');
    var INPUT = document.getElementById('servipet-chat-input');
    var BTN_ENVIAR = document.getElementById('servipet-chat-enviar');
    var BTN_CERRAR = document.getElementById('servipet-chat-cerrar');

    var API_CHAT = '/api/v1/chat';
    var KEY_SESION = 'servipet_chat_sesion';
    var KEY_HISTORIAL = 'servipet_chat_historial';
    var MAX_HISTORIAL = 20;
    var SALUDO =
        'Hola! Soy el asistente virtual de ' +
        (PANEL.dataset.comercioNombre || 'Servipet') +
        '. Puedo ayudarte con horarios, servicios y precios, o consultar tus turnos.';

    var estado = {
        abierto: false,
        enviando: false,
        autenticado: true,
        historialCargado: false,
        sesionId: leerSesionId(),
        ultimoMensaje: ''
    };

    // --- Utilidades ---------------------------------------------------------

    function escapeHtml(texto) {
        var div = document.createElement('div');
        div.textContent = texto == null ? '' : String(texto);
        return div.innerHTML;
    }

    function leerSesionId() {
        var valor = parseInt(localStorage.getItem(KEY_SESION), 10);
        return isNaN(valor) ? null : valor;
    }

    function guardarSesionId(id) {
        try {
            localStorage.setItem(KEY_SESION, String(id));
        } catch (e) { /* almacenamiento no disponible */ }
    }

    function limpiarSesion() {
        estado.sesionId = null;
        try {
            localStorage.removeItem(KEY_SESION);
            sessionStorage.removeItem(KEY_HISTORIAL);
        } catch (e) { /* almacenamiento no disponible */ }
    }

    function scrollAbajo() {
        MENSAJES.scrollTop = MENSAJES.scrollHeight;
    }

    function leerHistorial() {
        try {
            var items = JSON.parse(sessionStorage.getItem(KEY_HISTORIAL) || '[]');
            return Array.isArray(items) ? items : [];
        } catch (e) {
            return [];
        }
    }

    function guardarEnHistorial(tipo, texto) {
        try {
            var items = leerHistorial();
            items.push({ t: tipo, m: texto });
            while (items.length > MAX_HISTORIAL) items.shift();
            sessionStorage.setItem(KEY_HISTORIAL, JSON.stringify(items));
        } catch (e) { /* almacenamiento no disponible */ }
    }

    // --- Render de burbujas --------------------------------------------------

    function crearBurbuja(texto, tipo) {
        var fila = document.createElement('div');
        fila.className = 'chat-fila ' + (tipo === 'user' ? 'chat-fila-user' : 'chat-fila-bot');

        var burbuja = document.createElement('div');
        burbuja.className = 'chat-burbuja chat-burbuja-' + tipo;
        burbuja.innerHTML = escapeHtml(texto).replace(/\n/g, '<br>');
        fila.appendChild(burbuja);
        return fila;
    }

    function agregarBurbuja(texto, tipo, persistir) {
        MENSAJES.appendChild(crearBurbuja(texto, tipo));
        if (persistir !== false) guardarEnHistorial(tipo, texto);
        scrollAbajo();
    }

    function agregarErrorRed() {
        var fila = crearBurbuja('No pude conectarme con el asistente. Revisa tu conexion.', 'error');
        var boton = document.createElement('button');
        boton.type = 'button';
        boton.className = 'chat-reintentar block text-red-700 hover:text-red-900';
        boton.textContent = 'Reintentar';
        boton.addEventListener('click', function () {
            fila.remove();
            enviar(estado.ultimoMensaje, true);
        });
        fila.firstChild.appendChild(boton);
        MENSAJES.appendChild(fila);
        scrollAbajo();
    }

    function mostrarTyping(visible) {
        TYPING.classList.toggle('hidden', !visible);
        if (visible) scrollAbajo();
    }

    // --- Envio ---------------------------------------------------------------

    function enviar(mensaje, esInterno) {
        mensaje = (mensaje || '').trim();
        if (!mensaje || estado.enviando || !estado.autenticado) return;

        estado.enviando = true;
        estado.ultimoMensaje = mensaje;
        INPUT.value = '';

        if (!esInterno) {
            agregarBurbuja(mensaje, 'user');
        }
        mostrarTyping(true);

        fetch(API_CHAT, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({
                mensaje: mensaje,
                sesion_id: estado.sesionId
            })
        })
            .then(function (resp) {
                if (resp.status === 401) throw { codigo: 401 };
                if (resp.status === 403) throw { codigo: 403 };
                if (!resp.ok) throw { codigo: resp.status || 0 };
                return resp.json();
            })
            .then(function (data) {
                if (data && data.sesion_id) {
                    estado.sesionId = data.sesion_id;
                    guardarSesionId(data.sesion_id);
                }
                var tipo = data && data.estado === 'fallback' ? 'fallback' : 'bot';
                agregarBurbuja(
                    (data && data.respuesta) || 'No obtuve respuesta del asistente.',
                    tipo
                );
                INPUT.focus();
            })
            .catch(function (err) {
                if (err && err.codigo === 401) {
                    estado.autenticado = false;
                    INPUT.disabled = true;
                    BTN_ENVIAR.disabled = true;
                    agregarBurbuja(
                        'Para chatear con el asistente primero inicia sesion en la aplicacion.',
                        'fallback',
                        false
                    );
                } else if (err && err.codigo === 403 && estado.sesionId !== null) {
                    // Sesion vencida o ajena (ej. cambio de usuario): reiniciar y reintentar una vez.
                    limpiarSesion();
                    window.setTimeout(function () {
                        estado.enviando = false;
                        enviar(mensaje, true);
                    }, 50);
                    return;
                } else {
                    agregarErrorRed();
                }
            })
            .then(function () {
                estado.enviando = false;
                mostrarTyping(false);
            });
    }

    // --- Historial visual ----------------------------------------------------

    function cargarHistorialVisual() {
        estado.historialCargado = true;
        var items = leerHistorial();
        if (!items.length) {
            agregarBurbuja(SALUDO, 'bot', false);
            return;
        }
        items.forEach(function (item) {
            MENSAJES.appendChild(crearBurbuja(item.m, item.t));
        });
        scrollAbajo();
    }

    // --- Abrir / cerrar ------------------------------------------------------

    function abrirPanel() {
        estado.abierto = true;
        PANEL.classList.remove('hidden');
        LAUNCHER.setAttribute('aria-expanded', 'true');
        if (!estado.historialCargado) cargarHistorialVisual();
        INPUT.focus();
    }

    function cerrarPanel() {
        estado.abierto = false;
        PANEL.classList.add('hidden');
        LAUNCHER.setAttribute('aria-expanded', 'false');
        LAUNCHER.focus();
    }

    LAUNCHER.addEventListener('click', function () {
        if (estado.abierto) cerrarPanel();
        else abrirPanel();
    });

    BTN_CERRAR.addEventListener('click', cerrarPanel);

    document.addEventListener('keydown', function (evento) {
        if (evento.key === 'Escape' && estado.abierto) cerrarPanel();
    });

    FORM.addEventListener('submit', function (evento) {
        evento.preventDefault();
        enviar(INPUT.value, false);
    });
})();
