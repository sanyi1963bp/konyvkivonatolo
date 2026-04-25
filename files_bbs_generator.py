"""
FILES.BBS Generátor modul v2
==============================
Rekurzívan bejárja a megadott mappát, megkeresi a könyv fájlokat,
az adatbázisból kikeresi a hozzájuk tartozó metaadatokat,
és minden mappába FILES.BBS leíró fájlt generál.

FILES.BBS formátum (soronként):
    fájlnév.ext  |  Szerző  |  Cím  |  [Sorozat]  |  (Kiadó, Év)  |  Leírás

Gyors párosítás:
  1. Előre felépít egy szó-indexet az adatbázisból (szerző + cím szavai → könyv)
  2. A fájlnév szavaival keres az indexben (halmazmetszet alapú pontozás)
  3. Csak a jelölteket vizsgálja részletesen (nem az összes könyvet!)
  → Több tízezer könyves adatbázisnál is gyors
"""

import os
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Optional, Dict, List, Callable, Tuple
from difflib import SequenceMatcher

from database import search_books


# Támogatott könyv kiterjesztések
BOOK_EXTENSIONS = {
    ".epub", ".pdf", ".mobi", ".azw", ".azw3", ".fb2", ".lit",
    ".txt", ".rtf", ".doc", ".docx", ".odt", ".djvu", ".cbr", ".cbz",
}

# FILES.BBS fájl neve
BBS_FILENAME = "FILES.BBS"

# Stopszavak - ezeket kihagyjuk az indexelésből
_STOP_WORDS = {
    "a", "az", "es", "is", "nem", "egy", "the", "and", "of", "in",
    "to", "for", "on", "at", "by", "with", "from", "or", "an",
}


def _normalize(text: str) -> str:
    """Szöveg normalizálása: kisbetű, ékezet nélkül, csak alfanumerikus."""
    if not text:
        return ""
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r'[_\-–—\.,:;!?\(\)\[\]\{\}\'\"«»„"\'\'\#\&]+', ' ', text)
    text = re.sub(r'\(z-library\)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'_?upby\w*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _tokenize(text: str) -> List[str]:
    """Normalizált szöveg szavakra bontása, stopszavak kiszűrésével."""
    normalized = _normalize(text)
    words = normalized.split()
    return [w for w in words if len(w) >= 2 and w not in _STOP_WORDS]


def _parse_filename(filename: str) -> Tuple[str, str, str]:
    """Fájlnévből szerző és cím kinyerése.

    Returns: (szerzo, cim, kiterjesztes)
    """
    stem = Path(filename).stem
    ext = Path(filename).suffix.lower()

    for sep in [" - ", " – ", " — "]:
        if sep in stem:
            parts = stem.split(sep, 1)
            szerzo = parts[0].strip()
            cim = parts[1].strip()
            cim = re.sub(r'\s*\([^)]*\)\s*$', '', cim).strip()
            return szerzo, cim, ext

    cim = re.sub(r'\s*\([^)]*\)\s*$', '', stem).strip()
    return "", cim, ext


# ====================== GYORS INDEX-ALAPÚ KERESÉS ======================

class BookIndex:
    """Szó-index az adatbázis könyveihez a gyors kereséshez.

    Működés:
      - Minden könyv szerző+cím szavait indexeli (szó → könyv ID-k halmaz)
      - Kereséskor a fájlnév szavaival keres az indexben
      - Csak azokat a könyveket vizsgálja SequenceMatcher-rel,
        amelyeknek legalább 1 szava egyezik (jelöltek)
      - Így a keresés O(szavak_száma) a teljes O(n) helyett
    """

    def __init__(self, books: List[Dict]):
        self.books = {i: book for i, book in enumerate(books)}
        self.word_index: Dict[str, set] = defaultdict(set)
        self._build_index()

    def _build_index(self):
        """Szó-index felépítése."""
        for idx, book in self.books.items():
            szerzo = book.get("szerzo", "") or ""
            cim = book.get("cim", "") or ""
            for word in _tokenize(szerzo):
                self.word_index[word].add(idx)
            for word in _tokenize(cim):
                self.word_index[word].add(idx)

    def find_best(self, szerzo: str, cim: str) -> Optional[Dict]:
        """A legjobban illeszkedő könyv megkeresése.

        1. fázis: szó-index alapján jelöltek szűkítése
        2. fázis: jelölteken belül SequenceMatcher pontozás
        """
        if not cim and not szerzo:
            return None

        query_words = _tokenize(f"{szerzo} {cim}")
        if not query_words:
            return None

        # Jelöltek keresése szóegyezés alapján
        candidate_scores: Dict[int, int] = defaultdict(int)
        for word in query_words:
            # Pontos szóegyezés
            if word in self.word_index:
                for idx in self.word_index[word]:
                    candidate_scores[idx] += 2

            # Részleges egyezés hosszabb szavaknál
            if len(word) >= 4:
                for indexed_word, book_ids in self.word_index.items():
                    if len(indexed_word) >= 4:
                        if word in indexed_word or indexed_word in word:
                            for idx in book_ids:
                                candidate_scores[idx] += 1

        if not candidate_scores:
            return None

        # Top 20 jelölt
        top_candidates = sorted(
            candidate_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )[:20]

        # SequenceMatcher finomítás csak a jelölteken
        norm_szerzo = _normalize(szerzo)
        norm_cim = _normalize(cim)

        best_score = 0.0
        best_book = None

        for idx, _ in top_candidates:
            book = self.books[idx]
            db_szerzo = _normalize(book.get("szerzo", "") or "")
            db_cim = _normalize(book.get("cim", "") or "")

            if norm_szerzo:
                s_score = SequenceMatcher(None, norm_szerzo, db_szerzo).ratio()
                c_score = SequenceMatcher(None, norm_cim, db_cim).ratio()
                score = s_score * 0.4 + c_score * 0.6
            else:
                score = SequenceMatcher(None, norm_cim, db_cim).ratio()

            if score > best_score:
                best_score = score
                best_book = book

        if best_score >= 0.50:
            return best_book

        return None


# ====================== BBS FORMÁZÁS ======================

def _format_bbs_line(filename: str, book: Optional[Dict], max_desc_len: int = 200) -> str:
    """Egy FILES.BBS sor formázása."""
    if not book:
        return filename

    parts = [filename]

    szerzo = book.get("szerzo", "") or ""
    cim = book.get("cim", "") or ""
    leiras = book.get("leiras", "") or ""
    kiado = book.get("kiado", "") or ""
    ev = book.get("kiadas_eve", "") or ""
    sorozat = book.get("sorozat", "") or ""
    sorozat_szama = book.get("sorozat_szama", "") or ""
    isbn = book.get("isbn", "") or ""

    if szerzo:
        parts.append(szerzo)
    if cim:
        parts.append(cim)

    if sorozat:
        sor_info = sorozat
        if sorozat_szama:
            sor_info += f" #{sorozat_szama}"
        parts.append(f"[{sor_info}]")

    meta = []
    if kiado:
        meta.append(kiado)
    if ev:
        meta.append(ev)
    if isbn:
        meta.append(f"ISBN: {isbn}")
    if meta:
        parts.append("(" + ", ".join(meta) + ")")

    if leiras:
        desc = re.sub(r'\s+', ' ', leiras).strip()
        if len(desc) > max_desc_len:
            desc = desc[:max_desc_len].rsplit(' ', 1)[0] + "..."
        parts.append(desc)

    return "  |  ".join(parts)


# ====================== FŐ GENERÁTOR ======================

def generate_files_bbs(
    root_path: str,
    log_callback: Optional[Callable[[str], None]] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    stop_flag: Optional[Callable[[], bool]] = None,
    overwrite: bool = True,
    max_desc_len: int = 200,
) -> Dict[str, int]:
    """FILES.BBS fájlok generálása rekurzívan.

    Args:
        root_path: A gyökérmappa útvonala
        log_callback: Naplózó függvény
        progress_callback: Haladás jelző (aktuális, összesen)
        stop_flag: Megállító flag
        overwrite: Felülírja-e a meglévő FILES.BBS fájlokat
        max_desc_len: Leírás max hossza

    Returns:
        Statisztikák dict
    """
    log = log_callback or (lambda msg: None)
    progress = progress_callback or (lambda cur, tot: None)
    should_stop = stop_flag or (lambda: False)

    stats = {
        "dirs_processed": 0,
        "files_found": 0,
        "files_matched": 0,
        "bbs_created": 0,
        "bbs_skipped": 0,
    }

    if not os.path.isdir(root_path):
        log(f"❌ A mappa nem létezik: {root_path}")
        return stats

    # Adatbázis betöltése és index felépítése
    log("📚 Adatbázis betöltése és indexelése...")
    all_books = search_books(query="", limit=0, order_by="cim", desc=False)
    log(f"   {len(all_books)} könyv az adatbázisban")

    if not all_books:
        log("❌ Az adatbázis üres! Előbb tölts le adatokat a scraperrel.")
        return stats

    book_index = BookIndex(all_books)
    log(f"   Index felépítve: {len(book_index.word_index)} egyedi szó")

    # Mappák összegyűjtése
    log("🔍 Mappák keresése...")
    dirs_with_books: List[Tuple[str, List[str]]] = []

    for dirpath, dirnames, filenames in os.walk(root_path):
        if should_stop():
            log("🛑 Megszakítva!")
            return stats

        book_files = [
            f for f in filenames
            if Path(f).suffix.lower() in BOOK_EXTENSIONS
            and f.upper() != BBS_FILENAME
        ]

        if book_files:
            dirs_with_books.append((dirpath, book_files))

    total_dirs = len(dirs_with_books)
    log(f"   {total_dirs} mappa tartalmaz könyv fájlokat")

    if total_dirs == 0:
        log("⚠ Nem találtam könyv fájlokat a megadott mappában!")
        return stats

    # Feldolgozás mappánként
    for dir_idx, (dirpath, book_files) in enumerate(dirs_with_books):
        if should_stop():
            log("🛑 Megszakítva!")
            break

        progress(dir_idx + 1, total_dirs)
        rel_path = os.path.relpath(dirpath, root_path)

        bbs_path = Path(dirpath) / BBS_FILENAME

        if bbs_path.exists() and not overwrite:
            stats["bbs_skipped"] += 1
            continue

        stats["dirs_processed"] += 1
        bbs_lines = []
        dir_matched = 0

        for filename in sorted(book_files):
            stats["files_found"] += 1

            szerzo, cim, ext = _parse_filename(filename)
            best = book_index.find_best(szerzo, cim)

            if best:
                stats["files_matched"] += 1
                dir_matched += 1

            line = _format_bbs_line(filename, best, max_desc_len)
            bbs_lines.append(line)

        # FILES.BBS írása
        if bbs_lines:
            try:
                bbs_path.write_text(
                    "\n".join(bbs_lines) + "\n",
                    encoding="utf-8"
                )
                if bbs_path.exists():
                    stats["bbs_created"] += 1
                    log(f"✅ {rel_path}: {dir_matched}/{len(book_files)} párosítva → {bbs_path}")
                else:
                    log(f"⚠ {rel_path}: írás sikeres de fájl nem található!")
            except OSError as e:
                log(f"❌ {rel_path}: írási hiba - {e}")
            except Exception as e:
                log(f"❌ {rel_path}: váratlan hiba - {type(e).__name__}: {e}")

    # Összesítés
    log("")
    log("=" * 50)
    log("📊 FILES.BBS generálás összesítés:")
    log(f"   Feldolgozott mappák:  {stats['dirs_processed']}")
    log(f"   Talált könyv fájlok:  {stats['files_found']}")
    log(f"   DB-vel párosított:    {stats['files_matched']}")
    log(f"   FILES.BBS létrehozva: {stats['bbs_created']}")
    if stats["bbs_skipped"]:
        log(f"   Átugorva (létező):    {stats['bbs_skipped']}")
    log("=" * 50)

    return stats
