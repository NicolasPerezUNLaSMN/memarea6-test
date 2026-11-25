"""Atajos para armar boletines de prueba sin escribir todo el dict."""
from core import modelo


def W(dir, fuerza="", raf="", raf_int="", cambios=()):
    v = modelo.nuevo_viento()
    v.update(dir=dir, fuerza=fuerza, rafagas=raf, raf_int=raf_int, cambios=list(cambios))
    return v


def C(tipo, dir="", fuerza="", raf="", hora="", tempo=False, raf_int=""):
    c = modelo.nuevo_cambio()
    c.update(tipo=tipo, dir=dir, fuerza=fuerza, rafagas=raf, hora=hora, tempo=tempo, raf_int=raf_int)
    return c


def F(*fen, prob="PROB", cal="", mom="", evol="", con=""):
    it = modelo.nuevo_item_fenomeno()
    it.update(fen=list(fen), prob=prob, cal=cal, momento=mom, evol=evol, conector=con)
    return it


def V(v1, hasta="", ocnl=""):
    return {"v1": v1, "hasta": hasta, "ocnl": ocnl}


def SZ(viento, fen, vis, div=None, sin=False, obs=""):
    s = modelo.nueva_subzona()
    s.update(viento=viento, fenomenos={"sin_fenomenos": sin, "items": list(fen)}, vis=vis, obs=obs)
    if div:
        s["division"] = div
    return s


def COND(*pares):
    return {"tipo": "condiciones", "conds": [{"id": "x", "rel": r, "valor": v} for r, v in pares]}


RESTO = {"tipo": "resto", "conds": []}
