"""Ingreso con cuenta Microsoft y/o Google (login nativo de Streamlit, OpenID Connect).

Se activa solo si .streamlit/secrets.toml tiene la sección [auth] con al menos
un proveedor ([auth.microsoft], [auth.google]). Sin eso, la app funciona como
antes: el nombre del pronosticador se escribe a mano (uso local y pruebas).

Quién puede entrar se limita en la sección [acceso] del mismo archivo:
    dominios = ["smn.gob.ar"]          # cualquier cuenta de estos dominios
    correos  = ["alguien@gmail.com"]   # y además estas cuentas sueltas
Si no hay [acceso], entra cualquiera que se identifique (no recomendado con Google).
"""
NOMBRES = {"microsoft": "Microsoft", "google": "Google"}


def _secretos() -> dict:
    import streamlit as st
    try:
        return st.secrets.to_dict()
    except Exception:  # noqa: BLE001 — sin secrets.toml
        return {}


def proveedores(secretos: dict | None = None) -> list[str]:
    """Proveedores configurados en [auth], en orden (Microsoft primero)."""
    auth = (secretos if secretos is not None else _secretos()).get("auth") or {}
    provs = [k for k, v in auth.items() if isinstance(v, dict)]
    return sorted(provs, key=lambda p: (p not in NOMBRES, list(NOMBRES).index(p) if p in NOMBRES else 0, p))


def reglas(secretos: dict | None = None) -> dict:
    a = (secretos if secretos is not None else _secretos()).get("acceso") or {}
    return {"dominios": [d.lower().lstrip("@") for d in a.get("dominios", [])],
            "correos": [c.lower() for c in a.get("correos", [])]}


def permitido(correo: str, r: dict) -> bool:
    """¿Puede entrar esta cuenta? Sin reglas cargadas, entra cualquiera."""
    if not r["dominios"] and not r["correos"]:
        return True
    correo = (correo or "").strip().lower()
    if not correo or "@" not in correo:
        return False
    return correo in r["correos"] or correo.rsplit("@", 1)[1] in r["dominios"]


def identidad(usuario: dict) -> tuple[str, str]:
    """(nombre, correo) desde los datos que devuelve el proveedor.

    Las cuentas de trabajo de Microsoft a veces no traen «email»: se usa
    «preferred_username» (el usuario@dominio con el que se ingresa).
    """
    correo = usuario.get("email") or usuario.get("preferred_username") or usuario.get("upn") or ""
    nombre = usuario.get("name") or " ".join(x for x in (usuario.get("given_name"), usuario.get("family_name")) if x)
    return (nombre or correo), correo
