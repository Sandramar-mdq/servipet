/* Widget "Proximos Cumpleanos" del dashboard del comercio (Etapa 12).
 *
 * Consume `GET /api/v1/marketing/cumpleanos/proximos`, que solo devuelve
 * mascotas activas, vivas y con consentimiento explicito del cliente, y
 * genera la placa cuadrada 1:1 via `marketing_ui.descargarConRefuerzo`.
 *
 * Estados manejados: opt-in apagado (403), SuperAdmin sin comercio (400) y
 * sesion expirada (401).
 */
(function () {
    'use strict';

    var dataEl = document.getElementById('cumpleanos-data');
    if (!dataEl || !window.ServipetMarketing) return;

    var MKT = window.ServipetMarketing;
    var DIAS = parseInt(dataEl.dataset.dias, 10) || 7;
    var ES_ADMIN = dataEl.dataset.esAdmin === 'true';

    var seccion = document.getElementById('widget-cumpleanos');
    var elCargando = document.getElementById('cumple-cargando');
    var elVacio = document.getElementById('cumple-vacio');
    var elDeshabilitado = document.getElementById('cumple-deshabilitado');
    var elLista = document.getElementById('cumple-lista');
    var btnConfig = document.getElementById('cumpleanos-config');
    var tabs = Array.prototype.slice.call(document.querySelectorAll('.tab-cumpleanos'));

    document.getElementById('cumple-vacio-dias').textContent = DIAS;

    function marcarTab(dias) {
        tabs.forEach(function (tab) {
            var activo = parseInt(tab.dataset.dias, 10) === dias;
            tab.setAttribute('aria-selected', activo ? 'true' : 'false');
            tab.classList.toggle('border-[var(--color-primario)]', activo);
            tab.classList.toggle('bg-[var(--color-primario)]', activo);
            tab.classList.toggle('text-[var(--texto-sobre-primario)]', activo);
            tab.classList.toggle('border-transparent', activo);
            tab.classList.toggle('shadow-sm', activo);
            tab.classList.toggle('text-gray-500', !activo);
        });
    }

    tabs.forEach(function (tab) {
        tab.addEventListener('click', function () {
            var dias = parseInt(tab.dataset.dias, 10) || 7;
            if (dias === DIAS) return;
            DIAS = dias;
            marcarTab(DIAS);
            document.getElementById('cumple-vacio-dias').textContent = DIAS;
            cargar(false);
        });
    });

    marcarTab(DIAS);

    function mostrarEstado(nombre) {
        seccion.setAttribute('aria-busy', nombre === 'cargando' ? 'true' : 'false');
        elCargando.classList.toggle('hidden', nombre !== 'cargando');
        elVacio.classList.toggle('hidden', nombre !== 'vacio');
        elDeshabilitado.classList.toggle('hidden', nombre !== 'deshabilitado');
        elLista.classList.toggle('hidden', nombre !== 'lista');
        if (nombre !== 'lista') elLista.innerHTML = '';
    }

    function fechaCumple(item) {
        try {
            return new Date(item.fecha_nacimiento).toLocaleDateString('es-AR', {
                day: 'numeric', month: 'long'
            });
        } catch (e) {
            return '';
        }
    }

    function cuandoCumple(item) {
        if (item.dias_para === 0) return 'Cumple hoy';
        if (item.dias_para === 1) return 'Cumple manana';
        return 'Cumple en ' + item.dias_para + ' dias';
    }

    function iniciales(item) {
        var letra = (item.nombre || '?').trim().charAt(0).toUpperCase();
        return MKT.escapeHtml(letra);
    }

    function enlaceTelefono(item) {
        var telefono = (item.cliente_telefono || '').trim();
        if (!telefono) return '<span class="text-sm text-gray-500">Sin telefono</span>';
        var digitos = telefono.replace(/\D/g, '');
        if (!digitos) return MKT.escapeHtml(telefono);
        return '<a href="https://wa.me/' + digitos + '" target="_blank" rel="noopener" ' +
            'class="text-sm font-semibold text-emerald-600 hover:underline">' +
            MKT.escapeHtml(telefono) + '</a>';
    }

    function enlaceKit(item) {
        var url = '/page/marketing?mascota_id=' + encodeURIComponent(String(item.mascota_id)) +
            '&titulo=' + encodeURIComponent('Feliz Cumpleanos ' + item.nombre) +
            '&beneficio=' + encodeURIComponent(item.beneficio);
        return '<a href="' + url + '" ' +
            'class="shrink-0 px-3 py-2 rounded-xl text-sm font-medium border border-[var(--color-primario)] ' +
            'text-[var(--color-primario)] hover:opacity-90 active:opacity-80 transition">Abrir en Kit</a>';
    }

    function renderItem(item) {
        // La API devuelve `foto_webp` en base64 crudo, sin el prefijo data:.
        var foto = item.foto_webp
            ? '<img src="data:image/webp;base64,' + MKT.escapeHtml(item.foto_webp) + '" alt="" loading="lazy" class="w-12 h-12 rounded-xl object-cover shrink-0 border border-gray-200">'
            : '<div class="w-12 h-12 rounded-xl bg-gray-100 text-gray-500 flex items-center justify-center font-bold shrink-0" aria-hidden="true">' + iniciales(item) + '</div>';

        var chipEnviado = item.ya_enviado
            ? '<span class="inline-block bg-gray-100 text-gray-600 border border-gray-200 text-xs font-semibold px-2 py-0.5 rounded-full">Ya enviada</span>'
            : '';

        return '<li class="bg-white rounded-2xl border border-gray-200 shadow-sm p-4 flex items-center gap-4 flex-wrap">' +
            foto +
            '<div class="min-w-0 flex-1">' +
            '  <div class="flex items-center gap-2 flex-wrap">' +
            '    <span class="font-bold text-gray-800 text-sm">' + MKT.escapeHtml(item.nombre) + '</span>' +
            chipEnviado +
            '  </div>' +
            '  <p class="text-xs text-gray-500 mt-0.5">' + MKT.escapeHtml(cuandoCumple(item)) +
            (fechaCumple(item) ? ' · ' + MKT.escapeHtml(fechaCumple(item)) : '') +
            (item.anios ? ' · ' + MKT.escapeHtml(String(item.anios)) + ' anios' : '') + '</p>' +
            '  <p class="text-sm mt-0.5 text-gray-800">' + MKT.escapeHtml(item.cliente_nombre) +
            '  · ' + enlaceTelefono(item) + '</p>' +
            '  <p class="text-sm mt-1 truncate text-[var(--color-primario)]">' + MKT.escapeHtml(item.beneficio) + '</p>' +
            '</div>' +
            '<div class="flex items-center gap-2 shrink-0 flex-wrap">' +
            enlaceKit(item) +
            '<button type="button" data-mascota="' + MKT.escapeHtml(String(item.mascota_id)) + '" ' +
            '        data-beneficio="' + MKT.escapeHtml(item.beneficio) + '" ' +
            '        data-nombre="' + MKT.escapeHtml(item.nombre) + '" ' +
            '        data-ya-enviado="' + (item.ya_enviado ? 'true' : 'false') + '" ' +
            '        class="px-4 py-2 rounded-xl text-sm font-semibold bg-[var(--color-primario)] ' +
            '               text-[var(--texto-sobre-primario)] hover:opacity-90 active:opacity-80 transition ' +
            '               disabled:opacity-50 disabled:cursor-not-allowed">Generar Placa</button>' +
            '</div>' +
            '</li>';
    }

    function generarPlaca(boton) {
        var id = boton.dataset.mascota;
        var nombre = boton.dataset.nombre || '';
        var original = boton.textContent;

        MKT.modalBeneficio({
            titulo: 'Placa de ' + nombre,
            beneficio: boton.dataset.beneficio,
            yaEnviado: boton.dataset.yaEnviado === 'true'
        }).then(function (opciones) {
            if (!opciones) return;

            boton.disabled = true;
            boton.textContent = 'Generando...';

            var ruta = '/cumpleanos/mascotas/' + encodeURIComponent(id) + '/placa.png';
            var params = [];
            if (opciones.beneficio) params.push('beneficio=' + encodeURIComponent(opciones.beneficio));
            if (opciones.forzar) params.push('forzar=1');
            if (params.length) ruta += '?' + params.join('&');

            return MKT.descargarPieza(ruta, { nombre: 'cumpleanos_' + id + '.png' })
                .then(function (resultado) {
                    if (resultado.ok) {
                        MKT.mostrarToast('Placa de ' + nombre + ' descargada.', 'exito');
                        cargar(true);
                    } else if (resultado.estado === 'sesion') {
                        window.location.href = '/login';
                    } else if (resultado.estado === 'duplicado') {
                        if (window.confirm(resultado.detalle + '\n\nDeseas regenerarla?')) {
                            boton.dataset.yaEnviado = 'true';
                            return generarPlaca(boton);
                        }
                    } else {
                        MKT.mostrarToast(resultado.detalle, 'error');
                    }
                })
                .finally(function () {
                    boton.disabled = false;
                    boton.textContent = original;
                });
        });
    }

    elLista.addEventListener('click', function (event) {
        var boton = event.target.closest('[data-mascota]');
        if (!boton) return;
        generarPlaca(boton);
    });

    // --- Configuracion del beneficio (solo ADMIN) ---
    if (btnConfig && ES_ADMIN) {
        btnConfig.classList.remove('hidden');
        btnConfig.addEventListener('click', function () {
            fetch(MKT.API + '/cumpleanos/config')
                .then(function (resp) {
                    if (!resp.ok) throw new Error('HTTP ' + resp.status);
                    return resp.json();
                })
                .then(function (config) {
                    MKT.modalBeneficio({
                        titulo: 'Beneficio por defecto (' + config.clientes_consentidos + ' clientes consentidos)',
                        beneficio: config.beneficio
                    }).then(function (opciones) {
                        if (!opciones || !opciones.beneficio) return;

                        btnConfig.disabled = true;
                        return fetch(MKT.API + '/cumpleanos/config', {
                            method: 'PUT',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ beneficio: opciones.beneficio })
                        }).then(function (resp) {
                            if (!resp.ok) throw new Error('HTTP ' + resp.status);
                            MKT.mostrarToast('Beneficio actualizado.', 'exito');
                        }).catch(function () {
                            MKT.mostrarToast('No se pudo actualizar el beneficio.', 'error');
                        }).finally(function () {
                            btnConfig.disabled = false;
                        });
                    });
                })
                .catch(function () {
                    MKT.mostrarToast('No se pudo leer la configuracion de cumpleanos.', 'error');
                });
        });
    }

    function cargar(silencioso) {
        if (!silencioso) mostrarEstado('cargando');

        fetch(MKT.API + '/cumpleanos/proximos?dias=' + DIAS)
            .then(function (resp) {
                if (resp.status === 401) {
                    window.location.href = '/login';
                    return null;
                }
                if (resp.status === 403) {
                    return resp.json().catch(function () { return {}; })
                        .then(function (err) { return { __estado: 'deshabilitado', detalle: err.detail }; });
                }
                if (resp.status === 400) {
                    return { __estado: 'superadmin', detalle: '' };
                }
                if (!resp.ok) throw new Error('HTTP ' + resp.status);
                return resp.json();
            })
            .then(function (data) {
                if (!data) return;

                if (data.__estado === 'deshabilitado') {
                    document.getElementById('cumple-deshabilitado-detalle').textContent =
                        data.detalle || 'Este comercio todavia no activo el modulo.';
                    mostrarEstado('deshabilitado');
                    return;
                }
                if (data.__estado === 'superadmin') {
                    document.getElementById('cumple-deshabilitado-detalle').textContent =
                        'Los cumpleanos se consultan por comercio: ingressa como administrador de un comercio para verlos.';
                    mostrarEstado('deshabilitado');
                    return;
                }

                if (!data.items || data.items.length === 0) {
                    mostrarEstado('vacio');
                    return;
                }

                var fragmento = '';
                data.items.forEach(function (item) { fragmento += renderItem(item); });
                elLista.innerHTML = fragmento;
                mostrarEstado('lista');
            })
            .catch(function () {
                if (!silencioso) mostrarEstado('vacio');
            });
    }

    cargar(false);
})();
