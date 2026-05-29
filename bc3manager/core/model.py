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
from enum import Enum
from typing import Optional


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
                # Heurística: raíz o código con # sin unidad → capítulo
                if c.es_raiz_obra or (c.codigo.endswith("#") and not c.unidad):
                    c.tipo = TipoConcepto.CAPITULO
                elif c.hijos:
                    # Con descomposición y unidad → partida; sin unidad → capítulo
                    c.tipo = TipoConcepto.PARTIDA if c.unidad else TipoConcepto.CAPITULO
                else:
                    c.tipo = TipoConcepto.UNITARIO

    # ---- Recálculo de precios -------------------------------------------

    def recalcular(self) -> None:
        """
        Recalcula el precio de todos los conceptos con descomposición,
        de abajo hacia arriba. Los conceptos hoja conservan su precio de dato.
        """
        memo: dict[str, float] = {}
        en_proceso: set[str] = set()

        def precio_de(codigo: str) -> float:
            if codigo in memo:
                return memo[codigo]
            concepto = self.conceptos.get(codigo)
            if concepto is None:
                return 0.0
            # Para capítulos (código con #): respetar precio del BC3 si existe.
            # Para conceptos hoja (MO, MAQ, MAT): recalcular siempre desde hijos
            # o usar precio dato si no tienen hijos.
            precio_bc3 = getattr(concepto, '_precio_bc3', None)
            es_capitulo = '#' in codigo
            if precio_bc3 is not None and precio_bc3 > 0 and es_capitulo:
                memo[codigo] = precio_bc3
                concepto.precio = precio_bc3
                concepto.precio_es_dato = True
                return precio_bc3
            # Concepto hoja sin precio: 0
            if not concepto.hijos:
                memo[codigo] = concepto.precio
                return concepto.precio
            # Protección contra ciclos
            if codigo in en_proceso:
                memo[codigo] = concepto.precio
                return concepto.precio
            en_proceso.add(codigo)
            total = 0.0
            for hijo in concepto.hijos:
                total += precio_de(hijo.codigo_hijo) * hijo.cantidad
            en_proceso.discard(codigo)
            total = round(total, 4)
            concepto.precio = total
            concepto.precio_es_dato = False
            memo[codigo] = total
            return total

        for codigo in self.conceptos:
            precio_de(codigo)

    # ---- Importe (precio * medición) ------------------------------------

    def medicion_total(self, codigo_hijo: str, codigo_padre: str) -> float:
        """Medición de un concepto dentro de un padre concreto."""
        concepto = self.conceptos.get(codigo_hijo)
        if concepto is None:
            return 0.0
        med = concepto.mediciones.get(codigo_padre)
        return med.total if med else 0.0

    def importe_en_padre(self, codigo_hijo: str, codigo_padre: str) -> float:
        """Importe de una línea hijo dentro de su padre: precio * medición."""
        concepto = self.conceptos.get(codigo_hijo)
        if concepto is None:
            return 0.0
        med = self.medicion_total(codigo_hijo, codigo_padre)
        # Si no hay medición explícita, se usa la cantidad de la descomposición
        if med == 0.0:
            padre = self.conceptos.get(codigo_padre)
            if padre:
                for h in padre.hijos:
                    if h.codigo_hijo == codigo_hijo:
                        med = h.cantidad
                        break
        return round(concepto.precio * med, 2)

    def presupuesto_total(self) -> float:
        """Importe total del presupuesto (importe del concepto raíz)."""
        if not self.codigo_raiz:
            return 0.0
        raiz = self.conceptos.get(self.codigo_raiz)
        if not raiz:
            return 0.0
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
        # cantidad=0.0: sin medición explícita, el importe es 0.
        # El usuario la fija luego editando la celda Cantidad o añadiendo líneas de medición.
        padre.hijos.append(Hijo(codigo_hijo=codigo, factor=1.0, rendimiento=1.0, cantidad=0.0))

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
        unidad: str = "", resumen: str = ""
    ) -> None:
        """Añade un recurso unitario a la descomposición de una partida.

        Si el recurso no existe en el presupuesto, se crea como UNITARIO con los
        datos proporcionados.  Si ya existe como hijo de la partida, actualiza su
        rendimiento.  Si existe como concepto pero no está en la descomposición,
        lo enlaza.
        """
        partida = self.conceptos.get(codigo_partida)
        if partida is None:
            raise ValueError(f"Partida '{codigo_partida}' no encontrada")
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
        nuevo = Hijo(codigo_hijo=codigo, rendimiento=1.0, cantidad=0.0)
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
        concepto = self.conceptos.get(codigo)
        if concepto is None:
            return 0.0
        if concepto.tipo == TipoConcepto.CAPITULO and concepto.hijos:
            # Los capítulos con precio precalculado en BC3 (Presto 8.8) conservan
            # su precio original — es lo que el fichero dice que vale el capítulo.
            if concepto.precio_es_dato and concepto.precio > 0:
                return round(concepto.precio, 2)
            total = 0.0
            for hijo in concepto.hijos:
                total += self._importe_recursivo(hijo.codigo_hijo, codigo)
            return round(total, 2)
        # Partida: precio × medición.
        # Si la medición es 0 (o no hay medición), el importe es 0 — sin excepciones.
        return self.importe_en_padre(codigo, codigo_padre)
