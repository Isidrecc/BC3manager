"""
Modelo de datos del presupuesto BC3 (FIEBDC-3).

El núcleo de un presupuesto es un árbol de Conceptos. Cada concepto puede ser:
  - Capítulo / subcapítulo (agrupa otros conceptos)
  - Partida (unidad de obra, normalmente con descomposición y medición)
  - Concepto unitario / básico (mano de obra, material, maquinaria)

La relación padre->hijo se establece mediante los registros ~D (descomposición).
Los totales se propagan SIEMPRE de abajo hacia arriba mediante recálculo
determinista. El precio de un concepto con descomposición es la suma de
(precio_hijo * rendimiento) de sus hijos; el de una partida con medición es
precio_unitario * medición_total.

Esta separación es deliberada: cuando más adelante se añada una capa de IA,
la IA NUNCA calculará totales. Solo invocará operaciones sobre este modelo y
el recálculo se hará aquí, de forma auditable y reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Optional


def _redondea(x: float, dec: int) -> float:
    """Redondeo mitad-arriba (ROUND_HALF_UP), como Presto/Excel, a `dec`
    decimales. Python usa por defecto redondeo bancario (mitad al par), que
    difiere de Presto en los casos .xx5. Usar str(x) evita arrastrar el error
    de representación binaria del float."""
    q = Decimal(1).scaleb(-dec)          # 10^-dec  → p.ej. dec=2 → 0.01
    return float(Decimal(str(x)).quantize(q, rounding=ROUND_HALF_UP))


def _mult_red(a: float, b: float, dec: int) -> float:
    """Multiplica dos magnitudes en aritmética DECIMAL exacta y redondea
    mitad-arriba a `dec` decimales, como hace Presto.

    Hacer la multiplicación en float arrastra el error binario: p.ej.
    0,015 × 27,49 da 0,41234999… en float (debería ser 0,41235), y entonces
    el redondeo a 4 decimales baja a 0,4123 en vez de subir a 0,4124. Operando
    en Decimal el producto es exacto (0,41235) y el redondeo coincide con
    Presto. `str()` convierte cada float a su decimal más corto sin el ruido
    binario."""
    q = Decimal(1).scaleb(-dec)
    prod = Decimal(str(a)) * Decimal(str(b))
    return float(prod.quantize(q, rounding=ROUND_HALF_UP))


def _num_decimales(x: float) -> int:
    """Nº de decimales significativos de un valor, contados sobre su repr más
    corto (str), no sobre el float crudo. Devuelve -1 si parece ruido binario
    (más de 8 decimales), para no dar falsos avisos. Ej.: 0.315→3, -3.1415→4,
    29.0→0, 0.30→1."""
    s = str(abs(x))
    if "e" in s or "E" in s:        # notación científica → ruido
        return -1
    if "." not in s:
        return 0
    dec = s.split(".")[1].rstrip("0")
    n = len(dec)
    return -1 if n > 8 else n


class TipoConcepto(Enum):
    """Tipo de concepto según su papel en el árbol."""
    CAPITULO = "capitulo"          # Agrupador (incluye obra raíz y subcapítulos)
    PARTIDA = "partida"            # Unidad de obra
    UNITARIO = "unitario"          # Mano de obra, material, maquinaria (hoja)
    OTRO = "otro"                  # Sin clasificar


@dataclass
class LineaMedicion:
    """
    Una línea de medición (procedente de un registro ~M).

    El total de una línea es:  n_uds * longitud * anchura * altura
    donde los factores que valgan 0 se interpretan como 1 (no anulan el
    producto). Esto sigue el comportamiento habitual de los programas del
    sector: una línea "5 / 0 / 0 / 0" mide 5, no 0.
    """
    comentario: str = ""
    n_uds: float = 0.0
    longitud: float = 0.0
    anchura: float = 0.0
    altura: float = 0.0
    # Tipo de línea FIEBDC: 0=normal, 1=parcial, 2=acumulado, 3=fórmula, etc.
    tipo: int = 0
    formula: str = ""

    @property
    def subtotal(self) -> float:
        """Producto de los factores, tratando 0 como factor neutro (1)."""
        factores = [self.n_uds, self.longitud, self.anchura, self.altura]
        resultado = 1.0
        algun_factor = False
        for f in factores:
            if f != 0:
                resultado *= f
                algun_factor = True
        return resultado if algun_factor else 0.0


@dataclass
class Medicion:
    """Conjunto de líneas de medición de una partida en un destino (capítulo padre)."""
    lineas: list[LineaMedicion] = field(default_factory=list)
    # Total declarado en el campo 3 del registro ~M del BC3. Opcional: muchos
    # archivos lo dejan vacío y el total se obtiene sumando líneas. Cuando
    # viene relleno y NO coincide con la suma, suele indicar un fichero
    # generado con datos inconsistentes (manipulación manual, exportador con
    # bugs, edición en otro programa que no recalculó).
    total_declarado: float = 0.0

    @property
    def total(self) -> float:
        return round(sum(linea.subtotal for linea in self.lineas), 6)


@dataclass
class Hijo:
    """
    Referencia de un concepto a uno de sus hijos dentro de una descomposición (~D).

    rendimiento: cantidad del hijo por unidad del padre (factor * rendimiento en
    la especificación; aquí lo guardamos ya combinado para simplificar la v1).
    """
    codigo_hijo: str
    factor: float = 1.0
    rendimiento: float = 1.0

    @property
    def cantidad(self) -> float:
        return self.factor * self.rendimiento


@dataclass
class Concepto:
    """
    Un concepto del presupuesto: capítulo, partida o concepto unitario.

    codigo:     código único (clave en el diccionario de conceptos)
    unidad:     unidad de medida (m, m2, m3, ud, kg, PA, %...)
    resumen:    descripción corta
    texto:      descripción larga / pliego (registro ~T)
    precio:     precio unitario. En conceptos con descomposición es CALCULADO;
                en conceptos hoja (unitarios) es un dato de entrada.
    tipo:       TipoConcepto
    hijos:      lista de descomposición (vacía en conceptos hoja)
    mediciones: medición por cada padre que lo contiene (clave = código padre)
    """
    codigo: str
    unidad: str = ""
    resumen: str = ""
    texto: str = ""
    precio: float = 0.0
    tipo: TipoConcepto = TipoConcepto.OTRO
    hijos: list[Hijo] = field(default_factory=list)
    mediciones: dict[str, Medicion] = field(default_factory=dict)
    # Marca si el precio es dato de entrada (hoja) o calculado (con descomposición)
    precio_es_dato: bool = True

    @property
    def es_raiz_obra(self) -> bool:
        """En FIEBDC el concepto raíz tiene un código que termina en ## o #."""
        return self.codigo.endswith("##") or self.codigo.endswith("#")


class Presupuesto:
    """
    Contenedor de todos los conceptos y la lógica de recálculo del árbol.

    Mantiene un diccionario {codigo: Concepto}. El recálculo de precios se hace
    en profundidad (post-orden) con memoización para evitar recomputar y para
    cortar ciclos accidentales.
    """

    def __init__(self) -> None:
        self.conceptos: dict[str, Concepto] = {}
        self.codigo_raiz: Optional[str] = None
        # Metadatos de cabecera (~V) y coeficientes (~K)
        self.version_formato: str = ""
        self.programa_emisor: str = ""
        self.codificacion: str = ""
        self.tipo_datos: str = ""        # "1" presupuesto, "2" BBDD, "3" certificación...
        # Redondeos (registro ~K). Si el archivo trae ~K, replicamos el modo de
        # Presto: redondear cada subtotal de la descomposición y el precio de
        # partida/capítulo a `dec_*` decimales (mitad-arriba). Si NO hay ~K,
        # `redondeo_activo=False` y se calcula a precisión alta (comportamiento
        # histórico — no rompe presupuestos sintéticos sin ~K).
        self.redondeo_activo: bool = False
        # Decimales del registro ~K (orden FIEBDC verificado empíricamente):
        #   pos1 DecDet, pos2 DecCantMed, pos3 DecCantRend, pos4 DecImp,
        #   pos5 DecNat, pos6 DecPar, pos7 Dec
        self.dec_subtotal: int = 2       # DecImp: subtotales en descomposiciones
        self.dec_precio_partida: int = 2 # DecPar: precios de partidas
        self.dec_precio_capitulo: int = 2# Dec:    precios de capítulos
        self.dec_cantrend: int = 3       # DecCantRend: cantidades/rendimientos (incl. % implícito)
        self.dec_cantmed: int = 2        # DecCantMed: cantidades de mediciones
        self.dec_natural: int = 2        # DecNat: precios de conceptos básicos
        self.dec_importe: int = 2        # importes (precio × medición)
        self.dec_parcial: int = 2        # DSP/DecDet: parciales de líneas de medición
        # Decimales de las líneas de medición (FIEBDC campo 3 del ~K). Presto
        # redondea CADA factor a estos decimales ANTES de multiplicar: las
        # dimensiones a DD y el nº de partes iguales a DN (ambos 2 por defecto).
        # Sin esto, una altura 0,0475 se multiplica en crudo en vez de 0,05.
        self.dec_dim: int = 2            # DD: dimensiones (largo/ancho/alto)
        self.dec_num: int = 2            # DN: nº de partes iguales (uds)
        self.moneda: str = "EUR"         # divisa declarada en el ~K
        # Coeficientes económicos del campo 2 del registro ~K (FIEBDC):
        #   CI \ GG \ BI \ BAJA \ IVA   (todos en porcentaje).
        # Se guardan en tanto por uno (0.06 = 6%). El CI (costes indirectos) es
        # el único que afecta al PEM: el estándar define el precio de una unidad
        # de obra como Coste Directo + Coste Indirecto, aplicado POR PARTIDA.
        # GG/BI/IVA/BAJA se conservan para cálculos posteriores (PEC, total con
        # IVA) pero no intervienen en el PEM. Valen 0 si el archivo no los
        # declara (p.ej. Presto 8.8), preservando el cálculo exacto.
        self.ci_pct: float = 0.0    # Costes Indirectos
        self.gg_pct: float = 0.0    # Gastos Generales
        self.bi_pct: float = 0.0    # Beneficio Industrial
        self.baja_pct: float = 0.0  # Baja/alza de adjudicación
        self.iva_pct: float = 0.0   # IVA

    # ---- Construcción ----------------------------------------------------

    def add_concepto(self, concepto: Concepto) -> None:
        self.conceptos[concepto.codigo] = concepto

    def get(self, codigo: str) -> Optional[Concepto]:
        return self.conceptos.get(codigo)

    # ---- Clasificación de tipos -----------------------------------------

    def clasificar_tipos(self) -> None:
        """
        Asigna TipoConcepto a cada concepto. Usa el campo _tipo_fiebdc cuando
        está disponible (emitido por Presto y otros programas en el 6º campo
        del registro ~C). Si no, aplica heurísticas por código y estructura.

        Tipos FIEBDC:
          0=sin clasificar  1=mano obra  2=maquinaria  3=material
          4=resto costes    5=subcapítulo (capítulo)   6=partida alzada
        """
        UNITARIOS_FIEBDC = {"1", "2", "3", "4"}   # hoja
        CAPITULOS_FIEBDC = {"5"}
        PARTIDAS_FIEBDC  = {"6"}

        for c in self.conceptos.values():
            tf = getattr(c, "_tipo_fiebdc", "")

            if tf in UNITARIOS_FIEBDC:
                c.tipo = TipoConcepto.UNITARIO
            elif tf in CAPITULOS_FIEBDC:
                c.tipo = TipoConcepto.CAPITULO
            elif tf in PARTIDAS_FIEBDC:
                c.tipo = TipoConcepto.PARTIDA
            else:
                # ¿Sus hijos están MEDIDOS dentro de este concepto? Es decir, su
                # ~M apunta a mi código (son partidas que cuelgan de mí) o son
                # subcapítulos. Si es así, este concepto AGREGA importes y es un
                # capítulo. Si sus hijos son recursos (mano de obra, material…) o
                # auxiliares NO medidos en mí, no agrega: con medición es partida.
                # OJO: no vale "el hijo tiene hijos" (un recurso auxiliar puede
                # tener descomposición propia sin ser una partida de este padre).
                agrega = any(
                    (hc := self.conceptos.get(h.codigo_hijo)) is not None
                    and (c.codigo in hc.mediciones or hc.es_raiz_obra)
                    for h in c.hijos
                )
                # Heurística: raíz o código con # sin unidad → capítulo
                if c.es_raiz_obra or (c.codigo.endswith("#") and not c.unidad):
                    c.tipo = TipoConcepto.CAPITULO
                elif c.hijos and agrega:
                    # Hijos son partidas/subcapítulos → es un capítulo, AUNQUE
                    # traiga una medición "fantasma" (Prestos antiguos ponían a
                    # veces medición=1 en los capítulos). No lo confundas con
                    # partida por tener ~M.
                    c.tipo = TipoConcepto.CAPITULO
                elif c.mediciones:
                    # Tiene medición propia y NO agrega partidas: es una PARTIDA
                    # medida, aunque tenga descomposición de recursos y le falte
                    # la unidad en el ~C (caso 'Cartell de 120x120 d'alumini', y
                    # las partidas alzadas hoja con unidad "PA"). Los capítulos
                    # de verdad ya se han filtrado arriba por 'agrega'.
                    c.tipo = TipoConcepto.PARTIDA
                elif c.hijos:
                    # Con descomposición y unidad → partida; sin unidad → capítulo
                    c.tipo = TipoConcepto.PARTIDA if c.unidad else TipoConcepto.CAPITULO
                else:
                    c.tipo = TipoConcepto.UNITARIO

    # ---- Validación de precios cargados --------------------------------

    def comparar_importes_archivo(self) -> dict:
        """Devuelve la comparación COMPLETA entre lo grabado en el archivo BC3
        y lo que sale de la propagación recalculada.

        IMPORTANTE: este método llama a `recalcular()`. Antes de llamar,
        capturamos los valores del archivo (que están en `_precio_bc3` y en
        las mediciones leídas).

        Devuelve:
          {
            "partidas": [
              {codigo, padre, resumen, unidad,
               precio_archivo, precio_calc,
               medicion, importe_archivo, importe_calc, diferencia, diferencia_pct},
              ...  # TODAS las partidas, no solo las discrepantes
            ],
            "capitulos": [
              {codigo, padre, resumen,
               precio_archivo, importe_archivo,    # precio_bc3 del ~C (Presto 8.8)
               importe_calc,                       # suma de hijos
               diferencia, diferencia_pct},
              ...  # TODOS los capítulos
            ],
            "pem_archivo": float,         # suma de importe_archivo de capítulos raíz
            "pem_calculado": float,       # suma de importe_calc de capítulos raíz
            "diferencia_pem": float,
          }
        """
        # ---- Snapshot ANTES de recalcular ----
        # Para cada concepto guardamos el precio "del archivo" tal como vino
        precios_archivo: dict[str, float] = {}
        for cod, c in self.conceptos.items():
            pbc3 = getattr(c, "_precio_bc3", None)
            precios_archivo[cod] = pbc3 if pbc3 is not None else c.precio

        # Recalcular para tener los precios propagados
        self.recalcular()

        partidas: list[dict] = []
        capitulos: list[dict] = []

        # Recorrer el árbol enumerando cada (concepto, padre)
        def recorrer(codigo: str, codigo_padre: str) -> None:
            c = self.conceptos.get(codigo)
            if c is None:
                return
            if c.tipo == TipoConcepto.CAPITULO:
                p_archivo = precios_archivo.get(codigo, 0) or 0
                imp_archivo = round(p_archivo, 2)
                imp_calc = self._importe_recursivo(codigo, codigo_padre)
                diff = imp_calc - imp_archivo
                denom = max(abs(imp_archivo), abs(imp_calc))
                pct = (abs(diff) / denom * 100) if denom > 0 else 0
                # Solo añadimos si el capítulo tiene precio_bc3 (sino la comparación no tiene sentido)
                if p_archivo > 0 or imp_calc > 0:
                    capitulos.append({
                        "codigo": codigo,
                        "padre": codigo_padre,
                        "resumen": c.resumen,
                        "precio_archivo": round(p_archivo, 4),
                        "importe_archivo": imp_archivo,
                        "importe_calc": round(imp_calc, 2),
                        "diferencia": round(diff, 2),
                        "diferencia_pct": round(pct, 2),
                    })
                # Recursión hacia hijos
                for h in c.hijos:
                    recorrer(h.codigo_hijo, codigo)
            elif c.tipo == TipoConcepto.PARTIDA:
                # ESTRICTO: el lado "archivo" usa SOLO valores del archivo
                # (precio CD del ~C, medición declarada del ~M); el lado "calc"
                # usa lo que recalculamos (CD del desglose, medición de líneas).
                med_obj = c.mediciones.get(codigo_padre)
                # Medición del archivo = total declarado del ~M; si no lo hubiera,
                # la suma de sus líneas.
                if med_obj is not None and med_obj.total_declarado:
                    med_archivo = med_obj.total_declarado
                else:
                    med_archivo = self.medicion_total(codigo, codigo_padre)
                med_calc = self.medicion_total(codigo, codigo_padre)
                p_archivo = precios_archivo.get(codigo, 0) or 0   # CD del ~C
                p_calc = c.precio                                  # CD recalculado
                # Precio con CI (= TOTAL PARTIDA de Presto): CD + costes indirectos.
                # El ~C puede traer el CD con más decimales que DecPar (p.ej.
                # 8,8638); Presto lo redondea a DecPar antes de aplicar el CI.
                p_archivo_red = (_redondea(p_archivo, self.dec_precio_partida)
                                 if self.redondeo_activo else p_archivo)
                p_archivo_ci = self._con_ci(p_archivo_red)
                p_calc_ci = self.precio_con_ci(codigo)
                imp_archivo = round(p_archivo_ci * med_archivo, 2)  # estricto del archivo
                imp_calc = round(p_calc_ci * med_calc, 2)           # nuestro cálculo
                diff = imp_calc - imp_archivo
                denom = max(abs(imp_archivo), abs(imp_calc))
                pct = (abs(diff) / denom * 100) if denom > 0 else 0
                partidas.append({
                    "codigo": codigo,
                    "padre": codigo_padre,
                    "resumen": c.resumen,
                    "unidad": c.unidad,
                    "precio_archivo": round(p_archivo, 4),       # CD (lo que guarda el ~C)
                    "precio_calc": round(p_calc, 4),             # CD recalculado
                    "precio_archivo_ci": round(p_archivo_ci, 4), # CD + CI (Presto)
                    "precio_calc_ci": round(p_calc_ci, 4),       # CD + CI (calculado)
                    "medicion_archivo": round(med_archivo, 4),   # ~M declarada (archivo)
                    "medicion_calc": round(med_calc, 4),         # suma de líneas (calc)
                    "medicion": round(med_calc, 4),              # compat. (= calc)
                    "importe_archivo": imp_archivo,
                    "importe_calc": imp_calc,
                    "diferencia": round(diff, 2),
                    "diferencia_pct": round(pct, 2),
                })

        if self.codigo_raiz:
            raiz = self.conceptos.get(self.codigo_raiz)
            if raiz:
                for h in raiz.hijos:
                    recorrer(h.codigo_hijo, self.codigo_raiz)

        # PEM "archivo" = suma de importes archivo de capítulos raíz que tengan precio_bc3>0
        # PEM "calculado" = suma de importes calc de capítulos raíz
        raiz_cods = [h.codigo_hijo for h in raiz.hijos] if self.codigo_raiz and raiz else []
        pem_archivo = sum(
            (precios_archivo.get(c, 0) or 0) for c in raiz_cods
        )
        pem_calculado = self.presupuesto_total()

        return {
            "partidas": partidas,
            "capitulos": capitulos,
            "pem_archivo": round(pem_archivo, 2),
            "pem_calculado": round(pem_calculado, 2),
            "diferencia_pem": round(pem_calculado - pem_archivo, 2),
        }

    def revisar_consistencia_k(self, max_ejemplos: int = 5) -> dict:
        """Revisa si los valores del archivo respetan los decimales que declara
        su registro ~K (que para campos en positivo son EXACTOS). Un valor con
        MÁS decimales de los declarados es un aviso de no conformidad: el
        cálculo lo redondea igual (replica a Presto/FIEBDC), pero conviene saber
        que el archivo trae datos fuera de su propio ~K.

        Devuelve un dict por categoría:
          { categoria: {declarado, total, ejemplos:[{codigo,padre,campo,valor}]} }
        Solo se evalúa si hay ~K (redondeo_activo); si no, devuelve {}.
        """
        if not self.redondeo_activo:
            return {}

        cats: dict[str, dict] = {}

        def avisa(cat: str, declarado: int, codigo: str, padre: str,
                  campo: str, valor: float) -> None:
            nd = _num_decimales(valor)
            if nd < 0 or nd <= declarado:
                return
            d = cats.setdefault(cat, {"declarado": declarado, "total": 0, "ejemplos": []})
            d["total"] += 1
            if len(d["ejemplos"]) < max_ejemplos:
                d["ejemplos"].append({
                    "codigo": codigo, "padre": padre, "campo": campo,
                    "valor": valor, "decimales": nd,
                })

        for cod, c in self.conceptos.items():
            # Rendimientos del ~D (DR/DRS)
            for h in c.hijos:
                avisa("rendimientos", self.dec_cantrend, cod, "", "rendimiento",
                      h.rendimiento)
            # Precio de conceptos hoja (básicos): DES/DUO ~ dec_natural
            if not c.hijos and c.precio:
                avisa("precios_basicos", self.dec_natural, cod, "", "precio", c.precio)
            # Líneas de medición: uds (DN) y dimensiones (DD)
            for padre, m in c.mediciones.items():
                if padre == "__sin_padre__":
                    continue
                for ln in m.lineas:
                    avisa("uds_medicion", self.dec_num, cod, padre, "uds", ln.n_uds)
                    avisa("dimensiones", self.dec_dim, cod, padre, "longitud", ln.longitud)
                    avisa("dimensiones", self.dec_dim, cod, padre, "anchura", ln.anchura)
                    avisa("dimensiones", self.dec_dim, cod, padre, "altura", ln.altura)
        return cats

    def validar_precios_cargados(
        self, tolerancia_abs: float = 0.01, tolerancia_rel: float = 0.005
    ) -> list[dict]:
        """Atajo para mantener compatibilidad. Devuelve solo las discrepancias
        de precios (sin mediciones ni PEM). Usa `validar_completo` para todo."""
        return self.validar_completo(tolerancia_abs, tolerancia_rel)["precios"]

    def validar_completo(
        self, tolerancia_abs: float = 0.01, tolerancia_rel: float = 0.005
    ) -> dict:
        """Validación exhaustiva: compara los datos del archivo con la
        propagación completa de cantidades, precios e importes.

        Flujo de propagación que se verifica:
          1. Líneas de medición → medición total de la partida
          2. Precios hoja × rendimientos (~D) → precio de partida (descomp.)
          3. Precio × medición → importe de partida
          4. Suma de importes de partidas → importe de capítulo
          5. Suma de importes de capítulos raíz → PEM

        En cada paso se compara contra el valor declarado en el archivo (si lo
        hubiera) y se reporta cualquier diferencia significativa.

        Devuelve un dict con tres listas y un resumen:
          {
            "mediciones": [...],    # ~M total declarado != suma líneas
            "precios": [...],       # ~C precio != precio recalculado (partidas y capítulos)
            "pem": {...} or None,   # PEM archivo vs PEM calculado
            "resumen": {...},       # contadores y totales
          }
        """
        def es_diferente(archivo: float, calc: float) -> bool:
            diff = abs(archivo - calc)
            if diff < tolerancia_abs:
                return False
            denom = max(abs(archivo), abs(calc))
            if denom == 0:
                return diff > tolerancia_abs
            return (diff / denom) > tolerancia_rel

        # =====================================================================
        # FASE 1 — Snapshot de TODO lo que dice el archivo (antes de recalcular)
        # =====================================================================
        precios_archivo: dict[str, float] = {}
        mediciones_declaradas: dict[tuple[str, str], float] = {}
        mediciones_lineas: dict[tuple[str, str], float] = {}
        cantidades_d: dict[tuple[str, str], float] = {}
        for cod, c in self.conceptos.items():
            pbc3 = getattr(c, "_precio_bc3", None)
            if pbc3 is not None:
                precios_archivo[cod] = pbc3
            for h in c.hijos:
                cantidades_d[(h.codigo_hijo, cod)] = h.cantidad
            for padre, m in c.mediciones.items():
                if padre == "__sin_padre__":
                    continue
                # Suma de líneas con el redondeo de Presto (parcial a DecDet,
                # total a DecCantMed) para no marcar como descuadre lo que solo
                # es ruido de redondeo (p.ej. 7907,0325 cruda vs 7907,030 real).
                mediciones_lineas[(cod, padre)] = self.total_medicion(m)
                if m.total_declarado:
                    mediciones_declaradas[(cod, padre)] = m.total_declarado

        # =====================================================================
        # FASE 2 — Recalcular propagando desde las hojas hacia arriba
        # =====================================================================
        self.recalcular()

        # =====================================================================
        # FASE 3 — Comparar el archivo con la propagación
        # =====================================================================
        disc_mediciones: list[dict] = []
        disc_precios: list[dict] = []
        disc_pem: Optional[dict] = None

        # 3.1 — Medición total declarada vs suma de líneas
        for (cod, padre), declarada in mediciones_declaradas.items():
            suma = mediciones_lineas.get((cod, padre), 0.0)
            if es_diferente(declarada, suma):
                c = self.conceptos.get(cod)
                disc_mediciones.append({
                    "codigo": cod,
                    "padre": padre,
                    "resumen": c.resumen if c else "",
                    "declarada": round(declarada, 4),
                    "suma_lineas": round(suma, 4),
                    "diferencia": round(suma - declarada, 4),
                })

        # 3.2 — Precio archivo (~C) vs precio recalculado
        # Solo para conceptos con descomposición (los conceptos hoja siempre
        # tienen `precio_es_dato`, no hay nada que recalcular en ellos).
        for cod, p_archivo in precios_archivo.items():
            if p_archivo <= 0:
                continue
            c = self.conceptos.get(cod)
            if not c or not c.hijos:
                continue
            p_calc = c.precio
            # El precio recalculado de un capítulo es coste directo (CD), pero el
            # precio congelado del archivo incluye los costes indirectos. Para
            # comparar lo mismo con lo mismo, se aplica el CI al CD del capítulo.
            # Es "agregador" (capítulo o subcapítulo) si su tipo es CAPITULO y al
            # menos un hijo tiene mediciones o descomposición propia. Así se
            # excluyen las partidas con descomposición mal clasificadas como
            # capítulo (todos sus hijos son recursos hoja), cuyo precio de
            # archivo ya es CD sin CI.
            es_agregador = c.tipo == TipoConcepto.CAPITULO and any(
                (hc := self.conceptos.get(h.codigo_hijo)) and (hc.mediciones or hc.hijos)
                for h in c.hijos
            )
            if self.ci_pct and es_agregador:
                p_calc = p_calc * (1 + self.ci_pct)
            if es_diferente(p_archivo, p_calc):
                diff = p_calc - p_archivo
                denom = max(abs(p_archivo), abs(p_calc))
                disc_precios.append({
                    "codigo": cod,
                    "resumen": c.resumen,
                    "tipo": c.tipo.value,
                    "precio_bc3": round(p_archivo, 4),
                    "precio_calculado": round(p_calc, 4),
                    "diferencia": round(diff, 4),
                    "diferencia_pct": round((abs(diff) / denom * 100) if denom else 0, 2),
                })

        # 3.3 — PEM del archivo vs PEM calculado
        # PEM "archivo" = suma de precios congelados de los capítulos raíz.
        # El PEM es la cifra clave del presupuesto: se reporta ante CUALQUIER
        # diferencia >= 1 céntimo (sin tolerancia relativa), porque incluso
        # diferencias pequeñas acumuladas indican que el archivo y el cálculo
        # no cuadran exactamente y el usuario debe saberlo.
        pem_calc = self.presupuesto_total()
        if self.codigo_raiz:
            raiz = self.conceptos.get(self.codigo_raiz)
            if raiz:
                precios_raiz = [
                    precios_archivo.get(h.codigo_hijo, 0) or 0
                    for h in raiz.hijos
                ]
                # Solo comparable si TODOS los capítulos raíz tienen precio_bc3 > 0
                if precios_raiz and all(p > 0 for p in precios_raiz):
                    pem_archivo = sum(precios_raiz)
                    dif_pem = pem_calc - pem_archivo
                    if abs(dif_pem) >= 0.01:   # tolerancia: 1 céntimo, sin % relativo
                        disc_pem = {
                            "pem_archivo": round(pem_archivo, 2),
                            "pem_calculado": round(pem_calc, 2),
                            "diferencia": round(dif_pem, 2),
                        }

        # Ordenar por gravedad (diferencia absoluta) descendente
        disc_mediciones.sort(key=lambda d: abs(d["diferencia"]), reverse=True)
        disc_precios.sort(key=lambda d: abs(d["diferencia"]), reverse=True)

        return {
            "mediciones": disc_mediciones,
            "precios": disc_precios,
            "pem": disc_pem,
            "resumen": {
                "total_conceptos": len(self.conceptos),
                "total_mediciones": len(mediciones_lineas),
                "mediciones_con_total_declarado": len(mediciones_declaradas),
                "pem_calculado": round(pem_calc, 2),
            },
        }

    # ---- Recálculo de precios -------------------------------------------

    @staticmethod
    def es_porcentaje(concepto: "Concepto") -> bool:
        """True si el concepto es una línea de porcentaje (medios auxiliares,
        costes indirectos, etc.). En FIEBDC se identifican porque su unidad es
        '%' o su código empieza por '%'. Su contribución al precio de la partida
        NO es precio×rendimiento, sino (suma de líneas anteriores) × coeficiente."""
        if concepto is None:
            return False
        if (concepto.unidad or "").strip() == "%":
            return True
        if (concepto.codigo or "").startswith("%"):
            return True
        return False

    def recalcular(self) -> None:
        """
        Recalcula el precio de todos los conceptos con descomposición,
        de abajo hacia arriba. Los conceptos hoja conservan su precio de dato.

        Las líneas de PORCENTAJE (medios auxiliares %MA, costes indirectos…)
        se aplican sobre el acumulado de las líneas anteriores de la misma
        descomposición, NO como precio×rendimiento. Por eso la descomposición
        se procesa EN ORDEN manteniendo una suma corriente.
        """
        memo: dict[str, float] = {}
        en_proceso: set[str] = set()

        def precio_de(codigo: str) -> float:
            if codigo in memo:
                return memo[codigo]
            concepto = self.conceptos.get(codigo)
            if concepto is None:
                return 0.0
            # Concepto hoja sin descomposición: su precio es dato. Presto almacena
            # los precios de conceptos BÁSICOS (mano de obra, material, maquinaria)
            # redondeados a DecNat decimales. Si el ~C trae más decimales (p.ej.
            # 59,4882 con DecNat=3) hay que redondear ANTES de multiplicar por el
            # rendimiento, o el subtotal arrastra el error y puede volcar el redondeo
            # del precio de partida (1,02×59,4882=60,6780 en vez de 1,02×59,488=
            # 60,6778, que desvía la Suma la partida de 80,00 a 80,01).
            if not concepto.hijos:
                precio = concepto.precio
                if self.redondeo_activo and concepto.tipo == TipoConcepto.UNITARIO:
                    precio = _redondea(precio, self.dec_natural)
                    concepto.precio = precio
                memo[codigo] = precio
                return precio
            # Protección contra ciclos
            if codigo in en_proceso:
                memo[codigo] = concepto.precio
                return concepto.precio
            en_proceso.add(codigo)
            total = 0.0
            for hijo in concepto.hijos:
                hc = self.conceptos.get(hijo.codigo_hijo)
                if hc is not None and self.es_porcentaje(hc):
                    # Línea de porcentaje (medios auxiliares, etc.). Presto la
                    # trata como una cantidad implícita sobre el acumulado:
                    #   cantidad = acumulado × coef / precio_%   (coef = 0.07, precio_% = 7)
                    # Esa cantidad se redondea a DecCantRend y luego se multiplica
                    # por el precio del concepto %. Es lo que reproduce el archivo
                    # al céntimo (p.ej. DEM.01.01 → 0,104 × 7 = 0,728).
                    precio_pct = hc.precio
                    if precio_pct:
                        qty = total * hijo.cantidad / precio_pct
                        if self.redondeo_activo:
                            qty = _redondea(qty, self.dec_cantrend)
                            sub = _mult_red(precio_pct, qty, self.dec_subtotal)
                        else:
                            sub = precio_pct * qty
                    else:
                        sub = total * hijo.cantidad
                        if self.redondeo_activo:
                            sub = _redondea(sub, self.dec_subtotal)
                else:
                    # Subtotal = precio × rendimiento. La multiplicación se hace en
                    # Decimal exacto y se redondea a DecImp mitad-arriba (igual que
                    # Presto); en float, 0,015×27,49 daría 0,41234999… → 0,4123 en
                    # vez de 0,4124.
                    if self.redondeo_activo:
                        sub = _mult_red(precio_de(hijo.codigo_hijo), hijo.cantidad,
                                        self.dec_subtotal)
                    else:
                        sub = precio_de(hijo.codigo_hijo) * hijo.cantidad
                total += sub
            en_proceso.discard(codigo)
            # Redondeo del precio del concepto: DecPar (partidas) o Dec (capítulos).
            if self.redondeo_activo:
                dec = (self.dec_precio_capitulo
                       if concepto.tipo == TipoConcepto.CAPITULO
                       else self.dec_precio_partida)
                total = _redondea(total, dec)
            else:
                total = round(total, 4)
            concepto.precio = total
            concepto.precio_es_dato = False
            memo[codigo] = total
            return total

        for codigo in self.conceptos:
            precio_de(codigo)

    # ---- Importe (precio * medición) ------------------------------------

    def total_medicion(self, med: "Medicion") -> float:
        """Total de una medición replicando el redondeo de Presto: cada parcial
        de línea se redondea a DecDet y la suma a DecCantMed.

        Presto NO suma los parciales en crudo: redondea cada línea a DecDet
        (p.ej. 2823,5325 → 2823,53) y luego redondea el total a DecCantMed. Sin
        esto, la suma cruda (7907,0325) difiere del total real (7907,030) y el
        importe sale desviado por unos céntimos. Sin ~K (redondeo_activo=False)
        se usa la suma a alta precisión (comportamiento histórico)."""
        if med is None:
            return 0.0
        # Sin líneas de detalle: la medición es el total declarado en el ~M
        # (partidas alzadas / abonaments fixes, p.ej. medición = 1 sin desglose).
        if not med.lineas:
            return med.total_declarado
        if not self.redondeo_activo:
            return med.total
        suma = sum(self.parcial_linea(l) for l in med.lineas)
        return _redondea(suma, self.dec_cantmed)

    def parcial_linea(self, linea: "LineaMedicion") -> float:
        """Parcial de una línea de medición replicando a Presto: redondea CADA
        factor antes de multiplicar (nº de partes a DN, dimensiones a DD) y el
        parcial a DSP. Un factor 0/vacío es neutro (no multiplica). Ej.: altura
        0,0475 → 0,05 (DD=2) antes de entrar en el producto.

        Sin ~K (redondeo_activo=False) usa el producto crudo (subtotal)."""
        if not self.redondeo_activo:
            return linea.subtotal
        factores = (
            (linea.n_uds, self.dec_num),
            (linea.longitud, self.dec_dim),
            (linea.anchura, self.dec_dim),
            (linea.altura, self.dec_dim),
        )
        # Acumular en Decimal EXACTO: multiplicar los factores en float introduce
        # error binario (42,30·3·0,25 = 31.724999999999998 en vez de 31,725) y el
        # ROUND_HALF_UP final baja a 31,72 en lugar de subir a 31,73 como Presto.
        resultado = Decimal(1)
        algun_factor = False
        for valor, dec in factores:
            if valor != 0:
                q = Decimal(1).scaleb(-dec)
                resultado *= Decimal(str(valor)).quantize(q, rounding=ROUND_HALF_UP)
                algun_factor = True
        if not algun_factor:
            return 0.0
        q = Decimal(1).scaleb(-self.dec_parcial)
        return float(resultado.quantize(q, rounding=ROUND_HALF_UP))

    def medicion_total(self, codigo_hijo: str, codigo_padre: str) -> float:
        """Medición de un concepto dentro de un padre concreto."""
        concepto = self.conceptos.get(codigo_hijo)
        if concepto is None:
            return 0.0
        return self.total_medicion(concepto.mediciones.get(codigo_padre))

    def precio_con_ci(self, codigo: str) -> float:
        """Precio de una partida CON costes indirectos, como lo muestra Presto.

        El estándar FIEBDC define el precio de una unidad de obra como
        Coste Directo + Coste Indirecto. Presto aplica el % de CI a TODAS las
        partidas por igual: sobre el coste directo (ya redondeado a DecPar) suma
        el CI y redondea de nuevo.
          - 301.0010: round(8,86 × 1,06) = 9,39
          - 700.001a: round(32,33 × 1,06) = 34,27

        El CD ya incluye cualquier línea interna del desglose, incluidas las
        líneas de porcentaje tipo %CI / medios auxiliares que el redactor añade
        sobre ciertas líneas (son un coste más del desglose, NO el CI global).
        Por eso NO se excluyen: el 6% se aplica encima de todo, igual que Presto.

        Recursos básicos y capítulos devuelven su precio sin tocar. Con
        ci_pct = 0 (p.ej. Presto 8.8) devuelve el precio tal cual."""
        c = self.conceptos.get(codigo)
        if c is None:
            return 0.0
        if self.ci_pct and c.tipo == TipoConcepto.PARTIDA:
            return self._con_ci(c.precio)
        return c.precio

    def _con_ci(self, precio_cd: float) -> float:
        """Aplica el coste indirecto a un coste directo, con el redondeo de
        Presto (a DecPar). round(CD × (1+ci)). Con ci_pct = 0 devuelve el CD."""
        if not self.ci_pct:
            return precio_cd
        if self.redondeo_activo:
            return _mult_red(precio_cd, 1 + self.ci_pct, self.dec_precio_partida)
        return round(precio_cd * (1 + self.ci_pct), 2)

    def importe_en_padre(self, codigo_hijo: str, codigo_padre: str) -> float:
        """Importe de una línea hijo dentro de su padre: precio × medición.

        Si no hay medición explícita (sin registros ~M), el importe es 0 — sin
        fallback a la cantidad del ~D. Esto mantiene la coherencia con la
        cantidad mostrada en la UI: si la cantidad es 0, el importe es 0.

        Usa `precio_con_ci`: el precio de partida incluye el CI por partida, tal
        como hace Presto.
        """
        concepto = self.conceptos.get(codigo_hijo)
        if concepto is None:
            return 0.0
        med = self.medicion_total(codigo_hijo, codigo_padre)
        if self.redondeo_activo:
            return _mult_red(self.precio_con_ci(codigo_hijo), med, self.dec_importe)
        return round(self.precio_con_ci(codigo_hijo) * med, 2)

    def presupuesto_total(self) -> float:
        """Importe total del presupuesto (importe del concepto raíz)."""
        if not self.codigo_raiz:
            return 0.0
        raiz = self.conceptos.get(self.codigo_raiz)
        if not raiz:
            return 0.0
        # Suma de importes de los capítulos raíz. El CI ya está incorporado en
        # el precio de cada partida (ver precio_con_ci / importe_en_padre).
        total = 0.0
        for hijo in raiz.hijos:
            total += self._importe_recursivo(hijo.codigo_hijo, self.codigo_raiz)
        return round(total, 2)

    # ---- Operaciones de edición -----------------------------------------

    def modificar_precio(self, codigo: str, nuevo_precio: float) -> None:
        """Cambia el precio unitario de un concepto hoja y recalcula.
        Lanza ValueError si el concepto tiene descomposición (precio calculado)."""
        c = self.conceptos.get(codigo)
        if c is None:
            raise ValueError(f"Concepto '{codigo}' no encontrado")
        if c.hijos:
            raise ValueError(
                f"'{codigo}' tiene descomposición — el precio es calculado y no se puede editar directamente"
            )
        c.precio = nuevo_precio
        c.precio_es_dato = True
        c._precio_bc3 = nuevo_precio

    def modificar_medicion(
        self, codigo_hijo: str, codigo_padre: str,
        indice_linea: int, campo: str, valor: float
    ) -> None:
        """Modifica un campo de una línea de medición existente."""
        c = self.conceptos.get(codigo_hijo)
        if c is None:
            raise ValueError(f"Concepto '{codigo_hijo}' no encontrado")
        med = c.mediciones.get(codigo_padre)
        if med is None or indice_linea >= len(med.lineas):
            raise ValueError(f"Línea de medición {indice_linea} no encontrada")
        ln = med.lineas[indice_linea]
        if campo == "n_uds":
            ln.n_uds = valor
        elif campo == "longitud":
            ln.longitud = valor
        elif campo == "anchura":
            ln.anchura = valor
        elif campo == "altura":
            ln.altura = valor
        elif campo == "comentario":
            ln.comentario = str(valor)
        else:
            raise ValueError(f"Campo '{campo}' no válido")

    def add_linea_medicion(
        self, codigo_hijo: str, codigo_padre: str,
        comentario: str = "", n_uds: float = 0,
        longitud: float = 0, anchura: float = 0, altura: float = 0,
    ) -> None:
        """Añade una línea de medición a una partida."""
        c = self.conceptos.get(codigo_hijo)
        if c is None:
            raise ValueError(f"Concepto '{codigo_hijo}' no encontrado")
        if codigo_padre not in c.mediciones:
            c.mediciones[codigo_padre] = Medicion()
        c.mediciones[codigo_padre].lineas.append(
            LineaMedicion(
                comentario=comentario, n_uds=n_uds,
                longitud=longitud, anchura=anchura, altura=altura,
            )
        )

    def eliminar_linea_medicion(
        self, codigo_hijo: str, codigo_padre: str, indice: int
    ) -> None:
        """Elimina una línea de medición."""
        c = self.conceptos.get(codigo_hijo)
        if c is None:
            raise ValueError(f"Concepto '{codigo_hijo}' no encontrado")
        med = c.mediciones.get(codigo_padre)
        if med is None or indice >= len(med.lineas):
            raise ValueError(f"Línea {indice} no encontrada")
        med.lineas.pop(indice)

    def add_partida(
        self, codigo_padre: str, codigo: str, unidad: str,
        resumen: str, precio: float = 0,
    ) -> None:
        """Añade una partida nueva a un capítulo."""
        padre = self.conceptos.get(codigo_padre)
        if padre is None:
            raise ValueError(f"Capítulo padre '{codigo_padre}' no encontrado")
        if self.conceptos.get(codigo):
            raise ValueError(f"Ya existe un concepto con código '{codigo}'")
        nueva = Concepto(
            codigo=codigo, unidad=unidad, resumen=resumen,
            precio=precio, tipo=TipoConcepto.PARTIDA,
            precio_es_dato=True,
        )
        nueva._precio_bc3 = precio
        self.add_concepto(nueva)
        # rendimiento=0 → cantidad=0: sin medición explícita, el importe es 0.
        # (cantidad es factor*rendimiento; no es un campo asignable.)
        # El usuario la fija luego editando la celda Cantidad o añadiendo líneas de medición.
        padre.hijos.append(Hijo(codigo_hijo=codigo, factor=1.0, rendimiento=0.0))

    def add_capitulo(
        self, codigo: str, resumen: str, codigo_padre: str | None = None,
    ) -> None:
        """Añade un capítulo. Si no se da padre, se añade a la raíz."""
        if self.conceptos.get(codigo):
            raise ValueError(f"Ya existe un concepto con código '{codigo}'")
        nuevo = Concepto(
            codigo=codigo, resumen=resumen,
            tipo=TipoConcepto.CAPITULO,
        )
        self.add_concepto(nuevo)
        destino = codigo_padre or self.codigo_raiz
        padre = self.conceptos.get(destino)
        if padre:
            padre.hijos.append(Hijo(codigo_hijo=codigo, factor=1.0, rendimiento=1.0))

    def eliminar_concepto(self, codigo: str, codigo_padre: str) -> None:
        """Elimina un concepto del padre indicado (no borra el concepto en sí,
        solo lo desvincula del padre para no romper otras referencias)."""
        padre = self.conceptos.get(codigo_padre)
        if padre is None:
            raise ValueError(f"Padre '{codigo_padre}' no encontrado")
        padre.hijos = [h for h in padre.hijos if h.codigo_hijo != codigo]

    def modificar_resumen(self, codigo: str, resumen: str) -> None:
        """Cambia el resumen/descripción de un concepto."""
        c = self.conceptos.get(codigo)
        if c is None:
            raise ValueError(f"Concepto '{codigo}' no encontrado")
        c.resumen = resumen

    def modificar_texto(self, codigo: str, texto: str) -> None:
        """Cambia la descripción larga (texto pliego) de un concepto."""
        c = self.conceptos.get(codigo)
        if c is None:
            raise ValueError(f"Concepto '{codigo}' no encontrado")
        c.texto = texto

    def cambiar_tipo(self, codigo: str, nuevo_tipo: str) -> None:
        """Cambia el tipo de un concepto entre 'capitulo' y 'partida'.

        La estructura de hijos no se modifica; solo cambia cómo se
        calcula el importe y cómo se muestra en la interfaz.
        """
        c = self.conceptos.get(codigo)
        if c is None:
            raise ValueError(f"Concepto '{codigo}' no encontrado")
        if nuevo_tipo == "capitulo":
            c.tipo = TipoConcepto.CAPITULO
            c._tipo_fiebdc = "5"  # type: ignore[attr-defined]
        elif nuevo_tipo == "partida":
            c.tipo = TipoConcepto.PARTIDA
            c._tipo_fiebdc = "6"  # type: ignore[attr-defined]
        else:
            raise ValueError(f"Tipo '{nuevo_tipo}' no válido. Use 'capitulo' o 'partida'")

    def cambiar_tipo_recurso(self, codigo: str, tipo_fiebdc: str) -> None:
        """Cambia el subtipo de un recurso unitario.

        tipo_fiebdc:  '1' MO  |  '2' Maquinaria  |  '3' Material  |  '4' Auxiliar
        """
        c = self.conceptos.get(codigo)
        if c is None:
            raise ValueError(f"Concepto '{codigo}' no encontrado")
        if tipo_fiebdc not in ("1", "2", "3", "4"):
            raise ValueError(f"Subtipo FIEBDC '{tipo_fiebdc}' no válido (1-4)")
        c._tipo_fiebdc = tipo_fiebdc  # type: ignore[attr-defined]

    def modificar_unidad(self, codigo: str, unidad: str) -> None:
        """Cambia la unidad de medida de un concepto."""
        c = self.conceptos.get(codigo)
        if c is None:
            raise ValueError(f"Concepto '{codigo}' no encontrado")
        c.unidad = unidad

    def modificar_codigo(self, codigo_viejo: str, codigo_nuevo: str) -> None:
        """Cambia el código de un concepto, actualizando todas las referencias."""
        if codigo_viejo == codigo_nuevo:
            return
        c = self.conceptos.get(codigo_viejo)
        if c is None:
            raise ValueError(f"Concepto '{codigo_viejo}' no encontrado")
        if self.conceptos.get(codigo_nuevo):
            raise ValueError(f"Ya existe un concepto con código '{codigo_nuevo}'")
        # Actualizar en el diccionario
        del self.conceptos[codigo_viejo]
        c.codigo = codigo_nuevo
        self.conceptos[codigo_nuevo] = c
        # Actualizar referencias en hijos de todos los conceptos
        for otro in self.conceptos.values():
            for h in otro.hijos:
                if h.codigo_hijo == codigo_viejo:
                    h.codigo_hijo = codigo_nuevo
        # Actualizar mediciones (las claves del dict son código padre)
        for otro in self.conceptos.values():
            if codigo_viejo in otro.mediciones:
                otro.mediciones[codigo_nuevo] = otro.mediciones.pop(codigo_viejo)
        # Actualizar raíz si era la raíz
        if self.codigo_raiz == codigo_viejo:
            self.codigo_raiz = codigo_nuevo

    def modificar_rendimiento(
        self, codigo_padre: str, codigo_hijo: str, rendimiento: float
    ) -> None:
        """Cambia el rendimiento de un hijo dentro de su padre."""
        padre = self.conceptos.get(codigo_padre)
        if padre is None:
            raise ValueError(f"Concepto padre '{codigo_padre}' no encontrado")
        for h in padre.hijos:
            if h.codigo_hijo == codigo_hijo:
                h.rendimiento = rendimiento
                return
        raise ValueError(f"Hijo '{codigo_hijo}' no encontrado en '{codigo_padre}'")

    def add_recurso(
        self, codigo_partida: str, codigo_recurso: str,
        rendimiento: float = 1.0, precio: float = 0.0,
        unidad: str = "", resumen: str = "", tipo_fiebdc: str = "3"
    ) -> None:
        """Añade un recurso unitario a la descomposición de una partida.

        Si el recurso no existe en el presupuesto, se crea como UNITARIO con los
        datos proporcionados.  Si ya existe como hijo de la partida, actualiza su
        rendimiento.  Si existe como concepto pero no está en la descomposición,
        lo enlaza.

        tipo_fiebdc: subtipo del recurso (1 MO, 2 maquinaria, 3 material,
        4 auxiliar). Se escribe explícito en el ~C al exportar para que Presto
        no tenga que adivinar la naturaleza. Por defecto 3 (material), igual que
        muestra la UI; el usuario puede cambiarlo en la columna "Tipo".
        """
        partida = self.conceptos.get(codigo_partida)
        if partida is None:
            raise ValueError(f"Partida '{codigo_partida}' no encontrada")
        if tipo_fiebdc not in ("1", "2", "3", "4"):
            tipo_fiebdc = "3"
        # Crear el recurso si no existe
        if not self.conceptos.get(codigo_recurso):
            nuevo = Concepto(
                codigo=codigo_recurso,
                unidad=unidad,
                resumen=resumen or codigo_recurso,
                precio=precio,
                tipo=TipoConcepto.UNITARIO,
                precio_es_dato=True,
            )
            nuevo._precio_bc3 = precio  # type: ignore[attr-defined]
            nuevo._tipo_fiebdc = tipo_fiebdc  # type: ignore[attr-defined]
            self.add_concepto(nuevo)
        # Si ya está en la descomposición, sólo actualiza rendimiento
        for h in partida.hijos:
            if h.codigo_hijo == codigo_recurso:
                h.rendimiento = rendimiento
                return
        # Enlazar como nuevo hijo
        partida.hijos.append(Hijo(codigo_hijo=codigo_recurso, factor=1.0, rendimiento=rendimiento))
        partida.precio_es_dato = False

    def reordenar_recurso(
        self, codigo_partida: str, codigo_recurso: str, antes_de: Optional[str] = None
    ) -> None:
        """Mueve un recurso a otra posición dentro de la misma descomposición."""
        partida = self.conceptos.get(codigo_partida)
        if partida is None:
            raise ValueError(f"Partida '{codigo_partida}' no encontrada")
        hijo_obj = None
        for i, h in enumerate(partida.hijos):
            if h.codigo_hijo == codigo_recurso:
                hijo_obj = partida.hijos.pop(i)
                break
        if hijo_obj is None:
            raise ValueError(f"Recurso '{codigo_recurso}' no encontrado en '{codigo_partida}'")
        if antes_de is None:
            partida.hijos.append(hijo_obj)
        else:
            idx = next(
                (i for i, h in enumerate(partida.hijos) if h.codigo_hijo == antes_de),
                len(partida.hijos)
            )
            partida.hijos.insert(idx, hijo_obj)

    def reordenar_medicion(
        self, codigo_hijo: str, codigo_padre: str, from_idx: int, to_idx: int
    ) -> None:
        """Mueve una línea de medición de from_idx a to_idx."""
        c = self.conceptos.get(codigo_hijo)
        if c is None:
            raise ValueError(f"Concepto '{codigo_hijo}' no encontrado")
        med = c.mediciones.get(codigo_padre)
        if med is None:
            raise ValueError(f"Sin medición de '{codigo_hijo}' en '{codigo_padre}'")
        if not (0 <= from_idx < len(med.lineas)):
            raise ValueError(f"Índice {from_idx} fuera de rango")
        linea = med.lineas.pop(from_idx)
        to_idx = min(max(to_idx, 0), len(med.lineas))
        med.lineas.insert(to_idx, linea)

    def eliminar_recurso(self, codigo_partida: str, codigo_recurso: str) -> None:
        """Desvincula un recurso de la descomposición de una partida.
        No elimina el concepto recurso del presupuesto (puede usarse en otros sitios)."""
        partida = self.conceptos.get(codigo_partida)
        if partida is None:
            raise ValueError(f"Partida '{codigo_partida}' no encontrada")
        antes = len(partida.hijos)
        partida.hijos = [h for h in partida.hijos if h.codigo_hijo != codigo_recurso]
        if len(partida.hijos) == antes:
            raise ValueError(f"Recurso '{codigo_recurso}' no encontrado en '{codigo_partida}'")

    def mover_concepto(
        self, codigo: str, padre_origen: str,
        padre_destino: str, antes_de: Optional[str] = None
    ) -> None:
        """Mueve un concepto de su padre origen al padre destino.

        antes_de=None  → se añade al final.
        antes_de='X'   → se inserta antes del hijo con codigo_hijo=='X'.

        Lanza ValueError si:
          - algún padre no existe
          - el concepto no está en padre_origen
          - se intentaría crear un ciclo (padre_destino desciende de codigo)
          - el concepto ya existe en padre_destino (usar clonar_concepto para duplicar)
        """
        origen = self.conceptos.get(padre_origen)
        destino = self.conceptos.get(padre_destino)
        if origen is None:
            raise ValueError(f"Padre origen '{padre_origen}' no encontrado")
        if destino is None:
            raise ValueError(f"Padre destino '{padre_destino}' no encontrado")
        if padre_destino == codigo:
            raise ValueError("No se puede mover un concepto dentro de sí mismo")
        if self._es_descendiente(padre_destino, codigo):
            raise ValueError(
                f"No se puede mover '{codigo}' dentro de uno de sus propios descendientes"
            )
        # Impedir mover a un capítulo donde el concepto ya está presente
        if padre_destino != padre_origen:
            if any(h.codigo_hijo == codigo for h in destino.hijos):
                raise ValueError(
                    f"'{codigo}' ya existe en '{padre_destino}'. "
                    f"Para duplicarlo usa Copiar/Pegar."
                )
        # Extraer el Hijo del origen
        hijo_obj: Optional[Hijo] = None
        for i, h in enumerate(origen.hijos):
            if h.codigo_hijo == codigo:
                hijo_obj = origen.hijos.pop(i)
                break
        if hijo_obj is None:
            raise ValueError(f"'{codigo}' no encontrado en '{padre_origen}'")
        # Insertar en destino
        if antes_de is None:
            destino.hijos.append(hijo_obj)
        else:
            idx = next(
                (i for i, h in enumerate(destino.hijos) if h.codigo_hijo == antes_de),
                len(destino.hijos)
            )
            destino.hijos.insert(idx, hijo_obj)
        # Transferir la medición al nuevo padre (la clave del dict es el código del padre)
        if padre_destino != padre_origen:
            concepto = self.conceptos.get(codigo)
            if concepto:
                med = concepto.mediciones.pop(padre_origen, None)
                if med is not None:
                    concepto.mediciones[padre_destino] = med

    def copiar_concepto(
        self, codigo: str, padre_destino: str, antes_de: Optional[str] = None
    ) -> None:
        """Añade codigo como hijo de padre_destino sin quitarlo de su padre original.

        Permite que el mismo concepto (partida, capítulo, unitario) aparezca en
        varios lugares del árbol, que es el comportamiento estándar de FIEBDC-3.
        La medición en el nuevo padre empieza vacía (0).

        Lanza ValueError si:
          - el concepto o el destino no existen
          - el concepto ya es hijo de padre_destino
          - se intentaría crear un ciclo (padre_destino desciende de codigo)
        """
        c = self.conceptos.get(codigo)
        if c is None:
            raise ValueError(f"Concepto '{codigo}' no encontrado")
        destino = self.conceptos.get(padre_destino)
        if destino is None:
            raise ValueError(f"Destino '{padre_destino}' no encontrado")
        if codigo == padre_destino:
            raise ValueError("No se puede pegar un concepto dentro de sí mismo")
        if self._es_descendiente(padre_destino, codigo):
            raise ValueError(
                f"No se puede pegar '{codigo}' dentro de uno de sus propios descendientes"
            )
        if any(h.codigo_hijo == codigo for h in destino.hijos):
            raise ValueError(
                f"'{codigo}' ya existe en '{padre_destino}'. "
                f"Para moverlo usa arrastrar y soltar."
            )
        nuevo = Hijo(codigo_hijo=codigo, factor=1.0, rendimiento=0.0)  # cantidad=0
        if antes_de is None:
            destino.hijos.append(nuevo)
        else:
            idx = next(
                (i for i, h in enumerate(destino.hijos) if h.codigo_hijo == antes_de),
                len(destino.hijos)
            )
            destino.hijos.insert(idx, nuevo)

    def _es_descendiente(self, candidato: str, raiz: str) -> bool:
        """Devuelve True si candidato es hijo (directo o indirecto) de raiz."""
        c = self.conceptos.get(raiz)
        if c is None:
            return False
        for h in c.hijos:
            if h.codigo_hijo == candidato:
                return True
            if self._es_descendiente(candidato, h.codigo_hijo):
                return True
        return False

    def _importe_recursivo(self, codigo: str, codigo_padre: str) -> float:
        """Importe de un concepto. El CI ya va incluido en el precio de cada
        partida (ver precio_con_ci), así que aquí solo se suma de abajo arriba."""
        concepto = self.conceptos.get(codigo)
        if concepto is None:
            return 0.0
        if concepto.tipo == TipoConcepto.CAPITULO and concepto.hijos:
            # Importe de capítulo = SIEMPRE suma de importes de sus hijos.
            # No se respeta el "precio congelado" del archivo (Presto 8.8) para
            # garantizar que el PEM sea determinista: editar y revertir un
            # valor devuelve al PEM exacto del estado inicial.
            total = 0.0
            for hijo in concepto.hijos:
                total += self._importe_recursivo(hijo.codigo_hijo, codigo)
            return _redondea(total, self.dec_importe) if self.redondeo_activo else round(total, 2)
        # Partida: precio (con CI) × medición.
        # Si la medición es 0 (o no hay medición), el importe es 0 — sin excepciones.
        return self.importe_en_padre(codigo, codigo_padre)
