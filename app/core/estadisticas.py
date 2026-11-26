"""Datos para estadísticas y verificación en diferido, en CSV (sin base de datos).

Cada boletín que se genera sin errores agrega sus filas a dos archivos por año,
en DATA_DIR/estadisticas/:

- avisos_AAAA.csv: una fila por aviso (temporal y olas) y por corrida.
- pronosticos_AAAA.csv: una fila por zona (o parte de zona) y por corrida, con
  la fuerza en números Beaufort, los fenómenos y la visibilidad separados.

Se abren con Excel, LibreOffice, pandas o R. Separador «;» y UTF-8 con BOM,
para que Excel en castellano los abra bien. Volver a generar una corrida
reemplaza sus filas (no las duplica).
"""
import csv
import io
import re
from pathlib import Path

from . import almacen, olas, render
from .catalogo import todas_las_zonas

CAMPOS_AVISOS = [
    "corrida", "emision_utc", "valido_desde_utc", "valido_hasta_utc", "serie", "numero", "estado",
    "causa", "detalle", "fuerza_beaufort", "direccion", "rafagas", "zonas", "coordenadas", "desde", "hasta",
    "navtex", "area_archivo_olas", "periodo_olas", "altura_min_m", "altura_max_m", "evolucion_olas",
    "movimiento_olas", "autor", "texto_es",
]
CAMPOS_PRONOSTICOS = [
    "corrida", "emision_utc", "valido_desde_utc", "valido_hasta_utc", "zona_id", "zona", "parte",
    "direccion", "fuerza_min", "fuerza_max", "rafagas", "rafagas_beaufort", "cambios", "fuerza_max_periodo",
    "direccion_final", "fenomenos", "probabilidad", "calificativos", "evoluciones", "sin_fenomenos",
    "vis", "vis_hasta", "vis_ocnl", "con_aviso_temporal", "con_aviso_olas", "autor", "texto_es",
]


def carpeta() -> Path:
    p = almacen.carpeta().parent / "estadisticas"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _nums(fuerza: str) -> list[int]:
    return [int(x) for x in re.findall(r"\d+", fuerza or "")]


def _tiempos(b):
    t = render.tiempos(b)
    clave = f"{t['inicio']:%Y%m%d%H}"
    return clave, {"corrida": clave, "emision_utc": f"{t['emision']:%Y-%m-%d %H:%M}",
                   "valido_desde_utc": f"{t['inicio']:%Y-%m-%d %H:%M}",
                   "valido_hasta_utc": f"{t['fin']:%Y-%m-%d} {t['fin_hora']}"}


def filas_avisos(cat: dict, b: dict, autor: str = "") -> list[dict]:
    _, base = _tiempos(b)
    escala = cat["viento"]["escala"]["valores"]
    filas = []
    for a in b.get("avisos", []):
        fuerza = a.get("fuerza", "")
        filas.append({**base, "serie": "temporal", "numero": a.get("numero", ""), "estado": a.get("estado", "nuevo"),
                      "causa": a.get("causa", ""), "detalle": a.get("detalle", ""),
                      "fuerza_beaufort": escala.get(fuerza, fuerza), "direccion": a.get("dir", ""),
                      "rafagas": "si" if a.get("rafagas") else "no", "zonas": "|".join(a.get("zonas", [])),
                      "coordenadas": a.get("coords", ""), "desde": a.get("desde", ""), "hasta": a.get("hasta", ""),
                      "navtex": "si" if a.get("navtex") else "no", "autor": autor,
                      "texto_es": render.linea_aviso(cat, b, a, "es")})
    if (b.get("olas") or "").strip():
        numeros, estados = b.get("olas_numeros", {}), b.get("olas_estados", {})
        for a in olas.seleccionados(b, cat):
            n = numeros.get(a["clave"], "")
            info = olas.area_info(cat, a["area"])
            filas.append({**base, "serie": "olas", "numero": n, "estado": estados.get(str(n), "nuevo"),
                          "zonas": "|".join(info[0]) if info else "", "area_archivo_olas": a["area"],
                          "periodo_olas": f"{a['desde']}-{a['hasta']}", "altura_min_m": a["h1"],
                          "altura_max_m": a["h2"], "evolucion_olas": a["evol"], "movimiento_olas": a["mov"],
                          "autor": autor, "texto_es": olas.linea(cat, {}, a, "es", n=n) or a["original"]})
        for n in b.get("olas_ceses", []):
            filas.append({**base, "serie": "olas", "numero": n, "estado": "cese", "autor": autor})
    return filas


def filas_pronosticos(cat: dict, b: dict, autor: str = "") -> list[dict]:
    from . import mapa
    _, base = _tiempos(b)
    viento, oleaje, _ = mapa.zonas_en_aviso(cat, b)
    filas = []
    for z in todas_las_zonas(cat):
        zd = b["zonas"].get(z["id"])
        if not zd or not zd.get("incluir"):
            continue
        dividida = len(zd["subzonas"]) > 1
        for sz in zd["subzonas"]:
            v = sz["viento"]
            inicial = _nums(v.get("fuerza", ""))
            todas = inicial + [n for c in v.get("cambios", []) for n in _nums(c.get("fuerza", ""))]
            dir_final = next((c["dir"] for c in reversed(v.get("cambios", [])) if c.get("dir")), v.get("dir", ""))
            cambios = "; ".join(" ".join(x for x in ["TEMPO" if c.get("tempo") else "", c["tipo"], c.get("dir", ""),
                                                      c.get("fuerza", ""), c.get("hora", "")] if x)
                                for c in v.get("cambios", []))
            items = sz["fenomenos"].get("items", [])
            sin = sz["fenomenos"].get("sin_fenomenos") or not items
            filas.append({
                **base, "zona_id": z["id"], "zona": z["es"],
                "parte": render.etiqueta_division(cat, sz["division"], "es") if dividida else "",
                "direccion": v.get("dir", ""), "fuerza_min": min(inicial) if inicial else "",
                "fuerza_max": max(inicial) if inicial else "", "rafagas": v.get("rafagas", "") or "no",
                "rafagas_beaufort": v.get("raf_int", ""), "cambios": cambios,
                "fuerza_max_periodo": max(todas) if todas else "", "direccion_final": dir_final,
                "fenomenos": "" if sin else "|".join(f for it in items for f in it.get("fen", [])),
                "probabilidad": "" if sin else "|".join(it.get("prob", "") or "-" for it in items),
                "calificativos": "" if sin else "|".join(it.get("cal", "") or "-" for it in items),
                "evoluciones": "" if sin else "|".join(it.get("evol", "") or "-" for it in items),
                "sin_fenomenos": "si" if sin else "no",
                "vis": sz["vis"].get("v1", ""), "vis_hasta": sz["vis"].get("hasta", ""), "vis_ocnl": sz["vis"].get("ocnl", ""),
                "con_aviso_temporal": "|".join(viento.get(z["id"], [])), "con_aviso_olas": "si" if z["id"] in oleaje else "no",
                "autor": autor,
                "texto_es": render.linea_subzona(cat, b, z, sz, dividida, "es").split(": ", 1)[-1],
            })
    return filas


def _reemplazar(ruta: Path, campos: list[str], clave: str, nuevas: list[dict]):
    viejas = []
    if ruta.exists():
        with ruta.open(encoding="utf-8-sig", newline="") as f:
            viejas = [r for r in csv.DictReader(f, delimiter=";") if r.get("corrida") != clave]
    filas = sorted(viejas + [{k: r.get(k, "") for k in campos} for r in nuevas], key=lambda r: r["corrida"])
    with ruta.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos, delimiter=";")
        w.writeheader()
        w.writerows(filas)


def exportar(cat: dict, b: dict, autor: str = "") -> tuple[Path, Path]:
    clave, _ = _tiempos(b)
    anio = clave[:4]
    ra = carpeta() / f"avisos_{anio}.csv"
    rp = carpeta() / f"pronosticos_{anio}.csv"
    _reemplazar(ra, CAMPOS_AVISOS, clave, filas_avisos(cat, b, autor))
    _reemplazar(rp, CAMPOS_PRONOSTICOS, clave, filas_pronosticos(cat, b, autor))
    return ra, rp


def archivos() -> list[Path]:
    return sorted(carpeta().glob("*.csv"), reverse=True)
