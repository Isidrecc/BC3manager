# CLAUDE.md

## Qué es este proyecto

BC3Manager: visor/editor local de presupuestos BC3 (FIEBDC-3) con interfaz web Flask. Herramienta del sector de la construcción español (presupuestos, mediciones, certificaciones).

- Documentación técnica en `docs/`: `arquitectura.md` (módulos y flujo), `api-interna.md` (operaciones y endpoints), `formato-bc3.md` (formato y rarezas de Presto), `decisiones.md` (decisiones de diseño y su porqué). En la raíz solo README, CHANGELOG y este archivo.
- La especificación oficial del formato está en `FIEBDC/2024/Documentos-complementarios` (fuente de verdad del formato; hay también versiones 2016 y 2020).

## Stack

- Python >= 3.10. Única dependencia: Flask >= 3.0 (ver `pyproject.toml`). Opcional: `weasyprint` para PDF.
- Frontend: HTML/CSS/JS vanilla embebido en `web.py` como r-string. Sin React, sin npm, sin bundler. Carga Tabulator 6.3 y Google Fonts desde CDN (necesita internet para eso).
- Sin base de datos: el archivo `.bc3` original es la persistencia (autoguardado tras cada edición).
- En esta máquina el intérprete es `python3` (no existe el comando `python`).

## Arrancar en local

```bash
python3 tests/test_basico.py            # Tests (siempre tras tocar core/ o io/)
python3 -m bc3manager.web               # Web UI en http://127.0.0.1:5000 (puerto: env PORT)
python3 -m bc3manager.web archivo.bc3   # Web con archivo precargado + autoguardado
python3 -m bc3manager.cli info archivo.bc3   # CLI: info | arbol | informe | exportar
```

El servidor abre el navegador solo, en `127.0.0.1` (no `localhost`, que en algunos equipos da 403).

## Estructura

- `bc3manager/core/model.py` — Modelo de datos (Presupuesto, Concepto, Hijo, Medicion). TODO el recálculo vive aquí.
- `bc3manager/io/lector.py` — Parser BC3. Lee `~V ~K ~C ~D ~T ~M`; el resto de registros se ignora. Codificación cp1252/cp850 autodetectada del `~V`.
- `bc3manager/io/escritor.py` — Escritor BC3 (cp1252, CRLF).
- `bc3manager/reports/informes.py` — 4 informes HTML: mediciones, cuadro de precios, presupuesto, resumen.
- `bc3manager/web.py` — Un solo archivo: servidor Flask + frontend embebido (`HTML_TEMPLATE`) + undo/redo por snapshots + informes de validación (Excel y .txt) al abrir archivo.
- `bc3manager/cli.py` — Interfaz de línea de comandos.
- `scripts/gen_ejemplo.py` — Regenera `ejemplo_son_font.bc3` (archivo de muestra de los tests).
- `tests/test_basico.py` — Único archivo de tests. Junto a él, BC3 reales de prueba (`Test_Alqueria.bc3`, `Test_SONFONT.bc3`, `Test_REDONDEO.bc3`).

## Invariantes críticos

1. **Never let the UI or AI compute totals.** All prices/importes come from `Presupuesto.recalcular()` or `_importe_recursivo()`.
2. **Los precios del archivo NO mandan en el cálculo.** El precio de capítulo precalculado del `~C` se guarda en `_precio_bc3`, pero `recalcular()` y `_importe_recursivo()` suman SIEMPRE de abajo arriba (PEM determinista: editar y revertir un valor devuelve el PEM inicial). `_precio_bc3` se usa solo para la validación archivo-vs-calculado (`comparar_importes_archivo`, informes de validación). Una partida sin medición tiene importe 0, sin fallbacks. `test_presto88_sin_ci_sigue_exacto` blinda que con `ci_pct=0` el PEM cuadra con el archivo.
3. **Autosave:** every edit via `/api/editar` triggers `_autoguardar()` which writes the BC3 back to the original file path. Undo/redo (`/api/undo`, `/api/redo`) funciona por snapshots del BC3 serializado.
4. **BC3 round-trip:** after read→write→read, data must be preserved. Test with `test_round_trip`.
5. **Coeficientes y redondeos: SIEMPRE del registro `~K`, nunca hardcodeados.** El `~K` tiene 3 campos; la norma FIEBDC-2016 obliga a leer el **campo 3** (completo) y, en su defecto, el campo 1/2. `lector.py::_reg_K` lo hace.
   - **Campo 2** → coeficientes `CI \ GG \ BI \ BAJA \ IVA` (en %). Solo el **CI** (costes indirectos) afecta al PEM. GG/BI/IVA se guardan para PEC/IVA futuros, NO se usan aún en el cálculo.
   - **Campo 3** → todos los decimales (`DRC DC DFS DRS DUO DI DES DN DD DS DSP DEC`); ojo a los 2 huecos vacíos del patrón.
6. **CI por partida (FIEBDC: precio UO = Coste Directo + Coste Indirecto).** `precio_con_ci()` = `round(CD × (1+ci_pct), DecPar)`. Se aplica a **TODAS** las partidas, incluidas las que ya llevan una línea `%CI`/medios auxiliares en su `~D` (esa línea es un coste más del CD, NO el CI global — no la excluyas). El importe del capítulo es la suma de los importes de sus hijos (sin CI extra). Con `ci_pct=0` (Presto 8.8) no cambia nada.
7. **Redondeo como Presto: en cada paso, en DECIMAL exacto, mitad-arriba.** Usa `_redondea`/`_mult_red` (no `round()` de Python, que es bancario y arrastra error de float). Líneas de medición: redondear CADA factor antes de multiplicar — dimensiones a `dec_dim` (DD), nº de partes a `dec_num` (DN) — luego el parcial a `dec_parcial` (DSP) y el total a `dec_cantmed` (DS). Ver `parcial_linea`/`total_medicion`. Una `~M` sin líneas usa el `total_declarado` (partidas alzadas).
   No toques esta cadena sin correr los tests `test_alqueria_*`, que la fijan contra el informe real de Presto (301.0010→9,39; 215.0030 medición→112,21; PEM Alquería a <0,05%).

## Rarezas conocidas del parser y de Presto

- **Presto 8.8:** no hay concepto raíz `##` (el lector crea un `OBRA##` sintético); el `#` se omite en las referencias del `~D` (`02.01` en vez de `02.01#`, resuelto en `_resolver_alias_hash`); los capítulos traen precio precalculado en el `~C` y no hay registros `~M`.
- **Presto 20 / FIEBDC-2016:** el alias `#` aparece también en `~M` (`~M|001\...` con concepto `001#`); si no se normaliza, las mediciones quedan huérfanas y el PEM sale 0. Trae CI global en el campo 2 del `~K` (p.ej. 6%).
- **Campo 6 del `~C`** = tipo FIEBDC: 0 sin clasificar, 1 mano de obra, 2 maquinaria, 3 material, 5 capítulo, 6 partida alzada. Se guarda en `_tipo_fiebdc`.
- **Clasificación capítulo/partida:** un concepto con `~M` propia es PARTIDA (regla previa a mirar descomposición/unidad; los capítulos nunca llevan `~M` real). Un concepto es CAPÍTULO si sus hijos se miden dentro de él o son subcapítulos — así un capítulo con "medición fantasma de 1" (Prestos antiguos) sigue siendo capítulo.
- **Líneas de porcentaje** (`%MA`, medios auxiliares): se aplican sobre el acumulado de las líneas anteriores de la descomposición, no como precio×rendimiento. Ver `es_porcentaje` y el bucle de `recalcular()`.

## Convenciones de trabajo

- **Commits: Conventional Commits**, pequeños y atómicos (un cambio lógico por commit): `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`. Mensaje en imperativo y específico (`fix: alias # en ~M de Presto 20`, no `cambios`).
- **Claude NUNCA commitea.** El usuario commitea con GitHub Desktop. Claude deja los cambios en el working tree y sugiere el mensaje de commit.
- **Sesiones separadas:** documentar y cambiar código se hace en sesiones distintas. En una sesión de documentación, `bc3manager/`, `scripts/` y `tests/` son SOLO LECTURA (solo se escriben los `.md` de la raíz y `docs/`). En una sesión de código no se reescribe documentación de fondo (solo el CHANGELOG si procede).
- El usuario no revisa código: verifica a prueba y error. Explica los cambios en lenguaje claro y comprueba tú mismo con los tests antes de dar algo por hecho.

## Style notes

- Backend comments and variable names in Spanish (matching the domain).
- The web.py HTML template is a Python raw string (r-string). Be careful with backslashes.
- CSS uses CSS variables for theming (dark/light). All colors must use `var(--name)`.
- Frontend is vanilla JS. No React, no framework. Keep it that way for simplicity.

## Testing

Run `python3 tests/test_basico.py` after any change to model.py, lector.py or escritor.py. There's a sample file `ejemplo_son_font.bc3` for testing (regenerable with `python3 scripts/gen_ejemplo.py`). Expected PEM total: 4.523,25 €.

Los tests `test_alqueria_*` usan `tests/Test_Alqueria.bc3` (Presto 20 / FIEBDC-2016 real, con CI y redondeos) y **blindan** el comportamiento de costes indirectos y redondeo de los invariantes 5-7. Si tocas CI, redondeos o lectura del `~K` y se rompen, NO los relajes sin entender por qué: los valores están verificados contra el informe de desglose de precios de Presto. Si `Test_Alqueria.bc3` no está, esos tests se saltan solos.

## What NOT to do

- Don't add a database. The BC3 file is the persistence layer.
- Don't add npm/webpack/bundler. The frontend is intentionally a single embedded HTML string.
- Don't change the `_precio_bc3` / `precio_es_dato` logic without testing against both `ejemplo_son_font.bc3` AND a Presto 8.8 file (no root, no measurements, pre-calculated chapter prices), e.g. `tests/Test_SONFONT.bc3`.
