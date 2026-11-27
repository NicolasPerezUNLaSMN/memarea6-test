"""Palabras habilitadas: lista de lo que entiende el intérprete, para consultar y compartir."""
import csv
import io
from pathlib import Path

import yaml

RUTA = Path(__file__).resolve().parent.parent / "config" / "palabras_habilitadas.yaml"


def cargar(ruta: Path = RUTA) -> list[dict]:
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f)["secciones"]


def formas(fila: dict) -> list[str]:
    return [x.strip() for x in fila["escribe"].split("·") if x.strip()]


def filtrar(secciones: list[dict], buscar: str) -> list[dict]:
    """Secciones con solo las filas que contienen el texto buscado (sin distinguir mayúsculas)."""
    b = buscar.strip().lower()
    if not b:
        return secciones
    out = []
    for s in secciones:
        filas = [f for f in s["filas"] if b in f["escribe"].lower() or b in f["significa"].lower()]
        if filas or b in s["titulo"].lower():
            out.append({**s, "filas": filas or s["filas"]})
    return out


def a_markdown(secciones: list[dict]) -> str:
    out = ["# meMareaVI — Palabras habilitadas", "",
           "Formas de escribir el borrador que el intérprete reconoce. Mayúsculas y tildes dan igual.", ""]
    for s in secciones:
        out += [f"## {s['titulo']}", ""]
        if s.get("nota"):
            out += [s["nota"], ""]
        out += ["| Se puede escribir | En el boletín |", "| --- | --- |"]
        out += [f"| {f['escribe']} | {f['significa']} |" for f in s["filas"]]
        out.append("")
    return "\n".join(out)


def a_csv(secciones: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["seccion", "se puede escribir", "en el boletin"])
    for s in secciones:
        for f in s["filas"]:
            w.writerow([s["titulo"], f["escribe"], f["significa"]])
    return "﻿" + buf.getvalue()     # con BOM para que Excel respete las tildes
