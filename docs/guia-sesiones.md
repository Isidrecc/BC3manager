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

## Por qué el prompt de "sesión 1" ya no se usa

El prompt original ("mapa y orden inicial": hacer el mapa, auditar contradicciones, actualizar CLAUDE.md, proponer `docs/`) se ejecutó en junio de 2026 y sus productos son la propia carpeta `docs/`. Repetirlo regeneraría trabajo ya hecho. Su sucesor es la plantilla de mantenimiento de arriba: en vez de crear el orden, lo conserva.
