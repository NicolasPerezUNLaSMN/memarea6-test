"""Exportación a CSV para estadísticas y verificación."""
import csv
from pathlib import Path

from core import catalogo, estadisticas, interpretar, reglas, registro

CAT = catalogo.cargar()
DIR = Path(__file__).parent / "borradores"


def test_csv_de_avisos_y_pronosticos(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    texto = interpretar.leer_archivo((DIR / "navegantes_27-08-2022_12z.docx").read_bytes(), "x.docx")
    b, _ = interpretar.a_boletin(CAT, reglas.interpretar(CAT, texto), {"fecha": "2022-08-27", "corrida": "12"})
    b["olas"] = (DIR / "olas_4.txt").read_text(encoding="utf-8")
    registro.numerar(CAT, b, {"arranque": {}, "corridas": {}})
    ra, rp = estadisticas.exportar(CAT, b, autor="prueba")
    estadisticas.exportar(CAT, b, autor="prueba")              # misma corrida: no duplica
    avisos = list(csv.DictReader(ra.open(encoding="utf-8-sig"), delimiter=";"))
    pron = list(csv.DictReader(rp.open(encoding="utf-8-sig"), delimiter=";"))
    assert ra.name == "avisos_2022.csv" and rp.name == "pronosticos_2022.csv"
    assert [a["numero"] for a in avisos if a["serie"] == "temporal"] == ["392", "391", "390", "389"]
    assert {a["area_archivo_olas"] for a in avisos if a["serie"] == "olas"} == {"AREA DRAKE", "AREA CENTRO OESTE"}
    a392 = next(a for a in avisos if a["numero"] == "392")
    assert a392["fuerza_beaufort"] == "9" and a392["coordenadas"] == "35S-50S 40W-20W"
    assert len(pron) == 17                                       # 16 zonas, Área Norte en dos partes
    vald = next(p for p in pron if p["zona_id"] == "valdes")
    assert (vald["fuerza_min"], vald["fuerza_max"], vald["fuerza_max_periodo"]) == ("6", "7", "7")
    assert vald["direccion"] == "SECTOR S" and vald["direccion_final"] == "SECTOR W"
    assert vald["vis"] == "MUY_MALA" and vald["vis_hasta"] == "REGULAR" and vald["con_aviso_temporal"] == "390"
    drake = next(p for p in pron if p["zona_id"] == "drake")
    assert drake["con_aviso_olas"] == "si" and drake["autor"] == "prueba"
