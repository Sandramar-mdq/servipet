/**
 * Inicializa la conversión de fotos a WebP base64.
 * @param {string} inputId - ID del input[type=file]
 * @param {string} hiddenId - ID del input[type=hidden] donde se guarda el base64
 * @param {number} maxSize - ancho/alto máximo en px (default 800)
 */
function initFoto(inputId, hiddenId, maxSize = 800) {
    const input = document.getElementById(inputId);
    const hidden = document.getElementById(hiddenId);
    if (!input || !hidden) return;

    input.addEventListener('change', function () {
        const file = this.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = function (e) {
            const img = new Image();
            img.onload = function () {
                const canvas = document.createElement('canvas');
                let w = img.width;
                let h = img.height;

                if (w > h) {
                    if (w > maxSize) { h = h * maxSize / w; w = maxSize; }
                } else {
                    if (h > maxSize) { w = w * maxSize / h; h = maxSize; }
                }

                canvas.width = w;
                canvas.height = h;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, w, h);

                const base64 = canvas.toDataURL('image/webp', 0.8).split(',')[1];
                hidden.value = base64;
            };
            img.src = e.target.result;
        };
        reader.readAsDataURL(file);
    });
}
