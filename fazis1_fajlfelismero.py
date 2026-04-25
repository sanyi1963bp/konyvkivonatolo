"""
KönyvtárAI - 1. fázis: Fájlfelismerő motor (v2 - 4 minta)
===========================================================
Felismeri ezeket a fájlnév-formátumokat:

  1. Szerző - Cím.ext                     (alap)
  2. Meszoly.Agnes-A.kupolak.2020.HUN.EPUB.Ebook-WhoAmI  (ncore torrent)
  3. Cím (Szerző) (z-library.sk).ext      (Z-Library)
  4. barath_katalin_a_cim.ext             (kisbetűs, ékezet nélküli)

Telepítés (egyszer):
  pip install rapidfuzz tqdm

Futtatás:
  python fazis1_fajlfelismero.py

Ha megszakad, folytatható — a már kész fájlokat kihagyja.
"""

import sqlite3
import os
import re
import json
import unicodedata
from pathlib import Path
from datetime import datetime

try:
    from rapidfuzz import fuzz
except ImportError:
    print("❌ Hiányzó: pip install rapidfuzz tqdm")
    exit(1)

try:
    from tqdm import tqdm
    VAN_TQDM = True
except ImportError:
    VAN_TQDM = False

# ============================================================
# BEÁLLÍTÁSOK
# ============================================================

DB_PATH = r"H:\________________2026 FEjlesztesek\Ncore bővítés\ncore_konyvtar.db"

BOOK_FOLDERS = [
    r"X:\________Könyvek\_______Textben\____Szépirodalom",
]

SUPPORTED_FORMATS = {
    '.pdf', '.epub', '.doc', '.docx',
    '.txt', '.rtf', '.mobi', '.azw', '.azw3', '.fb2', '.prc'
}

AUTHOR_THRESHOLD = 78
TITLE_THRESHOLD  = 60
BATCH_SIZE       = 500

# ============================================================
# NORMALIZÁLÁS
# ============================================================

def norm(text: str) -> str:
    """Ékezetek le, kisbetű, elválasztók → szóköz."""
    t = unicodedata.normalize('NFD', str(text))
    t = ''.join(c for c in t if unicodedata.category(c) != 'Mn')
    t = t.lower()
    t = re.sub(r'[_\-\.\(\)\[\]\"\'\/\\]+', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


# ============================================================
# FÁJLNÉV ELŐFELDOLGOZÁS — a négy minta kezelése
# ============================================================

# ncore zajok amiket le kell vágni
NCORE_TAGS = re.compile(
    r'\b(HUN|ENG|GER|hun|eng)\b'
    r'|\b(EPUB|PDF|MOBI|AZW3|RTF|DOCX|FB2|PRC|LIT)\b'
    r'|\bEbook\b'
    r'|\bebook\b'
    r'|\b(19|20)\d{2}\b'
    r'|\b[A-Z][a-z]{1,3}[A-Z]\w{1,10}\b'  # CamelCase csoportnév (WhoAmI, UpByOM)
    r'|\s*-\s*[A-Z][a-zA-Z0-9]{3,15}$'     # -WhoAmI a végén
, re.IGNORECASE)

# Z-Library jelölők
ZLIB_TAGS = re.compile(
    r'\(z-lib(?:rary)?(?:\.[a-z]{1,4})*(?:,\s*[0-9a-z\.\-]+)*\)'
    r'|\(Z-Library\)'
    r'|\(1lib\.[a-z]+\)'
    r'|\([0-9a-z\.\-]+lib[^)]*\)'
, re.IGNORECASE)

# Ismétlődő cím (pl. "Cselszovok - Cselszovok")
def van_ismetles(nev: str) -> bool:
    reszek = re.split(r'\s*-\s*', nev, maxsplit=1)
    if len(reszek) == 2:
        return norm(reszek[0]) == norm(reszek[1])
    return False


def feldolgoz_fajlnev(nev_ext_nelkul: str) -> dict:
    """
    Fájlnév elemzése — felismeri a mintát és kinyeri
    a szerző/cím tippeket ahol lehet.

    Visszaad:
      pattern:     'alap' | 'ncore' | 'zlibrary' | 'ismeretlen'
      szerzo_hint: kinyert szerzőnév (vagy None)
      cim_hint:    kinyert cím (vagy None)
      clean_norm:  normalizált, megtisztított fájlnév
    """
    nev = nev_ext_nelkul.strip()

    # ── Z-Library minta ──────────────────────────────────────
    # Cím (Szerző Neve) (z-library.sk, 1lib.sk).epub
    if ZLIB_TAGS.search(nev) or '(Z-Library)' in nev or 'z-lib' in nev.lower():
        tiszta = ZLIB_TAGS.sub('', nev).strip()
        # Utolsó zárójel = szerző
        zp = re.search(r'\(([^)]{3,50})\)\s*$', tiszta)
        if zp:
            szerzo_hint = zp.group(1).strip()
            cim_hint    = re.sub(r'\([^)]*\)\s*$', '', tiszta).strip()
            # Számot a cím elejéről levágjuk (pl. "2. Akkon ostroma")
            cim_hint = re.sub(r'^\d+\.\s*', '', cim_hint)
            return {
                'pattern': 'zlibrary',
                'szerzo_hint': szerzo_hint,
                'cim_hint': cim_hint,
                'clean_norm': norm(cim_hint + ' ' + szerzo_hint)
            }

    # ── ncore torrent minta ───────────────────────────────────
    # Meszoly.Agnes-A.kupolak.titka.2020.HUN.EPUB.Ebook-WhoAmI
    if re.search(r'\.(HUN|ENG|EPUB|MOBI|Ebook)\b', nev, re.IGNORECASE) or \
       re.search(r'\b(19|20)\d{2}\b', nev) and '.' in nev:

        tiszta = NCORE_TAGS.sub(' ', nev)
        tiszta = re.sub(r'\s+', ' ', tiszta).strip()

        # Pontok → szóközök, majd keressük a ' - ' elválasztót
        tiszta_szok = tiszta.replace('.', ' ')
        reszek = re.split(r'\s+-\s+|\s*-\s+(?=[A-ZÁÉÍÓÖŐÚÜŰ])', tiszta_szok, maxsplit=1)

        if len(reszek) == 2:
            return {
                'pattern': 'ncore',
                'szerzo_hint': reszek[0].strip(),
                'cim_hint': reszek[1].strip(),
                'clean_norm': norm(tiszta_szok)
            }
        return {
            'pattern': 'ncore',
            'szerzo_hint': None,
            'cim_hint': None,
            'clean_norm': norm(tiszta_szok)
        }

    # ── Alap "Szerző - Cím" vagy "Cím - Szerző" minta ────────
    if ' - ' in nev and not van_ismetles(nev):
        # Levágjuk a felesleges suffixeket (pl. -upByOM)
        tiszta = re.sub(r'\s*-\s*[a-zA-Z]{2,8}[A-Z]{2}\w*$', '', nev)
        reszek = tiszta.split(' - ', maxsplit=1)
        if len(reszek) == 2:
            bal, jobb = reszek[0].strip(), reszek[1].strip()
            return {
                'pattern': 'alap',
                'szerzo_hint': bal,
                'cim_hint': jobb,
                'clean_norm': norm(tiszta)
            }
        # A suffix-levágás után már nincs ' - ' → általános keresés
        return {
            'pattern': 'alap',
            'szerzo_hint': None,
            'cim_hint': None,
            'clean_norm': norm(tiszta)
        }

    # ── Kisbetűs, ékezet nélküli, aláhúzásos ─────────────────
    # barath_katalin_a_turkizkek_hegedu
    # → a normalizálás már kezeli, de explicit felismerjük
    if '_' in nev or (nev == nev.lower() and '-' not in nev):
        return {
            'pattern': 'kisbetus',
            'szerzo_hint': None,
            'cim_hint': None,
            'clean_norm': norm(nev)
        }

    # ── Ismeretlen ────────────────────────────────────────────
    return {
        'pattern': 'ismeretlen',
        'szerzo_hint': None,
        'cim_hint': None,
        'clean_norm': norm(nev)
    }


# ============================================================
# INDEX ÉPÍTÉS
# ============================================================

def build_indexes(conn):
    print("Index betöltése az adatbázisból...")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, cim, szerzo FROM konyvek
        WHERE cim IS NOT NULL AND cim != ''
    """)
    osszes = cursor.fetchall()

    vezeteknev_idx = {}   # norm_szo → {eredeti_szerző, ...}
    szerzo_konyvek = {}   # eredeti_szerző → [(id, norm_cim), ...]

    for (kid, cim, szerzo) in osszes:
        if not szerzo or szerzo.strip() in ('', 'N/A'):
            continue

        szerzok = re.split(r'\s*[–;\/]\s*|\s*,\s*(?=[A-ZÁÉÍÓÖŐÚÜŰ])', szerzo)
        for sz in szerzok:
            sz = sz.strip()
            if len(sz) < 3:
                continue
            sz_norm = norm(sz)
            for szo in sz_norm.split():
                if len(szo) >= 3:
                    vezeteknev_idx.setdefault(szo, set()).add(szerzo)
            szerzo_konyvek.setdefault(szerzo, []).append((kid, norm(cim)))

    print(f"  {len(vezeteknev_idx):,} névszó  |  "
          f"{len(szerzo_konyvek):,} szerző  |  "
          f"{len(osszes):,} könyv\n")
    return vezeteknev_idx, szerzo_konyvek


# ============================================================
# SZERZŐ KERESÉS
# ============================================================

def find_author(info: dict, vezeteknev_idx: dict, szerzo_konyvek: dict) -> tuple:
    """
    Kétlépéses keresés:
    1. Ha van szerzo_hint → azt ellenőrizzük először
    2. Ha nincs → szótár alapú keresés a clean_norm-ban
    """
    fname_norm = info['clean_norm']

    # Ha van közvetlen tipp (alap vagy zlibrary vagy ncore minta)
    if info.get('szerzo_hint'):
        hint_norm = norm(info['szerzo_hint'])
        # Keressük a legjobb egyezést a hint alapján
        jeloltek = set()
        for szo in hint_norm.split():
            if szo in vezeteknev_idx:
                jeloltek.update(vezeteknev_idx[szo])

        if jeloltek:
            best_sz, best_sc = None, 0
            for sz in jeloltek:
                sc = fuzz.ratio(hint_norm, norm(sz))
                if sc > best_sc:
                    best_sc, best_sz = sc, sz
            if best_sc >= AUTHOR_THRESHOLD:
                return best_sz, best_sc

    # Ha van cim_hint is (alap minta) — próbáljuk fordítva (Cím - Szerző)
    if info.get('cim_hint') and info['pattern'] == 'alap':
        hint_norm = norm(info['cim_hint'])
        jeloltek = set()
        for szo in hint_norm.split():
            if szo in vezeteknev_idx:
                jeloltek.update(vezeteknev_idx[szo])
        if jeloltek:
            best_sz, best_sc = None, 0
            for sz in jeloltek:
                sc = fuzz.ratio(hint_norm, norm(sz))
                if sc > best_sc:
                    best_sc, best_sz = sc, sz
            if best_sc >= AUTHOR_THRESHOLD:
                return best_sz, best_sc

    # Szótár alapú keresés a teljes normalizált névben
    jeloltek = set()
    for szo in fname_norm.split():
        if szo in vezeteknev_idx:
            jeloltek.update(vezeteknev_idx[szo])

    best_sz, best_sc = None, 0
    for sz in jeloltek:
        sz_norm = norm(sz)
        sc = fuzz.partial_ratio(sz_norm, fname_norm) if len(sz_norm) >= 7 \
             else (90 if sz_norm in fname_norm else 0)
        if sc > best_sc:
            best_sc, best_sz = sc, sz

    if best_sc >= AUTHOR_THRESHOLD:
        return best_sz, best_sc
    return None, 0


# ============================================================
# KÖNYV KERESÉS
# ============================================================

def find_book(info: dict, szerzo: str, szerzo_konyvek: dict) -> tuple:
    """Memóriából keres — nem DB lekérdezés."""
    if szerzo not in szerzo_konyvek:
        return None, None, 0

    fname_norm = info['clean_norm']
    cim_hint   = norm(info['cim_hint']) if info.get('cim_hint') else None

    best_id, best_cim, best_sc = None, None, 0

    for (kid, cim_norm) in szerzo_konyvek[szerzo]:
        if not cim_norm:
            continue

        # Ha van cím tipp, azt preferáljuk
        if cim_hint:
            sc = fuzz.ratio(cim_hint, cim_norm)
            if sc < TITLE_THRESHOLD:
                sc = fuzz.partial_ratio(cim_norm, cim_hint)
        else:
            if cim_norm in fname_norm:
                sc = 96
            else:
                sc = fuzz.partial_ratio(cim_norm, fname_norm)

        if sc > best_sc:
            best_sc, best_id, best_cim = sc, kid, cim_norm

    if best_sc >= TITLE_THRESHOLD:
        return best_id, best_cim, best_sc
    return None, None, 0


# ============================================================
# DB TÁBLA
# ============================================================

def create_table(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS fizikai_fajlok (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            fajl_utvonal    TEXT UNIQUE NOT NULL,
            fajl_nev        TEXT,
            formatum        TEXT,
            konyv_id        INTEGER,
            talalat_szerzo  TEXT,
            talalat_cim     TEXT,
            egyezes_szint   TEXT,
            minta           TEXT,
            szerzo_szazalek REAL DEFAULT 0,
            cim_szazalek    REAL DEFAULT 0,
            letrehozva      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (konyv_id) REFERENCES konyvek(id)
        );
        CREATE INDEX IF NOT EXISTS idx_ff_konyv ON fizikai_fajlok(konyv_id);
        CREATE INDEX IF NOT EXISTS idx_ff_szint ON fizikai_fajlok(egyezes_szint);
        CREATE INDEX IF NOT EXISTS idx_ff_minta ON fizikai_fajlok(minta);
    """)
    conn.commit()


def szint(szerzo_pct, cim_pct, konyv_id) -> str:
    if konyv_id is None:
        return 'szerzo_ismert' if szerzo_pct > 0 else 'ismeretlen'
    if szerzo_pct >= 88 and cim_pct >= 85:
        return 'pontos'
    if szerzo_pct >= AUTHOR_THRESHOLD and cim_pct >= TITLE_THRESHOLD:
        return 'fuzzy'
    return 'gyenge'


# ============================================================
# FÁJLOK ÖSSZEGYŰJTÉSE
# ============================================================

def collect_files(mappak):
    fajlok = []
    for mappa in mappak:
        if not os.path.exists(mappa):
            print(f"⚠️  Nem találom: {mappa}")
            continue
        for root, dirs, files in os.walk(mappa):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for fn in files:
                if Path(fn).suffix.lower() in SUPPORTED_FORMATS:
                    fajlok.append(os.path.join(root, fn))
    return fajlok


# ============================================================
# FŐ FOLYAMAT
# ============================================================

def scan():
    print("=" * 65)
    print("  KönyvtárAI — Fájlfelismerő v2 (4 mintával)")
    print("=" * 65)
    print(f"  Indítva: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    create_table(conn)

    vezeteknev_idx, szerzo_konyvek = build_indexes(conn)

    # Már kész fájlok kihagyása
    cursor = conn.cursor()
    cursor.execute("SELECT fajl_utvonal FROM fizikai_fajlok")
    mar_kesz = {r[0] for r in cursor.fetchall()}
    print(f"Már feldolgozott: {len(mar_kesz):,} fájl → ezeket kihagyja\n")

    print("Fájlok összeszámlálása...")
    minden = collect_files(BOOK_FOLDERS)
    feldolgozando = [f for f in minden if f not in mar_kesz]
    print(f"  Összes: {len(minden):,}  |  Feldolgozandó: {len(feldolgozando):,}\n")

    if not feldolgozando:
        print("✅ Minden fájl feldolgozva!")
        conn.close()
        return

    stat   = {}
    mintak = {}
    batch  = []

    iterator = tqdm(feldolgozando, unit='fájl', dynamic_ncols=True) \
               if VAN_TQDM else feldolgozando

    for i, full_path in enumerate(iterator, 1):
        fn      = Path(full_path).name
        ext     = Path(full_path).suffix.lower()
        stem    = Path(full_path).stem

        # Fájlnév elemzése
        info = feldolgoz_fajlnev(stem)
        mintak[info['pattern']] = mintak.get(info['pattern'], 0) + 1

        # Szerző keresés
        szerzo, szerzo_pct = find_author(info, vezeteknev_idx, szerzo_konyvek)

        # Könyv keresés
        konyv_id = talalat_cim = None
        cim_pct  = 0
        if szerzo:
            konyv_id, talalat_cim, cim_pct = find_book(
                info, szerzo, szerzo_konyvek
            )

        s = szint(szerzo_pct, cim_pct, konyv_id)
        stat[s] = stat.get(s, 0) + 1

        batch.append((
            full_path, fn, ext.lstrip('.'),
            konyv_id, szerzo, talalat_cim,
            s, info['pattern'],
            round(szerzo_pct, 1), round(cim_pct, 1)
        ))

        if len(batch) >= BATCH_SIZE:
            conn.executemany("""
                INSERT OR REPLACE INTO fizikai_fajlok
                (fajl_utvonal, fajl_nev, formatum, konyv_id,
                 talalat_szerzo, talalat_cim,
                 egyezes_szint, minta, szerzo_szazalek, cim_szazalek)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, batch)
            conn.commit()
            batch.clear()

        if not VAN_TQDM and i % 2000 == 0:
            print(f"  {i:>7,}/{len(feldolgozando):,}  "
                  f"pontos:{stat.get('pontos',0)}  "
                  f"fuzzy:{stat.get('fuzzy',0)}  "
                  f"ism.:{stat.get('ismeretlen',0)}")

    if batch:
        conn.executemany("""
            INSERT OR REPLACE INTO fizikai_fajlok
            (fajl_utvonal, fajl_nev, formatum, konyv_id,
             talalat_szerzo, talalat_cim,
             egyezes_szint, minta, szerzo_szazalek, cim_szazalek)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, batch)
        conn.commit()

    # ── Összesítő ─────────────────────────────────────────────
    ossz = len(feldolgozando)
    print(f"\n{'=' * 65}")
    print(f"  Kész: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 65}")
    print(f"  Feldolgozott:             {ossz:>8,}")
    print(f"  🟢 Pontos:                {stat.get('pontos',0):>8,}  "
          f"({stat.get('pontos',0)/max(ossz,1)*100:.1f}%)")
    print(f"  🟡 Fuzzy:                 {stat.get('fuzzy',0):>8,}  "
          f"({stat.get('fuzzy',0)/max(ossz,1)*100:.1f}%)")
    print(f"  🔵 Csak szerző:           {stat.get('szerzo_ismert',0):>8,}  "
          f"({stat.get('szerzo_ismert',0)/max(ossz,1)*100:.1f}%)")
    print(f"  ⚪ Ismeretlen:            {stat.get('ismeretlen',0):>8,}  "
          f"({stat.get('ismeretlen',0)/max(ossz,1)*100:.1f}%)")
    print(f"\n  Fájlnév minták:")
    for m, db in sorted(mintak.items(), key=lambda x: -x[1]):
        print(f"    {m:<15} {db:>7,} fájl")
    print(f"{'=' * 65}")

    summary_path = os.path.join(os.path.dirname(DB_PATH), "fazis1_eredmeny.json")
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump({**stat, 'osszes': ossz, 'mintak': mintak,
                   'ido': datetime.now().isoformat()},
                  f, ensure_ascii=False, indent=2)
    print(f"\n  Elmentve: {summary_path}")
    print("  Következő: python fazis1_meta_elemzo.py\n")
    conn.close()


if __name__ == '__main__':
    scan()
