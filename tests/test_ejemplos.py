"""Reproduce dos boletines reales emitidos (tests/ejemplos/) a partir de los
datos estructurados que cargaría el pronosticador.

Las únicas diferencias admitidas son correcciones de errores del sistema
anterior, listadas en CORRECCIONES con su motivo.
"""
from pathlib import Path

from core import catalogo, modelo, render, validar
from ayudas import C, COND, F, RESTO, SZ, V, W

CAT = catalogo.cargar()
EJ = Path(__file__).parent / "ejemplos"

HIELO_22 = ("221400 UTC 1.LIMITE DE HIELO MARINO 5429S 02000W 5346S 02618W 5648S 03218W 5818S 03758W 5942S 04317W "
            "6147S 04814W 6238S 05247W 6317S 05654W 6703S 06032W 6416S 06337W 6537S 06558W 6541S 06716W "
            "2.TEMPANOS MAYORES A 10MN A81 5419S 03451W 28X25MN D33B 5551S 03636W 21X12MN D35 6008S 04310W "
            "15X6 MN A83 5932S 04932W 12X7MN A85 5504S 04932W 10X3MN 3.TEMPANOS MENOR A 10MN D32 5648S 04021W "
            "9X6MN TEMPANO1 5551S 04207W 5X3MN TEMPANO2 5738S 04509W 6X2MN TEMPANO3 5916S 04053W 4X1MN TEMPANO4 "
            "6044S 05856W 4X1MN TEMPANO5 6138S 05337W 4X3MN TEMPANO6 5444S 04254W 6X2MN TEMPANO7 6136S 05350W "
            "5X3MN 4.AREA DE TEMPANOS A5430S 02000W 5000S 02000W 5000S 02700W 5430S 02700W B5430S 02700W 5000S "
            "02700W 4700S 04000W 5930S 04000W C5930S 04000W 4700S 04000W 5500S 05000W 6230S 05000W D6230S 05000W "
            "5500S 05000W 6000S 06716W 6630S 06716W")


def leer(nombre, correcciones):
    txt = (EJ / nombre).read_text(encoding="utf-8")
    for viejo, nuevo in correcciones:
        assert viejo in txt, viejo
        txt = txt.replace(viejo, nuevo)
    es, en = txt.split("%\n\n")
    # El sistema anterior dejaba un renglón en blanco antes del pie en
    # castellano pero no en inglés; ahora se deja en los dos.
    if "\n\n-----" not in en:
        en = en.replace("\n-----", "\n\n-----", 1)
    return es, en


def sistema(tipo, pos, presion="", mov="", evol=(), exp_pos="", exp_hora="", ext_tipo="", ext_pos="", ext_mov=""):
    s = modelo.nuevo_sistema()
    s.update(tipo=tipo, pos=pos, presion=presion, mov=mov, evol=list(evol), exp_pos=exp_pos,
             exp_hora=exp_hora, ext_tipo=ext_tipo, ext_pos=ext_pos, ext_mov=ext_mov)
    return s


def aviso(n, causa, dir, desde, detalle="", verbo="futuro", zonas=(), coords=""):
    a = modelo.nuevo_aviso()
    a.update(numero=n, causa=causa, dir=dir, desde=desde, detalle=detalle, verbo=verbo,
             zonas=list(zonas), coords=coords)
    return a


def boletin(fecha, corrida, zonas, avisos, sinopsis, hielos):
    b = modelo.nuevo_boletin(CAT)
    b.update(fecha=fecha, corrida=corrida, avisos=avisos, sinopsis=sinopsis, hielos=hielos)
    for zid in b["zonas"]:
        b["zonas"][zid] = {"incluir": zid in zonas, "subzonas": zonas.get(zid, [SZ(W(""), [], V(""))])}
    return b


# ---------------------------------------------------------------- navegante (1)
CORRECCIONES_1 = [
    ("24-1--2026", "24-11-2026"),                 # fecha de validez truncada
    ("2026-1--24", "2026-11-24"),
    ("LUEGOPROB", "LUEGO PROB"),                  # falta un espacio
    ("PROB OFISOL", "PROB OF ISOL"),
    ("E DE 30 -", "E DE 30W -"),                  # longitud sin W
    ("E OF 30 -", "E OF 30W -"),
    ("NIGTH", "NIGHT"),                           # errata
    ("WEATHER NEXT RAIN", "WEATHER NXT RAIN"),    # LUEGO = NXT (OMM), unificado
    ("12:00 UTC  23,", "12:00 UTC 23,"),          # doble espacio (otros boletines tienen uno solo)
]


def test_navegante_1():
    def Z1(*a, **k):
        return [SZ(*a, **k)]

    raf = lambda d, f="", h="": C("BACK", d, f, "CON", h)
    zonas = {
        "rdp_int": Z1(W("VRB", "4", cambios=[C("BACK", "SECTOR W")]),
                      [F("NEBLINAS", prob="", evol="DISIPANDOSE"), F("LLUVIAS", cal="AISLADAS", mom="DESDE_MADRUGADA")],
                      V("BUENA", "REGULAR")),
        "rdp_ext": Z1(W("SECTOR N", "5", "CON", cambios=[raf("SECTOR W")]),
                      [F("LLUVIAS", cal="AISLADAS", mom="DESDE_MADRUGADA")], V("BUENA", "REGULAR")),
        "uruguay": Z1(W("SECTOR N", "4", cambios=[C("BACK", "SECTOR W")]),
                      [F("LLUVIAS", "TORMENTAS", cal="AISLADAS", mom="FINAL_PERIODO")], V("BUENA", "REGULAR", "MALA")),
        "mdp": Z1(W("SECTOR N", "4", cambios=[C("BACK", "SECTOR S", tempo=True)]),
                  [F("LLUVIAS", "TORMENTAS", cal="AISLADAS", mom="DESDE_TARDE", evol="MEJ_TEMP")], V("REGULAR", ocnl="MALA")),
        "bblanca": Z1(W("SECTOR N", "5", "CON", cambios=[raf("SECTOR S", "5/6", "24/0900")]),
                      [F("LLUVIAS", "TORMENTAS", cal="AISLADAS", mom="DESDE_NOCHE")], V("REGULAR", "MALA")),
        "valdes": Z1(W("SECTOR S", "5", "CON", cambios=[C("INCR", "", "6/8", "CON", "24/0600")]),
                     [F("SH", "LLUVIAS", mom="DESDE_NOCHE")], V("REGULAR", "MALA")),
        "sanjorge": Z1(W("SECTOR S", "6/5", "CON", cambios=[raf("SECTOR S", "7/8", "24/0000")]),
                       [F("SH", "LLUVIAS", mom="DESDE_NOCHE")], V("REGULAR", "MALA")),
        "patsur": Z1(W("SECTOR W", "5", "CON", cambios=[C("VEER", "SECTOR N"), raf("SECTOR S", "7/8", "24/0300")]),
                     [F("SH", "LLUVIAS", mom="DESDE_TARDE")], V("REGULAR", "MALA")),
        "findm": Z1(W("SECTOR W", "5/6", "CON", cambios=[C("INCR", "SECTOR S", "7/8", "CON", "24/0600")]),
                    [F("LLUVIAS", cal="AISLADAS", evol="MEJ_TEMP"), F("AGUANIEVE", prob="", mom="DESDE_NOCHE", con="LUEGO")],
                    V("REGULAR", "MALA")),
        "malvinas": Z1(W("SW", "5/6", "CON"), [F("SH", "LLUVIAS", cal="AISLADAS", evol="MEJ_TEMP")], V("REGULAR")),
        "norte": Z1(W("SECTOR W", "5/6", "CON"), [F("SH", "LLUVIAS", prob="BAJA", cal="AISLADAS")], V("REGULAR")),
        "cestre": [SZ(W("SECTOR E", "7", "CON", cambios=[raf("SECTOR W", "6")]), [F("SH", "LLUVIAS", cal="INTERMITENTES")],
                      V("MALA", "REGULAR"), div=COND(("E", "30W"), ("S", "45S"))),
                   SZ(W("SECTOR W", "6", "CON"), [F("SH", "LLUVIAS", cal="INTERMITENTES")], V("REGULAR"), div=RESTO)],
        "coeste": Z1(W("SECTOR W", "6", "CON"), [F("SH", "LLUVIAS", evol="MEJ_TEMP")], V("REGULAR", ocnl="MALA")),
        "sudeste": [SZ(W("SECTOR N", "5", "CON", cambios=[raf("SECTOR S", "6")]),
                       [F("SH", "LLUVIAS"), F("AGUANIEVE", mom="DESDE_NOCHE", con="LUEGO")], V("REGULAR", ocnl="MALA"),
                       div=COND(("S", "55S"))),
                    SZ(W("SECTOR N", "6/7", "CON", cambios=[raf("SECTOR W")]), [F("SH", "LLUVIAS", cal="AISLADAS")],
                       V("REGULAR", ocnl="MALA"), div=RESTO)],
        "sudoeste": [SZ(W("SECTOR S", "5/6", "CON"), [F("LLUVIAS", "NEVADAS", cal="AISLADAS")], V("REGULAR"),
                        div=COND(("E", "50W"))),
                     SZ(W("SECTOR S", "5", "CON", cambios=[C("VEER", "SECTOR N", "", "CON")]),
                        [F("SH", "LLUVIAS", cal="AISLADAS")], V("REGULAR"), div=RESTO)],
        "drake": Z1(W("SECTOR W", "5", "CON", cambios=[C("VEER", "SECTOR N", "6", "CON", tempo=True)]),
                    [F("LLUVIAS", "NEVADAS", cal="AISLADAS", evol="MEJ_TEMP")], V("REGULAR")),
    }
    avisos = [aviso("483", "CFNT", "SECTOR S", "24/0000", detalle="49S 66W 43S 65W",
                    zonas=["valdes", "sanjorge", "patsur", "findm"])]
    sinopsis = [
        sistema("CFNT", "51S 53W 39S 62W", mov="MOV E", evol=["WKN"]),
        sistema("DEPRESION", "47S 28W", "989", "MOV S", ["DPN"], "56S 27W", "24/1200", "OFNT", "46S 25W 47S 35W", "MOV S"),
        sistema("DEPRESION", "48S 42W", "985", "MOV SE", ["WKN"], ext_tipo="OFNT", ext_pos="51S 36W 55S 44W 49S 46W", ext_mov="MOV S"),
        sistema("ESTACIONARIO", "28S 56W 30S 46W"),
    ]
    b = boletin("2026-11-23", "12", zonas, avisos, sinopsis, HIELO_22)
    es, en = leer("navegante_1.txt", CORRECCIONES_1)
    assert render.generar(CAT, b, "es") == es
    assert render.generar(CAT, b, "en") == en
    errores, _ = validar.validar(CAT, b)
    assert errores == []


# ---------------------------------------------------------------- navegante (3)
CORRECCIONES_3 = [
    ("25-1-2026", "25-11-2026"),
    ("2026-1--25", "2026-11-25"),
    ("BARICO SOBRE PROVOCA", "BARICO PROVOCA"),   # "SOBRE" quedaba colgado
    ("GRADIENT ON ", "GRADIENT "),
    ("STORMS NEXT SH", "STORMS NXT SH"),
]


def test_navegante_3():
    def Z1(*a, **k):
        return [SZ(*a, **k)]

    back = lambda f, raf, h, n="": C("BACK", "SECTOR S", f, raf, h, raf_int=n)
    zonas = {
        "rdp_int": Z1(W("SECTOR W", "3/4", cambios=[back("5/6", "CON", "24/2100")]), [F("SH", mom="DESDE_TARDE")], V("BUENA", "REGULAR")),
        "rdp_ext": Z1(W("SECTOR W", "4", cambios=[back("6/7", "CON", "24/2100")]), [F("SH")], V("BUENA", "REGULAR")),
        "uruguay": Z1(W("SECTOR W", "4", cambios=[back("6/7", "INT", "24/2100", "8")]), [F("SH", mom="DESDE_TARDE")], V("BUENA", "REGULAR")),
        "mdp": Z1(W("SECTOR W", "4", cambios=[back("6/7", "INT", "24/1800", "8")]),
                  [F("TORMENTAS", cal="AISLADAS"), F("SH", prob="", con="LUEGO")], V("REGULAR", ocnl="MALA")),
        "bblanca": Z1(W("SECTOR W", "4", cambios=[back("6/7", "INT", "24/1800", "8")]),
                      [F("SH", prob="BAJA", evol="MEJORANDO", mom="DURANTE_TARDE")], V("REGULAR")),
    }
    avisos = [
        aviso("485", "GRADIENTE", "SECTOR S", "24/1800", coords="40S-50S 50W-60W"),
        aviso("484", "GRADIENTE", "SECTOR W", "24/1200", zonas=["drake"]),
        aviso("483", "GRADIENTE", "SECTOR S", "24/0000", verbo="presente", zonas=["valdes", "sanjorge", "patsur", "findm"]),
    ]
    hielos = next(l for l in leer("navegante_3.txt", CORRECCIONES_3)[0].split("\n") if "LIMITE DE HIELO" in l)
    sinopsis = [
        sistema("DEPRESION", "47S 55W", "993", "MOV E", ["DPN"], ext_tipo="CFNT", ext_pos="47S 55W 40S 54W 37S 57W", ext_mov="MOV NE"),
        sistema("ANTICICLON", "40S 66W", "1011", "MOV NE", ["WKN"]),
        sistema("CFNT", "59S 67W 55S 66W 50S 68W", mov="MOV NE"),
        sistema("DEPRESION", "54S 40W", "984", "MOV E", ["WKN"]),
    ]
    b = boletin("2026-11-24", "00", zonas, avisos, sinopsis, hielos)
    es, en = leer("navegante_3.txt", CORRECCIONES_3)
    assert render.generar(CAT, b, "es") == es
    assert render.generar(CAT, b, "en") == en
    errores, advertencias = validar.validar(CAT, b)
    assert errores == []
    assert any("no incluidas" in a for a in advertencias)


# ---------------------------------------------------------------- validaciones
def test_validacion_detecta_faltantes():
    b = modelo.nuevo_boletin(CAT)
    errores, _ = validar.validar(CAT, b)
    assert any("dirección del viento" in e for e in errores)
    assert any("visibilidad" in e for e in errores)
    assert any("fenómeno" in e for e in errores)


def test_texto_libre_sin_traducir():
    b = modelo.nuevo_boletin(CAT)
    sz = b["zonas"]["rdp_int"]["subzonas"][0]
    sz["obs"] = "oleaje de 2 metros"
    assert "[TRADUCIR: OLEAJE DE 2 METROS]" in render.generar(CAT, b, "en")
    b["traducciones"]["OLEAJE DE 2 METROS"] = "WAVES 2 METERS"
    assert "WAVES 2 METERS" in render.generar(CAT, b, "en")
