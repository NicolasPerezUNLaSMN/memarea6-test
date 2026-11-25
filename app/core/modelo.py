"""Estructura de datos del boletín (un dict serializable a JSON)."""
import copy
import datetime as dt
import uuid

from .catalogo import todas_las_zonas


def nid() -> str:
    return uuid.uuid4().hex[:8]


def nuevo_cambio() -> dict:
    return {"id": nid(), "tempo": False, "tipo": "BACK", "dir": "", "fuerza": "",
            "rafagas": "", "raf_int": "", "hora": ""}


def nuevo_viento() -> dict:
    return {"dir": "", "fuerza": "", "rafagas": "", "raf_int": "", "cambios": []}


def nuevo_item_fenomeno() -> dict:
    return {"id": nid(), "conector": "", "prob": "PROB", "fen": [], "cal": "",
            "momento": "", "evol": "", "momento_evol": ""}


def nueva_subzona() -> dict:
    return {
        "id": nid(),
        "division": {"tipo": "condiciones", "conds": [{"id": nid(), "rel": "N", "valor": ""}],
                     "lat1": "", "lat2": "", "lon1": "", "lon2": "", "cuadrante": "NE"},
        "viento": nuevo_viento(),
        "fenomenos": {"sin_fenomenos": False, "items": [nuevo_item_fenomeno()]},
        "vis": {"v1": "", "hasta": "", "ocnl": "", "ocnl_antes": False},
        "obs": "",
    }


def nuevo_aviso() -> dict:
    return {"id": nid(), "numero": "", "estado": "nuevo", "causa": "GRADIENTE", "detalle": "", "verbo": "futuro",
            "fuerza": "8", "dir": "", "rafagas": True, "zonas": [], "coords": "", "desde": "", "hasta": "", "navtex": False}


def nuevo_sistema() -> dict:
    return {"id": nid(), "tipo": "DEPRESION", "presion": "", "pos": "", "mov": "", "evol": [],
            "exp_pos": "", "exp_hora": "", "ext_tipo": "", "ext_pos": "", "ext_mov": "",
            "ext_exp_pos": "", "ext_exp_hora": "", "navtex": False}


def proxima_corrida(ahora: dt.datetime | None = None) -> tuple[dt.date, str]:
    """Sugerencia de fecha/corrida según la hora UTC actual."""
    ahora = ahora or dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    if ahora.hour < 12:
        return ahora.date(), "12"
    return ahora.date() + dt.timedelta(days=1), "00"


def nuevo_boletin(cat: dict) -> dict:
    fecha, corrida = proxima_corrida()
    return {
        "version": 1,
        "fecha": fecha.isoformat(),
        "corrida": corrida,
        "avisos": [],
        "hielos": "",
        "olas": "",
        "olas_excluir": [],
        "sinopsis": [],
        "zonas": {z["id"]: {"incluir": True, "subzonas": [nueva_subzona()]}
                  for z in todas_las_zonas(cat)},
        "traducciones": {},
    }


def siguiente_desde(b: dict) -> dict:
    """Copia de un boletín anterior, avanzada a la corrida siguiente."""
    n = copy.deepcopy(b)
    f = dt.date.fromisoformat(b["fecha"])
    if b["corrida"] == "00":
        n["corrida"] = "12"
    else:
        n["corrida"], n["fecha"] = "00", (f + dt.timedelta(days=1)).isoformat()
    return n


def recargar_ids(obj):
    """Regenera los ids internos (al copiar subzonas entre zonas)."""
    if isinstance(obj, dict):
        if "id" in obj:
            obj["id"] = nid()
        for v in obj.values():
            recargar_ids(v)
    elif isinstance(obj, list):
        for v in obj:
            recargar_ids(v)
    return obj


def completar(b: dict, cat: dict) -> dict:
    """Agrega zonas faltantes (si el catálogo cambió) a un boletín cargado."""
    for z in todas_las_zonas(cat):
        b["zonas"].setdefault(z["id"], {"incluir": False, "subzonas": [nueva_subzona()]})
    b.setdefault("traducciones", {})
    b.setdefault("olas", "")
    b.setdefault("olas_excluir", [])
    return b
