"""Intérprete por reglas (sin IA) con los borradores reales de pronosticadores."""
import json
from pathlib import Path

from core import catalogo, interpretar, reglas, render, validar

CAT = catalogo.cargar()
DIR = Path(__file__).parent / "borradores"


def boletin(nombre, fecha):
    texto = interpretar.leer_archivo((DIR / nombre).read_bytes(), nombre)
    datos = reglas.interpretar(CAT, texto)
    b, dudas = interpretar.a_boletin(CAT, datos, {"fecha": fecha, "corrida": "12", "hielos": ""})
    return b, dudas, render.generar(CAT, b, "es")


def test_24_7_igual_a_lo_esperado():
    b, dudas, es = boletin("navegante_24-7.docx", "2026-07-24")
    esperado = json.loads((DIR / "navegante_24-7_esperado_ia.json").read_text(encoding="utf-8"))
    b2, _ = interpretar.a_boletin(CAT, esperado, {"fecha": "2026-07-24", "corrida": "12", "hielos": ""})
    assert es == render.generar(CAT, b2, "es")
    assert [d["motivo"] for d in dudas] == ["No se encontró la visibilidad."]


def test_01_7_avisos_copias_y_sinopsis():
    b, dudas, es = boletin("navegante_01-07.docx", "2026-07-01")
    for linea in [
        "AVISO 298: CESE",
        "AVISO 300: FUERA DEL AREA",
        "AVISO 302: DEPRESION 997HPA 52S 43W PROVOCA VIENTO FUERZA 8 DEL SECTOR W CON RAFAGAS ENTRE 45S-50S 40W-30W HASTA EL 01/1800",
        "DEPRESION 997HPA 52S 43W MOV SE WKN EXP 57S 21W EL 02/1200 EXTIENDE CFNT EN 48S 42W 41S 51W 36S 62W MOV E "
        "EXP 38S 44W 48S 24W 52S 20W EL 02/1200",
        "ANTICICLON 1040HPA 42S 65W INTSF",
        "COSTA SUDESTE DEL URUGUAY: SECTOR S 4 CON RAFAGAS PROB DE NEBLINAS BANCOS DE NIEBLA PROB DE LLUVIAS SH VIS REGULAR",
        "AREA PASAJE DE DRAKE (55S- 60S Y 60W- 67W): SECTOR W 8 CON RAFAGAS TEMPO DECR 6 CON RAFAGAS PROB DE LLUVIA Y "
        "NIEVE MEZCLADA VIS MALA OCNL REGULAR",
        "AREA SUDOESTE (50S- 60S Y 40W- 60W): SECTOR S 7 RAFAGAS CON INTENSIDAD 8 BACK SECTOR W 8 EL 01/1500",
        "AREA CENTRO ESTE (40S- 50S Y 20W- 40W) S DE 45S - E DE 30W: NW 8 CON RAFAGAS DECR 6 CON RAFAGAS EL 01/1800",
    ]:
        assert linea in es, linea
    motivos = " ".join(d["motivo"] for d in dudas)
    assert "horario o antihorario" in motivos      # «en el sentido que su corazón diga»
    assert "45S-50S" in motivos                    # área del aviso 302
    assert validar.validar(CAT, b)[0] == []


def test_05_7_sin_proba_ciclogenesis_y_copia_explicita():
    b, dudas, es = boletin("navegante_05-07.docx", "2026-07-05")
    for linea in [
        "AVISO 308: FUERTE GRADIENTE BARICO PROVOCARA VIENTO FUERZA 9 DEL SECTOR W CON RAFAGAS EN AREA PASAJE DE DRAKE",
        "CICLOGENESIS EXP 38S 51W EL 06/1200",
        "ANTICICLON 1028HPA 44S 41W MOV NE WKN EXP 41S 34W EL 06/1200",
        "NEBLINAS BANCOS DE NIEBLA PROB DE LLUVIAS LLOVIZNAS VIS REGULAR OCNL MALA",
        "AREA NORTE (35S- 40S Y 20W- 55W) E DE 40W: SE 7/6 CON RAFAGAS VEER SECTOR E 4 PROB DE LLOVIZNAS",
        "AREA PASAJE DE DRAKE (55S- 60S Y 60W- 67W): NW 6/8 CON RAFAGAS PROB DE LLUVIAS VIS REGULAR A MALA",
    ]:
        assert linea in es, linea
    errores, advertencias = validar.validar(CAT, b)
    assert errores == []
    assert any("16/0000" in a for a in advertencias)   # «el 16 a las 0», fuera de validez


def test_19_9_plantilla_vacia():
    b, dudas, es = boletin("navegante_19-09-12utc.txt", "2026-09-19")
    assert "AVISO 427 ACTUALIZADO: FUERTE GRADIENTE BARICO PROVOCA VIENTO FUERZA 8 DEL SECTOR N CON RAFAGAS " \
           "EN AREA SUDOESTE (50S- 60S Y 40W- 60W) HASTA EL 19/1800" in es
    assert "No hay pronóstico para ninguna zona." in validar.validar(CAT, b)[0]
