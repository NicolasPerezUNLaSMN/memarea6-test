"""Traducción con IA de los textos libres (opcional).

Solo se usa si está definida la variable ANTHROPIC_API_KEY. Todo lo demás
del boletín se genera sin IA, a partir del catálogo.
"""
import json
import os
import re

MODELO_DEFECTO = "claude-sonnet-5-5"


def disponible() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def _glosario(cat: dict) -> str:
    filas = []
    for seccion in ("lista", "probabilidad", "calificativo", "momento", "evolucion", "conector"):
        for v in cat["fenomenos"][seccion].values():
            if v.get("es"):
                filas.append(f"{v['es']} = {v['en']}")
    for v in cat["visibilidad"]["valores"].values():
        filas.append(f"VIS {v['es']} = VIS {v['en']}")
    filas += [f"{k} = {v}" for k, v in cat["abreviaturas_omm"].items()]
    return "\n".join(filas)


def traducir(cat: dict, textos: list[str]) -> dict[str, str]:
    if not textos:
        return {}
    from anthropic import Anthropic

    sistema = (
        "Sos traductor del Servicio Meteorológico Nacional de Argentina. Traducís fragmentos "
        "de boletines meteorológicos marinos (METAREA VI, NAVTEX) del castellano al inglés.\n"
        "Reglas:\n"
        "1. Estilo telegráfico de boletín marino, TODO EN MAYÚSCULAS, sin tildes ni puntuación extra.\n"
        "2. Usá las equivalencias y abreviaturas OMM del glosario; si un término está ahí, usalo tal cual.\n"
        "3. No agregues ni quites información. Coordenadas, horas (DD/HHMM) y números se copian igual.\n"
        "4. Los nombres propios de lugares quedan en castellano (ej. GOLFO DE SAN JORGE).\n"
        "5. Respondé SOLO con un objeto JSON {\"texto original\": \"TRADUCCION\"}, sin nada más.\n\n"
        f"GLOSARIO (castellano = inglés):\n{_glosario(cat)}"
    )
    cliente = Anthropic()
    resp = cliente.messages.create(
        model=os.getenv("CLAUDE_MODEL", MODELO_DEFECTO),
        max_tokens=2000,
        temperature=0,
        system=sistema,
        messages=[{"role": "user", "content": json.dumps(textos, ensure_ascii=False)}],
    )
    texto = "".join(getattr(b, "text", "") for b in resp.content)
    texto = re.sub(r"^```(json)?|```$", "", texto.strip(), flags=re.M).strip()
    datos = json.loads(texto)
    return {k: v for k, v in datos.items() if k in textos and isinstance(v, str)}
