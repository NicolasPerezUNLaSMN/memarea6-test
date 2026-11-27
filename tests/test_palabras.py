"""La lista de palabras habilitadas tiene que coincidir con lo que entiende el intérprete."""
import pytest

from core import palabras, reglas

SECCIONES = palabras.cargar()
INTENSIDADES = [(forma, fila["clave"]) for s in SECCIONES for fila in s["filas"] if fila.get("clave")
                for forma in palabras.formas(fila)]


def test_hay_las_ocho_intensidades():
    claves = [c for _, c in INTENSIDADES]
    for clave in ("LEVES", "MODERADOS", "REGULARES", "FUERTES", "MUY_FUERTES", "TEMPORAL", "TEMPORAL_FUERTE",
                  "TEMPORAL_MUY_FUERTE"):
        assert clave in claves


@pytest.mark.parametrize("forma,clave", INTENSIDADES)
def test_cada_intensidad_se_entiende(forma, clave):
    texto = reglas.normalizar(f"{forma} sector n con r")
    v, _ = reglas.viento(texto, [], "")
    assert v["fuerza"] == [clave], texto
    assert v["dir"] == "SECTOR N" and v["rafagas"] == "CON"


@pytest.mark.parametrize("escrito,esperado", [
    ("VIS B", ("BUENA", "", "")), ("VIS R", ("REGULAR", "", "")), ("VIS M", ("MALA", "", "")),
    ("VIS MM", ("MUY_MALA", "", "")), ("VIS R A M", ("REGULAR", "MALA", "")), ("VIS B OC R", ("BUENA", "", "REGULAR")),
])
def test_visibilidad_con_letras(escrito, esperado):
    v = reglas.visibilidad(reglas.normalizar(escrito))
    assert (v["v1"], v["hasta"], v["ocnl"]) == esperado


@pytest.mark.parametrize("escrito,dir_", [
    ("R DE DIR VARIABLES CON R", "VRB"), ("MF SECTOR O CON R", "SECTOR W"), ("T SW CON R", "SW"),
])
def test_direcciones(escrito, dir_):
    v, _ = reglas.viento(reglas.normalizar(escrito), [], "")
    assert v["dir"] == dir_


def test_rafagas_de_temporal_con_letras():
    v, _ = reglas.viento(reglas.normalizar("MF SECTOR W CON R DE T"), [], "")
    assert (v["fuerza"], v["raf_int"]) == (["MUY_FUERTES"], "TEMPORAL")


def test_varios_sistemas_en_un_renglon():
    l = reglas.normalizar("ANTICICLON 1022 EN 32-45, SE MUEVE AL E, SIN CAMBIOS, SIN POS FINAL FF 53/38 40/46, SE MUEVE AL ESTE")
    assert [p.split()[0] for p in reglas.separar_sistemas(l)] == ["anticiclon", "frente"]
    # un frente asociado queda con su sistema
    for unido in ("depresion 1000 en 50/40 extiende un frente frio en 48/42 41/51",
                  "depresion 1000 en 50/40 con frente frio en 48/42",
                  "depresion 1000 en 50/40 frente frio asociado 48/42"):
        assert len(reglas.separar_sistemas(unido)) == 1, unido


def test_descargas():
    md, csv_ = palabras.a_markdown(SECCIONES), palabras.a_csv(SECCIONES)
    for s in SECCIONES:
        assert f"## {s['titulo']}" in md and s["titulo"] in csv_
    assert "temporal muy fuerte · TMF" in md


def test_buscar():
    r = palabras.filtrar(SECCIONES, "tmf")
    assert [s["titulo"] for s in r] == ["Intensidad del viento"] and len(r[0]["filas"]) == 1
    assert palabras.filtrar(SECCIONES, "") == SECCIONES
