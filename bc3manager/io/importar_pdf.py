"""
Importador de presupuestos en PDF generados con Presto.

Lee el documento "Presupuesto" tal como lo imprime Presto (también cuando se ha
pasado por Word antes de convertirlo a PDF) y reconstruye el presupuesto:

  - MEDICIONES ............ líneas de medición y cantidad total de cada partida
  - CUADRO DE PRECIOS Nº1 . precio de cada concepto, en cifra y en letra
  - CUADRO DE PRECIOS Nº2 . justificación del precio: coste directo y CI
  - PRESUPUESTO ........... árbol de capítulos, cantidad, precio e importe
  - RESUMEN ............... totales por capítulo, PEM, GG, BI e IVA

La fuente principal es la sección PRESUPUESTO (estructura, resumen, texto,
cantidad y precio). El resto de secciones sirven para CRUZAR datos: cada
discrepancia queda registrada como aviso en el informe de control, nunca se
corrige en silencio.

Uso típico (ver cli.py, subcomando importar-pdf):

    datos = leer_pdf_presto("presupuesto.pdf")
    p, control = construir_presupuesto(datos, modo_ci="incluido")
    escribir_bc3(p, "presupuesto.bc3")
    escribir_control_xlsx(control, "presupuesto_control.xlsx")

Requiere pdfplumber (y openpyxl para el informe Excel):
    pip install pdfplumber openpyxl
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from bc3manager.core.model import (
    Concepto, Hijo, LineaMedicion, Medicion, Presupuesto, TipoConcepto,
)


# =========================================================================
# Utilidades: números, textos, cantidades en letra
# =========================================================================

_RE_NUMERO = re.compile(r"^-?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?$")


def es_numero(texto: str) -> bool:
    """True si el texto es un número en formato español (1.234,56 / 32 / 0,45)."""
    return bool(_RE_NUMERO.match(texto))


def a_decimal(texto: str) -> Decimal:
    """'3.078.115,96' -> Decimal('3078115.96')."""
    return Decimal(texto.replace(".", "").replace(",", "."))


def redondea(valor: Decimal, decimales: int = 2) -> Decimal:
    """Redondeo mitad-arriba en Decimal exacto (como Presto)."""
    return valor.quantize(Decimal(1).scaleb(-decimales), rounding=ROUND_HALF_UP)


def unir_lineas(lineas: list[str], guion_mayusculas: bool = False) -> str:
    """Une las líneas de un texto partido por el ancho de columna.

    Deshace la separación silábica de Presto ("se-" + "guridad" -> "seguridad")
    solo cuando el guion está entre dos minúsculas. Un guion seguido de
    mayúscula o cifra se considera real y se conserva sin espacio
    ("UNE-" + "EN 1338" -> "UNE-EN 1338"). Con guion_mayusculas=True también se
    deshace entre mayúsculas (cantidades en letra: "EU-" + "ROS").
    """
    out = ""
    for t in lineas:
        t = t.strip()
        if not t:
            continue
        if not out:
            out = t
            continue
        if out.endswith("-") and len(out) >= 2 and out[-2].isalpha() and t[0].isalpha():
            silaba = (out[-2].islower() and t[0].islower()) or (
                guion_mayusculas and out[-2].isupper() and t[0].isupper())
            out = out[:-1] + t if silaba else out + t
        elif out.endswith("-") and len(out) >= 2 and out[-2] != " ":
            out = out + t
        else:
            out = out + " " + t
    return out


def normaliza(texto: str) -> str:
    """Forma canónica para COMPARAR textos entre secciones: sin espacios ni
    guiones (el corte de línea y la separación silábica cambian entre
    secciones porque cada una tiene un ancho de columna distinto)."""
    t = unicodedata.normalize("NFC", texto or "")
    return re.sub(r"[\s\-­]", "", t).casefold()


_UNIDADES_LETRA = {
    "CERO": 0, "UN": 1, "UNO": 1, "UNA": 1, "DOS": 2, "TRES": 3, "CUATRO": 4,
    "CINCO": 5, "SEIS": 6, "SIETE": 7, "OCHO": 8, "NUEVE": 9, "DIEZ": 10,
    "ONCE": 11, "DOCE": 12, "TRECE": 13, "CATORCE": 14, "QUINCE": 15,
    "DIECISEIS": 16, "DIECISIETE": 17, "DIECIOCHO": 18, "DIECINUEVE": 19,
    "VEINTE": 20, "VEINTIUN": 21, "VEINTIUNO": 21, "VEINTIUNA": 21,
    "VEINTIDOS": 22, "VEINTITRES": 23, "VEINTICUATRO": 24, "VEINTICINCO": 25,
    "VEINTISEIS": 26, "VEINTISIETE": 27, "VEINTIOCHO": 28, "VEINTINUEVE": 29,
    "TREINTA": 30, "CUARENTA": 40, "CINCUENTA": 50, "SESENTA": 60,
    "SETENTA": 70, "OCHENTA": 80, "NOVENTA": 90, "CIEN": 100, "CIENTO": 100,
    "DOSCIENTOS": 200, "DOSCIENTAS": 200, "TRESCIENTOS": 300, "TRESCIENTAS": 300,
    "CUATROCIENTOS": 400, "CUATROCIENTAS": 400, "QUINIENTOS": 500,
    "QUINIENTAS": 500, "SEISCIENTOS": 600, "SEISCIENTAS": 600,
    "SETECIENTOS": 700, "SETECIENTAS": 700, "OCHOCIENTOS": 800,
    "OCHOCIENTAS": 800, "NOVECIENTOS": 900, "NOVECIENTAS": 900,
}


def _sin_tildes(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t)
                   if unicodedata.category(c) != "Mn")


def _entero_en_letra(palabras: list[str]) -> Optional[int]:
    total = 0
    actual = 0
    vistas = False
    for w in palabras:
        if w == "Y":
            continue
        if w in _UNIDADES_LETRA:
            actual += _UNIDADES_LETRA[w]
            vistas = True
        elif w == "MIL":
            total += (actual or 1) * 1000
            actual = 0
            vistas = True
        elif w in ("MILLON", "MILLONES"):
            total = (total + (actual or 1)) * 1_000_000
            actual = 0
            vistas = True
        else:
            return None          # palabra desconocida: no arriesgar
    return total + actual if vistas else None


def cantidad_en_letra(texto: str) -> Optional[Decimal]:
    """'VEINTITRES EUROS con OCHENTA Y CUATRO CÉNTIMOS' -> Decimal('23.84').
    Devuelve None si el texto no se puede interpretar con seguridad."""
    t = _sin_tildes(texto).upper()
    t = re.sub(r"[^A-Z ]", " ", t)
    m = re.match(r"^\s*(.*?)\s*EUROS?\b(.*)$", t)
    if not m:
        return None
    euros = _entero_en_letra(m.group(1).split()) if m.group(1).strip() else 0
    if euros is None:
        return None
    resto = m.group(2)
    cent = 0
    mc = re.search(r"\bCON\b\s*(.*?)\s*CENTIMOS?\b", resto)
    if mc:
        cent = _entero_en_letra(mc.group(1).split())
        if cent is None:
            return None
    return Decimal(euros) + Decimal(cent) / 100


# =========================================================================
# Lectura del PDF: palabras -> líneas, con sección y columnas de cada página
# =========================================================================

@dataclass
class Palabra:
    texto: str
    x0: float
    x1: float
    top: float
    negrita: bool
    tam: float


@dataclass
class Linea:
    pagina: int
    seccion: str
    top: float
    palabras: list[Palabra]
    columnas: dict[str, tuple[float, float]]   # cabecera de columnas de la página

    @property
    def texto(self) -> str:
        return " ".join(p.texto for p in self.palabras)

    @property
    def x0(self) -> float:
        return self.palabras[0].x0

    @property
    def negrita(self) -> bool:
        return self.palabras[0].negrita

    @property
    def tam(self) -> float:
        return self.palabras[0].tam

    def es_raya(self) -> bool:
        return all(set(p.texto) == {"_"} for p in self.palabras)


SECCIONES = {
    "MEDICIONES": "mediciones",
    "CUADRODEPRECIOSN1": "cuadro1",
    "CUADRODEPRECIOSNO1": "cuadro1",
    "CUADRODEPRECIOSN2": "cuadro2",
    "CUADRODEPRECIOSNO2": "cuadro2",
    "PRESUPUESTO": "presupuesto",
    "PRESUPUESTOS": "presupuesto",
    "RESUMENDEPRESUPUESTO": "resumen",
}


def _clave_titulo(texto: str) -> str:
    t = _sin_tildes(texto).upper().replace("º", "").replace("ª", "")
    return re.sub(r"[^A-Z0-9]", "", t)


def _agrupar_lineas(palabras: list[Palabra], tolerancia: float = 2.5) -> list[list[Palabra]]:
    palabras = sorted(palabras, key=lambda p: (p.top, p.x0))
    grupos: list[list[Palabra]] = []
    for p in palabras:
        if grupos and abs(p.top - grupos[-1][0].top) <= tolerancia:
            grupos[-1].append(p)
        else:
            grupos.append([p])
    return [sorted(g, key=lambda p: p.x0) for g in grupos]


@dataclass
class DocumentoPDF:
    lineas: list[Linea]
    titulo_obra: str = ""
    paginas: int = 0
    paginas_por_seccion: dict[str, list[int]] = field(default_factory=dict)


def leer_lineas_pdf(ruta_pdf: str) -> DocumentoPDF:
    """Lee el PDF y devuelve sus líneas de contenido, sin cabeceras ni pies
    de página, etiquetadas con la sección a la que pertenecen."""
    try:
        import pdfplumber
    except ImportError as e:   # pragma: no cover - depende del entorno
        raise ImportError(
            "Para importar PDF hace falta pdfplumber: pip install pdfplumber") from e

    doc = DocumentoPDF(lineas=[])
    seccion = ""
    with pdfplumber.open(ruta_pdf) as pdf:
        doc.paginas = len(pdf.pages)
        for num, pag in enumerate(pdf.pages, start=1):
            crudas = pag.extract_words(extra_attrs=["fontname", "size"])
            palabras = [
                Palabra(w["text"], w["x0"], w["x1"], w["top"],
                        "bold" in w["fontname"].lower(), round(w["size"], 1))
                for w in crudas
            ]
            grupos = _agrupar_lineas(palabras)
            if not grupos:
                continue
            clave = _clave_titulo(" ".join(p.texto for p in grupos[0]))
            if clave in SECCIONES:
                seccion = SECCIONES[clave]
            # Cabecera de columnas ("CÓDIGO ... PRECIO") y la raya que la cierra
            columnas: dict[str, tuple[float, float]] = {}
            inicio = None
            for i, g in enumerate(grupos[:6]):
                if _clave_titulo(g[0].texto) in ("CODIGO", "CAPITULO") and len(g) > 2:
                    columnas = {_clave_titulo(p.texto): (p.x0, p.x1) for p in g}
                    inicio = i + 1
                    if inicio < len(grupos) and all(set(p.texto) == {"_"} for p in grupos[inicio]):
                        inicio += 1
                    break
            if inicio is None:
                continue              # portada de sección: sin contenido
            # Pie de página: la última raya ancha en el cuarto inferior
            fin = len(grupos)
            for i in range(len(grupos) - 1, inicio - 1, -1):
                g = grupos[i]
                if (g[0].top > 0.75 * float(pag.height) and g[0].x0 < 60
                        and all(set(p.texto) == {"_"} for p in g)):
                    fin = i
                    if not doc.titulo_obra:
                        pie = [x for x in grupos[i + 1:]
                               if not (len(x) == 1 and x[0].texto.isdigit())]
                        doc.titulo_obra = " ".join(
                            " ".join(p.texto for p in x) for x in pie).strip(" ¡")
                    break
            doc.paginas_por_seccion.setdefault(seccion, []).append(num)
            for g in grupos[inicio:fin]:
                doc.lineas.append(Linea(num, seccion, g[0].top, g, columnas))
    return doc


# =========================================================================
# Estructuras extraídas
# =========================================================================

NIVELES = ["CAPITULO", "SUBCAPITULO", "APARTADO", "SUBAPARTADO",
           "ELEMENTO", "SUBELEMENTO"]
_RE_CABECERA = re.compile(r"^(\S+)\s+(\S+)\s*(.*)$")


@dataclass
class Capitulo:
    codigo: str
    nivel: str
    resumen: str
    pagina: int
    hijos: list = field(default_factory=list)     # Capitulo | Ocurrencia
    total_pdf: Optional[Decimal] = None


@dataclass
class Ocurrencia:
    """Una aparición de una partida dentro de un capítulo del PRESUPUESTO."""
    codigo: str
    unidad: str
    resumen: str
    texto: str
    pagina: int
    padre: str
    indice: int                       # nº de aparición de ese código en ese padre
    ruta: str = ""
    cantidad: Optional[Decimal] = None
    precio: Optional[Decimal] = None
    importe: Optional[Decimal] = None


@dataclass
class LineaMed:
    comentario: str
    uds: Optional[Decimal] = None
    longitud: Optional[Decimal] = None
    anchura: Optional[Decimal] = None
    altura: Optional[Decimal] = None
    parcial: Optional[Decimal] = None


@dataclass
class MedicionPDF:
    codigo: str
    unidad: str
    resumen: str
    texto: str
    pagina: int
    padre: str
    indice: int
    lineas: list[LineaMed] = field(default_factory=list)
    total: Optional[Decimal] = None


@dataclass
class PrecioC1:
    codigo: str
    unidad: str
    resumen: str
    texto: str
    pagina: int
    precio: Optional[Decimal] = None
    letra: str = ""
    precio_letra: Optional[Decimal] = None


@dataclass
class PrecioC2:
    codigo: str
    unidad: str
    resumen: str
    texto: str
    pagina: int
    componentes: list[tuple[str, Optional[Decimal], Decimal]] = field(default_factory=list)
    suma: Optional[Decimal] = None          # coste directo ("Suma la partida")
    ci_pct: Optional[Decimal] = None        # % de costes indirectos
    ci_importe: Optional[Decimal] = None
    total: Optional[Decimal] = None         # TOTAL PARTIDA


@dataclass
class ResumenPDF:
    capitulos: list[tuple[str, str, Decimal]] = field(default_factory=list)
    pem: Optional[Decimal] = None
    gg_pct: Optional[Decimal] = None
    gg: Optional[Decimal] = None
    bi_pct: Optional[Decimal] = None
    bi: Optional[Decimal] = None
    pec: Optional[Decimal] = None
    iva_pct: Optional[Decimal] = None
    iva: Optional[Decimal] = None
    total: Optional[Decimal] = None


@dataclass
class DatosPDF:
    """Todo lo extraído del PDF, sección por sección, sin interpretar."""
    titulo_obra: str
    raiz: Capitulo                                  # árbol del PRESUPUESTO
    ocurrencias: list[Ocurrencia]
    pem_pdf: Optional[Decimal]                      # TOTAL PRESUPUESTO
    mediciones: list[MedicionPDF]
    cuadro1: dict[str, list[PrecioC1]]
    cuadro2: dict[str, list[PrecioC2]]
    resumen: ResumenPDF
    avisos_lectura: list[str]
    paginas_por_seccion: dict[str, list[int]]


# =========================================================================
# Parsers por sección
# =========================================================================

def _x_unidad(linea: Linea) -> float:
    """Inicio de la columna de unidad: 'UD' en los cuadros; en mediciones y
    presupuesto la unidad va al principio de la columna 'RESUMEN'."""
    c = linea.columnas
    if "UD" in c:
        return c["UD"][0]
    if "RESUMEN" in c:
        return c["RESUMEN"][0]
    return 95.0


def _es_cabecera_partida(linea: Linea) -> bool:
    """Línea de código + unidad + resumen (negrita pequeña, en la columna de
    código). Excluye los totales de capítulo y las rayas."""
    return (linea.negrita and linea.tam < 9.5 and linea.x0 < 70
            and not linea.texto.startswith("TOTAL") and not linea.es_raya())


def _partir_cabecera(linea: Linea) -> tuple[str, str, str, list[Palabra]]:
    """Separa código, unidad y resumen de una cabecera de partida. Devuelve
    también las palabras sobrantes de la derecha (precio en el cuadro nº1)."""
    xu = _x_unidad(linea)
    pal = linea.palabras
    codigo = [p for p in pal if p.x1 < xu - 0.5]
    resto = [p for p in pal if p.x1 >= xu - 0.5]
    unidad = ""
    if resto and resto[0].x0 < xu + 4 and len(resto) > 1:
        unidad = resto[0].texto
        resto = resto[1:]
    # Cifras pegadas al margen derecho (precio del cuadro nº1)
    derecha: list[Palabra] = []
    while resto and es_numero(resto[-1].texto) and resto[-1].x0 > 450:
        derecha.insert(0, resto.pop())
    return (" ".join(p.texto for p in codigo), unidad,
            " ".join(p.texto for p in resto), derecha)


class _Arbol:
    """Pila de capítulos común a las secciones con estructura de capítulos."""

    def __init__(self, avisos: list[str], seccion: str) -> None:
        self.raiz = Capitulo("", "OBRA", "", 0)
        self.pila: list[Capitulo] = [self.raiz]
        self.avisos = avisos
        self.seccion = seccion
        self.total_pendiente: Optional[Capitulo] = None
        self.total_obra: Optional[Decimal] = None
        self._pendiente_obra = False

    @property
    def actual(self) -> Capitulo:
        return self.pila[-1]

    def procesa(self, linea: Linea) -> bool:
        """Consume la línea si es cabecera o total de capítulo."""
        # Importe de un TOTAL que no cupo en su línea y bajó a la siguiente
        if (self.total_pendiente is not None or self._pendiente_obra) and \
                len(linea.palabras) == 1 and es_numero(linea.palabras[0].texto):
            v = a_decimal(linea.palabras[0].texto)
            if self._pendiente_obra:
                self.total_obra, self._pendiente_obra = v, False
            else:
                self.total_pendiente.total_pdf, self.total_pendiente = v, None
            return True
        if not (linea.negrita and linea.tam >= 9.5):
            return False
        palabras = [p.texto for p in linea.palabras]
        if palabras[0] == "TOTAL":
            num = [t for t in palabras if es_numero(t)]
            valor = a_decimal(num[-1]) if num else None
            if len(palabras) > 1 and _clave_titulo(palabras[1]) in NIVELES and len(palabras) > 2:
                codigo = palabras[2]
                for i in range(len(self.pila) - 1, 0, -1):
                    if self.pila[i].codigo == codigo:
                        nodo = self.pila[i]
                        nodo.total_pdf = valor
                        if valor is None:
                            self.total_pendiente = nodo
                        del self.pila[i:]
                        break
                else:
                    self.avisos.append(
                        f"[{self.seccion}] pág. {linea.pagina}: TOTAL de '{codigo}' sin capítulo abierto")
                return True
            if len(palabras) > 1 and _clave_titulo(palabras[1]).startswith("PRESUPUESTO"):
                self.total_obra = valor
                self._pendiente_obra = valor is None
                return True
            return False
        m = _RE_CABECERA.match(linea.texto)
        if m and _clave_titulo(m.group(1)) in NIVELES:
            nivel = _clave_titulo(m.group(1))
            prof = NIVELES.index(nivel) + 1
            while len(self.pila) > prof:
                self.pila.pop()
            if len(self.pila) < prof:
                self.avisos.append(
                    f"[{self.seccion}] pág. {linea.pagina}: {nivel} {m.group(2)} sin nivel superior")
            nodo = Capitulo(m.group(2), nivel, m.group(3).strip(), linea.pagina)
            self.actual.hijos.append(nodo)
            self.pila.append(nodo)
            return True
        return False


def _parse_presupuesto(lineas: list[Linea], avisos: list[str]):
    arbol = _Arbol(avisos, "presupuesto")
    ocurrencias: list[Ocurrencia] = []
    cuenta: dict[tuple[str, str], int] = {}
    oc: Optional[Ocurrencia] = None
    texto: list[str] = []

    def cerrar_texto() -> None:
        # Solo si hay texto pendiente: la línea de cifras ya cerró el texto y
        # la cabecera siguiente no debe pisarlo con una lista vacía.
        if oc is not None and texto:
            oc.texto = unir_lineas(texto)

    for ln in lineas:
        if arbol.procesa(ln):
            continue
        if ln.es_raya():
            continue
        if _es_cabecera_partida(ln):
            cerrar_texto()
            codigo, unidad, resumen, _ = _partir_cabecera(ln)
            padre = arbol.actual
            k = (padre.codigo, codigo)
            cuenta[k] = cuenta.get(k, 0) + 1
            ruta = " / ".join(c.codigo for c in arbol.pila[1:])
            oc = Ocurrencia(codigo, unidad, resumen, "", ln.pagina,
                            padre.codigo, cuenta[k] - 1, ruta)
            padre.hijos.append(oc)
            ocurrencias.append(oc)
            texto = []
            continue
        if oc is None:
            continue
        if not ln.negrita and ln.tam >= 8.5:
            texto.append(ln.texto)
            continue
        if not ln.negrita and all(es_numero(p.texto) for p in ln.palabras):
            col = ln.columnas
            valores: dict[str, Decimal] = {}
            for p in ln.palabras:
                destino = min(("CANTIDAD", "PRECIO", "IMPORTE"),
                              key=lambda c: abs(col.get(c, (0, 1e9))[1] - p.x1))
                valores[destino] = a_decimal(p.texto)
            oc.cantidad = valores.get("CANTIDAD")
            oc.precio = valores.get("PRECIO")
            oc.importe = valores.get("IMPORTE")
            cerrar_texto()
            texto = []
            continue
        avisos.append(f"[presupuesto] pág. {ln.pagina}: línea no reconocida: {ln.texto[:80]}")
    cerrar_texto()
    return arbol.raiz, ocurrencias, arbol.total_obra


_COLS_MED = (("UDS", "uds"), ("LONGITUD", "longitud"), ("ANCHURA", "anchura"),
             ("ALTURA", "altura"), ("PARCIALES", "parcial"), ("CANTIDAD", "total"))


def _parse_mediciones(lineas: list[Linea], avisos: list[str]) -> list[MedicionPDF]:
    arbol = _Arbol(avisos, "mediciones")
    res: list[MedicionPDF] = []
    cuenta: dict[tuple[str, str], int] = {}
    med: Optional[MedicionPDF] = None
    texto: list[str] = []
    ultima_era_medida = False

    for ln in lineas:
        if arbol.procesa(ln):
            continue
        if ln.es_raya():
            continue
        if _es_cabecera_partida(ln):
            if med is not None and not med.texto:
                med.texto = unir_lineas(texto)
            codigo, unidad, resumen, _ = _partir_cabecera(ln)
            padre = arbol.actual.codigo
            k = (padre, codigo)
            cuenta[k] = cuenta.get(k, 0) + 1
            med = MedicionPDF(codigo, unidad, resumen, "", ln.pagina, padre, cuenta[k] - 1)
            res.append(med)
            texto = []
            ultima_era_medida = False
            continue
        if med is None:
            continue
        if not ln.negrita and ln.tam >= 8.5:
            texto.append(ln.texto)
            continue
        # Línea de medición (letra pequeña): comentario + factores + parcial
        if not med.texto:
            med.texto = unir_lineas(texto)
        col = ln.columnas
        x_uds = col.get("UDS", (230, 244))[0]
        comentario: list[str] = []
        valores: dict[str, Decimal] = {}
        for p in ln.palabras:
            if es_numero(p.texto) and p.x1 > x_uds - 5:
                nombre, campo = min(_COLS_MED, key=lambda c: abs(col.get(c[0], (0, 1e9))[1] - p.x1))
                if abs(col.get(nombre, (0, 1e9))[1] - p.x1) <= 10 and campo not in valores:
                    valores[campo] = a_decimal(p.texto)
                    continue
            comentario.append(p.texto)
        coment = " ".join(comentario)
        total = valores.pop("total", None)
        if total is not None:
            med.total = total
        if valores:
            med.lineas.append(LineaMed(coment, valores.get("uds"), valores.get("longitud"),
                                       valores.get("anchura"), valores.get("altura"),
                                       valores.get("parcial")))
            ultima_era_medida = True
        elif coment and total is None:
            if ultima_era_medida and med.lineas:
                # Comentario largo que continúa en la línea siguiente
                med.lineas[-1].comentario = unir_lineas([med.lineas[-1].comentario, coment])
            else:
                med.lineas.append(LineaMed(coment))
        # "Total cantidades alzadas 1,00": comentario de la propia línea de total
    return res


def _parse_cuadro1(lineas: list[Linea], avisos: list[str]) -> dict[str, list[PrecioC1]]:
    arbol = _Arbol(avisos, "cuadro1")
    res: dict[str, list[PrecioC1]] = {}
    e: Optional[PrecioC1] = None
    texto: list[str] = []
    letra: list[str] = []

    def cerrar() -> None:
        if e is not None:
            e.texto = unir_lineas(texto)
            e.letra = unir_lineas(letra, guion_mayusculas=True)
            e.precio_letra = cantidad_en_letra(e.letra) if e.letra else None

    for ln in lineas:
        if arbol.procesa(ln) or ln.es_raya():
            continue
        if _es_cabecera_partida(ln):
            cerrar()
            codigo, unidad, resumen, derecha = _partir_cabecera(ln)
            e = PrecioC1(codigo, unidad, resumen, "", ln.pagina,
                         a_decimal(derecha[-1].texto) if derecha else None)
            res.setdefault(codigo, []).append(e)
            texto, letra = [], []
            continue
        if e is None:
            continue
        if ln.x0 > _x_unidad(ln) + 150:
            letra.append(ln.texto)
        else:
            texto.append(ln.texto)
    cerrar()
    return res


def _parse_cuadro2(lineas: list[Linea], avisos: list[str]) -> dict[str, list[PrecioC2]]:
    arbol = _Arbol(avisos, "cuadro2")
    res: dict[str, list[PrecioC2]] = {}
    e: Optional[PrecioC2] = None
    texto: list[str] = []

    for ln in lineas:
        if arbol.procesa(ln) or ln.es_raya():
            continue
        if _es_cabecera_partida(ln):
            if e is not None and not e.texto:
                e.texto = unir_lineas(texto)
            codigo, unidad, resumen, _ = _partir_cabecera(ln)
            e = PrecioC2(codigo, unidad, resumen, "", ln.pagina)
            res.setdefault(codigo, []).append(e)
            texto = []
            continue
        if e is None:
            continue
        if ln.x0 > _x_unidad(ln) + 150:
            # Línea de justificación: "Etiqueta ...... [6,00%] importe"
            nums = [p.texto for p in ln.palabras if es_numero(p.texto)]
            if not nums:
                continue
            importe = a_decimal(nums[-1])
            pct = None
            for p in ln.palabras:
                if p.texto.endswith("%") and es_numero(p.texto[:-1]):
                    pct = a_decimal(p.texto[:-1])
            etiqueta = " ".join(p.texto for p in ln.palabras
                                if not set(p.texto) <= set(".") and not es_numero(p.texto)
                                and not p.texto.endswith("%")).strip(" .")
            etiqueta = re.sub(r"\.{2,}.*$", "", etiqueta).strip()
            clave = _clave_titulo(etiqueta)
            if clave.startswith("TOTALPARTIDA"):
                e.total = importe
            elif clave.startswith("SUMALAPARTIDA"):
                e.suma = importe
            elif clave.startswith("COSTESINDIRECTOS"):
                e.ci_pct, e.ci_importe = pct, importe
            else:
                e.componentes.append((etiqueta, pct, importe))
            if not e.texto:
                e.texto = unir_lineas(texto)
        else:
            texto.append(ln.texto)
    if e is not None and not e.texto:
        e.texto = unir_lineas(texto)
    return res


def _parse_resumen(lineas: list[Linea]) -> ResumenPDF:
    r = ResumenPDF()
    for ln in lineas:
        t = ln.texto
        nums = [p.texto for p in ln.palabras if es_numero(p.texto)]
        clave = _clave_titulo(t)
        if not nums:
            continue
        if "EJECUCIONMATERIAL" in clave:
            r.pem = a_decimal(nums[-1])
        elif "GASTOSGENERALES" in clave:
            r.gg_pct, r.gg = a_decimal(nums[0]), a_decimal(nums[-1])
        elif "BENEFICIOINDUSTRIAL" in clave:
            r.bi_pct, r.bi = a_decimal(nums[0]), a_decimal(nums[-1])
        elif "EJECUCIONPORCONTRATA" in clave:
            r.pec = a_decimal(nums[-1])
        elif "IVA" in clave and "%" in t:
            r.iva_pct, r.iva = a_decimal(nums[0]), a_decimal(nums[-1])
        elif "LICITACION" in clave or "TOTALPRESUPUESTO" in clave:
            r.total = a_decimal(nums[-1])
        elif ln.x0 < 70 and len(nums) >= 2:
            # Capítulo: código, nombre ......, importe, %
            nombre = " ".join(p.texto for p in ln.palabras[1:]
                              if not es_numero(p.texto) and not set(p.texto) <= set("."))
            nombre = re.sub(r"\.{2,}.*$", "", nombre).strip(" .")
            r.capitulos.append((ln.palabras[0].texto, nombre, a_decimal(nums[-2])))
    return r


def leer_pdf_presto(ruta_pdf: str) -> DatosPDF:
    """Extrae todas las secciones del PDF de presupuesto de Presto."""
    return analizar_documento(leer_lineas_pdf(ruta_pdf))


def analizar_documento(doc: DocumentoPDF) -> DatosPDF:
    """Interpreta las líneas ya leídas del PDF (separado de la lectura, que es
    lo lento, para poder probar los parsers sin volver a abrir el PDF)."""
    avisos: list[str] = []
    por_sec: dict[str, list[Linea]] = {}
    for ln in doc.lineas:
        por_sec.setdefault(ln.seccion, []).append(ln)
    if "presupuesto" not in por_sec:
        raise ValueError("No se ha encontrado la sección PRESUPUESTO en el PDF")
    raiz, ocurrencias, pem = _parse_presupuesto(por_sec["presupuesto"], avisos)
    return DatosPDF(
        titulo_obra=doc.titulo_obra,
        raiz=raiz,
        ocurrencias=ocurrencias,
        pem_pdf=pem,
        mediciones=_parse_mediciones(por_sec.get("mediciones", []), avisos),
        cuadro1=_parse_cuadro1(por_sec.get("cuadro1", []), avisos),
        cuadro2=_parse_cuadro2(por_sec.get("cuadro2", []), avisos),
        resumen=_parse_resumen(por_sec.get("resumen", [])),
        avisos_lectura=avisos,
        paginas_por_seccion=doc.paginas_por_seccion,
    )


# =========================================================================
# Construcción del Presupuesto de BC3Manager + informe de control
# =========================================================================

ERROR = "ERROR"      # afecta a importes o no se puede representar en BC3
AVISO = "AVISO"      # dato descriptivo distinto entre secciones
INFO = "INFO"        # decisión tomada por el importador, para conocimiento


@dataclass
class Aviso:
    gravedad: str
    tipo: str
    codigo: str
    ubicacion: str
    detalle: str
    valor_presupuesto: str = ""
    valor_otro: str = ""


@dataclass
class FilaPartida:
    """Una aparición de partida en el presupuesto, con todos sus cruces."""
    ruta: str
    padre: str
    codigo: str
    unidad: str
    resumen: str
    pagina: int
    cantidad: Optional[Decimal]
    precio: Optional[Decimal]
    importe: Optional[Decimal]
    importe_calc: Optional[Decimal] = None
    med_total: Optional[Decimal] = None
    med_lineas: int = 0
    med_lineas_en_bc3: bool = False
    c1_precio: Optional[Decimal] = None
    c1_precio_letra: Optional[Decimal] = None
    c2_cd: Optional[Decimal] = None
    c2_ci_pct: Optional[Decimal] = None
    c2_total: Optional[Decimal] = None
    cd_mas_ci: Optional[Decimal] = None
    bc3_importe: Optional[Decimal] = None
    bc3_importe_releido: Optional[Decimal] = None
    padre_bc3: str = ""
    avisos: list[str] = field(default_factory=list)
    gravedad: str = ""


@dataclass
class FilaCapitulo:
    ruta: str
    codigo: str
    nivel: str
    resumen: str
    total_pdf: Optional[Decimal]
    suma_pdf: Decimal
    bc3_importe: Optional[Decimal] = None
    bc3_importe_releido: Optional[Decimal] = None
    resumen_pdf: Optional[Decimal] = None   # importe en la hoja de RESUMEN


@dataclass
class Control:
    titulo_obra: str
    ruta_pdf: str = ""
    modo_ci: str = "incluido"
    filas: list[FilaPartida] = field(default_factory=list)
    capitulos: list[FilaCapitulo] = field(default_factory=list)
    avisos: list[Aviso] = field(default_factory=list)
    globales: list[tuple[str, str, str]] = field(default_factory=list)
    ci_conclusion: str = ""
    ci_pct: Optional[Decimal] = None
    pem_pdf: Optional[Decimal] = None
    pem_bc3: Optional[Decimal] = None
    pem_bc3_releido: Optional[Decimal] = None

    def cuenta(self, gravedad: str) -> int:
        return sum(1 for a in self.avisos if a.gravedad == gravedad)


def _f(v: Optional[Decimal]) -> float:
    return float(v) if v is not None else 0.0


def _d(v: float) -> Decimal:
    return redondea(Decimal(str(v)), 2)


def _cod_cap(codigo: str) -> str:
    return codigo + "#"


def _firma_capitulo(c: Capitulo) -> tuple:
    """Contenido de un capítulo, para saber si dos apariciones son el mismo."""
    out = []
    for h in c.hijos:
        if isinstance(h, Capitulo):
            out.append(("C", h.codigo, _firma_capitulo(h)))
        else:
            out.append(("P", h.codigo, h.cantidad, h.precio))
    return tuple(out)


def _analizar_ci(datos: DatosPDF, control: Control) -> None:
    """Decide, con los datos del PDF, si el precio del presupuesto lleva el CI."""
    total = con_ci = sin_ci = 0
    pcts: set[Decimal] = set()
    reproduce = 0
    for o in datos.ocurrencias:
        e = (datos.cuadro2.get(o.codigo) or [None])[0]
        if e is None or e.total is None or o.precio is None:
            continue
        total += 1
        if e.ci_pct is not None:
            pcts.add(e.ci_pct)
        if o.precio == e.total and e.suma is not None and e.suma != e.total:
            con_ci += 1
        elif e.suma is not None and o.precio == e.suma:
            sin_ci += 1
        if e.suma is not None and e.ci_pct is not None and \
                redondea(e.suma * (1 + e.ci_pct / 100)) == e.total:
            reproduce += 1
    control.ci_pct = next(iter(pcts)) if len(pcts) == 1 else None
    pct_txt = _pct(control.ci_pct) if control.ci_pct is not None else \
        ("varios: " + ", ".join(_pct(p) for p in sorted(pcts)) if pcts else "no indicado")
    if total == 0:
        control.ci_conclusion = "Sin cuadro de precios nº2: no se puede comprobar el CI."
    elif con_ci == total:
        control.ci_conclusion = (
            f"El precio del PRESUPUESTO INCLUYE los costes indirectos ({pct_txt}) en las "
            f"{total} partidas: coincide con el TOTAL PARTIDA del cuadro nº2 y no con la "
            f"'Suma la partida' (coste directo). Además, CD × (1 + CI) redondeado reproduce "
            f"el precio en {reproduce} de {total} partidas.")
    elif sin_ci == total:
        control.ci_conclusion = (
            f"El precio del PRESUPUESTO es COSTE DIRECTO (sin CI) en las {total} partidas; "
            f"CI declarado en el cuadro nº2: {pct_txt}.")
    else:
        control.ci_conclusion = (
            f"Mezcla: {con_ci} partidas con CI incluido, {sin_ci} sin CI, "
            f"{total - con_ci - sin_ci} que no encajan en ninguno de los dos casos. Revisar.")
    control.globales.append(("Costes indirectos (cuadro nº2)", pct_txt, control.ci_conclusion))
    control.globales.append((
        "CD × (1+CI) reproduce el precio", f"{reproduce} de {total}",
        "Necesario para poder guardar el CI aparte (modo 'separado')."))


def construir_presupuesto(datos: DatosPDF, modo_ci: str = "incluido",
                          codigo_obra: str = "OBRA##") -> tuple[Presupuesto, Control]:
    """Monta el Presupuesto de BC3Manager a partir de lo leído en el PDF y
    devuelve también el informe de control con todos los cruces.

    modo_ci:
      "incluido"  precio de partida = precio del presupuesto (con CI) y CI = 0
                  en el ~K. Es lo más seguro: el importe no depende de cómo
                  aplique el CI el programa que abra el BC3.
      "separado"  precio de partida = coste directo del cuadro nº2 y el % de CI
                  en el ~K, como lo tenía Presto. BC3Manager recompone el precio
                  con precio_con_ci().
    """
    if modo_ci not in ("incluido", "separado"):
        raise ValueError("modo_ci debe ser 'incluido' o 'separado'")
    control = Control(titulo_obra=datos.titulo_obra, modo_ci=modo_ci, pem_pdf=datos.pem_pdf)
    av = control.avisos
    for a in datos.avisos_lectura:
        av.append(Aviso(AVISO, "Lectura", "", "", a))
    _analizar_ci(datos, control)

    p = Presupuesto()
    p.redondeo_activo = True
    p.dec_cantrend = 3
    p.tipo_datos = "1"
    r = datos.resumen
    p.gg_pct = float(r.gg_pct) / 100 if r.gg_pct is not None else 0.0
    p.bi_pct = float(r.bi_pct) / 100 if r.bi_pct is not None else 0.0
    p.iva_pct = float(r.iva_pct) / 100 if r.iva_pct is not None else 0.0
    if modo_ci == "separado":
        if control.ci_pct is None:
            raise ValueError("Modo 'separado' imposible: el CI no es único en el cuadro nº2")
        p.ci_pct = float(control.ci_pct) / 100

    raiz = Concepto(codigo=codigo_obra, resumen=datos.titulo_obra or "Obra",
                    tipo=TipoConcepto.CAPITULO, precio_es_dato=False)
    p.add_concepto(raiz)
    p.codigo_raiz = codigo_obra

    mediciones = {(m.padre, m.codigo, m.indice): m for m in datos.mediciones}
    primera: dict[str, Ocurrencia] = {}
    vistos_cap: dict[str, tuple] = {}
    en_padre: set[tuple[str, str]] = set()

    def anota(fila: FilaPartida, gravedad: str, tipo: str, detalle: str,
              v_pres: str = "", v_otro: str = "") -> None:
        fila.avisos.append(detalle)
        if gravedad == ERROR or (gravedad == AVISO and fila.gravedad != ERROR):
            fila.gravedad = gravedad
        av.append(Aviso(gravedad, tipo, fila.codigo,
                        f"{fila.ruta} (pág. {fila.pagina})", detalle, v_pres, v_otro))

    def compara_texto(fila: FilaPartida, o: Ocurrencia, seccion: str,
                      unidad: str, resumen: str, texto: str) -> None:
        if unidad != o.unidad:
            anota(fila, AVISO, "Unidad distinta", f"Unidad distinta en {seccion}", o.unidad, unidad)
        if normaliza(resumen) != normaliza(o.resumen):
            anota(fila, AVISO, "Resumen distinto", f"Resumen distinto en {seccion}", o.resumen, resumen)
        if normaliza(texto) != normaliza(o.texto):
            detalle = (f"Descripción vacía en {seccion}" if not texto
                       else f"Descripción distinta en {seccion}")
            anota(fila, AVISO, "Descripción distinta", detalle, o.texto, texto)

    def procesa_partida(o: Ocurrencia, padre_bc3: str, solo_control: bool = False) -> None:
        fila = FilaPartida(o.ruta, o.padre, o.codigo, o.unidad, o.resumen, o.pagina,
                           o.cantidad, o.precio, o.importe, padre_bc3=padre_bc3)
        control.filas.append(fila)
        if o.cantidad is None or o.precio is None or o.importe is None:
            anota(fila, ERROR, "Cifras", "No se han leído cantidad, precio e importe")
            return
        fila.importe_calc = redondea(o.cantidad * o.precio)
        if fila.importe_calc != o.importe:
            anota(fila, ERROR, "Importe", "Cantidad × precio no da el importe del PDF",
                  str(o.importe), str(fila.importe_calc))
        if not o.texto:
            anota(fila, AVISO, "Sin descripción", "La partida no tiene descripción en el presupuesto")

        # --- Cuadro de precios nº1 ---
        c1 = (datos.cuadro1.get(o.codigo) or [None])[0]
        if c1 is None:
            anota(fila, ERROR, "Cuadro nº1", "No aparece en el cuadro de precios nº1")
        else:
            fila.c1_precio, fila.c1_precio_letra = c1.precio, c1.precio_letra
            if c1.precio != o.precio:
                anota(fila, ERROR, "Precio cuadro nº1", "Precio distinto en el cuadro nº1",
                      str(o.precio), str(c1.precio))
            if c1.precio_letra is None:
                anota(fila, AVISO, "Precio en letra", "No se ha podido leer el precio en letra",
                      "", c1.letra)
            elif c1.precio_letra != c1.precio:
                anota(fila, ERROR, "Precio en letra", "El precio en letra no coincide con la cifra",
                      str(c1.precio), f"{c1.precio_letra} ({c1.letra})")
            compara_texto(fila, o, "cuadro nº1", c1.unidad, c1.resumen, c1.texto)
        # --- Cuadro de precios nº2 ---
        c2 = (datos.cuadro2.get(o.codigo) or [None])[0]
        if c2 is None:
            anota(fila, AVISO, "Cuadro nº2", "No aparece en el cuadro de precios nº2")
        else:
            fila.c2_cd, fila.c2_ci_pct, fila.c2_total = c2.suma, c2.ci_pct, c2.total
            if c2.suma is not None and c2.ci_pct is not None:
                fila.cd_mas_ci = redondea(c2.suma * (1 + c2.ci_pct / 100))
            if c2.total != o.precio:
                anota(fila, ERROR, "Precio cuadro nº2", "TOTAL PARTIDA del cuadro nº2 distinto del precio",
                      str(o.precio), str(c2.total))
            if c2.componentes and c2.suma is not None and \
                    sum(x[2] for x in c2.componentes) != c2.suma:
                anota(fila, AVISO, "Justificación", "La suma de la justificación no da 'Suma la partida'",
                      str(c2.suma), str(sum(x[2] for x in c2.componentes)))
            compara_texto(fila, o, "cuadro nº2", c2.unidad, c2.resumen, c2.texto)

        if solo_control:
            # Partida de un capítulo compartido: ya está en el BC3 por la
            # primera aparición del capítulo; aquí solo se comprueba.
            fila.med_lineas_en_bc3 = True
            return

        # --- Concepto único por código (BC3: un código = un concepto) ---
        if o.codigo not in primera:
            primera[o.codigo] = o
            precio = o.precio
            if modo_ci == "separado":
                if c2 is not None and c2.suma is not None:
                    precio = c2.suma
                else:
                    anota(fila, ERROR, "CI separado", "Sin coste directo en el cuadro nº2")
            c = Concepto(codigo=o.codigo, unidad=o.unidad, resumen=o.resumen, texto=o.texto,
                         precio=float(precio), tipo=TipoConcepto.PARTIDA, precio_es_dato=True)
            c._precio_bc3 = float(precio)
            p.add_concepto(c)
        else:
            o1 = primera[o.codigo]
            if o.precio != o1.precio:
                anota(fila, ERROR, "Código repetido",
                      f"Mismo código con otro precio que en {o1.ruta}: el BC3 solo admite uno",
                      str(o1.precio), str(o.precio))
            if o.unidad != o1.unidad:
                anota(fila, AVISO, "Código repetido", f"Mismo código con otra unidad que en {o1.ruta}",
                      o1.unidad, o.unidad)
            if normaliza(o.resumen) != normaliza(o1.resumen):
                anota(fila, AVISO, "Código repetido", f"Mismo código con otro resumen que en {o1.ruta}",
                      o1.resumen, o.resumen)
            if normaliza(o.texto) != normaliza(o1.texto):
                anota(fila, AVISO, "Código repetido",
                      f"Mismo código con otra descripción que en {o1.ruta}", o1.texto, o.texto)
        concepto = p.get(o.codigo)

        # --- Medición ---
        if (padre_bc3, o.codigo) in en_padre:
            anota(fila, ERROR, "Medición duplicada",
                  "El código aparece dos veces en el mismo capítulo: el BC3 solo guarda una medición")
            return
        en_padre.add((padre_bc3, o.codigo))
        m = mediciones.get((o.padre, o.codigo, o.indice))
        medicion = Medicion(total_declarado=float(o.cantidad))
        if m is None:
            anota(fila, AVISO, "Mediciones", "No aparece en el documento de mediciones: solo cantidad total")
        else:
            fila.med_total = m.total
            fila.med_lineas = sum(1 for l in m.lineas if l.parcial is not None)
            if m.total != o.cantidad:
                anota(fila, ERROR, "Medición", "La cantidad de mediciones no coincide con el presupuesto",
                      str(o.cantidad), str(m.total))
            compara_texto(fila, o, "mediciones", m.unidad, m.resumen, m.texto)
            for l in m.lineas:
                if l.parcial is None:
                    continue
                prod = Decimal(1)
                for v in (l.uds, l.longitud, l.anchura, l.altura):
                    if v:
                        prod *= v
                if redondea(prod) != l.parcial:
                    anota(fila, AVISO, "Línea de medición",
                          f"Parcial que no es el producto de sus factores ('{l.comentario}')",
                          str(l.parcial), str(redondea(prod)))
            if fila.med_lineas:
                medicion.lineas = [
                    LineaMedicion(comentario=l.comentario, n_uds=_f(l.uds), longitud=_f(l.longitud),
                                  anchura=_f(l.anchura), altura=_f(l.altura))
                    for l in m.lineas]
                if _d(p.total_medicion(medicion)) == o.cantidad:
                    fila.med_lineas_en_bc3 = True
                else:
                    anota(fila, AVISO, "Líneas de medición",
                          "Las líneas no reproducen la cantidad: el BC3 lleva solo el total",
                          str(o.cantidad), str(_d(p.total_medicion(medicion))))
                    medicion.lineas = []
        concepto.mediciones[padre_bc3] = medicion
        p.get(padre_bc3).hijos.append(Hijo(o.codigo, 1.0, float(o.cantidad)))

    def suma_pdf(c: Capitulo) -> Decimal:
        t = Decimal(0)
        for h in c.hijos:
            t += suma_pdf(h) if isinstance(h, Capitulo) else (h.importe or Decimal(0))
        return t

    def procesa_capitulo(c: Capitulo, padre_bc3: str, ruta: str,
                         solo_control: bool = False, codigo_bc3: str = "") -> None:
        ruta_c = f"{ruta} / {c.codigo}" if ruta else c.codigo
        fila = FilaCapitulo(ruta_c, c.codigo, c.nivel, c.resumen, c.total_pdf, suma_pdf(c))
        control.capitulos.append(fila)
        if c.total_pdf is not None and fila.suma_pdf != c.total_pdf:
            av.append(Aviso(ERROR, "Total capítulo", c.codigo, ruta_c,
                            "La suma de las partidas no da el total del capítulo en el PDF",
                            str(c.total_pdf), str(fila.suma_pdf)))
        if solo_control:
            for h in c.hijos:
                if isinstance(h, Capitulo):
                    procesa_capitulo(h, _cod_cap(h.codigo), ruta_c, True)
                else:
                    procesa_partida(h, codigo_bc3 or padre_bc3, True)
            return
        codigo = _cod_cap(c.codigo)
        firma = _firma_capitulo(c)
        if codigo in vistos_cap:
            if vistos_cap[codigo] == firma:
                p.get(padre_bc3).hijos.append(Hijo(codigo, 1.0, 1.0))
                av.append(Aviso(INFO, "Capítulo repetido", c.codigo, ruta_c,
                                "Mismo código y mismo contenido que otro capítulo: en el BC3 es "
                                "un único capítulo que cuelga de los dos sitios (como en Presto)"))
                for h in c.hijos:
                    if isinstance(h, Capitulo):
                        procesa_capitulo(h, codigo, ruta_c, True, _cod_cap(h.codigo))
                    else:
                        procesa_partida(h, codigo, True)
                return
            n = 2
            while f"{c.codigo}-{n}#" in vistos_cap:
                n += 1
            nuevo = f"{c.codigo}-{n}#"
            av.append(Aviso(AVISO, "Capítulo repetido", c.codigo, ruta_c,
                            f"Mismo código que otro capítulo pero distinto contenido: se renombra a {nuevo}"))
            codigo = nuevo
        vistos_cap[codigo] = firma
        cap = Concepto(codigo=codigo, resumen=c.resumen, tipo=TipoConcepto.CAPITULO,
                       precio_es_dato=False)
        cap._fila_control = fila
        p.add_concepto(cap)
        p.get(padre_bc3).hijos.append(Hijo(codigo, 1.0, 1.0))
        for h in c.hijos:
            if isinstance(h, Capitulo):
                procesa_capitulo(h, codigo, ruta_c)
            else:
                procesa_partida(h, codigo)

    for h in datos.raiz.hijos:
        if isinstance(h, Capitulo):
            procesa_capitulo(h, codigo_obra, "")
        else:
            procesa_partida(h, codigo_obra)

    # Totales de la hoja RESUMEN frente al árbol
    caps1 = {f.codigo: f for f in control.capitulos if f.nivel == "CAPITULO"}
    for cod, nombre, imp in r.capitulos:
        f = caps1.get(cod)
        if f is None:
            av.append(Aviso(ERROR, "Resumen", cod, "Resumen de presupuesto",
                            "Capítulo del resumen que no está en el presupuesto"))
            continue
        f.resumen_pdf = imp
        if f.total_pdf != imp:
            av.append(Aviso(ERROR, "Resumen", cod, "Resumen de presupuesto",
                            "Importe del resumen distinto del total del capítulo",
                            str(f.total_pdf), str(imp)))
        if normaliza(nombre) != normaliza(f.resumen):
            av.append(Aviso(AVISO, "Resumen", cod, "Resumen de presupuesto",
                            "Nombre del capítulo distinto en el resumen", f.resumen, nombre))

    p.recalcular()
    _rellenar_bc3(p, control, releido=False)
    _avisos_globales(datos, control)
    return p, control


def _rellenar_bc3(p: Presupuesto, control: Control, releido: bool) -> None:
    """Importes calculados por BC3Manager (recalcular + importe_en_padre)."""
    atributo = "bc3_importe_releido" if releido else "bc3_importe"
    for f in control.filas:
        if f.padre_bc3 and p.get(f.codigo) is not None:
            setattr(f, atributo, _d(p.importe_en_padre(f.codigo, f.padre_bc3)))
    for f in control.capitulos:
        codigo = _cod_cap(f.codigo)
        if p.get(codigo) is not None:
            setattr(f, atributo, _d(p._importe_recursivo(codigo, "")))
    if releido:
        control.pem_bc3_releido = _d(p.presupuesto_total())
    else:
        control.pem_bc3 = _d(p.presupuesto_total())


def _avisos_globales(datos: DatosPDF, control: Control) -> None:
    g = control.globales
    r = datos.resumen
    suma = sum((f.importe or Decimal(0)) for f in control.filas)
    g.insert(0, ("PEM según el PDF (TOTAL PRESUPUESTO)", _eur(datos.pem_pdf), ""))
    g.insert(1, ("Suma de importes de partidas del PDF", _eur(suma),
                 "OK" if suma == datos.pem_pdf else "NO CUADRA"))
    g.insert(2, ("PEM en la hoja de resumen", _eur(r.pem),
                 "OK" if r.pem == datos.pem_pdf else "NO CUADRA"))
    g.insert(3, ("PEM calculado por BC3Manager", _eur(control.pem_bc3),
                 "OK" if control.pem_bc3 == datos.pem_pdf else "NO CUADRA"))
    g.append(("Gastos generales / Beneficio industrial",
              f"{_pct(r.gg_pct)} / {_pct(r.bi_pct)}", "Se guardan en el ~K (no afectan al PEM)"))
    g.append(("IVA", _pct(r.iva_pct), "Se guarda en el ~K"))
    g.append(("Partidas (apariciones)", str(len(control.filas)), ""))
    g.append(("Conceptos distintos", str(len({f.codigo for f in control.filas})), ""))
    g.append(("Partidas con líneas de medición en el BC3",
              str(sum(1 for f in control.filas if f.med_lineas_en_bc3)),
              "El resto lleva solo la cantidad total (partidas alzadas)"))
    if control.pem_bc3 is not None and datos.pem_pdf is not None and \
            control.pem_bc3 != datos.pem_pdf:
        control.avisos.append(Aviso(ERROR, "PEM", "", "",
                                    "El PEM recalculado por BC3Manager no coincide con el del PDF",
                                    str(datos.pem_pdf), str(control.pem_bc3)))
    for f in control.filas:
        if f.bc3_importe is not None and f.importe is not None and f.bc3_importe != f.importe:
            f.avisos.append("BC3Manager calcula otro importe")
            f.gravedad = ERROR
            control.avisos.append(Aviso(ERROR, "Importe BC3", f.codigo, f.ruta,
                                        "BC3Manager calcula un importe distinto del PDF",
                                        str(f.importe), str(f.bc3_importe)))


def _pct(v: Optional[Decimal]) -> str:
    return "—" if v is None else f"{v:.2f}".replace(".", ",") + " %"


def _eur(v: Optional[Decimal]) -> str:
    if v is None:
        return "—"
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return s + " €"


# =========================================================================
# Verificación de ida y vuelta: escribir el BC3, releerlo y recalcular
# =========================================================================

def verificar_bc3(ruta_bc3: str, control: Control) -> None:
    """Relee el BC3 escrito con el lector de BC3Manager y vuelve a calcular
    importes de partidas, capítulos y PEM. Cualquier diferencia con el PDF
    queda como ERROR en el control."""
    from bc3manager.io.lector import leer_bc3
    p2 = leer_bc3(ruta_bc3)
    p2.recalcular()
    _rellenar_bc3(p2, control, releido=True)
    control.globales.insert(4, (
        "PEM del BC3 escrito y vuelto a leer", _eur(control.pem_bc3_releido),
        "OK" if control.pem_bc3_releido == control.pem_pdf else "NO CUADRA"))
    for f in control.filas:
        if f.bc3_importe_releido is not None and f.bc3_importe_releido != f.importe:
            f.gravedad = ERROR
            f.avisos.append("El BC3 releído da otro importe")
            control.avisos.append(Aviso(ERROR, "BC3 releído", f.codigo, f.ruta,
                                        "Al releer el BC3 el importe cambia",
                                        str(f.importe), str(f.bc3_importe_releido)))
    for f in control.capitulos:
        if f.bc3_importe_releido is not None and f.total_pdf is not None and \
                f.bc3_importe_releido != f.total_pdf:
            control.avisos.append(Aviso(ERROR, "BC3 releído", f.codigo, f.ruta,
                                        "Al releer el BC3 el total del capítulo cambia",
                                        str(f.total_pdf), str(f.bc3_importe_releido)))


# =========================================================================
# Informe de control en Excel
# =========================================================================

_NOMBRE_NIVEL = {"CAPITULO": "Capítulo", "SUBCAPITULO": "Subcapítulo", "APARTADO": "Apartado",
                 "SUBAPARTADO": "Subapartado", "ELEMENTO": "Elemento",
                 "SUBELEMENTO": "Subelemento"}


def escribir_control_xlsx(control: Control, ruta: str) -> None:
    """Excel de control: Resumen, Partidas, Capítulos y Avisos."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError as e:   # pragma: no cover
        raise ImportError("Para el informe de control hace falta openpyxl: "
                          "pip install openpyxl") from e

    wb = Workbook()
    negrita = Font(bold=True)
    cab_fill = PatternFill("solid", fgColor="DDE3EA")
    rojo = PatternFill("solid", fgColor="F8D0D0")
    amarillo = PatternFill("solid", fgColor="FFF1C2")
    verde = PatternFill("solid", fgColor="D6EFD8")
    fmt_eur = '#,##0.00 "€"'
    fmt_num = '#,##0.00'

    def cabecera(ws, titulos: list[str], anchos: list[int]) -> None:
        ws.append(titulos)
        for i, (t, a) in enumerate(zip(titulos, anchos), start=1):
            c = ws.cell(row=ws.max_row, column=i)
            c.font, c.fill = negrita, cab_fill
            c.alignment = Alignment(wrap_text=True, vertical="top")
            ws.column_dimensions[get_column_letter(i)].width = a
        ws.freeze_panes = f"A{ws.max_row + 1}"   # (ws.cell crearía una fila vacía)

    def num(v: Optional[Decimal]):
        return float(v) if v is not None else None

    # --- Resumen ---
    ws = wb.active
    ws.title = "Resumen"
    ws.append(["Control de importación PDF → BC3"])
    ws["A1"].font = Font(bold=True, size=14)
    ws.append([control.titulo_obra])
    ws.append([f"PDF: {control.ruta_pdf}"])
    ws.append([f"Modo de costes indirectos en el BC3: {control.modo_ci}"
               + (" (precio con CI, CI = 0 en el ~K)" if control.modo_ci == "incluido"
                  else " (coste directo + CI en el ~K)")])
    ws.append([])
    cabecera(ws, ["Comprobación", "Valor", "Resultado / comentario"], [48, 22, 110])
    ws.freeze_panes = None
    for concepto, valor, coment in control.globales:
        ws.append([concepto, valor, coment])
        c = ws.cell(row=ws.max_row, column=3)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        if coment == "OK":
            c.fill = verde
        elif coment.startswith("NO CUADRA"):
            c.fill = rojo
    ws.append([])
    ws.append(["Avisos", "Nº", "Qué significa"])
    for c in ws[ws.max_row]:
        c.font, c.fill = negrita, cab_fill
    ws.append([ERROR, control.cuenta(ERROR),
               "Afecta a importes o no se puede representar en BC3. Hay que resolverlo."])
    ws.append([AVISO, control.cuenta(AVISO),
               "Texto, resumen o unidad distintos entre secciones del PDF. El BC3 usa el del PRESUPUESTO."])
    ws.append([INFO, control.cuenta(INFO), "Decisión del importador, para conocimiento."])

    # --- Partidas ---
    ws = wb.create_sheet("Partidas")
    titulos = ["Capítulo (ruta)", "Código", "Ud", "Resumen", "Pág.",
               "Cantidad", "Precio", "Importe PDF", "Cant × Precio",
               "Cantidad en mediciones", "Nº líneas medición", "Líneas en BC3",
               "Precio cuadro nº1", "Precio en letra", "Coste directo (nº2)", "CI %",
               "CD × (1+CI)", "Importe BC3Manager", "Importe BC3 releído",
               "Estado", "Avisos"]
    anchos = [26, 14, 6, 46, 6, 12, 11, 14, 14, 12, 9, 8, 11, 11, 12, 7, 12, 14, 14, 9, 70]
    cabecera(ws, titulos, anchos)
    for f in control.filas:
        ws.append([f.ruta, f.codigo, f.unidad, f.resumen, f.pagina,
                   num(f.cantidad), num(f.precio), num(f.importe), num(f.importe_calc),
                   num(f.med_total), f.med_lineas, "sí" if f.med_lineas_en_bc3 else "no",
                   num(f.c1_precio), num(f.c1_precio_letra), num(f.c2_cd), num(f.c2_ci_pct),
                   num(f.cd_mas_ci), num(f.bc3_importe), num(f.bc3_importe_releido),
                   f.gravedad or "OK", " · ".join(dict.fromkeys(f.avisos))])
        fila = ws.max_row
        for col in (6, 10):
            ws.cell(row=fila, column=col).number_format = fmt_num
        for col in (7, 8, 9, 13, 14, 15, 17, 18, 19):
            ws.cell(row=fila, column=col).number_format = fmt_eur
        relleno = rojo if f.gravedad == ERROR else amarillo if f.gravedad == AVISO else None
        if relleno:
            for col in (2, 20):
                ws.cell(row=fila, column=col).fill = relleno
    ws.auto_filter.ref = ws.dimensions

    # --- Capítulos ---
    ws = wb.create_sheet("Capítulos")
    cabecera(ws, ["Ruta", "Código", "Nivel", "Resumen", "Total en el PDF",
                  "Suma de sus partidas", "Hoja resumen", "Importe BC3Manager",
                  "Importe BC3 releído", "Estado"],
             [34, 14, 13, 46, 16, 16, 16, 16, 16, 10])
    for f in control.capitulos:
        valores = [v for v in (f.suma_pdf, f.resumen_pdf, f.bc3_importe, f.bc3_importe_releido)
                   if v is not None]
        ok = f.total_pdf is not None and all(v == f.total_pdf for v in valores)
        ws.append([f.ruta, f.codigo, _NOMBRE_NIVEL.get(f.nivel, f.nivel.capitalize()),
                   f.resumen, num(f.total_pdf),
                   num(f.suma_pdf), num(f.resumen_pdf), num(f.bc3_importe),
                   num(f.bc3_importe_releido), "OK" if ok else "REVISAR"])
        fila = ws.max_row
        for col in range(5, 10):
            ws.cell(row=fila, column=col).number_format = fmt_eur
        ws.cell(row=fila, column=10).fill = verde if ok else rojo
    ws.auto_filter.ref = ws.dimensions

    # --- Avisos ---
    ws = wb.create_sheet("Avisos")
    cabecera(ws, ["Gravedad", "Tipo", "Código", "Dónde", "Detalle",
                  "Valor en PRESUPUESTO", "Valor en la otra sección"],
             [9, 20, 14, 34, 50, 70, 70])
    orden = {ERROR: 0, AVISO: 1, INFO: 2}
    for a in sorted(control.avisos, key=lambda a: orden.get(a.gravedad, 9)):
        ws.append([a.gravedad, a.tipo, a.codigo, a.ubicacion, a.detalle,
                   a.valor_presupuesto, a.valor_otro])
        fila = ws.max_row
        ws.cell(row=fila, column=1).fill = rojo if a.gravedad == ERROR else \
            amarillo if a.gravedad == AVISO else verde
        for col in (5, 6, 7):
            ws.cell(row=fila, column=col).alignment = Alignment(wrap_text=True, vertical="top")
    ws.auto_filter.ref = ws.dimensions
    wb.save(ruta)


# =========================================================================
# Orquestador
# =========================================================================

def importar_pdf(ruta_pdf: str, ruta_bc3: Optional[str] = None,
                 ruta_control: Optional[str] = None, modo_ci: str = "incluido",
                 codigo_obra: str = "OBRA##") -> Control:
    """PDF de Presto -> (BC3 + Excel de control). Si no se da ruta_bc3 el BC3
    se escribe en un temporal solo para la verificación de ida y vuelta."""
    import os
    import tempfile
    from bc3manager.io.escritor import escribir_bc3

    datos = leer_pdf_presto(ruta_pdf)
    p, control = construir_presupuesto(datos, modo_ci=modo_ci, codigo_obra=codigo_obra)
    control.ruta_pdf = os.path.basename(ruta_pdf)
    if ruta_bc3:
        escribir_bc3(p, ruta_bc3)
        verificar_bc3(ruta_bc3, control)
    else:
        fd, tmp = tempfile.mkstemp(suffix=".bc3")
        os.close(fd)
        try:
            escribir_bc3(p, tmp)
            verificar_bc3(tmp, control)
        finally:
            os.remove(tmp)
    if ruta_control:
        escribir_control_xlsx(control, ruta_control)
    return control
