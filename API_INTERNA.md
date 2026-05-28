# BC3Manager — API Interna

> Referencia de todas las operaciones del sistema. Úsala como especificación en sesiones de IA.

---

## Modelo de datos

```
Presupuesto
├── conceptos: dict[codigo → Concepto]
└── codigo_raiz: str  (el nodo raíz del árbol)

Concepto
├── codigo: str          (clave única, ej: "01#", "E0101", "MO001")
├── unidad: str          (m, m2, kg, ud, PA…)
├── resumen: str         (descripción corta)
├── texto: str           (descripción larga / pliego)
├── precio: float        (calculado si tiene hijos; dato si es hoja)
├── precio_es_dato: bool (True = no recalcular este precio)
├── tipo: TipoConcepto   (CAPITULO | PARTIDA | UNITARIO | OTRO)
├── hijos: list[Hijo]    (descomposición: lista de recursos/subconceptos)
└── mediciones: dict[codigo_padre → Medicion]

Hijo
├── codigo_hijo: str
├── factor: float
└── rendimiento: float   → .cantidad = factor × rendimiento

LineaMedicion
├── comentario, n_uds, longitud, anchura, altura: float
└── .subtotal → producto de los factores no-cero
```

**Regla fundamental:** los totales los calcula siempre `recalcular()`. Nunca la UI ni la IA.

---

## I/O — Lectura y escritura

### `leer_bc3(ruta: str) → Presupuesto`
Lee un archivo `.bc3` del disco y devuelve el árbol completo en memoria.  
Pasos internos: detecta codificación → parsea registros (~V ~C ~D ~T ~M) → resuelve alias `#` → clasifica tipos → detecta raíz → recalcula precios.  
**Lanza:** ninguna excepción explícita (errores de IO son Python estándar).

### `escribir_bc3(presupuesto: Presupuesto, ruta: str) → None`
Serializa el Presupuesto en memoria a un archivo `.bc3` válido (cp1252).  
Genera registros: `~V` (cabecera), `~C` (conceptos), `~D` (descomposiciones), `~T` (textos), `~M` (mediciones).  
**Efecto:** sobreescribe el archivo en `ruta`.

---

## Modelo — Consultas (sin efectos)

### `presupuesto.get(codigo) → Concepto | None`
Devuelve el concepto por código exacto.

### `presupuesto.medicion_total(codigo_hijo, codigo_padre) → float`
Suma de subtotales de todas las líneas de medición de `codigo_hijo` dentro de `codigo_padre`.

### `presupuesto.importe_en_padre(codigo_hijo, codigo_padre) → float`
`precio × medicion_total`. Si no hay medición usa la cantidad de la descomposición.

### `presupuesto.presupuesto_total() → float`
Importe total del árbol desde la raíz. Suma recursiva de `_importe_recursivo`.

### `presupuesto.recalcular() → None`
Recalcula precios de todos los conceptos con hijos (post-orden, con memoización).  
Los conceptos con `precio_es_dato=True` y `'#' in codigo` conservan su precio original (`_precio_bc3`).

---

## Modelo — Edición (con efectos)

Todas las operaciones de edición **lanzan `ValueError`** si el concepto no existe o los parámetros son inválidos. Ninguna llama a `recalcular()` por sí sola — la web lo hace vía `_resp()`.

### `modificar_precio(codigo, nuevo_precio: float)`
Recibe: código de un concepto **hoja** (sin hijos) y el nuevo precio.  
Efecto: actualiza `precio`, `precio_es_dato=True` y `_precio_bc3`.  
Lanza `ValueError` si el concepto tiene descomposición (precio calculado, no editable directamente).

### `modificar_resumen(codigo, resumen: str)`
Cambia la descripción corta del concepto.

### `modificar_unidad(codigo, unidad: str)`
Cambia la unidad de medida.

### `modificar_codigo(codigo_viejo, codigo_nuevo)`
Renombra un concepto y actualiza todas las referencias (hijos de otros conceptos, claves en mediciones, `codigo_raiz`).  
Lanza `ValueError` si el código nuevo ya existe.

### `modificar_rendimiento(codigo_padre, codigo_hijo, rendimiento: float)`
Cambia el rendimiento de un hijo dentro de la descomposición de su padre.

### `modificar_medicion(codigo_hijo, codigo_padre, indice_linea, campo, valor)`
`campo` puede ser: `n_uds`, `longitud`, `anchura`, `altura`, `comentario`.  
Modifica esa celda en la línea `indice_linea` (base 0).

### `add_linea_medicion(codigo_hijo, codigo_padre, comentario, n_uds, longitud, anchura, altura)`
Añade una línea nueva al final de la medición de `codigo_hijo` en `codigo_padre`.  
Crea la `Medicion` si no existe.

### `eliminar_linea_medicion(codigo_hijo, codigo_padre, indice)`
Elimina la línea en posición `indice` (base 0).

### `add_partida(codigo_padre, codigo, unidad, resumen, precio)`
Crea un `Concepto` nuevo de tipo PARTIDA y lo añade como hijo de `codigo_padre`.  
Lanza `ValueError` si el código ya existe o el padre no existe.

### `add_capitulo(codigo, resumen, codigo_padre=None)`
Crea un `Concepto` de tipo CAPITULO. Si `codigo_padre` es None, se añade a la raíz.

### `eliminar_concepto(codigo, codigo_padre)`
Desvincula el concepto del padre (quita el `Hijo` del padre).  
**No borra** el concepto del diccionario (puede estar referenciado desde otros sitios).

---

## HTTP API — Endpoints Flask

Estado global del servidor: `_estado = {"presupuesto", "ruta_original", "nombre_archivo", "ruta_arg"}`.

| Método | Ruta | Entrada | Salida |
|--------|------|---------|--------|
| GET | `/` | — | HTML completo de la app |
| POST | `/api/cargar` | `multipart/form-data` con `archivo` (.bc3) | `{info, arbol, archivo}` |
| POST | `/api/cargar_local` | — (usa `_estado["ruta_arg"]`) | `{info, arbol, archivo}` |
| GET | `/api/tiene_archivo` | — | `{"tiene": bool}` |
| POST | `/api/editar` | JSON `{accion, ...params}` → ver tabla abajo | `{ok, info, arbol}` completo |
| GET | `/api/informe?tipo=X` | `tipo`: `presupuesto`, `resumen`, `mediciones`, `cuadro` | HTML del informe |
| GET | `/api/exportar` | — | Descarga del `.bc3` actual |

Tras cada `/api/editar` exitoso: llama a `_autoguardar()` (escribe el BC3 al archivo original).

### Acciones de `/api/editar`

| `accion` | Parámetros requeridos |
|----------|-----------------------|
| `precio` | `codigo`, `valor` (float) |
| `resumen` | `codigo`, `valor` (str) |
| `unidad` | `codigo`, `valor` (str) |
| `codigo` | `codigo_viejo`, `codigo_nuevo` |
| `rendimiento` | `codigo_padre`, `codigo_hijo`, `valor` (float) |
| `medicion` | `codigo_hijo`, `codigo_padre`, `indice`, `campo`, `valor` |
| `add_linea_medicion` | `codigo_hijo`, `codigo_padre`, + opcionales: `comentario`, `n_uds`, `longitud`, `anchura`, `altura` |
| `eliminar_linea_medicion` | `codigo_hijo`, `codigo_padre`, `indice` |
| `add_partida` | `codigo_padre`, `codigo`, + opcionales: `unidad`, `resumen`, `precio` |
| `add_capitulo` | `codigo`, + opcionales: `resumen`, `codigo_padre` |
| `eliminar_concepto` | `codigo`, `codigo_padre` |

**Errores:** todos los endpoints devuelven `{"error": "mensaje"}` con código HTTP 400/500.

---

## Estructura de respuesta `{info, arbol}`

```json
info: {
  "obra": str, "version": str, "programa": str,
  "capitulos": int, "partidas": int, "unitarios": int,
  "total": float, "total_fmt": str
}

arbol: [ nodo, ... ]   // solo CAPITULO y PARTIDA (los UNITARIO van dentro de recursos)

nodo: {
  "codigo", "unidad", "resumen", "texto", "tipo",
  "precio", "precio_fmt",
  "medicion", "medicion_fmt",
  "importe", "importe_fmt",
  "padre": str,
  "hijos": [ nodo, ... ],          // solo si CAPITULO
  "recursos": [ recurso, ... ],    // solo si PARTIDA
  "lineas_medicion": [ linea, ... ]
}

recurso: { "codigo", "unidad", "resumen", "precio", "precio_fmt",
           "rendimiento", "rendimiento_fmt", "importe", "importe_fmt" }

linea: { "comentario", "n_uds", "longitud", "anchura", "altura",
         "subtotal", "subtotal_fmt" }
```

---

## Informes disponibles (`/api/informe?tipo=X`)

| tipo | Contenido |
|------|-----------|
| `presupuesto` | Árbol completo: capítulos, partidas, mediciones, importes. Total PEM al final. |
| `resumen` | Un renglón por capítulo con su importe. Total PEM. |
| `mediciones` | Por cada partida: tabla de líneas de medición con subtotales. |
| `cuadro` | Cuadro de precios unitarios: partidas y sus recursos con precio y rendimiento. |

---

## Lo que NO está implementado (v1)

- Coeficientes `~K` (CI, GG, BI): se leen del BC3 pero no se aplican al cálculo.
- Certificaciones (tipo_datos `"3"`).
- Undo/redo.
- Capa de IA conversacional (fase futura — invocaría estas mismas operaciones vía tool-calling).
