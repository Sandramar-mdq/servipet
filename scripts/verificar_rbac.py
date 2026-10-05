"""Smoke test HTTP de la matriz RBAC y aislamiento multi-tenant (Iteracion 3).

Verifica contra un despliegue real que cada nivel de la jerarquia obtiene el
codigo HTTP esperado en cada endpoint. Sale con codigo 1 si hay regresiones, para
poder engancharse como paso de post-deploy.

Uso:
    # contra un deploy
    BASE_URL=https://servipet.onrender.com python scripts/verificar_rbac.py

    # contra la app local
    python scripts/verificar_rbac.py

Credenciales: las mismas variables que `scripts/seed_alpha.py`
(ADMIN_*, ALPHA_ADMIN_*, ALPHA_EMPLEADO_*, ALPHA_CLIENTE_*). Si falta alguna,
el script aborta sin hacer peticiones.

Endpoints marcados como DIFERIDOS se listan aparte y NO cuentan como fallo: son
routers que siguen sin guard (`pages.py`, `mascotas.py`, `atenciones.py`,
`admin_turnos.py`, `reports.py:/page/reportes`, `client.py:/cliente/comunidad`).
Verificar que un anonimo los alcanza es el recordatorio de que el agujero sigue
abierto, no un error del despliegue.
"""

import os
import sys
from dataclasses import dataclass

import httpx

NIVELES_ENV = {
    "ANON": None,
    "SUPERADMIN": "ADMIN",
    "ADMIN_COMERCIO": "ALPHA_ADMIN",
    "EMPLEADO": "ALPHA_EMPLEADO",
    "CLIENTE": "ALPHA_CLIENTE",
}


@dataclass
class Caso:
    endpoint: str
    metodo: str
    esperado: dict[str, int]
    diferido: bool = False
    nota: str = ""


def _credenciales() -> dict[str, tuple[str, str]]:
    salida = {}
    for nivel, prefijo in NIVELES_ENV.items():
        if prefijo is None:
            continue
        email = (os.environ.get(f"{prefijo}_EMAIL") or "").strip()
        password = os.environ.get(f"{prefijo}_PASSWORD") or ""
        if not email or not password:
            print(
                f"Error: faltan {prefijo}_EMAIL / {prefijo}_PASSWORD. "
                "Definelas antes de correr la verificacion.",
                file=sys.stderr,
            )
            raise SystemExit(2)
        salida[nivel] = (email, password)
    return salida


def _login(client: httpx.Client, base: str, email: str, password: str) -> dict | None:
    resp = client.post(f"{base}/auth/login", json={"email": email, "password": password})
    if resp.status_code != 200:
        return None
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _construir_casos() -> list[Caso]:
    """Matriz (endpoint, metodo) -> {nivel: codigo esperado}."""
    return [
        # --- Sondas de identidad -------------------------------------------
        Caso("GET", "/api/v1/health", {
            "ANON": 200, "SUPERADMIN": 200, "ADMIN_COMERCIO": 200,
            "EMPLEADO": 200, "CLIENTE": 200,
        }),
        Caso("POST", "/auth/login", {"ANON": 401}),
        Caso("GET", "/auth/me", {
            "ANON": 401, "SUPERADMIN": 200, "ADMIN_COMERCIO": 200,
            "EMPLEADO": 200, "CLIENTE": 200,
        }),
        # El formulario staff rechaza CLIENTE (app/routers/login.py:44)
        Caso("POST", "/login", {"CLIENTE": 401}),

        # --- Plataforma SuperAdmin -----------------------------------------
        Caso("GET", "/admin/comercios", {
            "ANON": 401, "SUPERADMIN": 200, "ADMIN_COMERCIO": 403,
            "EMPLEADO": 403, "CLIENTE": 403,
        }),
        Caso("GET", "/comercios/", {
            "ANON": 401, "SUPERADMIN": 200, "ADMIN_COMERCIO": 403,
            "EMPLEADO": 403, "CLIENTE": 403,
        }),

        # --- Operacion del tenant ------------------------------------------
        Caso("GET", "/clientes/", {
            "ANON": 401, "SUPERADMIN": 400, "ADMIN_COMERCIO": 200,
            "EMPLEADO": 200, "CLIENTE": 403,
        }),
        Caso("GET", "/clientes/?comercio_id=999999", {
            "ADMIN_COMERCIO": 403, "EMPLEADO": 403,
        }),
        Caso("GET", "/ventas/", {
            "ANON": 401, "ADMIN_COMERCIO": 200, "EMPLEADO": 403, "CLIENTE": 403,
        }),
        Caso("GET", "/caja/actual", {
            "ANON": 401, "ADMIN_COMERCIO": 200, "EMPLEADO": 403, "CLIENTE": 403,
        }),
        Caso("GET", "/dashboard/resumen", {
            "ANON": 401, "ADMIN_COMERCIO": 200, "EMPLEADO": 403, "CLIENTE": 403,
        }),
        Caso("GET", "/productos/", {
            "ANON": 401, "ADMIN_COMERCIO": 200, "EMPLEADO": 403, "CLIENTE": 403,
        }),
        Caso("GET", "/reportes/caja/pdf", {
            "ANON": 401, "ADMIN_COMERCIO": 200, "EMPLEADO": 403, "CLIENTE": 403,
        }),

        # --- Marketing / comunidad -----------------------------------------
        Caso("GET", "/page/marketing", {
            "ANON": 401, "ADMIN_COMERCIO": 200, "EMPLEADO": 200, "CLIENTE": 403,
        }),
        Caso("GET", "/admin/personalizacion", {
            "ANON": 401, "ADMIN_COMERCIO": 200, "EMPLEADO": 403, "CLIENTE": 403,
        }),
        Caso("GET", "/api/v1/marketing/cumpleanos/proximos", {
            "ANON": 401, "SUPERADMIN": 400, "ADMIN_COMERCIO": 200,
            "EMPLEADO": 200, "CLIENTE": 403,
        }),

        # --- Portal cliente -------------------------------------------------
        # Sin `cliente_profile` el guard responde 404, no 403.
        Caso("GET", "/portal/me", {
            "ANON": 401, "ADMIN_COMERCIO": 404, "EMPLEADO": 403, "CLIENTE": 200,
        }),

        # --- DIFERIDOS: sin guard, elanonimo entra ------------------------
        Caso("GET", "/mascotas/", {"ANON": 200}, diferido=True,
             nota="app/routers/mascotas.py sin guard"),
        Caso("GET", "/atenciones/", {"ANON": 200}, diferido=True,
             nota="app/routers/atenciones.py sin guard"),
        Caso("GET", "/page/turnos", {"ANON": 200}, diferido=True,
             nota="app/routers/admin_turnos.py sin guard ni filtro Turno"),
        Caso("GET", "/page/reportes", {"ANON": 200}, diferido=True,
             nota="reports.py:/page/reportes sin guard y con comercio_id=1 fijo"),
    ]


def main() -> None:
    base = (os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")
    credenciales = _credenciales()
    casos = _construir_casos()

    print(f"Verificacion RBAC contra {base}")
    print(f"Casos: {len(casos)}  Niveles: {', '.join(NIVELES_ENV)}")
    print()

    headers_por_nivel: dict[str, dict | None] = {"ANON": None}
    with httpx.Client(timeout=20.0, follow_redirects=False) as client:
        for nivel, (email, password) in credenciales.items():
            headers_por_nivel[nivel] = _login(client, base, email, password)
            estado = "login OK" if headers_por_nivel[nivel] else "LOGIN FALLIDO"
            print(f"  {nivel:<16} {email:<32} {estado}")
        print()

        fallos: list[str] = []
        diferidos: list[str] = []

        for caso in casos:
            for nivel, esperado in caso.esperado.items():
                headers = headers_por_nivel.get(nivel)
                if nivel != "ANON" and headers is None:
                    fallos.append(
                        f"{caso.metodo} {caso.endpoint} [{nivel}]: sin sesion ({caso.nota})"
                    )
                    continue

                resp = client.request(
                    caso.metodo, f"{base}{caso.endpoint}", headers=headers
                )
                ok = resp.status_code == esperado
                etiqueta = f"{caso.metodo} {caso.endpoint} [{nivel}]"
                marca = "OK  " if ok else "FAIL"
                if ok:
                    continue
                detalle = (
                    f"{marca} {etiqueta}: {resp.status_code} != {esperado}"
                )
                if caso.diferido:
                    # Solo cuenta como diferido si el anonimo efectivamente entra.
                    if nivel == "ANON" and resp.status_code == 200:
                        diferidos.append(f"{caso.metodo} {caso.endpoint} -> {caso.nota}")
                    else:
                        fallos.append(detalle)
                else:
                    fallos.append(detalle)

    print("Diferidos (huecos conocidos, fuera del alcance de la Iteracion 3):")
    if diferidos:
        for d in diferidos:
            print(f"  - {d}")
    else:
        print("  - ninguno: ningun endpoint diferido quedo expuesto")
    print()

    if fallos:
        print(f"FALLOS: {len(fallos)}")
        for f in fallos:
            print(f"  - {f}")
        raise SystemExit(1)

    print("RBAC OK: la matriz respondio como se espera.")


if __name__ == "__main__":
    main()