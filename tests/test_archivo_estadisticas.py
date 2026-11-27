"""Archivo de boletines finales (sin borradores), estadísticas entre fechas y reglas de acceso."""
import datetime as dt
import json
from pathlib import Path

import pytest

from core import acceso, almacen, catalogo, estadisticas, interpretar, render, tablero

CAT = catalogo.cargar()
DIR = Path(__file__).parent / "borradores"


@pytest.fixture
def datos(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    return tmp_path


def emitir(nombre, fecha, autor):
    texto = interpretar.leer_archivo((DIR / nombre).read_bytes(), nombre)
    base = {"fecha": fecha, "corrida": "12", "hielos": "", "texto_claro": texto}
    b, _ = interpretar.a_boletin(CAT, interpretar.interpretar_texto(CAT, texto), base)
    for i, a in enumerate(b["avisos"]):          # sin registro: numeración a mano
        a["numero"] = a["numero"] or str(900 + i)
    textos = render.generar_todo(CAT, b)
    almacen.guardar(b, textos, autor)
    estadisticas.exportar(CAT, b, autor)
    return b, textos


def test_no_se_guarda_el_borrador(datos):
    b, textos = emitir("navegante_palavecino2.docx", "2026-11-27", "Palavecino")
    assert b["texto_claro"]                                         # en memoria sí estaba
    guardado = json.loads((datos / "boletines" / "20261127_12Z.json").read_text(encoding="utf-8"))
    assert "texto_claro" not in guardado and guardado["autor"] == "Palavecino"
    assert "texto_claro" not in almacen.cargar("20261127_12Z")
    t = almacen.textos("20261127_12Z")
    assert set(t) == {"es", "en", "navtex"}
    assert t["es"][1] == textos["es"] and t["es"][0].startswith("WWST01_SABM_")


def test_textos_retocados_reemplazan_los_generados(datos):
    b, textos = emitir("navegante_palavecino2.docx", "2026-11-27", "")
    almacen.guardar_textos(b, {**textos, "es": textos["es"] + "\nRETOCADO"})
    assert almacen.textos("20261127_12Z")["es"][1].endswith("RETOCADO")


def test_listar_entre_fechas(datos):
    emitir("navegante_palavecino2.docx", "2026-11-27", "")
    emitir("navegante_24-7.docx", "2026-07-24", "")
    assert almacen.listar_entre(dt.date(2026, 11, 1), dt.date(2026, 11, 30)) == ["20261127_12Z"]
    assert len(almacen.listar_entre(dt.date(2026, 1, 1), dt.date(2026, 12, 31))) == 2


def test_estadisticas_del_periodo(datos):
    emitir("navegante_palavecino2.docx", "2026-11-27", "Palavecino")
    emitir("navegante_01-07.docx", "2026-07-01", "Otro")
    r = tablero.calcular(dt.date(2026, 11, 27), dt.date(2026, 11, 27))
    assert r["boletines"] == 1 and r["fuerza_max"] == 8
    assert r["avisos_temporal"] == 3                         # 490, 491 y el nuevo; 489 es solo un cese
    assert list(r["por_autor"]["autor"]) == ["Palavecino"]
    zonas = r["por_zona"].set_index("zona_id")
    assert zonas.loc["norte", "fuerza_max"] == 8 and zonas.loc["rdp_int", "fuerza_max"] == 4
    assert "LLUVIAS" in set(r["fenomenos"]["fenomeno"])
    assert len(r["por_dia"]) == 1 and r["por_dia"]["avisos_temporal"].iloc[0] == 3

    todo = tablero.calcular(dt.date(2026, 1, 1), dt.date(2026, 12, 31))
    assert todo["boletines"] == 2 and set(todo["por_autor"]["autor"]) == {"Palavecino", "Otro"}
    assert tablero.calcular(dt.date(2025, 1, 1), dt.date(2025, 12, 31)) == {"vacio": True}


# ---------------------------------------------------------------- acceso
def test_sin_proveedores_no_hay_login():
    assert acceso.proveedores({}) == []
    assert acceso.proveedores({"auth": {"redirect_uri": "x", "cookie_secret": "y"}}) == []


def test_proveedores_microsoft_primero():
    s = {"auth": {"redirect_uri": "x", "google": {"client_id": "g"}, "microsoft": {"client_id": "m"}}}
    assert acceso.proveedores(s) == ["microsoft", "google"]


@pytest.mark.parametrize("correo,ok", [
    ("nperez@smn.gob.ar", True), ("NPerez@SMN.gob.ar", True), ("alguien@gmail.com", False),
    ("invitado@gmail.com", True), ("x@otro.smn.gob.ar", False), ("", False), ("sin-arroba", False),
])
def test_permitido(correo, ok):
    r = acceso.reglas({"acceso": {"dominios": ["@smn.gob.ar"], "correos": ["Invitado@gmail.com"]}})
    assert acceso.permitido(correo, r) is ok


def test_sin_reglas_entra_cualquiera():
    assert acceso.permitido("quien@sea.com", acceso.reglas({}))


def test_identidad_microsoft_sin_email():
    assert acceso.identidad({"name": "Ana Pérez", "preferred_username": "aperez@smn.gob.ar"}) == \
        ("Ana Pérez", "aperez@smn.gob.ar")
    assert acceso.identidad({"email": "b@smn.gob.ar"}) == ("b@smn.gob.ar", "b@smn.gob.ar")
