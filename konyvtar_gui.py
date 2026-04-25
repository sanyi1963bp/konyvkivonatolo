#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KönyvtárAI — Főprogram
=======================
PyQt6-alapú könyvtárkezelő és AI asszisztens.

Telepítés:
  pip install PyQt6

Futtatás:
  python konyvtar_gui.py
"""

import sys, os, sqlite3, json, shutil, threading, csv
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QSplitter,
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QCheckBox, QButtonGroup,
    QListWidget, QComboBox, QScrollArea, QTextEdit,
    QTreeView, QProgressBar, QInputDialog, QMessageBox,
    QSizePolicy, QFrame
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QDir, QSize, QTimer
)
from PyQt6.QtGui import (
    QPixmap, QPainter, QColor, QPen, QFont, QIcon, QFileSystemModel
)

try:
    import requests as req
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# ══════════════════════════════════════════════════════════════
# KONFIGURÁCIÓ
# ══════════════════════════════════════════════════════════════

DB_PATH    = r"H:\________________2026 FEjlesztesek\Ncore bővítés\ncore_konyvtar.db"
META_PATH  = r"H:\________________2026 FEjlesztesek\Ncore bővítés\meta.json"
COVER_DIR      = Path(r"H:\________________2026 FEjlesztesek\Ncore bővítés\boritos_cache")
HISTORY_PATH   = Path(r"H:\________________2026 FEjlesztesek\Ncore bővítés\kereses_elozmenyek.json")
OLLAMA_URL     = "http://localhost:11434"
PAGE_SIZE  = 48
CARD_W     = 155
CARD_H     = 245
COVER_W    = 130
COVER_H    = 182

COVER_DIR.mkdir(exist_ok=True)

# Egyezési szint → szín (bal border a kártyán)
STATUS_COL = {
    'pontos':        '#2ecc71',
    'fuzzy':         '#27ae60',
    'moly_fuzzy':    '#3498db',
    'szerzo_ismert': '#f39c12',
    'ismeretlen':    '#e74c3c',
}
NO_FILE_COL = '#3a3a5c'

# ══════════════════════════════════════════════════════════════
# DARK THEME
# ══════════════════════════════════════════════════════════════

STYLE = """
* { font-family: 'Segoe UI', Arial, sans-serif; }
QMainWindow, QDialog { background: #111122; }
QWidget { background: #111122; color: #dde1ec; font-size: 13px; }
QSplitter::handle { background: #1e1e3a; }
QSplitter::handle:horizontal { width: 2px; }
QSplitter::handle:vertical { height: 2px; }

QScrollArea { border: none; background: transparent; }
QScrollBar:vertical {
    background: #1a1a30; width: 7px; border-radius: 3px; margin: 0;
}
QScrollBar::handle:vertical {
    background: #3a3a5c; border-radius: 3px; min-height: 20px;
}
QScrollBar::handle:vertical:hover { background: #e94560; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QLineEdit {
    background: #1e1e3a; border: 1px solid #2a2a50;
    border-radius: 8px; padding: 7px 12px; color: #dde1ec;
}
QLineEdit:focus { border-color: #e94560; }

QPushButton {
    background: #1e1e3a; border: 1px solid #2a2a50;
    border-radius: 7px; padding: 6px 14px; color: #dde1ec;
}
QPushButton:hover { background: #2a2a50; border-color: #e94560; }
QPushButton:pressed { background: #e94560; border-color: #e94560; color: white; }
QPushButton:checked { background: #e94560; border-color: #e94560; color: white; }
QPushButton:disabled { color: #444466; border-color: #1e1e3a; background: #161628; }

QListWidget {
    background: #1a1a30; border: 1px solid #2a2a50;
    border-radius: 8px; outline: none;
}
QListWidget::item { padding: 4px 8px; border-radius: 4px; }
QListWidget::item:hover { background: #2a2a50; }
QListWidget::item:selected { background: #e94560; color: white; }

QComboBox {
    background: #1e1e3a; border: 1px solid #2a2a50;
    border-radius: 7px; padding: 6px 10px; color: #dde1ec;
}
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background: #1e1e3a; border: 1px solid #2a2a50;
    selection-background-color: #e94560; outline: none;
}

QTextEdit {
    background: #1a1a30; border: 1px solid #2a2a50;
    border-radius: 8px; padding: 8px; color: #dde1ec;
}

QTreeView {
    background: #1a1a30; border: 1px solid #2a2a50;
    border-radius: 8px; color: #dde1ec; outline: none;
}
QTreeView::item { padding: 3px 6px; }
QTreeView::item:hover { background: #2a2a50; }
QTreeView::item:selected { background: #e94560; color: white; }
QHeaderView::section {
    background: #1e1e3a; color: #778; border: none;
    padding: 4px; font-size: 11px;
}

QProgressBar {
    background: #1e1e3a; border: 1px solid #2a2a50;
    border-radius: 6px; text-align: center; height: 16px;
    font-size: 11px;
}
QProgressBar::chunk { background: #e94560; border-radius: 5px; }

QCheckBox { color: #dde1ec; spacing: 6px; }
QCheckBox::indicator {
    width: 16px; height: 16px; border-radius: 4px;
    border: 2px solid #3a3a5c; background: #1a1a30;
}
QCheckBox::indicator:checked {
    background: #e94560; border-color: #e94560;
}

QFrame[frameShape="4"], QFrame[frameShape="5"] {
    color: #2a2a50;
}
"""

# ══════════════════════════════════════════════════════════════
# ADATBÁZIS RÉTEG
# ══════════════════════════════════════════════════════════════

class DB:
    _inst = None

    @classmethod
    def get(cls):
        if cls._inst is None:
            cls._inst = cls()
        return cls._inst

    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA cache_size=10000")
        self._lock = threading.Lock()
        self._init_user_tables()

    def _init_user_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS felhasznalo_adatok (
                konyv_id        INTEGER PRIMARY KEY,
                statusz         TEXT,
                sajat_ertekeles INTEGER,
                megjegyzes      TEXT,
                letrehozva      TEXT,
                modositva       TEXT,
                FOREIGN KEY (konyv_id) REFERENCES konyvek(id)
            );
        """)
        self.conn.commit()

    def query(self, sql, params=()):
        with self._lock:
            return self.conn.execute(sql, params).fetchall()

    def one(self, sql, params=()):
        with self._lock:
            return self.conn.execute(sql, params).fetchone()

    def set_user_data(self, konyv_id: int, statusz: str = None,
                      ertekeles: int = None, megjegyzes: str = None):
        """Olvasási státusz és/vagy értékelés mentése."""
        now = datetime.now().isoformat()
        with self._lock:
            existing = self.conn.execute(
                "SELECT * FROM felhasznalo_adatok WHERE konyv_id=?",
                (konyv_id,)).fetchone()
            if existing:
                fields, vals = [], []
                if statusz  is not None: fields.append("statusz=?");         vals.append(statusz)
                if ertekeles is not None: fields.append("sajat_ertekeles=?"); vals.append(ertekeles)
                if megjegyzes is not None: fields.append("megjegyzes=?");    vals.append(megjegyzes)
                fields.append("modositva=?"); vals.append(now)
                vals.append(konyv_id)
                self.conn.execute(
                    f"UPDATE felhasznalo_adatok SET {', '.join(fields)} WHERE konyv_id=?",
                    vals)
            else:
                self.conn.execute("""
                    INSERT INTO felhasznalo_adatok
                    (konyv_id, statusz, sajat_ertekeles, megjegyzes, letrehozva, modositva)
                    VALUES (?,?,?,?,?,?)
                """, (konyv_id, statusz, ertekeles, megjegyzes, now, now))
            self.conn.commit()

    def get_user_data(self, konyv_id: int) -> dict:
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM felhasznalo_adatok WHERE konyv_id=?",
                (konyv_id,)).fetchone()
        return dict(row) if row else {}

    def close(self):
        self.conn.close()
        DB._inst = None


CALIBRE_VIEWER = r"C:\Program Files\Calibre2\ebook-viewer.exe"

def open_book(book: dict):
    """Dupla kattintásra megnyitja a könyvet Calibre-rel vagy alapértelmezett programmal."""
    import subprocess
    fajl = book.get('fajl_utvonal')
    if not fajl:
        QMessageBox.information(
            None, "Nincs fájl",
            f"Ehhez a könyvhöz nincs letöltött fájl.\n\n"
            f"{book.get('cim', '')}")
        return
    if not os.path.exists(fajl):
        QMessageBox.warning(
            None, "Fájl nem található",
            f"A fájl nem létezik vagy áthelyezték:\n{fajl}")
        return
    # Calibre-rel próbálunk először
    if os.path.exists(CALIBRE_VIEWER):
        subprocess.Popen([CALIBRE_VIEWER, fajl])
    else:
        # Rendszer alapértelmezett program
        os.startfile(fajl)


def build_sql(filters: dict, page: int):
    w, p = [], []

    s = filters.get('search', '').strip()
    if s:
        w.append("(k.cim LIKE ? OR k.szerzo LIKE ?)")
        p += [f"%{s}%", f"%{s}%"]

    st = filters.get('statusz', 'mind')
    if st == 'van_fajl':
        w.append("f.id IS NOT NULL")
    elif st == 'csak_adat':
        w.append("f.id IS NULL")
    elif st == 'csak_fajl':
        w.append("f.id IS NOT NULL AND (k.leiras IS NULL OR k.leiras = '')")

    fmt = filters.get('formatum')
    if fmt:
        w.append(f"f.formatum IN ({','.join('?'*len(fmt))})")
        p += list(fmt)

    if filters.get('cimke'):
        w.append("k.cimkek LIKE ?")
        p.append(f"%{filters['cimke']}%")

    if filters.get('szerzo'):
        w.append("k.szerzo LIKE ?")
        p.append(f"%{filters['szerzo']}%")

    # Felhasználói olvasási státusz szűrő
    user_st = filters.get('user_statusz')
    if user_st == 'olvasni_akarom':
        w.append("u.statusz = 'olvasni_akarom'")
    elif user_st == 'olvasom':
        w.append("u.statusz = 'olvasom'")
    elif user_st == 'elolvastam':
        w.append("u.statusz = 'elolvastam'")
    elif user_st == 'ertekelt':
        w.append("u.sajat_ertekeles IS NOT NULL")

    where = ("WHERE " + " AND ".join(w)) if w else ""
    base = f"""
        FROM konyvek k
        LEFT JOIN fizikai_fajlok f ON f.konyv_id = k.id
        LEFT JOIN moly_adatok m ON m.konyv_id = k.id
        LEFT JOIN felhasznalo_adatok u ON u.konyv_id = k.id
        {where}
    """
    cnt = f"SELECT COUNT(DISTINCT k.id) {base}"
    sel = f"""
        SELECT DISTINCT
            k.id, k.cim, k.szerzo, k.kiado, k.kiadas_eve,
            k.kep_utvonal, k.leiras, k.cimkek, k.sorozat, k.isbn,
            f.fajl_utvonal, f.formatum, f.egyezes_szint,
            m.ertekeles, m.moly_url,
            u.statusz as user_statusz, u.sajat_ertekeles
        {base}
        ORDER BY k.cim
        LIMIT {PAGE_SIZE} OFFSET {page * PAGE_SIZE}
    """
    return sel, list(p), cnt, list(p)


# ══════════════════════════════════════════════════════════════
# WORKER SZÁLAK
# ══════════════════════════════════════════════════════════════

class BooksWorker(QThread):
    done  = pyqtSignal(list, int)
    error = pyqtSignal(str)

    def __init__(self, filters, page):
        super().__init__()
        self.filters = filters
        self.page    = page

    def run(self):
        try:
            db = DB.get()
            sel, p, cnt, cp = build_sql(self.filters, self.page)
            rows  = db.query(sel, p)
            total = db.one(cnt, cp)[0]
            self.done.emit([dict(r) for r in rows], total)
        except Exception as e:
            self.error.emit(str(e))


class CoverWorker(QThread):
    done = pyqtSignal(int, QPixmap)

    def __init__(self, book_id, url_or_path):
        super().__init__()
        self.book_id     = book_id
        self.url_or_path = url_or_path

    def run(self):
        if not self.url_or_path:
            return
        cache = COVER_DIR / f"{self.book_id}.jpg"
        try:
            if cache.exists():
                px = QPixmap(str(cache))
                if not px.isNull():
                    self.done.emit(self.book_id, px)
                    return
            uop = self.url_or_path
            if uop.startswith('http') and HAS_REQUESTS:
                r = req.get(uop, timeout=8)
                if r.status_code == 200:
                    cache.write_bytes(r.content)
                    px = QPixmap()
                    px.loadFromData(r.content)
                    if not px.isNull():
                        self.done.emit(self.book_id, px)
            elif os.path.exists(uop):
                px = QPixmap(uop)
                if not px.isNull():
                    self.done.emit(self.book_id, px)
        except Exception:
            pass


class AIWorker(QThread):
    chunk = pyqtSignal(str)
    done  = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, prompt: str, model: str):
        super().__init__()
        self.prompt = prompt
        self.model  = model

    def run(self):
        if not HAS_REQUESTS:
            self.error.emit("A 'requests' könyvtár hiányzik.\n  pip install requests")
            return
        try:
            r = req.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": self.model, "prompt": self.prompt, "stream": True},
                stream=True, timeout=90
            )
            for line in r.iter_lines():
                if line:
                    d = json.loads(line)
                    if d.get('response'):
                        self.chunk.emit(d['response'])
                    if d.get('done'):
                        break
            self.done.emit()
        except Exception as e:
            self.error.emit(str(e))


class CopyWorker(QThread):
    progress = pyqtSignal(int, int, str)
    done     = pyqtSignal(int, int)

    def __init__(self, files: list, dest: Path):
        super().__init__()
        self.files = files
        self.dest  = dest

    def run(self):
        ok, fail = 0, 0
        for i, src in enumerate(self.files):
            try:
                name = Path(src).name
                self.progress.emit(i + 1, len(self.files), name)
                shutil.copy2(src, self.dest / name)
                ok += 1
            except Exception:
                fail += 1
        self.done.emit(ok, fail)


# ══════════════════════════════════════════════════════════════
# KÖNYVKÁRTYA
# ══════════════════════════════════════════════════════════════

class BookCard(QWidget):
    clicked  = pyqtSignal(dict)
    toggled  = pyqtSignal(dict, bool)

    _PLACEHOLDER = None

    def __init__(self, book: dict, parent=None):
        super().__init__(parent)
        self.book      = book
        self._sel      = False
        self.setFixedSize(CARD_W, CARD_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._build()

    @classmethod
    def placeholder(cls) -> QPixmap:
        if cls._PLACEHOLDER is None:
            px = QPixmap(COVER_W, COVER_H)
            px.fill(QColor('#1a1a30'))
            p = QPainter(px)
            p.setPen(QColor('#3a3a5c'))
            p.setFont(QFont('Segoe UI Emoji', 36))
            p.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, '📖')
            p.end()
            cls._PLACEHOLDER = px
        return cls._PLACEHOLDER

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 8)
        lay.setSpacing(3)

        # Checkbox sor
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.addStretch()
        self.chk = QCheckBox()
        self.chk.stateChanged.connect(self._on_check)
        top.addWidget(self.chk)
        lay.addLayout(top)

        # Borítókép
        self.cover = QLabel()
        self.cover.setFixedSize(COVER_W, COVER_H)
        self.cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._set_placeholder()
        lay.addWidget(self.cover, 0, Qt.AlignmentFlag.AlignHCenter)

        # Cím
        cim = (self.book.get('cim') or 'Ismeretlen')[:55]
        tl = QLabel(cim)
        tl.setWordWrap(True)
        tl.setFixedWidth(CARD_W - 16)
        tl.setMaximumHeight(32)
        tl.setStyleSheet("font-size:11px; font-weight:600; color:#dde1ec;")
        tl.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        lay.addWidget(tl)

        # Szerző
        szerzo = (self.book.get('szerzo') or '')[:40]
        al = QLabel(szerzo)
        al.setFixedWidth(CARD_W - 16)
        al.setMaximumHeight(16)
        al.setStyleSheet("font-size:10px; color:#778;")
        al.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(al)

        # Olvasási státusz + saját értékelés sor
        bot = QHBoxLayout()
        bot.setContentsMargins(0, 0, 0, 0)
        self.status_icon = QLabel("")
        self.status_icon.setStyleSheet("font-size:12px;")
        bot.addWidget(self.status_icon)
        bot.addStretch()
        self.stars_lbl = QLabel("")
        self.stars_lbl.setStyleSheet("font-size:10px; color:#f39c12;")
        bot.addWidget(self.stars_lbl)
        lay.addLayout(bot)
        self._refresh_user_data()

    def _set_placeholder(self):
        self.cover.setPixmap(self.placeholder().scaled(
            COVER_W, COVER_H,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))

    def set_cover(self, px: QPixmap):
        self.cover.setPixmap(px.scaled(
            COVER_W, COVER_H,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))

    def _refresh_user_data(self):
        st = self.book.get('user_statusz')
        icons = {'olvasni_akarom': '📖', 'olvasom': '📚', 'elolvastam': '✅'}
        self.status_icon.setText(icons.get(st, ''))
        n = self.book.get('sajat_ertekeles') or 0
        self.stars_lbl.setText('★' * n if n else '')

    def set_selected(self, v: bool):
        self._sel = v
        self.chk.blockSignals(True)
        self.chk.setChecked(v)
        self.chk.blockSignals(False)
        self.update()

    def _on_check(self, state):
        self._sel = bool(state)
        self.toggled.emit(self.book, self._sel)
        self.update()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.book)

    def mouseDoubleClickEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            open_book(self.book)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Háttér
        bg = QColor('#252540' if self._sel else '#1a1a30')
        p.setBrush(bg)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, CARD_W, CARD_H, 10, 10)

        # Bal oldali státusz sáv
        szint = self.book.get('egyezes_szint')
        col = STATUS_COL.get(szint, NO_FILE_COL)
        p.setBrush(QColor(col))
        p.drawRoundedRect(0, 0, 4, CARD_H, 2, 2)

        # Kijelölés keret
        if self._sel:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor('#e94560'), 2))
            p.drawRoundedRect(1, 1, CARD_W - 2, CARD_H - 2, 10, 10)


# ══════════════════════════════════════════════════════════════
# BAL PANEL — SZŰRŐK
# ══════════════════════════════════════════════════════════════

class FilterPanel(QWidget):
    changed = pyqtSignal(dict)

    def __init__(self, meta: dict, parent=None):
        super().__init__(parent)
        self.meta = meta
        self.setFixedWidth(224)
        self.setStyleSheet("background: #16162a;")
        self._history = self._load_history()
        self._build()

    def _section(self, text: str, lay):
        l = QLabel(text)
        l.setStyleSheet(
            "font-size:10px; font-weight:bold; color:#556; "
            "letter-spacing:1px; padding: 8px 0 2px 2px;")
        lay.addWidget(l)

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 12, 10, 12)
        lay.setSpacing(4)

        # Fejléc
        h = QLabel("📚 KönyvtárAI")
        h.setStyleSheet("font-size:16px; font-weight:bold; color:#e94560; padding-bottom:6px;")
        lay.addWidget(h)

        # Keresés + előzmények
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍 Cím vagy szerző...")
        self.search.textChanged.connect(self._on_search_changed)
        self.search.returnPressed.connect(self._save_search)
        lay.addWidget(self.search)

        # Előzmény lista (rejtett, kereséskor jelenik meg)
        self.history_list = QListWidget()
        self.history_list.setMaximumHeight(120)
        self.history_list.setVisible(False)
        self.history_list.itemClicked.connect(self._pick_history)
        lay.addWidget(self.history_list)

        # Státusz
        self._section("STÁTUSZ", lay)
        self.status_grp = QButtonGroup(self)
        self.status_grp.setExclusive(True)
        grid = QGridLayout()
        grid.setSpacing(4)
        statuses = [
            ("Mind", "mind"), ("Van fájl", "van_fajl"),
            ("Csak adat", "csak_adat"), ("Csak fájl", "csak_fajl"),
        ]
        for i, (lbl, val) in enumerate(statuses):
            b = QPushButton(lbl)
            b.setCheckable(True)
            b.setProperty('val', val)
            b.setFixedHeight(28)
            if val == 'mind':
                b.setChecked(True)
            self.status_grp.addButton(b, i)
            grid.addWidget(b, i // 2, i % 2)
        lay.addLayout(grid)
        self.status_grp.buttonClicked.connect(lambda _: self._emit())

        # Olvasási státusz
        self._section("OLVASÁSI LISTA", lay)
        self.user_grp = QButtonGroup(self)
        self.user_grp.setExclusive(True)
        user_statuszok = [
            ("Mind", ""),
            ("📖 Olvasni akarom", "olvasni_akarom"),
            ("📚 Olvasom", "olvasom"),
            ("✅ Elolvastam", "elolvastam"),
            ("⭐ Értékeltem", "ertekelt"),
        ]
        for i, (lbl, val) in enumerate(user_statuszok):
            b = QPushButton(lbl)
            b.setCheckable(True)
            b.setProperty('uval', val)
            b.setFixedHeight(26)
            if val == "":
                b.setChecked(True)
            self.user_grp.addButton(b, i)
            lay.addWidget(b)
        self.user_grp.buttonClicked.connect(lambda _: self._emit())

        # Formátum
        self._section("FORMÁTUM", lay)
        fmt_wrap = QHBoxLayout()
        fmt_wrap.setSpacing(4)
        self.fmt_cbs = {}
        for fmt in ['epub', 'pdf', 'mobi', 'azw3', 'fb2']:
            cb = QCheckBox(fmt)
            cb.setStyleSheet("font-size:11px;")
            cb.stateChanged.connect(lambda _: self._emit())
            self.fmt_cbs[fmt] = cb
            fmt_wrap.addWidget(cb)
        lay.addLayout(fmt_wrap)

        # Cimkék
        self._section("CIMKÉK (top 30)", lay)
        self.tag_list = QListWidget()
        self.tag_list.setMaximumHeight(140)
        self.tag_list.addItem("— mind —")
        for item in self.meta.get('top_cimkek', [])[:30]:
            self.tag_list.addItem(f"{item['ertek']}  ({item['db']})")
        self.tag_list.setCurrentRow(0)
        self.tag_list.currentRowChanged.connect(lambda _: self._emit())
        lay.addWidget(self.tag_list)

        # Szerzők
        self._section("SZERZŐK (top 50)", lay)
        self.author_list = QListWidget()
        self.author_list.setMaximumHeight(180)
        self.author_list.addItem("— mind —")
        for item in self.meta.get('top_szerzok', [])[:50]:
            self.author_list.addItem(f"{item['ertek']}  ({item['db']})")
        self.author_list.setCurrentRow(0)
        self.author_list.currentRowChanged.connect(lambda _: self._emit())
        lay.addWidget(self.author_list)

        # Reset
        rst = QPushButton("↺  Szűrők törlése")
        rst.setFixedHeight(32)
        rst.clicked.connect(self._reset)
        lay.addWidget(rst)

        lay.addStretch()

        # Jelmagyarázat
        self._section("JELMAGYARÁZAT", lay)
        for label, col in [
            ("Pontos egyezés", '#2ecc71'),
            ("Fuzzy egyezés",  '#27ae60'),
            ("Moly egyezés",   '#3498db'),
            ("Csak szerző",    '#f39c12'),
            ("Ismeretlen",     '#e74c3c'),
            ("Nincs fájl",     '#3a3a5c'),
        ]:
            row = QHBoxLayout()
            dot = QLabel("●")
            dot.setStyleSheet(f"color:{col}; font-size:14px;")
            dot.setFixedWidth(18)
            row.addWidget(dot)
            row.addWidget(QLabel(label))
            row.addStretch()
            lay.addLayout(row)

    def _reset(self):
        self.search.clear()
        self.history_list.setVisible(False)
        self.status_grp.buttons()[0].setChecked(True)
        self.user_grp.buttons()[0].setChecked(True)
        for cb in self.fmt_cbs.values():
            cb.setChecked(False)
        self.tag_list.setCurrentRow(0)
        self.author_list.setCurrentRow(0)
        self._emit()

    def _on_search_changed(self, text: str):
        self._emit()
        # Előzmények megjelenítése ha van szöveg
        if text.strip():
            matches = [h for h in self._history
                       if text.lower() in h.lower()][:6]
            self.history_list.clear()
            if matches:
                for m in matches:
                    self.history_list.addItem(m)
                self.history_list.setVisible(True)
            else:
                self.history_list.setVisible(False)
        else:
            # Üres keresőnél mutassuk az összes előzményt
            self.history_list.clear()
            for h in self._history[:8]:
                self.history_list.addItem(h)
            self.history_list.setVisible(bool(self._history))

    def _pick_history(self, item):
        self.search.setText(item.text())
        self.history_list.setVisible(False)

    def _save_search(self):
        text = self.search.text().strip()
        if not text or len(text) < 2:
            return
        if text in self._history:
            self._history.remove(text)
        self._history.insert(0, text)
        self._history = self._history[:20]
        self.history_list.setVisible(False)
        try:
            HISTORY_PATH.write_text(
                json.dumps(self._history, ensure_ascii=False, indent=2),
                encoding='utf-8')
        except Exception:
            pass

    def _load_history(self) -> list:
        try:
            if HISTORY_PATH.exists():
                return json.loads(HISTORY_PATH.read_text(encoding='utf-8'))
        except Exception:
            pass
        return []

    def _emit(self):
        f = {}
        s = self.search.text().strip()
        if s:
            f['search'] = s
        btn = self.status_grp.checkedButton()
        if btn:
            f['statusz'] = btn.property('val')
        fmts = [k for k, cb in self.fmt_cbs.items() if cb.isChecked()]
        if fmts:
            f['formatum'] = fmts
        ri = self.tag_list.currentRow()
        if ri > 0:
            f['cimke'] = self.tag_list.item(ri).text().rsplit('  (', 1)[0]
        ai = self.author_list.currentRow()
        if ai > 0:
            f['szerzo'] = self.author_list.item(ai).text().rsplit('  (', 1)[0]
        ub = self.user_grp.checkedButton()
        if ub:
            uval = ub.property('uval')
            if uval:
                f['user_statusz'] = uval
        self.changed.emit(f)


# ══════════════════════════════════════════════════════════════
# KÖNYVRÁCS (KÖZÉP)
# ══════════════════════════════════════════════════════════════

class BookGrid(QWidget):
    book_clicked      = pyqtSignal(dict)
    selection_changed = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.filters  = {}
        self.page     = 0
        self.total    = 0
        self.cards    = []
        self.selected = {}       # id → book dict
        self._worker  = None
        self._covers  = []
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Eszközsáv ──
        bar = QWidget()
        bar.setFixedHeight(50)
        bar.setStyleSheet("background:#16162a; border-bottom:1px solid #2a2a50;")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(14, 0, 14, 0)
        bl.setSpacing(8)

        self.info_lbl = QLabel("Betöltés...")
        self.info_lbl.setStyleSheet("color:#778; font-size:12px;")
        bl.addWidget(self.info_lbl)
        bl.addStretch()

        for label, slot in [
            ("☑ Mind", self._select_all),
            ("☐ Töröl", self._deselect_all),
        ]:
            b = QPushButton(label)
            b.setFixedHeight(30)
            b.clicked.connect(slot)
            bl.addWidget(b)

        self.sel_lbl = QLabel("")
        self.sel_lbl.setStyleSheet("color:#e94560; font-size:12px; font-weight:bold;")
        bl.addWidget(self.sel_lbl)

        exp_btn = QPushButton("📥 Export CSV")
        exp_btn.setFixedHeight(30)
        exp_btn.clicked.connect(self._export_csv)
        bl.addWidget(exp_btn)

        root.addWidget(bar)

        # ── Rács ──
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.grid_w = QWidget()
        self.grid_w.setStyleSheet("background: transparent;")
        self.grid_l = QGridLayout(self.grid_w)
        self.grid_l.setSpacing(10)
        self.grid_l.setContentsMargins(14, 14, 14, 14)

        self.scroll.setWidget(self.grid_w)
        root.addWidget(self.scroll, 1)

        # ── Lapozó ──
        pag = QWidget()
        pag.setFixedHeight(50)
        pag.setStyleSheet("background:#16162a; border-top:1px solid #2a2a50;")
        pl = QHBoxLayout(pag)
        pl.setContentsMargins(14, 0, 14, 0)
        pl.setSpacing(8)

        self.prev_btn = QPushButton("◀  Előző")
        self.prev_btn.setFixedHeight(32)
        self.prev_btn.clicked.connect(self._prev)
        pl.addWidget(self.prev_btn)

        self.page_lbl = QLabel("")
        self.page_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_lbl.setStyleSheet("color:#aab; font-size:12px;")
        pl.addWidget(self.page_lbl, 1)

        self.next_btn = QPushButton("Következő  ▶")
        self.next_btn.setFixedHeight(32)
        self.next_btn.clicked.connect(self._next)
        pl.addWidget(self.next_btn)

        root.addWidget(pag)

    # ── Betöltés ──
    def load(self, filters: dict, page: int = 0):
        self.filters = filters
        self.page    = page
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
        self._worker = BooksWorker(filters, page)
        self._worker.done.connect(self._on_loaded)
        self._worker.error.connect(
            lambda e: self.info_lbl.setText(f"❌ {e}"))
        self._worker.start()
        self.info_lbl.setText("Betöltés...")

    def _on_loaded(self, books: list, total: int):
        self.total = total
        self._clear()

        cols = max(1, (self.scroll.viewport().width() - 14) // (CARD_W + 10))

        for i, book in enumerate(books):
            card = BookCard(book)
            card.clicked.connect(self.book_clicked)
            card.toggled.connect(self._on_toggle)
            if book['id'] in self.selected:
                card.set_selected(True)
            r, c = divmod(i, cols)
            self.grid_l.addWidget(card, r, c)
            self.cards.append(card)

            if book.get('kep_utvonal'):
                w = CoverWorker(book['id'], book['kep_utvonal'])
                w.done.connect(self._on_cover)
                self._covers.append(w)
                w.start()

        pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        self.page_lbl.setText(
            f"{self.page + 1} / {pages}  •  {total:,} könyv")
        self.prev_btn.setEnabled(self.page > 0)
        self.next_btn.setEnabled((self.page + 1) * PAGE_SIZE < total)
        self.info_lbl.setText(
            f"{total:,} könyv  •  {len(books)} megjelenítve az oldalon")

    def _on_cover(self, bid: int, px: QPixmap):
        for c in self.cards:
            if c.book['id'] == bid:
                c.set_cover(px)
                break

    def _on_toggle(self, book: dict, sel: bool):
        if sel:
            self.selected[book['id']] = book
        else:
            self.selected.pop(book['id'], None)
        n = len(self.selected)
        self.sel_lbl.setText(f"{n} kijelölve" if n else "")
        self.selection_changed.emit(list(self.selected.values()))

    def _select_all(self):
        for c in self.cards:
            self.selected[c.book['id']] = c.book
            c.set_selected(True)
        n = len(self.selected)
        self.sel_lbl.setText(f"{n} kijelölve")
        self.selection_changed.emit(list(self.selected.values()))

    def _deselect_all(self):
        self.selected.clear()
        for c in self.cards:
            c.set_selected(False)
        self.sel_lbl.setText("")
        self.selection_changed.emit([])

    def _clear(self):
        for w in self._covers:
            if w.isRunning():
                w.terminate()
        self._covers.clear()
        while self.grid_l.count():
            item = self.grid_l.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.cards.clear()

    def _export_csv(self):
        """Kijelölt (vagy szűrt összes) könyv exportálása CSV-be."""
        books_to_export = list(self.selected.values())

        if not books_to_export:
            # Ha nincs kijelölve semmi, az összes szűrt könyvet exportáljuk
            reply = QMessageBox.question(
                self, "Export",
                f"Nincs kijelölt könyv.\nExportálod az összes szűrt könyvet? ({self.total:,} db)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return
            # Lekérjük az összes szűrt könyvet
            db = DB.get()
            sel, p, _, _ = build_sql(self.filters, 0)
            # Limit nélkül
            sel_all = sel.replace(
                f"LIMIT {PAGE_SIZE} OFFSET 0", f"LIMIT 99999 OFFSET 0")
            rows = db.query(sel_all, p)
            books_to_export = [dict(r) for r in rows]

        # Fájlnév
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = Path(DB_PATH).parent / f"export_{ts}.csv"

        mezok = ['id', 'cim', 'szerzo', 'kiado', 'kiadas_eve',
                 'isbn', 'sorozat', 'cimkek', 'formatum',
                 'egyezes_szint', 'fajl_utvonal',
                 'ertekeles', 'user_statusz', 'sajat_ertekeles']

        try:
            with open(dest, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=mezok,
                                        extrasaction='ignore')
                writer.writeheader()
                writer.writerows(books_to_export)

            QMessageBox.information(
                self, "Export kész",
                f"✅ {len(books_to_export):,} könyv exportálva:\n{dest}")
        except Exception as e:
            QMessageBox.warning(self, "Hiba", f"Export sikertelen:\n{e}")

    def _prev(self):
        if self.page > 0:
            self.load(self.filters, self.page - 1)

    def _next(self):
        if (self.page + 1) * PAGE_SIZE < self.total:
            self.load(self.filters, self.page + 1)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        if not self.cards:
            return
        cols = max(1, (self.scroll.viewport().width() - 14) // (CARD_W + 10))
        for i, card in enumerate(self.cards):
            self.grid_l.removeWidget(card)
            r, c = divmod(i, cols)
            self.grid_l.addWidget(card, r, c)


# ══════════════════════════════════════════════════════════════
# KÖNYV RÉSZLETEK
# ══════════════════════════════════════════════════════════════

class BookDetailPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._cover_worker = None
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 8)
        lay.setSpacing(8)

        # Cím
        self.title_lbl = QLabel("Válassz egy könyvet a részletekért")
        self.title_lbl.setWordWrap(True)
        self.title_lbl.setStyleSheet(
            "font-size:15px; font-weight:bold; color:#e94560;")
        lay.addWidget(self.title_lbl)

        # Borító + info
        top = QHBoxLayout()
        top.setSpacing(12)

        self.cover_lbl = QLabel()
        self.cover_lbl.setFixedSize(90, 126)
        self.cover_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_lbl.setStyleSheet(
            "background:#1a1a30; border-radius:6px; "
            "font-size:28px;")
        self.cover_lbl.setText("📖")
        top.addWidget(self.cover_lbl, 0, Qt.AlignmentFlag.AlignTop)

        info = QVBoxLayout()
        info.setSpacing(4)
        self.author_lbl = QLabel("")
        self.author_lbl.setStyleSheet("font-size:13px; color:#aab;")
        self.author_lbl.setWordWrap(True)
        info.addWidget(self.author_lbl)

        self.meta_lbl = QLabel("")
        self.meta_lbl.setStyleSheet("font-size:11px; color:#778;")
        self.meta_lbl.setWordWrap(True)
        info.addWidget(self.meta_lbl)

        self.rating_lbl = QLabel("")
        self.rating_lbl.setStyleSheet("font-size:12px; color:#f39c12;")
        info.addWidget(self.rating_lbl)

        self.file_lbl = QLabel("")
        self.file_lbl.setStyleSheet("font-size:11px; color:#2ecc71;")
        self.file_lbl.setWordWrap(True)
        info.addWidget(self.file_lbl)

        info.addStretch()
        top.addLayout(info, 1)
        lay.addLayout(top)

        # ── Olvasási státusz gombok ──
        st_row = QHBoxLayout()
        st_row.setSpacing(4)
        self.st_grp = QButtonGroup(self)
        self.st_grp.setExclusive(True)
        self._st_btns = {}
        for lbl, val, col in [
            ("📖 Olvasni akarom", "olvasni_akarom", "#2980b9"),
            ("📚 Olvasom",        "olvasom",        "#8e44ad"),
            ("✅ Elolvastam",     "elolvastam",     "#27ae60"),
        ]:
            b = QPushButton(lbl)
            b.setCheckable(True)
            b.setFixedHeight(28)
            b.setProperty('stval', val)
            b.setStyleSheet(
                f"QPushButton:checked {{ background:{col}; border-color:{col}; color:white; }}")
            self.st_grp.addButton(b)
            self._st_btns[val] = b
            st_row.addWidget(b)

        clear_btn = QPushButton("✕")
        clear_btn.setFixedSize(28, 28)
        clear_btn.setToolTip("Státusz törlése")
        clear_btn.clicked.connect(self._clear_status)
        st_row.addWidget(clear_btn)
        lay.addLayout(st_row)
        self.st_grp.buttonClicked.connect(self._on_status_click)

        # ── Saját értékelés (csillagok) ──
        star_row = QHBoxLayout()
        star_row.setSpacing(2)
        star_row.addWidget(QLabel("Saját értékelés:"))
        self._star_btns = []
        for i in range(1, 6):
            sb = QPushButton("☆")
            sb.setFixedSize(28, 28)
            sb.setProperty('stars', i)
            sb.setStyleSheet(
                "QPushButton { font-size:16px; border:none; background:transparent; color:#f39c12; }"
                "QPushButton:hover { color:#e67e22; }")
            sb.clicked.connect(self._on_star_click)
            self._star_btns.append(sb)
            star_row.addWidget(sb)
        self._cur_stars = 0
        star_row.addStretch()
        lay.addLayout(star_row)

        # Leírás
        self.desc = QTextEdit()
        self.desc.setReadOnly(True)
        self.desc.setMaximumHeight(100)
        self.desc.setPlaceholderText("Leírás...")
        lay.addWidget(self.desc)

    def _on_status_click(self, btn):
        if not self.current_book:
            return
        DB.get().set_user_data(
            self.current_book['id'],
            statusz=btn.property('stval'))

    def _clear_status(self):
        if not self.current_book:
            return
        self.st_grp.setExclusive(False)
        for b in self.st_grp.buttons():
            b.setChecked(False)
        self.st_grp.setExclusive(True)
        DB.get().set_user_data(self.current_book['id'], statusz=None)

    def _on_star_click(self):
        btn = self.sender()
        stars = btn.property('stars')
        # Ha ugyanazt kattintod = töröl
        if stars == self._cur_stars:
            stars = 0
        self._set_stars(stars)
        if self.current_book:
            DB.get().set_user_data(
                self.current_book['id'],
                ertekeles=stars if stars > 0 else None)

    def _set_stars(self, n: int):
        self._cur_stars = n
        for sb in self._star_btns:
            sb.setText("★" if sb.property('stars') <= n else "☆")

    def show_book(self, book: dict):
        self.current_book = book
        self.title_lbl.setText(book.get('cim') or 'Ismeretlen cím')
        self.author_lbl.setText(book.get('szerzo') or '')

        # Felhasználói adatok betöltése DB-ből
        ud = DB.get().get_user_data(book['id'])
        self.st_grp.setExclusive(False)
        for b in self.st_grp.buttons():
            b.setChecked(False)
        self.st_grp.setExclusive(True)
        saved_st = ud.get('statusz') or book.get('user_statusz')
        if saved_st and saved_st in self._st_btns:
            self._st_btns[saved_st].setChecked(True)
        saved_stars = ud.get('sajat_ertekeles') or book.get('sajat_ertekeles') or 0
        self._set_stars(saved_stars)

        parts = []
        if book.get('kiado'):      parts.append(book['kiado'])
        if book.get('kiadas_eve'): parts.append(str(book['kiadas_eve']))
        if book.get('sorozat'):    parts.append(f"Sorozat: {book['sorozat']}")
        if book.get('isbn'):       parts.append(f"ISBN: {book['isbn']}")
        if book.get('cimkek'):     parts.append(book['cimkek'][:60])
        self.meta_lbl.setText("  •  ".join(parts))

        self.rating_lbl.setText(
            f"⭐ Moly értékelés: {book['ertekeles']}"
            if book.get('ertekeles') else "")

        if book.get('fajl_utvonal'):
            fmt   = (book.get('formatum') or '').upper()
            szint = book.get('egyezes_szint', '')
            self.file_lbl.setText(f"✅ {fmt}  |  egyezés: {szint}")
        else:
            self.file_lbl.setText("⚠️  Nincs letöltött fájl")

        self.desc.setPlainText(book.get('leiras') or '')

        # Borítókép
        self.cover_lbl.setText("📖")
        if book.get('kep_utvonal'):
            cache = COVER_DIR / f"{book['id']}.jpg"
            if cache.exists():
                px = QPixmap(str(cache))
                if not px.isNull():
                    self.cover_lbl.setText("")
                    self.cover_lbl.setPixmap(px.scaled(
                        90, 126,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation))
                    return
            if self._cover_worker and self._cover_worker.isRunning():
                self._cover_worker.terminate()
            self._cover_worker = CoverWorker(book['id'], book['kep_utvonal'])
            self._cover_worker.done.connect(self._on_cover)
            self._cover_worker.start()

    def _on_cover(self, _, px: QPixmap):
        self.cover_lbl.setText("")
        self.cover_lbl.setPixmap(px.scaled(
            90, 126,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))


# ══════════════════════════════════════════════════════════════
# AI PANEL
# ══════════════════════════════════════════════════════════════

class AIPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.book       = None
        self._worker    = None
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.setSpacing(6)

        # Fejléc + modell
        hdr = QHBoxLayout()
        t = QLabel("🤖  AI Asszisztens")
        t.setStyleSheet("font-size:13px; font-weight:bold; color:#e94560;")
        hdr.addWidget(t)
        hdr.addStretch()
        self.model_combo = QComboBox()
        self.model_combo.setFixedWidth(140)
        self._load_models()
        hdr.addWidget(self.model_combo)
        lay.addLayout(hdr)

        # Gombok
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        for label, slot in [
            ("📋 Összefoglaló", self._summary),
            ("💬 Vélemény",     self._opinion),
            ("📚 Hasonlók",     self._similar),
        ]:
            b = QPushButton(label)
            b.setFixedHeight(30)
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        self.stop_btn = QPushButton("⏹")
        self.stop_btn.setFixedSize(30, 30)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop)
        btn_row.addWidget(self.stop_btn)
        lay.addLayout(btn_row)

        # Kimenet
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText(
            "Válassz egy könyvet, majd kérj összefoglalót, véleményt vagy ajánlókat.")
        lay.addWidget(self.output, 1)

        # Saját kérdés
        q_row = QHBoxLayout()
        self.q_inp = QLineEdit()
        self.q_inp.setPlaceholderText("Kérdezz a könyvről...")
        self.q_inp.returnPressed.connect(self._custom)
        q_row.addWidget(self.q_inp, 1)
        send = QPushButton("▶")
        send.setFixedSize(32, 32)
        send.clicked.connect(self._custom)
        q_row.addWidget(send)
        lay.addLayout(q_row)

    def _load_models(self):
        self.model_combo.addItem("llama3")
        if not HAS_REQUESTS:
            return
        try:
            r = req.get(f"{OLLAMA_URL}/api/tags", timeout=3)
            if r.status_code == 200:
                models = [m['name'] for m in r.json().get('models', [])]
                if models:
                    self.model_combo.clear()
                    for m in models:
                        self.model_combo.addItem(m)
        except Exception:
            pass

    def set_book(self, book: dict):
        self.book = book

    def _ctx(self) -> str:
        if not self.book:
            return ""
        b = self.book
        lines = [f"Könyv: {b.get('cim', '')}"]
        if b.get('szerzo'):    lines.append(f"Szerző: {b['szerzo']}")
        if b.get('kiado'):     lines.append(f"Kiadó: {b['kiado']}")
        if b.get('kiadas_eve'):lines.append(f"Kiadás éve: {b['kiadas_eve']}")
        if b.get('cimkek'):    lines.append(f"Műfaj/cimkék: {b['cimkek']}")
        if b.get('leiras'):    lines.append(f"\nLeírás:\n{b['leiras'][:600]}")
        return "\n".join(lines)

    def _ask(self, prompt: str):
        if not self.book:
            self.output.setPlainText("⚠️  Először válassz ki egy könyvet!")
            return
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
        model = self.model_combo.currentText()
        self.output.clear()
        self.stop_btn.setEnabled(True)
        self._worker = AIWorker(prompt, model)
        self._worker.chunk.connect(lambda t: self.output.insertPlainText(t))
        self._worker.done.connect(lambda: self.stop_btn.setEnabled(False))
        self._worker.error.connect(lambda e: self.output.setPlainText(
            f"❌ {e}\n\nBiztos fut az Ollama?\n  ollama serve"))
        self._worker.start()

    def _summary(self):
        self._ask(
            f"Foglald össze röviden ezt a könyvet magyarul:\n\n{self._ctx()}")

    def _opinion(self):
        self._ask(
            f"Írj egy rövid kritikát és véleményt erről a könyvről magyarul:\n\n{self._ctx()}")

    def _similar(self):
        if not self.book:
            return
        b = self.book
        db = DB.get()
        # Keresés cimkék szerint
        cimkek = [c.strip() for c in (b.get('cimkek') or '').split(',') if len(c.strip()) > 2][:3]
        results = []
        seen = set()
        for cimke in cimkek:
            rows = db.query("""
                SELECT cim, szerzo FROM konyvek
                WHERE cimkek LIKE ? AND id != ? LIMIT 8
            """, (f"%{cimke}%", b['id']))
            for row in rows:
                if row['cim'] not in seen:
                    results.append(row)
                    seen.add(row['cim'])
        # Ha nincs cimke alapú, szerző szerint
        if not results and b.get('szerzo'):
            rows = db.query("""
                SELECT cim, szerzo FROM konyvek
                WHERE szerzo = ? AND id != ? LIMIT 8
            """, (b['szerzo'], b['id']))
            for row in rows:
                if row['cim'] not in seen:
                    results.append(row)
                    seen.add(row['cim'])

        if results:
            text = "📚  Hasonló könyvek az adatbázisban:\n\n"
            for row in results[:12]:
                text += f"• {row['cim']}  —  {row['szerzo']}\n"
            self.output.setPlainText(text)
        else:
            self._ask(
                f"Ajánlj hasonló könyveket ehhez, magyarul:\n\n{self._ctx()}")

    def _custom(self):
        q = self.q_inp.text().strip()
        if not q:
            return
        self._ask(f"Kérdés: {q}\n\nKönyv:\n{self._ctx()}\n\nVálaszolj magyarul.")
        self.q_inp.clear()

    def _stop(self):
        if self._worker:
            self._worker.terminate()
        self.stop_btn.setEnabled(False)


# ══════════════════════════════════════════════════════════════
# TELEFON PANEL
# ══════════════════════════════════════════════════════════════

class PhonePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._books  = []
        self._copy_w = None
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 8, 14, 12)
        lay.setSpacing(6)

        t = QLabel("📱  Másolás telefonra")
        t.setStyleSheet("font-size:13px; font-weight:bold; color:#e94560;")
        lay.addWidget(t)

        # Mappastruktúra (előbb létrehozzuk, mert _refresh_drives használja)
        self.fs = QFileSystemModel()
        self.fs.setFilter(QDir.Filter.Dirs | QDir.Filter.NoDotAndDotDot)
        self.tree = QTreeView()
        self.tree.setModel(self.fs)
        self.tree.setHeaderHidden(True)
        for col in range(1, 4):
            self.tree.hideColumn(col)
        self.tree.setMaximumHeight(180)
        self.tree.selectionModel().currentChanged.connect(self._on_sel)

        # Meghajtó kiválasztó
        dr = QHBoxLayout()
        dr.addWidget(QLabel("Meghajtó:"))
        self.drive_combo = QComboBox()
        self.drive_combo.setFixedWidth(80)
        self._refresh_drives()
        self.drive_combo.currentTextChanged.connect(self._on_drive)
        dr.addWidget(self.drive_combo)
        ref = QPushButton("↺")
        ref.setFixedSize(28, 28)
        ref.clicked.connect(self._refresh_drives)
        dr.addWidget(ref)
        dr.addStretch()
        lay.addLayout(dr)

        lay.addWidget(self.tree)

        # Mappa kezelő gombok
        fa = QHBoxLayout()
        fa.setSpacing(4)
        for label, slot in [
            ("+ Mappa", self._new_folder),
            ("✏ Nevez", self._rename),
            ("🗑 Töröl", self._delete),
        ]:
            b = QPushButton(label)
            b.setFixedHeight(28)
            b.clicked.connect(slot)
            fa.addWidget(b)
        lay.addLayout(fa)

        # Kijelölt cél mappa
        self.path_lbl = QLabel("← Válassz mappát a fán")
        self.path_lbl.setStyleSheet("font-size:11px; color:#778; padding:2px;")
        self.path_lbl.setWordWrap(True)
        lay.addWidget(self.path_lbl)

        # Másolás gomb
        self.copy_btn = QPushButton("📋  Kijelölt könyvek másolása")
        self.copy_btn.setFixedHeight(38)
        self.copy_btn.setEnabled(False)
        self.copy_btn.setStyleSheet(
            "QPushButton { background:#1a3a1a; border:1px solid #2a5a2a; "
            "border-radius:7px; font-size:13px; }"
            "QPushButton:hover { background:#2a5a2a; border-color:#3a8a3a; }"
            "QPushButton:disabled { background:#1a1a30; border-color:#2a2a50; color:#445544; }"
        )
        self.copy_btn.clicked.connect(self._copy)
        lay.addWidget(self.copy_btn)

        # Folyamatjelző
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        lay.addWidget(self.progress)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("font-size:11px; color:#2ecc71;")
        lay.addWidget(self.status_lbl)

    def _refresh_drives(self):
        cur = self.drive_combo.currentText()
        self.drive_combo.blockSignals(True)
        self.drive_combo.clear()
        if sys.platform == 'win32':
            import string
            for ltr in string.ascii_uppercase:
                p = f"{ltr}:\\"
                if os.path.exists(p):
                    self.drive_combo.addItem(p)
        else:
            for p in ['/media', '/mnt']:
                self.drive_combo.addItem(p)
        if cur:
            idx = self.drive_combo.findText(cur)
            if idx >= 0:
                self.drive_combo.setCurrentIndex(idx)
        self.drive_combo.blockSignals(False)
        self._on_drive(self.drive_combo.currentText())

    def _on_drive(self, drive: str):
        if drive and os.path.exists(drive):
            self.fs.setRootPath(drive)
            self.tree.setRootIndex(self.fs.index(drive))

    def _on_sel(self, idx):
        path = self.fs.filePath(idx)
        self.path_lbl.setText(path)

    def _current_path(self) -> Path | None:
        idx = self.tree.currentIndex()
        if not idx.isValid():
            return None
        return Path(self.fs.filePath(idx))

    def _new_folder(self):
        p = self._current_path()
        if not p:
            self.status_lbl.setText("⚠️  Válassz szülő mappát!")
            return
        name, ok = QInputDialog.getText(self, "Új mappa", "Mappa neve:")
        if ok and name.strip():
            try:
                (p / name.strip()).mkdir(parents=True, exist_ok=False)
                self.status_lbl.setText(f"✅ Létrehozva: {name}")
            except Exception as e:
                QMessageBox.warning(self, "Hiba", str(e))

    def _rename(self):
        p = self._current_path()
        if not p:
            return
        name, ok = QInputDialog.getText(
            self, "Átnevezés", "Új név:", text=p.name)
        if ok and name.strip() and name != p.name:
            try:
                p.rename(p.parent / name.strip())
                self.status_lbl.setText(f"✅ Átnevezve: {name}")
            except Exception as e:
                QMessageBox.warning(self, "Hiba", str(e))

    def _delete(self):
        p = self._current_path()
        if not p:
            return
        r = QMessageBox.question(
            self, "Törlés megerősítése",
            f"Biztosan törlöd ezt a mappát és tartalmát?\n\n{p}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r == QMessageBox.StandardButton.Yes:
            try:
                shutil.rmtree(p)
                self.status_lbl.setText(f"✅ Törölve: {p.name}")
            except Exception as e:
                QMessageBox.warning(self, "Hiba", str(e))

    def set_books(self, books: list):
        self._books = books
        n = len(books)
        fajlok = [b for b in books if b.get('fajl_utvonal')]
        self.copy_btn.setText(
            f"📋  {n} könyv másolása  ({len(fajlok)} fájl)"
            if n else "📋  Nincs kijelölt könyv")
        self.copy_btn.setEnabled(len(fajlok) > 0)

    def _copy(self):
        dest = self._current_path()
        if not dest:
            QMessageBox.warning(self, "Hiba",
                "Válassz célmappát a mappastruktúrában!")
            return
        fajlok = [b['fajl_utvonal'] for b in self._books
                  if b.get('fajl_utvonal')]
        if not fajlok:
            QMessageBox.information(self, "Info",
                "A kijelölt könyvekhez nincs letöltött fájl.")
            return

        self.progress.setMaximum(len(fajlok))
        self.progress.setValue(0)
        self.progress.setVisible(True)
        self.copy_btn.setEnabled(False)
        self.status_lbl.setText("Másolás folyamatban...")

        self._copy_w = CopyWorker(fajlok, dest)
        self._copy_w.progress.connect(
            lambda cur, tot, name: (
                self.progress.setValue(cur),
                self.status_lbl.setText(f"[{cur}/{tot}] {name}")
            ))
        self._copy_w.done.connect(self._on_copy_done)
        self._copy_w.start()

    def _on_copy_done(self, ok: int, fail: int):
        self.progress.setVisible(False)
        self.copy_btn.setEnabled(True)
        msg = f"✅  {ok} fájl másolva"
        if fail:
            msg += f"  •  ❌ {fail} sikertelen"
        self.status_lbl.setText(msg)


# ══════════════════════════════════════════════════════════════
# JOB OLDALPANEL (rész-összerakás)
# ══════════════════════════════════════════════════════════════

class RightPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(360)
        self.setMaximumWidth(460)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        spl = QSplitter(Qt.Orientation.Vertical)
        spl.setStyleSheet("QSplitter::handle { background:#2a2a50; height:3px; }")

        self.detail = BookDetailPanel()
        self.ai     = AIPanel()
        self.phone  = PhonePanel()

        spl.addWidget(self.detail)
        spl.addWidget(self.ai)
        spl.addWidget(self.phone)
        spl.setSizes([320, 380, 300])
        spl.setCollapsible(0, False)
        spl.setCollapsible(1, False)
        spl.setCollapsible(2, False)

        lay.addWidget(spl)

    def show_book(self, book: dict):
        self.detail.show_book(book)
        self.ai.set_book(book)

    def set_selected(self, books: list):
        self.phone.set_books(books)


# ══════════════════════════════════════════════════════════════
# FŐABLAK
# ══════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("KönyvtárAI  📚")
        self.setMinimumSize(1280, 760)
        self.resize(1520, 920)
        meta = self._load_meta()
        self._build(meta)
        QTimer.singleShot(100, self._initial_load)

    def _load_meta(self) -> dict:
        try:
            with open(META_PATH, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def _build(self, meta: dict):
        self.statusBar().setStyleSheet(
            "background:#14142a; color:#556; "
            "border-top:1px solid #2a2a50; font-size:12px;")

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        spl = QSplitter(Qt.Orientation.Horizontal)
        spl.setHandleWidth(2)

        self.filters = FilterPanel(meta)
        self.grid    = BookGrid()
        self.right   = RightPanel()

        spl.addWidget(self.filters)
        spl.addWidget(self.grid)
        spl.addWidget(self.right)
        spl.setSizes([224, 950, 400])
        spl.setCollapsible(0, True)
        spl.setCollapsible(2, True)

        root.addWidget(spl)

        # Összekötés
        self.filters.changed.connect(self._on_filter)
        self.grid.book_clicked.connect(self.right.show_book)
        self.grid.selection_changed.connect(self.right.set_selected)

        # Státuszsor info
        n = meta.get('osszes_konyv', 0)
        ef = meta.get('adatgazdagsag', {}).get('szerzo', {}).get('db', 0)
        self.statusBar().showMessage(
            f"📚  {n:,} könyv az adatbázisban  •  "
            f"Szerzővel: {ef:,}  •  "
            f"KönyvtárAI v1.0  —  moly.hu scraper fut / kész"
        )

    def _initial_load(self):
        self.grid.load({})

    def _on_filter(self, f: dict):
        self.grid.load(f, page=0)

    def closeEvent(self, ev):
        DB.get().close()
        ev.accept()


# ══════════════════════════════════════════════════════════════
# INDÍTÁS
# ══════════════════════════════════════════════════════════════

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("KönyvtárAI")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)

    if not os.path.exists(DB_PATH):
        QMessageBox.critical(
            None, "Hiányzó adatbázis",
            f"Nem találom az adatbázist:\n{DB_PATH}\n\n"
            "Futtasd először a fazis1_fajlfelismero.py-t!")
        sys.exit(1)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
