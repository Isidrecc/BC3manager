# El formato BC3 (FIEBDC-3) y cómo lo trata BC3Manager

> Todo lo relativo al formato en un solo sitio: qué registros se leen, qué significa cada campo que usamos y las rarezas conocidas de los archivos reales (Presto 8.8, Presto 20).
> La especificación oficial está en la carpeta `FIEBDC/2024/Documentos-complementarios` del repositorio (fuente de verdad; hay también versiones 2016 y 2020). Web oficial: [fiebdc.es](https://www.fiebdc.es).

## Lo básico del formato

Formato de texto plano. Cada registro empieza por `~` + una letra; los campos van separados por `|` y los subcampos por `\`. Codificación habitual: cp1252 (ANSI) o cp850 (DOS) — BC3Manager la autodetecta del registro `~V`. Se escribe siempre en cp1252 con saltos CRLF.

### Registros que BC3Manager lee (el resto se ignora)

| Registro | Qué es | Notas |
|----------|--------|-------|
| `~V` | Propiedad y versión | Versión del formato, programa emisor, juego de caracteres. |
| `~K` | Coeficientes y redondeos | Ver detalle abajo. **Nunca se hardcodea nada: todo sale de aquí.** |
| `~C` | Concepto | `~C|CODIGO|UNIDAD|RESUMEN|PRECIO|FECHA|TIPO|` |
| `~D` | Descomposición | `~D|PADRE|HIJO\FACTOR\RENDIMIENTO\HIJO2\...|` |
| `~T` | Texto largo | Descripción/pliego de un concepto. |
| `~M` | Mediciones | `~M|PADRE\HIJO|...|TOTAL|TIPO\COMENTARIO\N\LARGO\ANCHO\ALTO\...|` |

### No soportado (se ignora al leer y no se escribe)

Registros complementarios `~O ~L ~G ~E ~X`…, conceptos paramétricos, precios alternativos, divisas no-euro, certificaciones como flujo propio.

## El registro `~K` al detalle

Tiene 3 campos. La norma FIEBDC-2016 obliga a leer el **campo 3** (el completo y preferente) y, en su defecto, el campo 1/2. `lector.py::_reg_K` lo hace así.

- **Campo 2** → coeficientes `CI \ GG \ BI \ BAJA \ IVA` (en %). Solo el **CI** (costes indirectos) afecta al PEM; GG/BI/IVA se guardan para cálculos futuros (PEC, IVA) pero no intervienen aún.
- **Campo 3** → todos los decimales del cálculo: `DRC DC DFS DRS DUO DI DES DN DD DS DSP DEC` (ojo: el patrón tiene 2 huecos vacíos). Los que usa el cálculo:

| Sigla | En el código | Qué redondea |
|-------|--------------|--------------|
| DN | `dec_num` | nº de partes iguales (uds) de una línea de medición |
| DD | `dec_dim` | dimensiones (largo/ancho/alto) de una línea |
| DSP | `dec_parcial` | parcial de cada línea de medición |
| DS | `dec_cantmed` | total de la medición |
| DRC | `dec_cantrend` | cantidades/rendimientos (incl. el % implícito de líneas `%`) |
| DI | `dec_subtotal` | subtotales de la descomposición |
| DUO | `dec_precio_partida` | precio de partida (también el CI: `round(CD×(1+CI), DecPar)`) |
| DC | `dec_precio_capitulo` | precio de capítulo |
| DES | `dec_natural` | precios de conceptos básicos (MO, maquinaria, material) |

Si el archivo **no trae `~K`**, `redondeo_activo=False` y se calcula a precisión alta (presupuestos sintéticos sin `~K` no se ven afectados).

## El campo TIPO del `~C` (campo 6)

`0` sin clasificar · `1` mano de obra · `2` maquinaria · `3` material · `5` capítulo · `6` partida alzada. Se guarda en `_tipo_fiebdc` y se escribe explícito al exportar (Presto no tiene que adivinar). En la edición, los recursos admiten además `4` (auxiliar).

## Cómo se clasifica capítulo / partida / unitario

Los archivos reales no siempre traen el tipo bien puesto, así que `clasificar_tipos()` aplica reglas en este orden:

1. **Un concepto con `~M` propia es PARTIDA** — regla previa a mirar descomposición o unidad. Los capítulos nunca llevan `~M` real.
2. **Un concepto es CAPÍTULO si sus hijos se miden dentro de él** (la `~M` de los hijos apunta a su código) **o son subcapítulos.** Así, un capítulo con "medición fantasma de 1" (la ponían algunos Prestos antiguos) sigue siendo capítulo, y una partida cuyo recurso tiene descomposición propia sigue siendo partida.
3. Lo demás: hojas con precio = UNITARIO.

Casos reales que esto resuelve: partidas alzadas con unidad "PA" que se veían como capítulos vacíos, y partidas con descomposición pero sin unidad en el `~C`.

## Líneas de porcentaje (`%MA`, medios auxiliares, `%CI`…)

Un hijo cuyo código empieza por `%` no es precio×rendimiento: se aplica **sobre el acumulado de las líneas anteriores** de la misma descomposición. Presto lo trata como una cantidad implícita: `cantidad = acumulado × coef / precio_%`, redondeada a DRC, y luego cantidad × precio_%. Por eso la descomposición se procesa en orden con una suma corriente (ver `es_porcentaje` y el bucle de `recalcular()`).

Importante: una línea `%CI`/medios auxiliares dentro del desglose es **un coste más del Coste Directo**, no el CI global del `~K` — el CI por partida se aplica igualmente encima.

## Rarezas conocidas de los programas emisores

### Presto 8.8 (archivos antiguos)

- **No hay concepto raíz `##`**: los capítulos `01#`, `02#` están sueltos. El lector crea una raíz sintética `OBRA##`.
- **El `#` se omite en las referencias del `~D`**: `~D|02#|02.01\...` referencia `02.01` pero el concepto se llama `02.01#`. Lo resuelve `_resolver_alias_hash` tras la lectura.
- **Los capítulos traen precio precalculado en el `~C`** y no hay registros `~M`. Ese precio se guarda en `_precio_bc3` y se usa SOLO para validar (archivo vs calculado); el cálculo siempre suma de abajo arriba.
- **No declara CI** → `ci_pct=0` y el cálculo no aplica ningún recargo (el test `test_presto88_sin_ci_sigue_exacto` lo blinda).

### Presto 20 / FIEBDC-2016

- **El alias `#` aparece también en `~M`**: `~M|001\...` con el concepto llamado `001#`. Si no se normaliza, las mediciones quedan huérfanas y el **PEM sale 0**. Resuelto también en `_resolver_alias_hash`.
- **Trae CI global en el campo 2 del `~K`** (p. ej. 6%), que se aplica por partida: `precio = round(CD × 1,06, DecPar)`.
- Una `~M` **sin líneas de detalle** es una partida alzada: se usa su `total_declarado` como medición (no 0).

### Generales

- Archivos con **más decimales de los que su propio `~K` declara** (una dimensión 0,315 con DD=2): el cálculo los redondea igual que haría Presto, y el informe de validación lo lista como aviso de conformidad (`revisar_consistencia_k`).
- En una línea de medición, **los factores a 0 cuentan como 1** (una línea "5 / 0 / 0 / 0" mide 5, no 0) — comportamiento estándar del sector.

## La cadena de redondeo (resumen)

Todo redondeo se hace **en `Decimal` exacto, mitad-arriba** (`_redondea`, `_mult_red`), nunca con `round()` de Python (que es bancario y arrastra error de float: 0,015×27,49 = 0,41234999… daría 0,4123 en vez de 0,4124).

Línea de medición: redondear **cada factor antes de multiplicar** (uds→DN, dimensiones→DD) → parcial a DSP → total de medición a DS. Descomposición: precio básico a DES → subtotal a DI → precio de partida a DUO → CI encima (`round(CD×(1+CI), DecPar)`) → importe = precio×medición → capítulos = suma de hijos.

El porqué de estas decisiones (y las que se descartaron) está en [decisiones.md](decisiones.md). Los tests `test_alqueria_*` fijan esta cadena contra el informe real de Presto — no tocarla sin correrlos.
