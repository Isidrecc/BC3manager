# Arquitectura de BC3Manager

> Qué es cada pieza del programa y cómo viaja un archivo BC3 por dentro.
> Para la referencia detallada de operaciones y endpoints, ver [api-interna.md](api-interna.md).
> Para el formato BC3 y las rarezas de Presto, ver [formato-bc3.md](formato-bc3.md).

## Qué es este proyecto

Herramienta local para ver, editar e imprimir presupuestos de obra en formato BC3 (FIEBDC-3), el estándar de intercambio que usan Presto, Arquímedes, Menfis y demás programas españoles de presupuestos. Está escrita en Python con una interfaz web Flask que se abre en el navegador del propio equipo.

El objetivo a largo plazo es añadir una capa de IA que edite el presupuesto conversacionalmente **invocando operaciones del modelo** (tool-calling), nunca tocando los datos directamente. La versión actual es la base: lector/escritor/editor BC3 completo con autoguardado, deshacer/rehacer e informes de validación.

## Estructura del código

```
bc3manager/
├── core/
│   └── model.py        # Modelo de datos + motor de recálculo (todo el cálculo vive aquí)
├── io/
│   ├── lector.py       # Parser BC3 (lectura FIEBDC-3)
│   └── escritor.py     # Escritor BC3 (exportación FIEBDC-3)
├── reports/
│   └── informes.py     # Los 4 informes HTML
├── cli.py              # Interfaz de línea de comandos
└── web.py              # Servidor Flask + frontend embebido (un solo archivo)

scripts/
└── gen_ejemplo.py      # Regenera ejemplo_son_font.bc3 (archivo de muestra)

tests/
└── test_basico.py      # Único archivo de tests + BC3 reales de prueba al lado
```

## El recorrido de un BC3 por el programa

1. **Se lee** (`io/lector.py`, `leer_bc3()`): se abre el archivo, se autodetecta la codificación (cp1252/cp850 según el `~V`), se trocea el texto en registros y se procesan `~V ~K ~C ~D ~T ~M` (el resto se ignora). Después: se resuelven los alias `#` de Presto (`_resolver_alias_hash`), se clasifica cada concepto (capítulo/partida/unitario), se detecta la raíz (o se crea `OBRA##` sintética), se leen coeficientes y decimales del `~K` y se lanza un primer `recalcular()`.
2. **Vive en memoria** (`core/model.py`): la clase `Presupuesto` contiene un diccionario `{código → Concepto}` y el código raíz. El árbol es: obra → capítulos → partidas → recursos unitarios. No hay base de datos: la memoria es el estado y el `.bc3` original es la persistencia.
3. **Se calcula** (`core/model.py`): siempre de abajo arriba y de forma determinista. El precio de una partida sale de su descomposición; el de un capítulo, de sumar sus hijos. En cada paso se aplican los redondeos del `~K` (en `Decimal` exacto, mitad-arriba, como Presto) y el % de costes indirectos por partida (`precio_con_ci`). Los precios precalculados que trae el archivo NO mandan: se guardan en `_precio_bc3` solo para validación.
4. **Se muestra** (`web.py`): Flask sirve una única página (HTML/CSS/JS embebido en `HTML_TEMPLATE`) y una API JSON. El árbol se serializa con `_arbol_json`/`_info_json`. Cada edición en pantalla hace `POST /api/editar`, el modelo aplica el cambio, `recalcular()` actualiza todo, `_autoguardar()` escribe el BC3 al archivo original y apila un snapshot para deshacer.
5. **Se exporta**: tres salidas — el propio `.bc3` (autoguardado + `GET /api/exportar`, vía `io/escritor.py`), los 4 informes HTML (`reports/informes.py`) y los informes de validación (Excel + `.txt`) que comparan archivo vs calculado.

## El modelo de datos en dos palabras

- **`Presupuesto`** — contenedor de todos los conceptos + metadatos del archivo (versión, programa emisor, codificación) + coeficientes del `~K` (`ci_pct`, `gg_pct`, `bi_pct`, `iva_pct`...) + decimales de redondeo (`dec_*`).
- **`Concepto`** — un nodo del árbol: código, unidad, resumen, texto largo, precio, tipo (`CAPITULO | PARTIDA | UNITARIO | OTRO`), lista de hijos (descomposición) y mediciones por padre.
- **`Hijo`** — referencia de un concepto a un hijo de su descomposición, con factor y rendimiento (`cantidad = factor × rendimiento`).
- **`Medicion` / `LineaMedicion`** — las líneas de medición de una partida dentro de un capítulo concreto (comentario, nº uds, largo, ancho, alto). Una `Medicion` sin líneas usa su `total_declarado` (partidas alzadas).

Detalle completo en [api-interna.md](api-interna.md).

## La interfaz web (web.py)

Un solo archivo: servidor + página. Decisiones clave:

- Todo el estado del servidor vive en el diccionario `_estado` (monousuario, local): presupuesto cargado, ruta del archivo original, pilas de deshacer/rehacer, rutas de los informes de validación.
- El frontend es JS vanilla (sin framework). Usa la librería de tablas **Tabulator 6.3** y Google Fonts cargadas desde CDN (hace falta internet para eso).
- Las celdas editables son `<span class="ecell" contenteditable>`. Navegación con Tab/Enter/flechas, Escape cancela.
- **Deshacer/rehacer por snapshots**: tras cada edición se apila el BC3 serializado completo; deshacer = restaurar el snapshot anterior (y reescribirlo a disco).
- **Al cargar un archivo** se ejecuta una validación completa (precios, mediciones, PEM, conformidad con el `~K`) que se vuelca a consola y genera un Excel y un `.txt` junto al archivo original.
- Tema claro/oscuro con variables CSS, persistido en localStorage.

## Los informes (reports/informes.py)

Cuatro informes HTML generados desde el presupuesto en memoria, listos para imprimir a PDF desde el navegador:

1. **mediciones** — líneas de medición por partida.
2. **cuadro** — cuadro de precios unitarios (partidas y sus recursos).
3. **presupuesto** — presupuesto completo con capítulos, mediciones, precios e importes.
4. **resumen** — importe por capítulo + PEM total.

## Principios de diseño

1. **Los totales son siempre deterministas.** Los calcula el motor de recálculo; nunca la interfaz, nunca la IA. Editar un valor y revertirlo devuelve exactamente el PEM inicial.
2. **El archivo original es la fuente de verdad.** Autoguardado tras cada edición. Sin base de datos aparte.
3. **Compatibilidad BC3 por encima de funcionalidades.** Si algo rompe el ciclo leer→escribir→leer (round-trip), no se añade.
4. **Replicar a Presto, no "mejorarlo".** Redondeos y costes indirectos se calculan como lo hace el programa de origen, con los parámetros que declara el propio archivo en su `~K`. El porqué de cada decisión está en [decisiones.md](decisiones.md).
5. **La futura IA opera vía herramientas.** Llamará a operaciones como `modificar_precio()`, nunca editará la estructura de datos directamente.

## Desarrollo

```bash
python3 tests/test_basico.py            # Tests (siempre tras tocar core/ o io/)
python3 -m bc3manager.web               # Web en http://127.0.0.1:5000 (puerto: env PORT)
python3 -m bc3manager.web archivo.bc3   # Web con archivo precargado + autoguardado
python3 -m bc3manager.cli info archivo.bc3      # info | arbol | informe | exportar
python3 scripts/gen_ejemplo.py          # Regenerar el BC3 de muestra
```

## Dependencias

- Python >= 3.10.
- **Flask >= 3.0** — única dependencia obligatoria (solo para la web; el núcleo y la CLI no necesitan nada).
- Opcionales: **openpyxl** (Excel de validación; sin él, el programa avisa y sigue) y **weasyprint** (exportar informes a PDF).
- Frontend sin npm ni bundler; Tabulator y fuentes vienen de CDN.
