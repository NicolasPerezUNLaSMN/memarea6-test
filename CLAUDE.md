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
docker compose up -d --build       # solo si algún día hay servidor (hoy no se usa)
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
| `app/core/tablero.py` | Resumen de estadísticas entre fechas (pestaña «Estadísticas») |
| `app/core/almacen.py` | Archivo de boletines finales (sin borradores) |
| `app/core/acceso.py` | Ingreso con Microsoft/Google y quién puede entrar |
| `app/core/palabras.py` | Palabras habilitadas (`config/palabras_habilitadas.yaml`) |
| `app/config/catalogo.yaml` | Todo el vocabulario, traducciones, zonas, estaciones NAVTEX, geometría del mapa |

## Reglas del proyecto

- **El texto del boletín sale del catálogo, nunca escrito a mano en el código.** Un término nuevo o una traducción van en `catalogo.yaml`.
- **El intérprete no inventa.** Lo que no reconoce se omite y se informa como «duda».
- **Una forma nueva de escribir de los pronosticadores** se suma a las tablas de `reglas.py`, con un caso en `tests/`.
- **Los tests reproducen boletines reales** (`tests/ejemplos/`, `tests/borradores/`). Si un cambio rompe esa reproducción, es una regresión salvo que se decida otra cosa explícitamente.
- Los datos viven en `DATA_DIR` (por defecto `./data`): archivo de boletines, `registro_avisos.json`, `estadisticas/*.csv`. No hay base de datos y corre una sola instancia.
- `tests/borradores/` tiene borradores reales con nombres de pronosticadores: el repo tiene que ser privado.

## Decisiones ya tomadas (no volver a discutirlas sin pedido explícito)

- **Sin IA por defecto.** El texto claro se interpreta con reglas (`INTERPRETE=reglas`). El modo IA existe pero está apagado.
- **Entrada libre.** El pronosticador escribe como siempre (Word, PDF, .txt o en pantalla); el formulario quedó solo como «Ajuste fino».
- **Numeración**: temporal correlativo anual como el sistema viejo; olas con serie propia («AVISO DE OLAS N»), numeradas solas por área; las dos series vuelven a 1 el 1 de enero. Un aviso nuevo sin número toma el siguiente; «actualizar N» conserva el número.
- **Olas**: solo las líneas WARNING. Áreas A–G del archivo = Mar del Plata, Bahía Blanca, Península Valdés, Golfo San Jorge, Patagonia Sur, Fin del Mundo, Malvinas (mapa de referencia del SMN). Zona 1–5, Weddell y Bellingshausen son subáreas antárticas fuera del boletín (destildadas por defecto).
- **Inglés**: estilo de boletín marino, no literal (GUSTS FORCE 8, STRONG PRESSURE GRADIENT WILL CAUSE, TEMPORARY IMPROVEMENTS, SLEET, TSTM, FROM AFTERNOON, «RAIN AND TSTM»).
- **Formato**: replica los boletines emitidos (renglones en blanco, encabezado partido). Errores del sistema viejo corregidos a propósito (fechas truncadas, «SOBRE» colgado, NIGTH, LUEGOPROB…).
- **Estadísticas**: CSV por año en `DATA_DIR/estadisticas/`, sin base de datos; la pestaña «Estadísticas» los resume entre fechas (`core/tablero.py`).
- **Archivo**: se guardan solo los boletines finales (WWST01/02/03 + datos .json), nunca el borrador en texto claro (`almacen.NO_SE_GUARDA`).
- **Vocabulario**: las formas nuevas (tablas de `reglas.py`, catálogo, `palabras_habilitadas.yaml`) las agrega el equipo de desarrollo, con test. Los pronosticadores solo consultan la lista desde la app.
- **Ingreso**: login nativo de Streamlit con Microsoft y/o Google (`core/acceso.py`), activo solo si hay `.streamlit/secrets.toml`; acceso limitado por dominio/correo en `[acceso]`.
- **Dónde corre**: no hay servidor del SMN ni está previsto por ahora. Corre en la máquina personal del desarrollador (`streamlit run`, datos en `./data`) y en Streamlit Cloud (repo personal `memarea6-test`, se actualiza con cada push a `master`; su `data/` se borra en cada reinicio, solo para pruebas). `Dockerfile` y `docker-compose.yml` quedan para un eventual servidor; no proponer pasos de despliegue en servidor.

## Documentación

- `README.md`: uso, instalación y funcionamiento.
- Documento funcional con diagramas: «meMareaVI — Documentación del sistema» (Claude Doc).

## Pendiente

- Envío por FTP a la web del SMN, INTRAMET y el envío internacional (enganche: `generar_salida()` en `app.py`; propuesta: `core/envio.py` + botón «Enviar»).
- Confirmar con pronóstico los puntos marcados `REVISAR` en `catalogo.yaml` (escala de viento, estaciones NAVTEX, redacción de avisos de olas, inglés).
