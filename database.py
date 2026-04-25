"""
Adatbázis kezelő modul
======================
SQLite műveletek: tábla létrehozás, CRUD, keresés
"""

import sqlite3
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

from config import get

# Tábla séma
SCHEMA = """
CREATE TABLE IF NOT EXISTS konyvek (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ncore_id TEXT UNIQUE NOT NULL,
    szerzo TEXT,
    cim TEXT,
    kep_utvonal TEXT,
    meret TEXT,
    feltoltve_datum TEXT,
    cimkek TEXT,
    leiras TEXT,
    buy_link TEXT,
    teljes_link TEXT,
    formatum TEXT,
    kiado TEXT,
    kiadas_eve TEXT,
    isbn TEXT,
    sorozat TEXT,
    sorozat_szama TEXT,
    letrehozva TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_feltoltve ON konyvek(feltoltve_datum DESC)",
    "CREATE INDEX IF NOT EXISTS idx_szerzo ON konyvek(szerzo)",
    "CREATE INDEX IF NOT EXISTS idx_cim ON konyvek(cim)",
    "CREATE INDEX IF NOT EXISTS idx_formatum ON konyvek(formatum)",
    "CREATE INDEX IF NOT EXISTS idx_isbn ON konyvek(isbn)",
]


@contextmanager
def get_connection():
    """Context manager az adatbázis kapcsolathoz."""
    db_path = get("database_path", "ncore_konyvtar.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Dict-szerű sorok
    try:
        yield conn
    finally:
        conn.close()


def init_database():
    """Adatbázis és indexek létrehozása."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(SCHEMA)
        
        # ISBN oszlop hozzáadása, ha régi DB
        try:
            cursor.execute("SELECT isbn FROM konyvek LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE konyvek ADD COLUMN isbn TEXT")
            print("  [DB] 'isbn' oszlop hozzáadva.")
        
        for idx_sql in INDEXES:
            cursor.execute(idx_sql)
        
        conn.commit()


def get_latest_date() -> Optional[str]:
    """Legfrissebb feltöltési dátum lekérése."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(feltoltve_datum) FROM konyvek")
        result = cursor.fetchone()
        return result[0] if result else None


def get_oldest_date() -> Optional[str]:
    """Legrégebbi feltöltési dátum lekérése."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT MIN(feltoltve_datum) FROM konyvek")
        result = cursor.fetchone()
        return result[0] if result else None


def get_oldest_ncore_id() -> Optional[str]:
    """Legkisebb ncore_id lekérése (legrégebbi torrent)."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT ncore_id FROM konyvek ORDER BY CAST(ncore_id AS INTEGER) ASC LIMIT 1")
        result = cursor.fetchone()
        return result[0] if result else None


def book_exists(ncore_id: str) -> bool:
    """Létezik-e már a könyv az adatbázisban?"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM konyvek WHERE ncore_id = ?", (ncore_id,))
        return cursor.fetchone() is not None


def save_book(book: Dict[str, Any]) -> bool:
    """Könyv mentése vagy frissítése."""
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO konyvek (
                    ncore_id, szerzo, cim, kep_utvonal, meret, feltoltve_datum,
                    cimkek, leiras, buy_link, teljes_link, formatum, kiado,
                    kiadas_eve, isbn, sorozat, sorozat_szama
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                book.get("ncore_id"),
                book.get("szerzo"),
                book.get("cim"),
                book.get("kep_utvonal"),
                book.get("meret"),
                book.get("feltoltve_datum"),
                book.get("cimkek"),
                book.get("leiras"),
                book.get("buy_link"),
                book.get("teljes_link"),
                book.get("formatum"),
                book.get("kiado"),
                book.get("kiadas_eve"),
                book.get("isbn"),
                book.get("sorozat"),
                book.get("sorozat_szama"),
            ))
            conn.commit()
            return True
        except sqlite3.Error:
            return False


def search_books(
    query: str = "",
    formatum: Optional[str] = None,
    limit: int = 0,
    offset: int = 0,
    order_by: str = "feltoltve_datum",
    desc: bool = True
) -> List[Dict]:
    """Könyvek keresése. limit=0 esetén összes könyvet visszaadja."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        where_clauses = []
        params = []
        
        if query:
            where_clauses.append(
                "(cim LIKE ? OR szerzo LIKE ? OR cimkek LIKE ?"
                " OR ncore_id LIKE ? OR sorozat LIKE ?)"
            )
            q = f"%{query}%"
            params.extend([q, q, q, q, q])
        
        if formatum:
            where_clauses.append("formatum = ?")
            params.append(formatum)
        
        where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        order_dir = "DESC" if desc else "ASC"
        
        # Ha limit = 0, akkor nincs LIMIT
        if limit > 0:
            sql = f"""
                SELECT * FROM konyvek
                {where_sql}
                ORDER BY {order_by} {order_dir}
                LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])
        else:
            sql = f"""
                SELECT * FROM konyvek
                {where_sql}
                ORDER BY {order_by} {order_dir}
            """
        
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]


def get_book_by_id(book_id: int) -> Optional[Dict]:
    """Könyv lekérése ID alapján."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM konyvek WHERE id = ?", (book_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_book_by_ncore_id(ncore_id: str) -> Optional[Dict]:
    """Könyv lekérése nCore ID alapján."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM konyvek WHERE ncore_id = ?", (ncore_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def count_books(query: str = "", formatum: Optional[str] = None) -> int:
    """Könyvek számolása (kereséshez)."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        where_clauses = []
        params = []
        
        if query:
            where_clauses.append(
                "(cim LIKE ? OR szerzo LIKE ? OR cimkek LIKE ?"
                " OR ncore_id LIKE ? OR sorozat LIKE ?)"
            )
            q = f"%{query}%"
            params.extend([q, q, q, q, q])
        
        if formatum:
            where_clauses.append("formatum = ?")
            params.append(formatum)
        
        where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
        cursor.execute(f"SELECT COUNT(*) FROM konyvek {where_sql}", params)
        return cursor.fetchone()[0]


def get_formats() -> List[str]:
    """Elérhető formátumok listája."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT formatum FROM konyvek 
            WHERE formatum IS NOT NULL AND formatum != '' AND formatum != 'N/A'
            ORDER BY formatum
        """)
        return [row[0] for row in cursor.fetchall()]


def get_statistics() -> Dict[str, Any]:
    """Adatbázis statisztikák."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM konyvek")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT MIN(feltoltve_datum), MAX(feltoltve_datum) FROM konyvek")
        date_range = cursor.fetchone()
        
        cursor.execute("""
            SELECT formatum, COUNT(*) as cnt FROM konyvek 
            WHERE formatum IS NOT NULL AND formatum != ''
            GROUP BY formatum ORDER BY cnt DESC
        """)
        formats = {row[0]: row[1] for row in cursor.fetchall()}
        
        return {
            "total": total,
            "oldest": date_range[0],
            "newest": date_range[1],
            "formats": formats,
        }


# Érvényes (szerkeszthető) oszlopnevek a konyvek táblában
_VALID_COLUMNS = {
    "szerzo", "cim", "formatum", "kiado", "kiadas_eve", "isbn",
    "sorozat", "sorozat_szama", "meret", "cimkek", "leiras",
    "kep_utvonal", "buy_link", "teljes_link",
}


def update_book_field(ncore_id: str, column: str, value: Any) -> bool:
    """Egy könyv egyetlen mezőjének frissítése.

    Args:
        ncore_id: A torrent azonosítója (elsődleges keresési kulcs).
        column: Az oszlop neve (csak a _VALID_COLUMNS-ban lévők engedélyezettek).
        value: Az új érték.

    Returns:
        True ha sikeres, False ha hiba történt.
    """
    if column not in _VALID_COLUMNS:
        return False
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                f"UPDATE konyvek SET {column} = ? WHERE ncore_id = ?",
                (value, ncore_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error:
            return False


# ====================== BIZTONSÁGI MENTÉS ======================

import shutil
from datetime import datetime as _dt
from pathlib import Path as _Path

# Mentések almappája (az adatbázis mellé kerül)
_BACKUP_DIR_NAME = "backups"


def _get_db_path() -> _Path:
    """Az adatbázis fájl teljes elérési útja."""
    return _Path(get("database_path", "ncore_konyvtar.db")).resolve()


def _get_backup_dir() -> _Path:
    """A mentések mappa elérési útja (létrehozza, ha nem létezik)."""
    backup_dir = _get_db_path().parent / _BACKUP_DIR_NAME
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def create_backup(label: str = "") -> Optional[str]:
    """Biztonsági mentés készítése az adatbázisról.

    Args:
        label: Opcionális címke a fájlnévben (pl. "scraping_elott").

    Returns:
        A mentés fájl elérési útja, vagy None ha hiba történt.
    """
    db_path = _get_db_path()
    if not db_path.exists():
        return None

    backup_dir = _get_backup_dir()
    timestamp = _dt.now().strftime("%Y%m%d_%H%M%S")
    label_part = f"_{label}" if label else ""
    backup_name = f"ncore_konyvtar_{timestamp}{label_part}.db"
    backup_path = backup_dir / backup_name

    try:
        # SQLite safe backup: VACUUM INTO (nem zárolja a fő DB-t)
        with get_connection() as conn:
            conn.execute(f"VACUUM INTO '{backup_path}'")
        return str(backup_path)
    except sqlite3.Error:
        # Fallback: egyszerű fájlmásolás
        try:
            shutil.copy2(str(db_path), str(backup_path))
            return str(backup_path)
        except OSError:
            return None


def list_backups() -> List[Dict[str, Any]]:
    """Elérhető mentések listázása.

    Returns:
        Lista: [{"path": str, "name": str, "date": str, "size_mb": float}, ...]
        Dátum szerint csökkenő sorrendben (legfrissebb elöl).
    """
    backup_dir = _get_backup_dir()
    backups = []
    for f in backup_dir.glob("ncore_konyvtar_*.db"):
        stat = f.stat()
        # Fájlnévből próbáljuk kiolvasni a dátumot
        try:
            # "ncore_konyvtar_20250227_143022.db" vagy "_label.db"
            date_part = f.stem.replace("ncore_konyvtar_", "")[:15]
            date_str = _dt.strptime(date_part, "%Y%m%d_%H%M%S").strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        except ValueError:
            date_str = _dt.fromtimestamp(stat.st_mtime).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        backups.append({
            "path": str(f),
            "name": f.name,
            "date": date_str,
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
        })
    backups.sort(key=lambda x: x["date"], reverse=True)
    return backups


def restore_backup(backup_path: str) -> bool:
    """Adatbázis visszaállítása egy mentésből.

    Előbb biztonsági mentést készít az aktuálisról ("visszaallas_elott"),
    majd felülírja a fő adatbázist a kiválasztott mentéssel.

    Args:
        backup_path: A visszaállítandó mentés fájl elérési útja.

    Returns:
        True ha sikeres.
    """
    backup = _Path(backup_path)
    if not backup.exists():
        return False

    db_path = _get_db_path()

    # Biztonsági mentés az aktuálisról, mielőtt felülírnánk
    create_backup(label="visszaallitas_elott")

    try:
        shutil.copy2(str(backup), str(db_path))
        return True
    except OSError:
        return False


def delete_backup(backup_path: str) -> bool:
    """Egy mentés törlése.

    Args:
        backup_path: A törlendő fájl elérési útja.

    Returns:
        True ha sikeres.
    """
    try:
        p = _Path(backup_path)
        if p.exists() and p.parent == _get_backup_dir():
            p.unlink()
            return True
        return False
    except OSError:
        return False
