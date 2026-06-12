# Problemas y sospechas detectados — ordenados por gravedad

> Fecha: 2026-06-11. Auditoría de solo lectura: **nada de esto está corregido**.
> "Verificado" = reproducido empíricamente en esta auditoría. "Sospecha" = deducido del código y la norma, sin archivo real que lo confirme aún.
> El comportamiento general del programa está descrito en [auditoria-calculo.md](auditoria-calculo.md).

## Gravedad ALTA — provocan (o pueden provocar) diferencias reales de importes

### 1. Las partidas alzadas pierden su medición al guardar — VERIFICADO

- **Dónde:** `io/escritor.py::_mediciones_ordenadas` — salta toda medición sin líneas de detalle (`if not medicion.lineas: continue`), que es justo la forma de las partidas alzadas (solo total declarado).
- **Efecto medido:** ciclo leer→guardar→releer con `tests/Test_Alqueria.bc3`: el PEM cae **7.964,67 €** (de 9.073.347,54 a 9.065.382,87), exactamente el importe de la partida alzada 542.0600. Las 283 mediciones pasan a 282.
- **Por qué es grave:** el **autoguardado** reescribe el archivo original tras CUALQUIER edición en la web. Basta corregir una errata en un resumen para que el archivo pierda la alzada para siempre (salvo deshacer inmediato o copia previa). Además incumple la norma (p.21): *"deberá figurar siempre este registro \[~M\], exista o no desglose de mediciones"*.
- **Por qué no lo cazan los tests:** `test_round_trip` usa `ejemplo_son_font.bc3`, que no tiene partidas alzadas; `test_alqueria_partida_alzada_sin_lineas` solo comprueba la lectura, no el ciclo completo.

### 2. El archivo guardado pierde la referencia para validar — VERIFICADO

- **Dónde:** `io/escritor.py::_reg_C` escribe el precio **recalculado** de cada concepto; para los capítulos, eso es el coste directo **sin CI**, cuando el archivo de origen (Presto 20) traía el precio con CI. Y `_reg_M` escribe como total declarado la suma cruda de líneas (`Medicion.total`), no el total con redondeo Presto (`total_medicion`) ni el declarado original.
- **Efecto medido:** tras guardar y releer Alquería, la validación pasa de **0 a 38 discrepancias de precio** y de 0 a 2 de medición, y la comparación de PEM archivo-vs-calculado pasa de 0,41 € a **504.843 €** de diferencia (≈ el 6% de CI que ya no está en los precios de capítulo guardados).
- **Por qué es grave:** los importes calculados siguen siendo correctos, pero el informe de validación —la herramienta de confianza del usuario— queda inservible en cuanto se edita algo: a partir de ahí compara contra un archivo que ya no es el de origen y da falsas alarmas. Nota: la conformidad con la norma de escribir el CD sin CI en el `~C` de capítulos es discutible en ambos sentidos; lo objetivo es que el archivo guardado **ya no es comparable** con el de Presto.

### 3. Posible CI duplicado cuando el porcentaje viene de un concepto `%CI` — SOSPECHA

- **Dónde:** `io/lector.py::_detectar_costes_indirectos` — si el `~K` no declara CI pero existe un concepto cuyo código empieza por `%CI`, toma su precio como `ci_pct` global.
- **El riesgo:** si ese mismo concepto `%CI` aparece además como línea dentro de las descomposiciones (que es lo habitual), su coste ya se suma en el coste directo de cada partida (`recalcular` lo trata como línea de porcentaje)… y encima `precio_con_ci` aplica el `ci_pct` global otra vez. La norma (p.9) advierte expresamente de no aplicar dos veces el CI por esta dualidad `~K`/descomposición.
- **Estado:** ningún archivo de los tests activa esta vía (Alquería trae el CI en el `~K`; Presto 8.8 no tiene nada). Hace falta un archivo real que declare el CI solo como concepto `%CI` para confirmar o descartar.

## Gravedad MEDIA — desviaciones de la norma con efecto en casos concretos

### 4. El campo 1 del `~K` se interpreta en un orden distinto al de la norma

- **Dónde:** `io/lector.py::_reg_K`. El programa lee el campo 1 como `DecDet\DecCantMed\DecCantRend\DecImp\DecNat\DecPar\Dec` (orden del diálogo de Presto, "verificado empíricamente"). La norma 2024 (p.5) define ese campo como `DN\DD\DS\DR\DI\DP\DC\DM\DIVISA` — son significados distintos posición a posición.
- **Efecto:** solo afecta a archivos **sin campo 3** (los modernos lo traen y ahí el programa va correcto). En un archivo solo-campo-1 con decimales no estándar, cada redondeo podría aplicarse al paso equivocado.
- **Ojo:** la "verificación empírica" se hizo con `tests/Test_REDONDEO.bc3`, que parece un archivo construido a medida — si se construyó asumiendo ese mismo orden, la verificación es circular. Hace falta contrastar con un archivo solo-campo-1 generado por un programa real.

### 5. Al guardar se pierde el campo 3 del `~K` (y con él DN y DD)

- **Dónde:** `io/escritor.py::_reg_K` — escribe solo el campo 1 (con el orden propio del programa, ver nº 4) y el campo 2 de coeficientes. El campo 3, el preferente según la norma, no se emite, y los decimales de mediciones DN (uds) y DD (dimensiones) **solo existen en el campo 3**.
- **Efecto:** un archivo que declare DN/DD distintos de 2, tras guardarse y reabrirse, redondeará las mediciones con los defectos (2/2) → parciales y totales de medición distintos. Con Alquería no se nota porque casualmente trae DN=DD=2.

### 6. Los tipos de línea de medición (subtotales y fórmulas) no se interpretan

- **Dónde:** `io/lector.py::_reg_M` guarda el tipo de línea pero `model.py::parcial_linea`/`total_medicion` tratan toda línea como producto normal.
- **La norma (p.22):** tipo 1/2 son líneas de subtotal (sus dimensiones, si las hubiera, *"no se tendrán en cuenta"*); tipo 3 es una expresión algebraica en el comentario (*"solo se evalúa la expresión y no se multiplica por las unidades"*).
- **Efecto:** un archivo con líneas de subtotal que (incumpliendo la norma) lleven datos las **contaría dos veces**; un archivo con líneas de fórmula (los genera p.ej. Presto con mediciones por expresión) calcularía mal esa medición o la dejaría a 0. Ningún archivo de los tests trae estos tipos, así que hoy no hay caso confirmado.

### 7. Los decimales "en negativo" del `~K` se ignoran

- **Dónde:** `io/lector.py::_reg_K`, funciones internas `_dec`/`_d3`: usan `isdigit()`, que rechaza `-2` → se aplica el valor por defecto.
- **La norma (p.5):** un número de decimales negativo significa "número MÁXIMO de decimales" (no exacto). El programa ni lo detecta ni lo aproxima: usa el defecto, que puede no coincidir.

### 8. Porcentajes con máscara de prefijo no soportados

- **Dónde:** `model.py::es_porcentaje` + bucle de `recalcular()`: una línea de porcentaje se aplica sobre **todas** las líneas anteriores del desglose.
- **La norma (p.9-10):** el código de un porcentaje puede llevar una máscara de prefijo (p.ej. `O%N0001` se aplica solo a las líneas anteriores cuyo código empiece por `O`), y existe el carácter `&` (porcentaje acumulable). El programa solo reconoce el caso "sin máscara": detecta por código que **empieza** por `%` o unidad `%` (un `O%N0001` solo se detecta si su unidad es `%`), y no distingue `&`.
- **Efecto:** en archivos con porcentajes enmascarados, el % se aplicaría a más líneas de las debidas → precio de partida inflado.

### 9. Códigos sinónimos del `~C` descartados

- **Dónde:** `io/lector.py::_reg_C` — `codigos.split("\\")[0]`: si un concepto declara varios códigos sinónimos (la norma p.8 lo permite), solo se registra el primero.
- **Efecto:** si otro registro (`~D`, `~M`) referencia al concepto por un sinónimo, el enlace se rompe y se crea un concepto fantasma vacío → descomposición o medición perdida. No confirmado con archivo real.

## Gravedad BAJA — incoherencias sin efecto en importes (o con efecto muy improbable)

### 10. El "tipo de información" del `~V` está interpretado al revés

- **Dónde:** comentario de `model.py::Presupuesto.__init__` (`"1" presupuesto, "2" BBDD`) y `escritor.py::_reg_V` (escribe `1` por defecto). La norma (p.4) dice: **1 = Base de datos, 2 = Presupuesto**, 3 = Certificación, 4 = Actualización de BBDD.
- **Efecto:** los archivos exportados se etiquetan como "base de datos" siendo presupuestos. No afecta a importes; puede confundir a programas que lean ese campo (`ejemplo_son_font.bc3`, generado por `scripts/gen_ejemplo.py`, lleva ese `1`).

### 11. El `~V` exportado pierde la propiedad y la fecha del archivo original

- **Dónde:** `escritor.py::_reg_V` — escribe el campo PROPIEDAD vacío y como programa emisor "BC3Manager". Razonable, pero la procedencia original se pierde en el primer autoguardado.

### 12. DRC y DEC del campo 3 del `~K` no se leen

- **Dónde:** `io/lector.py::_reg_K` (bloque del campo 3). DRC (rendimientos a nivel presupuesto) y DEC (importes de elementos compuestos/auxiliares con descomposición propia) se ignoran; los auxiliares se redondean hoy con DUO/Dec según su clasificación.

### 13. El subtipo "4 = Auxiliar" choca con la norma 2024

- **Dónde:** `model.py::cambiar_tipo_recurso` ofrece `4`=auxiliar (convención de Presto antiguo); en la norma 2024 el tipo 4 del `~C` es "componentes adicionales de residuo" y el 5 "clasificación de residuo". El escritor (`_tipo_fiebdc_salida`) escribe 1-4 tal cual. Riesgo práctico mínimo, pero es una divergencia documentable.

### 14. El campo 3 del `~D` no se lee

- **Dónde:** `io/lector.py::_reg_D` lee el campo 2 (compatibilidad). El campo 3 de la norma añade códigos de porcentaje explícitos por línea, que afinarían el cálculo de los `%` (relacionado con el nº 8).

### 15. La detección del `%CI` de respaldo coge el primer match

- **Dónde:** `io/lector.py::_detectar_costes_indirectos` — toma el primer concepto cuyo código empiece por `%CI`; si hubiera varios (p.ej. distintos % por capítulo), se queda uno arbitrario. Relacionado con el nº 3.

---

## Qué cubre la validación actual y qué se le escapa

La validación al abrir (`validar_completo` + Excel/txt) **detecta bien** los descuadres internos del archivo de origen: mediciones cuyo total declarado no cuadra con sus líneas, precios del `~C` que no salen de su descomposición, y el PEM. Con Alquería: 0 discrepancias y PEM a 0,41 €.

**No puede detectar** (porque ocurren después de validar): todo lo que el guardado estropea o descarta (nº 1, 2, 5, 11) — el programa no avisa de que va a perder registros que no soporta. Y **no compara** contra el archivo en los aspectos que no lee (tipos de línea, sinónimos, paramétricos). La especificación del comando de comparación ([spec-script-comparacion.md](spec-script-comparacion.md)) propone cubrir justo este hueco con un modo de ida-y-vuelta.
