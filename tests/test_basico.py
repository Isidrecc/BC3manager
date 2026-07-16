"""
Batería de tests de BC3Manager.

Ejecutar:  python tests/test_basico.py        (no requiere pytest)
           (desde la RAÍZ del repo; importa bc3manager por ruta relativa)

Diseño completo en docs/auditoria/bateria-tests.md. Cuatro familias:

  1. PARAMÉTRICOS (`param_*`) — la MISMA comprobación sobre CADA archivo del
     corpus real. Son invariantes que cualquier BC3 debe cumplir: lectura sin
     errores, integridad de referencias, y round-trip determinista
     (leer→escribir→releer no pierde ni altera datos). Cazan los problemas
     conocidos (registro-bugs.md) en todos los archivos a la vez.

  2. LÍNEA BASE (`param_baseline_*`) — fija el PEM y el nº de discrepancias de
     validación ACTUALES de cada archivo, para detectar regresiones. OJO: que un
     archivo real traiga discrepancias archivo-vs-calculado NO es un fallo de la
     batería; es un hallazgo del propio archivo (precios precalculados que no
     cuadran con su desglose). Se documentan y se investigan aparte.

  3. DIRIGIDOS (`test_alqueria_*`, etc.) — valores EXACTOS clavados contra el
     informe real de Presto (CI por partida, redondeos, partidas alzadas...).
     Blindan los invariantes 5-7 de CLAUDE.md. Si se rompen, NO los relajes sin
     entender por qué: están verificados contra el desglose de Presto.

  4. EDICIÓN Y AUTOGUARDADO (`test_edit_*`) — operaciones del modelo + el ciclo
     guardar→reabrir y deshacer/rehacer (la capa que antes no tenía tests).

Los .bc3 del corpus viven junto a este archivo. Los tests que dependen de un
archivo ausente se SALTAN avisando (no cuentan como OK silencioso).
"""

from __future__ import annotations

import math
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bc3manager.io.lector import leer_bc3
from bc3manager.io.escritor import escribir_bc3
from bc3manager.core.model import Presupuesto, TipoConcepto


TESTS_DIR = os.path.dirname(os.path.abspath(__file__))


def _ruta(nombre: str) -> str:
    return os.path.join(TESTS_DIR, nombre)


class Saltado(Exception):
    """El test no aplica a este entorno (p.ej. falta su archivo)."""


# ===========================================================================
# CORPUS — archivos reales y su línea base
# ===========================================================================
# PEM y nº de discrepancias capturados el 2026-06-14 con `python tests/test_basico.py`.
# Sirven de regresión: si cambian, algo en el cálculo o en la validación cambió.
# `disc_precios` > 0 en los archivos de Andratx son HALLAZGOS conocidos (el PEM
# del archivo no cuadra con el recalculado de abajo arriba); ver bateria-tests.md
# y registro-bugs.md. No se "arreglan" relajando el test: se investigan aparte.
CORPUS = [
    {"archivo": "Test_Alqueria.bc3",      "programa": "Presto 20 (FIEBDC-2016)",
     "tiene_k": True, "ci": 0.06,   "pem": 9073347.54, "disc_precios": 0,  "disc_mediciones": 0},
    {"archivo": "Test_SONFONT.bc3",       "programa": "Presto 8.8",
     "tiene_k": True, "ci": 0.0,    "pem": 602630.88,  "disc_precios": 0,  "disc_mediciones": 0},
    {"archivo": "Test_REDONDEO.bc3",      "programa": "Presto 8.8 (decimales extremos)",
     "tiene_k": True, "ci": 0.0,    "pem": 602676.04,  "disc_precios": 0,  "disc_mediciones": 0},
    {"archivo": "Test_PEBTAndratx.bc3",   "programa": "Presto 8.8 (CI 6%)",
     "tiene_k": True, "ci": 0.06,   "pem": 90710.90,   "disc_precios": 29, "disc_mediciones": 0},
    {"archivo": "Test_PEBT_AC_Andratx.bc3", "programa": "Presto 8.8 (CI 6%)",
     "tiene_k": True, "ci": 0.06,   "pem": 5700.19,    "disc_precios": 3,  "disc_mediciones": 0},
    {"archivo": "Test_XarxaAndratx.bc3",  "programa": "Presto 8.8 (CI -0,7%)",
     "tiene_k": True, "ci": -0.007,  "pem": 3085573.51, "disc_precios": 35, "disc_mediciones": 0},
]


def _corpus_presentes() -> list[dict]:
    return [m for m in CORPUS if os.path.exists(_ruta(m["archivo"]))]


class _Ctx:
    """Carga un archivo del corpus UNA vez y hace su round-trip, para que las
    pruebas paramétricas no relean ni reescriban en cada comprobación."""

    def __init__(self, meta: dict) -> None:
        self.meta = meta
        self.ruta = _ruta(meta["archivo"])
        self.p = leer_bc3(self.ruta)                  # P1: lectura sin errores
        with tempfile.NamedTemporaryFile(suffix=".bc3", delete=False) as tmp:
            self.salida = tmp.name
        escribir_bc3(self.p, self.salida)
        self.p2 = leer_bc3(self.salida)               # round-trip

    def cleanup(self) -> None:
        try:
            os.unlink(self.salida)
        except OSError:
            pass


def _refs_rotas(p: Presupuesto) -> list[tuple]:
    """Hijos (~D) o padres de medición (~M) que apuntan a códigos inexistentes."""
    rotas = []
    for c in p.conceptos.values():
        for h in c.hijos:
            if h.codigo_hijo not in p.conceptos:
                rotas.append(("hijo", c.codigo, h.codigo_hijo))
        for padre in c.mediciones:
            if padre != "__sin_padre__" and padre not in p.conceptos:
                rotas.append(("medicion", padre, c.codigo))
    return rotas


def _n_mediciones(p: Presupuesto) -> int:
    return sum(len(c.mediciones) for c in p.conceptos.values())


# ===========================================================================
# FAMILIA 1 — PARAMÉTRICOS (se ejecutan sobre CADA archivo del corpus)
# ===========================================================================

def param_lectura_ok(ctx: _Ctx) -> None:
    """P1+P2: el archivo se lee, tiene conceptos y una raíz válida en el árbol."""
    assert len(ctx.p.conceptos) > 0, "no se leyó ningún concepto"
    assert ctx.p.codigo_raiz, "no se detectó la obra raíz"
    assert ctx.p.codigo_raiz in ctx.p.conceptos, "la raíz no está entre los conceptos"


def param_sin_referencias_rotas(ctx: _Ctx) -> None:
    """P3: ningún ~D/~M apunta a un código que no existe (alias #, sinónimos)."""
    rotas = _refs_rotas(ctx.p)
    assert not rotas, f"{len(rotas)} referencias rotas, p.ej. {rotas[:3]}"


def param_todo_clasificado(ctx: _Ctx) -> None:
    """P16: ningún concepto queda sin clasificar (TipoConcepto.OTRO)."""
    otros = [c.codigo for c in ctx.p.conceptos.values() if c.tipo == TipoConcepto.OTRO]
    assert not otros, f"{len(otros)} conceptos sin clasificar, p.ej. {otros[:3]}"


def param_numeros_sanos(ctx: _Ctx) -> None:
    """P15: todos los precios son finitos y el PEM es finito y > 0."""
    for c in ctx.p.conceptos.values():
        assert math.isfinite(c.precio), f"{c.codigo} tiene precio no finito ({c.precio})"
    pem = ctx.p.presupuesto_total()
    assert math.isfinite(pem) and pem > 0, f"PEM no sano: {pem}"


def param_recalculo_determinista(ctx: _Ctx) -> None:
    """P7: recalcular dos veces da el mismo PEM (sin estado oculto)."""
    pem1 = ctx.p.presupuesto_total()
    ctx.p.recalcular()
    pem2 = ctx.p.presupuesto_total()
    assert abs(pem1 - pem2) < 0.01, f"PEM no determinista: {pem1} != {pem2}"


def param_editar_revertir_devuelve_pem(ctx: _Ctx) -> None:
    """P7 (fuerte / invariante 2): editar un precio hoja y revertirlo devuelve
    el PEM exacto. Usa una copia fresca para no contaminar el resto de pruebas."""
    p = leer_bc3(ctx.ruta)
    leaf = next((c for c in p.conceptos.values()
                 if c.tipo == TipoConcepto.UNITARIO and not c.hijos and c.precio), None)
    if leaf is None:
        raise Saltado("sin recurso hoja con precio")
    pem0 = p.presupuesto_total()
    original = leaf.precio
    p.modificar_precio(leaf.codigo, original + 10.0)
    p.recalcular()
    p.modificar_precio(leaf.codigo, original)
    p.recalcular()
    assert abs(p.presupuesto_total() - pem0) < 0.01, (
        f"editar+revertir no devolvió el PEM: {pem0} -> {p.presupuesto_total()}"
    )


def param_roundtrip_estructura(ctx: _Ctx) -> None:
    """P8: leer→escribir→releer conserva nº de conceptos y de mediciones."""
    assert len(ctx.p2.conceptos) == len(ctx.p.conceptos), (
        f"conceptos {len(ctx.p.conceptos)} -> {len(ctx.p2.conceptos)}"
    )
    assert _n_mediciones(ctx.p2) == _n_mediciones(ctx.p), (
        f"mediciones {_n_mediciones(ctx.p)} -> {_n_mediciones(ctx.p2)}"
    )
    assert not _refs_rotas(ctx.p2), "el archivo reescrito tiene referencias rotas"


def param_roundtrip_pem(ctx: _Ctx) -> None:
    """P9: el PEM sobrevive al round-trip (no se pierde importe al guardar)."""
    pem1, pem2 = ctx.p.presupuesto_total(), ctx.p2.presupuesto_total()
    assert abs(pem1 - pem2) < 0.01, f"PEM cambió al guardar: {pem1:,.2f} -> {pem2:,.2f}"


def param_roundtrip_idempotente(ctx: _Ctx) -> None:
    """P11: un segundo round-trip ya no cambia nada (sin drift acumulativo)."""
    with tempfile.NamedTemporaryFile(suffix=".bc3", delete=False) as tmp:
        salida3 = tmp.name
    try:
        escribir_bc3(ctx.p2, salida3)
        p3 = leer_bc3(salida3)
    finally:
        os.unlink(salida3)
    assert len(p3.conceptos) == len(ctx.p2.conceptos), "drift en nº de conceptos"
    assert abs(p3.presupuesto_total() - ctx.p2.presupuesto_total()) < 0.01, "drift en PEM"


def param_roundtrip_no_empeora_validacion(ctx: _Ctx) -> None:
    """P10: guardar no debe AUMENTAR las discrepancias de validación."""
    v1 = ctx.p.validar_completo()
    v2 = ctx.p2.validar_completo()
    assert len(v2["precios"]) <= len(v1["precios"]), (
        f"guardar empeoró los precios: {len(v1['precios'])} -> {len(v2['precios'])}"
    )
    assert len(v2["mediciones"]) <= len(v1["mediciones"]), (
        f"guardar empeoró las mediciones: {len(v1['mediciones'])} -> {len(v2['mediciones'])}"
    )


def param_conserva_k(ctx: _Ctx) -> None:
    """P12: el ~K sobrevive al round-trip (coeficientes y decimales del campo 1).
    OJO: DN/DD viven solo en el campo 3, que el escritor aún no emite (bug nº 5);
    por eso aquí NO se comprueban dec_num/dec_dim."""
    if not ctx.meta["tiene_k"]:
        raise Saltado("archivo sin ~K")
    a, b = ctx.p, ctx.p2
    assert b.redondeo_activo, "se perdió el ~K al guardar"
    for attr in ("dec_parcial", "dec_cantmed", "dec_cantrend", "dec_subtotal",
                 "dec_natural", "dec_precio_partida", "dec_precio_capitulo"):
        assert getattr(a, attr) == getattr(b, attr), (
            f"{attr}: {getattr(a, attr)} -> {getattr(b, attr)}"
        )
    for attr in ("ci_pct", "gg_pct", "bi_pct", "baja_pct", "iva_pct"):
        assert abs(getattr(a, attr) - getattr(b, attr)) < 1e-9, (
            f"{attr}: {getattr(a, attr)} -> {getattr(b, attr)}"
        )


def param_conserva_version(ctx: _Ctx) -> None:
    """P13: la versión de formato del ~V sobrevive al round-trip."""
    assert ctx.p2.version_formato == ctx.p.version_formato, (
        f"versión {ctx.p.version_formato!r} -> {ctx.p2.version_formato!r}"
    )


def param_codificacion_roundtrip(ctx: _Ctx) -> None:
    """P17: los caracteres especiales (acentos, ñ, ç, €) sobreviven al guardar."""
    objetivo = next(
        (c for c in ctx.p.conceptos.values()
         if c.resumen and any(ord(ch) > 127 for ch in c.resumen)),
        None,
    )
    if objetivo is None:
        raise Saltado("sin caracteres especiales que comprobar")
    c2 = ctx.p2.get(objetivo.codigo)
    assert c2 is not None and c2.resumen == objetivo.resumen, (
        f"{objetivo.codigo}: {objetivo.resumen!r} -> {c2.resumen if c2 else None!r}"
    )


def param_baseline_pem(ctx: _Ctx) -> None:
    """LÍNEA BASE: el PEM coincide con el valor congelado del corpus (regresión)."""
    pem = ctx.p.presupuesto_total()
    assert abs(pem - ctx.meta["pem"]) < 0.01, (
        f"PEM cambió respecto a la línea base: {pem:,.2f} (esperado {ctx.meta['pem']:,.2f})"
    )


def param_baseline_discrepancias(ctx: _Ctx) -> None:
    """LÍNEA BASE: el nº de discrepancias de validación es el conocido (regresión).
    Un cambio aquí significa que la validación detecta MÁS o MENOS que antes."""
    v = ctx.p.validar_completo()
    assert len(v["precios"]) == ctx.meta["disc_precios"], (
        f"discrepancias de precio: {len(v['precios'])} (línea base {ctx.meta['disc_precios']})"
    )
    assert len(v["mediciones"]) == ctx.meta["disc_mediciones"], (
        f"discrepancias de medición: {len(v['mediciones'])} (línea base {ctx.meta['disc_mediciones']})"
    )


# ===========================================================================
# FAMILIA 3 — DIRIGIDOS (valores exactos clavados; un archivo concreto)
# ===========================================================================

def test_validacion_detecta_discrepancia():
    """La validación debe detectar un precio del ~C que no cuadra con su
    descomposición. Se fuerza un _precio_bc3 incoherente en una partida real."""
    ruta = _ruta("Test_Alqueria.bc3")
    if not os.path.exists(ruta):
        raise Saltado("falta Test_Alqueria.bc3")
    p = leer_bc3(ruta)
    objetivo = next((c for c in p.conceptos.values()
                     if c.tipo == TipoConcepto.PARTIDA and c.hijos and getattr(c, "_precio_bc3", 0)),
                    None)
    assert objetivo is not None, "no se encontró partida con descomposición y precio de archivo"
    objetivo._precio_bc3 = (objetivo._precio_bc3 or 1) * 10 + 999.99
    disc = p.validar_precios_cargados()
    assert any(d["codigo"] == objetivo.codigo for d in disc), (
        f"no se detectó la discrepancia forzada en {objetivo.codigo}"
    )


def test_lineas_porcentaje_medios_auxiliares():
    """Las líneas de porcentaje (%MA = medios auxiliares) se aplican sobre el
    acumulado de la descomposición, NO como precio×rendimiento.
      DEM.01.01: (2,16 + 8,28) × 1,07, redondeando cada subtotal = 11,17
      MOV.02.01: (21,60×0,08 + 55,23×0,155) × 1,07 = 11,01
    """
    ruta = _ruta("Test_SONFONT.bc3")
    if not os.path.exists(ruta):
        raise Saltado("falta Test_SONFONT.bc3")
    p = leer_bc3(ruta)
    assert Presupuesto.es_porcentaje(p.get("%MA.7"))
    assert p.redondeo_activo, "El ~K debe activar el redondeo a 2 decimales"
    assert p.get("DEM.01.01").precio == 11.17, (
        f"DEM.01.01 = {p.get('DEM.01.01').precio}, esperado 11.17 (Presto)"
    )
    assert p.get("MOV.02.01").precio == 11.01, (
        f"MOV.02.01 = {p.get('MOV.02.01').precio}, esperado 11.01 (Presto)"
    )
    for cod, c in p.conceptos.items():
        if c.tipo == TipoConcepto.PARTIDA and c.hijos:
            arch = getattr(c, "_precio_bc3", None)
            if arch and arch > 0:
                assert abs(arch - c.precio) < 0.02, f"{cod}: archivo={arch} calc={c.precio}"


def test_redondeos_k_distintos():
    """Lee los decimales del ~K (cada parámetro distinto) y reproduce EXACTAMENTE
    los precios e importes del archivo de Presto, incluido el PEM."""
    ruta = _ruta("Test_REDONDEO.bc3")
    if not os.path.exists(ruta):
        raise Saltado("falta Test_REDONDEO.bc3")
    p = leer_bc3(ruta)
    assert p.redondeo_activo
    assert p.dec_subtotal == 7, f"DecImp={p.dec_subtotal}"
    assert p.dec_precio_partida == 5, f"DecPar={p.dec_precio_partida}"
    assert p.dec_precio_capitulo == 4, f"Dec={p.dec_precio_capitulo}"
    assert p.dec_cantrend == 3, f"DecCantRend={p.dec_cantrend}"
    for cod, c in p.conceptos.items():
        if c.tipo == TipoConcepto.PARTIDA and c.hijos:
            arch = getattr(c, "_precio_bc3", None)
            if arch and arch > 0:
                assert abs(arch - c.precio) < 0.0001, f"{cod}: archivo={arch} calc={c.precio}"
    comp = p.comparar_importes_archivo()
    assert abs(comp["diferencia_pem"]) < 0.01, (
        f"PEM archivo={comp['pem_archivo']} calc={comp['pem_calculado']}"
    )


def test_rendimiento_cero_se_conserva():
    """Un rendimiento 0 en el ~D (partida no medida en ese capítulo) se conserva
    como 0, no se convierte en 1."""
    ruta = _ruta("Test_SONFONT.bc3")
    if not os.path.exists(ruta):
        raise Saltado("falta Test_SONFONT.bc3")
    p = leer_bc3(ruta)
    c01 = p.get("01#")
    ceros = {h.codigo_hijo for h in c01.hijos if h.cantidad == 0}
    assert {"MOV.03.03", "HID.01.02", "HID.02.01", "EST.01.01"} <= ceros, (
        f"Se perdieron los ceros: {ceros}"
    )


def test_export_estructura_presto():
    """El BC3 exportado imita la estructura de Presto para que NO reclasifique las
    partidas: ~C de partida pegado a su ~D, ~M con posición, y tipos FIEBDC de
    recurso correctos (la partida/capítulo es 0 = sin clasificar, por norma)."""
    ruta = _ruta("Test_SONFONT.bc3")
    if not os.path.exists(ruta):
        raise Saltado("falta Test_SONFONT.bc3")
    p = leer_bc3(ruta)
    with tempfile.NamedTemporaryFile(suffix=".bc3", delete=False) as tmp:
        salida = tmp.name
    try:
        escribir_bc3(p, salida)
        with open(salida, "rb") as f:
            texto = f.read().decode("cp1252", errors="replace")
    finally:
        os.unlink(salida)
    lineas = [ln for ln in texto.splitlines() if ln.startswith("~")]
    idx_c = next(i for i, ln in enumerate(lineas) if ln.startswith("~C|MOV.02.01|"))
    assert lineas[idx_c + 1].startswith("~D|MOV.02.01|"), (
        "El ~D de la partida debe ir justo tras su ~C; si no, Presto la reclasifica."
    )
    m_mov = next(ln for ln in lineas if ln.startswith("~M|01#\\MOV.02.01|"))
    assert m_mov.split("|")[2].strip("\\").strip() != "", f"~M sin posición: {m_mov}"

    def tipo_de(codigo):
        ln = next(l for l in lineas if l.startswith(f"~C|{codigo}|"))
        return ln.split("|")[6]
    assert tipo_de("MAQ.RET.10") == "2"   # maquinaria
    assert tipo_de("MO.006") == "1"       # mano de obra
    assert tipo_de("MT.GAV") == "3"       # material
    assert tipo_de("MOV.02.01") == "0"    # partida -> sin clasificar (estándar)
    assert tipo_de("01#") == "0"          # capítulo -> sin clasificar
    assert tipo_de("SF##") == "0"         # obra raíz -> sin clasificar


def test_presto88_sin_ci_sigue_exacto():
    """Un archivo sin CI en el ~K (ci_pct=0) no aplica recargo y el PEM cuadra."""
    ruta = _ruta("Test_SONFONT.bc3")
    if not os.path.exists(ruta):
        raise Saltado("falta Test_SONFONT.bc3")
    p = leer_bc3(ruta)
    assert p.ci_pct == 0.0
    arch = p.get(p.codigo_raiz)._precio_bc3
    if arch:
        assert abs(p.presupuesto_total() - arch) < 0.01


def test_round_trip_conserva_redondeos_k():
    """Al escribir se emite el ~K, de modo que al reabrir se conserva la
    configuración de redondeo y el PEM se recalcula igual."""
    ruta = _ruta("Test_REDONDEO.bc3")
    if not os.path.exists(ruta):
        raise Saltado("falta Test_REDONDEO.bc3")
    p1 = leer_bc3(ruta)
    pem1 = p1.presupuesto_total()
    with tempfile.NamedTemporaryFile(suffix=".bc3", delete=False) as tmp:
        salida = tmp.name
    try:
        escribir_bc3(p1, salida)
        p2 = leer_bc3(salida)
        assert p2.redondeo_activo, "El archivo escrito debe incluir ~K"
        assert p2.dec_subtotal == p1.dec_subtotal
        assert p2.dec_precio_partida == p1.dec_precio_partida
        assert p2.dec_precio_capitulo == p1.dec_precio_capitulo
        assert p2.dec_cantrend == p1.dec_cantrend
        assert abs(p2.presupuesto_total() - pem1) < 0.01
    finally:
        os.unlink(salida)


# ---- Regresión de costes indirectos (CI) y redondeos: Test_Alqueria.bc3 ----
ALQUERIA = _ruta("Test_Alqueria.bc3")


def test_alqueria_coeficientes_del_registro_K():
    """CI/GG/BI/IVA se leen del campo 2 del ~K (no de un concepto %CI)."""
    if not os.path.exists(ALQUERIA):
        raise Saltado("falta Test_Alqueria.bc3")
    p = leer_bc3(ALQUERIA)
    assert abs(p.ci_pct - 0.06) < 1e-9
    assert abs(p.gg_pct - 0.13) < 1e-9
    assert abs(p.bi_pct - 0.06) < 1e-9
    assert abs(p.iva_pct - 0.21) < 1e-9


def test_alqueria_decimales_del_campo3_K():
    """Los decimales de medición salen del campo 3 del ~K: DD=2, DN=2, DS=3, DSP=2."""
    if not os.path.exists(ALQUERIA):
        raise Saltado("falta Test_Alqueria.bc3")
    p = leer_bc3(ALQUERIA)
    assert p.dec_dim == 2 and p.dec_num == 2
    assert p.dec_cantmed == 3 and p.dec_parcial == 2


def test_alqueria_ci_por_partida():
    """El precio de partida incluye el CI: round(CD × 1,06), también con %CI interno."""
    if not os.path.exists(ALQUERIA):
        raise Saltado("falta Test_Alqueria.bc3")
    p = leer_bc3(ALQUERIA)
    assert abs(p.precio_con_ci("301.0010") - 9.39) < 1e-6
    assert abs(p.precio_con_ci("700.001a") - 34.27) < 1e-6
    assert abs(p.precio_con_ci("301.0115") - 8.54) < 1e-6


def test_alqueria_redondeo_dimensiones_medicion():
    """Cada dimensión se redondea a DD antes de multiplicar: 0,0475 -> 0,05,
    dando medición total 112,21 (no 111,32)."""
    if not os.path.exists(ALQUERIA):
        raise Saltado("falta Test_Alqueria.bc3")
    p = leer_bc3(ALQUERIA)
    assert abs(p.medicion_total("215.0030", "003#") - 112.21) < 1e-6


def test_alqueria_partida_alzada_sin_lineas():
    """Partida con ~M sin líneas: la medición es el total declarado (=1).
    542.0600 -> medición 1, importe 7964,67."""
    if not os.path.exists(ALQUERIA):
        raise Saltado("falta Test_Alqueria.bc3")
    p = leer_bc3(ALQUERIA)
    assert abs(p.medicion_total("542.0600", "003#") - 1.0) < 1e-6
    assert abs(p.importe_en_padre("542.0600", "003#") - 7964.67) < 0.01


def test_alqueria_round_trip_conserva_partida_alzada():
    """El ciclo leer→escribir→releer conserva el PEM y TODAS las mediciones,
    incluidas las PARTIDAS ALZADAS (~M sin líneas, solo total declarado)."""
    if not os.path.exists(ALQUERIA):
        raise Saltado("falta Test_Alqueria.bc3")
    p1 = leer_bc3(ALQUERIA)
    pem1 = p1.presupuesto_total()
    n_med1 = sum(len(c.mediciones) for c in p1.conceptos.values())
    imp_alzada1 = p1.importe_en_padre("542.0600", "003#")
    assert imp_alzada1 > 0
    with tempfile.NamedTemporaryFile(suffix=".bc3", delete=False) as tmp:
        salida = tmp.name
    try:
        escribir_bc3(p1, salida)
        p2 = leer_bc3(salida)
    finally:
        os.unlink(salida)
    n_med2 = sum(len(c.mediciones) for c in p2.conceptos.values())
    assert n_med2 == n_med1, f"se perdieron mediciones: {n_med1} -> {n_med2}"
    imp_alzada2 = p2.importe_en_padre("542.0600", "003#")
    assert abs(imp_alzada2 - imp_alzada1) < 0.01
    assert abs(p2.presupuesto_total() - pem1) < 0.01


def test_alqueria_round_trip_validacion_limpia():
    """Tras guardar y reabrir, la validación sigue LIMPIA (0 discrepancias)."""
    if not os.path.exists(ALQUERIA):
        raise Saltado("falta Test_Alqueria.bc3")
    p1 = leer_bc3(ALQUERIA)
    v1 = p1.validar_completo()
    assert len(v1["precios"]) == 0 and len(v1["mediciones"]) == 0
    with tempfile.NamedTemporaryFile(suffix=".bc3", delete=False) as tmp:
        salida = tmp.name
    try:
        escribir_bc3(p1, salida)
        p2 = leer_bc3(salida)
    finally:
        os.unlink(salida)
    v2 = p2.validar_completo()
    assert len(v2["precios"]) == 0, f"aparecen {len(v2['precios'])} discrepancias de precio"
    assert len(v2["mediciones"]) == 0, f"aparecen {len(v2['mediciones'])} de medición"
    comp = p2.comparar_importes_archivo()
    assert abs(comp["diferencia_pem"]) < 0.01


def test_alqueria_sin_discrepancias_y_pem():
    """0 discrepancias de precio/medición y PEM a < 0,05% del valor del archivo."""
    if not os.path.exists(ALQUERIA):
        raise Saltado("falta Test_Alqueria.bc3")
    p = leer_bc3(ALQUERIA)
    r = p.validar_completo()
    assert len(r["precios"]) == 0, f"precios inconsistentes: {r['precios'][:3]}"
    assert len(r["mediciones"]) == 0, f"mediciones inconsistentes: {r['mediciones'][:3]}"
    pem = p.presupuesto_total()
    arch = p.get(p.codigo_raiz)._precio_bc3
    assert abs(pem - arch) / arch < 0.0005, f"PEM {pem:,.2f} vs archivo {arch:,.2f}"


def test_alqueria_partida_con_descomposicion_sin_unidad():
    """Una partida con descomposición pero sin unidad se clasifica como PARTIDA
    (no capítulo) porque tiene medición propia. 701.0236a."""
    if not os.path.exists(ALQUERIA):
        raise Saltado("falta Test_Alqueria.bc3")
    p = leer_bc3(ALQUERIA)
    assert p.get("701.0236a").tipo == TipoConcepto.PARTIDA


def test_alqueria_consistencia_k_detecta_decimales():
    """El chequeo de consistencia avisa de valores con más decimales que el ~K:
    dimensiones (DD=2) como 0,315 y uds (DN=2) como -3,1415."""
    if not os.path.exists(ALQUERIA):
        raise Saltado("falta Test_Alqueria.bc3")
    p = leer_bc3(ALQUERIA)
    cats = p.revisar_consistencia_k()
    assert "dimensiones" in cats and cats["dimensiones"]["declarado"] == 2
    assert "uds_medicion" in cats and cats["uds_medicion"]["declarado"] == 2
    assert cats["dimensiones"]["total"] > 0 and cats["uds_medicion"]["total"] > 0


# ===========================================================================
# FAMILIA 4 — EDICIÓN Y AUTOGUARDADO (modelo + ciclo guardar/reabrir, undo/redo)
# ===========================================================================
# Se usa Test_SONFONT.bc3 como banco de pruebas (pequeño, con ~K, sin discrepancias).
EDIT_FILE = _ruta("Test_SONFONT.bc3")


def _cargar_edit() -> Presupuesto:
    if not os.path.exists(EDIT_FILE):
        raise Saltado("falta Test_SONFONT.bc3")
    return leer_bc3(EDIT_FILE)


def _primera_partida_con_hijos(p: Presupuesto) -> str:
    return next(c.codigo for c in p.conceptos.values()
                if c.tipo == TipoConcepto.PARTIDA and c.hijos)


def _roundtrip(p: Presupuesto) -> Presupuesto:
    with tempfile.NamedTemporaryFile(suffix=".bc3", delete=False) as tmp:
        salida = tmp.name
    try:
        escribir_bc3(p, salida)
        return leer_bc3(salida)
    finally:
        os.unlink(salida)


def _leaf_que_mueve_pem(p: Presupuesto) -> str | None:
    """Devuelve un recurso hoja cuyo cambio de precio SÍ altera el PEM (está en
    una partida medida). Restaura el precio antes de devolver."""
    pem0 = p.presupuesto_total()
    for c in list(p.conceptos.values()):
        if c.tipo == TipoConcepto.UNITARIO and not c.hijos and c.precio:
            orig = c.precio
            p.modificar_precio(c.codigo, orig + 100.0)
            p.recalcular()
            mueve = abs(p.presupuesto_total() - pem0) > 0.01
            p.modificar_precio(c.codigo, orig)
            p.recalcular()
            if mueve:
                return c.codigo
    return None


def test_edit_modificar_precio_persiste():
    """Editar el precio de un recurso hoja: se aplica, recalcula, y sobrevive al
    guardar→reabrir."""
    p = _cargar_edit()
    leaf = next(c.codigo for c in p.conceptos.values()
                if c.tipo == TipoConcepto.UNITARIO and not c.hijos and c.precio)
    p.modificar_precio(leaf, 123.45)
    assert abs(p.get(leaf).precio - 123.45) < 1e-9
    p2 = _roundtrip(p)
    assert abs(p2.get(leaf).precio - 123.45) < 0.01, "el precio editado no sobrevivió"


def test_edit_precio_partida_se_rechaza():
    """No se puede editar el precio de una partida con descomposición (calculado)."""
    p = _cargar_edit()
    partida = _primera_partida_con_hijos(p)
    try:
        p.modificar_precio(partida, 99.0)
    except ValueError:
        return
    raise AssertionError("modificar_precio sobre partida con descomposición debió fallar")


def test_edit_add_partida_nace_en_cero():
    """add_partida crea la partida con cantidad 0 (importe 0) y no rompe nada."""
    p = _cargar_edit()
    cap = next(c.codigo for c in p.conceptos.values() if c.tipo == TipoConcepto.CAPITULO)
    p.add_partida(cap, "NUEVA.TEST", "m2", "Partida de prueba", 10.0)
    h = next(h for h in p.get(cap).hijos if h.codigo_hijo == "NUEVA.TEST")
    assert h.cantidad == 0.0
    assert abs(p.importe_en_padre("NUEVA.TEST", cap)) < 1e-9


def test_edit_add_recurso_tipo_fiebdc():
    """Un recurso añadido se exporta con su tipo FIEBDC explícito (no vacío)."""
    p = _cargar_edit()
    partida = _primera_partida_con_hijos(p)
    p.add_recurso(partida, "REC.MAT.TEST", rendimiento=2.0, precio=5.0, unidad="kg")
    p.add_recurso(partida, "REC.MAQ.TEST", rendimiento=1.0, precio=9.0,
                  unidad="h", tipo_fiebdc="2")
    with tempfile.NamedTemporaryFile(suffix=".bc3", delete=False) as tmp:
        salida = tmp.name
    try:
        escribir_bc3(p, salida)
        with open(salida, "rb") as f:
            lineas = f.read().decode("cp1252", errors="replace").splitlines()
    finally:
        os.unlink(salida)
    def tipo(cod):
        return next(l for l in lineas if l.startswith(f"~C|{cod}|")).split("|")[6]
    assert tipo("REC.MAT.TEST") == "3"   # material por defecto
    assert tipo("REC.MAQ.TEST") == "2"   # maquinaria indicada


def test_edit_modificar_codigo_actualiza_referencias():
    """Renombrar un concepto actualiza TODAS las referencias (hijos, mediciones,
    raíz) y el archivo reescrito no queda con enlaces rotos."""
    p = _cargar_edit()
    viejo = next(c.codigo for c in p.conceptos.values()
                 if c.tipo == TipoConcepto.UNITARIO and not c.hijos)
    nuevo = viejo + ".REN"
    pem0 = p.presupuesto_total()
    p.modificar_codigo(viejo, nuevo)
    assert p.get(nuevo) is not None and p.get(viejo) is None
    assert not any(h.codigo_hijo == viejo
                   for c in p.conceptos.values() for h in c.hijos), "quedó referencia al código viejo"
    p2 = _roundtrip(p)
    assert not _refs_rotas(p2), "el archivo reescrito tras renombrar tiene referencias rotas"
    assert abs(p2.presupuesto_total() - pem0) < 0.01, "renombrar cambió el PEM"


def test_edit_eliminar_concepto_desvincula():
    """eliminar_concepto desvincula del padre pero NO borra el concepto (puede
    usarse en otros sitios)."""
    p = _cargar_edit()
    cap = "01#"
    if p.get(cap) is None:
        raise Saltado("estructura inesperada")
    hijo = p.get(cap).hijos[0].codigo_hijo
    p.eliminar_concepto(hijo, cap)
    assert not any(h.codigo_hijo == hijo for h in p.get(cap).hijos), "no se desvinculó del padre"
    assert p.get(hijo) is not None, "el concepto no debería borrarse del presupuesto"


def test_edit_copiar_no_crea_ciclo():
    """copiar_concepto debe impedir pegar un concepto dentro de sí mismo o de un
    descendiente (evita ciclos)."""
    p = _cargar_edit()
    cap = next(c.codigo for c in p.conceptos.values()
               if c.tipo == TipoConcepto.CAPITULO and c.hijos)
    try:
        p.copiar_concepto(cap, cap)
    except ValueError:
        return
    raise AssertionError("copiar un concepto dentro de sí mismo debió fallar")


def test_edit_cadena_ediciones_round_trip_valido():
    """Una cadena de ediciones seguidas deja un archivo que se relee sin error,
    con la validación tan limpia como el original (caza el drift del autoguardado)."""
    p = _cargar_edit()
    v0 = p.validar_completo()
    cap = next(c.codigo for c in p.conceptos.values() if c.tipo == TipoConcepto.CAPITULO)
    partida = _primera_partida_con_hijos(p)
    leaf = next(c.codigo for c in p.conceptos.values()
                if c.tipo == TipoConcepto.UNITARIO and not c.hijos and c.precio)
    # Varias ediciones encadenadas, cada una reescribiendo (como el autoguardado)
    p.modificar_resumen(partida, "Resumen editado de prueba")
    p = _roundtrip(p)
    p.add_partida(cap, "ENC.TEST", "ud", "Encadenada", 3.0)
    p = _roundtrip(p)
    p.modificar_precio(leaf, p.get(leaf).precio + 1.0)
    p = _roundtrip(p)
    assert not _refs_rotas(p), "la cadena de ediciones dejó referencias rotas"
    v1 = p.validar_completo()
    assert len(v1["precios"]) <= len(v0["precios"]) + 1, "la cadena de ediciones empeoró la validación"


def test_edit_undo_redo_restaura_pem():
    """Deshacer/rehacer (capa web): tras editar y deshacer, el PEM vuelve exacto;
    rehacer lo recupera. Usa los ayudantes de snapshot de web.py con una copia
    temporal como 'archivo original' (no toca el .bc3 real)."""
    try:
        from bc3manager import web
    except Exception as e:                       # Flask no disponible u otro fallo de import
        raise Saltado(f"no se pudo importar web.py: {e!r}")
    if not os.path.exists(EDIT_FILE):
        raise Saltado("falta Test_SONFONT.bc3")
    import shutil
    with tempfile.NamedTemporaryFile(suffix=".bc3", delete=False) as tmp:
        copia = tmp.name
    shutil.copy(EDIT_FILE, copia)
    try:
        p = leer_bc3(copia)
        web._estado["presupuesto"] = p
        web._estado["ruta_original"] = copia
        web._init_historial()                    # undo_stack = [S0]
        pem0 = p.presupuesto_total()
        leaf = next(c.codigo for c in p.conceptos.values()
                    if c.tipo == TipoConcepto.UNITARIO and not c.hijos and c.precio)
        p.modificar_precio(leaf, p.get(leaf).precio + 100.0)
        web._autoguardar()                       # undo_stack = [S0, S1]
        pem1 = web._estado["presupuesto"].presupuesto_total()
        assert abs(pem1 - pem0) > 0.01, "la edición no cambió el PEM (test mal montado)"
        # Deshacer: replica la lógica de /api/undo
        actual = web._estado["undo_stack"].pop()
        web._estado.setdefault("redo_stack", []).append(actual)
        web._restaurar_snapshot(web._estado["undo_stack"][-1])
        assert abs(web._estado["presupuesto"].presupuesto_total() - pem0) < 0.01, (
            "deshacer no devolvió el PEM original"
        )
        # Rehacer
        snap = web._estado["redo_stack"].pop()
        web._estado.setdefault("undo_stack", []).append(snap)
        web._restaurar_snapshot(snap)
        assert abs(web._estado["presupuesto"].presupuesto_total() - pem1) < 0.01, (
            "rehacer no recuperó el PEM editado"
        )
    finally:
        web._estado.clear()
        try:
            os.unlink(copia)
        except OSError:
            pass


# ===========================================================================
# RUNNER
# ===========================================================================

def _run() -> int:
    g = globals()
    parametricos = [g[k] for k in sorted(g) if k.startswith("param_")]
    dirigidos = [g[k] for k in sorted(g) if k.startswith("test_")]

    presentes = _corpus_presentes()
    ausentes = [m["archivo"] for m in CORPUS if not os.path.exists(_ruta(m["archivo"]))]

    print("=" * 64)
    print(f"CORPUS: {len(presentes)} presentes, {len(ausentes)} ausentes")
    for m in presentes:
        print(f"   + {m['archivo']:<26} {m['programa']}")
    for a in ausentes:
        print(f"   - {a:<26} (AUSENTE: sus paramétricos se saltan)")
    print("=" * 64)

    fallos = 0
    saltados = 0
    corridas = 0

    # --- Familia 1+2: paramétricos sobre cada archivo del corpus ---
    print("\n[PARAMÉTRICOS] mismo test sobre cada archivo")
    for meta in presentes:
        try:
            ctx = _Ctx(meta)
        except Exception as e:
            print(f"  FALLO  {meta['archivo']} :: carga/round-trip: {e!r}")
            fallos += 1
            continue
        fila_fallos = []
        ok = 0
        for fn in parametricos:
            corridas += 1
            try:
                fn(ctx)
                ok += 1
            except Saltado as s:
                saltados += 1
            except AssertionError as e:
                fallos += 1
                fila_fallos.append(f"{fn.__name__}: {e}")
            except Exception as e:
                fallos += 1
                fila_fallos.append(f"{fn.__name__}: ERROR {e!r}")
        ctx.cleanup()
        estado = "OK" if not fila_fallos else f"{len(fila_fallos)} FALLOS"
        print(f"  {meta['archivo']:<26} {ok}/{len(parametricos)} {estado}")
        for f in fila_fallos:
            print(f"        FALLO {f}")

    # --- Familia 3+4: dirigidos y edición ---
    print("\n[DIRIGIDOS Y EDICIÓN]")
    for fn in dirigidos:
        corridas += 1
        try:
            fn()
            print(f"  OK     {fn.__name__}")
        except Saltado as s:
            saltados += 1
            corridas -= 1
            print(f"  SALTADO {fn.__name__} ({s})")
        except AssertionError as e:
            fallos += 1
            print(f"  FALLO  {fn.__name__}: {e}")
        except Exception as e:
            fallos += 1
            print(f"  ERROR  {fn.__name__}: {e!r}")

    print("\n" + "=" * 64)
    print(f"{corridas - fallos}/{corridas} comprobaciones correctas "
          f"({saltados} saltadas, {fallos} fallidas)")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(_run())
