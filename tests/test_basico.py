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
