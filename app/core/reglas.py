"""Interpretación del texto claro SIN IA, con reglas.

Lee el borrador tal como lo escriben los pronosticadores (cada uno con su
estilo: oraciones completas, telegráfico, abreviado, un renglón por elemento,
PDF…) y devuelve los mismos datos que devolvería la IA (mismo formato que
interpretar.llamar_ia). Lo que no reconoce no lo inventa: lo informa como
«duda» para que el pronosticador lo revise.

Para sumar formas nuevas de escribir, alcanza casi siempre con ampliar las
tablas de esta primera parte (ABREVIATURAS, ERRATAS, FENOMENOS, MOMENTOS…).
"""
import difflib
import re
import unicodedata

from .catalogo import todas_las_zonas

# ====================================================================== tablas
# Abreviaturas que usan los pronosticadores → forma completa (en minúsculas, sin tildes)
ABREVIATURAS = {
    "mod": "moderados", "reg": "regulares", "mf": "muy fuertes", "temp": "temporal", "sec": "sector",
    "raf": "rafagas", "camb": "cambiando", "aisl": "aisladas", "tor": "tormentas", "mej": "mejorando",
    "mad": "madrugada", "madrug": "madrugada", "prof": "profundiza", "proba": "probabilidad",
    "prob": "probabilidad", "probab": "probabilidad", "dd": "direcciones", "var": "variables",
    "direc": "direccion", "visi": "vis", "ff": "frente frio", "fo": "frente ocluido", "fc": "frente calido",
    "fgb": "fuerte gradiente barico", "cpf": "con posicion final", "spf": "sin posicion final",
    "ext": "extiende", "antih": "antihorario", "anithorario": "antihorario", "incr": "aumentando",
    "decr": "disminuyendo", "des": "desmejorando", "desmej": "desmejorando",
}
# Se aplican ANTES de expandir abreviaturas (dependen del contexto)
PRE_ERRATAS = [
    (r"\bmej\.?\s+temp\w*", "mejoramientos temporarios"),
    (r"\bdir\.?\s+variables?\b", "direcciones variables"),
    (r"\bsin pos\.?\b", "sin posicion"), (r"\bpos\.?\s+final\b", "posicion final"),
    (r"\bsin mov\.?\b", "sin movimiento"), (r"\bfe\b", "frente estacionario"),
    (r"\bmat(?:inales?)?\b", ""),
]
# Estilo de una sola letra (M, R, F, T, L, MF; VIS B A R OC M; CAMBIANDO AH / H)
LETRAS_VIS = {"b": "buena", "r": "regular", "m": "mala", "mm": "muy mala", "oc": "ocasionalmente"}
LETRAS_FUERZA = {"m": "moderados", "r": "regulares", "f": "fuertes", "t": "temporal", "l": "leves", "mf": "muy fuertes"}


def _letras(t: str) -> str:
    t = re.sub(r"\bcon\s+r\b", "con rafagas", t)
    def vis(m):
        return "vis " + re.sub(r"\b(mm|oc|[bmr])\b", lambda x: LETRAS_VIS[x.group(1)], m.group(1))
    t = re.sub(r"\bvis\s+((?:mm|[bmr])\b(?:\s+(?:a|oc|oca|ocnl)\s+(?:mm|[bmr])\b)*)", vis, t)
    t = re.sub(r"\b(cambiando|cambian|cambia|rotando|rota|rotan)\s+ah\b", r"\1 antihorario", t)
    t = re.sub(r"\b(cambiando|cambian|cambia|rotando|rota|rotan)\s+h\b", r"\1 horario", t)
    sigue = (r"(?=\s+(?:a\s+(?:mf|[mrftl])\b|sector|sec|dir|direcciones|de\s+dir|del|con|so|se|ne|nw|no|sw|el|"
             r"cambiando|aumentando|disminuyendo|rotando)\b|\s*[,.]|\s*$)")
    for _ in range(2):   # «a r a f»: dos pasadas
        t = re.sub(rf"(?:(?<=^)|(?<=[:.,]\s)|(?<=[:.,])|(?<=\ba\s)|(?<=\s))\b(mf|[mrftl])\b{sigue}",
                   lambda m: LETRAS_FUERZA[m.group(1)], t)
    return t


# Erratas y formas habladas frecuentes (expresión regular → reemplazo)
ERRATAS = [
    (r"\bdela\b", "de la"), (r"\bbranca\b", "blanca"), (r"\ba ?prtir\b", "a partir"), (r"\bapartir\b", "a partir"),
    (r"\batemporal\b", "a temporal"), (r"\bregular es\b", "regulares"),
    (r"\bencendido (anti)?horario\b", r"en sentido \1horario"),
    (r"\b(cambiando|cambian|cambia|rotando|rota) el sentido\b", r"\1 en sentido"),
    (r"\brafagas de temprano\b", "rafagas de temporal"), (r"\brafa de\b", "rafagas de"),
    (r"\bse nueve\b", "se mueve"), (r"\bde (debilita|intensifica|profundiza)\b", r"se \1"),
    (r"\b(norte|sur|este|oeste) e (?=\d)", r"\1 de "), (r"\ba la (\d)", r"a las \1"),
    (r"\brob de\b", "probabilidad de"), (r"\ba tempo\b(?= (?:sector|sec|del|de)\b)", "a temporal"), (r"\bubicad[ao] en\b", "en"), (r"\bubicad[ao]\b", ""),
    (r"\bla visibilidad es\b", "vis"), (r"\bvisibilidad es\b", "vis"), (r"\bla visibilidad\b", "vis"),
    (r"\bvisibilidad\b", "vis"), (r"\bdirecciones? variables?\b", "direcciones variables"),
    (r"\b(?:y )?manteniendo (?:la )?direccion\b", ""), (r"\bocasional\b", "ocasionalmente"),
]

FUERZAS = [  # (expresión, término de la escala) — las más largas primero
    (r"temporal fuerte", "TEMPORAL_FUERTE"), (r"muy fuertes?", "MUY_FUERTES"), (r"temporal", "TEMPORAL"),
    (r"fuertes?", "FUERTES"), (r"regulares", "REGULARES"), (r"moderados?", "MODERADOS"), (r"leves?", "LEVES"),
]
FUERZA_RX = r"(?:temporal fuerte|muy fuertes?|temporal|fuertes?|regulares|moderados?|leves?)"
PUNTOS = {"n": "N", "norte": "N", "s": "S", "sur": "S", "e": "E", "este": "E", "o": "W", "w": "W",
          "oeste": "W", "ne": "NE", "noreste": "NE", "nordeste": "NE", "nw": "NW", "no": "NW", "noroeste": "NW",
          "se": "SE", "sudeste": "SE", "sureste": "SE", "sw": "SW", "so": "SW", "sudoeste": "SW", "suroeste": "SW"}
PUNTO_RX = (r"(norte|sur|este|oeste|noreste|nordeste|noroeste|sudeste|sureste|sudoeste|suroeste"
            r"|ne|nw|no|se|sw|so|n|s|e|o|w)")

FENOMENOS = [  # (expresión, clave del catálogo)
    (r"lluvias? y nieve(?: mezclad[ao]s?)?", "AGUANIEVE"),
    (r"chaparr[oó]n(?:es)? de nieve", "SH_NIEVE"),
    (r"chaparr[oó]n(?:es)? de granizo", "SH_GRANIZO"),
    (r"chaparr[oó]n(?:es)? de lluvias?", "SH"),
    (r"bancos? de niebla", "BANCOS_NIEBLA"),
    (r"chaparr[oó]n(?:es)?|chubascos?|\bsh\b", "SH"),
    (r"lloviznas?", "LLOVIZNAS"), (r"lluvias?", "LLUVIAS"), (r"tormentas?", "TORMENTAS"),
    (r"nevadas?", "NEVADAS"), (r"neblinas?", "NEBLINAS"), (r"nieblas?", "NIEBLAS"),
    (r"granizo", "GRANIZO"), (r"inestable", "INESTABLE"), (r"precipitacion(?:es)?", "PRECIPITACIONES"),
]
PROBABILIDADES = [
    (r"desmejorando con probabilidad(?:es)? de", "DESMEJORANDO"),
    (r"baja probabilidad(?:es)? de", "BAJA"),
    (r"probabilidad(?:es)?(?: de)?|probables?", "PROB"),
]
CALIFICATIVOS = [(r"aislad[ao]s?", "AISLADAS"), (r"intermitentes?", "INTERMITENTES"),
                 (r"(?:algunas )?fuertes?", "FUERTES"), (r"dispers[ao]s?", "DISPERSAS"), (r"ocasionales", "OCASIONALES"),
                 (r"debil(?:es)?", "DEBILES")]
MOMENTOS = [
    (r"a partir (?:de )?(?:la )?madrugada", "DESDE_MADRUGADA"), (r"a partir (?:de )?(?:la )?mañana", "DESDE_MANANA"),
    (r"a partir (?:de )?(?:la )?tarde", "DESDE_TARDE"), (r"a partir (?:de )?(?:la )?noche", "DESDE_NOCHE"),
    (r"a partir del mediodia", "DESDE_MEDIODIA"),
    (r"(?:hacia|al) (?:el )?final del periodo", "FINAL_PERIODO"),
    (r"(?:durante|en|por) la madrugada", "DURANTE_MADRUGADA"), (r"(?:durante|en|por) la mañana", "DURANTE_MANANA"),
    (r"(?:durante|en|por) la tarde", "DURANTE_TARDE"), (r"(?:durante|en|por) la noche", "DURANTE_NOCHE"),
    (r"hacia la madrugada", "HACIA_MADRUGADA"), (r"hacia la mañana", "HACIA_MANANA"),
    (r"hacia la tarde", "HACIA_TARDE"), (r"hacia la noche", "HACIA_NOCHE"),
]
EVOLUCIONES = [(r"(?:con )?(?:mejoramientos? temporari[ao]s|mejoras? temporari[ao]s)", "MEJ_TEMP"),
               (r"\bdesmejorando(?: paulatinamente)?", "DESMEJORANDO"),
               (r"\bmejorando(?: paulatinamente)?", "MEJORANDO"),
               (r"(?:en )?disipaci[oó]n|disip[aá]ndose", "DISIPANDOSE")]
RELLENO = r"\b(de|y|e|o|con|el|la|las|los|del|a|al|en|sin|proba|algunas|costeras|vientos?|luego)\b"

VIS = {"muy mala": "MUY_MALA", "muy malas": "MUY_MALA", "mala": "MALA", "malas": "MALA", "regular": "REGULAR",
       "regulares": "REGULAR", "buena": "BUENA", "buenas": "BUENA"}
VIS_VAL = r"(muy malas?|malas?|regulares|regular|buenas?)"
VIS_CON = r"(a|o|oca|ocasionalmente|ocnl)"
VIS_FRASE = re.compile(rf"^(?:vis\s+)?{VIS_VAL}(?:\s+{VIS_CON}\s+{VIS_VAL})*\s*$")

RAFAGAS_RX = r"\b(?:ra[a-z]{0,3}f[a-z]{0,5}|raf)\b"
CAMBIO_RX = (r"(?:cambiando|cambian|cambia|rotando|rotan|rota|aumentando|aumentan|aumenta|"
             r"disminuyendo|disminuyen|disminuye|virando|incrementando)")
FEN_INICIO = re.compile(r"\b(?:desmejorando con|baja probabilidad|probabilidad|probables?|neblinas?|nieblas?|"
                        r"bancos de niebla|lluvias?|lloviznas?|chaparr\w*|chubascos?|tormentas?|nevadas?|"
                        r"granizo|sin fenomenos?|inestable)\b")

VOCAB = set("""
avisos aviso actualizar actualiza actualizacion cese cesa afuera fuera gradiente barico provoca provocara temporal
sector rafagas hasta partir situacion sinopsis anticiclon depresion intensifica debilita profundiza rellena mueve
moviendose desplaza movimiento posicion final extiende frente frio calido ocluido estacionario ciclogenesis
pronostico pronosticos costero costas zonas costeras areas oceanicas oceanica interior exterior uruguay sudeste
costa plata bahia blanca peninsula valdes golfo jorge patagonia mundo islas malvinas norte centro oeste sudoeste
drake regulares moderados fuertes leves variables direcciones cambiando cambian rotando sentido horario
antihorario aumentando disminuyendo temporariamente prevaleciendo probables probabilidad lloviznas lluvias
lluvia chaparrones nieve mezclada nevadas neblinas nieblas niebla bancos granizo tormentas aisladas intermitentes
mejorando desmejorando mejoramientos temporarios disipandose disipacion madrugada manana tarde noche mediodia
desmejorando desmejora vigente vigentes mantiene persiste continua ratifica renueva actualizo actualizado precipitaciones debil debiles
temporales cambio cambios durante luego buena regular mala resto entera copiar copia pegar navtex hielos idem vientos cuña paulatinamente
fuerte fuerza viento entre alrededor misma mismo nuevo hacia desde mueven mueve provocaria posiciones presion
ocasionalmente ocasional visibilidad algunas costeras ubicada ubicado anterior quieran sentido corazon guardar
tenemos teniamos aquella pegamos vuelvan porque usaremos tiempo extiende asocia asociado eje frentes cambia
rotan rota aumenta aumentan disminuye disminuyen incrementando virando direccion variable mismas tormenta
nevada neblina chaparron llovizna aislada aislados intermitente debilitandose intensificandose profundizandose
moviendose desplaza desplazandose cesa ceses fuera mejoras mejora sector sectores norte este oeste sur noreste
noroeste sudeste sudoeste nordeste suroeste sureste mañana horas partir hasta luego tarde noche manteniendo
""".split())

TIPOS_SIN = [(r"anticiclon|\banti\b|\balta\b", "ANTICICLON"), (r"depresion|\bdepre\b|\bbaja\b", "DEPRESION"),
             (r"ciclogenesis", "CICLOGENESIS"), (r"fuerte gradiente barico", "GRADIENTE"),
             (r"frente fri[oa]|\bcfnt\b", "CFNT"), (r"frente (?:calido|caliente)|\bwfnt\b", "WFNT"),
             (r"frente ocluido|oclusion|\bofnt\b", "OFNT"), (r"frente estacionario", "ESTACIONARIO"),
             (r"vaguada", "VAGUADA")]
TIPOS_EXT = [(r"frente fri[oa]|\bcfnt\b", "CFNT"), (r"frente (?:calido|caliente)|\bwfnt\b", "WFNT"),
             (r"frente ocluido|\bofnt\b", "OFNT"), (r"eje de cu[ñn]a|\bcu[ñn]a\b", "CUNA")]
EVOL_SIN = [(r"intensific", "INTSF"), (r"debilit", "WKN"), (r"profundiz", "DPN"), (r"rellen|colma", "FLN"),
            (r"sin cambios?|\bnc\b", "NC")]


# ====================================================================== utilidades
def normalizar(texto: str) -> str:
    t = texto.replace("ñ", "\x00").replace("Ñ", "\x00")
    t = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
    t = t.replace("\x00", "ñ").lower()
    t = re.sub(r"[*_♥❤✓✔“”\"·•…!¡¿?]", " ", t)
    t = re.sub(r"[–—]", "-", t)
    t = re.sub(r"(?<=[a-z])-(?=[a-z])", " ", t)            # centro-este → centro este
    t = re.sub(r"[ \t]+", " ", t)
    for rx, bien in PRE_ERRATAS:
        t = re.sub(rx, bien, t)
    t = _letras(t)
    sigue = r"(?=\s*\.\s*(?:de|del|a|al|con|y|en|var|variables|ne|nw|se|sw|so|n|s|e|w|o|norte|sur|este|oeste|\d)\b)"
    for abrev, completa in ABREVIATURAS.items():
        # «prob. de lluvias» → sin punto; «lluvias aisl. regular» → el punto cierra la oración
        t = re.sub(rf"\b{abrev}\b{sigue}\s*\.", completa, t)
        t = re.sub(rf"\b{abrev}\b", completa, t)
    for rx, bien in ERRATAS:
        t = re.sub(rx, bien, t)
    t = corregir_erratas(t)
    return re.sub(r"[ \t]+", " ", t)


def corregir_erratas(t: str) -> str:
    def fix(m):
        w = m.group(0)
        if len(w) < 5 or w in VOCAB:
            return w
        cand = difflib.get_close_matches(w, VOCAB, n=1, cutoff=0.85)
        return cand[0] if cand else w
    return re.sub(r"[a-zñ]+", fix, t)


def _hhmm(dia, hh, mm=None):
    dia, hh, mm = int(dia), int(hh), int(mm or 0)
    if not (1 <= dia <= 31 and 0 <= hh <= 23 and 0 <= mm <= 59):
        return None
    return f"{dia:02d}/{hh:02d}{mm:02d}"


HORA_PATRONES = [
    re.compile(r"\b(?P<pre>el|del|desde el|hasta el|hasta|a partir del?)\s+(?P<d>\d{1,2})\s*/\s*(?P<h>\d{2})(?P<m>\d{2})?(?!\d)"
               r"(?:\s*(?:z|utc|hs)\b)?"),
    re.compile(r"\b(?P<pre>el|del|desde el|hasta el|hasta|a partir del?)\s+(?P<d>\d{1,2})\s+a\s+las?\s+(?P<h>\d{1,2})"
               r"(?::(?P<m>\d{2}))?(?:\s*(?:hs|horas|utc|z)\b)?"),
    re.compile(r"\b(?P<pre>el|del|desde el|hasta el|hasta|a partir(?: del?)?)\s+(?P<d>\d{1,2})\s+(?P<h>\d{1,2})\s*z\b"),
    re.compile(r"(?P<pre>)\b(?P<d>\d{1,2})\s+(?P<h>\d{2})\s*z\b"),
]


def horas(texto: str) -> list[tuple[int, int, str, str]]:
    """[(inicio, fin, 'DD/HHMM', prefijo)] sin solapamientos."""
    out, ocupado = [], [False] * len(texto)
    for rx in HORA_PATRONES:
        for m in rx.finditer(texto):
            if any(ocupado[m.start():m.end()]):
                continue
            v = _hhmm(m.group("d"), m.group("h"), m.groupdict().get("m"))
            if v:
                out.append((m.start(), m.end(), v, m.group("pre") or ""))
                ocupado[m.start():m.end()] = [True] * (m.end() - m.start())
    return sorted(out)


def sin_horas(texto: str) -> str:
    for ini, fin, _, _ in reversed(horas(texto)):
        texto = texto[:ini] + " " * (fin - ini) + texto[fin:]
    return texto


POS_RX = re.compile(
    r"\b(?:(?P<a1>\d{2})(?:º\d{2})?\s*s\s*[-/]?\s*(?P<b1>\d{2,3})(?:º\d{2})?\s*[ws]\b"   # 36s34w, 38s 44w, 53s33s
    r"|(?P<a2>\d{2})\s*/\s*(?P<b2>\d{2,3})(?![\d/])"                                    # 55/47
    r"|(?P<a3>\d{2})(?P<b3>\d{2})(?!\d)"                                                # 5126
    r"|(?P<a4>\d{2})\s*-\s*(?P<b4>\d{2,3})(?![\d/s])"                                   # 38-44
    r"|(?P<a5>\d{2})\s+(?P<b5>\d{2,3})(?![\d/sz]))")                                    # 38 32


def posiciones(texto: str) -> list[tuple[int, str]]:
    """[(inicio, '38S 44W')] — descarta horas, presiones y valores imposibles."""
    t = sin_horas(texto)
    out = []
    for m in POS_RX.finditer(t):
        g = m.groupdict()
        lat, lon = next((g[f"a{i}"], g[f"b{i}"]) for i in range(1, 6) if g[f"a{i}"])
        if 25 <= int(lat) <= 78 and 5 <= int(lon) <= 99:
            out.append((m.start(), f"{int(lat)}S {int(lon)}W"))
    return out


def sin_parentesis(texto: str) -> tuple[str, list[str]]:
    notas = []
    while True:
        nuevo = re.sub(r"\(([^()]*)\)", lambda m: notas.append(m.group(1).strip()) or " ", texto)
        if nuevo == texto:
            break
        texto = nuevo
    return re.sub(r"[()]", " ", texto), notas


def oraciones(texto: str) -> list[str]:
    return [o.strip(" ,;:-") for o in re.split(r"(?<!\d)\.|\.(?!\d)|\n", texto) if o.strip(" ,;:-")]


# ====================================================================== secciones
SECCIONES = [
    (re.compile(r"^(\d\s*)?(parte\s*)?(avisos?( de temporal)?|temporales|1 parte)$"), "avisos"),
    (re.compile(r"^(\d\s*(parte)?\s*\.?\s*)?(situacion|sinopsis)( general)?( sinoptica)?( a las.*)?$"), "sinopsis"),
    (re.compile(r"^(\d\s*parte\s*)?(pronosticos?( costeros?)?( de las costas)?|zonas costeras|costas)$"), "costeras"),
    (re.compile(r"^(\d\s*parte\s*)?pronostico de las .*$"), "costeras"),
    (re.compile(r"^(areas?( oceanicas?)?)$"), "oceanicas"),
    (re.compile(r"^navtex$"), "navtex"),
    (re.compile(r"^(navtex\s*:|hielos?|informacion de hielos)"), "ignorar"),
    (re.compile(r"^(al navtex lo que|https?:|fecha |boletin meteorologico|servicio meteorologico|hora y fecha|tec\b)"), "nota"),
]


def separar_secciones(texto: str) -> dict[str, list[str]]:
    secciones = {"avisos": [], "sinopsis": [], "costeras": [], "oceanicas": [], "navtex": []}
    actual = None
    for linea in texto.splitlines():
        l = linea.strip().strip("-•·").strip()
        if not l:
            continue
        cabecera = re.sub(r"^\d\s*[.)]?\s*", lambda m: m.group(0) if "parte" in l[:10] else "", l).rstrip(" :.;")
        cabecera = re.sub(r"\s+", " ", cabecera)
        nombre = next((n for rx, n in SECCIONES if rx.match(cabecera) or rx.match(l)), None)
        if nombre == "nota":
            continue
        if nombre:
            # «NAVTEX: la depresión 1005» trae contenido en la misma línea
            if nombre == "ignorar" and re.match(r"^navtex\s*:", l):
                secciones["navtex"].append(l.split(":", 1)[1].strip())
                actual = "navtex"
                continue
            actual = nombre
            continue
        if actual == "costeras" and re.match(r"^zonas costeras\s*:?$", cabecera):
            continue
        if actual in secciones:
            secciones[actual].append(l)
    return secciones


# ====================================================================== zonas
def _alias(cat):
    out = {"costeras": [], "oceanicas": []}
    extra = {"uruguay": ["costa se de uruguay", "se de uruguay", "sudeste de uruguay", "sudeste del uruguay"],
             "valdes": ["valdes", "peninsula de valdes"],
             "findm": ["costa del fin del mundo"], "malvinas": ["costa malvinas", "costa de malvinas"],
             "drake": ["area drake"], "sanjorge": ["golfo de san jorge"]}
    for z in todas_las_zonas(cat):
        oficial = re.sub(r"\(.*?\)", "", z["es"]).lower().strip()
        nombres = set(z.get("alias", [])) | {oficial, re.sub(r"^(costa de|costa|area)\s+", "", oficial)}
        nombres |= set(extra.get(z["id"], []))
        for n in list(nombres):
            nombres.add(re.sub(r"^(area|costa)\s+(de\s+)?", "", n))
            if z["grupo"] == "oceanicas":
                nombres.add("area " + re.sub(r"^area\s+", "", n))
        if z["grupo"] == "costeras":
            nombres |= {f"costa {n}" for n in list(nombres)}
        for n in nombres:
            if n:
                out[z["grupo"]].append((n, z["id"]))
    for g in out:
        out[g].sort(key=lambda x: -len(x[0]))
    return out


def zona_al_inicio(linea, alias):
    for nombre, zid in alias:
        m = re.match(rf"^{re.escape(nombre)}\b(?:\s*\([^)]*\))?\s*([:.;,]+|$)?\s*", linea)
        if not m:
            continue
        resto = linea[m.end():]
        if m.group(1) is not None or not resto or etiqueta(resto)[0] is not None:
            return zid, resto
    return None, linea


def zonas_mencionadas(texto, alias_todos):
    hallados, t = [], " " + texto + " "
    for nombre, zid in alias_todos:
        for m in re.finditer(rf"(?<![a-z]){re.escape(nombre)}(?![a-z])", t):
            hallados.append((m.start(), zid))
            t = t[:m.start()] + " " * len(nombre) + t[m.end():]
    vistos, out = set(), []
    for _, zid in sorted(hallados):
        if zid not in vistos:
            vistos.add(zid)
            out.append(zid)
    return out


# ---------------------------------------------------------------- subdivisiones
COND_RX = re.compile(r"(?:al\s+)?(norte|sur|este|oeste|n|s|e|w|o)\s*(?:de\s+)?(?:los\s+)?(\d{2,3})(?:º\d{2})?\s*([swo])?\b")
CUADRANTE_RX = re.compile(rf"^(?:al\s+)?{PUNTO_RX}\s+(?:del?|de la)\s+(?:area|zona)$")


def division(texto, dudas=None, donde=""):
    """Interpreta «e de 30w», «s de 47s y e de 50w», «ne del area», «resto»… o None."""
    e = texto.strip(" :;.,-")
    if re.fullmatch(r"(?:toda|entera|todo)(?: el area| la zona| el area)?", e):
        return {"tipo": "entera", "conds": []}
    if re.fullmatch(r"resto(?: del area| de la zona| del)?", e):
        return {"tipo": "resto", "conds": []}
    m = CUADRANTE_RX.match(e)
    if m:
        return {"tipo": "cuadrante", "conds": [], "cuadrante": PUNTOS[m.group(1)]}
    conds, t = [], e
    for m in COND_RX.finditer(e):
        rel = PUNTOS.get(m.group(1), "")
        if len(rel) != 1:
            continue
        conds.append({"rel": rel, "valor": m.group(2) + ("S" if rel in ("N", "S") else "W")})
        t = t.replace(m.group(0), " ", 1)
    for m in re.finditer(r"\b(\d{2,3})\s*([sw])\b", t):
        rel = "S" if m.group(2) == "s" else "E"
        conds.append({"rel": rel, "valor": m.group(1) + m.group(2).upper()})
        t = t.replace(m.group(0), " ", 1)
        if dudas is not None:
            dudas.append({"donde": donde, "texto": texto, "motivo": f"«{m.group(0)}» sin «al norte/sur/este/oeste de»: "
                          f"se interpretó {rel} DE {m.group(1)}{m.group(2).upper()}. Revisar."})
    if not conds or re.sub(r"\b(y|del?|los|area|zona)\b|[-,]", " ", t).strip():
        return None
    return {"tipo": "condiciones", "conds": conds}


def etiqueta(linea):
    """(etiqueta, resto) si la línea empieza con una subdivisión; (None, linea) si no."""
    m = re.match(r"^([^:]{1,45}?)\s*[:;]+\s*(.*)$", linea)
    if m and division(m.group(1)):
        return m.group(1), m.group(2)
    if division(linea):
        return linea, ""
    return None, linea


def unir_renglones(renglones):
    """Une los renglones de un mismo pronóstico (PDF cortado, un renglón por elemento…)."""
    texto = ""
    for r in renglones:
        r = r.strip()
        if not r:
            continue
        if not texto:
            texto = r
        elif texto.rstrip().endswith(".") or re.search(r"\b(de|y|a|con|del|al|en|la|las|el|los|o)$", texto) \
                or not re.match(r"^(vientos?|probabilidad|baja|vis\b|neblina|niebla|"
                                r"lluvia|llovizna|chaparr|tormenta|nevada|sin fenomeno)", r):
            texto += " " + r
        else:
            texto += ". " + r
    return texto


# ====================================================================== viento
def _direccion(texto):
    if re.search(r"direcciones variables|\bvariables?\b|\bvrb\b", texto):
        return "VRB"
    for rx in (rf"\b(?:del|al|a|de)?\s*sector\s+{PUNTO_RX}\b",
               rf"\b(?:del|al)\s+{PUNTO_RX}\b",
               rf"\ba\s+(ne|nw|se|sw|so|norte|sur|este|oeste|noreste|noroeste|sudeste|sudoeste)\b",
               rf"\b(?:horario|antihorario|anti)\s+(?:a\s+|al\s+)?{PUNTO_RX}\b",
               rf"\b{FUERZA_RX}\s+(ne|nw|se|sw|so)\b"):
        m = re.search(rx, texto)
        if m:
            p = PUNTOS[m.group(1)]
            return f"SECTOR {p}" if len(p) == 1 else p
    return ""


def _rafagas(texto):
    m = re.search(rf"(?:con\s+)?{RAFAGAS_RX}(?:\s+(?:de\s+|del\s+)?(temporal fuerte|temporal|muy fuertes|fuertes))?", texto)
    if not m:
        return "", "", texto
    resto = texto[:m.start()] + " " + texto[m.end():]
    if m.group(1):
        return "INT", next(k for rx, k in FUERZAS if re.fullmatch(rx, m.group(1))), resto
    return "CON", "", resto


def _fuerzas(texto):
    encontrados, t = [], texto
    for rx, clave in FUERZAS:
        for m in re.finditer(rf"\b{rx}\b", t):
            encontrados.append((m.start(), clave))
            t = t[:m.start()] + " " * (m.end() - m.start()) + t[m.end():]
    out = [c for _, c in sorted(encontrados)]
    for n in re.findall(r"\b(\d{1,2})\s*/\s*(\d{1,2})\b|\bfuerza\s+(\d{1,2})\b", sin_horas(texto)):
        out += [x for x in n if x]
    return out


def _segmento(texto):
    hs = horas(texto)
    hora = hs[0][2] if hs else ""
    t = sin_horas(texto)
    raf, raf_int, t = _rafagas(t)
    return {"dir": _direccion(t), "fuerza": _fuerzas(t), "rafagas": raf, "raf_int": raf_int, "hora": hora}


def _valor(k):
    from .catalogo import cargar
    escala = cargar()["viento"]["escala"]["valores"]
    return escala.get(k, int(k) if str(k).isdigit() else 0)


def viento(texto, dudas, donde):
    # «…, luego antihorario a …» sin verbo: es otro cambio
    texto = re.sub(r"\b(?:y\s+)?luego\s+(?=(?:en sentido\s+)?(?:anti)?horario)", "rotando ", texto)
    partes = [p for p in re.split(rf",?\s*\b(?={CAMBIO_RX}\b)", texto) if p.strip(" ,")]
    base = _segmento(partes[0])
    obs = []
    m = re.search(rf"prevaleciendo\s+(?:del\s+)?(?:sector\s+)?{PUNTO_RX}\b", partes[0])
    if m:
        p = PUNTOS[m.group(1)]
        obs.append(f"PREVALECIENDO DEL {'SECTOR ' + p if len(p) == 1 else p}")
    cambios, anterior = [], base
    for p in partes[1:]:
        seg = _segmento(p)
        tempo = bool(re.search(r"temporari|temporalmente", p))
        if re.search(r"antihorario|sentido anti|\banti\b", p):
            tipo = "BACK"
        elif re.search(r"horario", p):
            tipo = "VEER"
        elif re.match(r"(aumenta|incrementa)", p):
            tipo = "INCR"
        elif re.match(r"disminuy", p):
            tipo = "DECR"
        else:  # «cambiando»/«rotando» sin sentido
            f_ant = max([_valor(x) for x in anterior["fuerza"]] or [0])
            f_nue = max([_valor(x) for x in seg["fuerza"]] or [0])
            if seg["dir"] and seg["dir"] != anterior["dir"]:
                tipo = "VEER"
                dudas.append({"donde": donde, "texto": p, "motivo": "El cambio de dirección no dice si es horario "
                              "o antihorario: se puso VEER (horario). Revisar."})
            else:
                tipo = "INCR" if f_nue > f_ant else "DECR"
        if tipo in ("INCR", "DECR") and seg["dir"] == anterior["dir"]:
            seg["dir"] = ""
        if tipo in ("VEER", "BACK") and seg["fuerza"] == anterior["fuerza"]:
            seg["fuerza"] = []          # misma fuerza: no se repite
        if len(seg["fuerza"]) > 2:
            dudas.append({"donde": donde, "texto": p, "motivo": "Hay más de dos fuerzas en un mismo tramo del viento: "
                          "se tomaron las dos primeras. Revisar."})
            seg["fuerza"] = seg["fuerza"][:2]
        cambios.append({"tempo": tempo, "tipo": tipo, **seg})
        anterior = {**seg} if seg["dir"] else {**anterior, "fuerza": seg["fuerza"] or anterior["fuerza"]}
    if base["hora"]:
        dudas.append({"donde": donde, "texto": partes[0], "motivo": f"Hora {base['hora']} en el viento inicial, "
                      "sin cambio asociado: se omitió. Revisar."})
    return {"dir": base["dir"], "fuerza": base["fuerza"], "rafagas": base["rafagas"], "raf_int": base["raf_int"],
            "cambios": cambios}, obs


def es_viento(oracion):
    o = re.sub(r"^vientos?\s+(?:de\s+)?", "", oracion)
    return bool(re.match(rf"^(?:de\s+)?(?:{FUERZA_RX}|direcciones variables)", o))


def es_cambio(oracion):
    return bool(re.match(rf"(?:y\s+)?(?:luego\s+)?{CAMBIO_RX}\b", oracion))


# ====================================================================== fenómenos y visibilidad
def visibilidad(texto):
    t = texto.strip()
    if not VIS_FRASE.match(t):
        return None
    out = {"v1": "", "hasta": "", "ocnl": "", "ocnl_antes": False}
    rel = None
    for m in re.finditer(rf"{VIS_VAL}|\b{VIS_CON}\b", re.sub(r"^vis\s+", "", t)):
        v, c = m.group(1), m.group(2)
        if c:
            rel = "hasta" if c in ("a", "o") else "ocnl"
            if rel == "ocnl" and not out["hasta"]:
                out["ocnl_antes"] = True
        elif not out["v1"]:
            out["v1"] = VIS[v]
        elif rel:
            out[rel] = VIS[v]
    if out["ocnl_antes"] and not out["hasta"]:
        out["ocnl_antes"] = False
    return out


def _trozos_fenomenos(oracion):
    """Separa «neblinas en disipacion neblinas a partir de la noche» en dos grupos."""
    empieza_luego = bool(re.match(r"\s*(?:y\s+)?luego\b", oracion))
    partes = [p for p in re.split(r"[,;]?\s*\b(?:y\s+)?luego\b\s*", oracion) if p.strip()]
    out = []
    for k, p in enumerate(partes, start=1 if empieza_luego else 0):
        cortes = [0]
        visto_cola = False
        for m in re.finditer(r"\b(?:desmejorando con|baja probabilidad|probabilidad|probables?)\b|"
                             + "|".join(rx for rx, _ in FENOMENOS) + "|"
                             + "|".join(rx for rx, _ in EVOLUCIONES + MOMENTOS), p):
            es_fen = any(re.fullmatch(rx, m.group(0)) for rx, _ in FENOMENOS) or "probab" in m.group(0) \
                or m.group(0).startswith(("probable", "desmejorando"))
            if es_fen and visto_cola and m.start() > cortes[-1]:
                cortes.append(m.start())
                visto_cola = False
            elif not es_fen:
                visto_cola = True
            if "probab" in m.group(0) and m.start() > cortes[-1] and m.start() > 0 and not visto_cola:
                previo = p[cortes[-1]:m.start()]
                if any(re.search(rx, previo) for rx, _ in FENOMENOS):
                    cortes.append(m.start())
        for i, c in enumerate(cortes):
            trozo = p[c:cortes[i + 1] if i + 1 < len(cortes) else len(p)]
            # «lluvias aisladas y tormentas»: el calificativo es solo de las lluvias
            cal_rx = "|".join(rx for rx, _ in CALIFICATIVOS)
            fen_rx = "|".join(rx for rx, _ in FENOMENOS)
            m = re.search(rf"\b(?:{cal_rx})\b\s*(?:,|\by\b)\s*(?=(?:{fen_rx}))", trozo)
            if m and any(re.search(rx, trozo[:m.start()]) for rx, _ in FENOMENOS):
                corte = m.start() + len(re.match(rf"(?:{cal_rx})", trozo[m.start():]).group(0))
                out.append((trozo[:corte], "LUEGO" if k > 0 and i == 0 else ""))
                out.append((trozo[m.end():], "Y"))
                continue
            out.append((trozo, "LUEGO" if k > 0 and i == 0 else ""))
    return out


def _item(trozo, conector, dudas, donde):
    it = {"conector": conector, "prob": "", "fen": [], "cal": "", "momento": "", "evol": "", "momento_evol": "",
          "hora_evol": "", "hora_evol_tipo": "el"}
    t = trozo
    sin_prob = "sin proba" in t
    for rx, clave in PROBABILIDADES:
        m = re.search(rx, t)
        if m:
            it["prob"] = clave
            t = t[:m.start()] + " " * (m.end() - m.start()) + t[m.end():]
            break
    pos_evol = None
    for rx, clave in EVOLUCIONES:
        m = re.search(rx, t)
        if m:
            it["evol"], pos_evol = clave, m.start()
            t = t[:m.start()] + " " * (m.end() - m.start()) + t[m.end():]
            break
    for rx, clave in MOMENTOS:
        for m in re.finditer(rx, t):
            campo = "momento_evol" if pos_evol is not None and m.start() > pos_evol else "momento"
            if not it[campo]:
                it[campo] = clave
                t = t[:m.start()] + " " * (m.end() - m.start()) + t[m.end():]
    encontrados = []
    for rx, clave in FENOMENOS:
        for m in re.finditer(rx, t):
            encontrados.append((m.start(), clave))
            t = t[:m.start()] + " " * (m.end() - m.start()) + t[m.end():]
    it["fen"] = []
    for _, c in sorted(encontrados):
        if c not in it["fen"]:
            it["fen"].append(c)
    for rx, clave in CALIFICATIVOS:
        m = re.search(rf"\b{rx}\b", t)
        if m:
            it["cal"] = clave
            t = t[:m.start()] + " " + t[m.end():]
            break
    if sin_prob:
        it["prob"] = ""
        t = t.replace("sin proba", " ")
    hs = horas(trozo)
    if hs and pos_evol is not None and any(h[0] > pos_evol for h in hs):
        ini, fin, valor, pre = next(h for h in hs if h[0] > pos_evol)   # «mejorando el 24 a las 18»
        it["hora_evol"], it["hora_evol_tipo"] = valor, ("desde" if re.search(r"partir|desde", pre) else "el")
        hs = [h for h in hs if h[0] != ini]
    if hs:
        dudas.append({"donde": donde, "texto": trozo, "motivo": "Los fenómenos no llevan hora en el boletín; "
                      "la hora se omitió. Revisar."})
    t = sin_horas(t)
    sobrante = re.sub(RELLENO + r"|[,;:.]|\b\d+\b", " ", t).strip()
    return it, sobrante


def fenomenos(oracion, items, dudas, donde):
    if re.search(r"\bsin fenomenos?\b", oracion):
        return "sin"
    for trozo, conector in _trozos_fenomenos(oracion):
        it, sobrante = _item(trozo, conector, dudas, donde)
        if not it["fen"] and (it["evol"] or it["momento"] or it["momento_evol"]):
            # «Mejorando.», «desmejorando hacia el final del periodo», «mej el 24 a las 18»
            if items and not items[-1]["evol"] and it["evol"]:
                ultimo = items[-1]
                ultimo["evol"] = it["evol"]
                ultimo["momento_evol"] = it["momento_evol"] or it["momento"]
                ultimo["hora_evol"], ultimo["hora_evol_tipo"] = it["hora_evol"], it["hora_evol_tipo"]
            elif it["evol"]:      # evolución sola, o una segunda evolución: va como grupo propio
                it["momento_evol"] = it["momento_evol"] or it["momento"]
                it["momento"] = ""
                it["conector"] = it["conector"] or ("LUEGO" if items else "")
                items.append(it)
            elif items and not items[-1]["momento"]:
                items[-1]["momento"] = it["momento"] or it["momento_evol"]
            continue
        if sobrante:
            dudas.append({"donde": donde, "texto": trozo.strip(), "motivo": f"No se reconoció «{sobrante}»; se omitió."})
        if it["fen"]:
            items.append(it)
        elif trozo.strip() and not sobrante:
            dudas.append({"donde": donde, "texto": trozo.strip(), "motivo": "No se reconoció esta parte; se omitió."})
    return "ok"


def pronostico_zona(cuerpo, dudas, donde):
    """Una subzona: viento, fenómenos, visibilidad."""
    sz = {"division": {"tipo": "entera", "conds": [], "lat1": "", "lat2": "", "lon1": "", "lon2": ""},
          "viento": {"dir": "", "fuerza": [], "rafagas": "", "raf_int": "", "cambios": []},
          "fenomenos": {"sin_fenomenos": False, "items": []},
          "vis": {"v1": "", "hasta": "", "ocnl": "", "ocnl_antes": False}, "obs": "", "obs_en": ""}
    cuerpo = re.sub(r"\s*\bvis\b", ". vis", cuerpo)            # la visibilidad siempre arranca oración
    texto_viento, obs, sin = [], [], False
    for o in oraciones(cuerpo):
        # viento + fenómenos en la misma oración, sin puntuación (estilo telegráfico)
        if (es_viento(o) or es_cambio(o)) and FEN_INICIO.search(o):
            m = FEN_INICIO.search(o)
            if m.start() > 0:
                previa, o = o[:m.start()].strip(" ,"), o[m.start():]
                texto_viento.append(previa)
        trozos = [x.strip() for x in o.split(",")]
        if len(trozos) > 1 and visibilidad(trozos[-1]) and not es_viento(o):
            sz["vis"], o = visibilidad(trozos[-1]), ", ".join(trozos[:-1])
        if visibilidad(o):
            sz["vis"] = visibilidad(o)
        elif o.startswith("vis"):
            dudas.append({"donde": donde, "texto": o, "motivo": "No se reconoció la visibilidad."})
        elif es_viento(o) and not texto_viento:
            texto_viento.append(o)
        elif es_cambio(o) and texto_viento:
            texto_viento.append(o)
        elif o.strip():
            if fenomenos(o, sz["fenomenos"]["items"], dudas, donde) == "sin":
                sin = True
    if texto_viento:
        sz["viento"], obs = viento(", ".join(texto_viento), dudas, donde)
    else:
        dudas.append({"donde": donde, "texto": cuerpo, "motivo": "No se encontró el viento."})
    if not sz["fenomenos"]["items"]:
        sz["fenomenos"]["sin_fenomenos"] = True
    elif sin:
        dudas.append({"donde": donde, "texto": cuerpo, "motivo": "Dice «sin fenómenos» pero también hay fenómenos."})
    if not sz["vis"]["v1"]:
        dudas.append({"donde": donde, "texto": cuerpo, "motivo": "No se encontró la visibilidad."})
    if obs:
        sz["obs"] = " ".join(obs)
        sz["obs_en"] = sz["obs"].replace("PREVALECIENDO DEL", "MAINLY FROM")
    return sz


# ====================================================================== avisos
# Formas de decir que un aviso sigue o se actualiza (con erratas frecuentes)
ACTUALIZA_RX = re.compile(r"\b(?:se\s+)?a\w{0,2}uali[zs]\w*|\bsi(?:g|gu)e\s+vigente\b|\bcontin[uú]a(?:\s+vigente)?\b|"
                          r"\bse\s+mantiene(?:\s+vigente)?\b|\bpersiste\b|\b(?:se\s+)?ratific\w*|\b(?:se\s+)?renueva\b|"
                          r"\bvigente\b|\bupdate\w*")
INICIO_AVISO = re.compile(r"^(?:navtex\s+)?(?:se actualiza|a\w{0,2}ualiz\w*|sigue vigente|nuevo\b|aviso\b|\d{3,4}\b)")
SIN_AVISOS = re.compile(r"^(no hay avisos?|sin avisos?|nil|no hay|ninguno)\b")


def _area_coords(texto):
    m = re.search(r"(\d{2})\s*s?\s*-\s*(\d{2})\s*s\s*,?\s*(\d{2,3})\s*w?\s*-\s*(\d{2,3})\s*w", texto)
    if m:
        return "{}S-{}S {}W-{}W".format(*m.groups()), False
    nums = []
    for n in re.findall(r"\d+", sin_horas(texto)):
        nums += [n[:2], n[2:]] if len(n) == 4 else [n]
    nums = [n for n in nums if len(n) in (2, 3)]
    if len(nums) >= 4:
        return f"{nums[0]}S-{nums[1]}S {nums[2]}W-{nums[3]}W", True
    return "", False


ORDEN_ZONAS: dict = {}


def avisos(lineas, alias_todos, dudas):
    bloques = []
    for l in lineas:
        if SIN_AVISOS.match(l):
            continue
        if not bloques or INICIO_AVISO.match(l) or (bloques[-1].rstrip().endswith(".") and
                                                    re.match(r"^(fuerte gradiente|depresion|frente)", l)):
            bloques.append(l)
        else:
            bloques[-1] += " " + l
    out = []
    for texto in bloques:
        a = {"numero": "", "estado": "nuevo", "causa": "GRADIENTE", "detalle": "", "detalle_en": "", "verbo": "presente",
             "fuerza": "TEMPORAL", "dir": "", "rafagas": False, "zonas": [], "coords": "", "desde": "", "hasta": "",
             "navtex": "navtex" in texto}
        t = re.sub(r"\bnavtex\b", " ", texto)
        m = re.search(r"aviso\s*(\d{2,4})", t) or re.match(r"^\s*(\d{3,4})\b", t)
        if m:
            a["numero"] = m.group(1)
            cuerpo = t[m.end():]
        else:
            cuerpo = re.sub(r"^.*?\b(?:nuevo aviso|aviso nuevo|nuevo)\s*:?", "", t)
        donde = f"Aviso {a['numero'] or '(sin número)'}"
        if ACTUALIZA_RX.search(t):
            a["estado"] = "actualiza"
        cuerpo = re.sub(r"^\s*[:.]?\s*", "", ACTUALIZA_RX.sub(" ", cuerpo)).strip()
        cuerpo = re.sub(r"^[:.,\s]+", "", cuerpo)
        if not a["numero"] and a["estado"] != "nuevo":
            dudas.append({"donde": donde, "texto": texto, "motivo": "El aviso se actualiza pero no dice qué número: "
                          "completalo en «Ajuste fino»."})
        if re.match(r"\s*ces[ae]\w*\b", cuerpo):
            a["estado"] = "cese"
            out.append(a)
            continue
        if re.match(r"\s*(?:a?fuera+)\b", cuerpo):
            a["estado"] = "fuera_area"
            out.append(a)
            continue
        idx = re.search(r"provoc\w*", cuerpo)
        causa_txt = cuerpo[:idx.start()] if idx else cuerpo
        efecto = cuerpo[idx.start():] if idx else cuerpo
        dep = re.search(r"\b(?:depresion|depre|baja)\s+(\d{3,4})", causa_txt)
        if dep:
            pos = [p for _, p in posiciones(causa_txt[dep.end():])][:1]
            a["causa"], a["detalle"] = "DEPRESION", " ".join([f"{dep.group(1)}HPA", *pos])
        elif re.search(r"frente fri", causa_txt):
            a["causa"], a["detalle"] = "CFNT", " ".join(p for _, p in posiciones(causa_txt))
        elif re.search(r"ciclogenesis", causa_txt):
            a["causa"], a["detalle"] = "CICLOGENESIS", " ".join(p for _, p in posiciones(causa_txt))
        elif not re.search(r"gradiente", causa_txt):
            dudas.append({"donde": donde, "texto": texto, "motivo": "No se reconoció la causa; se puso fuerte gradiente bárico."})
        mov = re.search(rf"(?:\bmov\b|se mueve|moviendose|se desplaza)\s+(?:hacia\s+el\s+|al\s+|hacia\s+)?{PUNTO_RX}\b", causa_txt)
        if mov:
            a["detalle"] = (a["detalle"] + f" MOV {PUNTOS[mov.group(1)]}").strip()
        a["verbo"] = "futuro" if re.search(r"provocar(?:a|ia)\b", efecto) else "presente"
        if re.search(r"temporal fuerte", efecto):
            a["fuerza"] = "TEMPORAL_FUERTE"
        elif re.search(r"fuerza\s+(\d{1,2})", efecto):
            a["fuerza"] = re.search(r"fuerza\s+(\d{1,2})", efecto).group(1)
        elif not re.search(r"temporal", efecto):
            dudas.append({"donde": donde, "texto": texto, "motivo": "No indica la fuerza: se puso temporal (8)."})
        a["rafagas"] = bool(re.search(RAFAGAS_RX, efecto))
        for ini, fin, valor, pre in horas(efecto):
            if pre.startswith("hasta"):
                a["hasta"] = valor
            else:
                a["desde"] = a["desde"] or valor
        if re.search(r"a partir del?\s+\d+\s*/\s*\d{5,}", efecto):
            dudas.append({"donde": donde, "texto": texto, "motivo": "La hora de inicio no es válida. Revisar."})
        md = re.search(rf"(?:temporal(?: fuerte)?|fuerza\s+\d+|vientos?)\s+(.*?)(?:\b(?:con\s+)?{RAFAGAS_RX}|\ben\b|\bentre\b|$)", efecto)
        a["dir"] = _direccion(md.group(1) if md else efecto)
        m_donde = re.search(r"\b(?:en|entre)\b\s+(.*)$", re.sub(rf"(?:con\s+)?{RAFAGAS_RX}", " ", efecto))
        donde_txt = m_donde.group(1) if m_donde else ""
        a["zonas"] = sorted(zonas_mencionadas(donde_txt, alias_todos), key=lambda z: ORDEN_ZONAS.get(z, 99))
        if not a["zonas"]:
            a["coords"], dudoso = _area_coords(donde_txt)
            if dudoso:
                dudas.append({"donde": donde, "texto": texto, "motivo": f"Se interpretó el área como {a['coords']}. Revisar."})
        if "alrededor" in efecto:
            dudas.append({"donde": donde, "texto": texto, "motivo": "«Alrededor de la misma» no tiene forma en el boletín; "
                          "se usó el área indicada. Revisar."})
        if not a["zonas"] and not a["coords"]:
            dudas.append({"donde": donde, "texto": texto, "motivo": "No se encontró el área afectada."})
        if not a["dir"]:
            dudas.append({"donde": donde, "texto": texto, "motivo": "No se encontró la dirección del viento."})
        out.append(a)
    return out


# ====================================================================== sinopsis
def _mov(texto):
    m = re.search(rf"(?:\bmov\b|mueve|moviendose|desplaza\w*)\s+(?:sin cambios?\s+)?(?:hacia\s+el\s+|al\s+|hacia\s+|el\s+)?"
                  rf"{PUNTO_RX}\b", texto)
    if m:
        return "MOV " + PUNTOS[m.group(1)]
    if re.search(r"sin movimientos?|estacionari|\bstnr\b", texto):
        return "STNR"
    return ""


def _posiciones_y_final(texto):
    """(posición inicial, posición final, hora)."""
    if re.search(r"sin posicion final", texto):
        corte = None
    else:
        m = re.search(r"(?:con\s+)?pos(?:icion)?\s+final|\bexp\b", texto)
        corte = m.end() if m else None
        if corte is None:   # «se mueve al SE 57-21 el 2 a las 12»
            m = re.search(rf"(?:mueve|\bmov\b|moviendose)\s+\S+\s+{PUNTO_RX}?", texto)
            if m and horas(texto[m.end():]):
                corte = m.end()
    ps = posiciones(texto)
    ini = " ".join(p for i, p in ps if corte is None or i < corte)
    fin = " ".join(p for i, p in ps if corte is not None and i >= corte)
    hs = horas(texto[corte:] if corte is not None else texto)
    return ini, fin, hs[0][2] if hs else ""


def sinopsis(lineas, dudas):
    bloques = []
    for l in lineas:
        cabeza = re.sub(r"^navtex\s+", "", l)[:28]
        sigue = bool(bloques) and re.search(r"(?:\b(?:extiende|asocia\w*|con|en|y|de|un|el|al)|,)$", bloques[-1])
        if not bloques or (not sigue and (any(re.match(rf"(?:{rx})", cabeza) for rx, _ in TIPOS_SIN)
                                          or bloques[-1].endswith("."))):
            bloques.append(l)
        else:
            bloques[-1] += " " + l
    out = []
    for blq in bloques:
        texto, notas = sin_parentesis(blq)
        navtex = "navtex" in blq
        texto = re.sub(r"\bnavtex\b", " ", texto).strip()
        partes = re.split(r"\b(?:extiende|asocia(?:do)?(?:\s+con)?)\b\s*(?:un\s+)?", texto)
        principal = partes[0]
        tipo = next((k for rx, k in TIPOS_SIN if re.search(rx, principal[:30])), None)
        if not tipo:
            dudas.append({"donde": "Sinopsis", "texto": blq, "motivo": "No se reconoció el tipo de sistema; se omitió."})
            continue
        s = {"tipo": tipo, "presion": "", "pos": "", "mov": "" if tipo == "ESTACIONARIO" else _mov(principal), "evol": [], "exp_pos": "", "exp_hora": "",
             "ext_tipo": "", "ext_pos": "", "ext_mov": "", "ext_exp_pos": "", "ext_exp_hora": "", "navtex": navtex}
        mp = re.search(r"\b(9\d{2}|10[0-6]\d)(?!\d)\s*(?:hpa)?", principal)
        if mp and tipo in ("DEPRESION", "ANTICICLON"):
            s["presion"] = mp.group(1)
            principal = principal[:mp.start()] + " " + principal[mp.end():]
        s["evol"] = [k for rx, k in EVOL_SIN if re.search(rx, principal)]
        if tipo == "GRADIENTE":
            s["pos"], _ = _area_coords(principal)
        else:
            s["pos"], s["exp_pos"], s["exp_hora"] = _posiciones_y_final(principal)
        if tipo == "CICLOGENESIS" and not s["exp_pos"]:
            s["pos"], s["exp_pos"] = "", s["pos"]
        if len(partes) > 1:
            ext = partes[1]
            s["ext_tipo"] = next((k for rx, k in TIPOS_EXT if re.search(rx, ext[:25])), "CFNT")
            s["ext_mov"] = _mov(ext)
            s["ext_pos"], s["ext_exp_pos"], s["ext_exp_hora"] = _posiciones_y_final(ext)
            if not s["ext_pos"]:
                dudas.append({"donde": "Sinopsis", "texto": blq, "motivo": "No se encontró la posición del frente o eje."})
        if len(partes) > 2:
            dudas.append({"donde": "Sinopsis", "texto": blq, "motivo": "El sistema tiene más de un frente o eje asociado: "
                          "se tomó solo el primero. Revisar."})
        out.append(s)
    return out


def marcar_navtex(sistemas, avisos_, lineas, dudas):
    """Sección NAVTEX al final del borrador: marca los avisos y sistemas que nombra."""
    for l in lineas:
        ma = re.search(r"aviso\s*(\d{2,4})|\b(aviso nuevo|nuevo aviso|nuevo)\b", l)
        if ma:
            elegidos = [a for a in avisos_ if (ma.group(1) and a["numero"] == ma.group(1))
                        or (ma.group(2) and (not a["numero"] or a["estado"] == "nuevo"))]
            for a in elegidos[:1]:
                a["navtex"] = True
            if not elegidos:
                dudas.append({"donde": "NAVTEX", "texto": l, "motivo": "No se encontró el aviso que se pide para NAVTEX."})
            continue
        tipo = next((k for rx, k in TIPOS_SIN if re.search(rx, l[:30])), None)
        if not tipo:
            continue          # notas sueltas («no olvidar los hielos»)
        mp = re.search(r"\b(9\d{2}|10[0-6]\d)(?!\d)", l)
        candidatos = [s for s in sistemas if s["tipo"] == tipo and (not mp or s["presion"] == mp.group(1))]
        if candidatos:
            candidatos[0]["navtex"] = True
        elif l.strip():
            dudas.append({"donde": "NAVTEX", "texto": l, "motivo": "No se encontró en la sinopsis el sistema que se pide para NAVTEX."})


# ====================================================================== principal
def interpretar(cat: dict, texto: str) -> dict:
    dudas = []
    alias = _alias(cat)
    alias_todos = sorted(alias["costeras"] + alias["oceanicas"], key=lambda x: -len(x[0]))
    nombres = {z["id"]: z["es"] for z in todas_las_zonas(cat)}
    ORDEN_ZONAS.update({z["id"]: i for i, z in enumerate(todas_las_zonas(cat))})   # avisos: zonas de norte a sur
    sec = separar_secciones(normalizar(texto))

    # En la sección costera también pueden venir las áreas oceánicas sin título propio
    # («ÁREA NORTE: …»): se reconocen por «área …» o «Drake».
    oceanicas_explicitas = [(n, z) for n, z in alias["oceanicas"] if n.startswith("area ") or "drake" in n]
    por_seccion = {"costeras": alias["costeras"] + oceanicas_explicitas, "oceanicas": alias["oceanicas"]}
    zonas, fuente_copia = [], None
    for grupo in ("costeras", "oceanicas"):
        bloques = []          # [{zona, partes: [[etiqueta, [renglones]]]}]
        for linea in sec[grupo]:
            zid, resto = zona_al_inicio(linea, por_seccion[grupo])
            if zid:
                bloques.append({"zona": zid, "partes": [[None, []]]})
            elif not bloques:
                dudas.append({"donde": "Pronóstico", "texto": linea, "motivo": "Línea fuera de una zona; se omitió."})
                continue
            if not resto.strip():
                continue
            lab, cuerpo = etiqueta(resto)
            partes = bloques[-1]["partes"]
            if lab is not None:
                if partes[-1][0] is None and not partes[-1][1]:
                    partes[-1][0] = lab
                else:
                    partes.append([lab, []])
            if cuerpo.strip():
                partes[-1][1].append(cuerpo)

        for blq in bloques:
            zid = blq["zona"]
            donde = nombres[zid]
            z = {"zona": zid, "copiar_de": "", "subzonas": []}
            partes = [(lab, unir_renglones(r)) for lab, r in blq["partes"] if r or lab]
            partes = [(lab, c) for lab, c in partes if c.strip()]
            if not partes:
                continue
            primero, notas = sin_parentesis(partes[0][1])
            marca_copia = any(re.search(r"copi|peg", n) for n in notas)
            hay_pronostico = bool(_fuerzas(primero) or visibilidad(primero.strip(" .")) or "direcciones variables" in primero)
            if not hay_pronostico and re.search(r"\b(idem|igual|copia\w*|copiar|pegar|pegamos)\b", partes[0][1]):
                mencion = [m for m in zonas_mencionadas(primero, alias_todos) if m != zid]
                if mencion:
                    origen = mencion[0]
                elif re.search(r"\b(idem|igual)\b", primero):
                    origen = zonas[-1]["zona"] if zonas else None
                else:
                    origen = fuente_copia
                if origen:
                    z["copiar_de"] = origen
                    dudas.append({"donde": donde, "texto": partes[0][1], "motivo": f"Copiado de {nombres[origen]}. Verificar."})
                    zonas.append(z)
                else:
                    dudas.append({"donde": donde, "texto": partes[0][1],
                                  "motivo": "Dice que se copie, pero no hay ningún pronóstico para copiar."})
                continue
            if marca_copia:
                fuente_copia = zid
            for lab, cuerpo in partes:
                limpio, notas = sin_parentesis(cuerpo)
                if any("sin proba" in n for n in notas):
                    i = cuerpo.find("(")
                    previas = oraciones(sin_parentesis(cuerpo[:i])[0])
                    if previas:
                        limpio = limpio.replace(previas[-1], previas[-1] + " sin proba", 1)
                sz = pronostico_zona(limpio, dudas, donde)
                if lab:
                    d = division(lab, dudas, donde)
                    sz["division"].update(d or {"tipo": "entera", "conds": []})
                z["subzonas"].append(sz)
            if len(z["subzonas"]) > 1 and any(s["division"]["tipo"] == "entera" for s in z["subzonas"]):
                dudas.append({"donde": donde, "texto": "", "motivo": "Zona con varias partes y alguna sin indicar a qué "
                              "parte del área corresponde."})
            zonas.append(z)

    sistemas = sinopsis(sec["sinopsis"], dudas)
    lista_avisos = avisos(sec["avisos"], alias_todos, dudas)
    marcar_navtex(sistemas, lista_avisos, sec["navtex"], dudas)
    return {"avisos": lista_avisos, "sinopsis": sistemas,
            "zonas": [z for z in zonas if z["subzonas"] or z["copiar_de"]], "dudas": dudas}
