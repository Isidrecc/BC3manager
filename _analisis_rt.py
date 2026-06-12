"""Análisis del round-trip leer->escribir->releer sobre Test_Alqueria.bc3.
Script temporal de diagnóstico (se borra al terminar)."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bc3manager.io.lector import leer_bc3
from bc3manager.io.escritor import escribir_bc3
from bc3manager.core.model import TipoConcepto

ALQ = os.path.join("tests", "Test_Alqueria.bc3")

def resumen(p, etiqueta):
    n_med = sum(len(c.mediciones) for c in p.conceptos.values())
    n_med_sin_lineas = sum(
        1 for c in p.conceptos.values() for m in c.mediciones.values()
        if not m.lineas
    )
    n_med_con_lineas = n_med - n_med_sin_lineas
    val = p.validar_completo()
    comp = p.comparar_importes_archivo()
    print(f"\n===== {etiqueta} =====")
    print(f"  Conceptos:           {len(p.conceptos)}")
    print(f"  Mediciones (total):  {n_med}  (con líneas: {n_med_con_lineas}, sin líneas: {n_med_sin_lineas})")
    print(f"  PEM calculado:       {p.presupuesto_total():,.2f}")
    print(f"  Discrep. precios:    {len(val['precios'])}")
    print(f"  Discrep. mediciones: {len(val['mediciones'])}")
    print(f"  PEM archivo (comp):  {comp['pem_archivo']:,.2f}")
    print(f"  PEM calc  (comp):    {comp['pem_calculado']:,.2f}")
    print(f"  Dif PEM archivo-calc:{comp['diferencia_pem']:,.2f}")
    return p.presupuesto_total(), n_med, n_med_sin_lineas

# 1) Original
p1 = leer_bc3(ALQ)
pem1, nmed1, nsin1 = resumen(p1, "ORIGINAL (Test_Alqueria.bc3)")

# Localizar las partidas alzadas (~M sin líneas) y su importe
print("\n  --- Partidas con ~M SIN líneas (alzadas) en el original ---")
alzadas = []
for c in p1.conceptos.values():
    for padre, m in c.mediciones.items():
        if not m.lineas:
            imp = p1.importe_en_padre(c.codigo, padre)
            alzadas.append((c.codigo, padre, m.total_declarado, imp))
            print(f"    {c.codigo:<14} en {padre:<8} total_decl={m.total_declarado:<10} importe={imp:,.2f}  tipo={c.tipo.value}")
print(f"    TOTAL importe de alzadas: {sum(a[3] for a in alzadas):,.2f}")

# 2) Round-trip
with tempfile.NamedTemporaryFile(suffix=".bc3", delete=False) as tmp:
    salida = tmp.name
try:
    escribir_bc3(p1, salida)
    p2 = leer_bc3(salida)
    pem2, nmed2, nsin2 = resumen(p2, "TRAS round-trip (escribir+releer)")
finally:
    os.unlink(salida)

print("\n===== DIFERENCIAS =====")
print(f"  PEM:        {pem1:,.2f} -> {pem2:,.2f}   (cae {pem1-pem2:,.2f})")
print(f"  Mediciones: {nmed1} -> {nmed2}   (sin líneas: {nsin1} -> {nsin2})")
