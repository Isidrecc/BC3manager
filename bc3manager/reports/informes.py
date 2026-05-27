"""
Generadores de informes a partir de un Presupuesto.

Produce los cuatro informes que pide el flujo de trabajo habitual:
  1. Mediciones        -> detalle de líneas de medición por partida
  2. Cuadro de precios -> precio unitario de cada concepto (nº 1 y descompuesto)
  3. Presupuesto       -> capítulos, partidas, mediciones e importes
  4. Resumen           -> importe por capítulo y total

Los informes se generan como HTML, que es cómodo de revisar en pantalla y se
imprime a PDF directamente desde el navegador (o con herramientas como
weasyprint si se quiere automatizar). Se evita depender de librerías pesadas
en esta primera versión.
"""

from __future__ import annotations

import html
from datetime import date

from bc3manager.core.model import Presupuesto, TipoConcepto


# --------------------------------------------------------------------------
# Utilidades de recorrido del árbol
# --------------------------------------------------------------------------

def _recorrer(p: Presupuesto):
    """
    Genera (nivel, codigo_padre, concepto) recorriendo el árbol en preorden
    desde la raíz. Protege contra ciclos.
    """
    if not p.codigo_raiz:
        return
    visitados: set[tuple[str, str]] = set()

    def _walk(codigo: str, padre: str, nivel: int):
        concepto = p.get(codigo)
        if concepto is None:
            return
        clave = (padre, codigo)
        if clave in visitados:
            return
        visitados.add(clave)
        yield (nivel, padre, concepto)
        for hijo in concepto.hijos:
            # No descendemos dentro de conceptos unitarios (mano de obra...)
            hijo_concepto = p.get(hijo.codigo_hijo)
            if hijo_concepto and hijo_concepto.tipo in (
                TipoConcepto.CAPITULO,
                TipoConcepto.PARTIDA,
            ):
                yield from _walk(hijo.codigo_hijo, codigo, nivel + 1)

    yield from _walk(p.codigo_raiz, "", 0)


def _fmt_eur(valor: float) -> str:
    """Formatea un importe en euros con separador de miles español."""
    s = f"{valor:,.2f}"
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return s + " €"


def _fmt_num(valor: float, dec: int = 2) -> str:
    s = f"{valor:,.{dec}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _cab_html(titulo: str, p: Presupuesto) -> str:
    obra = p.get(p.codigo_raiz) if p.codigo_raiz else None
    nombre_obra = html.escape(obra.resumen) if obra and obra.resumen else "Presupuesto"
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<title>{html.escape(titulo)} — {nombre_obra}</title>
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; font-size: 11px; color: #1a1a1a; margin: 24px; }}
  h1 {{ font-size: 18px; border-bottom: 2px solid #2c5f7c; padding-bottom: 6px; color: #2c5f7c; }}
  h2 {{ font-size: 13px; color: #555; font-weight: normal; margin-top: 2px; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 12px; }}
  th {{ background: #2c5f7c; color: white; text-align: left; padding: 5px 7px; font-size: 10px; }}
  td {{ padding: 4px 7px; border-bottom: 1px solid #e0e0e0; vertical-align: top; }}
  .num {{ text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }}
  .cap {{ background: #eef4f8; font-weight: bold; }}
  .cod {{ color: #777; font-family: 'Consolas', monospace; font-size: 10px; }}
  .total {{ background: #2c5f7c; color: white; font-weight: bold; font-size: 13px; }}
  .sub {{ color: #888; font-size: 10px; }}
  .pie {{ margin-top: 30px; font-size: 9px; color: #aaa; text-align: center; }}
  tr.cap td {{ border-bottom: 1px solid #b8d0de; }}
</style></head><body>
<h1>{html.escape(titulo)}</h1>
<h2>{nombre_obra} · {date.today().strftime('%d/%m/%Y')}</h2>
"""


def _pie_html() -> str:
    return ('<div class="pie">Generado por BC3Manager · '
            'formato FIEBDC-3</div></body></html>')


# --------------------------------------------------------------------------
# 1. Informe de MEDICIONES
# --------------------------------------------------------------------------

def informe_mediciones(p: Presupuesto) -> str:
    out = [_cab_html("Mediciones", p)]
    out.append('<table><tr><th>Código</th><th>Ud</th><th>Descripción</th>'
               '<th class="num">Nº</th><th class="num">Largo</th>'
               '<th class="num">Ancho</th><th class="num">Alto</th>'
               '<th class="num">Parcial</th></tr>')
    for nivel, padre, c in _recorrer(p):
        if c.tipo == TipoConcepto.CAPITULO:
            sangria = "&nbsp;" * (nivel * 3)
            out.append(f'<tr class="cap"><td class="cod">{html.escape(c.codigo)}</td>'
                       f'<td></td><td colspan="6">{sangria}{html.escape(c.resumen)}</td></tr>')
        elif c.tipo == TipoConcepto.PARTIDA:
            med = c.mediciones.get(padre)
            out.append(f'<tr><td class="cod">{html.escape(c.codigo)}</td>'
                       f'<td>{html.escape(c.unidad)}</td>'
                       f'<td>{html.escape(c.resumen)}</td>'
                       f'<td colspan="4"></td>'
                       f'<td class="num"><b>{_fmt_num(med.total if med else 0, 3)}</b></td></tr>')
            if med:
                for ln in med.lineas:
                    out.append(f'<tr><td></td><td></td>'
                               f'<td class="sub">{html.escape(ln.comentario)}</td>'
                               f'<td class="num sub">{_fmt_num(ln.n_uds, 2) if ln.n_uds else ""}</td>'
                               f'<td class="num sub">{_fmt_num(ln.longitud, 2) if ln.longitud else ""}</td>'
                               f'<td class="num sub">{_fmt_num(ln.anchura, 2) if ln.anchura else ""}</td>'
                               f'<td class="num sub">{_fmt_num(ln.altura, 2) if ln.altura else ""}</td>'
                               f'<td class="num sub">{_fmt_num(ln.subtotal, 3)}</td></tr>')
    out.append('</table>')
    out.append(_pie_html())
    return "".join(out)


# --------------------------------------------------------------------------
# 2. CUADRO DE PRECIOS
# --------------------------------------------------------------------------

def informe_cuadro_precios(p: Presupuesto) -> str:
    out = [_cab_html("Cuadro de precios", p)]
    out.append('<table><tr><th>Código</th><th>Ud</th><th>Descripción</th>'
               '<th class="num">Precio</th></tr>')
    # Ordenamos: primero partidas, después unitarios, por código
    conceptos = sorted(
        [c for c in p.conceptos.values()
         if c.tipo in (TipoConcepto.PARTIDA, TipoConcepto.UNITARIO)],
        key=lambda c: (c.tipo != TipoConcepto.PARTIDA, c.codigo),
    )
    tipo_actual = None
    for c in conceptos:
        if c.tipo != tipo_actual:
            tipo_actual = c.tipo
            etiqueta = "Partidas" if c.tipo == TipoConcepto.PARTIDA else "Precios unitarios (mano de obra, materiales, maquinaria)"
            out.append(f'<tr class="cap"><td colspan="4">{etiqueta}</td></tr>')
        out.append(f'<tr><td class="cod">{html.escape(c.codigo)}</td>'
                   f'<td>{html.escape(c.unidad)}</td>'
                   f'<td>{html.escape(c.resumen)}</td>'
                   f'<td class="num">{_fmt_eur(c.precio)}</td></tr>')
    out.append('</table>')
    out.append(_pie_html())
    return "".join(out)


# --------------------------------------------------------------------------
# 3. PRESUPUESTO (con importes)
# --------------------------------------------------------------------------

def informe_presupuesto(p: Presupuesto) -> str:
    out = [_cab_html("Presupuesto", p)]
    out.append('<table><tr><th>Código</th><th>Ud</th><th>Descripción</th>'
               '<th class="num">Medición</th><th class="num">Precio</th>'
               '<th class="num">Importe</th></tr>')
    for nivel, padre, c in _recorrer(p):
        if c.tipo == TipoConcepto.CAPITULO:
            sangria = "&nbsp;" * (nivel * 3)
            importe_cap = p._importe_recursivo(c.codigo, padre) if padre else p.presupuesto_total()
            out.append(f'<tr class="cap"><td class="cod">{html.escape(c.codigo)}</td><td></td>'
                       f'<td>{sangria}{html.escape(c.resumen)}</td>'
                       f'<td colspan="2"></td>'
                       f'<td class="num">{_fmt_eur(importe_cap)}</td></tr>')
        elif c.tipo == TipoConcepto.PARTIDA:
            med = p.medicion_total(c.codigo, padre)
            imp = p.importe_en_padre(c.codigo, padre)
            out.append(f'<tr><td class="cod">{html.escape(c.codigo)}</td>'
                       f'<td>{html.escape(c.unidad)}</td>'
                       f'<td>{html.escape(c.resumen)}</td>'
                       f'<td class="num">{_fmt_num(med, 2)}</td>'
                       f'<td class="num">{_fmt_eur(c.precio)}</td>'
                       f'<td class="num">{_fmt_eur(imp)}</td></tr>')
    out.append(f'<tr class="total"><td colspan="5">TOTAL PRESUPUESTO DE EJECUCIÓN MATERIAL</td>'
               f'<td class="num">{_fmt_eur(p.presupuesto_total())}</td></tr>')
    out.append('</table>')
    out.append(_pie_html())
    return "".join(out)


# --------------------------------------------------------------------------
# 4. RESUMEN DE PRESUPUESTO (por capítulos)
# --------------------------------------------------------------------------

def informe_resumen(p: Presupuesto) -> str:
    out = [_cab_html("Resumen de presupuesto", p)]
    out.append('<table><tr><th>Código</th><th>Capítulo</th>'
               '<th class="num">Importe</th><th class="num">%</th></tr>')
    total = p.presupuesto_total()
    raiz = p.get(p.codigo_raiz) if p.codigo_raiz else None
    if raiz:
        for hijo in raiz.hijos:
            c = p.get(hijo.codigo_hijo)
            if c is None:
                continue
            importe = p._importe_recursivo(c.codigo, p.codigo_raiz)
            pct = (importe / total * 100) if total else 0
            out.append(f'<tr><td class="cod">{html.escape(c.codigo)}</td>'
                       f'<td>{html.escape(c.resumen)}</td>'
                       f'<td class="num">{_fmt_eur(importe)}</td>'
                       f'<td class="num">{_fmt_num(pct, 1)} %</td></tr>')
    out.append(f'<tr class="total"><td colspan="2">PRESUPUESTO DE EJECUCIÓN MATERIAL</td>'
               f'<td class="num">{_fmt_eur(total)}</td><td class="num">100,0 %</td></tr>')
    out.append('</table>')
    out.append(_pie_html())
    return "".join(out)


# --------------------------------------------------------------------------
# Despacho
# --------------------------------------------------------------------------

INFORMES = {
    "mediciones": informe_mediciones,
    "cuadro": informe_cuadro_precios,
    "presupuesto": informe_presupuesto,
    "resumen": informe_resumen,
}


def generar_informe(p: Presupuesto, tipo: str) -> str:
    fn = INFORMES.get(tipo)
    if fn is None:
        raise ValueError(f"Informe desconocido: {tipo}. Opciones: {list(INFORMES)}")
    return fn(p)
