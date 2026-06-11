# CLAUDE.md

## Project overview

BC3Manager: local BC3 (FIEBDC-3) budget viewer/editor with Flask web UI. Spanish construction industry tool.

Read ARCHITECTURE.md for full technical context.

## Key commands

```bash
python tests/test_basico.py          # Run tests (always run after changes to core/)
python -m bc3manager.web             # Start web UI on localhost:5000
python -m bc3manager.web file.bc3    # Start with file pre-loaded + autosave
```

## Code layout

- `bc3manager/core/model.py` — Data model. Presupuesto, Concepto, Medicion. All recalculation logic lives here.
- `bc3manager/io/lector.py` — BC3 parser. Handles Presto 8.8 quirks (no root ##, # alias in ~D, pre-calculated prices).
- `bc3manager/io/escritor.py` — BC3 writer.
- `bc3manager/reports/informes.py` — 4 HTML report generators.
- `bc3manager/web.py` — Flask server + embedded HTML/JS frontend (single file).
- `bc3manager/cli.py` — CLI interface.

## Critical invariants

1. **Never let the UI or AI compute totals.** All prices/importes come from `Presupuesto.recalcular()` or `_importe_recursivo()`.
2. **Presto 8.8 compatibility:** chapters with `_precio_bc3 > 0` must keep their original price. Don't break the `precio_de()` logic in `recalcular()`.
3. **Autosave:** every edit via `/api/editar` triggers `_autoguardar()` which writes the BC3 back to the original file path.
4. **BC3 round-trip:** after read→write→read, data must be preserved. Test with `test_round_trip`.
5. **Coeficientes y redondeos: SIEMPRE del registro `~K`, nunca hardcodeados.** El `~K` tiene 3 campos; la norma FIEBDC-2016 obliga a leer el **campo 3** (completo) y, en su defecto, el campo 1/2. `lector.py::_reg_K` lo hace.
   - **Campo 2** → coeficientes `CI \ GG \ BI \ BAJA \ IVA` (en %). Solo el **CI** (costes indirectos) afecta al PEM. GG/BI/IVA se guardan para PEC/IVA futuros, NO se usan aún en el cálculo.
   - **Campo 3** → todos los decimales (`DRC DC DFS DRS DUO DI DES DN DD DS DSP DEC`); ojo a los 2 huecos vacíos del patrón.
6. **CI por partida (FIEBDC: precio UO = Coste Directo + Coste Indirecto).** `precio_con_ci()` = `round(CD × (1+ci_pct), DecPar)`. Se aplica a **TODAS** las partidas, incluidas las que ya llevan una línea `%CI`/medios auxiliares en su `~D` (esa línea es un coste más del CD, NO el CI global — no la excluyas). El importe del capítulo es la suma de los importes de sus hijos (sin CI extra). Con `ci_pct=0` (Presto 8.8) no cambia nada.
7. **Redondeo como Presto: en cada paso, en DECIMAL exacto, mitad-arriba.** Usa `_redondea`/`_mult_red` (no `round()` de Python, que es bancario y arrastra error de float). Líneas de medición: redondear CADA factor antes de multiplicar — dimensiones a `dec_dim` (DD), nº de partes a `dec_num` (DN) — luego el parcial a `dec_parcial` (DSP) y el total a `dec_cantmed` (DS). Ver `parcial_linea`/`total_medicion`. Una `~M` sin líneas usa el `total_declarado` (partidas alzadas).
   No toques esta cadena sin correr los tests `test_alqueria_*`, que la fijan contra el informe real de Presto (301.0010→9,39; 215.0030 medición→112,21; PEM Alquería a <0,05%).

## Style notes

- Backend comments and variable names in Spanish (matching the domain).
- The web.py HTML template is a Python raw string (r-string). Be careful with backslashes.
- CSS uses CSS variables for theming (dark/light). All colors must use `var(--name)`.
- Frontend is vanilla JS. No React, no framework. Keep it that way for simplicity.

## Testing

Run `python tests/test_basico.py` after any change to model.py, lector.py or escritor.py. There's a sample file `ejemplo_son_font.bc3` for testing (regenerable with `python scripts/gen_ejemplo.py`). Expected PEM total: 4.523,25 €.

Los tests `test_alqueria_*` usan `tests/Test_Alqueria.bc3` (Presto 20 / FIEBDC-2016 real, con CI y redondeos) y **blindan** el comportamiento de costes indirectos y redondeo de los invariantes 5-7. Si tocas CI, redondeos o lectura del `~K` y se rompen, NO los relajes sin entender por qué: los valores están verificados contra el informe de desglose de precios de Presto. Si `Test_Alqueria.bc3` no está, esos tests se saltan solos.

## What NOT to do

- Don't add a database. The BC3 file is the persistence layer.
- Don't add npm/webpack/bundler. The frontend is intentionally a single embedded HTML string.
- Don't change the `_precio_bc3` / `precio_es_dato` logic without testing against both the SuDS example file AND a Presto 8.8 file (no root, no measurements, pre-calculated chapter prices).
