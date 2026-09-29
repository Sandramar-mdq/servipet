/* Boton "Placa de Cumpleanos" de la ficha de mascota (Etapa 12).
 *
 * La ficha no conoce si la placa ya se genero este ano (eso vive en el
 * deduplicado del servidor), asi que se ofrece siempre que el modulo este
 * activo y la mascota sea apta; el 409 se resuelve con confirmacion.
 */
(function () {
    'use strict';

    var boton = document.getElementById('btn-placa-cumpleanos');
    if (!boton || !window.ServipetMarketing) return;

    var MKT = window.ServipetMarketing;
    var id = boton.dataset.mascotaId;
    var nombre = boton.dataset.nombre || '';
    var original = boton.textContent;

    boton.addEventListener('click', function () {
        MKT.modalBeneficio({
            titulo: 'Placa de ' + nombre,
            beneficio: boton.dataset.beneficio
        }).then(function (opciones) {
            if (!opciones) return;

            boton.disabled = true;
            boton.textContent = 'Generando...';

            var params = [];
            if (opciones.beneficio) params.push('beneficio=' + encodeURIComponent(opciones.beneficio));
            if (opciones.forzar) params.push('forzar=1');

            var ruta = '/cumpleanos/mascotas/' + encodeURIComponent(id) + '/placa.png' +
                (params.length ? '?' + params.join('&') : '');

            return MKT.descargarPieza(ruta, { nombre: 'cumpleanos_' + id + '.png' })
                .then(function (resultado) {
                    if (resultado.ok) {
                        MKT.mostrarToast('Placa de ' + nombre + ' descargada.', 'exito');
                    } else if (resultado.estado === 'sesion') {
                        window.location.href = '/login';
                    } else if (resultado.estado === 'duplicado') {
                        MKT.mostrarToast(resultado.detalle, 'info');
                    } else {
                        MKT.mostrarToast(resultado.detalle, 'error');
                    }
                })
                .finally(function () {
                    boton.disabled = false;
                    boton.textContent = original;
                });
        });
    });
})();
