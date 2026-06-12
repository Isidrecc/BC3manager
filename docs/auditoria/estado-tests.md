# Estado de los tests

> Fecha: 2026-06-11. Diagnóstico de solo lectura — no se ha tocado ningún test.

## Lo primero: los tests SÍ funcionan

Ejecutados dos veces durante esta auditoría: **25/25 correctos**.

```bash
python3 tests/test_basico.py
```

### Por qué podía parecer que no funcionaban

1. **`python` no existe en este Mac** — solo `python3`. La documentación antigua (anterior a junio de 2026) decía `python tests/test_basico.py`; eso da `command not found`, que se confunde fácilmente con "los tests están rotos". Es la causa más probable de la sospecha.
2. Los tests deben lanzarse **desde la raíz del repositorio** (importan `bc3manager` por ruta relativa); desde otra carpeta fallan con `ModuleNotFoundError`.
3. Los 10 tests `test_alqueria_*` y `test_presto88_*` **se saltan en silencio** si faltan `tests/Test_Alqueria.bc3` o `tests/Test_SONFONT.bc3` (salen como OK sin comprobar nada). En una copia del repo sin esos BC3, el "25/25 OK" cubre menos de lo que parece.

## Qué cubre cada test (mapa test → qué protege)

Único archivo: `tests/test_basico.py`, sin frameworks (se ejecuta directo con `python3`). Tres grupos:

### Con `ejemplo_son_font.bc3` (sintético, SIN `~K`: no cubre redondeos ni CI)

| Test | Qué protege |
|------|-------------|
| `test_lectura_basica` | Lectura: 11 conceptos, raíz `OBRA##` |
| `test_precios_unitarios_dato` | Los precios de recursos hoja son dato y no se tocan |
| `test_recalculo_descomposicion` | Precio de partida = suma de su desglose |
| `test_medicion` | Total de medición = suma de líneas (150 m³) |
| `test_total` | PEM esperado: 4.523,25 € |
| `test_validar_precios_sin_discrepancias` / `..._detecta_discrepancia` | La validación archivo-vs-calculado y su sensibilidad |
| `test_rendimiento_cero_se_conserva` / `test_round_trip_conserva_rendimiento_cero` | Un rendimiento 0 explícito no se convierte en 1 (ni al reescribir) |
| `test_round_trip` | Leer→escribir→releer conserva conceptos y PEM |
| `test_add_partida_no_crashea` | Operación de edición `add_partida` |
| `test_lineas_porcentaje_medios_auxiliares` | Líneas `%` sobre el acumulado del desglose |
| `test_recurso_nuevo_tipo_fiebdc` / `test_export_estructura_presto` | El BC3 exportado lleva tipo de recurso y estructura que Presto 8.8 acepta |

### Con BC3 sintéticos propios del `~K`

| Test | Qué protege |
|------|-------------|
| `test_redondeos_k_distintos` | Lectura del campo 1 del `~K` (¡con el orden propio del programa — ver [problemas.md](problemas.md) nº 4: si la norma tiene razón, este test blinda una interpretación equivocada!) |
| `test_round_trip_conserva_redondeos_k` | El `~K` se reescribe y los decimales sobreviven al round-trip (solo campo 1 — el campo 3 no, ver problemas nº 5) |

### Con BC3 reales (`Test_Alqueria.bc3` Presto 20, `Test_SONFONT.bc3` Presto 8.8)

| Test | Qué protege |
|------|-------------|
| `test_alqueria_coeficientes_del_registro_K` | CI/GG/BI/IVA del campo 2 (6/13/6/21) |
| `test_alqueria_decimales_del_campo3_K` | DN/DD/DS/DSP del campo 3 |
| `test_alqueria_ci_por_partida` | `round(CD × 1,06)`: 301.0010 → 9,39 €, también con `%CI` interno |
| `test_alqueria_redondeo_dimensiones_medicion` | Factores redondeados antes de multiplicar (0,0475 → 0,05) |
| `test_alqueria_partida_alzada_sin_lineas` | `~M` sin líneas usa el total declarado (solo LECTURA — la escritura la pierde, problemas nº 1) |
| `test_alqueria_sin_discrepancias_y_pem` | 0 discrepancias y PEM a <0,05% del archivo |
| `test_alqueria_partida_con_descomposicion_sin_unidad` | Clasificación partida/capítulo en casos raros |
| `test_alqueria_consistencia_k_detecta_decimales` | El aviso de conformidad con el `~K` |
| `test_presto88_sin_ci_sigue_exacto` | Con `ci_pct=0` no se aplica recargo y el PEM cuadra |

## Qué NO está cubierto (huecos relevantes, en orden de importancia)

1. **Round-trip de los BC3 reales.** El ciclo leer→escribir→releer solo se prueba con el ejemplo sintético. Un `test_alqueria_round_trip` habría cazado la pérdida de la partida alzada (−7.964,67 € de PEM) y la degradación de la validación tras guardar ([problemas.md](problemas.md) nº 1 y 2). Es el hueco nº 1.
2. **La escritura del campo 3 del `~K`** (DN/DD) — problemas nº 5.
3. **Tipos de línea de medición** 1/2/3 (subtotales, fórmulas) — problemas nº 6.
4. **La vía de respaldo del CI** (`%CI` sin `~K`) y su posible doble cómputo — problemas nº 3.
5. **Toda la capa web** (`web.py`: endpoints, autoguardado, undo/redo, informes de validación) no tiene ni un test — se verifica solo a mano.
6. Decimales negativos del `~K`, sinónimos de código, porcentajes con máscara — problemas nº 7, 8, 9.

## Recomendación (para una futura sesión de código, no para esta)

Antes de tocar el escritor para corregir los problemas 1-2, escribir primero los tests de round-trip sobre `Test_Alqueria.bc3` (PEM idéntico, mismo nº de mediciones, validación limpia tras releer). Así la corrección nace blindada. El modo `--round-trip` especificado en [spec-script-comparacion.md](spec-script-comparacion.md) daría esto casi gratis.
