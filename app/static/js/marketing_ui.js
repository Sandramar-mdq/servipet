/* Utilidades compartidas del Modulo Solidario / Cumpleanos / Kit Marketing.
 *
 * Unica pieza de plumbing que usan `comunidad_admin.js`,
 * `marketing_dashboard.js` y `marketing_kit.js`:
 *
 *   - Descarga de piezas binarias (PDF / PNG) via fetch + Blob, porque los
 *     endpoints de `/api/v1/marketing` devuelven `Content-Disposition:
 *     attachment` y hay que poder reaccionar a un 409 antes de descargar.
 *   - Toasts accesibles (el proyecto no tenia ninguno).
 *   - Modales con foco atrapado, siguiendo el patron de `cliente/comunidad.html`.
 *
 * La autenticacion staff viaja por la cookie `access_token`: el fetch es
 * same-origin, asi que no hace falta header Authorization.
 */
(function () {
    'use strict';

    var API = '/api/v1/marketing';

    // ------------------------------------------------------------------
    // Toasts
    // ------------------------------------------------------------------

    var contenedorToast = null;

    function obtenerContenedorToast() {
        if (contenedorToast && document.body.contains(contenedorToast)) return contenedorToast;

        contenedorToast = document.createElement('div');
        contenedorToast.id = 'marketing-toasts';
        contenedorToast.setAttribute('role', 'status');
        contenedorToast.setAttribute('aria-live', 'polite');
        contenedorToast.className = 'fixed z-[60] bottom-4 inset-x-0 px-4 pointer-events-none flex flex-col items-center gap-2';
        contenedorToast.style.bottom = 'calc(1rem + env(safe-area-inset-bottom))';
        document.body.appendChild(contenedorToast);
        return contenedorToast;
    }

    var ESTILOS_TOAST = {
        exito: 'bg-emerald-600 text-white',
        error: 'bg-red-600 text-white',
        info: 'bg-gray-800 text-white'
    };

    function mostrarToast(mensaje, tipo) {
        if (!mensaje) return;
        var contenedor = obtenerContenedorToast();

        var toast = document.createElement('div');
        toast.className = 'pointer-events-auto max-w-xl w-full sm:w-auto px-4 py-3 rounded-2xl shadow-lg text-sm font-medium ' +
            (ESTILOS_TOAST[tipo] || ESTILOS_TOAST.info);
        toast.textContent = mensaje;
        contenedor.appendChild(toast);

        window.setTimeout(function () {
            if (toast.parentNode) toast.parentNode.removeChild(toast);
        }, 4500);
    }

    // ------------------------------------------------------------------
    // Descarga de piezas
    // ------------------------------------------------------------------

    function nombreDesdeDisposicion(resp, porDefecto) {
        var cabecera = resp.headers.get('Content-Disposition') || '';
        var coincidencia = /filename="?([^";]+)"?/i.exec(cabecera);
        return coincidencia ? coincidencia[1] : porDefecto;
    }

    function guardarBlob(blob, nombre) {
        var url = URL.createObjectURL(blob);
        var enlace = document.createElement('a');
        enlace.href = url;
        enlace.download = nombre;
        document.body.appendChild(enlace);
        enlace.click();
        document.body.removeChild(enlace);
        window.setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
    }

    /**
     * Descarga una pieza de `/api/v1/marketing`.
     *
     * @param {string} ruta  Path completo, ej. '/solidaridad/avisos/1/cartel.pdf'.
     * @param {object} [opciones]
     * @param {string} [opciones.metodo]      'GET' (default) o 'POST'.
     * @param {object} [opciones.body]       Payload JSON (solo POST).
     * @param {boolean}[opciones.forzar]     Agrega `forzar=1` al query string.
     * @param {string} [opciones.nombre]     Nombre de archivo por defecto.
     * @returns {Promise<{ok: boolean, estado: string, detalle: string}>}
     *          `estado` es 'ok' | 'duplicado' | 'deshabilitado' |
     *          'no-encontrado' | 'permisos' | 'sesion' | 'validacion' | 'error'.
     */
    function descargarPieza(ruta, opciones) {
        opciones = opciones || {};

        var url = API + ruta;
        if (opciones.forzar) {
            url += (ruta.indexOf('?') === -1 ? '?' : '&') + 'forzar=1';
        }

        var config = { method: opciones.metodo || 'GET' };
        if (opciones.body !== undefined) {
            config.headers = { 'Content-Type': 'application/json' };
            config.body = JSON.stringify(opciones.body);
        }

        return fetch(url, config)
            .then(function (resp) {
                if (resp.ok) {
                    var nombre = nombreDesdeDisposicion(resp, opciones.nombre || 'pieza.png');
                    return resp.blob().then(function (blob) {
                        guardarBlob(blob, nombre);
                        return { ok: true, estado: 'ok', detalle: '' };
                    });
                }

                return resp.json()
                    .catch(function () { return {}; })
                    .then(function (cuerpo) {
                        var detalle = (cuerpo && cuerpo.detail) ? cuerpo.detail : 'Error ' + resp.status;
                        if (typeof detalle !== 'string') detalle = 'Datos invalidos: revisa el formulario.';
                        return { ok: false, estado: estadoDesdeCodigo(resp.status), detalle: detalle };
                    });
            })
            .catch(function () {
                return { ok: false, estado: 'error', detalle: 'Error de conexion. Intenta de nuevo.' };
            });
    }

    function estadoDesdeCodigo(codigo) {
        if (codigo === 409) return 'duplicado';
        if (codigo === 403) return 'deshabilitado';
        if (codigo === 401) return 'sesion';
        if (codigo === 404) return 'no-encontrado';
        if (codigo === 422) return 'validacion';
        return 'error';
    }

    /**
     * `descargarPieza` + confirmacion ante duplicado (409) reintentando con
     * `forzar=1`. De esta forma el 409 -que es un resultado esperado por el
     * control anti-duplicado- se resuelve con un click, no con un error.
     */
    function descargarConRefuerzo(ruta, opciones) {
        opciones = opciones || {};
        return descargarPieza(ruta, opciones).then(function (resultado) {
            if (resultado.ok || resultado.estado !== 'duplicado') return resultado;

            var regenerar = window.confirm(
                resultado.detalle + '\n\n' +
                'Deseas regenerarla de todos modos? Se reemplaza el registro anterior.'
            );
            if (!regenerar) return resultado;

            var reforzado = {};
            for (var clave in opciones) {
                if (Object.prototype.hasOwnProperty.call(opciones, clave)) reforzado[clave] = opciones[clave];
            }
            reforzado.forzar = true;
            return descargarPieza(ruta, reforzado);
        });
    }

    // ------------------------------------------------------------------
    // Modales accesibles
    // ------------------------------------------------------------------

    var FOCO_SELECTOR = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
    var modalAbierto = null;

    function elementosFocales(modal) {
        return Array.prototype.slice.call(modal.querySelectorAll(FOCO_SELECTOR))
            .filter(function (el) { return el.offsetParent !== null; });
    }

    function abrirModal(modal) {
        if (!modal) return;
        modal.__retornoFoco = document.activeElement;
        modal.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
        modalAbierto = modal;

        var foco = elementosFocales(modal)[0];
        if (foco) foco.focus();
    }

    function cerrarModal(modal) {
        if (!modal) return;
        modal.classList.add('hidden');
        document.body.style.overflow = '';
        if (modalAbierto === modal) modalAbierto = null;

        var retorno = modal.__retornoFoco;
        modal.__retornoFoco = null;
        if (retorno && typeof retorno.focus === 'function') retorno.focus();
    }

    function alPresionarTecla(event) {
        if (!modalAbierto) return;

        if (event.key === 'Escape') {
            cerrarModal(modalAbierto);
            return;
        }
        if (event.key !== 'Tab') return;

        var focales = elementosFocales(modalAbierto);
        if (focales.length === 0) return;

        var primero = focales[0];
        var ultimo = focales[focales.length - 1];

        if (event.shiftKey && document.activeElement === primero) {
            event.preventDefault();
            ultimo.focus();
        } else if (!event.shiftKey && document.activeElement === ultimo) {
            event.preventDefault();
            primero.focus();
        }
    }

    document.addEventListener('keydown', alPresionarTecla);

    // Cualquier elemento con `data-cerrar-modal` cierra su modal contenedor.
    document.addEventListener('click', function (event) {
        var disparador = event.target.closest('[data-cerrar-modal]');
        if (!disparador) return;
        var modal = disparador.closest('[role="dialog"]');
        if (modal) cerrarModal(modal);
    });

    // ------------------------------------------------------------------
    // Formularios
    // ------------------------------------------------------------------

    /**
     * PATCH del opt-in de modulos del comercio. Solo se envian las claves
     * presentes en `flags`; las ausentes las ignora el backend (semantica
     * patch) y no pisan el estado del otro modulo.
     */
    function guardarOptIn(comercioId, flags) {
        var cuerpo = {};
        ['habilitar_red_comunitaria', 'habilitar_modulo_solidario', 'habilitar_cumpleanos'].forEach(function (clave) {
            if (flags[clave] !== undefined) {
                cuerpo[clave] = flags[clave];
            }
        });

        return fetch('/comercios/' + comercioId + '/opt-in', {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(cuerpo)
        }).then(function (resp) {
            if (resp.status === 401) {
                window.location.href = '/login';
                return null;
            }
            if (!resp.ok) throw new Error('HTTP ' + resp.status);
            return resp.json();
        });
    }

    /** Normaliza a `#RRGGBB` mayuscula (lo que espera PromocionCreate). */
    function normalizarColor(valor) {
        return (valor || '').trim().toUpperCase();
    }

    function colorValido(valor) {
        return /^#[0-9A-F]{6}$/.test(normalizarColor(valor));
    }

    function escapeHtml(texto) {
        var div = document.createElement('div');
        div.textContent = texto == null ? '' : String(texto);
        return div.innerHTML;
    }

    // ------------------------------------------------------------------
    // Modal de beneficio (cumpleanos)
    // ------------------------------------------------------------------

    var BENEFICIO_MAX = 200;
    var modalBeneficioActivo = null;

    function crearModalBeneficio() {
        if (modalBeneficioActivo && document.body.contains(modalBeneficioActivo)) {
            return modalBeneficioActivo;
        }

        var overlay = document.createElement('div');
        overlay.id = 'modal-beneficio';
        overlay.setAttribute('role', 'dialog');
        overlay.setAttribute('aria-modal', 'true');
        overlay.setAttribute('aria-labelledby', 'modal-beneficio-titulo');
        overlay.className = 'hidden fixed inset-0 z-[70] bg-black/50 flex items-end sm:items-center justify-center p-0 sm:p-4';

        overlay.innerHTML =
            '<div class="bg-white w-full sm:max-w-md rounded-t-3xl sm:rounded-3xl p-5 max-h-[90vh] overflow-y-auto">' +
            '  <h2 id="modal-beneficio-titulo" class="text-lg font-bold text-gray-800 mb-1"></h2>' +
            '  <p class="text-sm text-gray-500 mb-4">Texto que se imprime en la placa. Maximo ' + BENEFICIO_MAX + ' caracteres.</p>' +
            '  <label for="modal-beneficio-input" class="block text-sm font-medium text-gray-700 mb-1">Beneficio</label>' +
            '  <textarea id="modal-beneficio-input" rows="3" maxlength="' + BENEFICIO_MAX + '" ' +
            '            class="w-full border border-gray-300 rounded-xl px-3 py-2 text-sm focus:ring-2 focus:outline-none" style="--tw-ring-color: var(--color-primario);"></textarea>' +
            '  <p id="modal-beneficio-ayuda" class="text-xs text-gray-500 mt-1"></p>' +
            '  <label id="modal-beneficio-fila-forzar" class="hidden items-center gap-2 mt-3 text-sm text-gray-700">' +
            '    <input type="checkbox" id="modal-beneficio-forzar" class="w-4 h-4 rounded border-gray-300">' +
            '    <span>Regenerar aunque ya se haya enviado este ano</span>' +
            '  </label>' +
            '  <div class="flex gap-2 mt-5">' +
            '    <button type="button" data-cerrar-modal ' +
            '            class="flex-1 bg-gray-100 text-gray-700 font-semibold py-3 rounded-2xl text-sm hover:bg-gray-200 transition">Cancelar</button>' +
            '    <button type="button" id="modal-beneficio-ok" ' +
            '            class="flex-1 bg-[var(--color-primario)] text-[var(--texto-sobre-primario)] font-semibold py-3 rounded-2xl text-sm hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition">Generar</button>' +
            '  </div>' +
            '</div>';

        overlay.addEventListener('click', function (event) {
            if (event.target === overlay) cerrarModal(overlay);
        });
        document.body.appendChild(overlay);
        modalBeneficioActivo = overlay;
        return overlay;
    }

    /**
     * Abre el modal de beneficio y resuelve con `{beneficio, forzar}` al
     * confirmar, o `null` si el usuario cancela.
     *
     * @param {object} opciones
     * @param {string} opciones.titulo        Encabezado del modal.
     * @param {string} [opciones.beneficio]   Valor inicial (editable).
     * @param {boolean}[opciones.yaEnviado]  Muestra el check de regeneración.
     */
    function modalBeneficio(opciones) {
        opciones = opciones || {};

        var modal = crearModalBeneficio();
        var input = modal.querySelector('#modal-beneficio-input');
        var ayuda = modal.querySelector('#modal-beneficio-ayuda');
        var filaForzar = modal.querySelector('#modal-beneficio-fila-forzar');
        var checkForzar = modal.querySelector('#modal-beneficio-forzar');
        var botonOk = modal.querySelector('#modal-beneficio-ok');

        modal.querySelector('#modal-beneficio-titulo').textContent = opciones.titulo || 'Generar placa';
        input.value = opciones.beneficio || '';
        checkForzar.checked = false;

        filaForzar.classList.toggle('hidden', !opciones.yaEnviado);
        filaForzar.classList.toggle('flex', !!opciones.yaEnviado);
        ayuda.textContent = (opciones.beneficio || '').length + ' / ' + BENEFICIO_MAX + ' caracteres';

        // El overlay se reutiliza entre llamadas: se asignan handlers en vez de
        // acumular listeners con addEventListener sobre los mismos nodos.
        input.oninput = function () {
            ayuda.textContent = input.value.length + ' / ' + BENEFICIO_MAX + ' caracteres';
        };

        return new Promise(function (resolver) {
            var resuelto = false;

            function finalizar(resultado) {
                if (resuelto) return;
                resuelto = true;
                cerrarModal(modal);
                botonOk.disabled = false;
                botonOk.textContent = 'Generar';
                resolver(resultado);
            }

            function confirmar() {
                botonOk.disabled = true;
                botonOk.textContent = 'Generando...';
                finalizar({ beneficio: input.value.trim(), forzar: checkForzar.checked });
            }

            function alEnter(event) {
                if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) confirmar();
            }

            botonOk.onclick = confirmar;
            input.onkeydown = alEnter;
            modal.onclick = function (event) {
                if (event.target.closest('[data-cerrar-modal]')) finalizar(null);
            };

            // `cerrarModal` (Escape o click en el overlay) no emite eventos, asi
            // que se observa la clase para resolver la promesa como cancelada.
            if (modal.__observador) modal.__observador.disconnect();
            var observador = new MutationObserver(function () {
                if (modal.classList.contains('hidden')) {
                    observador.disconnect();
                    finalizar(null);
                }
            });
            modal.__observador = observador;
            observador.observe(modal, { attributes: true, attributeFilter: ['class'] });
        });
    }

    window.ServipetMarketing = {
        API: API,
        descargarPieza: descargarPieza,
        descargarConRefuerzo: descargarConRefuerzo,
        mostrarToast: mostrarToast,
        abrirModal: abrirModal,
        cerrarModal: cerrarModal,
        modalBeneficio: modalBeneficio,
        guardarOptIn: guardarOptIn,
        normalizarColor: normalizarColor,
        colorValido: colorValido,
        escapeHtml: escapeHtml
    };
})();
