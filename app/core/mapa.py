"""Mapa del METAREA VI con las zonas en aviso (SVG, sin conexión a internet).

- Avisos de temporal: zonas nombradas y áreas por coordenadas («40S-50S 50W-60W»).
- Avisos de olas: las áreas del archivo de olas que corresponden a zonas del boletín.

La costa es de Natural Earth (dominio público), recortada y simplificada en
static/costa.json. Las zonas y los colores están en catalogo.yaml → mapa.
"""
import json
import math
import re
from functools import lru_cache
from pathlib import Path

from . import olas
from .catalogo import todas_las_zonas

COSTA = Path(__file__).resolve().parent.parent / "static" / "costa.json"
ANCHO = 760


@lru_cache(maxsize=1)
def _costa():
    return json.loads(COSTA.read_text(encoding="utf-8"))


class _Proy:
    """Equirectangular con la escala horizontal corregida por la latitud media."""

    def __init__(self, v):
        self.o, self.e, self.n, self.s = v["oeste"], v["este"], v["norte"], v["sur"]
        lat0 = math.radians((self.n + self.s) / 2)
        self.kx = ANCHO / (self.e - self.o)
        self.ky = self.kx / math.cos(lat0)
        self.alto = round((self.n - self.s) * self.ky)

    def xy(self, lon, lat):
        return round((lon - self.o) * self.kx, 1), round((self.n - lat) * self.ky, 1)

    def rect(self, oeste, sur, este, norte):
        x1, y1 = self.xy(oeste, norte)
        x2, y2 = self.xy(este, sur)
        return x1, y1, x2 - x1, y2 - y1


def _coords_aviso(texto):
    """«40S-50S 50W-60W» → (oeste, sur, este, norte)."""
    m = re.search(r"(\d{1,2})S\s*-\s*(\d{1,2})S\s+(\d{1,3})W\s*-\s*(\d{1,3})W", texto or "")
    if not m:
        return None
    la1, la2, lo1, lo2 = (int(x) for x in m.groups())
    return -max(lo1, lo2), -max(la1, la2), -min(lo1, lo2), -min(la1, la2)


def zonas_en_aviso(cat, b):
    """({zona: [números de aviso de temporal]}, {zona: [áreas de olas]}, [rectángulos por coordenadas])."""
    viento, rects = {}, []
    for a in b.get("avisos", []):
        if a.get("estado") in ("cese", "fuera_area"):
            continue
        for zid in a.get("zonas", []):
            viento.setdefault(zid, []).append(a.get("numero", ""))
        r = _coords_aviso(a.get("coords", ""))
        if r:
            rects.append((r, a.get("numero", "")))
    oleaje = {}
    if (b.get("olas") or "").strip():
        for a in olas.seleccionados(b, cat):
            info = olas.area_info(cat, a["area"])
            for zid in (info[0] if info else []):
                oleaje.setdefault(zid, []).append(a["area"])
    return viento, oleaje, rects


def svg(cat, b) -> str:
    mc = cat["mapa"]
    col = mc["colores"]
    p = _Proy(mc["vista"])
    viento, oleaje, rects = zonas_en_aviso(cat, b)
    alto_leyenda = 44
    H = p.alto + alto_leyenda
    partes = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ANCHO} {H}" width="100%" role="img" '
              f'aria-label="Mapa de zonas con aviso de temporal y de olas" font-family="sans-serif">',
              '<defs><pattern id="rayado-olas" width="8" height="8" patternUnits="userSpaceOnUse" '
              f'patternTransform="rotate(45)"><rect width="4" height="8" fill="{col["olas"]}" fill-opacity="0.75"/>'
              '</pattern><clipPath id="marco"><rect x="0" y="0" '
              f'width="{ANCHO}" height="{p.alto}"/></clipPath></defs>',
              f'<rect x="0" y="0" width="{ANCHO}" height="{p.alto}" fill="{col["agua"]}"/>',
              '<g clip-path="url(#marco)">']

    orden = [z["id"] for z in todas_las_zonas(cat) if z["grupo"] == "oceanicas"] + \
            [z["id"] for z in todas_las_zonas(cat) if z["grupo"] == "costeras"]
    for zid in orden:
        zona = mc["zonas"].get(zid)
        if not zona:
            continue
        v, o = zid in viento, zid in oleaje
        for r in zona["rect"]:
            x, y, w, h = p.rect(*r)
            relleno = col["viento"] if v else ("url(#rayado-olas)" if o else "none")
            op = "0.45" if v else "1"
            partes.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{relleno}" fill-opacity="{op}" '
                          f'stroke="{col["borde"]}" stroke-width="0.8"/>')
            if v and o:
                partes.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="url(#rayado-olas)"/>')

    for (oeste, sur, este, norte), num in rects:
        x, y, w, h = p.rect(oeste, sur, este, norte)
        partes.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{col["viento"]}" fill-opacity="0.25" '
                      f'stroke="{col["viento"]}" stroke-width="2" stroke-dasharray="6 4"/>')
        partes.append(f'<text x="{x + 6}" y="{y + h - 8}" font-size="12" font-weight="600" fill="{col["viento"]}">'
                      f'Aviso {num}</text>')

    for poligono in _costa():
        puntos = " ".join(f"{x},{y}" for x, y in (p.xy(lon, lat) for lon, lat in poligono))
        partes.append(f'<polygon points="{puntos}" fill="{col["tierra"]}" stroke="#A8A291" stroke-width="0.7"/>')

    for zid in orden:
        zona = mc["zonas"].get(zid)
        if not zona:
            continue
        oeste, sur, este, norte = zona["rect"][0]
        costera = oeste <= -70
        if zona.get("rotulo_en"):
            x, y = p.xy(*zona["rotulo_en"])
            ancla = zona.get("ancla", "middle")
        elif costera:   # rótulo del lado del mar
            x, y = p.xy(este, (sur + norte) / 2)
            x -= 6
            ancla = "end"
        else:
            x, y = p.xy((oeste + este) / 2, (sur + norte) / 2)
            ancla = "middle"
        peso = "700" if zid in viento or zid in oleaje else "400"
        tam = "11" if costera or zona.get("rotulo_en") else "12"
        partes.append(f'<text x="{x}" y="{y + 4}" text-anchor="{ancla}" font-size="{tam}" font-weight="{peso}" '
                      f'fill="{col["texto"]}" paint-order="stroke" stroke="{col["agua"]}" stroke-width="3">'
                      f'{zona["rotulo"]}</text>')
    partes.append("</g>")

    # leyenda
    y0 = p.alto + 16
    partes.append(f'<rect x="16" y="{y0}" width="18" height="14" fill="{col["viento"]}" fill-opacity="0.45" '
                  f'stroke="{col["borde"]}"/><text x="40" y="{y0 + 12}" font-size="13" fill="{col["texto"]}">'
                  'Aviso de temporal</text>')
    partes.append(f'<rect x="190" y="{y0}" width="18" height="14" fill="url(#rayado-olas)" stroke="{col["borde"]}"/>'
                  f'<text x="214" y="{y0 + 12}" font-size="13" fill="{col["texto"]}">Aviso de olas</text>')
    partes.append(f'<rect x="340" y="{y0}" width="18" height="14" fill="{col["viento"]}" fill-opacity="0.25" '
                  f'stroke="{col["viento"]}" stroke-width="2" stroke-dasharray="4 3"/>'
                  f'<text x="364" y="{y0 + 12}" font-size="13" fill="{col["texto"]}">Aviso por coordenadas</text>')
    partes.append("</svg>")
    return "".join(partes)
