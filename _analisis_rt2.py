"""Análisis profundo del problema 2: degradación de la validación tras guardar.
Script temporal de diagnóstico."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bc3manager.io.lector import leer_bc3
from bc3manager.io.escritor import escribir_bc3
from bc3manager.core.model import TipoConcepto

ALQ = os.path.join("tests", "Test_Alqueria.bc3")
p1 = leer_bc3(ALQ)

# --- Hipótesis: el ~C de un capítulo en el ORIGINAL guarda CD+CI, no CD ---
print("=== Capítulos: ¿qué guarda su ~C original vs CD vs CD+CI? ===")
print(f"  {'codigo':<10} {'_precio_bc3':>14} {'CD calc':>14} {'CD*1.06':>14}")
raiz = p1.get(p1.codigo_raiz)
def caps_orden(cod, prof=0):
    c = p1.get(cod)
    if not c: return
    for h in c.hijos:
        hc = p1.get(h.codigo_hijo)
        if hc and hc.tipo == TipoConcepto.CAPITULO:
            bc3 = getattr(hc, "_precio_bc3", None)
            cd = hc.precio
            if bc3 and prof < 1:  # solo capítulos raíz para no saturar
                print(f"  {hc.codigo:<10} {bc3:>14.4f} {cd:>14.4f} {cd*1.06:>14.4f}")
            caps_orden(h.codigo_hijo, prof+1)
caps_orden(p1.codigo_raiz)

# Round-trip y desglose de las discrepancias
with tempfile.NamedTemporaryFile(suffix=".bc3", delete=False) as tmp:
    salida = tmp.name
try:
    escribir_bc3(p1, salida)
    p2 = leer_bc3(salida)
finally:
    os.unlink(salida)

val2 = p2.validar_completo()
print(f"\n=== Las {len(val2['precios'])} discrepancias de PRECIO tras round-trip ===")
tipos = {}
for d in val2["precios"]:
    tipos[d["tipo"]] = tipos.get(d["tipo"], 0) + 1
print(f"  Por tipo: {tipos}")
print(f"  {'codigo':<10} {'tipo':<9} {'archivo':>12} {'calc':>12} {'dif%':>7}")
for d in val2["precios"][:6]:
    print(f"  {d['codigo']:<10} {d['tipo']:<9} {d['precio_bc3']:>12.4f} {d['precio_calculado']:>12.4f} {d['diferencia_pct']:>6.2f}%")

print(f"\n=== Las {len(val2['mediciones'])} discrepancias de MEDICIÓN tras round-trip ===")
for d in val2["mediciones"]:
    print(f"  {d['codigo']:<14} en {d['padre']:<8} declarada={d['declarada']} suma_lineas={d['suma_lineas']} dif={d['diferencia']}")

# ¿La partida alzada 542.0600 sigue teniendo importe?
print("\n=== Partida alzada 542.0600 tras round-trip ===")
c = p2.get("542.0600")
if c:
    print(f"  mediciones: {dict((k, len(v.lineas)) for k,v in c.mediciones.items())}")
    print(f"  importe en 003#: {p2.importe_en_padre('542.0600', '003#'):,.2f}")
else:
    print("  542.0600 ya no existe")
