"""Numeración de avisos: correlativa anual, serie propia para olas, reinicio el 1 de enero."""
from pathlib import Path

from core import catalogo, modelo, registro, render

CAT = catalogo.cargar()
DIR = Path(__file__).parent / "borradores"


def aviso(numero="", estado="nuevo", zonas=("drake",)):
    a = modelo.nuevo_aviso()
    a.update(numero=numero, estado=estado, dir="SECTOR W", zonas=list(zonas), desde="")
    return a


def boletin(fecha, corrida, avisos, olas_txt=""):
    b = modelo.nuevo_boletin(CAT)
    b.update(fecha=fecha, corrida=corrida, avisos=avisos, olas=olas_txt)
    return b


def test_correlativo_actualizacion_y_cese_sugerido():
    reg = {"arranque": {"anio": 2026, "viento": 483, "olas": 0, "vigentes_viento": [483]}, "corridas": {}}
    # 1) aviso nuevo: toma el 484; el 483 vigente no aparece → se sugiere el cese
    b1 = boletin("2026-11-26", "12", [aviso()])
    info = registro.numerar(CAT, b1, reg)
    assert b1["avisos"][0]["numero"] == "484" and info["vigentes_sin_mencionar"] == [483]
    registro.registrar(CAT, b1, reg)
    # 2) regenerar la misma corrida no gasta números
    b1b = boletin("2026-11-26", "12", [aviso()])
    registro.numerar(CAT, b1b, reg)
    assert b1b["avisos"][0]["numero"] == "484"
    # 3) siguiente corrida: el 484 se actualiza, sale uno nuevo (485), el 483 cesa
    b2 = boletin("2026-11-27", "00", [aviso("484", "actualiza"), aviso(), aviso("483", "cese")])
    info = registro.numerar(CAT, b2, reg)
    assert [a["numero"] for a in b2["avisos"]] == ["484", "485", "483"]
    assert info["vigentes_sin_mencionar"] == [] and info["no_vigentes"] == []
    registro.registrar(CAT, b2, reg)
    assert registro.resumen(reg, "2026123199")["vigentes_viento"] == [484, 485]
    # 4) actualizar un aviso que no existe se advierte
    b3 = boletin("2026-11-27", "12", [aviso("999", "actualiza"), aviso("484", "actualiza"), aviso("485", "actualiza")])
    assert registro.numerar(CAT, b3, reg)["no_vigentes"] == [999]


def test_reinicio_el_1_de_enero():
    reg = {"arranque": {"anio": 2026, "viento": 520, "olas": 40, "vigentes_viento": []}, "corridas": {}}
    b = boletin("2026-12-31", "12", [aviso()])
    registro.numerar(CAT, b, reg)
    assert b["avisos"][0]["numero"] == "521"
    registro.registrar(CAT, b, reg)
    b2 = boletin("2027-01-01", "12", [aviso("521", "actualiza", ["norte"]), aviso()])
    registro.numerar(CAT, b2, reg)
    assert [a["numero"] for a in b2["avisos"]] == ["521", "1"]      # el vigente conserva su número


def test_olas_serie_propia_por_area():
    reg = {"arranque": {"anio": 2026, "viento": 300, "olas": 10, "vigentes_viento": []}, "corridas": {}}
    olas4 = (DIR / "olas_4.txt").read_text(encoding="utf-8")   # avisos en Drake y Centro Oeste
    olas3 = (DIR / "olas_3.txt").read_text(encoding="utf-8")   # avisos en Drake y Centro Oeste
    olas1 = (DIR / "olas_1.txt").read_text(encoding="utf-8")   # sin avisos
    b1 = boletin("2026-11-26", "12", [aviso()], olas4)
    registro.numerar(CAT, b1, reg)
    es = render.generar(CAT, b1, "es")
    assert "AVISO DE OLAS 11: AREA PASAJE DE DRAKE" in es and "AVISO DE OLAS 12: AREA CENTRO OESTE" in es
    assert b1["avisos"][0]["numero"] == "301"                       # series separadas
    registro.registrar(CAT, b1, reg)
    b2 = boletin("2026-11-27", "00", [], olas3)
    registro.numerar(CAT, b2, reg)
    es = render.generar(CAT, b2, "es")
    assert "AVISO DE OLAS 11 ACTUALIZADO: AREA PASAJE DE DRAKE" in es
    assert "AVISO DE OLAS 12 ACTUALIZADO: AREA CENTRO OESTE" in es
    registro.registrar(CAT, b2, reg)
    b3 = boletin("2026-11-27", "12", [], olas1)
    registro.numerar(CAT, b3, reg)
    es = render.generar(CAT, b3, "es")
    assert "AVISO DE OLAS 11: CESE" in es and "AVISO DE OLAS 12: CESE" in es
