"""Estadísticas para la pestaña «Estadísticas», a partir de los CSV de estadisticas.py.

Todo se calcula entre dos fechas (fecha de inicio de validez de cada corrida).
Sin base de datos: lee los avisos_AAAA.csv y pronosticos_AAAA.csv de los años
del rango.
"""
import datetime as dt

import pandas as pd

from . import estadisticas

VIS_MALA = {"MALA", "MUY_MALA"}


def _leer(prefijo: str, desde: dt.date, hasta: dt.date) -> pd.DataFrame:
    partes = []
    for anio in range(desde.year, hasta.year + 1):
        ruta = estadisticas.carpeta() / f"{prefijo}_{anio}.csv"
        if ruta.exists():
            partes.append(pd.read_csv(ruta, sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False))
    if not partes:
        return pd.DataFrame()
    df = pd.concat(partes, ignore_index=True)
    df["fecha"] = pd.to_datetime(df["valido_desde_utc"].str[:10]).dt.date
    return df[(df["fecha"] >= desde) & (df["fecha"] <= hasta)].copy()


def _num(serie: pd.Series) -> pd.Series:
    return pd.to_numeric(serie, errors="coerce")


def calcular(desde: dt.date, hasta: dt.date) -> dict:
    """Resumen del período. Si no hay datos, devuelve {'vacio': True}."""
    pr, av = _leer("pronosticos", desde, hasta), _leer("avisos", desde, hasta)
    if pr.empty and av.empty:
        return {"vacio": True}
    corridas = sorted(set(pr.get("corrida", [])) | set(av.get("corrida", [])))
    if pr.empty:
        pr = pd.DataFrame(columns=estadisticas.CAMPOS_PRONOSTICOS + ["fecha"])
    if av.empty:
        av = pd.DataFrame(columns=estadisticas.CAMPOS_AVISOS + ["fecha"])

    pr["fmax"] = _num(pr["fuerza_max_periodo"])
    temporal = av[av["serie"] == "temporal"]
    olas = av[av["serie"] == "olas"]
    activos = temporal[~temporal["estado"].isin(["cese", "fuera_area"])]
    # Avisos distintos que estuvieron vigentes (un número que solo aparece como cese no cuenta)
    nuevos_t = activos["numero"].replace("", pd.NA).dropna().unique()
    nuevos_o = olas[olas["estado"] != "cese"]["numero"].replace("", pd.NA).dropna().unique()

    # ---- por zona
    pr["temporal_8"] = pr["fmax"] >= 8
    pr["con_aviso"] = pr["con_aviso_temporal"] != ""
    pr["con_fen"] = pr["sin_fenomenos"] == "no"
    pr["vis_mala"] = pr["vis"].isin(VIS_MALA) | pr["vis_hasta"].isin(VIS_MALA)
    por_zona = (pr.groupby(["zona_id", "zona"], sort=False)
                .agg(corridas=("corrida", "nunique"), fuerza_max=("fmax", "max"), fuerza_media=("fmax", "mean"),
                     corridas_f8=("temporal_8", "sum"), con_aviso=("con_aviso", "sum"),
                     con_fenomenos=("con_fen", "sum"), vis_mala=("vis_mala", "sum"))
                .reset_index())
    por_zona["fuerza_media"] = por_zona["fuerza_media"].round(1)

    # ---- fenómenos (cada fenómeno cuenta una vez por zona y corrida)
    fen = pr[pr["fenomenos"] != ""][["corrida", "zona_id", "fenomenos"]].copy()
    fen["fenomeno"] = fen["fenomenos"].str.split("|")
    fen = fen.explode("fenomeno").drop_duplicates(["corrida", "zona_id", "fenomeno"])
    fenomenos = fen["fenomeno"].value_counts().rename_axis("fenomeno").reset_index(name="veces")

    # ---- por día
    dias = pd.DataFrame({"fecha": pd.date_range(desde, hasta).date})
    f_dia = pr.groupby("fecha")["fmax"].max().rename("fuerza_max")
    a_dia = activos.groupby("fecha")["numero"].nunique().rename("avisos_temporal")
    o_dia = olas[olas["estado"] != "cese"].groupby("fecha")["numero"].nunique().rename("avisos_olas")
    por_dia = dias.join(f_dia, on="fecha").join(a_dia, on="fecha").join(o_dia, on="fecha")
    por_dia[["avisos_temporal", "avisos_olas"]] = por_dia[["avisos_temporal", "avisos_olas"]].fillna(0).astype(int)

    # ---- por pronosticador
    autores = pd.concat([pr[["corrida", "autor"]], av[["corrida", "autor"]]]).drop_duplicates()
    autores["autor"] = autores["autor"].replace("", "(sin nombre)")
    por_autor = autores.groupby("autor")["corrida"].nunique().sort_values(ascending=False) \
        .rename_axis("autor").reset_index(name="boletines")

    # ---- lista de avisos (última aparición de cada número)
    lista = av[av["numero"] != ""].sort_values("corrida").groupby(["serie", "numero"], sort=False).agg(
        primera=("valido_desde_utc", "first"), ultima=("valido_desde_utc", "last"), corridas=("corrida", "nunique"),
        estado_final=("estado", "last"), fuerza=("fuerza_beaufort", "max"), zonas=("zonas", "last"),
        coordenadas=("coordenadas", "last"), texto=("texto_es", lambda s: next((x for x in s[::-1] if x), ""))
    ).reset_index().sort_values(["serie", "primera"], ascending=[False, True])

    return {
        "vacio": False,
        "boletines": len(corridas),
        "dias_con_boletin": len({c[:8] for c in corridas}),
        "avisos_temporal": len(nuevos_t),
        "avisos_olas": len(nuevos_o),
        "corridas_con_aviso": int(activos["corrida"].nunique()),
        "fuerza_max": None if pr["fmax"].isna().all() else int(pr["fmax"].max()),
        "zona_mas_ventosa": None if por_zona["fuerza_max"].isna().all()
        else por_zona.loc[por_zona["fuerza_max"].idxmax(), "zona"],
        "por_zona": por_zona, "fenomenos": fenomenos, "por_dia": por_dia, "por_autor": por_autor, "avisos": lista,
    }
