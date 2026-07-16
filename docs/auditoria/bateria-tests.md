# Batería de tests: diseño

> **Documento de diseño** (sesión de documentación, 2026-06-14). Propone **cómo**
> queremos testear de aquí en adelante; **no** describe lo que hay hoy (eso está
> en [estado-tests.md](estado-tests.md)). Implementar esto es una **sesión de
> código** aparte: aquí solo se diseña el catálogo y se justifica cada test.
> Los problemas que se citan (nº 1-18) son los de [registro-bugs.md](registro-bugs.md).

## La idea en una frase

Pasar la **misma batería de comprobaciones por muchos archivos `.bc3` reales** y
distintos, para cazar en cada uno los problemas que **ya sabemos que pueden
ocurrir**, en vez de clavar valores a mano archivo por archivo. Un BC3 nuevo se
añade al corpus y automáticamente pasa por todas las comprobaciones genéricas.

## Cómo cambia respecto a hoy

| Hoy | Objetivo |
|---|---|
| 27 tests, casi todos atados a **un** archivo y a valores concretos | 3 familias: **paramétricos** (mismo test, todos los archivos), **dirigidos** (valores clavados de regresión) y **edición/autoguardado** (hoy sin tests) |
| Si falta un `.bc3`, el test se salta **en silencio** y suma como OK | Los saltos son **ruidosos**: al final se lista qué archivos se probaron y qué comprobaciones corrieron, para que "todo verde" signifique algo |
| El ejemplo sintético sin `~K` da falsa confianza | El corpus son archivos reales de varios programas + un fixture sintético mínimo **con `~K`** para los casos límite controlados |

**Principio:** cada test tiene **un** objetivo y caza **un** tipo de problema. Si
un test falla, su nombre y su mensaje deben decir qué se rompió y dónde.

---

## El corpus de archivos

### Qué tenemos

| Archivo | Origen | `~K` | Rasgos que ejercita |
|---|---|---|---|
| `tests/Test_Alqueria.bc3` | Real, Presto 20 (FIEBDC-2016) | Sí (CI 6 %, GG/BI/IVA, campo 3 completo) | CI por partida, cadena de redondeos, partidas alzadas, alias `#` en `~M` |
| `tests/Test_SONFONT.bc3` | Real, Presto 8.8 | No | Sin CI, sin `~M`, precios de capítulo precalculados, líneas `%MA`, alias `#` en `~D` |
| `tests/Test_REDONDEO.bc3` | Sintético | Sí (cada decimal distinto) | Lectura del campo 1 del `~K`, redondeo paso a paso |

Los tres archivos reales **están commiteados** en el repo (`git ls-files`), así que
la batería siempre tiene casos que probar sin depender de copias externas.

### Decisión sobre `ejemplo_son_font.bc3` — ELIMINARLO (2026-06-14)

Decidido con el usuario: **se elimina del repo** (también su generador
`scripts/gen_ejemplo.py` queda sin uso). Motivo: sin `~K` no toca el CI ni los
redondeos —lo serio del programa— y daba falsa confianza (era responsable de buena
parte del "25/25 OK"). Como los tres `.bc3` reales están commiteados, quitarlo
**no** deja la batería sin casos.

Implicaciones para la **sesión de código** que lo ejecute:

- Hay que **reescribir o retirar los ~9 tests** que hoy lo usan (`test_lectura_basica`,
  `test_total`, `test_recalculo_descomposicion`, `test_medicion`,
  `test_precios_unitarios_dato`, `test_validar_precios_*`, `test_add_partida_no_crashea`,
  `test_recurso_nuevo_tipo_fiebdc`, `test_round_trip`). Sus objetivos no se pierden:
  pasan a ser tests **paramétricos** (P1-P18) sobre el corpus real.
- **Consecuencia a cubrir:** este archivo era el **único** que disparaba el bug
  latente del escritor (siempre emite `~K`, y un archivo sin él gana redondeo al
  guardarse: 4.523,25 → 4.524,00). Test_SONFONT también es sin `~K` pero su PEM no
  se desplaza (sus precios ya están a 2 decimales). Al eliminar el de juguete,
  conviene **abrir una entrada en [registro-bugs.md](registro-bugs.md)** para ese
  comportamiento del escritor y, si se quiere seguir cazándolo, sumar al corpus un
  `.bc3` real **sin `~K` y con precios de más de 2 decimales** (la prueba P9 lo
  detectaría).

### Qué archivos pedir (lista de la compra por problema)

Para "ir a buscar problemas que ya sabemos que pueden pasar" hace falta corpus que
los **active**. Hoy ningún archivo dispara los bugs 3, 6, 7, 8, 9. Si me pasas
archivos de estos tipos, podremos blindarlos:

| Quiero un archivo que… | Activa / caza | Bug |
|---|---|---|
| Declare el CI como concepto `%CI` y **no** en el `~K` | Posible doble cómputo de CI | nº 3 |
| Traiga **solo campo 1** del `~K` (Presto antiguo), no campo 3 | Orden del campo 1 vs norma | nº 4 |
| Use DN/DD distintos de 2 (decimales de medición no estándar) | Pérdida del campo 3 al guardar | nº 5 |
| Tenga líneas de medición de **subtotal/fórmula** (tipo 1/2/3) | Doble conteo o medición a 0 | nº 6 |
| Use decimales **negativos** en el `~K` | Se ignoran, redondeo equivocado | nº 7 |
| Tenga **porcentajes con máscara** (`O%N0001`) o `&` | % aplicado a más líneas de la cuenta | nº 8 |
| Declare **códigos sinónimos** en el `~C` | Enlace roto, concepto fantasma | nº 9 |
| Sea de **otro programa** (Arquímedes/CYPE, Menfis, TCQ, Gest) | Rarezas de parser distintas de Presto | — |
| Sea una **base de datos** (BEDEC/ITeC) o una **certificación** (tipo 3) | Tipos de `~V` y flujos no contemplados | nº 10, README |
| Tenga **acentos, ñ, ç, €** y mezcle codificación cp1252/cp850 | Mojibake en el round-trip | — |

> Cuantos más programas y más variados, mejor: el valor de la batería paramétrica
> crece con cada archivo distinto que sobreviva (o que destape un fallo nuevo).

---

## Familia 1 — Tests paramétricos (el mismo test sobre CADA archivo)

Se ejecutan sobre **todos** los archivos del corpus. Si un archivo no tiene el
rasgo (p.ej. no trae `~K`), el test se **adapta o se salta con aviso**, nunca en
silencio. Son la columna vertebral del rediseño.

| # | Test | Objetivo: qué busca / qué caza | Criterio de paso | Relац. |
|---|------|-------------------------------|------------------|--------|
| P1 | **Lectura sin errores** | Que el parser no reviente con ningún archivo | Lee sin excepción, ≥1 concepto, detecta una raíz | — |
| P2 | **Raíz única y conexa** | Huérfanos, raíz mal detectada, ciclos | Hay 1 `codigo_raiz`; todo concepto cuelga de ella; sin ciclos | parser, `_detectar_raiz` |
| P3 | **Sin referencias rotas** | Enlaces `~D`/`~M` a códigos inexistentes | Todo `codigo_hijo` y todo padre de medición existe en `conceptos` | nº 9, alias `#` |
| P4 | **Sin conceptos fantasma** | Restos de alias/sinónimos no resueltos | Ningún concepto vacío (sin precio, hijos, medición ni resumen) referenciado | nº 9 |
| P5 | **Validación interna limpia** | Que NUESTRO cálculo reproduzca los números del propio archivo | `validar_completo` → 0 discrepancias de precio y medición **o** las lista como diferencias del archivo, no nuestras | invariantes 5-7 |
| P6 | **PEM archivo ≈ calculado** | Desvíos de CI/redondeo acumulados | `comparar_importes_archivo`: \|dif PEM\| < umbral (p.ej. 0,05 %) | nº 3, 4 |
| P7 | **Recálculo determinista** | Cálculo que depende del estado o del orden | Llamar `recalcular()` 2× da el mismo PEM; editar y revertir un precio devuelve el PEM exacto | invariante 2 |
| P8 | **Round-trip estructural** | Pérdida de registros al guardar | leer→escribir→releer: mismo nº de conceptos, de mediciones y de relaciones padre-hijo | nº 1, 5 |
| P9 | **Round-trip de PEM** | Pérdida/alteración de importe al guardar | PEM(original) == PEM(reescrito) a 1 céntimo | nº 1 (alzadas), escritor-`~K` |
| P10 | **Round-trip de validación** | Que guardar no estropee la referencia de validación | Tras guardar→reabrir, `validar_completo` sigue tan limpio como el original (0→0) | nº 2 |
| P11 | **Round-trip idempotente** | Drift acumulativo (cada guardado cambia algo) | leer→escribir→leer→escribir: el 2.º y 3.er estado son idénticos | nº 5, escritor |
| P12 | **Conservación del `~K`** | Pérdida de coeficientes/decimales | ci/gg/bi/iva/baja y todos los `dec_*` sobreviven al round-trip | nº 5 |
| P13 | **Conservación del `~V`** | Metadatos de cabecera | versión y tipo de datos sobreviven (y se escriben con el significado correcto) | nº 10, 11 |
| P14 | **Mediciones cuadran** | `~M` con total declarado que no casa con sus líneas | Para cada `~M` con total declarado, suma de líneas ≈ declarado (redondeo Presto) | nº 6 |
| P15 | **Números sanos** | Parsing de coma/punto/negativos, NaN/infinitos | Todo precio e importe es finito; sin negativos salvo bajas declaradas | nº 7 |
| P16 | **Clasificación coherente** | Partidas convertidas en capítulo (pierden importe) o al revés | Ningún concepto con `~M` propia clasificado como capítulo; ninguna partida con importe 0 por mala clasificación | clasificación |
| P17 | **Codificación round-trip** | Mojibake de acentos/ñ/ç/€ | Resúmenes con caracteres especiales se conservan tras escribir→releer | cp1252/cp850 |
| P18 | **Conformidad de decimales (`~K`)** | Archivos fuera de su propio `~K` (informativo) | `revisar_consistencia_k` corre sin error y reporta categorías | nº 7, 12 |

---

## Familia 2 — Tests dirigidos (valores exactos clavados)

Atados a un archivo y un concepto concretos, con el número verificado contra el
informe real del programa de origen. Son la **red de regresión** de los
invariantes 5-7: si cambian, se rompe algo del cálculo. Los actuales `test_alqueria_*`
ya son de este tipo; aquí se mantienen y se amplían cuando un archivo nuevo aporte
un caso límite verificable.

| Test | Archivo · concepto | Valor clavado | Qué fija |
|---|---|---|---|
| CI por partida | Alquería · 301.0010 | CD 8,86 → **9,39** | `round(CD × 1,06)`, incluso con `%CI` interno |
| Redondeo de dimensión | Alquería · 215.0030 | altura 0,0475→0,05 → medición **112,21** | Cada factor se redondea antes de multiplicar |
| Partida alzada | Alquería · 542.0600 | medición **1**, importe **7.964,67** | `~M` sin líneas usa el total declarado |
| Línea `%MA` | SONFONT · DEM.01.01 / MOV.02.01 | **11,17** / **11,01** | `%` sobre el acumulado del desglose |
| Decimales distintos | REDONDEO | DecImp=7, DecPar=5, Dec=4… | Lectura del campo 1 del `~K` |
| Presto 8.8 sin CI | SONFONT | `ci_pct=0`, PEM exacto | No aplicar recargo donde no toca |
| Alias `#` en `~D` y `~M` | SONFONT / Alquería | mediciones no huérfanas, PEM > 0 | Normalización del `#` de Presto |
| (nuevo, al recibir archivo) | — | — | Un valor exacto por cada bug 3/6/7/8/9 que un archivo real active |

---

## Familia 3 — Edición y autoguardado (la capa que HOY no tiene tests)

`web.py` (endpoints, autoguardado, undo/redo) y las operaciones de edición de
`model.py` no tienen **ni un test**: es el hueco nº 1 de cobertura. Estas pruebas
no necesitan navegador; ejercitan las operaciones del modelo y el ciclo de
autoguardado (escribir a disco → releer). Cada operación de `/api/editar` debería
tener su prueba.

| Test | Operación | Qué busca / caza |
|---|---|---|
| E1 | `modificar_precio` (hoja) → autoguardar → reabrir | El precio persiste y el PEM se recalcula coherente |
| E2 | `modificar_precio` sobre partida con descomposición | Debe **rechazarse** (precio calculado, no editable) |
| E3 | `modificar_codigo` | Se actualizan **todas** las referencias (hijos, mediciones, raíz); round-trip sin enlaces rotos |
| E4 | `add_partida` / `add_capitulo` | Nace con cantidad 0 (importe 0); no rompe el PEM |
| E5 | `add_recurso` / `eliminar_recurso` | Recurso con tipo FIEBDC explícito; el precio de partida cambia como debe |
| E6 | `reordenar_recurso` | El orden **no** cambia el precio… salvo si hay línea `%` (entonces SÍ, y el test lo verifica) |
| E7 | `mover_concepto` / `copiar_concepto` | No se crean ciclos; la medición se transfiere (mover) o empieza vacía (copiar) |
| E8 | `eliminar_concepto` | Desvincula del padre, **no** borra el concepto (otras referencias intactas) |
| E9 | `cambiar_tipo` capítulo↔partida | El importe se recalcula según el nuevo tipo |
| E10 | **Undo / Redo** | Tras editar→deshacer, PEM y estructura vuelven exactos; rehacer los recupera |
| E11 | **Autoguardado deja archivo válido** | Tras cualquier edición, el `.bc3` en disco se relee sin error y con los mismos números |
| E12 | **Cadena de ediciones + round-trip** | 5-10 ediciones seguidas → el archivo final sigue válido y la validación limpia (caza el drift del autoguardado) |

---

## El test estrella: ida y vuelta con informe de diferencias

El "abrir → exportar → reabrir → comparar original vs reimportado" que mencionas es
la combinación de **P8 + P9 + P10 + P11**, y es el que más fallos reales ha cazado
(las partidas alzadas, la validación rota). Conviene que, además de pasar/fallar,
**emita un informe de diferencias** cantidad a cantidad e importe a importe: qué
partidas cambiaron de precio, medición o importe entre el archivo original y el
reescrito. Eso es exactamente el modo `--round-trip` y el comando
`python -m bc3manager.cli validar archivo.bc3` especificados en
[spec-script-comparacion.md](spec-script-comparacion.md): la batería de tests y ese
comando CLI comparten el mismo motor (`validar_completo` + `comparar_importes_archivo`).
Implementarlos juntos es lo más rentable.

---

## Cómo se organizaría en el código (sin programar aún)

Para la futura sesión de código, una forma de estructurarlo:

- **Carpeta de corpus**: `tests/corpus/` con todos los `.bc3` reales; un pequeño
  manifiesto (qué programa, qué rasgos, valores esperados conocidos) por archivo.
- **Tests paramétricos**: una función por comprobación (P1-P18) que recibe la ruta
  del archivo; un *runner* la aplica a cada archivo del corpus. Con `pytest` sería
  `@pytest.mark.parametrize` sobre la lista de archivos; sin pytest, un bucle en el
  `__main__` que imprima `archivo · test · OK/FALLO`.
- **Saltos ruidosos**: si un archivo no aplica a un test (sin `~K`, sin `~M`…), se
  reporta como `SALTADO (motivo)`, no como OK. Al final, un resumen: "N archivos ×
  M comprobaciones; X corridas, Y saltadas, Z fallidas".
- **Tests dirigidos**: siguen como funciones con valores clavados (como hoy), en
  su propio archivo, separados de los paramétricos.
- **Tests de edición**: ejercitan `model.py` + el ciclo de autoguardado con un
  archivo temporal; no requieren levantar Flask.

## Qué implementar primero (orden sugerido)

1. **P1-P5 y P8-P10** sobre el corpus actual (3-4 archivos): lectura, integridad,
   validación interna y round-trip. Es la mayor red de seguridad por el menor
   esfuerzo, y reaprovecha `validar_completo`.
2. El **informe de diferencias** del round-trip / comando `validar` (spec ya escrita).
3. **E1-E3, E10, E11** (las ediciones más usadas + undo/redo + autoguardado): cubre
   el hueco de la capa web sin navegador.
4. Ampliar el **corpus** con archivos que activen los bugs 3/6/7/8/9 y añadir sus
   tests dirigidos a medida que lleguen.

> Cuando esto se implemente, [estado-tests.md](estado-tests.md) se reescribe para
> describir la nueva realidad; este documento queda como la justificación del diseño.
