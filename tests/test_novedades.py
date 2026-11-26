"""Casos detectados en las pruebas con pronosticadores."""
from pathlib import Path

from core import catalogo, interpretar, reglas, render

CAT = catalogo.cargar()
DIR = Path(__file__).parent / "borradores"


def _zona(texto):
    sz = reglas.pronostico_zona(reglas.normalizar(texto), [], "x")
    datos = {"zonas": [{"zona": "rdp_int", "copiar_de": "", "subzonas": [sz]}]}
    b, _ = interpretar.a_boletin(CAT, datos, {"fecha": "2026-11-20", "corrida": "12"})
    return [render.lineas_grupo(CAT, b, "costeras", l)[0].split(": ", 1)[1] for l in ("es", "en")]


def test_lluvia_aislada_y_otro_fenomeno():
    es, en = _zona("Leves de direcciones variables. Probabilidad de lluvia aislada y tormentas. Buena a regular.")
    assert es == "VRB 3 PROB DE LLUVIAS AISLADAS Y TORMENTAS VIS BUENA A REGULAR"
    assert en == "VRB 3 PROB OF ISOL RAIN AND TSTM VIS GOOD TO MODERATE"
    es, _ = _zona("Leves del sector N. Lluvias y tormentas aisladas. Buena.")
    assert es == "SECTOR N 3 LLUVIAS TORMENTAS AISLADAS VIS BUENA"        # el calificativo es de las dos


def test_abreviatura_con_punto_al_final():
    es, _ = _zona("Moderados del sector E. Prob. de lluvias aisl. Regular.")
    assert es == "SECTOR E 4 PROB DE LLUVIAS AISLADAS VIS REGULAR"


def test_variantes_de_actualizacion():
    cat_alias = reglas._alias(CAT)
    todos = sorted(cat_alias["costeras"] + cat_alias["oceanicas"], key=lambda x: -len(x[0]))
    lineas = ["342 actualizar: fgb provoca temporal del sector W con rafagas en el area sudeste",
              "AVISO 343 acualizo: fgb provoca temporal del sector N con rafagas en drake",
              "Aviso 344: sige vigente fgb provoca temporal del sector S con rafagas en area sudoeste",
              "AVISO 345 SE MANTIENE: depresion 990 en 50-40 provoca temporal fuerte del sector W en area sudeste",
              "Aviso 346: continua vigente. fgb provoca temporal del NW en golfo san jorge",
              "AVISO 347: fgb provocara temporal del sector W con rafagas en malvinas"]
    avisos = reglas.avisos([reglas.normalizar(l) for l in lineas], todos, [])
    assert [a["estado"] for a in avisos] == ["actualiza"] * 5 + ["nuevo"]
    assert avisos[3]["causa"] == "DEPRESION" and avisos[3]["detalle"] == "990HPA 50S 40W"


def test_estilo_una_letra():
    texto = interpretar.leer_archivo((DIR / "navegante_sin_fecha.docx").read_bytes(), "x.docx")
    datos = reglas.interpretar(CAT, texto)
    b, dudas = interpretar.a_boletin(CAT, datos, {"fecha": "2026-11-23", "corrida": "12", "hielos": ""})
    es = render.generar(CAT, b, "es")
    for linea in [
        "AVISO : FRENTE FRIO LINEA 49S 66W 43S 65W PROVOCARA VIENTO FUERZA 8 DEL SECTOR S CON RAFAGAS EN COSTA "
        "PENINSULA DE VALDES GOLFO DE SAN JORGE COSTA PATAGONIA SUR COSTA FIN DEL MUNDO A PARTIR DEL 24/0000",
        "RINCON BAHIA BLANCA(38º30S - 41ºS): SECTOR N 5 CON RAFAGAS BACK SECTOR S 5/6 CON RAFAGAS EL 24/0900",
        "COSTA FIN DEL MUNDO(54ºS - 55ºS): SECTOR W 5/6 CON RAFAGAS INCR 7/8 EL 24/0600 PROB DE LLUVIAS AISLADAS "
        "MEJORAMIENTOS TEMPORARIOS LUEGO PROB DE LLUVIA Y NIEVE MEZCLADA A PARTIR DE LA NOCHE VIS REGULAR A MALA",
        "COSTA SUDESTE DEL URUGUAY: SECTOR N 4 BACK SECTOR W PROB DE LLUVIAS TORMENTAS AISLADAS HACIA EL FINAL DEL "
        "PERIODO VIS BUENA A REGULAR OCNL MALA",
        "FRENTE ESTACIONARIO 28S 56W 30S 46W NC",
    ]:
        assert linea in es, linea
    # la sección NAVTEX del borrador marca el aviso nuevo y dos sistemas
    assert [a["navtex"] for a in b["avisos"]] == [True]
    assert [s["navtex"] for s in b["sinopsis"]] == [True, False, False, True]
    assert dudas == []          # el aviso nuevo sin número recibe el siguiente al generar


def test_mejorando_y_desmejorando_con_o_sin_tiempo():
    casos = {
        "Regulares del sector W. Probabilidad de lluvias, desmejorando hacia el final del periodo. Regular.":
            ("PROB DE LLUVIAS DESMEJORANDO HACIA EL FINAL DEL PERIODO", "PROB OF RAIN DETERIORATING LATER IN PERIOD"),
        "Regulares del sector W. Prob de lluvias des hacia el final del periodo. Regular.":
            ("PROB DE LLUVIAS DESMEJORANDO HACIA EL FINAL DEL PERIODO", "PROB OF RAIN DETERIORATING LATER IN PERIOD"),
        "Regulares del sector W. Prob de lluvias mej el 24 a las 18. Regular.":
            ("PROB DE LLUVIAS MEJORANDO EL 24/1800", "PROB OF RAIN IMPR BY 24/1800"),
        "Regulares del sector W. Lluvias aisladas mejorando a partir del 24/1800. Regular.":
            ("LLUVIAS AISLADAS MEJORANDO A PARTIR DEL 24/1800", "ISOL RAIN IMPR FROM 24/1800"),
        "Regulares del sector W. Prob de lluvias, des el 24/18z. Regular.":
            ("PROB DE LLUVIAS DESMEJORANDO EL 24/1800", "PROB OF RAIN DETERIORATING BY 24/1800"),
        "Regulares del sector W. Lluvias. Desmejorando. Regular.":
            ("LLUVIAS DESMEJORANDO", "RAIN DETERIORATING"),
        "Regulares del sector W. Desmejorando hacia el final del periodo. Regular.":
            ("DESMEJORANDO HACIA EL FINAL DEL PERIODO", "DETERIORATING LATER IN PERIOD"),
        "Regulares del sector W. Lluvias mejorando hacia la noche luego desmejorando hacia el final del periodo. Regular.":
            ("LLUVIAS MEJORANDO HACIA LA NOCHE LUEGO DESMEJORANDO HACIA EL FINAL DEL PERIODO",
             "RAIN IMPR BY NIGHT NXT DETERIORATING LATER IN PERIOD"),
    }
    for texto, (es, en) in casos.items():
        r_es, r_en = _zona(texto)
        assert r_es == f"SECTOR W 5 {es} VIS REGULAR", texto
        assert r_en == f"SECTOR W 5 {en} VIS MODERATE", texto
