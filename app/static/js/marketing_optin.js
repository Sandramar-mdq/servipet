/* Opt-in de los modulos de Marketing en el panel de Personalizacion (Etapa 12).
 *
 * Sin `habilitar_modulo_solidario` / `habilitar_cumpleanos` activados, todos los
 * endpoints de `/api/v1/marketing` responden 403. Este panel es el unico lugar
 * de la UI donde se encienden.
 *
 * Al cambiar un switch se envía únicamente ese flag: `guardarOptIn` completa con
 * `null` el resto, y el endpoint lo trata como "no tocar".
 */
(function () {
    'use strict';

    var dataEl = document.getElementById('modulos-data');
    if (!dataEl || !window.ServipetMarketing) return;

    var MKT = window.ServipetMarketing;
    var COMERCIO_ID = parseInt(dataEl.dataset.comercioId, 10) || 1;

    var MODULOS = [
        {
            input: 'switch-solidario',
            descripcion: 'desc-solidario',
            flag: 'habilitar_modulo_solidario',
            activo: 'Activado: los avisos pueden generar cartel A4 y placa 9:16.',
            inactivo: 'Desactivado: no se pueden generar carteles ni placas de avisos.'
        },
        {
            input: 'switch-cumpleanos',
            descripcion: 'desc-cumpleanos',
            flag: 'habilitar_cumpleanos',
            activo: 'Activado: el dashboard muestra los proximos cumpleanos.',
            inactivo: 'Desactivado: no se listan ni generan placas de cumpleanos.'
        }
    ];

    function pintarDescripcion(modulo) {
        var el = document.getElementById(modulo.descripcion);
        if (!el) return;
        var checkbox = document.getElementById(modulo.input);
        el.textContent = checkbox.checked ? modulo.activo : modulo.inactivo;
        el.className = 'text-xs font-medium mt-1 ' + (checkbox.checked ? 'text-emerald-600' : 'text-gray-400');
    }

    function conectar(modulo) {
        var checkbox = document.getElementById(modulo.input);
        if (!checkbox) return;

        pintarDescripcion(modulo);

        checkbox.addEventListener('change', function () {
            var estado = checkbox.checked;
            var flags = {};
            flags[modulo.flag] = estado;

            checkbox.disabled = true;
            pintarDescripcion(modulo);

            MKT.guardarOptIn(COMERCIO_ID, flags)
                .then(function (comercio) {
                    if (!comercio) return;
                    pintarDescripcion(modulo);
                    MKT.mostrarToast(
                        estado ? 'Modulo activado.' : 'Modulo desactivado.', estado ? 'exito' : 'info');
                })
                .catch(function () {
                    checkbox.checked = !estado; // revertir
                    pintarDescripcion(modulo);
                    MKT.mostrarToast('No se pudo actualizar la configuracion. Intenta de nuevo.', 'error');
                })
                .finally(function () {
                    checkbox.disabled = false;
                });
        });
    }

    MODULOS.forEach(conectar);
})();
