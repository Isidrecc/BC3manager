"""
Genera el archivo de muestra ejemplo_son_font.bc3 usado por los tests.

Cifras pensadas para casar con los asserts de tests/test_basico.py:
  - MO001 (peon)       18,50 EUR/h
  - MQ001 (retro)      45,00 EUR/h
  - E0101 precio       11,375 = MO001*0,25 + MQ001*0,15
  - E0101 medicion     150   = 2*40*1,5 + 1*30
  - 11 conceptos en total
  - codigo_raiz        OBRA##

Se escribe en cp1252 con CRLF, como el resto de BC3 del sector.
"""
from pathlib import Path

REG = [
    # Cabecera
    r"~V|PROPIEDAD|FIEBDC-3/2024\30/05/2026|BC3Manager_Sample||ANSI||1||",
    # Conceptos (11)
    r"~C|OBRA##||Ejemplo Son Font|0||0|",
    r"~C|01#||Movimiento de tierras|0||5|",
    r"~C|02#||Drenaje y saneamiento|0||5|",
    r"~C|E0101|m3|Excavacion en zanja a maquina|11.375||6|",
    r"~C|E0102|m3|Relleno y compactacion de zanjas|4.10||6|",
    r"~C|E0201|m|Tuberia PVC saneamiento DN200|41.00||6|",
    r"~C|E0202|ud|Arqueta de registro 40x40|29.75||6|",
    r"~C|MO001|h|Peon ordinario|18.50||1|",
    r"~C|MQ001|h|Retroexcavadora mixta|45.00||2|",
    r"~C|MT001|m|Tuberia PVC SN-4 DN200|22.50||3|",
    r"~C|MT002|kg|Cemento CEM II/B-L 32,5N|0.15||3|",
    # Descomposiciones
    r"~D|OBRA##|01#\1\1\02#\1\1\|",
    r"~D|01#|E0101\1\1\E0102\1\1\|",
    r"~D|02#|E0201\1\1\E0202\1\1\|",
    r"~D|E0101|MO001\1\0.25\MQ001\1\0.15\|",
    r"~D|E0102|MO001\1\0.10\MQ001\1\0.05\|",
    r"~D|E0201|MO001\1\1\MT001\1\1\|",
    r"~D|E0202|MO001\1\1\MT002\1\75\|",
    # Mediciones (tipo \ comentario \ N \ longitud \ anchura \ altura, ceros = factor neutro)
    r"~M|01#\E0101||150|0\Tramo principal\2\40\0\1.5\0\Tramo lateral\1\30\0\0\|",
    r"~M|01#\E0102||100|0\Relleno zanjas\2\50\0\1\|",
    r"~M|02#\E0201||50|0\Colector general\1\50\0\0\|",
    r"~M|02#\E0202||12|0\Arquetas en cruces\12\0\0\0\|",
]

contenido = "\r\n".join(REG) + "\r\n"
destino = Path(__file__).resolve().parent.parent / "ejemplo_son_font.bc3"
destino.write_text(contenido, encoding="cp1252", newline="")
print(f"Generado: {destino}  ({destino.stat().st_size} bytes)")
