"""Archivo de boletines emitidos en disco (carpeta DATA_DIR, montada como volumen).

Se guardan solo los boletines finales (generados sin errores): los textos
WWST01 (castellano), WWST02 (inglés), el combinado y WWST03 (NAVTEX), más sus
datos estructurados (.json) para poder reabrirlos y partir de ellos. El
borrador en texto claro del pronosticador NO se guarda.
"""
import datetime as dt
import json
import os
from pathlib import Path

from . import render

# Datos que no se guardan: el borrador del pronosticador
NO_SE_GUARDA = ("texto_claro",)


def carpeta() -> Path:
    p = Path(os.getenv("DATA_DIR", "./data")) / "boletines"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _codificar(texto: str) -> bytes:
    if os.getenv("TXT_NEWLINE", "lf").lower() == "crlf":
        texto = texto.replace("\n", "\r\n")
    return texto.encode(os.getenv("TXT_ENCODING", "utf-8"), errors="replace")


def a_bytes(texto: str) -> bytes:
    return _codificar(texto)


def nombre_base(b: dict) -> str:
    return f"{render.tiempos(b)['inicio']:%Y%m%d}_{b['corrida']}Z"


def sin_borrador(b: dict) -> dict:
    return {k: v for k, v in b.items() if k not in NO_SE_GUARDA}


def guardar(b: dict, textos: dict, autor: str = "") -> str:
    """Guarda un boletín final (datos + los cuatro textos). Reemplaza la misma corrida."""
    base = nombre_base(b)
    d = carpeta()
    datos = {**sin_borrador(b), "autor": autor, "guardado": dt.datetime.now().isoformat(timespec="seconds")}
    (d / f"{base}.json").write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    guardar_textos(b, textos)
    return base


def guardar_textos(b: dict, textos: dict):
    """Reescribe los textos de la corrida (p. ej. retocados a mano antes de descargarlos)."""
    base, d = nombre_base(b), carpeta()
    for k, nombre in render.nombre_archivos(b).items():
        if k in textos:
            (d / f"{base}_{nombre}").write_bytes(_codificar(textos[k]))


def listar() -> list[str]:
    return sorted((p.stem for p in carpeta().glob("*Z.json")), reverse=True)


def fecha_de(nombre: str) -> dt.date:
    return dt.datetime.strptime(nombre[:8], "%Y%m%d").date()


def listar_entre(desde: dt.date, hasta: dt.date) -> list[str]:
    return [n for n in listar() if desde <= fecha_de(n) <= hasta]


def cargar(nombre: str) -> dict:
    return sin_borrador(json.loads((carpeta() / f"{nombre}.json").read_text(encoding="utf-8")))


def textos(nombre: str) -> dict:
    """Textos emitidos de una corrida: {'es', 'en', 'navtex'} → (nombre de archivo, texto)."""
    out = {}
    for ruta in sorted(carpeta().glob(f"{nombre}_WWST*.txt")):
        clave = {"WWST01": "es", "WWST02": "en", "WWST03": "navtex"}.get(ruta.name.split("_")[2])
        if clave:
            crudo = ruta.read_bytes().decode(os.getenv("TXT_ENCODING", "utf-8"), errors="replace")
            out[clave] = (ruta.name[len(nombre) + 1:], crudo.replace("\r\n", "\n"))
    return out
