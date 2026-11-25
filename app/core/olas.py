"""Avisos de olas a partir del archivo BOL_METAREA_VI_ING.

El archivo trae, por área y por período, la altura de ola. Solo interesan las
líneas «WARNING:», que se pasan al boletín (debajo de los avisos de temporal)
en castellano y en inglés con el vocabulario del catálogo.
"""
import re

MESES = {m: i + 1 for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}
RE_VALIDO = re.compile(r"VALIDO DESDE (\d{1,2}) ([A-Z]{3}) (\d{1,2}) UTC HASTA (\d{1,2}) ([A-Z]{3}) (\d{1,2}) UTC")
RE_PERIODO = re.compile(r"^(\d{6})\s*-\s*(\d{6})\s*UTC$")
RE_AREA = re.compile(r"^(AREA .+|ZONA .+|MAR DE .+)$")
RE_AVISO = re.compile(
    r"^WARNING:\s*(?:(AT)\s+(N|NE|E|SE|S|SW|W|NW)|(IN THE CENTER)|(IN THE REST))?,?\s*"
    r"(\d+(?:\.\d)?)\s*/\s*(\d+(?:\.\d)?)\s*M\s*(.*?)\s*,\s*MOVING\s+(N|NE|E|SE|S|SW|W|NW)\s*\.?$")


def _hora(ddhhmm: str) -> str:
    return f"{ddhhmm[:2]}/{ddhhmm[2:]}"


def leer(texto: str) -> dict:
    """Devuelve {"valido": {...} o None, "avisos": [...], "no_reconocidos": [...]}."""
    valido, area, periodo = None, None, None
    avisos, raros = [], []
    for linea in (l.strip().upper() for l in texto.splitlines()):
        if not linea:
            continue
        m = RE_VALIDO.search(linea)
        if m:
            d1, m1, h1, d2, m2, h2 = m.groups()
            valido = {"desde": (MESES.get(m1, 0), int(d1), int(h1)), "hasta": (MESES.get(m2, 0), int(d2), int(h2))}
            continue
        if RE_AREA.match(linea):
            area, periodo = re.sub(r"\s+", " ", linea), None
            continue
        m = RE_PERIODO.match(linea)
        if m:
            periodo = m.groups()
            continue
        if linea.startswith("WARNING"):
            m = RE_AVISO.match(linea)
            if not m or not area or not periodo:
                raros.append(linea)
                continue
            at, rumbo, centro, resto, h1, h2, evol, mov = m.groups()
            lugar = ("AT", rumbo) if at else ("IN THE CENTER", "") if centro else ("IN THE REST", "") if resto else ("", "")
            avisos.append({"clave": f"{area}|{periodo[0]}|{linea}", "area": area, "desde": _hora(periodo[0]),
                           "hasta": _hora(periodo[1]), "lugar": lugar, "h1": h1, "h2": h2,
                           "evol": re.sub(r"\s+", " ", evol), "mov": mov, "original": linea})
    return {"valido": valido, "avisos": avisos, "no_reconocidos": raros}


def _evolucion(cat, evol, lang):
    for patron, trad in cat["olas"]["evolucion"].items():
        rx = "^" + re.escape(patron).replace(re.escape("{h}"), r"(\d+(?:\.\d)?)") + "$"
        m = re.match(rx, evol)
        if m:
            return trad[lang].format(h=m.group(1) if m.groups() else "")
    return None


def linea(cat, zonas: dict, a: dict, lang: str) -> str | None:
    """Línea del aviso en el idioma pedido; None si algo no tiene traducción."""
    oc = cat["olas"]
    zid = oc["areas"].get(a["area"])
    area = zonas[zid][lang] if zid in zonas else a["area"]
    lugar_k, rumbo = a["lugar"]
    lugar = oc["lugar"][lugar_k][lang].format(d=rumbo) if lugar_k else ""
    evol = _evolucion(cat, a["evol"], lang) if a["evol"] else ""
    if evol is None:
        return None
    texto = " ".join(p for p in [lugar, oc["altura"][lang].format(h1=a["h1"], h2=a["h2"])] if p)
    texto += (f" {evol}" if evol else "") + ", " + oc["movimiento"][lang].format(d=a["mov"])
    return oc["linea"][lang].format(area=area, desde=a["desde"], hasta=a["hasta"], texto=texto)


def seleccionados(b: dict) -> list[dict]:
    datos = leer(b.get("olas", "") or "")
    excluir = set(b.get("olas_excluir", []))
    return [a for a in datos["avisos"] if a["clave"] not in excluir]
