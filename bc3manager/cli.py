"""
Interfaz de línea de comandos de BC3Manager.

Uso:
  python -m bc3manager.cli info       archivo.bc3
  python -m bc3manager.cli arbol      archivo.bc3
  python -m bc3manager.cli informe    archivo.bc3 --tipo presupuesto --salida informe.html
  python -m bc3manager.cli exportar   archivo.bc3 --salida copia.bc3

Tipos de informe: mediciones | cuadro | presupuesto | resumen
"""

from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

from bc3manager.core.model import TipoConcepto
from bc3manager.io.lector import leer_bc3
from bc3manager.io.escritor import escribir_bc3
from bc3manager.reports.informes import generar_informe, INFORMES


def _fmt_eur(v: float) -> str:
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return s + " €"


def cmd_info(args) -> None:
    p = leer_bc3(args.archivo)
    obra = p.get(p.codigo_raiz) if p.codigo_raiz else None
    print(f"Archivo:        {args.archivo}")
    print(f"Versión:        {p.version_formato}")
    print(f"Programa:       {p.programa_emisor}")
    print(f"Codificación:   {p.codificacion}")
    print(f"Tipo de datos:  {p.tipo_datos or '(no indicado)'}")
    print(f"Obra raíz:      {p.codigo_raiz}  {obra.resumen if obra else ''}")
    print(f"Nº conceptos:   {len(p.conceptos)}")
    caps = sum(1 for c in p.conceptos.values() if c.tipo == TipoConcepto.CAPITULO)
    parts = sum(1 for c in p.conceptos.values() if c.tipo == TipoConcepto.PARTIDA)
    unit = sum(1 for c in p.conceptos.values() if c.tipo == TipoConcepto.UNITARIO)
    print(f"  Capítulos:    {caps}")
    print(f"  Partidas:     {parts}")
    print(f"  Unitarios:    {unit}")
    print(f"PEM total:      {_fmt_eur(p.presupuesto_total())}")


def cmd_arbol(args) -> None:
    p = leer_bc3(args.archivo)
    from bc3manager.reports.informes import _recorrer
    for nivel, padre, c in _recorrer(p):
        sangria = "  " * nivel
        if c.tipo == TipoConcepto.CAPITULO:
            print(f"{sangria}[{c.codigo}] {c.resumen}")
        elif c.tipo == TipoConcepto.PARTIDA:
            med = p.medicion_total(c.codigo, padre)
            imp = p.importe_en_padre(c.codigo, padre)
            print(f"{sangria}{c.codigo} ({c.unidad}) {c.resumen} "
                  f"— {med:.2f} × {_fmt_eur(c.precio)} = {_fmt_eur(imp)}")


def cmd_informe(args) -> None:
    p = leer_bc3(args.archivo)
    contenido = generar_informe(p, args.tipo)
    salida = Path(args.salida) if args.salida else Path(f"informe_{args.tipo}.html")
    salida.write_text(contenido, encoding="utf-8")
    print(f"Informe '{args.tipo}' escrito en: {salida.resolve()}")
    if args.abrir:
        webbrowser.open(salida.resolve().as_uri())


def cmd_exportar(args) -> None:
    p = leer_bc3(args.archivo)
    escribir_bc3(p, args.salida)
    print(f"Exportado a: {Path(args.salida).resolve()}")
    print(f"PEM total conservado: {_fmt_eur(p.presupuesto_total())}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="bc3manager",
        description="Visor, editor e informes para archivos BC3 (FIEBDC-3).",
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    pi = sub.add_parser("info", help="Resumen del archivo")
    pi.add_argument("archivo")
    pi.set_defaults(func=cmd_info)

    pa = sub.add_parser("arbol", help="Imprime el árbol del presupuesto")
    pa.add_argument("archivo")
    pa.set_defaults(func=cmd_arbol)

    pr = sub.add_parser("informe", help="Genera un informe HTML")
    pr.add_argument("archivo")
    pr.add_argument("--tipo", choices=list(INFORMES), default="presupuesto")
    pr.add_argument("--salida", help="Ruta del HTML de salida")
    pr.add_argument("--abrir", action="store_true", help="Abre el informe en el navegador")
    pr.set_defaults(func=cmd_informe)

    pe = sub.add_parser("exportar", help="Reescribe el presupuesto a un nuevo BC3")
    pe.add_argument("archivo")
    pe.add_argument("--salida", required=True)
    pe.set_defaults(func=cmd_exportar)

    args = parser.parse_args(argv)
    try:
        args.func(args)
    except FileNotFoundError:
        print(f"Error: no se encuentra el archivo '{args.archivo}'", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
