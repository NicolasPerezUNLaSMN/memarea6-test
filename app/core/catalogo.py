"""Carga del catálogo de términos (config/catalogo.yaml)."""
import os
from functools import lru_cache
from pathlib import Path

import yaml

RUTA_DEFECTO = Path(__file__).resolve().parent.parent / "config" / "catalogo.yaml"


@lru_cache(maxsize=1)
def cargar(ruta: str | None = None) -> dict:
    ruta = ruta or os.getenv("CATALOGO_PATH") or RUTA_DEFECTO
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f)


def todas_las_zonas(cat: dict) -> list[dict]:
    """Zonas en orden de salida, con el grupo al que pertenecen."""
    out = []
    for grupo in ("costeras", "oceanicas"):
        for z in cat["zonas"][grupo]:
            out.append({**z, "grupo": grupo})
    return out
