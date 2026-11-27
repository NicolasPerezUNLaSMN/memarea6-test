"""Texto claro del pronosticador → datos estructurados del boletín.

La IA solo INTERPRETA: devuelve los datos con el vocabulario cerrado del
catálogo (el esquema lo impone). El texto final lo arma render.py con reglas
fijas, igual que si se hubiera cargado a mano.

Dos partes:
  llamar_ia()   llama al modelo con el texto y devuelve su JSON crudo.
  a_boletin()   convierte ese JSON en un boletín (sin IA, testeable).
"""
import copy
import io
import json
import os

from . import modelo
from .catalogo import todas_las_zonas

MODELO_DEFECTO = "claude-sonnet-5-5"

PLANTILLA = """AVISOS:


SITUACION:


PRONOSTICO COSTERO:
Rio de la Plata interior:
Rio de la Plata exterior:
Costa sudeste del Uruguay:
Mar del Plata:
Bahia Blanca:
Peninsula Valdes:
Golfo San Jorge:
Patagonia Sur:
Fin del mundo:
Islas Malvinas:

AREAS OCEANICAS:
Area norte:
Area centro este:
Area centro oeste:
Area sudeste:
Area sudoeste:
Drake:
"""


# ====================================================================== lectura
def _resaltado(parrafo) -> bool:
    """¿El párrafo tiene texto resaltado (no blanco)? Así marcan algunos lo que va al NAVTEX."""
    from docx.enum.text import WD_COLOR_INDEX

    for r in parrafo.runs:
        if r.text.strip() and r.font.highlight_color not in (None, WD_COLOR_INDEX.WHITE, WD_COLOR_INDEX.AUTO):
            return True
    return False


def leer_archivo(datos: bytes, nombre: str) -> str:
    if nombre.lower().endswith(".docx"):
        import docx  # python-docx

        doc = docx.Document(io.BytesIO(datos))
        lineas = []
        for p in doc.paragraphs:
            texto = p.text
            # lo resaltado se marca como NAVTEX (salvo la nota que explica el color)
            if texto.strip() and _resaltado(p) and "navtex" not in texto.lower():
                texto = "NAVTEX " + texto
            lineas.append(texto)
        for tabla in doc.tables:
            for fila in tabla.rows:
                lineas.append(" | ".join(c.text for c in fila.cells))
        return "\n".join(lineas)
    if nombre.lower().endswith(".pdf"):
        import pypdf

        lector = pypdf.PdfReader(io.BytesIO(datos))
        paginas = [p.extract_text(extraction_mode="layout") for p in lector.pages]
        return "\n".join(l.strip() for pag in paginas for l in pag.splitlines())
    for cod in ("utf-8", "cp1252", "latin-1"):
        try:
            return datos.decode(cod)
        except UnicodeDecodeError:
            continue
    return datos.decode("utf-8", errors="replace")


# ====================================================================== esquema
def _esquema(cat: dict) -> dict:
    escala = list(cat["viento"]["escala"]["valores"])
    fuerzas = escala + [str(i) for i in range(13)]
    dirs = [""] + cat["viento"]["direcciones"]
    fen = cat["fenomenos"]
    zonas = [z["id"] for z in todas_las_zonas(cat)]
    S = lambda **k: {"type": "string", **k}
    E = lambda vals: {"type": "string", "enum": list(vals)}
    A = lambda items: {"type": "array", "items": items}
    O = lambda props, req=None: {"type": "object", "properties": props, "required": req or list(props)}

    rafagas = E(["", "CON", "INT"])
    cambio = O({"tempo": {"type": "boolean"}, "tipo": E(cat["viento"]["cambios"]), "dir": E(dirs),
                "fuerza": A(E(fuerzas)), "rafagas": rafagas, "raf_int": E([""] + fuerzas),
                "hora": S(description="DD/HHMM o vacío")})
    viento = O({"dir": E(dirs), "fuerza": A(E(fuerzas)), "rafagas": rafagas, "raf_int": E([""] + fuerzas),
                "cambios": A(cambio)})
    item = O({"conector": E(fen["conector"]), "prob": E(fen["probabilidad"]), "fen": A(E(fen["lista"])),
              "cal": E(fen["calificativo"]), "momento": E(fen["momento"]), "evol": E(fen["evolucion"]),
              "momento_evol": E(fen["momento"]), "hora_evol": S(description="DD/HHMM de la evolución o vacío"),
              "hora_evol_tipo": E(["el", "desde"])})
    vis_vals = [""] + list(cat["visibilidad"]["valores"])
    division = O({"tipo": E(["entera", "condiciones", "coordenadas", "cuadrante", "resto"]),
                  "conds": A(O({"rel": E(["N", "S", "E", "W"]), "valor": S(description="ej. 45S o 40W")})),
                  "lat1": S(), "lat2": S(), "lon1": S(), "lon2": S(),
                  "cuadrante": E([""] + cat["subdivision"]["cuadrantes"])})
    subzona = O({"division": division, "viento": viento,
                 "fenomenos": O({"sin_fenomenos": {"type": "boolean"}, "items": A(item)}),
                 "vis": O({"v1": E(vis_vals), "hasta": E(vis_vals), "ocnl": E(vis_vals),
                           "ocnl_antes": {"type": "boolean"}}),
                 "obs": S(description="Lo que no entra en los campos, en castellano. Vacío si no hay."),
                 "obs_en": S(description="Traducción al inglés de obs, estilo boletín marino.")})
    zona = O({"zona": E(zonas), "copiar_de": E([""] + zonas), "subzonas": A(subzona)})
    aviso = O({"numero": S(), "estado": E(cat["avisos"]["estados"]), "causa": E(cat["avisos"]["causas"]),
               "detalle": S(description="Presión y/o posición de la causa, ej. '997HPA 52S 43W'; texto si causa=OTRA"),
               "detalle_en": S(description="Traducción si causa=OTRA; si no, vacío"),
               "verbo": E(cat["avisos"]["verbo"]), "fuerza": E(["TEMPORAL", "TEMPORAL_FUERTE", "TEMPORAL_MUY_FUERTE", "8", "9", "10", "11", "12"]),
               "dir": E(dirs), "rafagas": {"type": "boolean"}, "zonas": A(E(zonas)),
               "coords": S(description="ej. 45S-50S 30W-40W, o vacío"),
               "desde": S(description="DD/HHMM o vacío"), "hasta": S(description="DD/HHMM o vacío"),
               "navtex": {"type": "boolean"}})
    sistema = O({"tipo": E(cat["sinopsis"]["tipos"]), "presion": S(), "pos": S(description="ej. 47S 55W"),
                 "mov": E(cat["sinopsis"]["movimientos"]), "evol": A(E(cat["sinopsis"]["evoluciones"])),
                 "exp_pos": S(), "exp_hora": S(), "ext_tipo": E([""] + list(cat["sinopsis"]["frentes_extiende"])),
                 "ext_pos": S(), "ext_mov": E(cat["sinopsis"]["movimientos"]), "ext_exp_pos": S(), "ext_exp_hora": S(),
                 "navtex": {"type": "boolean"}})
    duda = O({"donde": S(description="Sección o zona"), "texto": S(description="Fragmento original"),
              "motivo": S(description="Qué hay que revisar y qué se asumió")})
    return O({"avisos": A(aviso), "sinopsis": A(sistema), "zonas": A(zona), "dudas": A(duda)})


def _instrucciones(cat: dict) -> str:
    zonas = "\n".join(f"- {z['id']}: {z['es']} (también: {', '.join(z.get('alias', []))})"
                      for z in todas_las_zonas(cat))
    fen = cat["fenomenos"]
    lista = lambda d: ", ".join(f"{k}={v['es']}" for k, v in d.items() if k)
    escala = ", ".join(f"{k}" for k in cat["viento"]["escala"]["valores"])
    return f"""Sos el asistente del Servicio Meteorológico Nacional (Argentina) que pasa a datos el borrador
del Boletín Meteorológico para Navegantes METAREA VI. El pronosticador escribe en castellano, en texto
claro y con su estilo. Tu tarea es SOLO interpretar y cargar los datos con la herramienta
cargar_boletin, usando exclusivamente los valores permitidos. No redactes el boletín.

ZONAS (usá el id):
{zonas}
"Costa sudeste" (sección costera) es Uruguay; "Área sudeste" (oceánica) es sudeste.

CONVENCIONES
- Coordenadas: siempre latitud Sur y longitud Oeste. "38-44" = "38S 44W". Varias posiciones van
  separadas por espacio: "47S 55W 40S 54W".
- Horas: "el 25 a las 9" = "25/0900"; "el 2 a las 0" = "02/0000". Copiá el día tal como está escrito,
  aunque parezca un error (lo controla el sistema), y anotalo como duda si te parece un error.
- Corregí sin comentar los errores de tipeo obvios (provica, bnuena, radafas).

VIENTO
- Fuerza: términos {escala}. "Fuertes a regulares" = ["FUERTES","REGULARES"] (respetá el orden).
  "Muy fuertes" = MUY_FUERTES. "Temporal fuerte" = TEMPORAL_FUERTE. "Temporal muy fuerte" = TEMPORAL_MUY_FUERTE. Si el texto da números, usá números.
- Dirección: "del sector norte/sur/este/oeste (u O)" = "SECTOR N/S/E/W". "Del NW", "del SW" = "NW", "SW".
  "Direcciones variables" = "VRB".
- Cambios, en orden: "cambiando en sentido horario" / "horario" = VEER; "antihorario" / "anti" = BACK;
  "aumentando" = INCR; "disminuyendo" = DECR. "Temporariamente" = tempo true. Si el cambio no dice el
  sentido, elegí el más probable según las direcciones y anotá una duda. Un cambio puede no tener
  dirección (solo fuerza) o no tener fuerza.
- Ráfagas: "con ráfagas" = CON. "Ráfagas de temporal" = INT con raf_int TEMPORAL; "ráfagas fuertes" =
  INT con raf_int FUERTES.
- "Prevaleciendo del sector X" y otras precisiones sin campo: van a obs.

FENÓMENOS (cada fenómeno o grupo es un item, en el orden del texto)
- Probabilidad: "probables" / "probabilidad de" = PROB; "baja probabilidad" = BAJA; "desmejorando con
  probabilidad de" = DESMEJORANDO; sin palabra de probabilidad o "(sin proba)" = "".
- Fenómenos: {lista(fen['lista'])}. "Chaparrones" = SH. "Chaparrones de nieve" = SH_NIEVE.
  "Chaparrones de granizo" = SH_GRANIZO. "Lluvias y chaparrones" = ["LLUVIAS","SH"].
- Calificativo: {lista(fen['calificativo'])}.
- Momento: {lista(fen['momento'])}.
- Evolución: {lista(fen['evolucion'])}. "Mejorando" suelto al final = MEJORANDO.
- "Luego" = conector LUEGO en el item siguiente.
- Si la zona no menciona ningún fenómeno, sin_fenomenos = true (así lo escriben cuando no hay).

VISIBILIDAD (si la zona no la menciona, dejá v1 vacío y anotá una duda): "regular oca buena" = v1 REGULAR, ocnl BUENA. "Regular a mala" = v1 REGULAR, hasta MALA.
Valores: BUENA, REGULAR, MALA, MUY_MALA.

SUBDIVISIONES
- "Entera" o sin subdivisión: una sola subzona con division.tipo "entera".
- "Este de 35" = condiciones [E, "35W"]; "al sur de los 45" = [S, "45S"]; "resto del área" = resto.
- Si la subdivisión es ambigua (ej. "s45, 30W"), cargá la interpretación más probable y anotá una duda.

COPIAS: los pronosticadores marcan con "(copiar)", "(lo podés copiar)" o "(pegar)" un pronóstico que
se repite en otras zonas, y en esas zonas escriben "usar copia", "usar la copia", "pegar", etc.
Para esas zonas: copiar_de = id de la zona fuente (la marcada más recientemente antes, salvo que el texto
nombre otra zona) y subzonas = []. Anotá siempre una duda "copiado de …" para que lo verifiquen.

AVISOS: estado nuevo / actualiza ("actualizar") / cese ("cese") / fuera_area ("afuera", "fuera").
FGB = fuerte gradiente bárico (GRADIENTE). "Temporal" = TEMPORAL; "temporal fuerte" = TEMPORAL_FUERTE.
"Provoca" = presente; "provocará" = futuro. Depresión como causa: detalle "997HPA 52S 43W".
Zonas por nombre en zonas; áreas por coordenadas en coords ("45S-50S 30W-40W"); si las coordenadas
son ambiguas, anotá una duda. "A partir del…" = desde; "hasta el…" = hasta. Mantené el orden del texto.

SITUACIÓN / SINOPSIS: "anti" = ANTICICLON; "depre" = DEPRESION. "Se intensifica" = INTSF, "se debilita" =
WKN, "se profundiza" = DPN, "se rellena" = FLN. "Se mueve al NE" = "MOV NE"; "sin movimiento" = STNR.
"Pos final X el D a las H" = exp_pos X, exp_hora DD/HHMM. Un frente que extiende la depresión va en
ext_* (con su propia posición final en ext_exp_*). Ciclogénesis prevista: tipo CICLOGENESIS, pos vacía
y la posición en exp_pos.

NAVTEX: lo que el borrador marca con «NAVTEX» (al principio o entre paréntesis, o repetido en una
sección NAVTEX al final) lleva navtex = true; el resto, false.

IGNORÁ: los recordatorios y comentarios personales, y los hielos (se cargan aparte).
Las zonas que no figuran en el texto no se cargan.

NUNCA INVENTES. Lo que no encaje en los valores permitidos va textual en obs (con su traducción en obs_en)
y con una duda. Mejor una duda de más que un dato inventado."""


# ====================================================================== motor
def motor() -> str:
    """«reglas» (por defecto, sin IA) o «ia» (requiere ANTHROPIC_API_KEY)."""
    m = os.getenv("INTERPRETE", "reglas").lower()
    return "ia" if m == "ia" and os.getenv("ANTHROPIC_API_KEY") else "reglas"


def interpretar_texto(cat: dict, texto: str) -> dict:
    if motor() == "ia":
        return llamar_ia(cat, texto)
    from . import reglas
    return reglas.interpretar(cat, texto)


# ====================================================================== IA
def llamar_ia(cat: dict, texto: str) -> dict:
    from anthropic import Anthropic

    herramienta = {"name": "cargar_boletin",
                   "description": "Carga los datos interpretados del borrador del boletín.",
                   "input_schema": _esquema(cat)}
    resp = Anthropic().messages.create(
        model=os.getenv("CLAUDE_MODEL", MODELO_DEFECTO),
        max_tokens=16000,
        temperature=0,
        system=_instrucciones(cat),
        tools=[herramienta],
        tool_choice={"type": "tool", "name": "cargar_boletin"},
        messages=[{"role": "user", "content": f"Borrador del pronosticador:\n\n{texto}"}],
    )
    for bloque in resp.content:
        if getattr(bloque, "type", "") == "tool_use":
            return bloque.input
    raise RuntimeError("La IA no devolvió datos.")


# ====================================================================== post-proceso
def _fuerza(cat, valores) -> str:
    escala = cat["viento"]["escala"]["valores"]
    nums = [str(escala.get(v, v)) for v in valores or [] if v != ""]
    out = []
    for n in nums:
        if not out or out[-1] != n:
            out.append(n)
    return "/".join(out)


def _subzona(cat, d) -> dict:
    sz = modelo.nueva_subzona()
    div = d.get("division") or {}
    tipo = div.get("tipo", "entera")
    sz["division"] = {
        "tipo": "condiciones" if tipo == "entera" else tipo,
        "conds": [{"id": modelo.nid(), "rel": c["rel"], "valor": c.get("valor", "")} for c in div.get("conds", [])]
        or [{"id": modelo.nid(), "rel": "N", "valor": ""}],
        **{k: div.get(k, "") for k in ("lat1", "lat2", "lon1", "lon2")},
        "cuadrante": div.get("cuadrante") or "NE",
    }
    v = d.get("viento") or {}
    sz["viento"] = {
        "dir": v.get("dir", ""), "fuerza": _fuerza(cat, v.get("fuerza")), "rafagas": v.get("rafagas", ""),
        "raf_int": _fuerza(cat, [v.get("raf_int", "")]),
        "cambios": [{**modelo.nuevo_cambio(), "tempo": bool(c.get("tempo")), "tipo": c.get("tipo", "BACK"),
                     "dir": c.get("dir", ""), "fuerza": _fuerza(cat, c.get("fuerza")),
                     "rafagas": c.get("rafagas", ""), "raf_int": _fuerza(cat, [c.get("raf_int", "")]),
                     "hora": c.get("hora", "")} for c in v.get("cambios", [])],
    }
    f = d.get("fenomenos") or {}
    items = [{**modelo.nuevo_item_fenomeno(),
              **{k: it.get(k, "") for k in ("conector", "prob", "cal", "momento", "evol", "momento_evol", "hora_evol")},
              "hora_evol_tipo": it.get("hora_evol_tipo") or "el",
              "fen": list(it.get("fen", []))} for it in f.get("items", [])]
    sz["fenomenos"] = {"sin_fenomenos": bool(f.get("sin_fenomenos")), "items": items}
    vis = d.get("vis") or {}
    sz["vis"] = {**{k: vis.get(k, "") for k in ("v1", "hasta", "ocnl")}, "ocnl_antes": bool(vis.get("ocnl_antes"))}
    sz["obs"] = d.get("obs", "")
    return sz


def a_boletin(cat: dict, datos: dict, base: dict) -> tuple[dict, list[dict]]:
    """Arma el boletín a partir del JSON de la IA.

    base aporta fecha, corrida, hielos y texto claro (lo que no viene de la IA).
    Devuelve (boletín, dudas).
    """
    b = modelo.nuevo_boletin(cat)
    for k in ("fecha", "corrida", "hielos", "olas", "olas_excluir", "olas_incluir", "texto_claro"):
        if k in base:
            b[k] = base[k]
    dudas = list(datos.get("dudas", []))
    nombres = {z["id"]: z["es"] for z in todas_las_zonas(cat)}

    # ---- avisos
    for a in datos.get("avisos", []):
        n = modelo.nuevo_aviso()
        n.update({k: a.get(k, n[k]) for k in ("numero", "estado", "causa", "detalle", "verbo", "dir", "coords", "desde", "hasta",
                                              "navtex")})
        n["fuerza"] = _fuerza(cat, [a.get("fuerza", "TEMPORAL")]) or "8"
        n["rafagas"] = bool(a.get("rafagas"))
        n["zonas"] = [z for z in a.get("zonas", []) if z in nombres]
        if n["causa"] == "OTRA" and a.get("detalle_en"):
            from .render import normalizar
            b["traducciones"][normalizar(n["detalle"])] = normalizar(a["detalle_en"])
        b["avisos"].append(n)

    # ---- sinopsis
    for s in datos.get("sinopsis", []):
        n = modelo.nuevo_sistema()
        n.update({k: s.get(k, n[k]) for k in n if k != "id"})
        b["sinopsis"].append(n)

    # ---- zonas
    crudo = {z["zona"]: z for z in datos.get("zonas", []) if z.get("zona") in nombres}
    for zid in b["zonas"]:
        b["zonas"][zid] = {"incluir": False, "subzonas": [modelo.nueva_subzona()]}

    def resolver(zid, visitadas=()):
        z = crudo[zid]
        if z.get("copiar_de") and not z.get("subzonas"):
            fuente = z["copiar_de"]
            if fuente in visitadas or fuente not in crudo:
                dudas.append({"donde": nombres[zid], "texto": "",
                              "motivo": f"Debía copiarse de {nombres.get(fuente, fuente)}, que no tiene pronóstico."})
                return None
            return resolver(fuente, visitadas + (zid,))
        return z.get("subzonas", [])

    from .render import normalizar
    for zid in crudo:
        subs = resolver(zid)
        if not subs:
            continue
        subzonas = [_subzona(cat, s) for s in copy.deepcopy(subs)]
        if len(subzonas) == 1:
            subzonas[0]["division"]["tipo"] = "condiciones"
        b["zonas"][zid] = {"incluir": True, "subzonas": subzonas}
        for s in subs:
            if s.get("obs", "").strip() and s.get("obs_en", "").strip():
                b["traducciones"][normalizar(s["obs"])] = normalizar(s["obs_en"])
    return b, dudas
