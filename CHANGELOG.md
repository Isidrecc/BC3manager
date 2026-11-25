# Historial de cambios — BC3Manager

Registro de cambios relevantes. El más reciente arriba. Para el detalle técnico
y las reglas que NO hay que romper, ver `CLAUDE.md` (invariantes 5-7).

---

## 2026-11 — Importar presupuestos desde el PDF de Presto (feat)

Nuevo módulo `bc3manager/io/importar_pdf.py` y subcomando de la CLI
`importar-pdf`: lee el documento "Presupuesto" impreso por Presto (también si se
ha pasado por Word) y genera el BC3 más una **tabla de control en Excel**.

- Lee las cinco secciones: mediciones (con sus líneas), cuadros de precios nº1
  (cifra y letra) y nº2 (coste directo y CI), presupuesto (árbol de hasta seis
  niveles: capítulo … elemento) y resumen (PEM, GG, BI, IVA).
- La fuente es la sección PRESUPUESTO; el resto se usa para **cruzar** datos.
  Toda discrepancia queda en la hoja "Avisos" (ERROR si afecta a importes, AVISO
  si es solo texto), nunca se corrige en silencio.
- Detecta si el precio lleva los costes indirectos comparando con el cuadro nº2.
  Dos modos: `--ci incluido` (precio con CI y CI=0 en el `~K`, por defecto) y
  `--ci separado` (coste directo y el % de CI en el `~K`).
- Verificación de ida y vuelta: escribe el BC3, lo relee con el lector de
  BC3Manager y comprueba partida a partida, capítulo a capítulo y el PEM.
- Un capítulo repetido con el mismo código y contenido se escribe como un único
  concepto colgado de los dos sitios (como en Presto).
- Dependencias opcionales nuevas: `pip install pdfplumber openpyxl`
  (grupo `importar-pdf` en `pyproject.toml`).
- Tests nuevos `test_importar_pdf_*`; el de un PDF real solo corre si se define
  la variable `BC3_PDF_PRUEBA` (los PDF de obra no se suben al repositorio).

---

## 2026-06 — Batería de tests paramétrica sobre archivos reales (test)

Se implementa el diseño de `docs/auditoria/bateria-tests.md`. `tests/test_basico.py`
pasa de 27 tests clavados a mano a tres familias sobre un **corpus de 6 BC3 reales**
(Alquería, SONFONT, REDONDEO y los tres de Andratx): **paramétricos** (`param_*`,
la misma comprobación sobre cada archivo: lectura, referencias, recálculo
determinista, round-trip, conservación del `~K`…), **línea base** (PEM y nº de
discrepancias de cada archivo, como regresión) y **dirigidos** (valores exactos
contra un archivo concreto). Nuevos `test_edit_*`: primera cobertura de la capa
web (edición, autoguardado, undo/redo).

Las discrepancias de precio de los archivos de Andratx (29, 3 y 35) se fijan como
**línea base, no como fallo**: son hallazgos conocidos —el PEM del archivo no
cuadra con el recalculado de abajo arriba— pendientes de investigar. No se
"arreglan" relajando el test.

Nota: se añadió `from __future__ import annotations` a `tests/test_basico.py`
para que las anotaciones `X | None` funcionen en el Python 3.9 del entorno, como
ya hace el resto del repo.

---

## 2026-06 — Diseño de la batería de tests (docs)

Nuevo `docs/auditoria/bateria-tests.md`: diseño de una estrategia de tests
**paramétrica** (la misma batería de comprobaciones sobre muchos `.bc3` reales)
para cazar los problemas conocidos (registro-bugs nº 1-18) en cada archivo, en vez
de clavar valores a mano archivo por archivo. Define tres familias de tests
(paramétricos P1-P18, dirigidos de regresión, y edición/autoguardado E1-E12 — la
capa web hoy sin cobertura), una "lista de la compra" de qué archivos pedir para
activar cada bug, una propuesta sobre `ejemplo_son_font.bc3`, y el orden de
implementación. Es diseño; implementarlo será una sesión de código.

---

## 2026-06 — Cobertura de tests al día (docs)

`docs/auditoria/estado-tests.md` pasa de la foto del 2026-06-11 (25/25) a
documento vivo (**27/27**): añade los dos `test_alqueria_round_trip_*` al mapa
test→qué-protege, un **inventario de los `.bc3` de prueba** (qué cubre y qué NO
cada uno, y que `Test_SONFONT.bak/.xlsx/.pzh` no los usa ningún test), un
**checklist de qué correr según lo que toques**, y retira el "round-trip de BC3
reales" de los huecos (ya cubierto por los tests nuevos).

---

## 2026-06 — La validación deja de romperse al guardar (fix)

Compañero del arreglo de las partidas alzadas. Al guardar/exportar, el `~C` de
cada capítulo se escribía con el coste directo **sin** los costes indirectos
(Presto guarda ahí el importe **con** el 6%), y el total de cada `~M` como suma
cruda en vez del total redondeado. Tras guardar y reabrir, la validación —la red
de seguridad del usuario— pasaba de 0 a **38 falsas discrepancias de precio + 2
de medición**, y el hueco de PEM archivo-vs-calculado saltaba a **~+512.000 €**
(el 6% de CI ausente de los precios de capítulo guardados).

- **Arreglo (`io/escritor.py`):** (1) `_reg_C` escribe el **importe** del capítulo
  (la suma de los importes de sus partidas, cada una con su CI), igual que Presto
  — siempre, sin condiciones (con CI=0 el importe sale sin recargo). (2) `_reg_M`
  escribe el **total redondeado** como Presto (`total_medicion`), no la suma
  cruda (p.ej. `215.0030` → 112,21, no 111,326). El cálculo NO cambia: el precio
  de capítulo nunca interviene en el PEM (recalcular suma de abajo arriba); esto
  solo fija la referencia con la que el archivo se valida a sí mismo.
- **Autocomprobación coherente (`core/model.py`):** `validar_completo` calculaba
  el capítulo como `CD×(1+CI)` para compararlo, un cálculo que no existe en
  ningún otro sitio y que solo cuadraba "por tolerancia". Ahora compara el
  **importe del capítulo** (suma de importes de partidas), igual que
  `comparar_importes_archivo` y que la pantalla. Resultado: comparación **exacta**
  (hueco de PEM 0,00, no ~800 €) y robusta para cualquier archivo bien formado,
  sin parches ni dependencia de tolerancias.
- **Test de regresión:** `test_alqueria_round_trip_validacion_limpia` (ciclo
  leer→escribir→releer: 0 discrepancias de precio y medición, PEM cuadrado).
  Falla con el código viejo (38+2), pasa con el nuevo. **27/27 OK.**
- **Verificado:** Alquería tras guardar→reabrir: PEM 9.073.347,54 € idéntico, 0
  discrepancias, hueco de PEM −0,00 €. Sin regresión en Presto 8.8 ni en
  archivos sin CI.
- **Hallazgo lateral (no arreglado):** el escritor **siempre** emite un `~K`, así
  que un archivo que no lo traía gana redondeo al guardarse y sus valores se
  re-redondean (p.ej. `ejemplo_son_font.bc3`: PEM 4.523,25 → 4.524,00 en
  round-trip). Es pre-existente e independiente de este arreglo; queda anotado
  para el registro de bugs.

---

## 2026-06 — Registro de bugs vivo y flujo de trabajo de arreglos (docs)

- `docs/auditoria/problemas.md` → `docs/auditoria/registro-bugs.md` ("Registro de
  bugs y mejoras"): pasa de foto de auditoría a **documento vivo**, con una tabla
  de estado arriba; al resolver un ítem se tacha con fecha y commit. El nº 1
  (partidas alzadas) ya queda tachado (2026-06-14). Actualizados los enlaces de
  los documentos que lo referenciaban.
- `docs/guia-sesiones.md`: la plantilla de sesión de CÓDIGO recoge ahora el
  **flujo de arreglo acordado** (entender el problema con pruebas → explicar y
  proponer commit → luz verde → test primero → verificar → cerrar el bucle).
- Se registran 3 bugs de **interfaz/usabilidad** pendientes (nº 16-18): casillas
  de medición en blanco que se ven como "0", celdas que cortan el contenido sin
  poder redimensionarse, y títulos de partida que a veces no se pintan ("—").

---

## 2026-06 — Conservar las partidas alzadas al guardar (fix)

Al guardar/exportar un BC3 se perdían las **partidas alzadas** (mediciones sin
desglose línea a línea, solo total declarado). El escritor descartaba todo
registro `~M` sin líneas; como el autoguardado reescribe el archivo en cada
edición, bastaba un cambio cualquiera para perder esas partidas y su importe.

- **Síntoma medido:** en `tests/Test_Alqueria.bc3`, tras un ciclo
  guardar→reabrir el PEM caía **7.964,67 €** (de 9.073.347,54 a 9.065.382,87) —
  la alzada `542.0600`, que pasaba a importe 0. Las mediciones bajaban de 283 a
  282. Ocurría en silencio, sin aviso.
- **Arreglo (`io/escritor.py`):** (1) `_mediciones_ordenadas` ya no salta las
  mediciones sin líneas que tienen total declarado (solo descarta las realmente
  vacías); (2) `_reg_M` escribe el `total_declarado` cuando no hay líneas (antes
  escribía la suma de líneas, que es 0 sin líneas → medición 0). Cumple la norma
  FIEBDC (p.21): el registro `~M` debe figurar siempre, exista o no desglose.
- **Test de regresión:** `test_alqueria_round_trip_conserva_partida_alzada`
  blinda el ciclo leer→escribir→releer (PEM idéntico, nº de mediciones y el
  importe de la alzada conservados). Falla con el código viejo, pasa con el
  nuevo. 26/26 tests OK.
- **Pendiente (no incluido aquí):** tras exportar, el banner de validación sigue
  avisando de ~504.843 € y "38 conceptos inconsistentes". Es un fallo distinto y
  **cosmético** (el `~C` de capítulo se escribe sin el CI): no afecta al cálculo,
  queda para otra sesión.

---

## 2026-06 — Reorganización de la documentación

- Nueva carpeta `docs/` con la documentación técnica, cada tema en un único
  sitio: `arquitectura.md`, `api-interna.md`, `formato-bc3.md` y
  `decisiones.md` (decisiones de diseño con su porqué, antes enterradas aquí).
- `ARCHITECTURE.md` y `API_INTERNA.md` desaparecen de la raíz: su contenido,
  **actualizado y corregido**, vive ahora en `docs/`. Estaban desfasados
  respecto al código (decían que los coeficientes `~K` no se aplicaban, que no
  había deshacer/rehacer, y les faltaba media API de edición).
- `Analisis estrategico.md` → `docs/estrategia/analisis-estrategico.md`
  (es un estudio de negocio, no documentación técnica).
- README reescrito: refleja la interfaz web, el cálculo con `~K` y enlaza a
  `docs/`. CLAUDE.md actualizado como contexto permanente (invariante 2
  corregido: los precios del archivo ya no mandan en el cálculo).
- Nueva `docs/guia-sesiones.md`: plantillas de prompt para sesiones de
  documentación (mantenimiento) y de código, con las reglas comunes
  (Conventional Commits, la IA no commitea, verificar contra el código).

---

## 2026-06 — Visualización coherente de mediciones e informe de validación

### Visualización (`web.py`)
- La tabla de mediciones ahora muestra los valores **ya redondeados a sus
  decimales del `~K`** (uds→DN, dimensiones→DD), que son los que de verdad se
  usan en el cálculo. Antes mostraba el valor crudo (0,315) pero calculaba con
  el redondeado (0,32), y la línea no cuadraba al multiplicarla a mano. Ahora
  "lo que ves multiplicado = el parcial".

### Informe de validación `.txt` (`web.py`, `core/model.py`)
- Se genera un **informe `.txt`** junto al Excel al abrir el archivo
  (`validacion_<obra>.txt`), con el MISMO contenido que el volcado de terminal
  (fuente única: `_construir_informe`). Dos bloques:
  - **(A) Coherencia interna:** mediciones, precios y PEM (archivo vs calculado).
  - **(B) Conformidad con el `~K`:** lista de valores con MÁS decimales de los
    que declara el `~K` (p.ej. dimensión 0,315 con DD=2, uds -3,1415 con DN=2).
    Es solo un AVISO: el cálculo los redondea igual que Presto; informa de qué
    trae el archivo fuera de su propia norma. Método `revisar_consistencia_k`.

### Política de redondeo (decisión)
- Se sigue la **norma FIEBDC** al pie de la letra: cada factor se redondea a sus
  decimales del `~K` (uds→DN, dimensiones→DD, parcial→DSP, total→DS, etc.). No
  se replica el comportamiento observado de Presto de "no redondear el uds",
  porque no está confirmado con suficientes pruebas. Pendiente: contrastar el
  comportamiento real de Presto con más casos antes de desviarse de la norma.

---

## 2026-06 — Costes indirectos y redondeos conformes a FIEBDC-2016

Trabajando con un presupuesto real de Presto 20 (`tests/Test_Alqueria.bc3`,
FIEBDC-3/2016) afloró que nuestros importes no cuadraban con Presto. Se corrigió
toda la cadena de cálculo para que replique al programa de origen. Resumen:

### Lectura del archivo (`io/lector.py`)
- **Alias `#` en registros `~M`:** Presto 20 referencia el capítulo padre sin el
  `#` (`~M|001\...`) aunque el `~C` lo lleve (`001#`). Si no se normaliza, las
  mediciones quedaban huérfanas y el **PEM salía 0,00 €**. Arreglado en
  `_resolver_alias_hash` (renombra claves de medición tras borrar fantasmas).
- **Coeficientes y decimales SIEMPRE del registro `~K`** (nunca hardcodeados):
  - Campo 2 → `CI \ GG \ BI \ BAJA \ IVA` (en %). Solo el **CI** afecta al PEM.
  - Campo 3 (el completo y preferente según la norma; campo 1 de respaldo) →
    todos los decimales, incluidos **DD** (dimensiones) y **DN** (nº de partes)
    de las líneas de medición, que antes no leíamos.

### Cálculo (`core/model.py`)
- **Costes indirectos POR PARTIDA** (FIEBDC: precio = Coste Directo + Coste
  Indirecto): `precio_con_ci()` = `round(CD × (1+CI), DecPar)`. Se aplica a
  **todas** las partidas, incluidas las que ya llevan una línea `%CI` / medios
  auxiliares en su desglose (esa línea es un coste más del CD, no el CI global).
  Ej.: 301.0010 → 9,39 €; 700.001a → 34,27 €.
- **Redondeo como Presto, en decimal exacto y mitad-arriba** (`_redondea`,
  `_mult_red`): multiplicar en float arrastraba error (0,015×27,49 = 0,41234999…
  → 0,4123 en vez de 0,4124). Se opera en `Decimal`.
- **Líneas de medición: redondear cada factor antes de multiplicar**
  (`parcial_linea`): dimensiones a DD, nº de partes a DN; luego parcial a DSP y
  total a DS. Ej.: una altura 0,0475 se usa como 0,05 (antes en crudo).
  Esto resolvió casi todos los "descuadres de medición" que parecían errores del
  archivo (215.0030, 332.0040, 320.0110) y que en realidad eran bug nuestro.
- **Partidas alzadas:** una `~M` sin líneas de detalle usa el `total_declarado`
  (medición = 1), no 0. Ej.: 542.0600 → medición 1, importe 7.964,67 €.

### Clasificación de conceptos (`core/model.py`)
- Un concepto **con medición (`~M`) propia es una partida**, regla aplicada
  ANTES que la descomposición/unidad. Los capítulos nunca llevan `~M`. Esto
  arregla dos casos que se veían como capítulos:
  - **Hojas con medición** (partidas alzadas, unidad "PA"): 012# (PARTIDAS
    ALZADAS) y 013# (SEGURETAT I SALUT) se veían vacíos en el árbol.
  - **Partidas con descomposición pero sin unidad** en el `~C`: p.ej.
    701.0236a ("Cartell de 120x120 d'alumini"), que salía como capítulo. Al
    corregirlo, su importe (antes 0) entra en el PEM y éste queda exacto.
  - Criterio robusto para no confundir: un concepto es **capítulo** si sus
    hijos están MEDIDOS dentro de él (su `~M` apunta a su código) o son
    subcapítulos. Así, un capítulo con **medición "fantasma" de 1** (que ponían
    algunos Prestos antiguos) sigue siendo capítulo, y una partida cuyo recurso
    es un auxiliar con descomposición propia sigue siendo partida.

### Escritura (`io/escritor.py`)
- El `~K` exportado conserva el campo 2 (coeficientes CI/GG/BI/BAJA/IVA). Antes
  estaba fijo a "0" y se perdían al guardar (round-trip roto).

### Interfaz (`web.py`)
- Recuadro de **costes indirectos** junto al PEM total.
- **Desglose de precio** bajo la descomposición de cada partida (Suma la partida
  · Costes indirectos · Redondeo · TOTAL PARTIDA), como el informe de Presto.
- **Total de medición** al pie del recuadro de mediciones.
- Excel de comprobación: importes con CI; columnas separadas de **medición
  archivo (~M)** vs **medición calc (líneas)** — diseño estricto archivo vs
  calculado.
- Apertura del navegador en `http://127.0.0.1:5000` (no `localhost`, que en
  algunos equipos da 403).

### Resultado
- PEM de Alquería a **-0,0045 %** del valor congelado del archivo (≈400 € sobre
  9 M). Cero discrepancias de precio y de medición. Presto 8.8 sigue exacto.
- Tests de regresión `test_alqueria_*` en `tests/test_basico.py` (23/23 OK) que
  blindan estos valores contra el informe real de Presto.
