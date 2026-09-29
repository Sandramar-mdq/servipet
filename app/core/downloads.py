"""Choke point unico para descargas binarias (PDF / PNG) del sistema.

Replica exactamente el contrato de `app.routers.reports._descarga` para que los
modulos de Marketing B2B no dependan del router de reportes ni dupliquen la
logica de headers.
"""

from fastapi.responses import Response


def descarga_archivo(contenido: bytes, media_type: str, filename: str) -> Response:
    """Devuelve el contenido como descarga adjunta.

    - ``contenido`` se entrega completamente en memoria (mismo criterio que los
      reportes existentes: los PDF del sistema no se escriben a disco).
    - El ``filename`` va en ``Content-Disposition`` con la forma simple
      ``attachment; filename="..."``, igual que el resto del proyecto.
    """
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=contenido, media_type=media_type, headers=headers)
