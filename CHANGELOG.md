# Historial de cambios — BC3Manager

Registro de cambios relevantes. El más reciente arriba. Para el detalle técnico
y las reglas que NO hay que romper, ver `CLAUDE.md` (invariantes 5-7).

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
