"""Numeración de los avisos, sin depender del sistema anterior.

- Avisos de temporal: número correlativo anual. Un aviso nuevo toma el
  siguiente; uno que se actualiza conserva el suyo.
- Avisos de olas: serie propia, también correlativa anual. Se numeran solos:
  un área que ya tenía aviso vigente conserva su número, un área nueva toma el
  siguiente y un área que deja de tener aviso pasa a CESE.
- Las dos series vuelven a 1 el 1 de enero.

El registro es un archivo JSON en DATA_DIR (registro_avisos.json) con lo que
se emitió en cada corrida. El estado (último número, avisos vigentes) se
calcula repasando las corridas anteriores a la que se genera, así que volver a
generar la misma corrida no gasta números nuevos.
"""
import datetime as dt
import json

from . import almacen, olas, render

VACIO = {"arranque": {"anio": None, "viento": 0, "olas": 0, "vigentes_viento": []}, "corridas": {}}


def ruta():
    return almacen.carpeta().parent / "registro_avisos.json"


def cargar() -> dict:
    p = ruta()
    if p.exists():
        reg = json.loads(p.read_text(encoding="utf-8"))
        reg.setdefault("arranque", dict(VACIO["arranque"]))
        reg.setdefault("corridas", {})
        return reg
    return json.loads(json.dumps(VACIO))


def guardar(reg: dict):
    ruta().write_text(json.dumps(reg, ensure_ascii=False, indent=1), encoding="utf-8")


def clave_corrida(b: dict) -> str:
    return f"{render.tiempos(b)['inicio']:%Y%m%d%H}"


def estado_previo(reg: dict, clave: str) -> tuple[dict, dict]:
    """(vigentes {serie: {numero: datos}}, último número del año {serie: n}) antes de la corrida `clave`."""
    anio = int(clave[:4])
    arr = reg.get("arranque", {})
    vig = {"viento": {int(n): {"numero": int(n), "desde": "arranque"} for n in arr.get("vigentes_viento", [])},
           "olas": {}}
    ult = {"viento": 0, "olas": 0}
    if arr.get("anio") == anio:
        ult = {"viento": int(arr.get("viento") or 0), "olas": int(arr.get("olas") or 0)}
    for k in sorted(c for c in reg.get("corridas", {}) if c < clave):
        for serie in ("viento", "olas"):
            for e in reg["corridas"][k].get(serie, []):
                n = int(e["numero"])
                if int(k[:4]) == anio:
                    ult[serie] = max(ult[serie], n)
                if e["estado"] in ("cese", "fuera_area"):
                    vig[serie].pop(n, None)
                else:
                    vig[serie][n] = {**e, "corrida": k}
    return vig, ult


def numerar(cat: dict, b: dict, reg: dict | None = None) -> dict:
    """Asigna números a los avisos nuevos y a los de olas; deja en b["registro_info"] lo que hay que revisar."""
    reg = reg if reg is not None else cargar()
    clave = clave_corrida(b)
    vig, ult = estado_previo(reg, clave)
    info = {"vigentes_sin_mencionar": [], "no_vigentes": [], "ya_usados": [], "asignados": [],
            "ultimo_viento": ult["viento"], "ultimo_olas": ult["olas"]}

    # ---- temporal
    siguiente = ult["viento"]
    mencionados = set()
    for a in b.get("avisos", []):
        num = str(a.get("numero", "")).strip()
        if a.get("numero_auto") and a.get("estado", "nuevo") == "nuevo":
            num = ""                    # se vuelve a asignar (la corrida pudo cambiar)
        if not num and a.get("estado", "nuevo") == "nuevo":
            siguiente += 1
            a["numero"], a["numero_auto"] = str(siguiente), True
            info["asignados"].append(siguiente)
            mencionados.add(siguiente)
            continue
        if not num.isdigit():
            continue
        n = int(num)
        mencionados.add(n)
        if a.get("estado") in ("actualiza", "cese", "fuera_area") and n not in vig["viento"]:
            info["no_vigentes"].append(n)
        if a.get("estado", "nuevo") == "nuevo" and n not in vig["viento"] and n <= ult["viento"]:
            info["ya_usados"].append(n)
    info["vigentes_sin_mencionar"] = sorted(n for n in vig["viento"] if n not in mencionados)

    # ---- olas (solo si se cargó el archivo de esta corrida)
    b["olas_numeros"], b["olas_estados"], b["olas_ceses"] = {}, {}, []
    if (b.get("olas") or "").strip():
        por_area_vigente = {e.get("area"): n for n, e in vig["olas"].items()}
        por_area, sig_olas = {}, ult["olas"]
        for a in olas.seleccionados(b, cat):
            if a["area"] not in por_area:
                if a["area"] in por_area_vigente:
                    n, estado = por_area_vigente[a["area"]], "actualiza"
                else:
                    sig_olas += 1
                    n, estado = sig_olas, "nuevo"
                por_area[a["area"]] = n
                b["olas_estados"][str(n)] = estado
            b["olas_numeros"][a["clave"]] = por_area[a["area"]]
        b["olas_ceses"] = sorted(n for area, n in por_area_vigente.items() if area not in por_area)
        b["olas_areas"] = {str(n): area for area, n in por_area.items()}
    b["registro_info"] = info
    return info


def registrar(cat: dict, b: dict, reg: dict | None = None, autor: str = "") -> dict:
    """Guarda lo emitido en esta corrida (reemplaza lo que hubiera de la misma corrida)."""
    guardar_al_final = reg is None
    reg = reg if reg is not None else cargar()
    viento = [{"numero": int(a["numero"]), "estado": a.get("estado", "nuevo"), "zonas": a.get("zonas", []),
               "coords": a.get("coords", ""), "texto": render.linea_aviso(cat, b, a, "es")}
              for a in b.get("avisos", []) if str(a.get("numero", "")).isdigit()]
    olas_reg = [{"numero": int(n), "estado": b.get("olas_estados", {}).get(n, "nuevo"), "area": area}
                for n, area in b.get("olas_areas", {}).items()]
    olas_reg += [{"numero": n, "estado": "cese", "area": ""} for n in b.get("olas_ceses", [])]
    entrada = {"generado": dt.datetime.now().isoformat(timespec="seconds"), "autor": autor, "viento": viento}
    if (b.get("olas") or "").strip():
        entrada["olas"] = olas_reg
    reg.setdefault("corridas", {})[clave_corrida(b)] = entrada
    if guardar_al_final:
        guardar(reg)
    return reg


def resumen(reg: dict | None = None, clave: str | None = None) -> dict:
    """Estado para mostrar: último número y vigentes a partir de la corrida `clave` (por defecto, después de todo)."""
    reg = reg if reg is not None else cargar()
    vig, ult = estado_previo(reg, clave or f"{dt.date.today().year}123199")
    return {"ultimo_viento": ult["viento"], "ultimo_olas": ult["olas"],
            "vigentes_viento": sorted(vig["viento"]), "vigentes_olas": {n: e.get("area", "") for n, e in vig["olas"].items()}}
