/* Panel white-label de branding y accesibilidad - Etapa 8.3 */
(function () {
    'use strict';

    var dataEl = document.getElementById('branding-data');
    var form = document.getElementById('form-personalizacion');
    if (!dataEl || !form) return;

    var PRESETS = {};
    try {
        PRESETS = JSON.parse(dataEl.dataset.presets || '{}') || {};
    } catch (e) {
        PRESETS = {};
    }

    var pickerPrimario = document.getElementById('picker-primario');
    var pickerSecundario = document.getElementById('picker-secundario');
    var hexPrimario = document.getElementById('hex-primario');
    var hexSecundario = document.getElementById('hex-secundario');
    var pillPrimario = document.getElementById('wcag-primario');
    var pillSecundario = document.getElementById('wcag-secundario');
    var panelPreview = document.getElementById('panel-preview');
    var selectModo = document.getElementById('select-a11y-modo');
    var modoDescripcion = document.getElementById('modo-descripcion');
    var switchDyslexic = document.getElementById('switch-dyslexic');
    var radiosPreset = form.querySelectorAll('.preset-radio');

    var HEX_RE = /^#[0-9A-Fa-f]{6}$/;

    var DESCRIPCIONES_MODO = {
        normal: 'Interfaz estandar con los colores de tu marca.',
        alto_contraste: 'Fondo negro, texto blanco y foco reforzado para baja vision.',
        daltonismo: 'Iconografia obligatoria en estados: la informacion no depende solo del color.'
    };

    function hexValido(valor) {
        return typeof valor === 'string' && HEX_RE.test(valor);
    }

    function canalLineal(c) {
        return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
    }

    function luminancia(hex) {
        if (!hexValido(hex)) return null;
        var r = parseInt(hex.slice(1, 3), 16) / 255;
        var g = parseInt(hex.slice(3, 5), 16) / 255;
        var b = parseInt(hex.slice(5, 7), 16) / 255;
        return 0.2126 * canalLineal(r) + 0.7152 * canalLineal(g) + 0.0722 * canalLineal(b);
    }

    function ratioContraste(a, b) {
        var la = luminancia(a);
        var lb = luminancia(b);
        if (la === null || lb === null) return null;
        var claro = Math.max(la, lb);
        var oscuro = Math.min(la, lb);
        return (claro + 0.05) / (oscuro + 0.05);
    }

    function textoAccesible(fondo) {
        var l = luminancia(fondo);
        if (l === null) return '#FFFFFF';
        var ratioBlanco = 1.05 / (l + 0.05);
        var ratioNegro = (l + 0.05) / 0.05;
        return ratioBlanco >= ratioNegro ? '#FFFFFF' : '#000000';
    }

    function actualizarPill(pill, fondo, etiquetaTexto) {
        if (!pill) return;
        var texto = textoAccesible(fondo);
        var ratio = ratioContraste(fondo, texto);

        pill.classList.remove('bg-green-100', 'text-green-700', 'bg-red-100', 'text-red-700');

        if (ratio === null) {
            pill.textContent = '\u2715 ' + etiquetaTexto + ' invalido';
            pill.classList.add('bg-red-100', 'text-red-700');
            return;
        }

        if (ratio >= 4.5) {
            pill.textContent = '\u2713 AA ' + ratio.toFixed(2) + ':1 sobre ' + texto.toLowerCase();
            pill.classList.add('bg-green-100', 'text-green-700');
        } else {
            pill.textContent = '\u2715 ' + ratio.toFixed(2) + ':1 sobre ' + texto.toLowerCase();
            pill.classList.add('bg-red-100', 'text-red-700');
        }
    }

    function marcarPresets(nombreActivo) {
        radiosPreset.forEach(function (radio) {
            var card = radio.closest('.preset-card');
            if (!card) return;
            card.classList.toggle('activa', radio.value === nombreActivo);
        });
    }

    function presetDeColores(primario, secundario) {
        var nombres = Object.keys(PRESETS);
        for (var i = 0; i < nombres.length; i++) {
            var p = PRESETS[nombres[i]];
            if (p.color_primario.toUpperCase() === primario.toUpperCase() &&
                p.color_secundario.toUpperCase() === secundario.toUpperCase()) {
                return nombres[i];
            }
        }
        return null;
    }

    function sincronizarMarcaPreset() {
        var p = hexPrimario.value.trim();
        var s = hexSecundario.value.trim();
        if (!hexValido(p) || !hexValido(s)) return;
        marcarPresets(presetDeColores(p, s));
    }

    function aplicarCambios() {
        var p = hexPrimario.value.trim();
        var s = hexSecundario.value.trim();

        var root = document.documentElement.style;
        root.setProperty('--color-primario', hexValido(p) ? p : '#1E40AF');
        root.setProperty('--color-secundario', hexValido(s) ? s : '#0D9488');
        root.setProperty('--texto-sobre-primario', textoAccesible(p));
        root.setProperty('--texto-sobre-secundario', textoAccesible(s));

        actualizarPill(pillPrimario, p, 'color primario');
        actualizarPill(pillSecundario, s, 'color secundario');
    }

    function setColores(primario, secundario) {
        hexPrimario.value = primario.toUpperCase();
        hexSecundario.value = secundario.toUpperCase();
        if (pickerPrimario) pickerPrimario.value = primario.toLowerCase();
        if (pickerSecundario) pickerSecundario.value = secundario.toLowerCase();
        aplicarCambios();
    }

    radiosPreset.forEach(function (radio) {
        radio.addEventListener('change', function () {
            var preset = PRESETS[radio.value];
            if (!preset) return;
            setColores(preset.color_primario, preset.color_secundario);
            marcarPresets(radio.value);
        });
    });

    [pickerPrimario, pickerSecundario].forEach(function (picker) {
        if (!picker) return;
        picker.addEventListener('input', function () {
            var hexField = picker === pickerPrimario ? hexPrimario : hexSecundario;
            hexField.value = picker.value.toUpperCase();
            marcarPresets(null);
            aplicarCambios();
        });
    });

    [[hexPrimario, pickerPrimario], [hexSecundario, pickerSecundario]].forEach(function (par) {
        var hexField = par[0];
        var picker = par[1];
        if (!hexField) return;
        hexField.addEventListener('input', function () {
            if (picker && hexValido(hexField.value)) picker.value = hexField.value.toLowerCase();
            aplicarCambios();
            sincronizarMarcaPreset();
        });
    });

    if (selectModo && panelPreview) {
        var refrescarModo = function () {
            panelPreview.dataset.a11yModo = selectModo.value;
            if (modoDescripcion) modoDescripcion.textContent = DESCRIPCIONES_MODO[selectModo.value] || '';
        };
        selectModo.addEventListener('change', refrescarModo);
        refrescarModo();
    }

    if (switchDyslexic && panelPreview) {
        switchDyslexic.addEventListener('change', function () {
            panelPreview.classList.toggle('a11y-dyslexic', switchDyslexic.checked);
        });
    }

    setColores(
        (hexPrimario && hexPrimario.value) || '#1E40AF',
        (hexSecundario && hexSecundario.value) || '#0D9488'
    );
    sincronizarMarcaPreset();
})();
