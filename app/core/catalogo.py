"""Carga del catálogo de términos (config/catalogo.yaml)."""
import os
from pathlib import Path

import yaml

RUTA_DEFECTO = Path(__file__).resolve().parent.parent / "config" / "catalogo.yaml"
_cache: dict = {}


def cargar(ruta: str | None = None) -> dict:
    """Lee el catálogo; si el archivo cambió (actualización o edición), lo vuelve a leer."""
    ruta = Path(ruta or os.getenv("CATALOGO_PATH") or RUTA_DEFECTO)
    marca = ruta.stat().st_mtime
    if ruta in _cache and _cache[ruta][0] == marca:
        return _cache[ruta][1]
    with open(ruta, encoding="utf-8") as f:
        datos = yaml.safe_load(f)
    _cache[ruta] = (marca, datos)
    return datos


def todas_las_zonas(cat: dict) -> list[dict]:
    """Zonas en orden de salida, con el grupo al que pertenecen."""
    out = []
    for grupo in ("costeras", "oceanicas"):
        for z in cat["zonas"][grupo]:
            out.append({**z, "grupo": grupo})
    return out
