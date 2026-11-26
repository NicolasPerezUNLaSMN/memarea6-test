# meMareaVI — contexto para Claude Code

App interna del Servicio Meteorológico Nacional (SMN, Argentina) que arma el
Boletín Meteorológico para Navegantes del METAREA VI a partir del borrador en
texto claro que escribe el pronosticador. Genera WWST01 (castellano),
WWST02 (inglés) y WWST03 (NAVTEX, inglés). Reemplaza a un formulario PHP viejo.

Todo el proyecto (código, comentarios, mensajes, commits) está en castellano
rioplatense. Respondé en castellano.

## Comandos

```bash
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt pytest
pytest tests                       # tienen que pasar todos antes de cualquier commit
streamlit run app/app.py           # app local en http://localhost:8501
python scripts/probar_borradores.py --fecha 2026-07-24 tests/borradores/navegante_24-7.docx
docker compose up -d --build       # como corre en el servidor del SMN
```

## Arquitectura

Texto claro → interpretación (reglas, sin IA) → datos del boletín → controles → generación con reglas fijas.

| Archivo | Qué hace |
| --- | --- |
| `app/app.py` | Interfaz Streamlit (solo muestra y conecta; no tiene lógica de contenido) |
| `app/core/reglas.py` | Intérprete del texto claro sin IA. Tablas al principio: ABREVIATURAS, PRE_ERRATAS, ERRATAS, FENOMENOS, MOMENTOS, EVOLUCIONES… |
| `app/core/interpretar.py` | Lee Word (con resaltado = NAVTEX), PDF y .txt; modo IA opcional; `a_boletin()` arma el boletín desde los datos |
| `app/core/render.py` | Arma WWST01/02/03, hielos y avisos de olas |
| `app/core/validar.py` | Errores (bloquean la descarga) y advertencias |
| `app/core/registro.py` | Numeración de avisos: temporal correlativo anual, olas serie propia, reinicio el 1 de enero |
| `app/core/olas.py` | Lee el archivo de olas (BOL_METAREA_VI_ING), solo líneas WARNING |
| `app/core/mapa.py` | Mapa SVG de zonas en aviso |
| `app/core/estadisticas.py` | CSV para estadísticas y verificación |
| `app/config/catalogo.yaml` | Todo el vocabulario, traducciones, zonas, estaciones NAVTEX, geometría del mapa |

## Reglas del proyecto

- **El texto del boletín sale del catálogo, nunca escrito a mano en el código.** Un término nuevo o una traducción van en `catalogo.yaml`.
- **El intérprete no inventa.** Lo que no reconoce se omite y se informa como «duda».
- **Una forma nueva de escribir de los pronosticadores** se suma a las tablas de `reglas.py`, con un caso en `tests/`.
- **Los tests reproducen boletines reales** (`tests/ejemplos/`, `tests/borradores/`). Si un cambio rompe esa reproducción, es una regresión salvo que se decida otra cosa explícitamente.
- Los datos viven en `DATA_DIR` (en Docker, `/data`): historial, `registro_avisos.json`, `estadisticas/*.csv`. No hay base de datos y corre una sola instancia.
- `tests/borradores/` tiene borradores reales con nombres de pronosticadores: el repo tiene que ser privado.

## Pendiente

- Envío por FTP a la web del SMN, INTRAMET y el envío internacional (enganche: `generar_salida()` en `app.py`; propuesta: `core/envio.py` + botón «Enviar»).
- Confirmar con pronóstico los puntos marcados `REVISAR` en `catalogo.yaml` (escala de viento, estaciones NAVTEX, redacción de avisos de olas, inglés).
