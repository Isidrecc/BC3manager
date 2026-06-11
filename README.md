# BC3Manager

Visor, editor e informes para archivos **BC3** (formato **FIEBDC-3**), el estándar de intercambio de presupuestos, mediciones y certificaciones de obra en España.

Herramienta ligera y autocontenida para trabajar con presupuestos sin depender de software propietario de escritorio. Abre un `.bc3` en una interfaz web local, deja consultarlo y editarlo, recalcula precios e importes exactamente igual que el programa de origen (redondeos y costes indirectos incluidos) y genera los informes habituales listos para imprimir.

> Estado: **funcional**. Lee y escribe los registros fundamentales del formato (`~V ~K ~C ~D ~T ~M`), replica el cálculo de Presto (verificado contra presupuestos reales) y produce los cuatro informes principales. Ver [Limitaciones](#limitaciones-conocidas).

## Qué hace

- **Abrir y visualizar** un BC3 en el navegador: capítulos, partidas, textos, mediciones y precios, en árbol jerárquico editable.
- **Editar** con autoguardado al archivo original y deshacer/rehacer: precios, mediciones, descomposiciones, mover/copiar conceptos, añadir capítulos y partidas…
- **Recalcular de forma determinista**, aplicando los coeficientes y redondeos que declara el propio archivo en su registro `~K` (costes indirectos por partida, redondeo decimal mitad-arriba como Presto).
- **Validar al abrir**: genera un informe (Excel + `.txt`) que compara los importes del archivo con los calculados y avisa de inconsistencias.
- **Exportar** de vuelta a un BC3 válido reabrible en Presto, Arquímedes, Menfis, etc.
- **Imprimir informes** HTML (listos para PDF desde el navegador): mediciones, cuadro de precios, presupuesto y resumen.

## Instalación

Requiere Python 3.10 o superior y Flask (única dependencia obligatoria).

```bash
git clone https://github.com/Isidrecc/BC3manager.git
cd BC3manager
pip install flask
```

Opcionales: `openpyxl` (Excel de validación) y `weasyprint` (informes a PDF automáticos).

## Uso (interfaz web)

```bash
python3 -m bc3manager.web                    # abre http://127.0.0.1:5000 en el navegador
python3 -m bc3manager.web presupuesto.bc3    # con archivo precargado + autoguardado
```

Con archivo precargado, cada edición se guarda automáticamente al `.bc3` original.

## Uso (línea de comandos)

```bash
# Resumen del archivo (versión, nº de conceptos, PEM total)
python3 -m bc3manager.cli info presupuesto.bc3

# Árbol del presupuesto en consola
python3 -m bc3manager.cli arbol presupuesto.bc3

# Generar un informe HTML (mediciones | cuadro | presupuesto | resumen)
python3 -m bc3manager.cli informe presupuesto.bc3 --tipo presupuesto --salida pres.html --abrir

# Reescribir a un nuevo BC3 (comprueba el ciclo leer/escribir)
python3 -m bc3manager.cli exportar presupuesto.bc3 --salida copia.bc3
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
p.modificar_precio("MT002", mat.precio * 1.08)
p.recalcular()

# Generar informe y exportar
open("resumen.html", "w", encoding="utf-8").write(generar_informe(p, "resumen"))
escribir_bc3(p, "presupuesto_revisado.bc3")
```

## Documentación

| Documento | Contenido |
|-----------|-----------|
| [docs/arquitectura.md](docs/arquitectura.md) | Qué hace cada módulo y el recorrido de un BC3 por el programa |
| [docs/api-interna.md](docs/api-interna.md) | Modelo de datos, operaciones y endpoints HTTP |
| [docs/formato-bc3.md](docs/formato-bc3.md) | El formato FIEBDC-3 y las rarezas de Presto 8.8 / Presto 20 |
| [docs/decisiones.md](docs/decisiones.md) | Decisiones de diseño y su porqué |
| [docs/guia-sesiones.md](docs/guia-sesiones.md) | Plantillas de prompt para trabajar con IA (documentar / cambiar código) |
| [CHANGELOG.md](CHANGELOG.md) | Historial de cambios |

La especificación oficial del formato (2016/2020/2024) está en la carpeta `FIEBDC/` del repositorio y en [fiebdc.es](https://www.fiebdc.es). Una referencia práctica de lectura registro a registro es el proyecto [pyArq-Presupuestos](https://pyarq.obraencurso.es/fiebdc).

## Limitaciones conocidas

El FIEBDC-3 es amplio; aún **no** se contemplan:

- GG, BI e IVA del registro `~K` (se leen y se conservan, pero el cálculo del PEM solo aplica los costes indirectos). PEC y totales con IVA quedan para el futuro.
- Conceptos paramétricos, precios alternativos múltiples, divisas distintas del euro.
- Registros de información complementaria, comercial, documental, ambiental (`~O ~L ~G ~E ~X`, etc.).
- Certificaciones (tipo de datos «3») como flujo diferenciado del presupuesto.

## Hoja de ruta

- [x] Interfaz web editable con autoguardado, deshacer/rehacer e informes de validación.
- [x] Coeficientes del `~K`: costes indirectos por partida y redondeos exactos como Presto.
- [ ] PEC y totales con IVA (aplicar GG/BI/IVA).
- [ ] Soporte de certificaciones.
- [ ] Exportación de informes a PDF y Excel.
- [ ] **Capa de IA**: edición conversacional del presupuesto mediante herramientas deterministas (la IA decide *qué* operación ejecutar; el motor la ejecuta y recalcula). Las claves de API irán siempre en variables de entorno, nunca en el código.

## Contribuir

Las aportaciones son bienvenidas, especialmente **archivos BC3 reales** (anonimizados, sin precios bajo licencia ni datos de clientes) que ayuden a detectar casos límite del parser. Abre un *issue* describiendo qué programa generó el archivo y qué falla.

## Licencia

MIT. Ver [LICENSE](LICENSE).

## Aviso

Herramienta de apoyo. Verifica siempre los resultados frente a tu software de referencia antes de usar un presupuesto con validez contractual. No está afiliada a la Asociación FIEBDC ni a RIB Software / Presto.
