# API interna de BC3Manager

> Referencia de todas las operaciones del sistema: modelo de datos, operaciones de consulta y edición, endpoints HTTP y formato de las respuestas. Úsala como especificación en sesiones de IA.
> Visión general del programa: [arquitectura.md](arquitectura.md). Formato BC3: [formato-bc3.md](formato-bc3.md).

---

## Modelo de datos (`core/model.py`)

```
Presupuesto
├── conceptos: dict[codigo → Concepto]
├── codigo_raiz: str
├── version_formato, programa_emisor, codificacion, tipo_datos   (cabecera ~V)
├── ci_pct, gg_pct, bi_pct, baja_pct, iva_pct                    (~K campo 2, en tanto por uno)
├── redondeo_activo: bool          (True si el archivo trae ~K)
├── dec_subtotal, dec_precio_partida, dec_precio_capitulo,       (~K: decimales
│   dec_cantrend, dec_cantmed, dec_natural, dec_importe,          de cada paso
│   dec_parcial, dec_dim, dec_num                                 del cálculo)
└── moneda: str

Concepto
├── codigo: str          (clave única, ej: "01#", "E0101", "MO001")
├── unidad: str          (m, m2, kg, ud, PA, %…)
├── resumen: str         (descripción corta)
├── texto: str           (descripción larga / pliego, registro ~T)
├── precio: float        (calculado si tiene hijos; dato si es hoja)
├── precio_es_dato: bool
├── tipo: TipoConcepto   (CAPITULO | PARTIDA | UNITARIO | OTRO)
├── hijos: list[Hijo]    (descomposición)
├── mediciones: dict[codigo_padre → Medicion]
├── _precio_bc3          (precio original del archivo — SOLO para validación)
└── _tipo_fiebdc         (campo 6 del ~C: 0,1,2,3,5,6…)

Hijo
├── codigo_hijo: str
├── factor: float
└── rendimiento: float   → .cantidad = factor × rendimiento

Medicion
├── lineas: list[LineaMedicion]
├── total_declarado: float   (campo total del ~M; una ~M sin líneas lo usa como medición)
└── .total → suma de subtotales de las líneas

LineaMedicion
├── comentario: str
├── n_uds, longitud, anchura, altura: float   (los factores a 0 cuentan como 1)
├── tipo: int      (tipo de línea FIEBDC: 0 normal, 1 parcial, 2 acumulado, 3 fórmula)
└── formula: str
```

**Regla fundamental:** los totales los calcula siempre el modelo (`recalcular()`, `_importe_recursivo()`). Nunca la UI ni la IA.

---

## I/O — Lectura y escritura (`io/`)

### `leer_bc3(ruta: str) → Presupuesto`
Lee un `.bc3` del disco y devuelve el árbol completo en memoria.
Pasos internos: detecta codificación → parsea registros (`~V ~K ~C ~D ~T ~M`) → resuelve alias `#` → clasifica tipos → detecta raíz → detecta costes indirectos → recalcula.

### `escribir_bc3(presupuesto, ruta: str) → None`
Serializa el presupuesto a un `.bc3` válido (cp1252, CRLF). Genera `~V ~K ~C ~D ~T ~M`. El `~K` exportado conserva coeficientes y decimales (round-trip completo).
**Efecto:** sobreescribe el archivo en `ruta`.

---

## Modelo — Consultas (sin efectos)

### `presupuesto.get(codigo) → Concepto | None`
Concepto por código exacto.

### `presupuesto.recalcular() → None`
Recalcula el precio de todos los conceptos con descomposición, de abajo arriba (post-orden con memoización). Los conceptos hoja conservan su precio de dato (redondeado a `DecNat` si hay `~K`). Las líneas de porcentaje (`%MA`…) se aplican sobre el acumulado de las líneas anteriores. **Los precios de capítulo del archivo se ignoran**: siempre se suma desde los descendientes.

### `presupuesto.precio_con_ci(codigo) → float`
Precio de una partida CON costes indirectos: `round(CD × (1 + ci_pct), DecPar)`. Para capítulos y unitarios devuelve su precio tal cual.

### `presupuesto.medicion_total(codigo_hijo, codigo_padre) → float`
Total de medición replicando a Presto: cada factor redondeado (uds→DN, dimensiones→DD), cada parcial a DSP, el total a DS. Una `~M` sin líneas usa el `total_declarado`.

### `presupuesto.importe_en_padre(codigo_hijo, codigo_padre) → float`
`precio_con_ci × medición`. **Sin medición, el importe es 0** — no hay fallback a la cantidad del `~D` ni al precio del archivo.

### `presupuesto.presupuesto_total() → float`
PEM: suma recursiva de los importes de los capítulos raíz (`_importe_recursivo`). El importe de un capítulo es SIEMPRE la suma de los importes de sus hijos.

### Validación (consultas sin efectos)

- `comparar_importes_archivo() → dict` — compara importes/PEM del archivo (`_precio_bc3`) con lo calculado.
- `validar_precios_cargados() → list` — discrepancias de precio concepto a concepto.
- `revisar_consistencia_k() → dict` — valores con más decimales de los que declara el `~K` (aviso, no error).
- `validar_completo() → dict` — todo lo anterior de una vez (lo usa la web al cargar).

---

## Modelo — Edición (con efectos)

Todas lanzan `ValueError` si el concepto no existe o los parámetros son inválidos. Ninguna llama a `recalcular()` por sí sola — la web lo hace en `_resp()`.

### Conceptos
- `modificar_precio(codigo, nuevo_precio)` — solo conceptos **hoja** (sin descomposición); actualiza `precio`, `precio_es_dato=True` y `_precio_bc3`.
- `modificar_resumen(codigo, resumen)` — descripción corta.
- `modificar_texto(codigo, texto)` — descripción larga (pliego, `~T`).
- `modificar_unidad(codigo, unidad)` — unidad de medida.
- `modificar_codigo(codigo_viejo, codigo_nuevo)` — renombra y actualiza TODAS las referencias (hijos, claves de mediciones, raíz). Falla si el nuevo ya existe.
- `cambiar_tipo(codigo, "capitulo"|"partida")` — cambia cómo se calcula y se muestra; no toca la estructura.
- `cambiar_tipo_recurso(codigo, tipo_fiebdc)` — subtipo de un unitario: `'1'` MO, `'2'` maquinaria, `'3'` material, `'4'` auxiliar.

### Estructura del árbol
- `add_partida(codigo_padre, codigo, unidad, resumen, precio)` — crea una PARTIDA como hijo del padre.
- `add_capitulo(codigo, resumen, codigo_padre=None)` — crea un CAPÍTULO (en la raíz si no se indica padre).
- `eliminar_concepto(codigo, codigo_padre)` — desvincula del padre. **No borra** el concepto del diccionario (puede estar referenciado en otros sitios).
- `mover_concepto(codigo, padre_origen, padre_destino, antes_de=None)` — mueve un concepto de padre (con su medición). `antes_de=None` → al final. Falla si crearía un ciclo o ya existe en destino.
- `copiar_concepto(codigo, padre_destino, antes_de=None)` — el mismo concepto en varios sitios del árbol (estándar en FIEBDC-3). La medición en el nuevo padre empieza vacía.

### Descomposición (recursos de una partida)
- `add_recurso(codigo_partida, codigo_recurso, rendimiento=1, precio=0, unidad="", resumen="", tipo_fiebdc="3")` — añade un recurso; lo crea como UNITARIO si no existe, o actualiza el rendimiento si ya estaba.
- `eliminar_recurso(codigo_partida, codigo_recurso)` — lo desvincula de la descomposición (no lo borra del presupuesto).
- `reordenar_recurso(codigo_partida, codigo_recurso, antes_de=None)` — cambia su posición.
- `modificar_rendimiento(codigo_padre, codigo_hijo, rendimiento)` — cambia el rendimiento de un hijo.

### Mediciones
- `modificar_medicion(codigo_hijo, codigo_padre, indice, campo, valor)` — `campo`: `n_uds`, `longitud`, `anchura`, `altura` (el `comentario` lo trata la web aparte).
- `add_linea_medicion(codigo_hijo, codigo_padre, comentario, n_uds, longitud, anchura, altura)` — línea nueva al final; crea la `Medicion` si no existe.
- `eliminar_linea_medicion(codigo_hijo, codigo_padre, indice)` — elimina la línea (base 0).
- `reordenar_medicion(codigo_hijo, codigo_padre, from_idx, to_idx)` — mueve una línea de posición.

---

## HTTP API — Endpoints Flask (`web.py`)

Estado global del servidor (monousuario): `_estado = {presupuesto, ruta_original, nombre_archivo, ruta_arg, undo_stack, redo_stack, discrepancias, ruta_validacion_xlsx, ruta_validacion_txt}`.

| Método | Ruta | Entrada | Salida |
|--------|------|---------|--------|
| GET | `/` | — | HTML completo de la app |
| POST | `/api/cargar` | `multipart/form-data` con `archivo` (.bc3) | payload de carga (ver abajo) |
| POST | `/api/cargar_local` | — (usa `_estado["ruta_arg"]`) | payload de carga |
| GET | `/api/tiene_archivo` | — | `{"tiene": bool}` |
| POST | `/api/editar` | JSON `{accion, ...params}` (tabla abajo) | `{ok, info, arbol, undo_disponible, redo_disponible}` |
| POST | `/api/undo` | — | igual que `/api/editar` |
| POST | `/api/redo` | — | igual que `/api/editar` |
| GET | `/api/informe?tipo=X` | `tipo`: `presupuesto`, `resumen`, `mediciones`, `cuadro` | HTML del informe |
| GET | `/api/exportar` | — | descarga del `.bc3` actual |
| GET | `/api/validacion_xlsx` | — | descarga del Excel de validación (necesita `openpyxl`) |

Tras cada `/api/editar` exitoso: `_autoguardar()` escribe el BC3 al archivo original, apila un snapshot para deshacer y vacía la pila de rehacer. Deshacer/rehacer restauran un snapshot completo y también lo escriben a disco.

Al cargar un archivo (`/api/cargar`, `/api/cargar_local`): validación completa + Excel y `.txt` de validación generados junto al BC3 (o en carpeta temporal si vino por upload).

**Errores:** todos los endpoints devuelven `{"error": "mensaje"}` con código HTTP 400/500.

### Acciones de `/api/editar`

| `accion` | Parámetros requeridos |
|----------|-----------------------|
| `precio` | `codigo`, `valor` (float) |
| `resumen` | `codigo`, `valor` (str) |
| `unidad` | `codigo`, `valor` (str) |
| `texto` | `codigo`, `valor` (str) |
| `codigo` | `codigo_viejo`, `codigo_nuevo` |
| `cambiar_tipo` | `codigo`, `tipo` (`"capitulo"`/`"partida"`) |
| `tipo_recurso` | `codigo`, `tipo_fiebdc` (`"1"`-`"4"`) |
| `rendimiento` | `codigo_padre`, `codigo_hijo`, `valor` (float) |
| `medicion` | `codigo_hijo`, `codigo_padre`, `indice`, `campo`, `valor` |
| `add_linea_medicion` | `codigo_hijo`, `codigo_padre` + opc.: `comentario`, `n_uds`, `longitud`, `anchura`, `altura` |
| `eliminar_linea_medicion` | `codigo_hijo`, `codigo_padre`, `indice` |
| `reordenar_medicion` | `codigo_hijo`, `codigo_padre`, `from_idx`, `to_idx` |
| `add_partida` | `codigo_padre`, `codigo` + opc.: `unidad`, `resumen`, `precio` |
| `add_capitulo` | `codigo` + opc.: `resumen`, `codigo_padre` |
| `eliminar_concepto` | `codigo`, `codigo_padre` |
| `add_recurso` | `codigo_partida`, `codigo_recurso` + opc.: `rendimiento`, `precio`, `unidad`, `resumen`, `tipo_fiebdc` |
| `eliminar_recurso` | `codigo_partida`, `codigo_recurso` |
| `reordenar_recurso` | `codigo_partida`, `codigo_recurso` + opc.: `antes_de` |
| `mover` | `codigo`, `padre_origen`, `padre_destino` + opc.: `antes_de` |
| `copiar` | `codigo`, `padre_destino` + opc.: `antes_de` |

---

## Estructura de las respuestas

### Payload de carga (`/api/cargar`, `/api/cargar_local`)

```json
{
  "info": {...}, "arbol": [...], "archivo": "nombre.bc3",
  "discrepancias": [...],            // precios archivo vs calculado
  "mediciones_inconsistentes": 0,
  "pem": { "archivo": float, "calculado": float, "diferencia": float },
  "validacion_xlsx": "ruta/validacion_obra.xlsx"
}
```

### `info`

```json
{ "obra": str, "version": str, "programa": str,
  "capitulos": int, "partidas": int, "unitarios": int,
  "total": float, "total_fmt": str,
  "ci_pct": float,                  // % de costes indirectos del ~K
  "archivo_temporal": bool }        // true si vino por upload (no hay autosave útil)
```

### `arbol` (solo CAPITULO y PARTIDA; los UNITARIO van en `recursos`)

```json
nodo: {
  "codigo", "unidad", "resumen", "texto", "tipo", "tipo_fiebdc",
  "precio", "precio_fmt",            // partidas: precio CON costes indirectos
  "medicion", "medicion_fmt", "medicion_total_fmt",
  "importe", "importe_fmt",
  "padre": str,
  "hijos": [nodo, ...],              // solo capítulos
  "recursos": [recurso, ...],        // solo partidas
  "lineas_medicion": [linea, ...],
  "desglose_precio": {               // solo partidas: como el informe de Presto
    "suma_fmt", "ci_pct", "ci_importe_fmt", "redondeo_fmt", "total_fmt", "tiene_ci"
  }
}

recurso: { "codigo", "unidad", "resumen", "tipo_fiebdc", "es_porcentaje",
           "precio", "precio_fmt", "rendimiento", "rendimiento_fmt",
           "importe", "importe_fmt" }

linea:   { "comentario", "n_uds", "longitud", "anchura", "altura",
           "subtotal", "subtotal_fmt" }
           // los factores llegan YA redondeados a sus decimales del ~K
           // (lo que ves multiplicado = el parcial)
```

---

## Informes (`/api/informe?tipo=X`)

| tipo | Contenido |
|------|-----------|
| `presupuesto` | Árbol completo: capítulos, partidas, mediciones, importes. PEM al final. |
| `resumen` | Un renglón por capítulo con su importe. PEM total. |
| `mediciones` | Por cada partida: tabla de líneas de medición con subtotales. |
| `cuadro` | Cuadro de precios unitarios: partidas y sus recursos con precio y rendimiento. |

---

## Lo que NO está implementado

- GG/BI/IVA del `~K`: se leen y conservan, pero no se aplican (el PEM solo lleva CI). PEC y total con IVA quedan para el futuro.
- Certificaciones (`tipo_datos` "3") como flujo diferenciado.
- Conceptos paramétricos, precios alternativos múltiples, divisas distintas del euro.
- Registros complementarios del formato (`~O ~L ~G ~E ~X`…).
- Capa de IA conversacional (fase futura — invocaría estas mismas operaciones vía tool-calling).
