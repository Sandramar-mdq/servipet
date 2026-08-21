/* Feed Comunitario Servipet - PWA cliente (Etapa 7.3) */
(function () {
    'use strict';

    var dataEl = document.getElementById('comunidad-data');
    if (!dataEl) return;

    var COMERCIO_ID = parseInt(dataEl.dataset.comercioId, 10) || 1;
    var TELEFONO_COMERCIO = (dataEl.dataset.telefonoComercio || '').replace(/\D/g, '');
    var ACTOR = {};
    try {
        ACTOR = JSON.parse(dataEl.dataset.actor || '{}') || {};
    } catch (e) {
        ACTOR = {};
    }

    var API_BASE = '/api/v1/comunidad';
    var LIMIT = 10;

    var estado = { tipo: 'TODOS', offset: 0, total: 0, cargando: false };

    var elLista = document.getElementById('feed-lista');
    var elCargando = document.getElementById('feed-cargando');
    var elVacio = document.getElementById('feed-vacio');
    var elDeshabilitado = document.getElementById('feed-deshabilitado');
    var btnCargarMas = document.getElementById('btn-cargar-mas');
    var modal = document.getElementById('modal-aviso');
    var form = document.getElementById('form-nuevo-aviso');
    var campoTelefono = document.getElementById('campo-telefono');
    var inputTelefono = document.getElementById('aviso-telefono');
    var modalError = document.getElementById('modal-error');
    var btnPublicar = document.getElementById('btn-publicar');

    var BADGES = {
        'PERDIDA': { label: 'Perdido', clases: 'bg-red-100 text-red-700 border-red-200' },
        'ENCONTRADA': { label: 'Encontrado', clases: 'bg-amber-100 text-amber-800 border-amber-200' },
        'ADOPCION': { label: 'Adopción', clases: 'bg-emerald-100 text-emerald-700 border-emerald-200' },
        'CUMPLEAÑOS': { label: 'Cumpleaños', clases: 'bg-violet-100 text-violet-700 border-violet-200' },
        'AVISO_BARRIAL': { label: 'Aviso barrial', clases: 'bg-sky-100 text-sky-700 border-sky-200' }
    };

    function escapeHtml(texto) {
        var div = document.createElement('div');
        div.textContent = texto == null ? '' : String(texto);
        return div.innerHTML;
    }

    function mostrarEstado(nombre) {
        elCargando.classList.toggle('hidden', nombre !== 'cargando');
        elVacio.classList.toggle('hidden', nombre !== 'vacio');
        elDeshabilitado.classList.toggle('hidden', nombre !== 'deshabilitado');
        if (nombre !== 'lista') {
            elLista.innerHTML = '';
            btnCargarMas.classList.add('hidden');
        }
    }

    function soloDigitos(telefono) {
        return (telefono || '').replace(/\D/g, '');
    }

    function fechaRelativa(iso) {
        try {
            var fecha = new Date(iso);
            return fecha.toLocaleDateString('es-AR', { day: 'numeric', month: 'short', year: 'numeric' });
        } catch (e) {
            return '';
        }
    }

    function puedeGestionar(aviso) {
        if (!ACTOR.tipo) return false;
        if (ACTOR.es_staff) return true;
        if (ACTOR.tipo === 'cliente' && aviso.cliente_id != null && aviso.cliente_id === ACTOR.cliente_id) return true;
        if (ACTOR.usuario_id != null && aviso.creado_por_usuario_id === ACTOR.usuario_id) return true;
        return false;
    }

    function linkContacto(aviso) {
        if (aviso.tipo_contacto === 'DIRECTO_WHATSAPP') {
            var tel = soloDigitos(aviso.telefono_contacto);
            if (!tel) return null;
            var texto = 'Hola! Vi tu aviso #' + aviso.id + ' en la comunidad de Servipet';
            return { url: 'https://wa.me/' + tel + '?text=' + encodeURIComponent(texto), clases: 'bg-green-500 hover:bg-green-600 active:bg-green-700 text-white', icono: whatsappSvg(), texto: 'WhatsApp' };
        }
        // VIA_COMERCIO: consulta al WhatsApp del local
        if (!TELEFONO_COMERCIO) return null;
        var consulta = 'Hola! Consulto por el aviso #' + aviso.id + ': ' + aviso.titulo;
        return {
            url: 'https://wa.me/' + TELEFONO_COMERCIO + '?text=' + encodeURIComponent(consulta),
            clases: 'bg-blue-50 hover:bg-blue-100 active:bg-blue-200 text-blue-700 border border-blue-200',
            icono: comercioSvg(),
            texto: 'Consultar por el comercio'
        };
    }

    function whatsappSvg() {
        return '<svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path d="M12.04 2a9.9 9.9 0 00-8.5 14.95L2 22l5.2-1.5A9.9 9.9 0 1012.04 2zm0 18.1a8.1 8.1 0 01-4.13-1.13l-.3-.18-3.08.89.9-3-.2-.31a8.1 8.1 0 1112.5 1.02 8.05 8.05 0 01-5.69 2.71zm4.45-6.07c-.24-.12-1.44-.71-1.66-.79-.22-.08-.39-.12-.55.12s-.63.79-.77.95c-.14.16-.28.18-.52.06a6.62 6.62 0 01-1.95-1.2 7.3 7.3 0 01-1.35-1.68c-.14-.24-.02-.37.1-.49.11-.11.24-.28.36-.42.12-.14.16-.24.24-.4.08-.16.04-.3-.02-.42-.06-.12-.55-1.32-.75-1.81-.2-.48-.4-.41-.55-.42h-.47c-.16 0-.42.06-.64.3-.22.24-.84.82-.84 2s.86 2.32.98 2.48c.12.16 1.69 2.58 4.1 3.62.57.25 1.02.4 1.37.51.58.18 1.1.16 1.51.1.46-.07 1.42-.58 1.62-1.14.2-.56.2-1.04.14-1.14-.06-.1-.22-.16-.46-.28z"/></svg>';
    }

    function comercioSvg() {
        return '<svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"/></svg>';
    }

    function renderCard(aviso) {
        var badge = BADGES[aviso.tipo] || { label: aviso.tipo, clases: 'bg-gray-100 text-gray-600 border-gray-200' };
        var resuelto = aviso.estado === 'RESUELTO';
        var contacto = linkContacto(aviso);
        var gestionable = puedeGestionar(aviso);

        var html = '';
        html += '<article class="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden' + (resuelto ? ' opacity-80' : '') + '" data-aviso-id="' + aviso.id + '">';

        if (aviso.foto_url) {
            html += '<img src="' + escapeHtml(aviso.foto_url) + '" alt="' + escapeHtml(aviso.titulo) + '" loading="lazy" class="w-full max-h-72 object-cover">';
        }

        html += '<div class="p-4">';
        html += '<div class="flex items-center gap-2 flex-wrap mb-2">';
        html += '<span class="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold border ' + badge.clases + '">' + escapeHtml(badge.label) + '</span>';
        if (resuelto) {
            html += '<span class="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-gray-100 text-gray-500 border border-gray-200">Resuelto ✓</span>';
        }
        html += '<span class="text-xs text-gray-400 ml-auto">' + escapeHtml(fechaRelativa(aviso.fecha_publicacion)) + '</span>';
        html += '</div>';

        html += '<h3 class="font-bold text-gray-800 leading-snug">' + escapeHtml(aviso.titulo) + '</h3>';
        html += '<p class="text-sm text-gray-600 mt-1 whitespace-pre-line">' + escapeHtml(aviso.descripcion) + '</p>';

        html += '<div class="flex flex-wrap gap-2 mt-4">';

        if (!resuelto && contacto) {
            html += '<a href="' + escapeHtml(contacto.url) + '" target="_blank" rel="noopener noreferrer" ';
            html += 'class="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-semibold transition ' + contacto.clases + '">';
            html += contacto.icono + '<span>' + contacto.texto + '</span></a>';
        }

        if (gestionable && !resuelto) {
            html += '<button type="button" data-accion="resolver" data-id="' + aviso.id + '" ';
            html += 'class="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100 active:bg-emerald-200 transition">✓ Marcar resuelto</button>';
        }
        if (gestionable) {
            html += '<button type="button" data-accion="eliminar" data-id="' + aviso.id + '" ';
            html += 'class="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-semibold bg-red-50 text-red-600 border border-red-200 hover:bg-red-100 active:bg-red-200 transition">🗑 Eliminar</button>';
        }

        html += '</div></div></article>';
        return html;
    }

    function actualizarPaginacion() {
        var hayMas = estado.offset + LIMIT < estado.total;
        btnCargarMas.classList.toggle('hidden', !hayMas);
    }

    function cargar(reset) {
        if (estado.cargando) return;
        estado.cargando = true;

        if (reset) {
            estado.offset = 0;
            mostrarEstado('cargando');
        } else {
            btnCargarMas.disabled = true;
            btnCargarMas.textContent = 'Cargando...';
        }

        var params = new URLSearchParams({
            limit: LIMIT,
            offset: estado.offset,
            estado: 'ACTIVO'
        });
        if (estado.tipo !== 'TODOS') params.set('tipo', estado.tipo);

        fetch(API_BASE + '/' + COMERCIO_ID + '/avisos?' + params.toString())
            .then(function (resp) {
                if (resp.status === 403) {
                    mostrarEstado('deshabilitado');
                    return null;
                }
                if (!resp.ok) throw new Error('HTTP ' + resp.status);
                return resp.json();
            })
            .then(function (data) {
                if (!data) return;
                estado.total = data.total;

                if (reset) elLista.innerHTML = '';
                var fragmento = '';
                data.items.forEach(function (aviso) { fragmento += renderCard(aviso); });
                elLista.insertAdjacentHTML('beforeend', fragmento);

                if (estado.total === 0) {
                    mostrarEstado('vacio');
                } else {
                    mostrarEstado('lista');
                }

                estado.offset += data.items.length;
                actualizarPaginacion();
            })
            .catch(function () {
                if (reset) mostrarEstado('vacio');
            })
            .finally(function () {
                estado.cargando = false;
                btnCargarMas.disabled = false;
                btnCargarMas.textContent = 'Cargar más avisos';
            });
    }

    // --- Filtros ---
    document.querySelectorAll('.filtro-tab').forEach(function (tab) {
        tab.addEventListener('click', function () {
            document.querySelectorAll('.filtro-tab').forEach(function (t) {
                t.className = t.className
                    .replace('bg-indigo-600 text-white border-indigo-600', '')
                    .trim();
                t.classList.add('bg-white', 'text-gray-600', 'border-gray-300');
            });
            tab.classList.remove('bg-white', 'text-gray-600', 'border-gray-300');
            tab.classList.add('bg-indigo-600', 'text-white', 'border-indigo-600');

            estado.tipo = tab.dataset.tipo;
            cargar(true);
        });
    });

    // --- Paginacion ---
    btnCargarMas.addEventListener('click', function () { cargar(false); });

    // --- Acciones sobre cards (delegacion) ---
    elLista.addEventListener('click', function (event) {
        var boton = event.target.closest('[data-accion]');
        if (!boton) return;
        var id = boton.dataset.id;
        var accion = boton.dataset.accion;

        if (accion === 'resolver') {
            fetch(API_BASE + '/avisos/' + id + '/estado', {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ estado: 'RESUELTO' })
            }).then(function (resp) {
                if (resp.ok) cargar(true);
            }).catch(function () {});
        }

        if (accion === 'eliminar') {
            if (!window.confirm('¿Eliminar este aviso definitivamente?')) return;
            fetch(API_BASE + '/avisos/' + id, { method: 'DELETE' })
                .then(function (resp) {
                    if (resp.status === 204) cargar(true);
                })
                .catch(function () {});
        }
    });

    // --- Modal nuevo aviso ---
    window.abrirModalAviso = function () {
        modal.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
    };

    function cerrarModal() {
        modal.classList.add('hidden');
        document.body.style.overflow = '';
        modalError.classList.add('hidden');
    }

    var btnNuevo = document.getElementById('btn-nuevo-aviso');
    if (btnNuevo) btnNuevo.addEventListener('click', abrirModalAviso);

    modal.querySelectorAll('[data-cerrar-modal]').forEach(function (el) {
        el.addEventListener('click', cerrarModal);
    });

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' && !modal.classList.contains('hidden')) cerrarModal();
    });

    // Toggle del telefono segun tipo de contacto
    document.querySelectorAll('input[name="tipo_contacto"]').forEach(function (radio) {
        radio.addEventListener('change', function () {
            var directo = this.value === 'DIRECTO_WHATSAPP';
            campoTelefono.classList.toggle('hidden', !directo);
            inputTelefono.required = directo;
            if (!directo) inputTelefono.value = '';
        });
    });

    // Envio del formulario
    form.addEventListener('submit', function (event) {
        event.preventDefault();
        modalError.classList.add('hidden');
        btnPublicar.disabled = true;
        btnPublicar.textContent = 'Publicando...';

        var datos = new FormData(form);
        var imagen = document.getElementById('aviso-imagen').files[0];
        if (!imagen) datos.delete('imagen');

        fetch(API_BASE + '/' + COMERCIO_ID + '/avisos', { method: 'POST', body: datos })
            .then(function (resp) {
                if (resp.status === 201) {
                    form.reset();
                    campoTelefono.classList.add('hidden');
                    inputTelefono.required = false;
                    cerrarModal();
                    cargar(true);
                    return null;
                }
                if (resp.status === 401) {
                    window.location.href = '/cliente/login';
                    return null;
                }
                return resp.json().catch(function () { return {}; }).then(function (err) {
                    var detalle = typeof err.detail === 'string' ? err.detail : 'No se pudo publicar el aviso. Revisá los datos.';
                    modalError.textContent = detalle;
                    modalError.classList.remove('hidden');
                    return null;
                });
            })
            .catch(function () {
                modalError.textContent = 'Error de conexión. Intentá de nuevo.';
                modalError.classList.remove('hidden');
            })
            .finally(function () {
                btnPublicar.disabled = false;
                btnPublicar.textContent = 'Publicar';
            });
    });

    // --- Inicio ---
    cargar(true);
})();
