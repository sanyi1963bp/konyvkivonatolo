"""
Minta nézegetó — megmutatja az ismeretlen fájlok nevét
Tedd az adatbázis mellé és futtasd:
  python minta_nezegeto.py
"""

import sqlite3

DB_PATH = r"H:\________________2026 FEjlesztesek\Ncore bővítés\ncore_konyvtar.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("=" * 70)
print("  ISMERETLEN fájlok (első 20)")
print("=" * 70)
cursor.execute("""
    SELECT fajl_nev, fajl_utvonal FROM fizikai_fajlok
    WHERE egyezes_szint = 'ismeretlen'
    LIMIT 20
""")
for nev, ut in cursor.fetchall():
    print(f"Fájlnév:  {nev}")
    print(f"Teljes út: {ut}")
    print()

print("=" * 70)
print("  PONTOS találatok (első 10) — ezek jól működtek")
print("=" * 70)
cursor.execute("""
    SELECT fajl_nev, talalat_szerzo, talalat_cim FROM fizikai_fajlok
    WHERE egyezes_szint = 'pontos'
    LIMIT 10
""")
for nev, szerzo, cim in cursor.fetchall():
    print(f"Fájlnév:  {nev}")
    print(f"Szerző:   {szerzo}")
    print(f"Cím:      {cim}")
    print()

conn.close()
input("Nyomj Entert a kilépéshez...")
