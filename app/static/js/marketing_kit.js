/* Kit de Marketing B2B: formulario + vista previa + descarga (Etapa 12).
 *
 * La placa se arma en el servidor con `POST /api/v1/marketing/kit/promocion/
 * placa.png`; este archivo solo valida contra las mismas reglas del schema
 * (`PromocionCreate`) para no gastar un 422 y dibuja una aproximacion de 1:1.
 */
(function () {
    'use strict';

    var form = document.getElementById('form-kit');
    if (!form || !window.ServipetMarketing) return;

    var MKT = window.ServipetMarketing;

    var campos = {
        titulo: document.getElementById('kit-titulo'),
        beneficio: document.getElementById('kit-beneficio'),
        descuento: document.getElementById('kit-descuento'),
        condiciones: document.getElementById('kit-condiciones'),
        usarBranding: document.getElementById('kit-usar-branding'),
        registrar: document.getElementById('kit-registrar'),
        colorPrimario: document.getElementById('kit-color-primario'),
        colorSecundario: document.getElementById('kit-color-secundario')
    };

    var boton = document.getElementById('kit-generar');
    var error = document.getElementById('kit-error');
    var bloqueColores = document.getElementById('kit-colores');
    var previewContenedor = document.getElementById('kit-preview');

    var preview = {
        barra: document.getElementById('kit-preview-barra'),
        cuerpo: document.getElementById('kit-preview-cuerpo'),
        titulo: document.getElementById('kit-preview-titulo'),
        beneficio: document.getElementById('kit-preview-beneficio'),
        subtitulo: document.getElementById('kit-preview-subtitulo'),
        pie: document.getElementById('kit-preview-pie'),
        comercio: document.getElementById('kit-preview-comercio')
    };

    var COLOR_TEXTO_OSCURO = '#191923';
    var NOMBRE_COMERCIO = previewContenedor.dataset.comercioNombre || 'Servipet';

    function mostrarError(mensaje) {
        error.textContent = mensaje;
        error.classList.toggle('hidden', !mensaje);
    }

    function aclarar(hex, factor) {
        var valor = String(hex || '').replace('#', '');
        if (valor.length !== 6) return '#f5f5f7';
        var r = parseInt(valor.slice(0, 2), 16);
        var g = parseInt(valor.slice(2, 4), 16);
        var b = parseInt(valor.slice(4, 6), 16);
        r = Math.round(r + (255 - r) * factor);
        g = Math.round(g + (255 - g) * factor);
        b = Math.round(b + (255 - b) * factor);
        return 'rgb(' + r + ',' + g + ',' + b + ')';
    }

    function coloresEfectivos() {
        if (!campos.usarBranding.checked) {
            return { primario: '#1E40AF', secundario: '#0D9488', branding: false };
        }
        return {
            primario: MKT.normalizarColor(campos.colorPrimario.value),
            secundario: MKT.normalizarColor(campos.colorSecundario.value),
            branding: true
        };
    }

    function pintarPreview() {
        var colores = coloresEfectivos();
        var titulo = campos.titulo.value.trim();
        var beneficio = campos.beneficio.value.trim() || campos.descuento.value.trim();

        preview.barra.style.backgroundColor = colores.primario;
        preview.pie.style.backgroundColor = colores.primario;
        preview.pie.style.color = '#ffffff';
        preview.cuerpo.style.backgroundColor = aclarar(colores.primario, colores.branding ? 0.75 : 0.9);

        preview.titulo.textContent = titulo || 'Tu promocion aqui';
        preview.titulo.style.color = COLOR_TEXTO_OSCURO;
        preview.titulo.style.fontSize = 'clamp(1rem, 5cqw, 1.8rem)';

        preview.beneficio.textContent = beneficio;
        preview.beneficio.style.color = colores.primario;
        preview.beneficio.style.fontSize = 'clamp(1.1rem, 6cqw, 2.2rem)';
        preview.beneficio.classList.toggle('hidden', !beneficio);

        var condiciones = campos.condiciones.value.trim();
        preview.subtitulo.textContent = condiciones ? 'Condiciones: ' + condiciones : '';
        preview.subtitulo.style.color = 'rgb(90,90,100)';

        preview.comercio.textContent = colores.branding ? NOMBRE_COMERCIO : 'Servipet';
    }

    function payload() {
        var colores = coloresEfectivos();
        var cuerpo = {
            titulo: campos.titulo.value.trim(),
            usar_branding: campos.usarBranding.checked,
            registrar: campos.registrar.checked
        };

        if (campos.descuento.value.trim()) cuerpo.descuento = campos.descuento.value.trim();
        if (campos.beneficio.value.trim()) cuerpo.beneficio_texto = campos.beneficio.value.trim();
        if (campos.condiciones.value.trim()) cuerpo.condiciones = campos.condiciones.value.trim();
        if (campos.usarBranding.checked) {
            cuerpo.color_primario = colores.primario;
            cuerpo.color_secundario = colores.secundario;
        }

        return cuerpo;
    }

    function validar() {
        var titulo = campos.titulo.value.trim();
        if (titulo.length < 3) {
            mostrarError('El titulo necesita al menos 3 caracteres.');
            campos.titulo.focus();
            return null;
        }
        if (!campos.beneficio.value.trim() && !campos.descuento.value.trim()) {
            mostrarError('Carga al menos un beneficio o un descuento para que la placa tenga sentido.');
            campos.beneficio.focus();
            return null;
        }
        mostrarError('');
        return payload();
    }

    form.addEventListener('submit', function (event) {
        event.preventDefault();

        var cuerpo = validar();
        if (!cuerpo) return;

        boton.disabled = true;
        boton.textContent = 'Generando...';

        MKT.descargarPieza('/kit/promocion/placa.png', {
            metodo: 'POST',
            body: cuerpo,
            nombre: 'promo.png'
        }).then(function (resultado) {
            if (resultado.ok) {
                MKT.mostrarToast('Placa descargada.', 'exito');
            } else if (resultado.estado === 'sesion') {
                window.location.href = '/login';
            } else {
                mostrarError(resultado.detalle);
            }
        }).catch(function () {
            mostrarError('Error de conexion. Intenta de nuevo.');
        }).finally(function () {
            boton.disabled = false;
            boton.textContent = 'Generar y descargar placa';
        });
    });

    form.addEventListener('input', function () {
        mostrarError('');
        pintarPreview();
    });

    campos.usarBranding.addEventListener('change', function () {
        bloqueColores.classList.toggle('opacity-50', !campos.usarBranding.checked);
        bloqueColores.classList.toggle('pointer-events-none', !campos.usarBranding.checked);
        pintarPreview();
    });

    // El preview escala con el ancho del contenedor (container queries).
    if (previewContenedor && 'containerType' in previewContenedor.style) {
        previewContenedor.style.containerType = 'inline-size';
    }

    pintarPreview();
})();
