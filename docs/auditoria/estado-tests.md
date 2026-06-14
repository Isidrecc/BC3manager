# Estado y cobertura de los tests

> **Documento vivo.** Mapa de qué prueba cada test, contra qué archivos lo hace,
> qué se debe correr tras cada cambio y qué queda sin cubrir. Esto es solo
> documentación: no se ha tocado ningún test.
> Última revisión: **2026-06-14 — 27/27 OK** (`python tests/test_basico.py`).
> Origen: auditoría de solo lectura del 2026-06-11 (entonces eran 25/25).

## Lo primero: los tests SÍ funcionan

Verificado el 2026-06-14: **27/27 correctos**.

```bash
python tests/test_basico.py
```

- En esta máquina (Windows) el intérprete es **`python`**. La documentación general
  usa `python3` porque se escribió en Mac; usa el comando que exista en tu equipo.
  Lanzar `python3` donde no existe (o `python` donde no existe) da
  *command not found*, que se confunde fácilmente con "los tests están rotos".
  Es la causa nº 1 de la falsa sospecha de que fallan.
- Hay que ejecutarlos **desde la raíz del repositorio** (importan `bc3manager`
  por ruta relativa); desde otra carpeta fallan con `ModuleNotFoundError`.
- **No hay framework** (ni pytest necesario): el `__main__` recorre las funciones
  `test_*`, las ejecuta y cuenta fallos. Cada test es una función con `assert`.
- **Skips silenciosos:** los tests `test_alqueria_*`, `test_presto88_*`,
  `test_redondeos_*` y los de `Test_SONFONT.bc3` hacen `return` sin avisar si su
  `.bc3` no está en `tests/`. En una copia del repo sin esos archivos, el
  "27/27 OK" cubre bastante menos de lo que parece (quedarían ~10 tests reales,
  todos sobre el ejemplo sintético).

## Contra qué se prueba: los archivos de datos

Cuatro `.bc3`. **Solo uno** (`ejemplo_son_font.bc3`) está en la raíz; los otros tres
viven en `tests/`. El archivo manda qué se puede comprobar:

| Archivo | Origen | ¿Trae `~K`? | Cubre | NO sirve para |
|---|---|---|---|---|
| `ejemplo_son_font.bc3` (raíz) | Sintético, lo genera `scripts/gen_ejemplo.py` | **No** (`redondeo_activo=False`, `ci_pct=0`) | Lectura, estructura, descomposición, medición, round-trip básico. PEM 4.523,25 € | Redondeos ni costes indirectos (sin `~K`) |
| `tests/Test_Alqueria.bc3` | **Real**, Presto 20 (FIEBDC-2016) | **Sí**: CI 6 %, GG 13 %, BI 6 %, IVA 21 %; decimales en campo 3 | **El caso principal:** CI por partida, cadena de redondeos, partidas alzadas, round-trip completo con validación. PEM 9.073.347,54 € | — |
| `tests/Test_SONFONT.bc3` | **Real**, Presto 8.8 | No | Caso "sin CI": rendimientos 0 que se conservan, líneas `%MA`, estructura que Presto 8.8 acepta al reabrir | Redondeos del `~K` |
| `tests/Test_REDONDEO.bc3` | Sintético (decimales extremos) | **Sí** (cada decimal distinto) | Lectura del campo 1 del `~K` y que cada paso redondea con su decimal | — |

**Archivos compañeros que NINGÚN test usa:** `tests/Test_SONFONT.bak` (copia de
seguridad), `tests/Test_SONFONT.xlsx` (informe de validación exportado) y
`tests/Test_SONFONT.pzh` (formato comprimido propio de Presto). Están ahí como
referencia, no son entrada de las pruebas: borrarlos no rompe nada.

> `ejemplo_son_font.bc3` es **regenerable**: `python scripts/gen_ejemplo.py`.
> Sus cifras están pensadas para casar con los `assert` (MO001 18,50; E0101
> 11,375; medición 150; 11 conceptos; PEM 4.523,25 €). No lo edites a mano.

## Qué correr tras cada cambio

Regla de fondo (en CLAUDE.md → "Testing" e invariantes 1-7, y en el flujo de
[guia-sesiones.md](../guia-sesiones.md)): **corre toda la batería** tras tocar
`core/model.py`, `io/lector.py` o `io/escritor.py`. El detalle de qué blinda qué:

| Si tocas… | Corre sobre todo… | Por qué |
|---|---|---|
| Redondeos, costes indirectos o lectura del `~K` | los `test_alqueria_*` | Están verificados contra el informe de desglose real de Presto (invariante 7). Si se rompen, NO los relajes sin entender por qué. |
| El **escritor** o cualquier cosa que afecte al guardado | `test_round_trip*` y `test_alqueria_round_trip_*` | El **autoguardado reescribe el `.bc3` original en cada edición**: un round-trip que pierda datos corrompe el archivo del usuario para siempre. |
| `_precio_bc3` / `precio_es_dato` | el ejemplo **y** un Presto 8.8 (`Test_SONFONT.bc3`) | Lo exige CLAUDE.md → "What NOT to do": son lógicas que se comportan distinto con y sin precios precalculados. |
| Clasificación capítulo/partida | `test_alqueria_partida_*`, `test_export_estructura_presto` | Una partida mal clasificada como capítulo pierde su importe. |
| La capa web (`web.py`): endpoints, undo/redo, UI | **no hay test** → verificación manual en la web | Hueco conocido (ver abajo). |

Y el flujo cuando el cambio es un arreglo (de [guia-sesiones.md](../guia-sesiones.md)):
batería en verde **antes** de tocar → escribir un test que FALLE y demuestre el
fallo → arreglo mínimo → test en verde → verificar de punta a punta con un BC3
real, con números antes/después.

## Qué cubre cada test (mapa test → qué protege)

Único archivo: `tests/test_basico.py`. Agrupado por el archivo que usa cada test.

### A) Con `ejemplo_son_font.bc3` (sintético, SIN `~K`: no cubre redondeos ni CI)

| Test | Qué protege |
|------|-------------|
| `test_lectura_basica` | Lectura: 11 conceptos, raíz `OBRA##`, versión `FIEBDC-3/2024` |
| `test_precios_unitarios_dato` | Los precios de recursos hoja son dato y no se tocan |
| `test_recalculo_descomposicion` | Precio de partida = suma de su desglose (11,375) |
| `test_medicion` | Total de medición = suma de líneas (150 m³) |
| `test_total` | PEM esperado: 4.523,25 € |
| `test_validar_precios_sin_discrepancias` / `…_detecta_discrepancia` | La validación archivo-vs-calculado y su sensibilidad |
| `test_add_partida_no_crashea` | Edición `add_partida` (la partida nueva nace con cantidad 0) |
| `test_recurso_nuevo_tipo_fiebdc` | Un recurso añadido se exporta con tipo FIEBDC explícito (no vacío) |
| `test_round_trip` | Leer→escribir→releer conserva conceptos y precios hoja |

### B) Con `Test_SONFONT.bc3` (real, Presto 8.8, sin `~K`)

| Test | Qué protege |
|------|-------------|
| `test_rendimiento_cero_se_conserva` / `test_round_trip_conserva_rendimiento_cero` | Un rendimiento 0 explícito no se convierte en 1 (ni al reescribir); el PEM se mantiene |
| `test_lineas_porcentaje_medios_auxiliares` | Líneas `%MA` sobre el acumulado del desglose (DEM.01.01 → 11,17; MOV.02.01 → 11,01) |
| `test_export_estructura_presto` | El `~C` de partida pegado a su `~D`, `~M` con posición, y tipos FIEBDC de recursos — para que Presto no reclasifique al reabrir |
| `test_presto88_sin_ci_sigue_exacto` | Con `ci_pct=0` no se aplica recargo y el PEM cuadra exacto |

### C) Con `Test_REDONDEO.bc3` (sintético, `~K` con decimales distintos)

| Test | Qué protege |
|------|-------------|
| `test_redondeos_k_distintos` | Lectura del campo 1 del `~K` y que precios e importes salen exactos (ver [registro-bugs.md](registro-bugs.md) nº 4: el orden de ese campo difiere de la norma) |
| `test_round_trip_conserva_redondeos_k` | El `~K` se reescribe y los decimales sobreviven al round-trip (solo campo 1 — el campo 3 aún no, ver nº 5) |

### D) Con `Test_Alqueria.bc3` (real, Presto 20 / FIEBDC-2016, `~K` completo)

| Test | Qué protege |
|------|-------------|
| `test_alqueria_coeficientes_del_registro_K` | CI/GG/BI/IVA del campo 2 (6/13/6/21) |
| `test_alqueria_decimales_del_campo3_K` | DD/DN/DS/DSP del campo 3 |
| `test_alqueria_ci_por_partida` | `round(CD × 1,06)`: 301.0010 → 9,39 €, también con `%CI` interno |
| `test_alqueria_redondeo_dimensiones_medicion` | Factores redondeados antes de multiplicar (altura 0,0475 → 0,05; medición 112,21) |
| `test_alqueria_partida_alzada_sin_lineas` | `~M` sin líneas usa el total declarado (lectura): 542.0600 → medición 1, importe 7.964,67 |
| `test_alqueria_round_trip_conserva_partida_alzada` | **(nuevo)** El ciclo guardar→reabrir conserva PEM, las 283 mediciones y la alzada 542.0600 — blinda el bug nº 1 |
| `test_alqueria_round_trip_validacion_limpia` | **(nuevo)** Tras guardar→reabrir, la validación sigue a 0 discrepancias y el PEM cuadrado — blinda lo que describía el bug nº 2 |
| `test_alqueria_sin_discrepancias_y_pem` | 0 discrepancias y PEM a < 0,05 % del archivo |
| `test_alqueria_partida_con_descomposicion_sin_unidad` | Clasificación partida/capítulo en casos raros (701.0236a) |
| `test_alqueria_consistencia_k_detecta_decimales` | El aviso de conformidad con el `~K` |

## Qué NO está cubierto (huecos, en orden de importancia)

> El hueco nº 1 del diagnóstico del 2026-06-11 —**round-trip de los BC3
> reales**— **ya está cubierto** por los dos `test_alqueria_round_trip_*`
> añadidos al arreglar las partidas alzadas. La lista de abajo es la actual.

1. **Toda la capa web** (`web.py`): endpoints, autoguardado, undo/redo, informes
   de validación. No tiene ni un test — se verifica solo a mano. Aquí caen
   también los tres bugs de interfaz ([registro-bugs.md](registro-bugs.md)
   nº 16-18). Es el hueco nº 1 hoy.
2. **La escritura del campo 3 del `~K`** (DN/DD) — registro-bugs nº 5. Con
   Alquería no se nota porque casualmente trae DN=DD=2.
3. **Tipos de línea de medición** 1/2/3 (subtotales, fórmulas) — nº 6. Ningún
   archivo de los tests trae estos tipos.
4. **La vía de respaldo del CI** (`%CI` sin `~K`) y su posible doble cómputo — nº 3.
5. **Decimales negativos del `~K`, sinónimos de código, porcentajes con
   máscara** — nº 7, 8, 9. Sin archivo real que los active.

## Recomendación

Los tests de round-trip sobre BC3 reales —que en el diagnóstico anterior eran la
recomendación principal— ya existen y blindan los arreglos del escritor. El
siguiente blindaje con más retorno sería **un primer test de la capa web**
(aunque sea arrancar el servidor, abrir un archivo y comprobar que el
autoguardado deja el `.bc3` válido), porque es la única parte del programa que
toca el archivo del usuario sin red de seguridad automática. El modo
`--round-trip` y el comando `validar` de la CLI especificados en
[spec-script-comparacion.md](spec-script-comparacion.md) darían parte de esto casi gratis.
