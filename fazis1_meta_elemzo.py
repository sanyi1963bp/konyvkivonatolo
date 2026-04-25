"""
KönyvtárAI - Meta-elemző
=========================
Első indításkor lefut és feltérképezi az adatbázis tartalmát.
Elmenti a meta.json fájlba, amit a főprogram minden indításkor
beolvas — így "tudja" milyen adatok vannak a könyvtárban.

Futtatás:
  python fazis1_meta_elemzo.py

Eredmény:
  meta.json a DB mellé mentve — tartalmazza:
    - rekordszámok
    - top cimkék, kiadók, évek, formátumok
    - sorozatok listája
    - adatgazdagság statisztika (hány mezőnél van valós adat)
"""

import sqlite3
import json
import os
import re
from collections import Counter
from datetime import datetime

# ============================================================
# BEÁLLÍTÁSOK
# ============================================================

DB_PATH = r"H:\________________2026 FEjlesztesek\Ncore bővítés\ncore_konyvtar.db"
META_PATH = os.path.join(os.path.dirname(DB_PATH), "meta.json")

# ============================================================
# SEGÉDFUNKCIÓK
# ============================================================

def is_valid(value) -> bool:
    """Ellenőrzi, hogy egy mező valódi adatot tartalmaz-e (nem None, nem 'N/A')."""
    if value is None:
        return False
    s = str(value).strip()
    return s not in ('', 'N/A', 'n/a', 'NA', '-', 'ismeretlen', 'unknown')


def top_n(counter: Counter, n: int = 30) -> list:
    """Counter → top N elem listája [{ertek, db}] formában."""
    return [
        {"ertek": k, "db": v}
        for k, v in counter.most_common(n)
        if k and is_valid(k)
    ]


# ============================================================
# FŐ ELEMZÉS
# ============================================================

def elemez():
    print("=" * 60)
    print("  KönyvtárAI — Meta-elemző")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # ── Alapszámok ─────────────────────────────────────────
    print("\n[1/6] Alapszámok...")
    cursor.execute("SELECT COUNT(*) as db FROM konyvek")
    osszes = cursor.fetchone()["db"]

    cursor.execute("""
        SELECT COUNT(*) as db FROM konyvek
        WHERE kep_utvonal IS NOT NULL AND kep_utvonal != ''
    """)

    # ── Szerzők ────────────────────────────────────────────
    print("[2/6] Szerzők elemzése...")
    cursor.execute("SELECT szerzo FROM konyvek WHERE szerzo IS NOT NULL AND szerzo != 'N/A'")
    szerzo_counter = Counter()
    szerzo_osszes = set()
    for (sz,) in cursor.fetchall():
        if not sz:
            continue
        # Több szerző szétválasztása
        reszek = re.split(r'\s*[–;\/]\s*|\s*,\s*(?=[A-ZÁÉÍÓÖŐÚÜŰ])', sz)
        for r in reszek:
            r = r.strip()
            if r and is_valid(r):
                szerzo_counter[r] += 1
                szerzo_osszes.add(r)

    # ── Cimkék ─────────────────────────────────────────────
    print("[3/6] Cimkék elemzése...")
    cursor.execute("SELECT cimkek FROM konyvek WHERE cimkek IS NOT NULL AND cimkek != ''")
    cimke_counter = Counter()
    for (cimkek,) in cursor.fetchall():
        if not cimkek:
            continue
        for c in re.split(r'[,;]+', cimkek):
            c = c.strip().lower()
            if c and len(c) > 1:
                cimke_counter[c] += 1

    # ── Kiadók ─────────────────────────────────────────────
    print("[4/6] Kiadók elemzése...")
    cursor.execute("SELECT kiado FROM konyvek WHERE kiado IS NOT NULL AND kiado != 'N/A'")
    kiado_counter = Counter(
        row[0].strip()
        for row in cursor.fetchall()
        if row[0] and is_valid(row[0])
    )

    # ── Évek ───────────────────────────────────────────────
    print("[5/6] Kiadási évek elemzése...")
    cursor.execute("SELECT kiadas_eve FROM konyvek WHERE kiadas_eve IS NOT NULL AND kiadas_eve != 'N/A'")
    ev_counter = Counter()
    for (ev,) in cursor.fetchall():
        if ev and re.match(r'^\d{4}$', str(ev).strip()):
            ev_counter[str(ev).strip()] += 1

    # ── Formátumok ─────────────────────────────────────────
    cursor.execute("SELECT formatum FROM konyvek WHERE formatum IS NOT NULL AND formatum != ''")
    format_counter = Counter(
        row[0].lower().strip()
        for row in cursor.fetchall()
        if row[0]
    )

    # ── Sorozatok ──────────────────────────────────────────
    cursor.execute("""
        SELECT sorozat, COUNT(*) as db FROM konyvek
        WHERE sorozat IS NOT NULL AND sorozat != 'N/A' AND sorozat != ''
        GROUP BY sorozat
        ORDER BY db DESC
        LIMIT 100
    """)
    sorozatok = [
        {"nev": row["sorozat"], "db": row["db"]}
        for row in cursor.fetchall()
    ]

    # ── Adatgazdagság ──────────────────────────────────────
    print("[6/6] Adatgazdagság felmérése...")
    cursor.execute("""
        SELECT
            SUM(CASE WHEN szerzo IS NOT NULL AND szerzo != 'N/A' THEN 1 ELSE 0 END) as van_szerzo,
            SUM(CASE WHEN cim IS NOT NULL AND cim != '' THEN 1 ELSE 0 END) as van_cim,
            SUM(CASE WHEN kiado IS NOT NULL AND kiado != 'N/A' THEN 1 ELSE 0 END) as van_kiado,
            SUM(CASE WHEN kiadas_eve IS NOT NULL AND kiadas_eve != 'N/A' THEN 1 ELSE 0 END) as van_ev,
            SUM(CASE WHEN isbn IS NOT NULL AND isbn != 'N/A' THEN 1 ELSE 0 END) as van_isbn,
            SUM(CASE WHEN leiras IS NOT NULL AND leiras != '' THEN 1 ELSE 0 END) as van_leiras,
            SUM(CASE WHEN cimkek IS NOT NULL AND cimkek != '' THEN 1 ELSE 0 END) as van_cimkek,
            SUM(CASE WHEN sorozat IS NOT NULL AND sorozat != 'N/A' THEN 1 ELSE 0 END) as van_sorozat,
            SUM(CASE WHEN kep_utvonal IS NOT NULL AND kep_utvonal != '' THEN 1 ELSE 0 END) as van_boruto
        FROM konyvek
    """)
    adatgazdagsag_raw = cursor.fetchone()

    adatgazdagsag = {
        "szerzo":  {"db": adatgazdagsag_raw["van_szerzo"],  "szazalek": round(adatgazdagsag_raw["van_szerzo"]  / osszes * 100, 1)},
        "cim":     {"db": adatgazdagsag_raw["van_cim"],     "szazalek": round(adatgazdagsag_raw["van_cim"]     / osszes * 100, 1)},
        "kiado":   {"db": adatgazdagsag_raw["van_kiado"],   "szazalek": round(adatgazdagsag_raw["van_kiado"]   / osszes * 100, 1)},
        "ev":      {"db": adatgazdagsag_raw["van_ev"],      "szazalek": round(adatgazdagsag_raw["van_ev"]      / osszes * 100, 1)},
        "isbn":    {"db": adatgazdagsag_raw["van_isbn"],    "szazalek": round(adatgazdagsag_raw["van_isbn"]    / osszes * 100, 1)},
        "leiras":  {"db": adatgazdagsag_raw["van_leiras"],  "szazalek": round(adatgazdagsag_raw["van_leiras"]  / osszes * 100, 1)},
        "cimkek":  {"db": adatgazdagsag_raw["van_cimkek"],  "szazalek": round(adatgazdagsag_raw["van_cimkek"]  / osszes * 100, 1)},
        "sorozat": {"db": adatgazdagsag_raw["van_sorozat"], "szazalek": round(adatgazdagsag_raw["van_sorozat"] / osszes * 100, 1)},
        "boruto":  {"db": adatgazdagsag_raw["van_boruto"],  "szazalek": round(adatgazdagsag_raw["van_boruto"]  / osszes * 100, 1)},
    }

    # ── Fizikai fájlok (ha a fájlfelismerő már futott) ─────
    fizikai = {}
    try:
        cursor.execute("SELECT COUNT(*) as db FROM fizikai_fajlok")
        fizikai["osszes_fajl"] = cursor.fetchone()["db"]

        cursor.execute("""
            SELECT egyezes_szint, COUNT(*) as db
            FROM fizikai_fajlok
            GROUP BY egyezes_szint
        """)
        fizikai["egyezes_bontasban"] = {
            row["egyezes_szint"]: row["db"]
            for row in cursor.fetchall()
        }

        cursor.execute("""
            SELECT formatum, COUNT(*) as db
            FROM fizikai_fajlok
            GROUP BY formatum ORDER BY db DESC
        """)
        fizikai["formatum_bontasban"] = {
            row["formatum"]: row["db"]
            for row in cursor.fetchall()
        }
    except Exception:
        fizikai = {"megjegyzes": "A fájlfelismerő még nem futott (fazis1_fajlfelismero.py)"}

    conn.close()

    # ── Meta JSON összeállítás ─────────────────────────────
    meta = {
        "letrehozva":     datetime.now().isoformat(),
        "db_utvonal":     DB_PATH,
        "osszes_konyv":   osszes,
        "egyedi_szerzok": len(szerzo_osszes),

        "top_szerzok":    top_n(szerzo_counter, 50),
        "top_cimkek":     top_n(cimke_counter, 50),
        "top_kiadok":     top_n(kiado_counter, 30),
        "top_evek":       top_n(ev_counter, 30),
        "formatumok":     top_n(format_counter, 10),
        "sorozatok":      sorozatok[:50],

        "adatgazdagsag":  adatgazdagsag,
        "fizikai_fajlok": fizikai,

        # Gyors keresési segédletek a főprogramnak
        "minden_cimke":   sorted(list(cimke_counter.keys())),
        "minden_kiado":   sorted(list(kiado_counter.keys())),
    }

    # Mentés
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # ── Konzol összefoglaló ────────────────────────────────
    print(f"\n{'=' * 60}")
    print(f"  Összes könyv az adatbázisban: {osszes:,}")
    print(f"  Egyedi szerzők:               {len(szerzo_osszes):,}")
    print(f"\n  Adatgazdagság:")
    for mezo, stat in adatgazdagsag.items():
        print(f"    {mezo:<10}: {stat['db']:>7,} db  ({stat['szazalek']}%)")
    print(f"\n  Top 10 cimke:")
    for item in top_n(cimke_counter, 10):
        print(f"    {item['ertek']:<25} {item['db']:>5} könyv")
    print(f"\n  Top 10 kiadó:")
    for item in top_n(kiado_counter, 10):
        print(f"    {item['ertek']:<25} {item['db']:>5} könyv")
    print(f"\n{'=' * 60}")
    print(f"  Meta adatok elmentve: {META_PATH}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    elemez()
