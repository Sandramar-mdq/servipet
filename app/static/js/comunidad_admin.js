/* Panel de moderacion de la Red Comunitaria - Etapa 7.4 */
(function () {
    'use strict';

    var dataEl = document.getElementById('comunidad-admin-data');
    if (!dataEl) return;

    var COMERCIO_ID = parseInt(dataEl.dataset.comercioId, 10) || 1;
    var ES_ADMIN = dataEl.dataset.esAdmin === 'true';

    var API_BASE = '/api/v1/comunidad';
    var LIMIT = 20;

    var estado = { filtro: '', offset: 0, total: 0, cargando: false };

    var elLista = document.getElementById('admin-lista');
    var elCargando = document.getElementById('admin-cargando');
    var elVacio = document.getElementById('admin-vacio');
    var btnCargarMas = document.getElementById('btn-cargar-mas-admin');
    var switchOptin = document.getElementById('switch-optin');
    var optinError = document.getElementById('optin-error');
    var optinDescripcion = document.getElementById('optin-descripcion');

    var BADGES = {
        'PERDIDA': { label: 'Perdido', clases: 'bg-red-100 text-red-700 border-red-200' },
        'ENCONTRADA': { label: 'Encontrado', clases: 'bg-amber-100 text-amber-800 border-amber-200' },
        'ADOPCION': { label: 'Adopción', clases: 'bg-emerald-100 text-emerald-700 border-emerald-200' },
        'CUMPLEAÑOS': { label: 'Cumpleaños', clases: 'bg-violet-100 text-violet-700 border-violet-200' },
        'AVISO_BARRIAL': { label: 'Aviso barrial', clases: 'bg-sky-100 text-sky-700 border-sky-200' }
    };

    var CHIPS_ESTADO = {
        'ACTIVO': 'bg-green-100 text-green-700 border-green-200',
        'RESUELTO': 'bg-gray-100 text-gray-500 border-gray-200',
        'ARCHIVADO': 'bg-orange-100 text-orange-700 border-orange-200'
    };

    function escapeHtml(texto) {
        var div = document.createElement('div');
        div.textContent = texto == null ? '' : String(texto);
        return div.innerHTML;
    }

    function formatearFecha(iso) {
        try {
            return new Date(iso).toLocaleDateString('es-AR', { day: 'numeric', month: 'short', year: 'numeric' });
        } catch (e) {
            return '';
        }
    }

    function mostrarEstado(nombre) {
        elCargando.classList.toggle('hidden', nombre !== 'cargando');
        elVacio.classList.toggle('hidden', nombre !== 'vacio');
        if (nombre !== 'lista') {
            elLista.innerHTML = '';
            btnCargarMas.classList.add('hidden');
        }
    }

    function renderCard(aviso) {
        var badge = BADGES[aviso.tipo] || { label: aviso.tipo, clases: 'bg-gray-100 text-gray-600 border-gray-200' };
        var chip = CHIPS_ESTADO[aviso.estado] || CHIPS_ESTADO.ACTIVO;
        var activo = aviso.estado === 'ACTIVO';

        var html = '';
        html += '<article class="bg-white rounded-2xl border border-gray-200 shadow-sm p-4" data-aviso-id="' + aviso.id + '">';
        html += '<div class="flex gap-3">';

        if (aviso.foto_url) {
            html += '<img src="' + escapeHtml(aviso.foto_url) + '" alt="" loading="lazy" class="w-16 h-16 rounded-xl object-cover shrink-0">';
        }

        html += '<div class="min-w-0 flex-1">';
        html += '<div class="flex items-center gap-2 flex-wrap mb-1">';
        html += '<span class="inline-flex px-2 py-0.5 rounded-full text-xs font-semibold border ' + badge.clases + '">' + escapeHtml(badge.label) + '</span>';
        html += '<span class="inline-flex px-2 py-0.5 rounded-full text-xs font-semibold border ' + chip + '">' + escapeHtml(aviso.estado) + '</span>';
        html += '<span class="text-xs text-gray-400 ml-auto">' + escapeHtml(formatearFecha(aviso.fecha_publicacion)) + '</span>';
        html += '</div>';
        html += '<h3 class="font-bold text-gray-800 text-sm leading-snug truncate">#' + aviso.id + ' · ' + escapeHtml(aviso.titulo) + '</h3>';
        html += '<p class="text-sm text-gray-600 mt-1 line-clamp-2">' + escapeHtml(aviso.descripcion) + '</p>';
        if (aviso.telefono_contacto) {
            html += '<p class="text-xs text-gray-400 mt-1">Contacto: ' + escapeHtml(aviso.telefono_contacto) + ' (' + escapeHtml(aviso.tipo_contacto === 'DIRECTO_WHATSAPP' ? 'directo' : 'vía comercio') + ')</p>';
        }
        html += '</div>';

        html += '<div class="flex flex-col gap-2 shrink-0">';
        if (activo) {
            html += '<button type="button" data-accion="resolver" data-id="' + aviso.id + '" class="px-3 py-1.5 rounded-xl text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100 active:bg-emerald-200 transition">✓ Resuelto</button>';
            html += '<button type="button" data-accion="archivar" data-id="' + aviso.id + '" class="px-3 py-1.5 rounded-xl text-xs font-semibold bg-orange-50 text-orange-700 border border-orange-200 hover:bg-orange-100 active:bg-orange-200 transition">📦 Archivar</button>';
        } else if (aviso.estado !== 'ACTIVO') {
            html += '<button type="button" data-accion="reactivar" data-id="' + aviso.id + '" class="px-3 py-1.5 rounded-xl text-xs font-semibold bg-indigo-50 text-indigo-600 border border-indigo-200 hover:bg-indigo-100 active:bg-indigo-200 transition">↺ Reactivar</button>';
        }
        html += '<button type="button" data-accion="eliminar" data-id="' + aviso.id + '" class="px-3 py-1.5 rounded-xl text-xs font-semibold bg-red-50 text-red-600 border border-red-200 hover:bg-red-100 active:bg-red-200 transition">🗑 Eliminar</button>';
        html += '</div>';

        html += '</div></article>';
        return html;
    }

    function actualizarPaginacion() {
        btnCargarMas.classList.toggle('hidden', estado.offset + LIMIT >= estado.total);
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

        var params = new URLSearchParams({ limit: LIMIT, offset: estado.offset });
        if (estado.filtro) params.set('estado', estado.filtro);

        fetch(API_BASE + '/admin/' + COMERCIO_ID + '/avisos?' + params.toString())
            .then(function (resp) {
                if (resp.status === 401) {
                    window.location.href = '/auth/login';
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

                if (estado.total === 0 && reset) {
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

    // --- Filtros por estado ---
    document.querySelectorAll('.filtro-estado').forEach(function (tab) {
        tab.addEventListener('click', function () {
            document.querySelectorAll('.filtro-estado').forEach(function (t) {
                t.classList.remove('bg-indigo-600', 'text-white', 'border-indigo-600');
                t.classList.add('bg-white', 'text-gray-600', 'border-gray-300');
            });
            tab.classList.remove('bg-white', 'text-gray-600', 'border-gray-300');
            tab.classList.add('bg-indigo-600', 'text-white', 'border-indigo-600');

            estado.filtro = tab.dataset.estado;
            cargar(true);
        });
    });

    // --- Paginacion ---
    btnCargarMas.addEventListener('click', function () { cargar(false); });

    // --- Acciones de moderacion (delegacion) ---
    elLista.addEventListener('click', function (event) {
        var boton = event.target.closest('[data-accion]');
        if (!boton) return;
        var id = boton.dataset.id;
        var accion = boton.dataset.accion;

        var nuevoEstado = null;
        if (accion === 'resolver') nuevoEstado = 'RESUELTO';
        if (accion === 'archivar') nuevoEstado = 'ARCHIVADO';
        if (accion === 'reactivar') nuevoEstado = 'ACTIVO';

        if (nuevoEstado) {
            fetch(API_BASE + '/avisos/' + id + '/estado', {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ estado: nuevoEstado })
            }).then(function (resp) {
                if (resp.ok) cargar(false);
            }).catch(function () {});
        }

        if (accion === 'eliminar') {
            if (!window.confirm('¿Eliminar el aviso #' + id + ' definitivamente?')) return;
            fetch(API_BASE + '/avisos/' + id, { method: 'DELETE' })
                .then(function (resp) {
                    if (resp.status === 204) cargar(false);
                })
                .catch(function () {});
        }
    });

    // --- Switch Opt-In ---
    if (switchOptin && ES_ADMIN) {
        switchOptin.addEventListener('change', function () {
            var habilitar = switchOptin.checked;
            optinError.classList.add('hidden');
            switchOptin.disabled = true;

            // El router de comercios esta montado en /comercios (sin prefijo /api/v1)
            fetch('/comercios/' + COMERCIO_ID + '/opt-in', {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ habilitar_red_comunitaria: habilitar })
            })
                .then(function (resp) {
                    if (!resp.ok) throw new Error('HTTP ' + resp.status);
                    return resp.json();
                })
                .then(function (comercio) {
                    optinDescripcion.textContent = comercio.habilitar_red_comunitaria
                        ? 'Activada: los clientes ven el feed y pueden publicar avisos.'
                        : 'Desactivada: la comunidad está oculta para los clientes.';
                })
                .catch(function (err) {
                    switchOptin.checked = !habilitar; // revertir
                    optinError.textContent = 'No se pudo actualizar la configuración. Intentá de nuevo.';
                    optinError.classList.remove('hidden');
                    if (window.console && console.error) console.error('opt-in:', err);
                })
                .finally(function () {
                    switchOptin.disabled = false;
                });
        });
    }

    // --- Inicio ---
    cargar(true);
})();
