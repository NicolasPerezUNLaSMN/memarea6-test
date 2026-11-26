"""Generación determinística de los textos del boletín en español e inglés.

Todo sale del catálogo. La IA solo interviene en los textos libres, cuyas
traducciones llegan ya resueltas en b["traducciones"].
"""
import datetime as dt
import re
import unicodedata

from .catalogo import todas_las_zonas

MESES_EN = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY",
            "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"]
LANGS = ("es", "en")


# ------------------------------------------------------------------ util
def normalizar(s: str) -> str:
    """Mayúsculas, sin tildes (se conservan Ñ y º), espacios simples."""
    if not s:
        return ""
    s = s.upper().replace("Ñ", "\x00")
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = s.replace("\x00", "Ñ")
    return re.sub(r"\s+", " ", s).strip()


def unir(*partes) -> str:
    return " ".join(p.strip() for p in partes if p and p.strip())


def traduccion(b: dict, texto: str) -> str:
    t = normalizar(texto)
    en = b.get("traducciones", {}).get(t)
    return normalizar(en) if en else f"[TRADUCIR: {t}]"


# ------------------------------------------------------------------ fechas
def tiempos(b: dict) -> dict:
    fecha = dt.date.fromisoformat(b["fecha"])
    if b["corrida"] == "12":
        emision = dt.datetime(fecha.year, fecha.month, fecha.day, 12, 0)
        sinop, ini = "09:00", "12:00"
    else:
        emision = dt.datetime(fecha.year, fecha.month, fecha.day) - dt.timedelta(minutes=1)
        sinop, ini = "21:00", "00:00"
    fin = fecha + dt.timedelta(days=1)
    return {
        "emision": emision, "sinop": sinop, "ini": ini, "fin_hora": ini, "fin": fin,
        "inicio": dt.datetime(fecha.year, fecha.month, fecha.day, int(ini[:2])),
        "id": emision.strftime("%d%H%M"),
    }


def nombre_archivos(b: dict) -> dict:
    t = tiempos(b)
    return {"es": f"WWST01_SABM_{t['id']}.txt", "en": f"WWST02_SABM_{t['id']}.txt",
            "comb": f"WWST_SABM_{t['id']}_ES_EN.txt", "navtex": f"WWST03_SABM_{t['id']}.txt"}


# ------------------------------------------------------------------ viento
def _rafagas(cat, tipo, n, lang):
    r = cat["viento"]["rafagas"]
    if tipo == "CON":
        return r["con"][lang]
    if tipo == "INT":
        return r["intensidad"][lang].format(n=n.strip())
    return ""


def viento(cat, v, lang):
    partes = [v["dir"], v["fuerza"], _rafagas(cat, v["rafagas"], v.get("raf_int", ""), lang)]
    for c in v.get("cambios", []):
        hora = cat["viento"]["hora"][lang].format(h=c["hora"].strip()) if c.get("hora", "").strip() else ""
        partes += [cat["viento"]["tempo"] if c.get("tempo") else "", c["tipo"], c.get("dir", ""),
                   c.get("fuerza", ""), _rafagas(cat, c.get("rafagas", ""), c.get("raf_int", ""), lang), hora]
    return unir(*partes)


def fuerzas_sostenidas(v) -> list[int]:
    """Valores de fuerza del viento (sin contar intensidad de ráfagas)."""
    vals = []
    for f in [v.get("fuerza", "")] + [c.get("fuerza", "") for c in v.get("cambios", [])]:
        vals += [int(x) for x in re.findall(r"\d+", f or "")]
    return vals


# ------------------------------------------------------------------ fenómenos
def _item(cat, it, lang):
    fc = cat["fenomenos"]
    nombres = [fc["lista"][f][lang] for f in it.get("fen", []) if f in fc["lista"]]
    union = fc.get("union", {}).get(lang, " ")
    if union.strip() and len(nombres) > 1:      # inglés: «RAIN AND TSTM», «RAIN, SH AND TSTM»
        fen = ", ".join(nombres[:-1]) + union + nombres[-1]
    else:
        fen = unir(*nombres)
    prob = fc["probabilidad"].get(it.get("prob", ""), {}).get(lang, "")
    cal = fc["calificativo"].get(it.get("cal", ""), {}).get(lang, "")
    mom_d = fc["momento"].get(it.get("momento", ""), {})
    mom = mom_d.get(lang, "")
    evo = fc["evolucion"].get(it.get("evol", ""), {}).get(lang, "")
    nucleo = unir(prob, fen, cal) if lang == "es" else unir(prob, cal, fen)
    cola = unir(evo, mom) if mom_d.get("despues") else unir(mom, evo)
    mom_evo = fc["momento"].get(it.get("momento_evol", ""), {}).get(lang, "")
    hora_evo = ""
    if it.get("hora_evol", "").strip() and it.get("evol"):
        tipo = it.get("hora_evol_tipo") or "el"
        hora_evo = fc["hora_evolucion"][tipo][lang].format(h=it["hora_evol"].strip())
    return unir(nucleo, cola, mom_evo, hora_evo)


def fenomenos(cat, f, lang):
    if f.get("sin_fenomenos"):
        return cat["fenomenos"]["sin_fenomenos"][lang]
    partes = []
    for i, it in enumerate(f.get("items", [])):
        if i > 0:
            partes.append(cat["fenomenos"]["conector"].get(it.get("conector", ""), {}).get(lang, ""))
        partes.append(_item(cat, it, lang))
    return unir(*partes)


# ------------------------------------------------------------------ visibilidad
def visibilidad(cat, v, lang):
    vc = cat["visibilidad"]
    if not v.get("v1"):
        return ""
    txt = unir(vc["prefijo"], vc["valores"][v["v1"]][lang])
    hasta = unir(vc["hasta"][lang], vc["valores"][v["hasta"]][lang]) if v.get("hasta") else ""
    ocnl = unir(vc["ocnl"][lang], vc["valores"][v["ocnl"]][lang]) if v.get("ocnl") else ""
    return unir(txt, ocnl, hasta) if v.get("ocnl_antes") else unir(txt, hasta, ocnl)


# ------------------------------------------------------------------ zonas
def etiqueta_division(cat, d, lang):
    sc = cat["subdivision"]
    if d["tipo"] == "resto":
        return sc["resto"][lang]
    if d["tipo"] == "cuadrante":
        return sc["cuadrante"][lang].format(c=d.get("cuadrante", ""))
    if d["tipo"] == "coordenadas":
        return sc["coordenadas"][lang].format(**{k: normalizar(d.get(k, "")) for k in ("lat1", "lat2", "lon1", "lon2")})
    return sc["union"].join(f"{sc['relaciones'][c['rel']][lang]} {normalizar(c['valor'])}"
                            for c in d.get("conds", []))


def linea_subzona(cat, b, zona, sz, dividida, lang):
    etiqueta = zona[lang]
    if dividida:
        etiqueta = f"{etiqueta} {etiqueta_division(cat, sz['division'], lang)}"
    obs = ""
    if sz.get("obs", "").strip():
        obs = normalizar(sz["obs"]) if lang == "es" else traduccion(b, sz["obs"])
    cuerpo = unir(viento(cat, sz["viento"], lang), fenomenos(cat, sz["fenomenos"], lang), obs,
                  visibilidad(cat, sz["vis"], lang))
    return f"{etiqueta}: {cuerpo}"


def lineas_grupo(cat, b, grupo, lang):
    out = []
    for z in cat["zonas"][grupo]:
        zd = b["zonas"].get(z["id"])
        if not zd or not zd.get("incluir"):
            continue
        dividida = len(zd["subzonas"]) > 1
        out += [linea_subzona(cat, b, z, sz, dividida, lang) for sz in zd["subzonas"]]
    return out


# ------------------------------------------------------------------ avisos
def linea_aviso(cat, b, a, lang):
    ac = cat["avisos"]
    estado = ac["estados"][a.get("estado") or "nuevo"]
    if a.get("estado") in ("cese", "fuera_area"):
        return estado["linea"][lang].format(n=a["numero"].strip(), texto="")
    causa = ac["causas"][a["causa"]]
    if a["causa"] == "OTRA":
        detalle = normalizar(a["detalle"]) if lang == "es" else traduccion(b, a["detalle"])
    else:
        detalle = normalizar(a.get("detalle", ""))
    partes = [causa[lang].format(d=detalle), ac["verbo"][a["verbo"]][lang],
              ac["viento"][lang].format(f=a["fuerza"], dir=a["dir"]),
              ac["rafagas"][lang] if a.get("rafagas") else ""]
    zonas = {z["id"]: z for z in todas_las_zonas(cat)}
    nombres = []
    for zid in a.get("zonas", []):
        z = zonas[zid]
        nombres.append(z.get(f"aviso_{lang}", z[lang]))
    donde = []
    if nombres:
        donde.append(ac["en_zonas"][lang].format(z=" ".join(nombres)))
    if a.get("coords", "").strip():
        donde.append(ac["entre"][lang].format(c=normalizar(a["coords"])))
    partes.append(ac["union_zonas_coords"][lang].join(donde))
    if a.get("desde", "").strip():
        partes.append(ac["desde"][lang].format(h=a["desde"].strip()))
    if a.get("hasta", "").strip():
        partes.append(ac["hasta"][lang].format(h=a["hasta"].strip()))
    return estado["linea"][lang].format(n=a["numero"].strip(), texto=unir(*partes))


# ------------------------------------------------------------------ sinopsis
def linea_sistema(cat, s, lang):
    sc = cat["sinopsis"]
    t = sc["tipos"][s["tipo"]]
    pos = normalizar(s.get("pos", ""))
    if pos and t.get("prefijo_pos"):
        pos = f"{t['prefijo_pos'][lang]} {pos}"
    partes = [t[lang].format(p=s.get("presion", "").strip(), pos=pos), s.get("mov", ""), *s.get("evol", [])]
    if s.get("exp_pos", "").strip() or s.get("exp_hora", "").strip():
        partes.append(sc["esperado"][lang].format(pos=normalizar(s.get("exp_pos", "")), h=s.get("exp_hora", "").strip()))
    if s.get("ext_tipo"):
        frente = sc["frentes_extiende"].get(s["ext_tipo"], {}).get(lang, s["ext_tipo"])
        partes += [sc["extiende"][lang].format(f=frente, pos=normalizar(s.get("ext_pos", ""))),
                   s.get("ext_mov", "")]
        if s.get("ext_exp_pos", "").strip() or s.get("ext_exp_hora", "").strip():
            partes.append(sc["esperado"][lang].format(pos=normalizar(s.get("ext_exp_pos", "")),
                                                      h=s.get("ext_exp_hora", "").strip()))
    return re.sub(r" {2,}", " ", unir(*partes))


def bloques_hielo(cat, texto) -> dict:
    """Separa un informe de hielos en sus bloques por idioma.

    Devuelve {"es": ..., "en": ...} con lo que haya; cada bloque ya en una
    sola línea, sin título ni pedido final.
    """
    hc = cat["hielos"]
    t = normalizar(texto)
    marcas = sorted((t.find(normalizar(titulo)), lang, normalizar(titulo))
                    for lang, titulo in hc.get("titulos", {}).items() if normalizar(titulo) in t)
    if not marcas:
        return {"es": _limpiar_hielo(hc, t)}
    out = {}
    for i, (pos, lang, titulo) in enumerate(marcas):
        fin = marcas[i + 1][0] if i + 1 < len(marcas) else len(t)
        out[lang] = _limpiar_hielo(hc, t[pos + len(titulo):fin])
    return out


def _limpiar_hielo(hc, t):
    for frase in hc.get("quitar_desde", []):
        i = t.find(normalizar(frase))
        if i >= 0:
            t = t[:i]
    return unir(t)


def lineas_olas(cat, b, lang) -> list[str]:
    """Avisos de olas numerados (ver registro.numerar) y sus ceses."""
    from . import olas
    if not (b.get("olas") or "").strip():
        return []
    oc = cat["olas"]
    zonas = {z["id"]: z for z in todas_las_zonas(cat)}
    numeros, estados = b.get("olas_numeros", {}), b.get("olas_estados", {})
    out = []
    for a in olas.seleccionados(b, cat):
        n = numeros.get(a["clave"], "")
        texto = olas.linea(cat, zonas, a, lang, n=n, estado=estados.get(str(n), "nuevo"))
        out.append(texto or (a["original"] if lang == "en" else f"[TRADUCIR: {a['original']}]"))
    out += [oc["linea_cese"][lang].format(n=n) for n in b.get("olas_ceses", [])]
    if not out:
        txt = oc["sin_avisos"][lang]
        return [txt] if txt else []
    return ([oc["titulo"][lang]] if oc["titulo"][lang] else []) + out


def hielos(cat, texto, lang):
    bloques = bloques_hielo(cat, texto)
    if lang in bloques:
        return bloques[lang]
    t = bloques.get("es", "")
    for patron, reemplazo in cat["hielos"]["reemplazos"]:
        t = re.sub(patron, reemplazo, t)
    return t


# ------------------------------------------------------------------ boletín
def generar(cat: dict, b: dict, lang: str) -> str:
    e = cat["encabezado"][lang]
    t = tiempos(b)
    em = t["emision"]
    if lang == "es":
        linea_fecha = f"{em:%d-%m-%Y}, {em:%H:%M} UTC."
        fecha_fin = f"{t['fin']:%d-%m-%Y}"
    else:
        linea_fecha = f"{em:%H:%M} UTC {em:%d}, {MESES_EN[em.month - 1]} {em.year}"
        fecha_fin = f"{t['fin']:%Y-%m-%d}"

    enc = cat["encabezado"]
    blanco = lambda clave: [""] * enc.get("renglones_en_blanco", {}).get(clave, 0)
    control = enc.get("caracteres_control", False)
    L = (["\x01"] if control else []) + [f"{e['id']} {t['id']}", *e["lineas_fijas_1"], linea_fecha, *e["lineas_fijas_2"]]

    if b["avisos"]:
        L.append(e["parte1_con_avisos"])
        L += [linea_aviso(cat, b, a, lang) for a in b["avisos"]]
    else:
        L += e["parte1_sin_avisos"]
    L += lineas_olas(cat, b, lang)

    L += blanco("antes_parte2")
    L.append(e["parte2"].format(hora=t["sinop"]))
    if b.get("hielos", "").strip():
        L.append(hielos(cat, b["hielos"], lang))
    L += [linea_sistema(cat, s, lang) for s in b["sinopsis"]]

    L += blanco("antes_parte3")
    L.append(e["parte3"].format(ini=t["ini"], fin=t["fin_hora"], fecha_fin=fecha_fin))
    costeras = lineas_grupo(cat, b, "costeras", lang)
    oceanicas = lineas_grupo(cat, b, "oceanicas", lang)
    if costeras:
        L += [e["costas"], *costeras]
    if oceanicas:
        L += (blanco("antes_oceanicas") if costeras else []) + [e["oceanicas"], *oceanicas]

    L += blanco("antes_pie")
    L += enc["pie"]
    if control:
        L[-1] += "\x03"
    return "\n".join(L) + "\n"


def generar_todo(cat: dict, b: dict) -> dict:
    es, en = generar(cat, b, "es"), generar(cat, b, "en")
    sep = cat["encabezado"]["separador_combinado"]
    return {"es": es, "en": en, "comb": f"{es}{sep}\n\n{en}", "navtex": generar_navtex(cat, b)}


def textos_libres(b: dict) -> list[str]:
    """Textos que necesitan traducción con IA (normalizados, sin duplicados)."""
    out = []
    for zd in b["zonas"].values():
        if zd.get("incluir"):
            out += [sz["obs"] for sz in zd["subzonas"] if sz.get("obs", "").strip()]
    out += [a["detalle"] for a in b["avisos"] if a["causa"] == "OTRA" and a.get("detalle", "").strip()]
    vistos, res = set(), []
    for t in map(normalizar, out):
        if t not in vistos:
            vistos.add(t)
            res.append(t)
    return res


# ------------------------------------------------------------------ NAVTEX
def generar_navtex(cat: dict, b: dict) -> str:
    """Boletín para estaciones NAVTEX (WWST03), en inglés."""
    import textwrap

    nc = cat["navtex"]
    t = tiempos(b)
    em = t["emision"]
    extra = nc.get("renglones_extra", {})
    L = [f"{nc['id']} {t['id']}", nc["titulo"],
         nc["fecha"].format(mes=MESES_EN[em.month - 1], dia=em.day, hora=f"{em:%H:%M}"), *nc["lineas_fijas"]]
    L += [""] * extra.get("despues_encabezado", 0)

    L.append(nc["avisos_titulo"])
    avisos = [a for a in b["avisos"] if a.get("navtex")]
    L += [linea_aviso(cat, b, a, "en") for a in avisos] or [nc["sin_avisos"]]
    L += [""] * extra.get("despues_avisos", 0)

    L.append(nc["sinopsis_titulo"])
    L += [linea_sistema(cat, s, "en") for s in b["sinopsis"] if s.get("navtex")]
    L.append(nc["pronostico"].format(ini=t["ini"], fin=t["fin_hora"], fecha_fin=f"{t['fin']:%Y-%m-%d}"))

    L.append(nc["estaciones_titulo"])
    zonas = {z["id"]: z for z in todas_las_zonas(cat)}
    for est in nc["estaciones"]:
        textos = []
        for zid in est["zonas"]:
            zd = b["zonas"].get(zid)
            if not zd or not zd.get("incluir"):
                continue
            dividida = len(zd["subzonas"]) > 1
            for sz in zd["subzonas"]:
                linea = linea_subzona(cat, b, zonas[zid], sz, dividida, "en").split(": ", 1)[1]
                if dividida:
                    linea = f"{etiqueta_division(cat, sz['division'], 'en')}: {linea}"
                linea = linea.rstrip(".") + "."
                if nc.get("repetir_iguales") or linea not in textos:
                    textos.append(linea)
        if textos:
            L.append(f"{est['nombre']}:{nc['separador_zonas']}" + nc["separador_zonas"].join(textos))
    L += [""] * extra.get("antes_pie", 0)
    L += cat["encabezado"]["pie"]

    ancho = nc.get("ancho", 80)
    lineas = []
    for parrafo in L:
        if not parrafo:
            lineas.append("")
            continue
        lineas += textwrap.wrap(parrafo, width=ancho, break_long_words=False, break_on_hyphens=False) or [""]
    sep = "\n\n" if nc.get("interlineado_doble", True) else "\n"
    return sep.join(lineas) + "\n"
