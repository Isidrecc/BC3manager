# Decisiones de diseño

> Qué se decidió, cuándo y por qué — para no rediscutirlo cada vez ni deshacerlo por accidente. Las decisiones de cálculo están blindadas por los tests `test_alqueria_*` y `test_presto88_sin_ci_sigue_exacto`.
> El historial de cambios fechado está en el [CHANGELOG](../CHANGELOG.md).

---

## Cálculo

### El PEM es determinista: los precios del archivo no mandan (2026-06)

**Decisión:** `recalcular()` y `_importe_recursivo()` suman SIEMPRE de abajo arriba. El precio de capítulo precalculado que traen algunos archivos (Presto 8.8) se guarda en `_precio_bc3` pero solo se usa para los informes de validación, nunca en el cálculo.
**Por qué:** editar un valor y revertirlo debe devolver exactamente el PEM inicial. Si los capítulos "congelaran" el precio del archivo, tras la primera edición el total saltaría de forma impredecible.
**Antes era al revés** (los capítulos con `_precio_bc3` conservaban su precio); documentación anterior a junio de 2026 puede reflejar el comportamiento viejo.

### Una partida sin medición tiene importe 0, sin fallbacks (2026-06)

**Decisión:** si no hay registros `~M` (o la medición es 0), el importe es 0. No se usa la cantidad de la descomposición ni el precio del archivo como respaldo.
**Por qué:** coherencia con lo que muestra la pantalla — si la cantidad visible es 0, el importe debe ser 0. Los fallbacks ocultaban datos incompletos.
**Excepción razonada:** una `~M` sin líneas de detalle pero con total declarado es una **partida alzada** y usa ese total como medición.

### Costes indirectos POR PARTIDA, a todas las partidas (2026-06)

**Decisión:** `precio_con_ci() = round(CD × (1 + ci_pct), DecPar)`, aplicado a TODAS las partidas — incluidas las que ya llevan una línea `%CI`/medios auxiliares en su desglose. El importe de capítulo es la suma de los importes de sus hijos, sin CI extra.
**Por qué:** es lo que define FIEBDC (precio de unidad de obra = Coste Directo + Coste Indirecto) y lo que hace Presto. La línea `%` del desglose es un coste más del CD, no el CI global: excluirla descuadraba partidas reales (301.0010 → 9,39 €; 700.001a → 34,27 €, verificados contra el informe de Presto).

### GG / BI / IVA se leen pero no se aplican (2026-06)

**Decisión:** del campo 2 del `~K` solo el CI interviene en el cálculo. Gastos generales, beneficio industrial, baja e IVA se conservan en memoria y en el round-trip.
**Por qué:** el programa calcula PEM. PEC y totales con IVA son una funcionalidad futura; aplicar coeficientes a medias daría totales que no son ni una cosa ni la otra.

### Redondeo en `Decimal` exacto, mitad-arriba — nunca `round()` de Python (2026-06)

**Decisión:** todos los redondeos pasan por `_redondea`/`_mult_red` (módulo `decimal`, `ROUND_HALF_UP`).
**Por qué:** `round()` de Python es bancario (al par) y opera sobre floats que arrastran error binario: 0,015 × 27,49 = 0,41234999… → 0,4123, cuando Presto da 0,4124. Los "descuadres de medición" que parecían errores de los archivos reales (215.0030, 332.0040, 320.0110) eran en realidad este bug nuestro.

### Política de redondeo: la norma FIEBDC al pie de la letra (2026-06)

**Decisión:** cada factor de una línea de medición se redondea a sus decimales del `~K` ANTES de multiplicar (uds→DN, dimensiones→DD), luego el parcial a DSP y el total a DS. No replicamos el comportamiento observado en algún Presto de "no redondear el uds".
**Por qué:** ese comportamiento de Presto no está confirmado con suficientes casos. Ante la duda, manda la norma. **Pendiente:** contrastar el comportamiento real de Presto con más archivos antes de desviarse de ella.

### Los coeficientes y decimales salen SIEMPRE del `~K` del archivo, nunca hardcodeados

**Decisión:** cada archivo se calcula con sus propios parámetros declarados. Sin `~K`, `redondeo_activo=False` y precisión alta.
**Por qué:** dos archivos distintos pueden declarar decimales distintos; un valor fijo en el código cuadraría unos y descuadraría otros. Es además lo que exige la norma (campo 3 preferente, campo 1/2 de respaldo).

---

## Visualización

### La tabla de mediciones muestra los valores YA redondeados (2026-06)

**Decisión:** la web muestra cada factor redondeado a sus decimales del `~K` (lo que de verdad entra en el cálculo), no el valor crudo del archivo.
**Por qué:** antes se mostraba 0,315 pero se calculaba con 0,32, y la línea no cuadraba al multiplicarla a mano. Regla: "lo que ves multiplicado = el parcial".

### Validación al abrir: archivo vs calculado, y conformidad con el `~K` (2026-06)

**Decisión:** al cargar un BC3 se genera un Excel y un `.txt` (misma fuente: `_construir_informe`) con dos bloques: (A) coherencia interna — mediciones, precios y PEM del archivo frente a lo calculado; (B) conformidad con el `~K` — valores con más decimales de los declarados, como AVISO, no error.
**Por qué:** el usuario verifica a prueba y error contra Presto; estos informes hacen visible cualquier desviación nada más abrir, y separan "el archivo no cuadra consigo mismo" de "el archivo incumple su propia norma de decimales".

---

## Producto / técnica

### Sin base de datos: el `.bc3` original es la persistencia

Autoguardado tras cada edición (`_autoguardar()`). Un presupuesto es un archivo que el usuario ya gestiona (copias, versiones, envíos); una BD duplicaría ese estado y rompería la interoperabilidad como flujo natural.

### Un solo archivo web.py con el HTML embebido; sin npm, sin bundler

Frontend JS vanilla en una r-string de Python (más Tabulator y Google Fonts por CDN). Mantiene la herramienta autocontenida: instalar = tener Python y Flask. La complejidad de un build de frontend no se justifica para una app local monousuario.

### Deshacer/rehacer por snapshots del BC3 completo

Cada edición apila el BC3 serializado entero; deshacer restaura el snapshot anterior (y lo escribe a disco). Menos eficiente que un diff, pero trivialmente correcto: el snapshot es exactamente el formato que ya sabemos leer y escribir, y el round-trip está testeado.

### El navegador se abre en `127.0.0.1`, no en `localhost`

En algunos equipos `localhost` se resuelve por un proxy/host alternativo y devuelve 403. La IP va directa.

### La futura capa de IA invocará operaciones, nunca calculará

Cualquier IA (o la propia interfaz) llama a operaciones del modelo (`modificar_precio`, `mover_concepto`…) y es `recalcular()` quien deriva los totales. Mantiene los números auditables y deterministas.
