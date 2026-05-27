# BC3Manager — Architecture

## What this project is

A local desktop tool for viewing, editing and reporting on construction budgets in BC3 format (FIEBDC-3), the standard interchange format used by Presto, Arquímedes, Menfis and other Spanish construction budgeting software. Built in Python with a Flask web UI that runs locally in the browser.

The long-term goal is to add an AI layer (via tool-calling, not direct editing) that lets the user modify budgets conversationally. The current version is the foundation: a fully working BC3 reader/writer/editor with autosave.

## Project structure

```
bc3manager/
├── core/
│   └── model.py          # Data model + recalculation engine
├── io/
│   ├── lector.py          # BC3 parser (FIEBDC-3 reader)
│   └── escritor.py        # BC3 writer (FIEBDC-3 export)
├── reports/
│   └── informes.py        # HTML report generators (4 types)
├── cli.py                 # Command-line interface
└── web.py                 # Flask web UI (single file: server + HTML + JS)
```

## Core concepts

### The budget tree

A budget (Presupuesto) is a tree of Concepts (Concepto). Each concept has a type:

- **CAPITULO** — chapter/group node. Contains other chapters or partidas. Code usually ends with `#`.
- **PARTIDA** — work unit. Has a decomposition (child resources) and measurements. Has a unit (m, m2, m3, kg...).
- **UNITARIO** — leaf resource: labor (mano de obra), material, or machinery. Has a fixed price.

The tree looks like:
```
OBRA## (root)
├── 01# Movimiento de tierras (CAPITULO)
│   ├── E0101 Excavación en zanja (PARTIDA)
│   │   ├── MO001 Peón ordinario (UNITARIO) × 0.25 h
│   │   └── MQ001 Retroexcavadora (UNITARIO) × 0.15 h
│   └── E0102 Relleno (PARTIDA)
└── 02# Drenaje (CAPITULO)
```

### Price recalculation

Prices propagate **bottom-up deterministically**. A partida's price = sum of (child price × rendimiento). A chapter's price = sum of its children's prices. This is done in `Presupuesto.recalcular()`.

**Critical exception for Presto 8.8 files:** These files store pre-calculated prices in the `~C` record for chapters and don't include `~M` (measurement) records. The parser stores the original price in `_precio_bc3` and `recalcular()` respects it for nodes where `'#' in codigo`. See the `precio_de()` function inside `recalcular()`.

### Measurements

A partida can have measurement lines (LineaMedicion) within a parent chapter. Each line has: comentario, n_uds, longitud, anchura, altura. The subtotal = product of non-zero factors. The total measurement = sum of line subtotals. The importe = price × measurement.

### The `_importe_recursivo` method

This is the key method for calculating importes up the tree. It handles two cases:
1. Chapter with children → recursively sum children's importes
2. Partida → price × measurement

Both cases have a fallback: if the calculated result is 0 but the concept has `precio_es_dato=True` and `precio > 0`, use the stored price. This handles Presto 8.8 files.

## BC3 format (FIEBDC-3)

Text-based format. Each record starts with `~` + letter. Fields separated by `|`. Subfields by `\`.

Records we handle:
- `~V` — Version/header
- `~K` — Coefficients (read but not applied in v1)
- `~C` — Concept definition: `~C|CODE|UNIT|SUMMARY|PRICE|DATE|TYPE|`
- `~D` — Decomposition: `~D|PARENT_CODE|CHILD\FACTOR\RENDIMIENTO\...|`
- `~T` — Long text/description
- `~M` — Measurements: `~M|PARENT\CHILD||TOTAL|TYPE\COMMENT\N\L\W\H\...|`

### Known Presto 8.8 quirks (already handled)

1. **No root concept with `##`** — chapters like `01#`, `02#` are top-level. Parser creates a synthetic `OBRA##` root.
2. **`#` omitted in `~D` references** — `~D|02#|02.01\1\1\` references `02.01` but the concept is `02.01#`. A post-read alias resolution pass (`_resolver_alias_hash`) fixes this.
3. **Pre-calculated chapter prices** — prices in `~C` for chapters are the real importes. No `~M` records exist. The `_precio_bc3` mechanism preserves these.
4. **Type field in `~C`** — field 6 indicates: 0=unclassified, 1=labor, 2=machinery, 3=material, 5=chapter, 6=lump sum. Stored as `_tipo_fiebdc`.

Encoding: cp1252 (ANSI) or cp850 (DOS). Auto-detected from `~V`.

## Web interface (web.py)

Single-file Flask app. The HTML template is embedded as `HTML_TEMPLATE` (a raw string).

### Architecture

- Flask serves the HTML page and a JSON API
- All state lives in `_estado` dict (single-user, local)
- Frontend is vanilla JS (no framework)
- Editable cells use `contentEditable` spans with class `ecell`
- Every edit calls `POST /api/editar` with `{accion, ...params}`
- After every successful edit, `_autoguardar()` writes the BC3 back to the original file

### API endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Serve the HTML page |
| POST | `/api/cargar` | Upload and parse a BC3 file |
| POST | `/api/cargar_local` | Load file passed as CLI argument |
| GET | `/api/tiene_archivo` | Check if a file was passed as argument |
| POST | `/api/editar` | All edit operations (single endpoint) |
| GET | `/api/informe?tipo=X` | Generate HTML report |
| GET | `/api/exportar` | Download BC3 file |

### Edit actions (via `/api/editar`)

The `accion` field determines the operation:
- `precio` — change unit price
- `resumen` — change description
- `unidad` — change unit of measure
- `codigo` — rename concept code (updates all references)
- `rendimiento` — change rendimiento in decomposition
- `medicion` — change a measurement line field
- `add_linea_medicion` / `eliminar_linea_medicion`
- `add_partida` / `add_capitulo` / `eliminar_concepto`

### Frontend inline editing

Editable cells are `<span class="ecell" contenteditable="true">`. Navigation:
- Tab/Shift+Tab: move between cells
- Enter: confirm and move to next
- Arrow up/down: move within same table column
- Escape: cancel
- Focus selects cell content via `Range.selectNodeContents()`

### Theme

Dark/light toggle. CSS variables in `:root` (dark) and `html[data-theme=light]`. Persisted in localStorage.

## Reports (informes.py)

Four HTML reports, all generated from the in-memory Presupuesto:
1. **mediciones** — measurement lines per partida
2. **cuadro** — unit price table (partidas + unitarios)
3. **presupuesto** — full budget with chapters, measurements, prices, importes
4. **resumen** — importe per chapter + PEM total

## What's NOT implemented yet

- Applying `~K` coefficients (CI, GG, BI) to calculations
- Certifications (tipo_datos "3") as a separate workflow
- Parametric concepts, multiple alternative prices, non-EUR currencies
- Supplementary FIEBDC records (`~O`, `~L`, `~G`, `~E`, `~X`)
- Undo/redo
- AI conversational editing layer (future phase)

## Design principles

1. **Totals are always deterministic.** The recalculation engine, not the user or AI, computes all derived values.
2. **The original file is the source of truth.** Autosave writes back after every edit. No separate database.
3. **BC3 compatibility over features.** If a feature would break round-trip BC3 compatibility, don't add it.
4. **AI operates via tools, not direct editing.** When the AI layer is added, it will call operations like `modificar_precio()`, never edit the data structure directly. This keeps calculations auditable.

## Development

```bash
# Run tests
python tests/test_basico.py

# Run web UI
python -m bc3manager.web

# Run web UI with file
python -m bc3manager.web path/to/file.bc3

# CLI commands
python -m bc3manager.cli info file.bc3
python -m bc3manager.cli arbol file.bc3
python -m bc3manager.cli informe file.bc3 --tipo presupuesto --abrir
python -m bc3manager.cli exportar file.bc3 --salida output.bc3
```

## Dependencies

- Python >= 3.10
- Flask >= 3.0 (only dependency)
- No frontend framework (vanilla JS)
