# BC3Manager

Visor, editor e informes para archivos **BC3** (formato **FIEBDC-3**), el estándar de intercambio de presupuestos, mediciones y certificaciones de obra en España.

Proyecto de código abierto pensado como herramienta ligera y autocontenida para trabajar con presupuestos sin depender de software propietario de escritorio. Lee un `.bc3`, te deja consultar y editar su estructura, recalcula precios e importes de forma determinista y genera los informes habituales listos para imprimir.

> Estado: **versión inicial funcional**. Lee y escribe los registros fundamentales del formato (`~V`, `~K`, `~C`, `~D`, `~T`, `~M`) y produce los cuatro informes principales. Ver [Limitaciones](#limitaciones-conocidas) y [Hoja de ruta](#hoja-de-ruta).

## Qué hace

- **Abrir y visualizar** un archivo BC3: capítulos, partidas, textos, mediciones y precios, en árbol jerárquico.
- **Editar** la estructura mediante el modelo de datos (precios unitarios, mediciones, descomposiciones) y **exportar** de vuelta a un BC3 válido reabrible en Presto, Arquímedes, Menfis, etc.
- **Recalcular** precios desde la descomposición e importes desde la medición, de forma determinista (los totales nunca se "estiman").
- **Imprimir informes** en HTML (listos para PDF desde el navegador):
  1. Mediciones
  2. Cuadro de precios
  3. Presupuesto
  4. Resumen de presupuesto

## Instalación

Requiere Python 3.10 o superior. No tiene dependencias externas obligatorias para el núcleo.

```bash
git clone https://github.com/TU_USUARIO/bc3manager.git
cd bc3manager
python -m bc3manager.cli info ejemplo_son_font.bc3
```

## Uso (línea de comandos)

```bash
# Resumen del archivo (versión, nº de conceptos, PEM total)
python -m bc3manager.cli info presupuesto.bc3

# Árbol del presupuesto en consola
python -m bc3manager.cli arbol presupuesto.bc3

# Generar un informe HTML (mediciones | cuadro | presupuesto | resumen)
python -m bc3manager.cli informe presupuesto.bc3 --tipo presupuesto --salida pres.html --abrir

# Reescribir a un nuevo BC3 (comprueba el ciclo leer/escribir)
python -m bc3manager.cli exportar presupuesto.bc3 --salida copia.bc3
```

## Uso (como librería)

```python
from bc3manager.io.lector import leer_bc3
from bc3manager.io.escritor import escribir_bc3
from bc3manager.reports.informes import generar_informe

p = leer_bc3("presupuesto.bc3")
print(p.presupuesto_total())

# Editar: subir un 8% el precio de un material y recalcular todo
mat = p.get("MT002")
mat.precio *= 1.08
p.recalcular()

# Generar informe y exportar
open("resumen.html", "w", encoding="utf-8").write(generar_informe(p, "resumen"))
escribir_bc3(p, "presupuesto_revisado.bc3")
```

## Arquitectura

```
bc3manager/
├── core/
│   └── model.py        # Modelo de datos: Concepto, Hijo, Medicion, Presupuesto + recálculo
├── io/
│   ├── lector.py       # Parser de los registros FIEBDC-3
│   └── escritor.py     # Exportación a BC3
├── reports/
│   └── informes.py     # Generadores de los 4 informes (HTML)
└── cli.py              # Interfaz de línea de comandos
```

El diseño separa deliberadamente **datos** (el modelo) de **cálculo** (recálculo determinista) y de **operaciones**. Esto deja el terreno preparado para una eventual capa de IA que **invoque operaciones** sobre el modelo sin calcular nunca los totales por sí misma (ver hoja de ruta).

## Limitaciones conocidas

Esta primera versión cubre el núcleo del formato, pero el FIEBDC-3 es amplio y tiene muchos casos. Aún **no** se contemplan:

- Aplicación de coeficientes del registro `~K` (costes indirectos, GG, BI, redondeos por divisa). Se leen pero no se aplican al cálculo.
- Conceptos paramétricos, precios alternativos múltiples, divisas distintas del euro.
- Registros de información complementaria, comercial, documental, ambiental (`~O`, `~L`, `~G`, `~E`, `~X`, etc.).
- Certificaciones (tipo de datos «3») como flujo diferenciado del presupuesto.
- Las heurísticas de clasificación capítulo/partida/unitario son pragmáticas y pueden necesitar ajuste con archivos reales variados.

El formato es un estándar abierto y gratuito; la especificación oficial está en [fiebdc.es](https://www.fiebdc.es). Una referencia práctica de lectura registro a registro muy útil es el proyecto [pyArq-Presupuestos](https://pyarq.obraencurso.es/fiebdc).

## Hoja de ruta

- [ ] Aplicar coeficientes `~K` (CI, GG, BI) y redondeos correctos.
- [ ] Soporte de certificaciones.
- [ ] Interfaz gráfica (árbol editable en escritorio o web).
- [ ] Exportación de informes a PDF y Excel.
- [ ] **Capa de IA**: edición conversacional del presupuesto mediante herramientas deterministas (la IA decide *qué* operación ejecutar; el motor la ejecuta y recalcula). Las claves de API irán siempre en variables de entorno, nunca en el código.

## Contribuir

Las aportaciones son bienvenidas, especialmente **archivos BC3 reales** (anonimizados, sin precios bajo licencia ni datos de clientes) que ayuden a detectar casos límite del parser. Abre un *issue* describiendo qué programa generó el archivo y qué falla.

## Licencia

MIT. Ver [LICENSE](LICENSE).

## Aviso

Herramienta de apoyo. Verifica siempre los resultados frente a tu software de referencia antes de usar un presupuesto con validez contractual. No está afiliada a la Asociación FIEBDC ni a RIB Software / Presto.
