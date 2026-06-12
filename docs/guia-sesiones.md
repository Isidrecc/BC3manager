# Guía de sesiones de trabajo con IA

> Plantillas de prompt para iniciar sesiones. Hay dos tipos de sesión y **no se mezclan**: en una sesión de documentación el código es solo lectura; en una sesión de código no se reescribe la documentación de fondo. El porqué: mezclar ambas hace imposible revisar los cambios (el usuario verifica a prueba y error, no leyendo diffs), y mantiene cada commit pequeño y de un solo tema.

Reglas comunes a cualquier sesión:

- **La IA nunca commitea.** Deja los cambios en el árbol de trabajo y sugiere el mensaje (Conventional Commits: `feat:` `fix:` `docs:` `test:` `refactor:` `chore:`, imperativo y específico).
- **Explicaciones en lenguaje claro**, sin tecnicismos: el usuario no revisa código.
- El intérprete en esta máquina es `python3` (no existe `python`).
- La documentación nunca afirma nada que el código contradiga: ante la duda, **verificar contra el código**, no contra otros documentos.
- Cada dato vive en **un solo documento**; los demás enlazan a él (mapa de qué va dónde: README de `docs/`… ver tabla del [README](../README.md#documentación)).

---

## Plantilla: sesión de DOCUMENTACIÓN (mantenimiento)

```text
SESIÓN DE DOCUMENTACIÓN — mantenimiento

SOLO LECTURA de código: no toques bc3manager/, scripts/ ni tests/. Solo escribe
documentación (los .md de la raíz y docs/). No commitees: deja los cambios y
sugiéreme el mensaje (docs: ...).

Contexto: la documentación ya está ordenada. El mapa del programa está en
docs/arquitectura.md; las operaciones y endpoints en docs/api-interna.md; el
formato y las rarezas de Presto en docs/formato-bc3.md; las decisiones de diseño
con su porqué en docs/decisiones.md; CLAUDE.md es el contexto permanente.
Regla de oro: cada dato vive en UN solo documento, los demás enlazan.

1. Mira qué ha cambiado en el código desde la última sesión de documentación
   (git log y CHANGELOG) y verifica los documentos contra el código real.
   Lista lo que esté desfasado, con citas (archivo y línea).
2. Corrige cada documento en su único sitio, sin duplicar contenido.
3. Si hubo decisiones de diseño nuevas (en el código o en el CHANGELOG),
   añádelas a docs/decisiones.md con fecha y porqué.
4. Mantén CLAUDE.md al día, pero solo lo permanente (stack, arranque,
   estructura, invariantes, rarezas, convenciones). Si un invariante cambió
   en el código, corrígelo y avísamelo en lenguaje claro.
5. Añade una entrada al CHANGELOG si el cambio de documentación es relevante.
6. Resúmeme qué has tocado y qué queda pendiente.
```

## Plantilla: sesión de CÓDIGO

```text
SESIÓN DE CÓDIGO — [objetivo concreto, UNO por sesión]

Lee CLAUDE.md y respeta los invariantes (sobre todo redondeos y costes
indirectos: los tests test_alqueria_* los blindan contra el informe real de
Presto — si se rompen, NO los relajes sin entender por qué).
No reescribas la documentación de fondo (docs/); solo el CHANGELOG si procede.
No commitees: deja los cambios y sugiéreme el mensaje de commit.

1. Antes de tocar nada: python3 tests/test_basico.py y confirma que todo pasa.
2. [TAREA CONCRETA — pequeña y verificable. Si es grande, trocéala en varias
   sesiones o varios commits.]
3. Corre los tests otra vez. Si tocaste cálculo (model.py) o lectura/escritura
   (io/), comprueba además con un BC3 real (tests/Test_Alqueria.bc3,
   tests/Test_SONFONT.bc3) que el PEM no cambia.
4. Explícame el cambio en lenguaje claro: qué hacía antes, qué hace ahora,
   cómo puedo comprobarlo yo en la web.
5. Si el cambio introduce una decisión de diseño nueva o cambia un invariante,
   dímelo explícitamente: se documentará en la próxima sesión de documentación
   (tú solo anótalo en el CHANGELOG).
```

---

## Plantilla: sesión de AUDITORÍA de cálculo

```text
SESIÓN DE AUDITORÍA DE CÁLCULO — cómo funciona HOY, sin corregir nada

SOLO LECTURA de código: no toques bc3manager/, scripts/ ni tests/. Escribe solo
en docs/auditoria/. Documenta cómo funciona HOY el programa, en lenguaje claro,
citando archivo y función. Anota los problemas SIN corregirlos. No commitees.

Contexto (no partas de cero):
- docs/formato-bc3.md y docs/decisiones.md ya describen el ~K, la cadena de
  redondeo y el CI. La auditoría debe VERIFICARLOS contra el código y la norma,
  no repetirlos: si encuentras desajustes entre doc, código y norma, son
  hallazgos, apúntalos.
- Norma: FIEBDC/2024/Documentos-complementarios. OJO: el programa implementa la
  lectura del ~K según la norma 2016 (campo 3 preferente, campo 1/2 de
  respaldo); contrasta con la 2024 y anota si esta cambia algo.
- Archivos de caso: tests/Test_Alqueria.bc3 (Presto 20 real: ~K completo,
  CI 6%, GG 13%, BI 6%, IVA 21%) es el caso principal para redondeos y CI;
  tests/Test_REDONDEO.bc3 para decimales extremos; tests/Test_SONFONT.bc3 para
  Presto 8.8. ejemplo_son_font.bc3 NO trae ~K (el programa pasa a
  redondeo_activo=False y ci_pct=0): sirve para auditar la LECTURA (A), no los
  redondeos (B) ni el CI (C). Documenta esa limitación donde toque.

Documenta, citando archivo::función de bc3manager/:
A) LECTURA: cómo se interpretan capítulos, partidas, descompuestos (~D) y
   líneas de medición (~M): io/lector.py (_reg_C, _reg_D, _reg_M,
   _resolver_alias_hash, _detectar_raiz) y la clasificación capítulo/partida
   (core/model.py::clasificar_tipos). Incluye las rarezas de Presto (alias #,
   raíz sintética, mediciones huérfanas) verificadas con los archivos de tests.
B) REDONDEOS: dónde declara el BC3 sus decimales (~K: qué campo y qué sigla
   controla qué paso — verifícalo contra la norma y contra el ~K real de
   Test_Alqueria.bc3), si el programa usa ESOS decimales o los suyos
   (core/model.py: atributos dec_*, redondeo_activo, _redondea, _mult_red), y
   el ORDEN exacto al subir de nivel:
   factor de línea → parcial de línea → total de medición → precio básico →
   subtotal del desglose → precio de partida → CI → importe de partida →
   capítulo → PEM
   (parcial_linea, total_medicion, recalcular, precio_con_ci,
   importe_en_padre, _importe_recursivo). Documenta también qué pasa SIN ~K.
C) COSTES INDIRECTOS: de dónde sale el % (campo 2 del ~K,
   lector.py::_detectar_costes_indirectos), sobre qué base se aplica (coste
   directo de cada partida) y en qué momento (precio_con_ci, antes de
   multiplicar por la medición), contrastado con la norma y con el desglose
   real de Test_Alqueria (301.0010: CD 8,86 + 6% → 9,39). Incluye el caso de
   la línea %CI dentro del desglose (es un coste directo más, no el CI global).
D) DIFERENCIAS archivo vs calculado: qué hace el programa cuando el importe
   escrito en el BC3 no coincide con el recalculado. Pista: en el cálculo nunca
   usa el del archivo (_precio_bc3 es solo para comparar); al abrir avisa por
   consola y genera Excel + .txt (web.py::_payload_carga, _construir_informe;
   model.py::validar_completo, comparar_importes_archivo,
   revisar_consistencia_k). OJO: documenta también qué pasa con el archivo en
   disco por el autoguardado (¿cuándo se reescribe con valores recalculados?).

Entregables, en docs/auditoria/, todo en lenguaje claro:
1. auditoria-calculo.md — explica A, B, C y D con citas archivo::función.
2. problemas.md — problemas y sospechas por gravedad (alta/media/baja), cada
   uno con dónde está y por qué puede provocar diferencias de cantidades o
   importes. Sin corregir nada. Distingue lo que la validación actual ya
   detecta de lo que se le escapa.
3. spec-script-comparacion.md — especificación (sin programar) de un comando
   de comparación. OJO: el programa YA compara archivo vs calculado al abrir
   (validar_completo + Excel/txt). La spec debe REUTILIZAR eso como comando
   CLI (p.ej. python3 -m bc3manager.cli validar archivo.bc3): entrada, salida
   (lista de diferencias cantidad a cantidad e importe a importe), códigos de
   salida para usarlo en automatismos, y qué le falta a la validación
   existente.
4. estado-tests.md — los tests HOY PASAN (25/25 el 2026-06-11 con
   `python3 tests/test_basico.py`). Documenta: cómo ejecutarlos, qué cubre
   cada test (mapa test → invariante que protege), qué NO está cubierto, y
   las causas típicas de "no me funcionan" (la nº 1 en este Mac: usar
   `python` en vez de `python3`).
```

**Cambios respecto al prompt original de esta sesión** (por si se quiere entender el porqué): (1) el punto "diagnostica por qué los tests no funcionan" partía de una premisa falsa — pasan 25/25; se convirtió en un mapa de cobertura. (2) `ejemplo_son_font.bc3` no trae `~K`, así que no vale para auditar redondeos ni CI; el caso real es `Test_Alqueria.bc3`. (3) el "script de comparación" ya existe dentro del programa (`validar_completo` + Excel/txt al abrir); la spec pasa a ser "conviértelo en comando CLI". (4) se añadió el contraste norma 2016 vs 2024 y el efecto del autoguardado sobre el archivo original.

---

## Por qué el prompt de "sesión 1" ya no se usa

El prompt original ("mapa y orden inicial": hacer el mapa, auditar contradicciones, actualizar CLAUDE.md, proponer `docs/`) se ejecutó en junio de 2026 y sus productos son la propia carpeta `docs/`. Repetirlo regeneraría trabajo ya hecho. Su sucesor es la plantilla de mantenimiento de arriba: en vez de crear el orden, lo conserva.
