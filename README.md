# meMareaVI

<img src="app/static/logo.svg" width="96" alt="meMareaVI">

Boletín meteorológico para navegantes · METAREA VI

App web interna para que los pronosticadores escriban el boletín METAREA VI
en texto claro, como hoy, y obtengan los dos textos de difusión:

- `WWST01_SABM_DDHHMM.txt` en castellano
- `WWST02_SABM_DDHHMM.txt` en inglés

## Cómo funciona

1. El pronosticador arrastra su Word (o .txt) o escribe en la página, con su
   estilo de siempre: «Regulares a fuertes del sector W con ráfagas…».
2. El texto se **interpreta** a datos (dirección, fuerza, cambios, fenómenos,
   visibilidad, subdivisiones, avisos, sinopsis). Entiende las copias entre
   zonas («(copiar)» / «usar copia»), «oca», «sentido horario», «sin proba»,
   coordenadas «38-44», horas «el 25 a las 9», etc.
3. El **código** arma los dos .txt con reglas fijas a partir de esos datos y de
   `app/config/catalogo.yaml`.
4. Se muestra lo que hay que revisar (lo que no se reconoció, copias,
   suposiciones) y los controles automáticos. Para corregir: se edita el texto
   y se vuelve a interpretar, o se ajusta el dato en «Ajuste fino». Las
   descargas se habilitan cuando no hay errores.

### Dos formas de interpretar el texto (variable `INTERPRETE`)

- **`reglas`** (por defecto): sin IA, gratis y todo local. Reconoce las formas
  de escribir de los borradores reales de varios pronosticadores
  (`tests/borradores/`): oraciones completas, estilo telegráfico sin
  puntuación, abreviaturas (MOD, REG, MF, TEMP, SEC, RAF, CAMB, ANTIH, DD VAR,
  PROBA, VISI, OCA, FGB, FF, FO, CPF, SPF…), un renglón por elemento, PDF,
  «IDEM», copias, cuadrantes («NE del área»), coordenadas «38-44», «55/47»,
  «5126», «36S34W» y horas «el 25 a las 9», «14/1800», «9/00», «01 09Z»
  (`app/core/reglas.py`). Lo que no
  reconoce no lo inventa: lo informa para revisar. Si aparecen formas nuevas
  de escribir, se agregan a las tablas del principio de ese archivo.
- **`ia`**: con Claude (requiere `ANTHROPIC_API_KEY`, con costo por uso). Más
  tolerante a redacciones imprevistas. Devuelve los mismos datos, así que el
  resto de la app no cambia.

En los dos casos el boletín lo arma el código, no la IA.

### Palabras de fuerza del viento

Los pronosticadores escriben «leves, moderados, regulares, fuertes, muy
fuertes, temporal, temporal fuerte». La conversión a Beaufort está en el
catálogo (`viento.escala`) y es **tentativa**: hay que confirmarla con el área
de pronóstico y poner `confirmada: true`. Hasta entonces la app lo advierte en
cada boletín.

## Puesta en marcha

Requiere Docker con Docker Compose.

```bash
cp .env.example .env        # completar si se quiere IA
docker compose up -d --build
```

Queda en `http://<servidor>:8501`.

La app **no tiene usuarios ni contraseñas**: publicarla solo en la intranet,
o detrás del proxy inverso / SSO que ya usen.

## Boletín NAVTEX (WWST03)

Además de WWST01 y WWST02, la app arma el boletín para estaciones NAVTEX en
inglés, con el formato del WWST03 emitido (renglón en blanco entre líneas,
líneas de hasta 80 caracteres). Lleva:

- los avisos y sistemas marcados para NAVTEX. Se toman del borrador si dice
  «NAVTEX» al principio o «(NAVTEX)» al final, si está **resaltado en el Word**,
  o si se repite en una sección «NAVTEX» al final. Se pueden tildar o destildar
  en la pestaña «WWST03 · NAVTEX» del resultado;
- el pronóstico de las costas agrupado por estación (Buenos Aires, Mar del
  Plata, Bahía Blanca, Comodoro Rivadavia, Río Gallegos, Ushuaia). Qué zonas
  cubre cada estación está en `navtex.estaciones` del catálogo (REVISAR).

## Posiciones en la sinopsis

No siempre se ponen posiciones iniciales ni finales: la app no lo exige. Solo
advierte (sin bloquear) si una posición escrita tiene un formato raro.

## Hielos

Se adjunta el archivo del Servicio de Hidrografía Naval (por ejemplo
`NAVAREAVI_20260922_SMN.txt`, que trae el informe en inglés y en castellano)
o se pega el texto. Cada idioma del boletín toma su bloque, en una sola línea,
sin el título (se conserva la hora) y sin el pedido final de informar
témpanos. Si se pega solo el castellano, el inglés se arma por reemplazos.

## Avisos de olas

Se adjunta el archivo de olas (`BOL_METAREA_VI_ING…txt`) o se pega su texto.
La app toma **solo las líneas `WARNING:`** (no «IN THE REST» ni los períodos
sin aviso), las lista con una casilla cada una para destildar las que no van,
y las ubica debajo de los avisos de temporal, en castellano y en inglés:

    AVISO DE OLAS:
    AREA PASAJE DE DRAKE (55S- 60S Y 60W- 67W) 15/0900-15/2100 UTC: EN EL S 5.0/6.0M DECRECIENDO, DESPLAZANDOSE AL NE

Las áreas del archivo que coinciden con las del boletín (Norte, Centro Este,
Centro Oeste, Sur Este, Sur Oeste, Drake) salen con su nombre oficial; las
demás (A…G, ZONA 1…5, Mar de Weddell) con el nombre del archivo, y la app lo
advierte. Avisa también si la fecha del archivo no corresponde al boletín.
Título, forma de la línea y traducciones están en `olas` del catálogo (REVISAR:
no había boletines emitidos con avisos de olas para tomar como modelo).

## Formato del texto

Replica los boletines emitidos: encabezado en varias líneas, dos renglones en
blanco antes de la 2.ª y la 3.ª parte, uno antes de «AREAS OCEANICAS» y uno
antes del pie. Se ajusta en `encabezado.renglones_en_blanco` del catálogo.
Los caracteres de control SOH/ETX que agregaba el sistema anterior están
desactivados (`encabezado.caracteres_control`).

## Uso diario (pronosticador)

1. Elegir fecha y corrida en la barra lateral (o **Partir del último
   boletín**, que trae el texto anterior para editarlo y avanza la corrida).
2. Arrastrar el Word o escribir el texto, y pegar el bloque de hielos.
3. **Interpretar y generar**. Revisar dudas y controles, y descargar.

Cada boletín generado queda guardado en `./data/boletines/` (texto claro y
datos en `.json`, y los tres `.txt`).

## Probar la interpretación con borradores reales

```bash
python scripts/probar_borradores.py --fecha 2026-07-24 --corrida 12 tests/borradores/navegante_24-7.docx
python scripts/probar_borradores.py tests/borradores/*.docx
```

Usa el intérprete configurado en `INTERPRETE`. Guarda en `./prueba_ia/` los datos interpretados y los .txt, muestra dudas y
controles, y si hay un `<borrador>_esperado_ia.json` compara contra él línea
por línea. Conviene correrlo con varios borradores reales antes de poner la
app en uso, y cada vez que se cambie el modelo o las instrucciones.

## Controles automáticos

Antes de generar, la app bloquea si falta viento, fenómenos o visibilidad en
alguna zona, o si hay formatos inválidos (fuerza Beaufort, horas `DD/HHMM`,
latitudes y longitudes, posiciones de la sinopsis). Además advierte, sin
bloquear, sobre:

- zonas no incluidas;
- zonas con aviso de temporal cuyo pronóstico no llega a esa fuerza, y zonas
  con fuerza 8 o más que ningún aviso nombra;
- horas fuera del período de validez;
- palabras en castellano que quedaron en el bloque de hielos traducido;
- textos libres sin traducir.

## Cambiar vocabulario o textos fijos

Todo está en `app/config/catalogo.yaml` (zonas, direcciones, fenómenos,
visibilidad, causas de avisos, sistemas de la sinopsis, encabezados y
reemplazos para los hielos). Con docker compose el archivo está montado:
editarlo y reiniciar con `docker compose restart`.

Después de cambiar el catálogo, correr los tests (ver abajo): reproducen dos
boletines reales y avisan si un cambio altera el formato.

## Tests

```bash
pip install -r requirements.txt pytest
pytest tests
```

`tests/test_reglas.py` interpreta sin IA los cuatro borradores reales de
`tests/borradores/` y verifica el resultado.

`tests/test_interpretar.py` prueba todo lo que pasa después de la interpretación (escala
de viento, copias entre zonas, armado del boletín) con la respuesta esperada
para el borrador real del 24/7. No llama a la IA.

`tests/test_ejemplos.py` vuelve a generar los boletines reales del 23/11 12 UTC
y del 24/11 00 UTC (en `tests/ejemplos/`) a partir de datos estructurados y
compara el texto completo, carácter por carácter. Las únicas diferencias
aceptadas son las correcciones listadas abajo.

## Diferencias con los boletines anteriores

Correcciones de errores del sistema anterior:

- Fecha de validez truncada (`24-1--2026`, `2026-1--24`) → `24-11-2026`, `2026-11-24`.
- «FUERTE GRADIENTE BARICO SOBRE PROVOCARA…»: se quita el «SOBRE» / «ON» colgado.
- Espacios faltantes (`LUEGOPROB`, `PROB OFISOL`), errata `NIGTH` y longitud sin `W` (`E DE 30`).
- «LUEGO» se traduce siempre `NXT` (abreviatura OMM); antes alternaba NXT y NEXT.
- Encabezado de hielos en inglés con texto sobrante (`EA ICE AND ICEBERGS`).

Decisiones a confirmar con el área de pronóstico (marcadas `REVISAR` en el catálogo):

- «A PARTIR DE LA MAÑANA» se traduce `STARTING MORNING` (antes `EARLY MORNING`, igual que «madrugada»).
- «TARDE» se sigue traduciendo `EVENING`; la OMM usa *afternoon* para tarde.
- «TORMENTAS» se sigue traduciendo `STORMS`; la abreviatura OMM es `TSTM`.
- «RAFAGAS CON INTENSIDAD 8» se sigue traduciendo `GUST WITH 8 INTENSITY`.
- La tabla de palabras de viento → Beaufort (ver arriba).
- Textos de avisos actualizados, cesados y fuera del área, y «HASTA EL».
- Fenómenos nuevos vistos en los borradores: chaparrones de nieve y de
  granizo, bancos de niebla, «desmejorando con probabilidad de», ciclogénesis.
