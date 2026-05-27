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

## Style notes

- Backend comments and variable names in Spanish (matching the domain).
- The web.py HTML template is a Python raw string (r-string). Be careful with backslashes.
- CSS uses CSS variables for theming (dark/light). All colors must use `var(--name)`.
- Frontend is vanilla JS. No React, no framework. Keep it that way for simplicity.

## Testing

Run `python tests/test_basico.py` after any change to model.py, lector.py or escritor.py. There's a sample file `ejemplo_son_font.bc3` for testing. Expected PEM total: 4.815,45 €.

## What NOT to do

- Don't add a database. The BC3 file is the persistence layer.
- Don't add npm/webpack/bundler. The frontend is intentionally a single embedded HTML string.
- Don't change the `_precio_bc3` / `precio_es_dato` logic without testing against both the SuDS example file AND a Presto 8.8 file (no root, no measurements, pre-calculated chapter prices).
