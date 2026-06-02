"""
Tests básicos de BC3Manager.

Ejecutar con:  python -m pytest   (si tienes pytest)
o simplemente: python tests/test_basico.py

Verifican el núcleo: lectura, recálculo de precios, importes, total y el
ciclo completo leer -> escribir -> releer (round-trip).
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bc3manager.io.lector import leer_bc3
from bc3manager.io.escritor import escribir_bc3


EJEMPLO = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "ejemplo_son_font.bc3",
)


def test_lectura_basica():
    p = leer_bc3(EJEMPLO)
    assert p.codigo_raiz == "OBRA##"
    assert len(p.conceptos) == 11
    assert p.version_formato == "FIEBDC-3/2024"


def test_precios_unitarios_dato():
    p = leer_bc3(EJEMPLO)
    assert abs(p.get("MO001").precio - 18.50) < 1e-6
    assert abs(p.get("MQ001").precio - 45.00) < 1e-6


def test_recalculo_descomposicion():
    p = leer_bc3(EJEMPLO)
    # E0101 = peón 18.50*0.25 + retro 45.00*0.15 = 11.375
    assert abs(p.get("E0101").precio - 11.375) < 1e-3


def test_medicion():
    p = leer_bc3(EJEMPLO)
    # E0101 en 01#: 2*40*1.5 + 1*30 = 120 + 30 = 150
    assert abs(p.medicion_total("E0101", "01#") - 150.0) < 1e-3


def test_total():
    p = leer_bc3(EJEMPLO)
    assert abs(p.presupuesto_total() - 4523.25) < 0.01


def test_validar_precios_sin_discrepancias():
    """En el ejemplo, los precios del archivo deben coincidir con el recálculo."""
    p = leer_bc3(EJEMPLO)
    discrepancias = p.validar_precios_cargados()
    assert discrepancias == [], (
        f"No deberían haber discrepancias en ejemplo_son_font.bc3. "
        f"Encontradas: {discrepancias}"
    )


def test_validar_precios_detecta_discrepancia():
    """Si tras cargar manipulamos un _precio_bc3 para que no cuadre con la
    descomposición, validar_precios_cargados debe detectarlo."""
    p = leer_bc3(EJEMPLO)
    # E0101 tiene precio calculado 11.375 (MO001*0.25 + MQ001*0.15)
    # Forzamos un _precio_bc3 distinto para simular un archivo inconsistente
    p.get("E0101")._precio_bc3 = 99.99
    disc = p.validar_precios_cargados()
    assert any(d["codigo"] == "E0101" for d in disc), (
        f"Debería haber detectado discrepancia en E0101. Encontradas: {disc}"
    )


def test_rendimiento_cero_se_conserva():
    """Un rendimiento 0 en el ~D (partida sin medición en ese capítulo) debe
    conservarse como 0, no convertirse en 1. Si no, al exportar se inflaban
    mediciones e importes y Presto reinterpretaba la partida."""
    ruta = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "Test_SONFONT.bc3"
    )
    if not os.path.exists(ruta):
        return
    p = leer_bc3(ruta)
    c01 = p.get("01#")
    ceros = {h.codigo_hijo for h in c01.hijos if h.cantidad == 0}
    # En el original, estas partidas tienen rendimiento 0 en 01# (no se miden ahí)
    assert {"MOV.03.03", "HID.01.02", "HID.02.01", "EST.01.01"} <= ceros, (
        f"Se perdieron los ceros: {ceros}"
    )


def test_add_partida_no_crashea():
    """add_partida no debe pasar 'cantidad' al constructor de Hijo (es propiedad
    de solo lectura). La partida nueva nace con cantidad 0."""
    p = leer_bc3(EJEMPLO)
    p.add_partida("01#", "NUEVA.X", "m2", "Prueba", 10.0)
    h = next(h for h in p.get("01#").hijos if h.codigo_hijo == "NUEVA.X")
    assert h.cantidad == 0.0


def test_round_trip_conserva_rendimiento_cero():
    """Tras exportar y releer, los rendimientos 0 y el PEM deben mantenerse."""
    import tempfile
    ruta = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "Test_SONFONT.bc3"
    )
    if not os.path.exists(ruta):
        return
    p = leer_bc3(ruta)
    pem = p.presupuesto_total()
    with tempfile.NamedTemporaryFile(suffix=".bc3", delete=False) as tmp:
        salida = tmp.name
    try:
        escribir_bc3(p, salida)
        rt = leer_bc3(salida)
        ceros_o = {h.codigo_hijo for h in p.get("01#").hijos if h.cantidad == 0}
        ceros_r = {h.codigo_hijo for h in rt.get("01#").hijos if h.cantidad == 0}
        assert ceros_o == ceros_r, f"{ceros_o} != {ceros_r}"
        assert abs(rt.presupuesto_total() - pem) < 0.01
    finally:
        os.unlink(salida)


def test_lineas_porcentaje_medios_auxiliares():
    """Las líneas de porcentaje (%MA = medios auxiliares) deben aplicarse sobre
    el acumulado de la descomposición, NO como precio×rendimiento.

    Caso real de Test_SONFONT.bc3:
      MOV.02.01 = MO.006×0.08 + MAQ.RET.10×0.155, + 7% medios auxiliares
                = (21.60×0.08 + 55.23×0.155) × 1.07 = 11.0089 ≈ 11.01
    """
    ruta = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "Test_SONFONT.bc3"
    )
    if not os.path.exists(ruta):
        return  # archivo opcional; si no está, no se ejecuta
    p = leer_bc3(ruta)
    # El concepto %MA.7 debe detectarse como porcentaje
    from bc3manager.core.model import Presupuesto
    assert Presupuesto.es_porcentaje(p.get("%MA.7"))
    # El archivo trae ~K → el redondeo de Presto debe estar activo
    assert p.redondeo_activo, "El ~K debe activar el redondeo a 2 decimales"
    # Precio exacto al céntimo con redondeo de subtotales (DecImp=2) + 7% medios aux.
    #   DEM.01.01: (2,16 + 8,28) × 1,07, redondeando cada subtotal = 11,17
    assert p.get("DEM.01.01").precio == 11.17, (
        f"DEM.01.01 = {p.get('DEM.01.01').precio}, esperado 11.17 (Presto)"
    )
    assert p.get("MOV.02.01").precio == 11.01, (
        f"MOV.02.01 = {p.get('MOV.02.01').precio}, esperado 11.01 (Presto)"
    )
    # Todas las partidas con descomposición deben coincidir con su _precio_bc3
    from bc3manager.core.model import TipoConcepto
    for cod, c in p.conceptos.items():
        if c.tipo == TipoConcepto.PARTIDA and c.hijos:
            arch = getattr(c, "_precio_bc3", None)
            if arch and arch > 0:
                # Tolerancia 2 céntimos: absorbe el redondeo a 2 decimales que
                # aplica Presto al precio unitario. El bug de medios auxiliares
                # producía desviaciones del 5-7% (céntimos a euros), muy por
                # encima de esta tolerancia.
                assert abs(arch - c.precio) < 0.02, (
                    f"{cod}: archivo={arch} calc={c.precio}"
                )


def test_redondeos_k_distintos():
    """Verifica que se leen los decimales del registro ~K (cada parámetro con
    un valor distinto) y que el cálculo reproduce EXACTAMENTE los precios e
    importes del archivo de Presto, incluido el PEM."""
    ruta = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "Test_REDONDEO.bc3"
    )
    if not os.path.exists(ruta):
        return
    from bc3manager.core.model import TipoConcepto
    p = leer_bc3(ruta)
    # Mapeo del ~K  \8\2\3\7\6\5\4\  →  DecImp=7, DecPar=5, Dec=4, DecCantRend=3
    assert p.redondeo_activo
    assert p.dec_subtotal == 7, f"DecImp={p.dec_subtotal}"
    assert p.dec_precio_partida == 5, f"DecPar={p.dec_precio_partida}"
    assert p.dec_precio_capitulo == 4, f"Dec={p.dec_precio_capitulo}"
    assert p.dec_cantrend == 3, f"DecCantRend={p.dec_cantrend}"
    # Todas las partidas con descomposición deben coincidir AL CÉNTIMO con el archivo
    for cod, c in p.conceptos.items():
        if c.tipo == TipoConcepto.PARTIDA and c.hijos:
            arch = getattr(c, "_precio_bc3", None)
            if arch and arch > 0:
                assert abs(arch - c.precio) < 0.0001, (
                    f"{cod}: archivo={arch} calc={c.precio}"
                )
    # El PEM calculado debe coincidir con el del archivo
    comp = p.comparar_importes_archivo()
    assert abs(comp["diferencia_pem"]) < 0.01, (
        f"PEM archivo={comp['pem_archivo']} calc={comp['pem_calculado']}"
    )


def test_round_trip_conserva_redondeos_k():
    """Al escribir un BC3 debe emitirse el registro ~K, de modo que al reabrirlo
    (en BC3Manager u otro programa) se conserve la configuración de redondeo y
    los precios se recalculen igual. Verifica el ciclo leer→escribir→releer."""
    ruta = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "Test_REDONDEO.bc3"
    )
    if not os.path.exists(ruta):
        return
    p1 = leer_bc3(ruta)
    pem1 = p1.presupuesto_total()
    with tempfile.NamedTemporaryFile(suffix=".bc3", delete=False) as tmp:
        salida = tmp.name
    try:
        escribir_bc3(p1, salida)
        p2 = leer_bc3(salida)
        # El ~K debe haberse escrito y releído con los mismos decimales
        assert p2.redondeo_activo, "El archivo escrito debe incluir ~K"
        assert p2.dec_subtotal == p1.dec_subtotal
        assert p2.dec_precio_partida == p1.dec_precio_partida
        assert p2.dec_precio_capitulo == p1.dec_precio_capitulo
        assert p2.dec_cantrend == p1.dec_cantrend
        # Y el PEM debe ser idéntico tras el round-trip
        assert abs(p2.presupuesto_total() - pem1) < 0.01, (
            f"PEM cambió en round-trip: {pem1} -> {p2.presupuesto_total()}"
        )
    finally:
        os.unlink(salida)


def test_round_trip():
    p = leer_bc3(EJEMPLO)
    total_original = p.presupuesto_total()
    with tempfile.NamedTemporaryFile(suffix=".bc3", delete=False) as tmp:
        ruta = tmp.name
    try:
        escribir_bc3(p, ruta)
        p2 = leer_bc3(ruta)
        # El total puede diferir ligeramente porque el BC3 exportado incluye
        # los precios recalculados en ~C, lo que activa precio_es_dato en p2.
        # Verificamos que los precios de conceptos hoja se conservan.
        assert abs(p2.get("MO001").precio - 18.50) < 1e-3
        assert abs(p2.get("MQ001").precio - 45.00) < 1e-3
        assert len(p2.conceptos) == len(p.conceptos)
    finally:
        os.unlink(ruta)


def test_export_estructura_presto():
    """El BC3 exportado debe imitar la estructura de Presto para que NO
    reclasifique las partidas al reabrir (bug: partidas de movimiento de tierras
    convertidas en 'maquinaria'). Verifica dos cosas:
      1. El ~C de cada partida va seguido INMEDIATAMENTE de su ~D. Si Presto lee
         un ~C sin descomposición pegada, la toma por recurso hoja (maquinaria).
      2. Los registros ~M llevan el campo POSICIÓN relleno (p.ej. "1\\2\\")."""
    ruta = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "Test_SONFONT.bc3"
    )
    if not os.path.exists(ruta):
        return
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
    # 1) ~C de partida pegado a su ~D
    idx_c = next(i for i, ln in enumerate(lineas) if ln.startswith("~C|MOV.02.01|"))
    assert lineas[idx_c + 1].startswith("~D|MOV.02.01|"), (
        "El ~D de la partida debe ir justo tras su ~C; si no, Presto la "
        "reclasifica como maquinaria."
    )
    # 2) ~M con posición (campo 2 no vacío)
    m_mov = next(ln for ln in lineas if ln.startswith("~M|01#\\MOV.02.01|"))
    posicion = m_mov.split("|")[2]
    assert posicion.strip("\\").strip() != "", f"~M sin posición: {m_mov}"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    fallos = 0
    for fn in fns:
        try:
            fn()
            print(f"  OK   {fn.__name__}")
        except AssertionError as e:
            fallos += 1
            print(f" FALLO {fn.__name__}: {e}")
    print(f"\n{len(fns) - fallos}/{len(fns)} tests correctos")
    sys.exit(1 if fallos else 0)
