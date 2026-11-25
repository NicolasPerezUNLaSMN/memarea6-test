"""Borradores reales de distintos pronosticadores (estilos, abreviaturas, PDF,
un renglón por elemento) interpretados sin IA, y boletín NAVTEX."""
from pathlib import Path

from core import catalogo, interpretar, reglas, render, validar

CAT = catalogo.cargar()
DIR = Path(__file__).parent / "borradores"


def boletin(nombre, fecha):
    texto = interpretar.leer_archivo((DIR / nombre).read_bytes(), nombre)
    datos = reglas.interpretar(CAT, texto)
    b, dudas = interpretar.a_boletin(CAT, datos, {"fecha": fecha, "corrida": "12", "hielos": ""})
    return b, dudas, render.generar(CAT, b, "es")


def contiene(es, *lineas):
    for l in lineas:
        assert l in es, l


def test_kseminski_idem_resaltado_y_gradiente_en_sinopsis():
    b, dudas, es = boletin("kseminski.docx", "2026-11-08")
    contiene(es,
             "AVISO 466 ACTUALIZADO: FUERTE GRADIENTE BARICO PROVOCA VIENTO FUERZA 8 DEL SECTOR W CON RAFAGAS EN COSTA "
             "PATAGONIA SUR COSTA FIN DEL MUNDO COSTA DE ISLAS MALVINAS AREA PASAJE DE DRAKE",
             "FUERTE GRADIENTE BARICO ENTRE 50S-60S 40W-68W MOV E",
             "RIO DE LA PLATA EXTERIOR: VRB 3 VEER SECTOR N EL 09/0000 NEBLINAS BANCOS DE NIEBLA DISIPANDOSE VIS BUENA OCNL REGULAR",
             "COSTA FIN DEL MUNDO(54ºS - 55ºS): SECTOR W 8 RAFAGAS CON INTENSIDAD 9",
             "AREA NORTE (35S- 40S Y 20W- 55W) W DE 35W:")
    # lo resaltado en el Word va al NAVTEX
    assert [a["navtex"] for a in b["avisos"]] == [True]
    assert [(s["tipo"], s["navtex"]) for s in b["sinopsis"]] == [
        ("GRADIENTE", True), ("DEPRESION", False), ("ANTICICLON", True), ("CFNT", False)]
    assert validar.validar(CAT, b)[0] == []


def test_cabral_telegrafico_cuadrantes_y_seccion_navtex():
    b, dudas, es = boletin("cabral.docx", "2026-11-30")
    contiene(es,
             "ANTICICLON 1039HPA 34S 29W MOV E NC EXTIENDE EJE DE CUÑA EN 34S 29W 48S 27W 57S 27W MOV E",
             "ANTICICLON 1035HPA 53S 83W MOV NE EXP 45S 62W EL 01/0900",
             "RIO DE LA PLATA EXTERIOR: SECTOR W 3 BACK SE NEBLINAS BANCOS DE NIEBLA DISIPANDOSE NEBLINAS BANCOS DE NIEBLA "
             "A PARTIR DE LA NOCHE VIS BUENA OCNL MALA",
             "AREA CENTRO ESTE (40S- 50S Y 20W- 40W) NE DEL AREA: SECTOR W 5 CON RAFAGAS VEER SECTOR N 5/8",
             "AREA NORTE (35S- 40S Y 20W- 55W) W DE 30W - E DE 40W:")
    assert [(s["presion"], s["navtex"]) for s in b["sinopsis"]] == [("1039", False), ("990", True), ("1035", True)]
    motivos = " ".join(d["motivo"] for d in dudas)
    assert "no tiene número" in motivos and "horario o antihorario" in motivos


def test_guetti_cpf_spf_y_cambios_encadenados():
    b, dudas, es = boletin("guetti.docx", "2026-11-20")
    contiene(es,
             "DEPRESION 993HPA 43S 50W MOV S DPN EXP 45S 50W EL 21/1200 EXTIENDE OFNT EN 44S 41W 45S 57W 39S 56W MOV S",
             "DEPRESION 1011HPA 36S 29W MOV E WKN\n",
             "RIO DE LA PLATA EXTERIOR: SECTOR S 3 VEER SECTOR N 3/4 BACK SECTOR W PROB DE SH TORMENTAS AISLADAS",
             "AREA CENTRO ESTE (40S- 50S Y 20W- 40W) E DE 30W - S DE 45S: SECTOR S 4/3 VEER SECTOR W 3 VIS BUENA",
             "RINCON BAHIA BLANCA(38º30S - 41ºS): SECTOR W 4/3 PROB DE LLUVIAS TORMENTAS AISLADAS MEJORANDO HACIA LA MADRUGADA")
    assert dudas == [] and validar.validar(CAT, b)[0] == []


def test_un_renglon_por_elemento_2022():
    b, dudas, es = boletin("navegantes_27-08-2022_12z.docx", "2022-08-27")
    contiene(es,
             "AVISO 389: DEPRESION 973HPA 56S 55W MOV NE PROVOCA VIENTO FUERZA 8 DEL SW CON RAFAGAS EN AREA PASAJE DE DRAKE",
             "DEPRESION 1005HPA 37S 53W MOV SE DPN EXP 49S 25W EL 28/1200 EXTIENDE CFNT EN 37S 53W 34S 58W MOV SE "
             "EXP 49S 25W 37S 35W 30S 45W EL 28/1200",
             "COSTA FIN DEL MUNDO(54ºS - 55ºS): SECTOR S 7/8 CON RAFAGAS VEER SECTOR W 6/7 CON RAFAGAS EL 28/0300",
             "COSTA PENINSULA DE VALDES(41ºS - 45ºS): SECTOR S 6/7 RAFAGAS CON INTENSIDAD 8 DECR 6/5 EL 28/0300 VEER "
             "SECTOR W 4/3 EL 28/0600 PROB DE SH MEJORANDO A PARTIR DEL MEDIODIA VIS MUY MALA A REGULAR")
    assert [a["navtex"] for a in b["avisos"]] == [False, False, True, True]
    assert validar.validar(CAT, b)[0] == []


def test_pdf_montero():
    b, dudas, es = boletin("montero_1.pdf", "2026-11-14")
    contiene(es,
             "DEPRESION 978HPA 55S 47W MOV NE NC EXP 54S 25W EL 15/0000 EXTIENDE CFNT EN 54S 49W 53S 53W 53S 59W MOV E",
             "COSTA PATAGONIA SUR(48ºS - 54ºS): SECTOR W 5/6 CON RAFAGAS BACK SECTOR S 6/7 RAFAGAS CON INTENSIDAD 8 EL "
             "14/0900 PROB DE LLUVIAS FUERTES LUEGO LLUVIA Y NIEVE MEZCLADA MEJORANDO HACIA EL FINAL DEL PERIODO VIS MALA "
             "OCNL MUY MALA A REGULAR",
             "AREA SUDESTE (50S- 60S Y 20W- 40W) RESTO DEL AREA: SECTOR E 6/7 RAFAGAS CON INTENSIDAD 8 VEER SECTOR S 6 "
             "CON RAFAGAS EL 14/1200 VEER SECTOR W EL 14/2100 PROB DE NEVADAS HACIA EL FINAL DEL PERIODO",
             "AREA PASAJE DE DRAKE (55S- 60S Y 60W- 67W): SECTOR S 5/6")
    assert [(s["presion"], s["navtex"]) for s in b["sinopsis"]] == [("1031", True), ("978", False), ("1002", True)]


def test_navtex_formato():
    b, _, _ = boletin("kseminski.docx", "2026-11-08")
    nav = render.generar_navtex(CAT, b)
    lineas = nav.rstrip("\n").split("\n")
    assert lineas[:5] == ["WWST03 SABM 081200", "", "WEATHER BULLETIN FOR NAVTEX STATIONS - METAREA 6 -", "",
                          "NOVEMBER 8, 12:00UTC"]
    assert all(len(l) <= 80 for l in lineas)
    assert all(l == "" for l in lineas[1::2])                       # interlineado doble
    assert "GALE WARNING:\n\nWARNING 466 UPDATED: STRONG BARIC GRADIENT" in nav
    assert "GENERAL SYNOPSIS:\n\nSTRONG BARIC GRADIENT BETWEEN 50S-60S 40W-68W MOV E\n\nHIGH 1029HPA" in nav
    assert "LOW 1002HPA" not in nav                                   # no marcada para NAVTEX
    assert "USHUAIA:    SECTOR W 8 GUST WITH 9 INTENSITY" in nav
    assert lineas[-3:] == ["-----------------------------------------------------------------", "", "NNNN="]
