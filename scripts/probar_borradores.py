"""Prueba la interpretación del texto claro sobre borradores de pronosticadores.

Usa el intérprete configurado: por reglas (por defecto, sin IA) o con IA
(INTERPRETE=ia y ANTHROPIC_API_KEY definida).

Uso:
    python scripts/probar_borradores.py tests/borradores/*.docx
    python scripts/probar_borradores.py --fecha 2026-07-24 --corrida 12 tests/borradores/navegante_24-7.docx

Para cada borrador guarda en ./prueba_ia/ los datos interpretados y los
dos .txt, y muestra las dudas y los controles. Si existe
<borrador>_esperado_ia.json al lado del borrador, compara el boletín que
sale contra el esperado, línea por línea.
"""
import argparse
import datetime as dt
import difflib
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "app"))
from core import catalogo, interpretar, render, validar  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("archivos", nargs="+")
    ap.add_argument("--fecha", default=dt.date.today().isoformat())
    ap.add_argument("--corrida", default="12", choices=["00", "12"])
    args = ap.parse_args()
    cat = catalogo.cargar()
    salida = Path("prueba_ia")
    salida.mkdir(exist_ok=True)

    for ruta in map(Path, args.archivos):
        print("=" * 80, f"\n{ruta.name}\n" + "=" * 80)
        texto = interpretar.leer_archivo(ruta.read_bytes(), ruta.name)
        datos = interpretar.interpretar_texto(cat, texto)
        (salida / f"{ruta.stem}_datos.json").write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
        base = {"fecha": args.fecha, "corrida": args.corrida, "hielos": ""}
        b, dudas = interpretar.a_boletin(cat, datos, base)
        es, en = render.generar(cat, b, "es"), render.generar(cat, b, "en")
        (salida / f"{ruta.stem}_WWST01.txt").write_text(es, encoding="utf-8")
        (salida / f"{ruta.stem}_WWST02.txt").write_text(en, encoding="utf-8")
        print(es)
        print(f"\nINTERPRETACIÓN ({interpretar.motor()}) — DUDAS:")
        for d in dudas:
            print(f"  - {d.get('donde')}: {d.get('motivo')}")
        errores, advertencias = validar.validar(cat, b)
        print("ERRORES:", *[f"\n  - {e}" for e in errores] or [" ninguno"])
        print("ADVERTENCIAS:", *[f"\n  - {a}" for a in advertencias] or [" ninguna"])

        esperado = ruta.with_name(f"{ruta.stem}_esperado_ia.json")
        if esperado.exists():
            b2, _ = interpretar.a_boletin(cat, json.loads(esperado.read_text(encoding="utf-8")), base)
            es2 = render.generar(cat, b2, "es")
            diff = list(difflib.unified_diff(es2.splitlines(), es.splitlines(), "esperado", "ia", lineterm="", n=0))
            print("\nCOMPARACIÓN CON LO ESPERADO:", "idéntico" if not diff else "")
            for linea in diff[2:]:
                print("  " + linea)
        print()


if __name__ == "__main__":
    main()
