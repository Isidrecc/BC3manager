# Especificación: comando de comparación archivo vs calculado

> Fecha: 2026-06-11. **Solo especificación — no está programado.**
> Punto de partida obligatorio: el programa YA hace esta comparación al abrir un archivo en la web (`model.py::validar_completo`, `comparar_importes_archivo`, `revisar_consistencia_k`, y los informes Excel/.txt de `web.py`). Este comando NO debe reimplementar nada: debe **reutilizar esas mismas funciones** desde la línea de comandos, para poder validar sin abrir la web y para automatizar comprobaciones.

## Qué se quiere

Un subcomando nuevo de la CLI existente (`bc3manager/cli.py`):

```bash
python3 -m bc3manager.cli validar archivo.bc3 [opciones]
```

Coge el BC3, lo pasa por el lector y el motor de cálculo, y compara **cantidad a cantidad e importe a importe** lo calculado contra lo que pone el archivo, devolviendo la lista de diferencias.

## Comparaciones que debe hacer (todas existen ya en el modelo)

| # | Qué compara | Lado "archivo" | Lado "calculado" | Función existente |
|---|------------|----------------|------------------|-------------------|
| 1 | Medición de cada partida (en cada capítulo) | total declarado del `~M` | suma de líneas con redondeo del `~K` | `validar_completo` (bloque mediciones) |
| 2 | Precio de cada concepto con descomposición | precio del `~C` (`_precio_bc3`) | precio recalculado de abajo arriba (con CI si es capítulo) | `validar_completo` (bloque precios) |
| 3 | Importe de cada partida | precio archivo × medición archivo | precio calc × medición calc | `comparar_importes_archivo` (lista `partidas`) |
| 4 | Importe de cada capítulo | precio congelado del `~C` | suma de importes de sus hijos | `comparar_importes_archivo` (lista `capitulos`) |
| 5 | PEM | suma de capítulos raíz del archivo | `presupuesto_total()` | ambas |
| 6 | Conformidad de decimales | valores del archivo | decimales declarados en su `~K` | `revisar_consistencia_k` |

## Salida

- **Por defecto (pantalla):** el mismo informe que ya se genera al abrir en la web (fuente única `web.py::_construir_informe` — habría que mover esa función al modelo o a un módulo común para no importar la web desde la CLI; anotarlo como decisión de implementación). Resumen final: nº de diferencias por bloque y la diferencia de PEM.
- **`--txt ruta` / `--xlsx ruta`:** escribir los mismos informes de validación que la web (reutilizando `_construir_informe` y `_generar_excel_validacion`).
- **`--json ruta` (nuevo, para automatismos):** volcar tal cual el dict que devuelven `validar_completo` + `comparar_importes_archivo`, sin reformatear.
- **`--tolerancia-abs` y `--tolerancia-rel`:** mismos parámetros y defectos que `validar_completo` (0,01 € y 0,5%).

## Códigos de salida (para usarlo en scripts y en tests)

- `0` — sin diferencias por encima de la tolerancia.
- `1` — hay diferencias (de medición, precio, importe o PEM).
- `2` — error de uso o de lectura (archivo inexistente, ilegible, sin conceptos).

## Modo ida-y-vuelta (`--round-trip`) — la pieza que hoy NO existe

La validación actual solo compara el archivo de **entrada** consigo mismo. El hueco detectado en la auditoría está en la **escritura** (ver [problemas.md](problemas.md) nº 1, 2 y 5), y este modo lo cubriría:

1. Leer `archivo.bc3` → calcular PEM y todas las mediciones/importes (A).
2. Escribirlo a un temporal con `escribir_bc3` → releerlo → calcular lo mismo (B).
3. Comparar A contra B concepto a concepto: mediciones, precios, importes, PEM, y además **inventario**: conceptos, mediciones y registros presentes en A que falten en B.
4. Salida y códigos de error como arriba.

Con el estado actual del programa, este modo sobre `Test_Alqueria.bc3` fallaría señalando la partida alzada perdida (−7.964,67 € de PEM) — exactamente el tipo de regresión que debe cazar. A futuro, sería razonable que los tests lo invocaran sobre los tres BC3 reales de `tests/`.

## Caso de prueba de referencia

- `ejemplo_son_font.bc3`: sin `~K` → sin redondeo por pasos ni CI; debe salir limpio (0 diferencias, PEM 4.523,25 €). OJO: por su falta de `~K` **no** sirve para validar redondeos; el caso completo es `tests/Test_Alqueria.bc3` (0 discrepancias al abrir, PEM calculado a 0,41 € del archivo).

## Qué NO debe hacer

- No recalcular nada por su cuenta ni duplicar lógica de comparación: si falta una comparación, se añade en `model.py` y la usan la web Y el comando.
- No escribir nunca sobre el archivo de entrada (el modo `--round-trip` trabaja sobre un temporal).
- No "arreglar" diferencias: solo informar.
