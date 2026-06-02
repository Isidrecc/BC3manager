"""
Lector de archivos BC3 (FIEBDC-3).

Implementa la lectura de los registros fundamentales del formato. La referencia
práctica más útil para interpretar cada campo es el proyecto open source
pyArq-Presupuestos (https://pyarq.obraencurso.es/fiebdc), que documenta su
lectura registro a registro; la especificación oficial está en
https://www.fiebdc.es

Registros soportados en esta primera versión:
  ~V  Propiedad y versión (cabecera del archivo)
  ~K  Coeficientes (decimales, CI, GG, BI...)  -> se lee, no se aplica aún
  ~C  Concepto (código, unidad, resumen, precio, fecha)
  ~D  Descomposición (relación padre -> hijos con factor y rendimiento)
  ~T  Texto (descripción larga / pliego de un concepto)
  ~M  Medición (líneas de medición de una partida en un destino)

Estructura sintáctica del formato:
  - Cada registro empieza por '~' + letra y ocupa una "línea lógica".
    Una línea lógica puede abarcar varias líneas físicas; un registro nuevo
    solo empieza cuando aparece '~' al principio de una línea física.
  - Campos separados por '|'
  - Subcampos separados por '\'

Codificación: el formato usa ANSI (cp1252) o ASCII MS-DOS (cp850). Se intenta
detectar a partir del registro ~V; si no, se prueban ambas.
"""

from __future__ import annotations

import re

from bc3manager.core.model import (
    Concepto,
    Hijo,
    LineaMedicion,
    Medicion,
    Presupuesto,
)


def _to_float(valor: str) -> float:
    """Convierte un campo BC3 a float. Admite coma o punto decimal; vacío -> 0."""
    if not valor:
        return 0.0
    valor = valor.strip().replace(",", ".")
    try:
        return float(valor)
    except ValueError:
        return 0.0


def _leer_bytes(ruta: str) -> bytes:
    with open(ruta, "rb") as f:
        return f.read()


def _detectar_codificacion(datos: bytes) -> str:
    """
    Detecta la codificación a partir del campo JUEGO_CARACTERES del registro ~V.
    Devuelve un nombre de códec de Python. Por defecto cp1252 (ANSI).
    """
    cabecera = datos[:400].decode("latin-1", errors="replace").upper()
    if "ASCII" in cabecera or "850" in cabecera or "DOS" in cabecera:
        return "cp850"
    return "cp1252"


def _separar_registros(texto: str) -> list[str]:
    """
    Divide el texto en registros lógicos. Un registro empieza por '~' al
    principio de una línea física. Las continuaciones (líneas que no empiezan
    por '~') se unen al registro en curso.
    """
    registros: list[str] = []
    actual: list[str] = []
    for linea in texto.splitlines():
        if linea.startswith("~"):
            if actual:
                registros.append("".join(actual))
            actual = [linea]
        else:
            # Continuación del registro anterior
            if actual:
                actual.append(linea)
    if actual:
        registros.append("".join(actual))
    return registros


class LectorBC3:
    """Parsea un archivo .bc3 y devuelve un objeto Presupuesto."""

    def __init__(self) -> None:
        self.presupuesto = Presupuesto()

    def leer(self, ruta: str) -> Presupuesto:
        datos = _leer_bytes(ruta)
        codec = _detectar_codificacion(datos)
        try:
            texto = datos.decode(codec, errors="replace")
        except LookupError:
            texto = datos.decode("cp1252", errors="replace")
        self.presupuesto.codificacion = codec

        registros = _separar_registros(texto)
        for registro in registros:
            self._procesar_registro(registro)

        self._resolver_alias_hash()
        self.presupuesto.clasificar_tipos()
        self._detectar_raiz()
        self.presupuesto.recalcular()
        return self.presupuesto

    # ---- Despacho por tipo de registro ----------------------------------

    def _procesar_registro(self, registro: str) -> None:
        if len(registro) < 2 or registro[0] != "~":
            return
        tipo = registro[1].upper()
        # El cuerpo es lo que sigue a "~X"; los campos van separados por '|'
        cuerpo = registro[2:]
        campos = cuerpo.split("|")
        # campos[0] suele estar vacío porque el cuerpo empieza por '|'
        handler = {
            "V": self._reg_V,
            "K": self._reg_K,
            "C": self._reg_C,
            "D": self._reg_D,
            "T": self._reg_T,
            "M": self._reg_M,
        }.get(tipo)
        if handler:
            handler(campos)

    # ---- ~V Propiedad y versión -----------------------------------------

    def _reg_V(self, campos: list[str]) -> None:
        # ~V | propiedad | VERSION\FECHA | programa | cabecera_alt | codif | coment | tipo | ...
        def get(i: int) -> str:
            return campos[i].strip() if i < len(campos) else ""
        version = get(2)
        if "\\" in version:
            version = version.split("\\")[0]
        self.presupuesto.version_formato = version
        self.presupuesto.programa_emisor = get(3)
        self.presupuesto.tipo_datos = get(7)

    # ---- ~K Coeficientes y redondeos ------------------------------------

    def _reg_K(self, campos: list[str]) -> None:
        # ~K | DECIMALES\...\MONEDA\ | CI\GG... | ... |
        #
        # El campo DECIMALES (índice 1) contiene los decimales de redondeo que
        # aplica el programa origen (Presto): cantidades, precios de partidas,
        # subtotales de descomposición, importes, etc. Diálogo de Presto:
        #   DecCantCap, DecCantMed, DecCantRend, Dec, DecPar, DecNat, DecImp, DecDet, DecFac
        #
        # La presencia de ~K indica que el archivo viene de un programa que
        # redondea a 2 decimales en cada paso (subtotales e importes). Activamos
        # ese modo para que nuestros precios coincidan con los del archivo.
        #
        # Los decimales de precios/subtotales/importes son 2 en prácticamente
        # todas las configuraciones del sector (y así están en el diálogo de
        # Presto). El único que suele diferir es el de cantidades/rendimientos
        # (3), que no re-redondeamos porque ya vienen almacenados en el ~D.
        self.presupuesto.redondeo_activo = True
        # Parsear el campo DECIMALES (índice 1). Orden FIEBDC verificado
        # empíricamente con un archivo de prueba que usa un valor distinto por
        # parámetro (Test_REDONDEO):
        #   pos1 DecDet | pos2 DecCantMed | pos3 DecCantRend | pos4 DecImp |
        #   pos5 DecNat | pos6 DecPar | pos7 Dec
        # (DecCantCap y DecFac no se emiten en este campo.)
        campo_dec = campos[1] if len(campos) > 1 else ""
        partes = campo_dec.split("\\")
        # partes[0] suele ser '' (antes del primer '\'); los valores numéricos
        # están en partes[1..7]; el resto (p.ej. 'EUR') se ignora.
        def _dec(i: int, defecto: int) -> int:
            try:
                v = partes[i].strip()
                return int(v) if v.isdigit() else defecto
            except (IndexError, ValueError):
                return defecto
        p = self.presupuesto
        p.dec_parcial         = _dec(1, p.dec_parcial)          # DecDet
        p.dec_cantmed         = _dec(2, p.dec_cantmed)          # DecCantMed
        p.dec_cantrend        = _dec(3, p.dec_cantrend)         # DecCantRend
        p.dec_subtotal        = _dec(4, p.dec_subtotal)         # DecImp
        p.dec_natural         = _dec(5, p.dec_natural)          # DecNat
        p.dec_precio_partida  = _dec(6, p.dec_precio_partida)   # DecPar
        p.dec_precio_capitulo = _dec(7, p.dec_precio_capitulo)  # Dec
        # El importe (precio × medición) usa, por convención de Presto, el mismo
        # nº de decimales que el precio de capítulo (Dec) para el rollup.
        p.dec_importe = p.dec_precio_capitulo
        # Moneda: primer subcampo no numérico del campo DECIMALES (p.ej. 'EUR').
        for tok in partes:
            t = tok.strip()
            if t and not t.isdigit():
                p.moneda = t
                break
        return

    # ---- ~C Concepto ----------------------------------------------------

    def _reg_C(self, campos: list[str]) -> None:
        # ~C | CODIGO | UNIDAD | RESUMEN | PRECIO\PRECIO2... | FECHA | TIPO |
        #
        # El campo TIPO (índice 6) en FIEBDC-3 indica la naturaleza del concepto:
        #   0 = sin clasificar  1 = mano de obra  2 = maquinaria  3 = material
        #   4 = resto costes    5 = subcapítulo   6 = partida alzada
        # Presto 8.8 emite siempre este campo; lo usamos para clasificar mejor.
        def get(i: int) -> str:
            return campos[i].strip() if i < len(campos) else ""
        codigos = get(1)
        codigo = codigos.split("\\")[0].strip()
        if not codigo:
            return
        unidad = get(2)
        resumen = get(3)
        precio_campo = get(4)
        primer_precio = precio_campo.split("\\")[0] if precio_campo else ""
        precio = _to_float(primer_precio)
        fecha = get(5)         # campo FECHA (se conserva para round-trip fiel)
        tipo_fiebdc = get(6)   # campo extra de Presto y otros programas

        concepto = self.presupuesto.get(codigo)
        if concepto is None:
            concepto = Concepto(codigo=codigo)
            self.presupuesto.add_concepto(concepto)
        concepto.unidad = unidad or concepto.unidad
        concepto.resumen = resumen or concepto.resumen
        if precio:
            concepto.precio = precio
            concepto.precio_es_dato = True
            # _precio_bc3: precio original leído del archivo, inmune al recálculo
            concepto._precio_bc3 = precio
        if fecha:
            concepto._fecha_bc3 = fecha
        if tipo_fiebdc:
            concepto._tipo_fiebdc = tipo_fiebdc

    # ---- ~D Descomposición ----------------------------------------------

    def _reg_D(self, campos: list[str]) -> None:
        # ~D | CODIGO_PADRE | CODIGO_HIJO\FACTOR\RENDIMIENTO \ CODIGO_HIJO\FACTOR\REND ... |
        def get(i: int) -> str:
            return campos[i] if i < len(campos) else ""
        codigo_padre = get(1).strip()
        if not codigo_padre:
            return
        padre = self.presupuesto.get(codigo_padre)
        if padre is None:
            padre = Concepto(codigo=codigo_padre)
            self.presupuesto.add_concepto(padre)

        cuerpo_hijos = get(2)
        # Los hijos vienen en tripletes codigo\factor\rendimiento separados por '\'
        partes = cuerpo_hijos.split("\\")
        # Recorremos en grupos de 3
        i = 0
        while i < len(partes):
            codigo_hijo = partes[i].strip() if i < len(partes) else ""
            # Leer los valores CRUDOS: hay que distinguir "vacío" (→ por defecto 1)
            # de "0" explícito (→ 0). Un rendimiento 0 significa medición/cantidad 0
            # en ese padre (p.ej. una partida que no se mide en ese capítulo) y debe
            # conservarse; convertirlo a 1 inflaba mediciones e importes al exportar.
            factor_raw = partes[i + 1].strip() if i + 1 < len(partes) else ""
            rend_raw   = partes[i + 2].strip() if i + 2 < len(partes) else ""
            factor = _to_float(factor_raw) if factor_raw != "" else 1.0
            rend   = _to_float(rend_raw)   if rend_raw   != "" else 1.0
            if codigo_hijo:
                # Presto 8.8 omite el # en los codigos de capitulo dentro de ~D.
                # Resolvemos: si no existe sin # pero existe con #, usamos con #.
                if self.presupuesto.get(codigo_hijo) is None and                    self.presupuesto.get(codigo_hijo + '#') is not None:
                    codigo_hijo = codigo_hijo + '#'
                padre.hijos.append(
                    Hijo(
                        codigo_hijo=codigo_hijo,
                        factor=factor,
                        rendimiento=rend,
                    )
                )
                if self.presupuesto.get(codigo_hijo) is None:
                    self.presupuesto.add_concepto(Concepto(codigo=codigo_hijo))
            i += 3

    # ---- ~T Texto -------------------------------------------------------

    def _reg_T(self, campos: list[str]) -> None:
        # ~T | CODIGO | TEXTO |
        def get(i: int) -> str:
            return campos[i] if i < len(campos) else ""
        codigo = get(1).strip()
        texto = get(2)
        if not codigo:
            return
        concepto = self.presupuesto.get(codigo)
        if concepto is None:
            concepto = Concepto(codigo=codigo)
            self.presupuesto.add_concepto(concepto)
        concepto.texto = texto.strip()

    # ---- ~M Medición ----------------------------------------------------

    def _reg_M(self, campos: list[str]) -> None:
        # ~M | CODIGO_PADRE\CODIGO_HIJO | POSICION | MEDICION_TOTAL |
        #      COMENTARIO\TIPO\COMENTARIO\N\LONG\ANCHO\ALTO \ ... |
        def get(i: int) -> str:
            return campos[i] if i < len(campos) else ""
        relacion = get(1)
        codigo_padre = ""
        codigo_hijo = ""
        if "\\" in relacion:
            trozos = relacion.split("\\")
            codigo_padre = trozos[0].strip()
            codigo_hijo = trozos[1].strip() if len(trozos) > 1 else ""
        else:
            codigo_hijo = relacion.strip()
        if not codigo_hijo:
            return

        concepto = self.presupuesto.get(codigo_hijo)
        if concepto is None:
            concepto = Concepto(codigo=codigo_hijo)
            self.presupuesto.add_concepto(concepto)

        medicion = Medicion()
        # Campo 3: medición total declarada en el archivo (opcional, redundante con
        # la suma de líneas). Útil para detectar archivos inconsistentes.
        total_decl = get(3).strip()
        if total_decl:
            try:
                medicion.total_declarado = _to_float(total_decl)
            except (ValueError, TypeError):
                pass
        lineas_campo = get(4)
        # Las líneas vienen como subcampos separados por '\', en grupos de 6:
        # TIPO \ COMENTARIO \ N \ LONGITUD \ ANCHURA \ ALTURA
        partes = lineas_campo.split("\\")
        i = 0
        while i + 5 < len(partes) + 1 and i < len(partes):
            tipo = partes[i] if i < len(partes) else ""
            comentario = partes[i + 1] if i + 1 < len(partes) else ""
            n = partes[i + 2] if i + 2 < len(partes) else ""
            longitud = partes[i + 3] if i + 3 < len(partes) else ""
            anchura = partes[i + 4] if i + 4 < len(partes) else ""
            altura = partes[i + 5] if i + 5 < len(partes) else ""
            # Solo añadimos si hay algún dato numérico
            if any(_to_float(x) != 0 for x in (n, longitud, anchura, altura)) or comentario.strip():
                try:
                    tipo_int = int(tipo) if tipo.strip().lstrip("-").isdigit() else 0
                except ValueError:
                    tipo_int = 0
                medicion.lineas.append(
                    LineaMedicion(
                        comentario=comentario.strip(),
                        n_uds=_to_float(n),
                        longitud=_to_float(longitud),
                        anchura=_to_float(anchura),
                        altura=_to_float(altura),
                        tipo=tipo_int,
                    )
                )
            i += 6

        if codigo_padre:
            concepto.mediciones[codigo_padre] = medicion
        else:
            concepto.mediciones["__sin_padre__"] = medicion

    # ---- Resolución de alias de # en descomposiciones ----------------

    def _resolver_alias_hash(self) -> None:
        """
        Presto 8.8 emite los hijos en ~D sin el # final (ej: '02.01') aunque
        el ~C correspondiente lo lleve ('02.01#'). Esta pasada unifica ambas
        representaciones: si existe codigo+'#' como concepto, reemplaza el hijo
        sin # por la versión con #, y fusiona los datos si procede.
        """
        aliased: set[str] = set()   # códigos sin # que se redirigieron a su gemelo con #
        for concepto in self.presupuesto.conceptos.values():
            for hijo in concepto.hijos:
                cod = hijo.codigo_hijo
                if not cod.endswith('#'):
                    cod_con_hash = cod + '#'
                    c_hash = self.presupuesto.get(cod_con_hash)
                    c_sin  = self.presupuesto.get(cod)
                    if c_hash is not None:
                        # Fusionar: si el concepto sin # tiene datos útiles, pasarlos
                        if c_sin is not None and c_sin.resumen and not c_hash.resumen:
                            c_hash.resumen = c_sin.resumen
                        # Apuntar el hijo al concepto con #
                        hijo.codigo_hijo = cod_con_hash
                        aliased.add(cod)

        # Eliminar los conceptos "fantasma" sin #: son artefactos creados al leer
        # un ~D que referenciaba el código sin # antes de existir su gemelo con #.
        # Solo se borran si están vacíos (sin descomposición, sin precio, sin
        # mediciones) y ya nadie los referencia — así no se exportan ~C basura.
        for cod in aliased:
            c = self.presupuesto.get(cod)
            if c is None:
                continue
            vacio = (not c.hijos and not c.mediciones
                     and not getattr(c, "_precio_bc3", None) and not c.resumen)
            referenciado = any(
                h.codigo_hijo == cod
                for otro in self.presupuesto.conceptos.values()
                for h in otro.hijos
            )
            if vacio and not referenciado:
                del self.presupuesto.conceptos[cod]

    # ---- Detección de la obra raíz --------------------------------------

    def _detectar_raiz(self) -> None:
        """
        Estrategia por orden de prioridad:

        1. Existe un concepto cuyo código termina exactamente en '##' → es la raíz.
        2. No existe '##': buscamos conceptos que no sean hijos de nadie y que
           tengan hijos propios (son capítulos raíz sueltos, como en Presto 8.8
           sin concepto raíz explícito).
           - Si hay uno solo → es la raíz.
           - Si hay varios   → creamos una raíz sintética 'OBRA##' que los agrupa,
             conservando el precio de cada capítulo como precio_es_dato=True para
             que el importe de cada fase se recalcule correctamente.
        """
        # Paso 1: buscar raíz explícita con ##
        for codigo, c in self.presupuesto.conceptos.items():
            if codigo.endswith("##"):
                self.presupuesto.codigo_raiz = codigo
                return

        # Paso 2: conceptos que no son hijos de nadie.
        # Normalizamos quitando el # final para comparar, porque Presto 8.8
        # omite el # en los códigos de ~D aunque los conceptos lo lleven.
        todos_hijos: set[str] = set()
        for c in self.presupuesto.conceptos.values():
            for h in c.hijos:
                todos_hijos.add(h.codigo_hijo)
                todos_hijos.add(h.codigo_hijo.rstrip('#'))

        candidatos = [
            cod for cod, c in self.presupuesto.conceptos.items()
            if cod not in todos_hijos
            and cod.rstrip('#') not in todos_hijos
            and c.hijos
        ]

        if not candidatos:
            return

        if len(candidatos) == 1:
            self.presupuesto.codigo_raiz = candidatos[0]
            return

        # Varios capítulos raíz sueltos (caso Presto 8.8 sin ##):
        # creamos un nodo raíz sintético que los agrupa.
        raiz = Concepto(codigo="OBRA##", resumen="Presupuesto")
        raiz.precio_es_dato = False
        for cod in candidatos:
            raiz.hijos.append(Hijo(codigo_hijo=cod, factor=1.0, rendimiento=1.0))
        self.presupuesto.add_concepto(raiz)
        self.presupuesto.codigo_raiz = "OBRA##"


def leer_bc3(ruta: str) -> Presupuesto:
    """Función de conveniencia: lee un archivo BC3 y devuelve el Presupuesto."""
    return LectorBC3().leer(ruta)
