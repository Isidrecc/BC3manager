# Auditoría del cálculo — cómo funciona HOY el programa

> Fecha: 2026-06-11. Sesión de solo lectura: nada de lo aquí descrito se ha corregido.
> Contrastado con la norma **FIEBDC-3/2024** (`FIEBDC/2024/Formato-FIEBDC-3-2024.pdf`, registros ~V p.4, ~K p.5-7, ~C p.8, ~D p.9-10, ~M p.21-22) y verificado empíricamente con `tests/Test_Alqueria.bc3` (Presto 20 real, ~K completo, CI 6%) y `ejemplo_son_font.bc3`.
> Los problemas detectados están en [problemas.md](problemas.md). Aquí solo se describe el comportamiento.

**Limitación importante del archivo de ejemplo:** `ejemplo_son_font.bc3` NO trae registro `~K` (solo `~V ~C ~D ~M`). Sin `~K` el programa desactiva el redondeo por pasos (`redondeo_activo=False`) y no hay costes indirectos (`ci_pct=0`). Sirve para auditar la lectura (A); para redondeos (B) y CI (C) el caso real es `Test_Alqueria.bc3`.

---

## A) Cómo lee el programa el archivo BC3

Todo en `io/lector.py`. El orden del proceso está en `LectorBC3.leer()`: detectar codificación → trocear registros → procesar `~V ~K ~C ~D ~T ~M` (cualquier otro registro **se ignora**, `_procesar_registro`) → resolver alias `#` → clasificar tipos → detectar raíz → detectar CI → primer recálculo.

### Conceptos (`lector.py::_reg_C`)

De cada `~C` se leen: código, unidad, resumen, **primer** precio y tipo. Detalles:

- Si el campo CODIGO trae varios códigos sinónimos separados por `\` (la norma lo permite, p.8), **solo se usa el primero**; los sinónimos se descartan.
- Si el campo PRECIO trae varios precios alternativos, solo se usa el primero.
- El precio del archivo se guarda dos veces: en `precio` (que el recálculo puede sobrescribir) y en `_precio_bc3` (copia intocable que solo sirve para comparar después, ver D).
- El campo 6 (TIPO) se guarda en `_tipo_fiebdc`. OJO: los valores 5=capítulo y 6=partida alzada que emite Presto **no están en la norma 2024** (que define 0-3 como naturalezas de recurso y 4-5 para residuos); el programa los acepta porque los archivos reales los traen.

### Descomposiciones (`lector.py::_reg_D`)

Los hijos vienen en tripletes `código\factor\rendimiento`. Detalles:

- Campo vacío → 1,0 por defecto (lo que dice la norma); un `0` explícito se conserva como 0 (una partida que no se mide en ese capítulo).
- Solo se lee el **campo 2** del `~D` (el de compatibilidad). La norma define un campo 3 más completo, con códigos de porcentaje explícitos por línea, que el programa no lee.
- Si el hijo referenciado no existe todavía, se crea un concepto vacío que los registros posteriores irán rellenando.

### Alias `#` (`lector.py::_resolver_alias_hash`)

La norma dice (p.8): *"Las referencias a un CODIGO con y sin # y/o ##, se entienden únicas a un mismo concepto"*. Presto se apoya en eso: el 8.8 referencia `02.01` en el `~D` cuando el concepto es `02.01#`, y Presto 20 hace lo mismo en el `~M` (`~M|001\...` para el capítulo `001#`). La pasada de resolución: (1) redirige los hijos sin `#` a su gemelo con `#`, (2) borra los conceptos "fantasma" vacíos que se crearon por el camino, y (3) renombra las claves de medición. Sin el paso 3, todas las mediciones de un Presto 20 quedaban huérfanas y el PEM salía 0 (bug real corregido en 2026-06).

### Clasificación capítulo/partida/unitario (`core/model.py::clasificar_tipos`)

Primero manda el `_tipo_fiebdc` si viene (1-4 unitario, 5 capítulo, 6 partida). Si no viene, heurísticas en orden:

1. Raíz o código acabado en `#` sin unidad → capítulo.
2. Si sus hijos se **miden dentro de él** (la `~M` del hijo apunta a su código) → capítulo, aunque traiga una "medición fantasma de 1" (Prestos antiguos).
3. Si tiene medición propia y no agrega partidas → **partida** (aunque no tenga unidad en el `~C`).
4. Con descomposición: partida si tiene unidad, capítulo si no.
5. Lo demás → unitario.

### Líneas de medición (`lector.py::_reg_M`)

Estructura del `~M`: `PADRE\HIJO | POSICIÓN | TOTAL | TIPO\COMENTARIO\N\LARGO\ANCHO\ALTO\...`. Detalles:

- El campo POSICIÓN **se ignora al leer** (el padre se identifica por código).
- El TOTAL del archivo se guarda en `total_declarado` — no se usa para calcular salvo en un caso: una `~M` **sin líneas de detalle** (partida alzada) usa el total declarado como medición (`model.py::total_medicion`).
- El TIPO de línea (1=subtotal parcial, 2=subtotal acumulado, 3=expresión, norma p.22) **se guarda pero no se interpreta**: toda línea con algún dato se trata como línea normal de producto. Ver [problemas.md](problemas.md) nº 6.
- Una línea solo se añade si tiene algún número distinto de 0 o un comentario.
- En una línea, los factores a 0 cuentan como neutros (una línea "5 / 0 / 0 / 0" mide 5, no 0): `model.py::LineaMedicion.subtotal`.

---

## B) Redondeos: quién manda y en qué orden

### Dónde declara el archivo sus decimales

En el registro `~K` (norma p.5-7). Tiene 3 campos y la norma es explícita: *"los programas deben leer el campo 3 por ser más completo y en su defecto el campo 1"*. `lector.py::_reg_K` hace exactamente eso: lee el campo 1 y, si existe el campo 3, lo sobrescribe.

- **Campo 3** (preferente): `DRC\DC\\DFS\DRS\\DUO\DI\DES\DN\DD\DS\DSP\DEC\DIVISA`. El programa toma: DC→decimales de importes de capítulo e importes en general, DRS→rendimientos, DUO→precio de partida, DI→subtotales del desglose, DES→precios de básicos, DN→nº de uds de una línea, DD→dimensiones, DS→total de medición, DSP→parcial de línea. Verificado contra el `~K` real de Alquería (`3\2\\3\4\\2\4\3\2\2\3\2\3\EUR\` → DI=4, DUO=2, DN=DD=2, DS=3, DSP=2). No se leen DRC ni DEC.
- **Campo 1** (compatibilidad): la norma 2024 lo define como `DN\DD\DS\DR\DI\DP\DC\DM\DIVISA`, pero el programa lo lee con otro orden ("DecDet\DecCantMed\DecCantRend\DecImp\DecNat\DecPar\Dec", el del diálogo de Presto, "verificado empíricamente" con `Test_REDONDEO.bc3`). **Las dos interpretaciones no coinciden** — ver [problemas.md](problemas.md) nº 4. Solo afecta a archivos sin campo 3.
- **Decimales en negativo** (la norma dice que significan "número MÁXIMO de decimales"): el programa no los reconoce y aplica el valor por defecto — [problemas.md](problemas.md) nº 7.

¿Respeta el programa esos decimales o usa los suyos? **Los del archivo, siempre**, con una excepción global: si el archivo no trae `~K`, `redondeo_activo=False` y todo se calcula a precisión alta sin redondeo por pasos (es el caso de `ejemplo_son_font.bc3`). Si trae `~K` pero le faltan posiciones, se usan los defectos de la norma (2 casi todo, 3 para rendimientos), que son los valores iniciales de `model.py::Presupuesto.__init__`.

### Cómo redondea (técnica)

Todo pasa por `model.py::_redondea` y `_mult_red`: convertir a `Decimal` exacto, multiplicar ahí, y redondear **mitad-arriba** (≥5 sube). Coincide con la norma (p.6: *"criterio <5 queda igual y >=5 suma, y las operaciones que se hagan del importe serán con este valor redondeado"*). No se usa el `round()` de Python porque es "al par" y opera en float con error binario (0,015×27,49 = 0,41234999… → daría 0,4123 en vez de 0,4124).

### El ORDEN de redondeo al subir de nivel

Este es el orden exacto que sigue hoy el programa, de abajo arriba, redondeando **en cada paso antes de seguir** (igual que el esquema aclaratorio de la norma, p.7):

```
1. Cada factor de la línea de medición se redondea ANTES de multiplicar:
   nº de uds → DN, largo/ancho/alto → DD          (model.py::parcial_linea)
2. El producto (parcial de línea) → DSP            (model.py::parcial_linea)
3. La suma de parciales (total de medición) → DS   (model.py::total_medicion)
   · ~M sin líneas: medición = total_declarado (partida alzada)
4. El precio de cada recurso básico → DES          (model.py::recalcular)
5. Cada subtotal del desglose (precio × rendimiento) → DI   (recalcular)
   · Líneas %: cantidad implícita = acumulado×coef/precio_% → DRC,
     luego cantidad × precio_% → DI                (recalcular)
6. La suma del desglose (coste directo de la partida) → DUO (recalcular)
7. El CI encima: round(CD × (1+ci_pct)) → DUO      (model.py::precio_con_ci)
8. Importe de partida = precio_con_ci × medición → DC (model.py::importe_en_padre)
9. Importe de capítulo = suma de importes de hijos → DC (model.py::_importe_recursivo)
10. PEM = suma de capítulos raíz, redondeo final a 2 (model.py::presupuesto_total)
```

Resultado contrastado: con Alquería, 0 discrepancias de precio y de medición al abrir, y PEM calculado a 0,41 € del archivo (sobre 9,07 millones, un 0,000045). Los tests `test_alqueria_*` fijan pasos concretos de esta cadena contra el informe de desglose de Presto.

**Decisión documentada pendiente de confirmar** (ver [decisiones.md](../decisiones.md)): el programa redondea también el nº de uds a DN, como dice la norma; se observó algún Presto que parece no hacerlo, pero no está confirmado.

---

## C) Costes indirectos

### De dónde sale el porcentaje

1. **Vía estándar** (la que usa Alquería): campo 2 del `~K` = `CI\GG\BI\BAJA\IVA` en porcentaje (`lector.py::_reg_K`). Alquería declara `6\13\6\0\21` → CI 6%, GG 13%, BI 6%, IVA 21%. **Solo el CI entra en el cálculo del PEM**; GG/BI/BAJA/IVA se guardan sin usar (PEC e IVA son funcionalidad futura).
2. **Vía de respaldo** (`lector.py::_detectar_costes_indirectos`): si el `~K` no trae CI, se busca un concepto cuyo código empiece por `%CI` y se toma su precio como porcentaje. Solo se usa si la vía 1 no dio nada. Esta heurística tiene un riesgo de doble cómputo — ver [problemas.md](problemas.md) nº 3.
3. Si no hay ninguna de las dos: `ci_pct=0` y no se aplica nada (Presto 8.8, que ya trae los indirectos dentro de sus precios; el test `test_presto88_sin_ci_sigue_exacto` lo protege).

### Sobre qué base y en qué momento

Sobre el **coste directo de cada partida**, ya redondeado a DUO, y justo antes de multiplicar por la medición: `precio = round(CD × (1+ci_pct), DUO)` (`model.py::precio_con_ci` y `_con_ci`). Es decir, el CI se aplica **por partida** (no al final sobre el total), que es lo que define la norma: el esquema de la p.7 dice precio de unidad de obra = Coste directo (DI) + Coste indirecto (DI) → total DUO. Verificado con Alquería: 301.0010 → round(8,86 × 1,06) = 9,39 €; 700.001a → 34,27 €.

Detalles importantes:

- Se aplica a **todas** las partidas, incluidas las que ya llevan una línea `%CI`/medios auxiliares en su desglose: esa línea es un coste directo más del redactor, no el CI global. La norma (p.9) advierte exactamente de esta dualidad: *"no aplicar dos veces el concepto de costes indirectos en una misma unidad de obra, ya que el formato permite disponer los costes indirectos tanto en el registro ~K como en la descomposición"*. Con Alquería, aplicar el 6% encima de todo es lo que reproduce a Presto al céntimo.
- Los capítulos no llevan CI extra: su importe es la suma de los importes de sus hijos (que ya lo llevan).
- Las líneas de porcentaje del desglose (`%MA` etc., `model.py::es_porcentaje`) se calculan sobre el acumulado de las líneas anteriores, no como precio×rendimiento. El programa aplica el % sobre **todas** las líneas anteriores; la norma permite además máscaras de prefijo que limitan a qué líneas se aplica, y eso no está implementado — [problemas.md](problemas.md) nº 8.

---

## D) Qué pasa cuando el archivo y el cálculo no coinciden

### La política: el cálculo manda, el archivo se usa para avisar

Es exactamente lo que pide la norma (p.8, registro ~C): *"En el caso de que el concepto posea descomposición, este precio será el resultado de dicha descomposición […] En caso de discrepancia, tendrá preponderancia el resultado obtenido por su descomposición […] y complementariamente se podría informar al usuario de dicha situación"*. Y para las mediciones (p.22): *"al leer este registro se recalculará este valor"*.

En la práctica:

- **En el cálculo, el valor escrito en el archivo no se usa nunca.** `recalcular()` suma siempre de abajo arriba y los importes salen de `_importe_recursivo`; el precio del `~C` de un concepto con descomposición se sobrescribe. La copia original queda en `_precio_bc3` solo como referencia.
- **Al abrir un archivo, el programa compara y avisa** (`web.py::_payload_carga`): ejecuta `model.py::validar_completo()` que compara (1) el total declarado de cada `~M` con la suma de sus líneas, (2) el precio del `~C` con el recalculado por descomposición (aplicando CI a los capítulos para comparar lo mismo con lo mismo), y (3) el PEM del archivo (suma de precios congelados de los capítulos raíz) con el PEM calculado, con tolerancia de 1 céntimo. El resultado se muestra de tres formas: volcado por consola, un **Excel** y un **.txt** de validación generados junto al archivo (`web.py::_construir_informe`, `_generar_excel_validacion`). Hay además un chequeo de conformidad (`model.py::revisar_consistencia_k`): valores con MÁS decimales de los que su propio `~K` declara, que es solo un aviso (la norma p.5 lo considera un error del archivo: *"se debe especificar como error"*).
- **No reescribe nada por el hecho de detectar diferencias.** El archivo solo se toca cuando el usuario edita.

### Pero ojo con el autoguardado

Cuando el usuario **edita** algo en la web, `web.py::_autoguardar()` reescribe el archivo original completo con `io/escritor.py`. Lo que se escribe son los valores **recalculados** (no los originales), y solo los registros que el programa conoce (`~V ~K ~C ~D ~T ~M`):

- Cualquier registro no soportado del archivo original (`~L` pliegos, `~G` gráficos, `~E` entidades, `~X` info técnica, `~R` residuos, paramétricos…) **desaparece** en ese primer guardado.
- El `~C` de cada concepto se escribe con su precio recalculado (los capítulos, con su coste directo **sin** CI), y el total de cada `~M` con la suma de líneas. A partir de ahí, la "referencia del archivo" para futuras validaciones ya no es la del archivo de origen.
- Las mediciones **sin líneas** (partidas alzadas) directamente no se exportan.

Las consecuencias medibles de esto están en [problemas.md](problemas.md) nº 1 y nº 2 — verificadas con un ciclo leer→guardar→releer de Alquería: el PEM cae 7.964,67 € (la partida alzada 542.0600) y la validación pasa de 0 a 38 discrepancias falsas.
