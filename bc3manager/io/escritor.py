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


class EscritorBC3:
    """Genera el texto BC3 a partir de un Presupuesto."""

    def __init__(self, presupuesto: Presupuesto) -> None:
        self.p = presupuesto

    def generar_texto(self) -> str:
        lineas: list[str] = []
        lineas.append(self._reg_V())
        lineas.append(self._reg_K())   # coeficientes y redondeos
        # Conceptos
        for concepto in self.p.conceptos.values():
            lineas.append(self._reg_C(concepto))
        # Descomposiciones
        for concepto in self.p.conceptos.values():
            if concepto.hijos:
                lineas.append(self._reg_D(concepto))
        # Textos
        for concepto in self.p.conceptos.values():
            if concepto.texto:
                lineas.append(self._reg_T(concepto))
        # Mediciones
        for concepto in self.p.conceptos.values():
            for codigo_padre, medicion in concepto.mediciones.items():
                if medicion.lineas:
                    lineas.append(self._reg_M(concepto, codigo_padre, medicion))
        return "\r\n".join(lineas) + "\r\n"

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
        return f"~C|{c.codigo}|{c.unidad}|{_escape(c.resumen)}|{_fmt(c.precio, 6)}||{tipo}|"

    def _reg_D(self, c: Concepto) -> str:
        trozos: list[str] = []
        for h in c.hijos:
            trozos.append(f"{h.codigo_hijo}\\{_fmt(h.factor, 4)}\\{_fmt(h.rendimiento, 4)}\\")
        return f"~D|{c.codigo}|{''.join(trozos)}|"

    def _reg_T(self, c: Concepto) -> str:
        return f"~T|{c.codigo}|{_escape(c.texto)}|"

    def _reg_M(self, c: Concepto, codigo_padre: str, medicion) -> str:
        padre = "" if codigo_padre == "__sin_padre__" else codigo_padre
        relacion = f"{padre}\\{c.codigo}" if padre else c.codigo
        subcampos: list[str] = []
        for ln in medicion.lineas:
            subcampos.append(
                f"{ln.tipo}\\{_escape(ln.comentario)}\\"
                f"{_fmt(ln.n_uds, 3)}\\{_fmt(ln.longitud, 3)}\\"
                f"{_fmt(ln.anchura, 3)}\\{_fmt(ln.altura, 3)}\\"
            )
        total = _fmt(medicion.total, 3)
        return f"~M|{relacion}||{total}|{''.join(subcampos)}|"


def _escape(texto: str) -> str:
    """Evita que caracteres de control del formato rompan el registro."""
    if not texto:
        return ""
    return texto.replace("|", " ").replace("\\", " ").replace("\r", " ").replace("\n", " ")


def escribir_bc3(presupuesto: Presupuesto, ruta: str) -> None:
    """Función de conveniencia para exportar un Presupuesto a .bc3."""
    EscritorBC3(presupuesto).escribir(ruta)
