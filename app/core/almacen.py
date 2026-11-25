"""Historial de boletines en disco (carpeta DATA_DIR, montada como volumen)."""
import json
import os
from pathlib import Path

from . import render


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


def guardar(b: dict, textos: dict, autor: str = "") -> str:
    t = render.tiempos(b)
    base = f"{t['inicio']:%Y%m%d}_{b['corrida']}Z"
    d = carpeta()
    (d / f"{base}.json").write_text(json.dumps({**b, "autor": autor}, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, nombre in render.nombre_archivos(b).items():
        (d / f"{base}_{nombre}").write_bytes(_codificar(textos[k]))
    return base


def listar() -> list[str]:
    return sorted((p.stem for p in carpeta().glob("*Z.json")), reverse=True)


def cargar(nombre: str) -> dict:
    return json.loads((carpeta() / f"{nombre}.json").read_text(encoding="utf-8"))
