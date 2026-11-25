"""Post-proceso de la interpretación (sin llamar a la IA).

navegante_24-7_esperado_ia.json es lo que la IA debería devolver para el
borrador real navegante_24-7.docx; sirve para probar todo lo que pasa
después de la IA, y como referencia para evaluar la IA real
(scripts/probar_borradores.py).
"""
import json
from pathlib import Path

from core import catalogo, interpretar, render, validar

CAT = catalogo.cargar()
DIR = Path(__file__).parent / "borradores"
BASE = {"fecha": "2026-07-24", "corrida": "12", "hielos": ""}


def cargar_24_7():
    datos = json.loads((DIR / "navegante_24-7_esperado_ia.json").read_text(encoding="utf-8"))
    return interpretar.a_boletin(CAT, datos, BASE)


def test_borrador_24_7_genera_boletin():
    b, dudas = cargar_24_7()
    es, en = render.generar(CAT, b, "es"), render.generar(CAT, b, "en")
    assert "AVISO 342 ACTUALIZADO: FUERTE GRADIENTE BARICO PROVOCA VIENTO FUERZA 8 DEL SECTOR W CON RAFAGAS " \
           "EN AREA SUDESTE (50S- 60S Y 20W- 40W) HASTA EL 25/0900" in es
    assert "ANTICICLON 1026HPA 38S 44W MOV E INTSF EXP 36S 28W EL 25/1200" in es
    assert "RIO DE LA PLATA EXTERIOR: SECTOR N 5/4 CON RAFAGAS BAJA PROB DE LLOVIZNAS AISLADAS " \
           "PROB DE NEBLINAS DURANTE LA MAÑANA VIS REGULAR OCNL BUENA" in es
    assert "AREA NORTE (35S- 40S Y 20W- 55W) E DE 35W: SECTOR S 5/6 CON RAFAGAS PROB DE LLOVIZNAS VIS REGULAR" in es
    assert "SOUTH WEST AREA (50S- 60S AND 40W- 60W): SECTOR W 6 GUST WITH 8 INTENSITY DECR 4 BY 26/0600" in en
    errores, advertencias = validar.validar(CAT, b)
    assert errores == ["AREA CENTRO ESTE (40S- 50S Y 20W- 40W): falta la visibilidad."]
    assert any("26/0600" in a for a in advertencias)
    assert len(dudas) == 2


def _zona(zid, copiar_de="", subzonas=None):
    return {"zona": zid, "copiar_de": copiar_de, "subzonas": subzonas or []}


def test_copias_encadenadas_y_fuente_faltante():
    datos = json.loads((DIR / "navegante_24-7_esperado_ia.json").read_text(encoding="utf-8"))
    fuente = next(z for z in datos["zonas"] if z["zona"] == "malvinas")
    datos["zonas"] = [fuente, _zona("drake", "malvinas"), _zona("sudoeste", "drake"), _zona("findm", "golfo_inexistente"),
                      _zona("patsur", "sanjorge")]
    b, dudas = interpretar.a_boletin(CAT, datos, BASE)
    oce = render.lineas_grupo(CAT, b, "oceanicas", "es")
    assert len(oce) == 2  # drake y sudoeste, copiados de malvinas
    assert all(l.split(": ", 1)[1] == "SECTOR E 6 CON RAFAGAS PROB DE LLUVIAS VIS REGULAR OCNL MALA" for l in oce)
    assert not b["zonas"]["patsur"]["incluir"]
    assert any("SAN JORGE" in d["motivo"] for d in dudas)


def test_escala_de_viento():
    assert interpretar._fuerza(CAT, ["FUERTES", "REGULARES"]) == "6/5"
    assert interpretar._fuerza(CAT, ["TEMPORAL"]) == "8"
    assert interpretar._fuerza(CAT, ["FUERTES", "FUERTES"]) == "6"
    assert interpretar._fuerza(CAT, ["5", "6"]) == "5/6"


def test_lee_docx():
    texto = interpretar.leer_archivo((DIR / "navegante_24-7.docx").read_bytes(), "a.docx")
    assert "fuerte gradiente barico" in texto and "Drake" in texto


def test_esquema_usa_el_catalogo():
    esquema = json.dumps(interpretar._esquema(CAT))
    for clave in ("SH_NIEVE", "DESMEJORANDO", "MUY_FUERTES", "fuera_area", "CICLOGENESIS", "drake"):
        assert clave in esquema


def test_archivo_de_hielos_bilingue():
    texto = (DIR / "hielos_NAVAREAVI_20260922.txt").read_text(encoding="utf-8")
    es, en = render.hielos(CAT, texto, "es"), render.hielos(CAT, texto, "en")
    assert es.startswith("221400 UTC 1.LIMITE DE HIELO MARINO 5534S 02000W")
    assert en.startswith("221400 UTC 1.SEA ICE LIMIT 5534S 02000W")
    assert es.endswith("6117S 06716W 6700S 06716W") and en.endswith("6117S 06716W 6700S 06716W")
    assert "INFORMAR" not in es and "REPORT POSITION" not in en and "\n" not in es
    assert "TEMPANO2 5648S 04555W 5X3MN" in es and "ICEBERG2 5648S 04555W 5X3NM" in en


def test_hielos_solo_castellano_se_traduce():
    en = render.hielos(CAT, "221400 UTC 1.LIMITE DE HIELO MARINO 5429S 02000W 2.TEMPANOS MAYORES A 10MN A81", "en")
    assert en == "221400 UTC 1.SEA ICE LIMIT 5429S 02000W 2.ICEBERGS GREATER THAN 10NM A81"


def test_olas_solo_avisos_y_debajo_de_los_de_temporal():
    from core import modelo, olas
    b, _ = cargar_24_7()
    b["olas"] = (DIR / "olas_3.txt").read_text(encoding="utf-8")
    es = render.generar(CAT, b, "es").splitlines()
    i = es.index("AVISO DE OLAS:")
    assert es[i - 1].startswith("AVISO 342")                     # justo debajo de los de temporal
    assert es[i + 1] == "AREA PASAJE DE DRAKE (55S- 60S Y 60W- 67W) 15/0900-15/2100 UTC: EN EL S 5.0/6.0M DECRECIENDO, DESPLAZANDOSE AL NE"
    assert len([l for l in es if "UTC: EN EL" in l]) == 6
    assert not any("IN THE REST" in l or "EN EL RESTO" in l for l in es)   # solo los WARNING
    en = render.generar(CAT, b, "en")
    assert "WAVE WARNING:\nDRAKE AREA (55S- 60S AND 60W- 67W) 15/0900-15/2100 UTC: AT S 5.0/6.0M DECAYING, MOVING NE" in en
    # destildar uno
    b["olas_excluir"] = [olas.leer(b["olas"])["avisos"][0]["clave"]]
    assert "AREA PASAJE DE DRAKE" not in "\n".join(l for l in render.generar(CAT, b, "es").splitlines() if "UTC: EN EL" in l)
    # archivo sin avisos: no agrega nada
    b["olas"], b["olas_excluir"] = (DIR / "olas_1.txt").read_text(encoding="utf-8"), []
    assert "AVISO DE OLAS" not in render.generar(CAT, b, "es")
    # validación: fecha del archivo (15/07) distinta del boletín (24/07)
    b["olas"] = (DIR / "olas_3.txt").read_text(encoding="utf-8")
    _, adv = validar.validar(CAT, b)
    assert any("no parece corresponder" in a for a in adv)
    assert any("ZONA 1" in a for a in adv)
