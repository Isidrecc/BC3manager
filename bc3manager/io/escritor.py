"""
Escritor de archivos BC3 (FIEBDC-3).

Exporta un objeto Presupuesto a un archivo .bc3 válido, generando los registros
~V, ~C, ~D, ~T y ~M. El objetivo es que el archivo resultante pueda reabrirse
en Presto, Arquímedes, Menfis u otro software del sector sin pérdida de la
información fundamental.

Nota de codificación: se escribe en cp1252 (ANSI) por compatibilidad amplia.
Los caracteres no representables se sustituyen para no romper el archivo.
"""

from __future__ import annotations

from bc3manager.core.model import Concepto, Presupuesto, TipoConcepto


def _fmt(valor: float, decimales: int = 2) -> str:
    """Formatea un número para BC3 (punto decimal, sin separador de miles)."""
    if valor == int(valor):
        return str(int(valor))
    return f"{valor:.{decimales}f}".rstrip("0").rstrip(".")


def _fmt_m(valor: float) -> str:
    """Formatea un factor de una línea de medición (~M).

    En el modelo un factor 0 significa "neutro" (no anula el producto), igual
    que una celda vacía en Presto/Arquímedes. Por eso 0 se escribe como vacío:
    así la línea conserva su estructura original (p.ej. una línea de subtítulo
    sin dimensiones) y no se introducen ceros espurios que otros programas
    podrían interpretar literalmente.
    """
    if not valor:
        return ""
    return _fmt(valor, 3)


class EscritorBC3:
    """Genera el texto BC3 a partir de un Presupuesto."""

    def __init__(self, presupuesto: Presupuesto) -> None:
        self.p = presupuesto

    def generar_texto(self) -> str:
        lineas: list[str] = []
        lineas.append(self._reg_V())
        lineas.append(self._reg_K())   # coeficientes y redondeos

        # --- Conceptos (~C) con su descomposición (~D) PEGADA a continuación ---
        # Presto 8.8 fija la naturaleza del concepto al leer su ~C: si no
        # encuentra la descomposición inmediatamente después, lo toma por un
        # recurso hoja y lo reclasifica (p.ej. una partida de movimiento de
        # tierras pasa a "maquinaria"). Además emite primero los capítulos en
        # orden de árbol (DFS) y después el resto, como hace Presto al exportar.
        emitidos: set[str] = set()
        raiz = self.p.codigo_raiz

        def emitir(concepto: Concepto) -> None:
            lineas.append(self._reg_C(concepto))
            if concepto.hijos:
                lineas.append(self._reg_D(concepto))
            emitidos.add(concepto.codigo)

        # 1) Capítulos en orden de árbol (DFS preorden desde la raíz)
        for codigo in self._orden_capitulos():
            c = self.p.get(codigo)
            if c is not None and c.codigo not in emitidos:
                emitir(c)
        # 2) Resto de conceptos (partidas y unitarios), salvo la raíz
        for concepto in self.p.conceptos.values():
            if concepto.codigo in emitidos or concepto.codigo == raiz:
                continue
            emitir(concepto)
        # 3) La obra raíz, al final (como en los BC3 de Presto)
        if raiz:
            c = self.p.get(raiz)
            if c is not None and c.codigo not in emitidos:
                emitir(c)

        # --- Textos (~T) en bloque ---
        for concepto in self.p.conceptos.values():
            if concepto.texto:
                lineas.append(self._reg_T(concepto))

        # --- Mediciones (~M) agrupadas por capítulo padre y con POSICIÓN ---
        posiciones = self._calcular_posiciones()
        for codigo_padre, concepto, medicion, posicion in self._mediciones_ordenadas(posiciones):
            lineas.append(self._reg_M(concepto, codigo_padre, medicion, posicion))

        return "\r\n".join(lineas) + "\r\n"

    def _orden_capitulos(self) -> list[str]:
        """Códigos de los capítulos en orden de árbol (DFS preorden desde la
        raíz), igual que los exporta Presto: 01#, 02#, 02.01#, 02.02#, 03#..."""
        orden: list[str] = []
        visit: set[str] = set()

        def dfs(codigo: str) -> None:
            if codigo in visit:
                return
            visit.add(codigo)
            c = self.p.get(codigo)
            if c is None:
                return
            for h in c.hijos:
                hc = self.p.get(h.codigo_hijo)
                if hc is not None and hc.tipo == TipoConcepto.CAPITULO:
                    orden.append(h.codigo_hijo)
                    dfs(h.codigo_hijo)

        if self.p.codigo_raiz:
            dfs(self.p.codigo_raiz)
        else:
            # Sin raíz detectada: capítulos en orden de inserción.
            orden = [c.codigo for c in self.p.conceptos.values()
                     if c.tipo == TipoConcepto.CAPITULO]
        return orden

    def _calcular_posiciones(self) -> dict[str, list[int]]:
        """Camino de índices 1-based desde la raíz hasta cada concepto
        (p.ej. 02.01# -> [2, 1]). Sirve para el campo POSICIÓN de los ~M."""
        paths: dict[str, list[int]] = {}
        raiz = self.p.codigo_raiz
        if not raiz:
            return paths
        cola: list[tuple[str, list[int]]] = [(raiz, [])]
        visitados: set[str] = set()
        while cola:
            codigo, prefijo = cola.pop(0)
            if codigo in visitados:
                continue
            visitados.add(codigo)
            c = self.p.get(codigo)
            if c is None:
                continue
            for idx, h in enumerate(c.hijos, start=1):
                if h.codigo_hijo not in paths:
                    paths[h.codigo_hijo] = prefijo + [idx]
                cola.append((h.codigo_hijo, prefijo + [idx]))
        return paths

    def _mediciones_ordenadas(self, posiciones: dict[str, list[int]]):
        """Devuelve las mediciones como (codigo_padre, concepto, medicion,
        posicion_str) ordenadas por el camino del capítulo padre y, dentro de
        él, por el índice del hijo — el mismo orden que exporta Presto."""
        items = []
        for concepto in self.p.conceptos.values():
            for codigo_padre, medicion in concepto.mediciones.items():
                if not medicion.lineas:
                    continue
                ppath = posiciones.get(codigo_padre)
                padre_c = self.p.get(codigo_padre)
                cidx = None
                if padre_c is not None:
                    for i, h in enumerate(padre_c.hijos, start=1):
                        if h.codigo_hijo == concepto.codigo:
                            cidx = i
                            break
                if ppath is not None and cidx is not None:
                    clave = ppath + [cidx]
                    # Presto cierra el campo POSICIÓN con un '\' final (p.ej. "1\2\").
                    posicion = "\\".join(str(x) for x in clave) + "\\"
                else:
                    clave = [9999]          # mediciones sueltas, al final
                    posicion = ""
                items.append((clave, codigo_padre, concepto, medicion, posicion))
        items.sort(key=lambda it: it[0])
        for _clave, codigo_padre, concepto, medicion, posicion in items:
            yield codigo_padre, concepto, medicion, posicion

    def escribir(self, ruta: str) -> None:
        texto = self.generar_texto()
        with open(ruta, "w", encoding="cp1252", errors="replace", newline="") as f:
            f.write(texto)

    # ---- Generadores de registro ----------------------------------------

    def _reg_V(self) -> str:
        version = self.p.version_formato or "FIEBDC-3/2024"
        programa = "BC3Manager"
        return f"~V||{version}|{programa}||ANSI||{self.p.tipo_datos or '1'}||"

    def _reg_K(self) -> str:
        """Escribe el registro ~K con los decimales de redondeo y la moneda.

        Orden FIEBDC del campo DECIMALES (verificado empíricamente):
          DecDet \\ DecCantMed \\ DecCantRend \\ DecImp \\ DecNat \\ DecPar \\ Dec \\ MONEDA \\

        Así, al reabrir el archivo (en BC3Manager o en otro programa) se
        recupera exactamente la misma configuración de redondeo, y los precios
        se recalculan igual que en el programa de origen.
        """
        p = self.p
        decimales = (
            f"\\{p.dec_parcial}\\{p.dec_cantmed}\\{p.dec_cantrend}\\"
            f"{p.dec_subtotal}\\{p.dec_natural}\\{p.dec_precio_partida}\\"
            f"{p.dec_precio_capitulo}\\{p.moneda or 'EUR'}\\"
        )
        return f"~K|{decimales}|0|"

    def _reg_C(self, c: Concepto) -> str:
        # Precio con 6 decimales (suficiente para DecPar/DecNat hasta 6) y sin
        # ceros sobrantes — no truncar precios como 11.00965 (DecPar=5).
        # 6º campo: tipo FIEBDC (_tipo_fiebdc) para que otros programas
        # clasifiquen igual los conceptos (MO/MQ/MT/capítulo/partida).
        tipo = getattr(c, "_tipo_fiebdc", "") or ""
        fecha = getattr(c, "_fecha_bc3", "") or ""
        return f"~C|{c.codigo}|{c.unidad}|{_escape(c.resumen)}|{_fmt(c.precio, 6)}|{fecha}|{tipo}|"

    def _reg_D(self, c: Concepto) -> str:
        trozos: list[str] = []
        for h in c.hijos:
            trozos.append(f"{h.codigo_hijo}\\{_fmt(h.factor, 4)}\\{_fmt(h.rendimiento, 4)}\\")
        return f"~D|{c.codigo}|{''.join(trozos)}|"

    def _reg_T(self, c: Concepto) -> str:
        return f"~T|{c.codigo}|{_escape(c.texto)}|"

    def _reg_M(self, c: Concepto, codigo_padre: str, medicion, posicion: str = "") -> str:
        padre = "" if codigo_padre == "__sin_padre__" else codigo_padre
        relacion = f"{padre}\\{c.codigo}" if padre else c.codigo
        subcampos: list[str] = []
        for ln in medicion.lineas:
            tipo = str(ln.tipo) if ln.tipo else ""   # 0 = normal -> vacío
            subcampos.append(
                f"{tipo}\\{_escape(ln.comentario)}\\"
                f"{_fmt_m(ln.n_uds)}\\{_fmt_m(ln.longitud)}\\"
                f"{_fmt_m(ln.anchura)}\\{_fmt_m(ln.altura)}\\"
            )
        total = _fmt(medicion.total, 3)
        return f"~M|{relacion}|{posicion}|{total}|{''.join(subcampos)}|"


def _escape(texto: str) -> str:
    """Evita que caracteres de control del formato rompan el registro."""
    if not texto:
        return ""
    return texto.replace("|", " ").replace("\\", " ").replace("\r", " ").replace("\n", " ")


def escribir_bc3(presupuesto: Presupuesto, ruta: str) -> None:
    """Función de conveniencia para exportar un Presupuesto a .bc3."""
    EscritorBC3(presupuesto).escribir(ruta)
