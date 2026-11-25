"""Controles antes de generar. Devuelve (errores, advertencias).

Errores: impiden generar. Advertencias: se muestran pero dejan seguir.
"""
import datetime as dt
import re

from . import render
from .catalogo import todas_las_zonas

LAT = r"\d{1,2}(º\d{2})?S"
LON = r"\d{1,3}(º\d{2})?W"
RE_LAT = re.compile(rf"^{LAT}$")
RE_LON = re.compile(rf"^{LON}$")
RE_POS = re.compile(rf"^{LAT} {LON}( {LAT} {LON})*$")
RE_FUERZA = re.compile(r"^\d{1,2}(/\d{1,2})?$")
RE_HORA = re.compile(r"^(\d{2})/(\d{2})(\d{2})$")


def _hora(txt, b, donde, err, adv):
    m = RE_HORA.match(txt.strip())
    if not m:
        err.append(f"{donde}: la hora «{txt}» debe tener el formato DD/HHMM (ej. 24/1800).")
        return
    d, h, mi = map(int, m.groups())
    if not (1 <= d <= 31 and h <= 23 and mi <= 59):
        err.append(f"{donde}: la hora «{txt}» no es válida.")
        return
    t = render.tiempos(b)
    dias_validos = {t["inicio"].day, t["fin"].day}
    if d not in dias_validos:
        adv.append(f"{donde}: el día {d:02d} de «{txt}» está fuera del período de validez.")


def _fuerza(txt, donde, err, obligatoria=True):
    txt = (txt or "").strip()
    if not txt:
        if obligatoria:
            err.append(f"{donde}: falta la fuerza del viento.")
        return
    if not RE_FUERZA.match(txt) or any(int(x) > 12 for x in txt.split("/")):
        err.append(f"{donde}: la fuerza «{txt}» debe ser un número Beaufort (0–12), o un rango como 5/6.")


def _pos(txt, donde, err, obligatoria=True):
    t = render.normalizar(txt)
    if not t:
        if obligatoria:
            err.append(f"{donde}: falta la posición.")
        return
    if not RE_POS.match(t):
        err.append(f"{donde}: la posición «{t}» debe ser pares latitud longitud, ej. «47S 55W 40S 54W».")


def _viento(v, donde, b, err, adv):
    if not v.get("dir"):
        err.append(f"{donde}: falta la dirección del viento.")
    _fuerza(v.get("fuerza"), donde, err)
    if v.get("rafagas") == "INT":
        _fuerza(v.get("raf_int"), f"{donde} (intensidad de ráfagas)", err)
    for i, c in enumerate(v.get("cambios", []), 1):
        dc = f"{donde} › cambio {i}"
        _fuerza(c.get("fuerza"), dc, err, obligatoria=False)
        if c.get("rafagas") == "INT":
            _fuerza(c.get("raf_int"), f"{dc} (intensidad de ráfagas)", err)
        if c.get("hora", "").strip():
            _hora(c["hora"], b, dc, err, adv)
        if c["tipo"] in ("BACK", "VEER") and not c.get("dir"):
            adv.append(f"{dc}: {c['tipo']} sin dirección final.")


def _fenomenos(f, donde, err):
    if f.get("sin_fenomenos"):
        return
    items = f.get("items", [])
    if not items:
        err.append(f"{donde}: cargá al menos un fenómeno o marcá «sin fenómenos significativos».")
    for i, it in enumerate(items, 1):
        if not it.get("fen"):
            err.append(f"{donde} › fenómeno {i}: elegí al menos un fenómeno.")


def _division(d, donde, err):
    if d["tipo"] == "condiciones":
        if not d.get("conds"):
            err.append(f"{donde}: indicá la división (al norte de, al sur de…).")
        for c in d.get("conds", []):
            val = render.normalizar(c.get("valor", ""))
            if c["rel"] in ("N", "S") and not RE_LAT.match(val):
                err.append(f"{donde}: «{val or '(vacío)'}» debe ser una latitud, ej. 45S.")
            if c["rel"] in ("E", "W") and not RE_LON.match(val):
                err.append(f"{donde}: «{val or '(vacío)'}» debe ser una longitud, ej. 40W.")
    elif d["tipo"] == "cuadrante":
        if not d.get("cuadrante"):
            err.append(f"{donde}: elegí el cuadrante.")
    elif d["tipo"] == "coordenadas":
        for k, rx, ej in (("lat1", RE_LAT, "40S"), ("lat2", RE_LAT, "45S"), ("lon1", RE_LON, "30W"), ("lon2", RE_LON, "40W")):
            val = render.normalizar(d.get(k, ""))
            if not rx.match(val):
                err.append(f"{donde}: coordenada «{val or '(vacía)'}» inválida (ej. {ej}).")


def validar(cat: dict, b: dict) -> tuple[list[str], list[str]]:
    err, adv = [], []
    zonas = {z["id"]: z for z in todas_las_zonas(cat)}
    nombre = lambda zid: zonas[zid]["es"]

    # ---------- avisos
    numeros = []
    for i, a in enumerate(b["avisos"], 1):
        d = f"Aviso {a['numero'] or i}"
        if not a["numero"].strip().isdigit():
            err.append(f"{d}: falta el número de aviso (solo dígitos).")
        else:
            numeros.append(a["numero"].strip())
        if a.get("estado") in ("cese", "fuera_area"):
            continue
        if a["causa"] in ("CFNT", "WFNT", "CICLOGENESIS") and not a["detalle"].strip():
            err.append(f"{d}: falta la posición de la causa.")
        if a["causa"] in ("DEPRESION", "OTRA") and not a["detalle"].strip():
            err.append(f"{d}: falta el detalle de la causa.")
        if not a["dir"]:
            err.append(f"{d}: falta la dirección del viento.")
        if not a["zonas"] and not a["coords"].strip():
            err.append(f"{d}: indicá las zonas afectadas o las coordenadas.")
        for campo in ("desde", "hasta"):
            if a.get(campo, "").strip():
                _hora(a[campo], b, d, err, adv)
        if not a.get("desde", "").strip() and not a.get("hasta", "").strip() and a.get("estado", "nuevo") == "nuevo":
            adv.append(f"{d}: no indica desde cuándo rige.")
    if len(numeros) != len(set(numeros)):
        err.append("Avisos: hay números de aviso repetidos.")

    # ---------- sinopsis
    for i, s in enumerate(b["sinopsis"], 1):
        d = f"Sinopsis › sistema {i}"
        tipo = cat["sinopsis"]["tipos"][s["tipo"]]
        # Las posiciones no siempre se ponen: solo se advierte si el formato es raro.
        if tipo.get("presion") and s.get("presion", "").strip() and not re.fullmatch(r"\d{3,4}", s["presion"].strip()):
            err.append(f"{d}: la presión debe ser un número en hPa (ej. 993).")
        if not tipo.get("posicion_libre"):
            _pos(s.get("pos", ""), d, adv, obligatoria=False)
        if s.get("exp_pos", "").strip():
            _pos(s["exp_pos"], f"{d} (posición final)", adv)
        if s.get("exp_hora", "").strip():
            _hora(s["exp_hora"], b, f"{d} (hora de la posición final)", err, adv)
        if s.get("ext_tipo"):
            _pos(s.get("ext_pos", ""), f"{d} (frente asociado)", adv, obligatoria=False)
            if s.get("ext_exp_pos", "").strip():
                _pos(s["ext_exp_pos"], f"{d} (posición final del frente)", adv)
            if s.get("ext_exp_hora", "").strip():
                _hora(s["ext_exp_hora"], b, f"{d} (hora del frente)", err, adv)
    if not b["sinopsis"]:
        adv.append("Sinopsis: no hay sistemas cargados.")

    # ---------- hielos
    if b.get("hielos", "").strip():
        bloques = render.bloques_hielo(cat, b["hielos"])
        if "es" not in bloques:
            adv.append("Hielos: el archivo no trae el bloque en castellano; revisá el boletín en castellano.")
        en = render.hielos(cat, b["hielos"], "en")
        restos = [p for p in cat["hielos"]["palabras_sospechosas"] if p in en]
        if restos:
            adv.append(f"Hielos: después de traducir quedan palabras en castellano ({', '.join(restos)}). Revisá el texto en inglés.")
    else:
        adv.append("Hielos: el bloque de información de hielos está vacío.")

    # ---------- olas
    if (b.get("olas") or "").strip():
        from . import olas
        datos = olas.leer(b["olas"])
        zonas_cat = {z["id"]: z for z in todas_las_zonas(cat)}
        if datos["valido"]:
            mes, dia, hora = datos["valido"]["desde"]
            t0 = render.tiempos(b)["inicio"]
            try:
                desde = dt.datetime(t0.year, mes, dia, hora)
                if abs((desde - t0).total_seconds()) > 6 * 3600:
                    adv.append(f"Olas: el archivo es válido desde el {dia:02d}/{mes:02d} {hora:02d} UTC; "
                               "no parece corresponder a este boletín.")
            except ValueError:
                pass
        else:
            adv.append("Olas: no se encontró la línea «PRONOSTICO VALIDO DESDE…» en el archivo.")
        for linea_rara in datos["no_reconocidos"]:
            adv.append(f"Olas: no se reconoció el aviso «{linea_rara}»; no se incluyó.")
        for a in olas.seleccionados(b):
            if olas.linea(cat, zonas_cat, a, "es") is None:
                adv.append(f"Olas: «{a['evol']}» no tiene traducción en el catálogo (aviso de {a['area']}).")
        otras = sorted({a["area"] for a in olas.seleccionados(b) if a["area"] not in cat["olas"]["areas"]})
        if otras:
            adv.append("Olas: hay avisos en áreas que no son del boletín (" + ", ".join(otras) + "). "
                       "Destildalas si no corresponden.")

    # ---------- zonas
    excluidas = []
    for zid, zd in b["zonas"].items():
        if zid not in zonas:
            continue
        if not zd.get("incluir"):
            excluidas.append(nombre(zid))
            continue
        subs = zd["subzonas"]
        restos = 0
        for i, sz in enumerate(subs, 1):
            d = nombre(zid) + (f" › subzona {i}" if len(subs) > 1 else "")
            if len(subs) > 1:
                _division(sz["division"], d, err)
                restos += sz["division"]["tipo"] == "resto"
            _viento(sz["viento"], d, b, err, adv)
            _fenomenos(sz["fenomenos"], d, err)
            if not sz["vis"].get("v1"):
                err.append(f"{d}: falta la visibilidad.")
        if restos > 1:
            err.append(f"{nombre(zid)}: solo puede haber una subzona «resto del área».")
        if len(subs) > 1 and subs[-1]["division"]["tipo"] != "resto":
            adv.append(f"{nombre(zid)}: la zona está dividida y no tiene «resto del área». ¿Cubre toda el área?")
    if excluidas:
        if len(excluidas) == len(zonas):
            err.append("No hay pronóstico para ninguna zona.")
        else:
            adv.append("Zonas no incluidas en este boletín: " + ", ".join(excluidas) + ".")

    # ---------- coherencia avisos ↔ zonas
    cubiertas: dict[str, int] = {}
    for a in b["avisos"]:
        if a.get("estado") in ("cese", "fuera_area"):
            continue
        for zid in a["zonas"]:
            cubiertas[zid] = max(cubiertas.get(zid, 0), int(a["fuerza"]))
    for zid, zd in b["zonas"].items():
        if zid not in zonas or not zd.get("incluir"):
            continue
        maximo = max([f for sz in zd["subzonas"] for f in render.fuerzas_sostenidas(sz["viento"])] or [0])
        if zid in cubiertas and maximo < cubiertas[zid]:
            adv.append(f"{nombre(zid)}: tiene aviso de fuerza {cubiertas[zid]} pero el pronóstico llega a {maximo}.")
        if maximo >= 8 and zid not in cubiertas:
            adv.append(f"{nombre(zid)}: el pronóstico llega a fuerza {maximo} y ningún aviso nombra la zona (puede estar cubierta por coordenadas).")

    # ---------- textos libres sin traducir
    pendientes = [t for t in render.textos_libres(b) if t not in b.get("traducciones", {})]
    if pendientes:
        adv.append(f"Hay {len(pendientes)} texto(s) libre(s) sin traducir: en el inglés saldrán como [TRADUCIR: …].")

    # ---------- NAVTEX
    if not any(a.get("navtex") for a in b["avisos"]) and not any(s.get("navtex") for s in b["sinopsis"]):
        adv.append("NAVTEX: no hay avisos ni sistemas marcados para el boletín NAVTEX.")

    # ---------- escala de viento
    if not cat["viento"]["escala"].get("confirmada"):
        adv.append("La tabla de palabras → Beaufort (leves, moderados, regulares…) todavía no está "
                   "confirmada por el área de pronóstico. Revisá las fuerzas.")

    # ---------- fecha
    t = render.tiempos(b)
    if t["inicio"] < dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) - dt.timedelta(hours=12):
        adv.append("La fecha del boletín es anterior a hoy. ¿Es la correcta?")

    return err, adv
