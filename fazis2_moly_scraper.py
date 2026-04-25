
"""
KönyvtárAI - 2. fázis: Moly.hu adatgyűjtő
==========================================
Mit csinál:
  1. Bejelentkezik a moly.hu-ra
  2. Szerzőnként megkeresi a könyveiket
  3. Minden találatot elment az SQLite DB-be
  4. A fizikai_fajlok táblában frissíti az egyezéseket

Telepítés (egyszer):
  pip install requests beautifulsoup4

Futtatás:
  python fazis2_moly_scraper.py

Folytatható — a már lekért szerzőket kihagyja.
"""

import sqlite3
import requests
import time
import re
import json
import random

# .env fájl betöltése (ha létezik)
_env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(_env_path):
    with open(_env_path, encoding='utf-8') as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _v = _line.split('=', 1)
                os.environ.setdefault(_k.strip(), _v.strip())
import unicodedata
from bs4 import BeautifulSoup
from urllib.parse import quote
from datetime import datetime

# ============================================================
# BEÁLLÍTÁSOK
# ============================================================

DB_PATH   = r"H:\________________2026 FEjlesztesek\Ncore bővítés\ncore_konyvtar.db"
MOLY_BASE = "https://moly.hu"

# Moly.hu bejelentkezési adatok
# Ezeket a .env fájlban tárold (lásd: env.minta fájlt)
import os
MOLY_USER = os.getenv("MOLY_USER", "")   # felhasználónév
MOLY_PASS = os.getenv("MOLY_PASS", "")   # jelszó

# Kérések közötti szünet (másodperc) — ne terheljük az oldalt
DELAY_MIN = 1.2
DELAY_MAX = 2.8

# Hány egyedi szerzőt dolgozzon fel egy futásban (0 = mind)
LIMIT = 0

# ============================================================
# NORMALIZÁLÁS
# ============================================================

def norm(text: str) -> str:
    t = unicodedata.normalize('NFD', str(text))
    t = ''.join(c for c in t if unicodedata.category(c) != 'Mn')
    return t.lower().strip()


# ============================================================
# MOLY.HU SESSION
# ============================================================

def moly_login(user: str, password: str) -> requests.Session:
    """Bejelentkezik a moly.hu-ra és visszaadja a session-t."""
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'hu-HU,hu;q=0.9',
    })

    print("Moly.hu bejelentkezés...")

    # 1. Főoldal betöltése (a /felhasznalok/belepes átirányít ide)
    r = session.get(f"{MOLY_BASE}/", timeout=15)
    soup = BeautifulSoup(r.text, 'html.parser')

    # CSRF token a meta tagból
    csrf = None
    meta = soup.find('meta', {'name': 'csrf-token'})
    if meta:
        csrf = meta['content']

    # A bejelentkezési form megkeresése: amelyikben user_session[email] van
    login_form = None
    for form in soup.find_all('form'):
        if form.find('input', {'name': 'user_session[email]'}) or \
           form.find('input', {'name': 'felhasznalo[login]'}):
            login_form = form
            break

    if not login_form:
        # Próbáljuk közvetlenül a bejelentkezési oldalt (más URL-en lehet)
        r2 = session.get(f"{MOLY_BASE}/felhasznalok/belepes", timeout=15,
                         allow_redirects=False)
        if r2.status_code in (301, 302):
            pass  # átirányít, maradunk a főoldalnál
        else:
            soup2 = BeautifulSoup(r2.text, 'html.parser')
            csrf2 = soup2.find('meta', {'name': 'csrf-token'})
            if csrf2:
                csrf = csrf2['content']
            login_form = soup2.find('form')

    if not csrf:
        # Utolsó próba: form input
        for form in soup.find_all('form'):
            inp = form.find('input', {'name': 'authenticity_token'})
            if inp:
                csrf = inp.get('value')
                if not login_form:
                    login_form = form
                break

    if not csrf:
        raise RuntimeError("Nem sikerült a CSRF token megszerzése")

    # Form action URL és mezőnevek meghatározása
    if login_form and login_form.get('action'):
        action = login_form['action']
        form_action = MOLY_BASE + action if action.startswith('/') else action
    else:
        form_action = f"{MOLY_BASE}/felhasznalok/belepes"

    # Mezőnév detektálás (régi: felhasznalo[login], új: user_session[email])
    if login_form and login_form.find('input', {'name': 'user_session[email]'}):
        payload = {
            'authenticity_token': csrf,
            'user_session[email]': user,
            'user_session[password]': password,
            'commit': 'Belépés',
        }
    else:
        payload = {
            'authenticity_token': csrf,
            'felhasznalo[login]': user,
            'felhasznalo[password]': password,
            'felhasznalo[remember_me]': '1',
            'commit': 'Belépés',
        }

    print(f"  POST → {form_action}")

    # 2. Bejelentkezés POST
    r_post = session.post(
        form_action,
        data=payload,
        headers={'Referer': f"{MOLY_BASE}/"},
        timeout=15,
        allow_redirects=True
    )

    # Ellenőrzés: kijelentkezés link = be vagyunk jelentkezve
    sikeres_jelek = ['kijelentes', 'vezerlo', '/tagok/', 'sign_out', 'logout']
    for jel in sikeres_jelek:
        if jel in r_post.text or jel in r_post.url:
            print(f"  ✅ Bejelentkezve!")
            return session

    # Debug mentés ha nem sikerült
    debug_path = r"H:\________________2026 FEjlesztesek\Ncore bővítés\moly_login_debug.html"
    with open(debug_path, 'w', encoding='utf-8') as f:
        f.write(r_post.text)
    print(f"  ⚠️  Bejelentkezés kérdéses — debug: {debug_path}")
    print(f"  POST státusz: {r_post.status_code} | URL: {r_post.url}")
    # Folytatjuk — a keresés bejelentkezés nélkül is működik
    return session


def moly_get(session: requests.Session, url: str) -> BeautifulSoup:
    """Lekér egy oldalt és visszaadja BeautifulSoup-ként."""
    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
    r = session.get(url, timeout=20)
    r.raise_for_status()
    return BeautifulSoup(r.text, 'html.parser')


# ============================================================
# KERESÉS PARSE-OLÁS
# ============================================================

def parse_book_link(a_tag) -> dict:
    """
    Egy <a class="book_selector"> tagból kinyeri az adatokat.
    Pl: Rejtő Jenő (P. Howard): Piszkos Fred a kapitány
    """
    moly_id  = a_tag.get('data-id', '')
    href     = a_tag.get('href', '')
    fulltext = a_tag.get_text(' ', strip=True)

    # Szerző és cím szétválasztása ': ' mentén
    szerzo = cim = ''
    if ': ' in fulltext:
        reszek = fulltext.split(': ', 1)
        szerzo = reszek[0].strip()
        cim    = reszek[1].strip()
    else:
        cim = fulltext

    # Értékelés (a következő span.like_count-ban)
    ertekeles = ''
    next_span = a_tag.find_next_sibling('span', class_='like_count')
    if next_span:
        ertekeles = next_span.get_text(strip=True)

    # Sorozat (a következő a.action-ban)
    sorozat = ''
    next_a = a_tag.find_next_sibling('a', class_='action')
    if next_a:
        sorozat = next_a.get_text(strip=True).strip('()')

    return {
        'moly_id':    moly_id,
        'moly_url':   MOLY_BASE + href if href.startswith('/') else href,
        'moly_slug':  href.replace('/konyvek/', '').strip('/'),
        'szerzo':     szerzo,
        'cim':        cim,
        'ertekeles':  ertekeles,
        'sorozat':    sorozat,
    }


def search_author(session: requests.Session, szerzo: str) -> list:
    """
    Keres a moly.hu-n szerző neve alapján.
    Visszaadja a talált könyvek listáját.
    """
    url  = f"{MOLY_BASE}/kereses?query={quote(szerzo)}"
    soup = moly_get(session, url)

    konyvek = []
    for a in soup.select('p a.book_selector'):
        book = parse_book_link(a)
        if book['moly_id']:
            konyvek.append(book)

    # Ha van "Összes találat" link, lekérjük azt is
    osszes_link = soup.select_one('a.small_link[href*="konyvek/kereses"]')
    if osszes_link and len(konyvek) >= 10:
        osszes_url = MOLY_BASE + osszes_link['href']
        konyvek += search_all_books(session, osszes_url, max_pages=3)

    return konyvek


def search_all_books(session: requests.Session, url: str, max_pages: int = 3) -> list:
    """
    Lekéri a könyv-specifikus keresési oldalt (több találat, lapozható).
    """
    konyvek = []
    for page in range(1, max_pages + 1):
        paged_url = url + (f"&page={page}" if page > 1 else "")
        soup = moly_get(session, paged_url)

        talalt = soup.select('p a.book_selector')
        if not talalt:
            break

        for a in talalt:
            book = parse_book_link(a)
            if book['moly_id']:
                konyvek.append(book)

        # Ha kevesebb mint 20 találat volt, nincs több oldal
        if len(talalt) < 20:
            break

    return konyvek


def search_title(session: requests.Session, cim: str, szerzo: str = '') -> list:
    """Cím alapján keres — az ismeretlen fájlokhoz."""
    query = f"{cim} {szerzo}".strip() if szerzo else cim
    url   = f"{MOLY_BASE}/kereses?query={quote(query)}"
    soup  = moly_get(session, url)

    konyvek = []
    for a in soup.select('p a.book_selector'):
        book = parse_book_link(a)
        if book['moly_id']:
            konyvek.append(book)
    return konyvek


# ============================================================
# DB TÁBLA
# ============================================================

def create_moly_table(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS moly_adatok (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            moly_id        TEXT UNIQUE,
            moly_url       TEXT,
            moly_slug      TEXT,
            szerzo         TEXT,
            cim            TEXT,
            ertekeles      TEXT,
            sorozat        TEXT,
            konyv_id       INTEGER,
            letrehozva     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (konyv_id) REFERENCES konyvek(id)
        );
        CREATE INDEX IF NOT EXISTS idx_moly_konyv ON moly_adatok(konyv_id);
        CREATE INDEX IF NOT EXISTS idx_moly_szerzo ON moly_adatok(szerzo);

        CREATE TABLE IF NOT EXISTS moly_kereses_naplo (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            kereses    TEXT UNIQUE,
            db         INTEGER,
            letrehozva TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()


def mar_keresve(conn, kereses: str) -> bool:
    """Visszaadja hogy ezt a keresést már elvégeztük-e."""
    cur = conn.execute(
        "SELECT 1 FROM moly_kereses_naplo WHERE kereses = ?", (kereses,)
    )
    return cur.fetchone() is not None


def naplo_ment(conn, kereses: str, db: int):
    conn.execute(
        "INSERT OR REPLACE INTO moly_kereses_naplo (kereses, db) VALUES (?, ?)",
        (kereses, db)
    )
    conn.commit()


def moly_ment(conn, konyvek: list, konyv_id_map: dict = None):
    """Moly találatokat ment az adatbázisba."""
    for k in konyvek:
        konyv_id = None
        if konyv_id_map and k['moly_id'] in konyv_id_map:
            konyv_id = konyv_id_map[k['moly_id']]

        try:
            conn.execute("""
                INSERT OR REPLACE INTO moly_adatok
                (moly_id, moly_url, moly_slug, szerzo, cim,
                 ertekeles, sorozat, konyv_id)
                VALUES (?,?,?,?,?,?,?,?)
            """, (
                k['moly_id'], k['moly_url'], k['moly_slug'],
                k['szerzo'], k['cim'],
                k['ertekeles'], k['sorozat'], konyv_id
            ))
        except Exception:
            pass  # duplikált moly_id esetén nem gond

    conn.commit()


# ============================================================
# EGYEZTETÉS — moly találat ↔ fizikai fájl
# ============================================================

def egyeztet_fajlokkal(conn: sqlite3.Connection):
    """
    A moly_adatok tábla alapján frissíti a fizikai_fajlok táblát:
    ahol volt moly találat, ott beírja a moly_id-t és az egyezési szintet.
    """
    cols = [r[1] for r in conn.execute("PRAGMA table_info(fizikai_fajlok)")]
    if 'moly_id' not in cols:
        conn.execute("ALTER TABLE fizikai_fajlok ADD COLUMN moly_id TEXT")
        conn.commit()

    cur = conn.cursor()

    cur.execute("""
        SELECT id, fajl_nev, talalat_szerzo
        FROM fizikai_fajlok
        WHERE egyezes_szint = 'szerzo_ismert'
        AND moly_id IS NULL
        AND talalat_szerzo IS NOT NULL
    """)
    fajlok = cur.fetchall()

    frissitve = 0
    for (fid, fajl_nev, szerzo) in fajlok:
        cur2 = conn.execute("""
            SELECT moly_id, cim FROM moly_adatok
            WHERE lower(szerzo) LIKE ?
            LIMIT 50
        """, (f'%{norm(szerzo.split()[0])}%',))
        moly_konyvek = cur2.fetchall()

        if not moly_konyvek:
            continue

        from pathlib import Path
        fn_norm = norm(Path(fajl_nev).stem)

        best_id, best_sc = None, 0
        for (mid, cim) in moly_konyvek:
            if not cim:
                continue
            cim_n = norm(cim)
            if cim_n in fn_norm:
                sc = 95
            else:
                szavak = [s for s in cim_n.split() if len(s) > 3]
                egyezik = sum(1 for s in szavak if s in fn_norm)
                sc = int(egyezik / max(len(szavak), 1) * 85) if szavak else 0

            if sc > best_sc:
                best_sc, best_id = sc, mid

        if best_id and best_sc >= 60:
            conn.execute("""
                UPDATE fizikai_fajlok
                SET moly_id = ?, egyezes_szint = 'moly_fuzzy'
                WHERE id = ?
            """, (best_id, fid))
            frissitve += 1

    conn.commit()
    return frissitve


# ============================================================
# FŐ FOLYAMAT
# ============================================================

def run():
    print("=" * 65)
    print("  KönyvtárAI — Moly.hu adatgyűjtő")
    print("=" * 65)
    print(f"  Indítva: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    if not MOLY_PASS:
        print("❌ Hiányzó jelszó!")
        print("   Nyisd meg a fazis2_moly_scraper.py fájlt és")
        print("   írd be a jelszavadat a MOLY_PASS = '' sorba.\n")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    create_moly_table(conn)

    try:
        session = moly_login(MOLY_USER, MOLY_PASS)
    except Exception as e:
        print(f"❌ {e}")
        conn.close()
        return

    cur = conn.cursor()

    cur.execute("""
        SELECT DISTINCT talalat_szerzo, COUNT(*) as db
        FROM fizikai_fajlok
        WHERE egyezes_szint = 'szerzo_ismert'
        AND talalat_szerzo IS NOT NULL
        GROUP BY talalat_szerzo
        ORDER BY db DESC
    """)
    szerzok = [(r[0], r[1], 'szerzo_ismert') for r in cur.fetchall()]

    if LIMIT > 0:
        szerzok = szerzok[:LIMIT]

    print(f"Feldolgozandó szerzők: {len(szerzok):,}\n")

    ossz_talalt = 0
    ossz_kereses = 0

    for i, (szerzo, fajl_db, _) in enumerate(szerzok, 1):
        if mar_keresve(conn, szerzo):
            continue

        print(f"  [{i:>4}/{len(szerzok)}] {szerzo} ({fajl_db} fájl)...")

        try:
            konyvek = search_author(session, szerzo)
            moly_ment(conn, konyvek)
            naplo_ment(conn, szerzo, len(konyvek))
            ossz_talalt += len(konyvek)
            ossz_kereses += 1
            print(f"         → {len(konyvek)} könyv találva")

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                print("  ⚠️  Rate limit — várok 30 másodpercet...")
                time.sleep(30)
            else:
                print(f"  ❌ HTTP hiba: {e}")
        except Exception as e:
            print(f"  ❌ Hiba ({szerzo}): {e}")

        if ossz_kereses % 20 == 0 and ossz_kereses > 0:
            print("  ... rövid szünet ...")
            time.sleep(random.uniform(5, 10))

    print("\nEgyeztetés a fizikai fájlokkal...")
    frissitve = egyeztet_fajlokkal(conn)
    print(f"  {frissitve} fájl frissítve moly adattal")

    cur.execute("SELECT COUNT(*) FROM moly_adatok")
    ossz_moly = cur.fetchone()[0]

    cur.execute("""
        SELECT egyezes_szint, COUNT(*) FROM fizikai_fajlok
        GROUP BY egyezes_szint
    """)
    szintek = dict(cur.fetchall())

    print(f"\n{'=' * 65}")
    print(f"  Kész: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 65}")
    print(f"  Moly DB-ben tárolt könyvek: {ossz_moly:,}")
    print(f"  Ebben a futásban keresett:  {ossz_kereses:,} szerző")
    print(f"  Talált moly könyv:          {ossz_talalt:,}")
    print(f"\n  Fizikai fájlok státusza:")
    for szint, db in sorted(szintek.items(), key=lambda x: -x[1]):
        print(f"    {szint:<20} {db:>7,}")
    print(f"{'=' * 65}")

    conn.close()


if __name__ == '__main__':
    run()
