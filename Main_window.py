import sys
import os
from datetime import datetime
from typing import List, Dict, Set
from urllib.parse import quote_plus

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QDockWidget, QTableView, QLabel, QPushButton, QLineEdit,
    QComboBox, QStatusBar, QMenuBar, QMessageBox, QProgressBar,
    QAbstractItemView, QStyledItemDelegate, QToolBar,
    QFrame, QDialog, QFormLayout, QTabWidget, QCheckBox, QTextEdit,
    QSpinBox, QSlider, QMenu, QSizePolicy, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, QSortFilterProxyModel, QTimer, QAbstractTableModel, QThread, Signal, QUrl
from PySide6.QtGui import QPixmap, QMouseEvent, QColor, QBrush, QDesktopServices

import gui_config
from layout_state import get_layout_state, init_layout_state
from database import (
    search_books, count_books, get_formats, init_database, update_book_field,
    create_backup, list_backups, restore_backup, delete_backup
)
from downloader import Downloader
from scraper import Scraper
import config

# Érvényes e-book és szöveg formátumok
VALID_FORMATS = {
    "epub", "pdf", "mobi", "azw", "azw3", "fb2", "lit",
    "txt", "rtf", "doc", "docx", "odt", "djvu", "cbr", "cbz",
}

# Oszlopok, amelyeknél a helyi menüben keresés is elérhető
SEARCHABLE_COLUMNS = {"ncore_id", "szerzo", "cim", "sorozat"}

# Megjelölés színei
MARK_BG = QColor("#2d7a3a")
MARK_FG = QColor("#ffffff")

# Nem szerkeszthető oszlopok (csak olvasható)
READONLY_COLUMNS = {"ncore_id", "feltoltve_datum"}


# ====================== TABLE MODEL ======================
class BookTableModel(QAbstractTableModel):
    """Táblázat modell saját megjelölési rendszerrel.

    A marked_ids halmazban tárolt ncore_id-jú sorok zöld hátteret kapnak.
    Ez független a QTableView kiválasztásától, tehát tartósan megmarad.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.books: List[Dict] = []
        self.columns = []
        self.marked_ids: Set[str] = set()

    def rowCount(self, parent=None):
        return len(self.books)

    def columnCount(self, parent=None):
        return len(self.columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self.books):
            return None
        book = self.books[index.row()]
        col = self.columns[index.column()]

        if role == Qt.DisplayRole:
            val = book.get(col["name"], "")
            if col["name"] == "feltoltve_datum" and val:
                try:
                    return datetime.strptime(val, "%Y-%m-%d %H:%M:%S").strftime("%y-%m-%d")
                except Exception:
                    return val
            return str(val or "")

        if role == Qt.BackgroundRole:
            nid = str(book.get("ncore_id", ""))
            if nid in self.marked_ids:
                return QBrush(MARK_BG)
            return None

        if role == Qt.ForegroundRole:
            nid = str(book.get("ncore_id", ""))
            if nid in self.marked_ids:
                return QBrush(MARK_FG)
            return None

        if role == Qt.UserRole:
            return book

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.columns[section]["label"]
        return None

    def flags(self, index):
        """Cellák szerkeszthetősége.
        
        Csak olvasható: ncore_id, feltoltve_datum.
        Minden más oszlop szerkeszthető dupla kattintással.
        """
        base = super().flags(index)
        if not index.isValid():
            return base
        col = self.columns[index.column()]
        if col["name"] in READONLY_COLUMNS:
            return base  # Csak olvasható
        return base | Qt.ItemIsEditable

    def setData(self, index, value, role=Qt.EditRole):
        """Cella szerkesztése és mentése az adatbázisba."""
        if role != Qt.EditRole or not index.isValid():
            return False

        row = index.row()
        col_idx = index.column()
        if row >= len(self.books) or col_idx >= len(self.columns):
            return False

        col_name = self.columns[col_idx]["name"]
        if col_name in READONLY_COLUMNS:
            return False

        book = self.books[row]
        ncore_id = str(book.get("ncore_id", ""))
        if not ncore_id:
            return False

        new_value = str(value).strip()
        old_value = str(book.get(col_name, "") or "")

        # Ha nem változott, nem csinálunk semmit
        if new_value == old_value:
            return False

        # Mentés az adatbázisba
        if update_book_field(ncore_id, col_name, new_value):
            # Memóriában is frissítjük
            book[col_name] = new_value
            self.dataChanged.emit(index, index)
            return True

        return False

    def set_books(self, books: List[Dict]):
        self.beginResetModel()
        self.books = books
        self.endResetModel()

    def toggle_mark(self, row: int) -> bool:
        """Megjelölés ki/be váltása. Visszaadja az új állapotot (True=megjelölt)."""
        if row < 0 or row >= len(self.books):
            return False
        nid = str(self.books[row].get("ncore_id", ""))
        if not nid:
            return False
        if nid in self.marked_ids:
            self.marked_ids.discard(nid)
            result = False
        else:
            self.marked_ids.add(nid)
            result = True
        # Frissítjük a sor megjelenítését
        left = self.index(row, 0)
        right = self.index(row, self.columnCount() - 1)
        self.dataChanged.emit(left, right)
        return result

    def mark_row(self, row: int):
        """Sor megjelölése (hozzáadás)."""
        if row < 0 or row >= len(self.books):
            return
        nid = str(self.books[row].get("ncore_id", ""))
        if nid and nid not in self.marked_ids:
            self.marked_ids.add(nid)
            left = self.index(row, 0)
            right = self.index(row, self.columnCount() - 1)
            self.dataChanged.emit(left, right)

    def unmark_row(self, row: int):
        """Sor megjelölésének törlése."""
        if row < 0 or row >= len(self.books):
            return
        nid = str(self.books[row].get("ncore_id", ""))
        if nid and nid in self.marked_ids:
            self.marked_ids.discard(nid)
            left = self.index(row, 0)
            right = self.index(row, self.columnCount() - 1)
            self.dataChanged.emit(left, right)

    def clear_marks(self):
        """Minden megjelölés törlése."""
        self.marked_ids.clear()
        if self.books:
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(self.rowCount() - 1, self.columnCount() - 1)
            )

    def get_marked_books(self) -> List[Dict]:
        """Megjelölt könyvek listája."""
        return [b for b in self.books if str(b.get("ncore_id", "")) in self.marked_ids]


# ====================== CUSTOM TABLE VIEW ======================
class BookTableView(QTableView):
    """Egyedi táblázat:
    - Ctrl + bal klikk → megjelölés (hozzáadás)
    - Ctrl + jobb klikk → megjelölés törlése
    - Egérrel bekeretezés → megjelölés (hozzáadás)
    """

    def mousePressEvent(self, event: QMouseEvent):
        modifiers = event.modifiers()
        index = self.indexAt(event.position().toPoint())

        if index.isValid() and (modifiers & Qt.ControlModifier):
            # Ctrl + bal klikk → megjelölés
            if event.button() == Qt.LeftButton:
                src_model = self.model().sourceModel()
                src_index = self.model().mapToSource(index)
                src_model.mark_row(src_index.row())
                # Frissítjük a kijelöltek listáját a főablakban
                self._notify_parent()
                event.accept()
                return
            # Ctrl + jobb klikk → megjelölés törlése
            elif event.button() == Qt.RightButton:
                src_model = self.model().sourceModel()
                src_index = self.model().mapToSource(index)
                src_model.unmark_row(src_index.row())
                self._notify_parent()
                event.accept()
                return

        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Egérrel bekeretezés (rubberband) után a kijelölt sorokat megjelöljük."""
        super().mouseReleaseEvent(event)

        # Ha volt kiválasztás húzással (nem Ctrl), megjelöljük a kiválasztott sorokat
        if (event.button() == Qt.LeftButton
                and not (event.modifiers() & Qt.ControlModifier)):
            sel_indexes = self.selectionModel().selectedRows()
            if len(sel_indexes) > 1:  # Csak húzásnál (több sor)
                src_model = self.model().sourceModel()
                for idx in sel_indexes:
                    src_idx = self.model().mapToSource(idx)
                    src_model.mark_row(src_idx.row())
                self.clearSelection()
                self._notify_parent()

    def _notify_parent(self):
        """Értesíti a MainWindow-t a megjelölések változásáról."""
        win = self.window()
        if hasattr(win, 'update_marked_list'):
            win.update_marked_list()


# ====================== SCRAPER WORKER ======================
class ScraperWorker(QThread):
    """Háttérszálban futó scraper."""
    finished = Signal(int)
    log_signal = Signal(str)

    def __init__(self, mode="update"):
        super().__init__()
        self.mode = mode
        self.scraper = Scraper(log_callback=self.log_signal.emit)

    def run(self):
        try:
            if self.mode == "update":
                count = self.scraper.scrape_update()
            elif self.mode == "older":
                count = self.scraper.scrape_older(max_pages=3000)
            else:
                count = self.scraper.scrape_full(max_pages=3000)
            self.finished.emit(count)
        except Exception as e:
            self.log_signal.emit(f"❌ Hiba: {e}")
            self.finished.emit(0)

    def stop(self):
        self.scraper.stop()


# ====================== SETTINGS DIALOG ======================
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Beállítások")
        self.setMinimumSize(550, 550)
        self.config_gui = gui_config.get_config()
        self.layout_state = get_layout_state()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        # ---- Fiók fül ----
        gen_tab = QWidget()
        gen_lay = QFormLayout(gen_tab)
        curr = config.load_config()

        self.user_edit = QLineEdit(curr.get("username", ""))
        gen_lay.addRow("Felhasználónév:", self.user_edit)

        self.pass_edit = QLineEdit(curr.get("password", ""))
        self.pass_edit.setEchoMode(QLineEdit.Password)
        gen_lay.addRow("Jelszó:", self.pass_edit)

        self.path_edit = QLineEdit(curr.get("torrent_watch_folder", ""))
        gen_lay.addRow("Torrent mappa:", self.path_edit)

        tabs.addTab(gen_tab, "Fiók")

        # ---- Megjelenés fül ----
        app_tab = QWidget()
        app_lay = QVBoxLayout(app_tab)
        self.theme_combo = QComboBox()
        for key, theme in gui_config.THEMES.items():
            self.theme_combo.addItem(theme['name'], key)
        self.theme_combo.setCurrentText(
            gui_config.THEMES[self.config_gui.get("theme", default="midnight")]["name"]
        )
        app_lay.addWidget(QLabel("Színséma:"))
        app_lay.addWidget(self.theme_combo)

        app_lay.addSpacing(20)
        self.cb_cache = QCheckBox("Memória-cache használata rendezéshez")
        self.cb_cache.setChecked(
            self.layout_state.get("altalanos", "cache_hasznalat", default=True)
        )
        app_lay.addWidget(self.cb_cache)

        app_lay.addSpacing(20)
        app_lay.addWidget(QLabel("<b>Panelek:</b>"))
        self.cb_filter = QCheckBox("Bal oldali műveleti panel")
        self.cb_details = QCheckBox("Jobb oldali részletek panel")
        self.cb_filter.setChecked(not self.parent().filter_dock.isHidden())
        self.cb_details.setChecked(not self.parent().details_dock.isHidden())
        app_lay.addWidget(self.cb_filter)
        app_lay.addWidget(self.cb_details)
        app_lay.addStretch()
        tabs.addTab(app_tab, "Megjelenés")

        # ---- Elrendezés fül ----
        layout_tab = QWidget()
        lt_lay = QVBoxLayout(layout_tab)
        lt_lay.addWidget(QLabel(
            "<b>Elrendezés kezelése</b><br><br>"
            "Az ablak bezárásakor az összes méret és pozíció<br>"
            "automatikusan mentődik a <i>layout_state.json</i> fájlba.<br><br>"
            "Az aktuális állapotot itt mentheted el alapértelmezettként,<br>"
            "illetve itt állíthatod vissza a korábban mentett alapértelmezést."
        ))
        lt_lay.addSpacing(20)

        btn_save_def = QPushButton("💾 Jelenlegi állapot mentése alapértelmezettként")
        btn_save_def.clicked.connect(self._save_layout_default)
        lt_lay.addWidget(btn_save_def)

        lt_lay.addSpacing(10)
        btn_restore_def = QPushButton("🔄 Alapértelmezett elrendezés visszaállítása")
        btn_restore_def.clicked.connect(self._restore_layout_default)
        lt_lay.addWidget(btn_restore_def)

        lt_lay.addStretch()
        tabs.addTab(layout_tab, "Elrendezés")

        # ---- Adatbázis fül ----
        db_tab = QWidget()
        db_lay = QVBoxLayout(db_tab)
        db_lay.addWidget(QLabel(
            "<b>Biztonsági mentés és visszaállítás</b><br><br>"
            "Az adatbázisról bármikor készíthetsz biztonsági másolatot.<br>"
            "Visszaállításkor az aktuális állapotról automatikusan<br>"
            "mentés készül, mielőtt felülíródna."
        ))
        db_lay.addSpacing(10)

        btn_backup = QPushButton("💾 Biztonsági mentés készítése")
        btn_backup.clicked.connect(self._create_backup)
        db_lay.addWidget(btn_backup)

        db_lay.addSpacing(16)
        db_lay.addWidget(QLabel("<b>Elérhető mentések:</b>"))

        self.backup_list = QListWidget()
        self.backup_list.setMinimumHeight(150)
        self.backup_list.setStyleSheet(
            "QListWidget { font-family: Consolas, monospace; font-size: 12px; }"
        )
        db_lay.addWidget(self.backup_list, 1)

        btn_row = QHBoxLayout()
        btn_restore = QPushButton("🔄 Visszaállítás a kijelöltből")
        btn_restore.clicked.connect(self._restore_backup)
        btn_row.addWidget(btn_restore)

        btn_del = QPushButton("🗑 Kijelölt mentés törlése")
        btn_del.clicked.connect(self._delete_backup)
        btn_row.addWidget(btn_del)
        db_lay.addLayout(btn_row)

        db_lay.addStretch()
        tabs.addTab(db_tab, "Adatbázis")

        self._refresh_backup_list()

        layout.addWidget(tabs)
        save_btn = QPushButton("💾 Mentés és alkalmazás")
        save_btn.clicked.connect(self._save)
        layout.addWidget(save_btn)

    def _save(self):
        username = self.user_edit.text().strip()
        password = self.pass_edit.text().strip()

        if not username or not password:
            QMessageBox.warning(
                self, "Hiányzó adatok",
                "A felhasználónév és a jelszó megadása kötelező!\n"
                "Ezek nélkül a scraper és a letöltés nem működik."
            )
            return

        config.set("username", username)
        config.set("password", password)
        config.set("torrent_watch_folder", self.path_edit.text().strip())

        self.parent().filter_dock.setVisible(self.cb_filter.isChecked())
        self.parent().details_dock.setVisible(self.cb_details.isChecked())
        self.config_gui.set("theme", self.theme_combo.currentData())
        self.config_gui.save()
        self.layout_state.set("altalanos", "cache_hasznalat", self.cb_cache.isChecked())
        self.layout_state.save()
        self.parent().setStyleSheet(self.config_gui.generate_stylesheet())
        self.accept()

    def _save_layout_default(self):
        self.parent().save_current_state()
        self.layout_state.save_as_default()
        QMessageBox.information(
            self, "Elrendezés",
            "A jelenlegi elrendezés elmentve alapértelmezettként!\n\n"
            "Ezt bármikor visszaállíthatod a másik gombbal."
        )

    def _restore_layout_default(self):
        reply = QMessageBox.question(
            self, "Visszaállítás",
            "Biztosan visszaállítod az alapértelmezett elrendezést?\n\n"
            "A változás az újraindítás után lép érvénybe.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.layout_state.restore_default()
            QMessageBox.information(
                self, "Kész",
                "Az alapértelmezés visszaállítva!\n"
                "Indítsd újra az alkalmazást az érvénybe lépéshez."
            )
            self.accept()

    # ---- Adatbázis mentés ----

    def _refresh_backup_list(self):
        """Mentések listájának frissítése."""
        self.backup_list.clear()
        for b in list_backups():
            item = QListWidgetItem(
                f"{b['date']}   ({b['size_mb']:.1f} MB)   {b['name']}"
            )
            item.setData(Qt.UserRole, b["path"])
            self.backup_list.addItem(item)
        if self.backup_list.count() == 0:
            item = QListWidgetItem("  (nincs mentés)")
            item.setFlags(Qt.NoItemFlags)
            self.backup_list.addItem(item)

    def _create_backup(self):
        """Biztonsági mentés készítése."""
        result = create_backup()
        if result:
            QMessageBox.information(
                self, "Mentés kész",
                f"Biztonsági mentés sikeresen elkészült!\n\n{result}"
            )
            self._refresh_backup_list()
        else:
            QMessageBox.warning(
                self, "Hiba",
                "A biztonsági mentés nem sikerült!"
            )

    def _restore_backup(self):
        """Visszaállítás a kijelölt mentésből."""
        item = self.backup_list.currentItem()
        if not item or not item.data(Qt.UserRole):
            QMessageBox.information(self, "Nincs kijelölés",
                                    "Válassz ki egy mentést a listából!")
            return

        path = item.data(Qt.UserRole)
        name = item.text().strip()

        reply = QMessageBox.question(
            self, "Visszaállítás megerősítése",
            f"Biztosan visszaállítod az adatbázist?\n\n"
            f"Mentés: {name}\n\n"
            f"Az aktuális adatbázisról automatikusan\n"
            f"biztonsági másolat készül a visszaállítás előtt.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        if restore_backup(path):
            QMessageBox.information(
                self, "Visszaállítás kész",
                "Az adatbázis sikeresen visszaállítva!\n\n"
                "Az alkalmazást újra kell indítani\n"
                "a változások érvénybe lépéséhez."
            )
            self._refresh_backup_list()
        else:
            QMessageBox.warning(self, "Hiba",
                                "A visszaállítás nem sikerült!")

    def _delete_backup(self):
        """Kijelölt mentés törlése."""
        item = self.backup_list.currentItem()
        if not item or not item.data(Qt.UserRole):
            QMessageBox.information(self, "Nincs kijelölés",
                                    "Válassz ki egy mentést a listából!")
            return

        path = item.data(Qt.UserRole)
        reply = QMessageBox.question(
            self, "Törlés megerősítése",
            f"Biztosan törlöd ezt a mentést?\n\n{item.text().strip()}",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if delete_backup(path):
                self._refresh_backup_list()
            else:
                QMessageBox.warning(self, "Hiba",
                                    "A mentés törlése nem sikerült!")


# nCore torrent oldal URL sablon
NCORE_DETAIL_URL = "https://ncore.pro/torrents.php?action=details&id={ncore_id}"
# Moly.hu keresés URL sablon (magyar könyvkatalógus, ismertetők, vásárlás)
MOLY_SEARCH_URL = "https://moly.hu/kereses?utf8=%E2%9C%93&q={query}"


# ====================== DETAILS PANEL ======================
class DetailsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        ls = get_layout_state()
        min_w = ls.get("jobb_panel", "min_szelesseg", default=250)
        self.setMinimumWidth(min_w)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        self.cover_label = QLabel("Nincs borító")
        self.cover_label.setFixedSize(250, 360)
        self.cover_label.setStyleSheet(
            "border: 3px solid #444; background: #1a1a1a; border-radius: 6px;"
        )
        self.cover_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.cover_label, 0, Qt.AlignCenter)

        info = QFrame()
        info_layout = QVBoxLayout(info)
        self.lbl_author = QLabel("Szerző: -")
        self.lbl_title = QLabel("Cím: -")
        for lbl in (self.lbl_author, self.lbl_title):
            lbl.setWordWrap(True)
            info_layout.addWidget(lbl)
        layout.addWidget(info)

        # ---- Linkek ----
        link_style = (
            "QLabel a { color: #5dade2; text-decoration: none; }"
            "QLabel a:hover { text-decoration: underline; }"
            "QLabel { padding: 2px 0; }"
        )

        self.link_ncore = QLabel()
        self.link_ncore.setStyleSheet(link_style)
        self.link_ncore.setTextFormat(Qt.RichText)
        self.link_ncore.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.link_ncore.linkActivated.connect(self._open_url)
        layout.addWidget(self.link_ncore)

        self.link_moly = QLabel()
        self.link_moly.setStyleSheet(link_style)
        self.link_moly.setTextFormat(Qt.RichText)
        self.link_moly.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.link_moly.linkActivated.connect(self._open_url)
        layout.addWidget(self.link_moly)

        layout.addSpacing(6)

        self.desc_text = QTextEdit()
        self.desc_text.setReadOnly(True)
        layout.addWidget(QLabel("<b>Tartalom:</b>"))
        layout.addWidget(self.desc_text, 1)

    def _open_url(self, url: str):
        """Megnyitja az URL-t az alapértelmezett böngészőben."""
        QDesktopServices.openUrl(QUrl(url))

    def update_info(self, book: dict):
        self.lbl_author.setText(f"<b>Szerző:</b> {book.get('szerzo', '-')}")
        self.lbl_title.setText(f"<b>Cím:</b> {book.get('cim', '-')}")
        self.desc_text.setPlainText(book.get("leiras", "Nincs leírás"))

        # Borító
        path = book.get("kep_utvonal")
        if path and os.path.exists(path):
            pix = QPixmap(path).scaled(250, 360, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.cover_label.setPixmap(pix)
        else:
            self.cover_label.setText("Nincs borító")

        # nCore link
        ncore_id = book.get("ncore_id", "")
        if ncore_id:
            url = NCORE_DETAIL_URL.format(ncore_id=ncore_id)
            self.link_ncore.setText(
                f'🌐 <a href="{url}">Torrent oldala az nCore-on</a>'
            )
        else:
            self.link_ncore.setText("")

        # Moly.hu keresés (szerző + cím alapján)
        cim = book.get("cim", "")
        szerzo = book.get("szerzo", "")
        if cim:
            search_term = f"{szerzo} {cim}".strip() if szerzo else cim
            url = MOLY_SEARCH_URL.format(query=quote_plus(search_term))
            self.link_moly.setText(
                f'📚 <a href="{url}">Keresés a Moly.hu-n</a>'
            )
        else:
            self.link_moly.setText("")

    def clear(self):
        self.cover_label.clear()
        self.lbl_author.setText("Szerző: -")
        self.lbl_title.setText("Cím: -")
        self.link_ncore.setText("")
        self.link_moly.setText("")
        self.desc_text.clear()


# ====================== MAIN WINDOW ======================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        init_database()
        gui_config.init_config()
        self.config_gui = gui_config.get_config()
        self.ls = init_layout_state()

        self.downloader = Downloader(log_callback=self.log)
        self.worker = None

        self.use_cache = self.ls.get("altalanos", "cache_hasznalat", default=True)
        self.full_cache: List[Dict] = []

        self.order_by = self.ls.get("altalanos", "rendezes_oszlop", default="feltoltve_datum")
        self.desc = self.ls.get("altalanos", "rendezes_csokkeno", default=True)
        self.page_size = self.ls.get("lapozas", "oldalmeret", default=100)
        self.current_page = 0
        self.total_count = 0

        self.setup_ui()
        self.load_columns_from_state()
        self.reload_cache()
        self.refresh_data(reset_page=True)

        QTimer.singleShot(300, self.apply_saved_sizes)
        QTimer.singleShot(500, self._check_credentials)

    def log(self, msg: str):
        self.statusBar().showMessage(msg, 5000)
        if hasattr(self, 'log_text') and self.log_text.isVisible():
            self.log_text.append(msg)
            self.log_text.verticalScrollBar().setValue(
                self.log_text.verticalScrollBar().maximum()
            )

    def _check_credentials(self):
        """Ha nincs felhasználónév vagy jelszó, megnyitjuk a beállításokat."""
        cfg = config.load_config()
        if not cfg.get("username") or not cfg.get("password"):
            QMessageBox.information(
                self, "Első indítás",
                "Üdvözöllek! A használathoz add meg az nCore\n"
                "felhasználónevedet és jelszavadat a Beállításokban."
            )
            self.show_settings()

    # ======================== UI FELÉPÍTÉS ========================
    def setup_ui(self):
        self.setWindowTitle("nCore eBook Manager")
        self.setStyleSheet(self.config_gui.generate_stylesheet())

        w = self.ls.get("foablak", "szelesseg", default=1780)
        h = self.ls.get("foablak", "magassag", default=1080)
        x = self.ls.get("foablak", "x_pozicio", default=100)
        y = self.ls.get("foablak", "y_pozicio", default=50)
        self.resize(w, h)
        self.move(x, y)
        if self.ls.get("foablak", "maximalizalt", default=False):
            self.showMaximized()

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.statusBar().addPermanentWidget(self.progress_bar)

        # ---- Központi rész ----
        central = QWidget()
        cl = QVBoxLayout(central)

        self.table_view = BookTableView()
        self.table_view.setAlternatingRowColors(
            self.ls.get("tablazat", "valtakozo_sorok", default=True)
        )
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.setSortingEnabled(False)
        self.table_view.setEditTriggers(
            QAbstractItemView.EditKeyPressed | QAbstractItemView.AnyKeyPressed
        )
        self.table_view.doubleClicked.connect(self.on_double_click)
        self.table_view.horizontalHeader().sectionClicked.connect(self.on_header_clicked)
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.show_context_menu)

        self.model = BookTableModel()
        self.proxy = QSortFilterProxyModel()
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.table_view.setModel(self.proxy)

        cl.addWidget(self.table_view, 1)

        # ---- CSÚSZKA ----
        slider_row = QWidget()
        sl_lay = QHBoxLayout(slider_row)
        sl_lay.setContentsMargins(10, 8, 10, 8)

        slider_h = self.ls.get("lapozas", "csuszka_magassag", default=38)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(1)
        self.slider.setMaximum(1)
        self.slider.setMinimumHeight(slider_h)
        self.slider.setStyleSheet(self.ls.get_slider_stylesheet())
        self.slider.valueChanged.connect(self.slider_preview)
        self.slider.sliderReleased.connect(self.slider_released)
        sl_lay.addWidget(QLabel("📍 Oldal:"))
        sl_lay.addWidget(self.slider, 1)
        cl.addWidget(slider_row)

        # ---- LAPOZÁS ----
        nav = QWidget()
        nl = QHBoxLayout(nav)
        nl.setContentsMargins(10, 8, 10, 8)
        for txt, slot in [
            ("⏮ Első", self.first_page),
            ("⏪", self.prev_page),
            ("⏩", self.next_page),
            ("⏭ Utolsó", self.last_page),
        ]:
            btn = QPushButton(txt)
            btn.setFixedWidth(80)
            btn.clicked.connect(slot)
            nl.addWidget(btn)

        self.page_spin = QSpinBox()
        self.page_spin.setFixedWidth(100)
        self.page_spin.setMinimum(1)
        self.page_spin.valueChanged.connect(self.spin_page_changed)
        nl.addWidget(self.page_spin)

        self.lbl_info = QLabel("0 / 0 (0 könyv)")
        nl.addWidget(self.lbl_info)

        self.page_size_combo = QComboBox()
        self.page_size_combo.addItems(["50", "100", "200", "500", "1000"])
        self.page_size_combo.setCurrentText(str(self.page_size))
        self.page_size_combo.currentTextChanged.connect(self.change_page_size)
        nl.addWidget(QLabel("   Oldalméret:"))
        nl.addWidget(self.page_size_combo)

        cl.addWidget(nav)
        self.setCentralWidget(central)

        # ============ BAL OLDALI PANEL ============
        self.filter_dock = QDockWidget("Műveletek / Szűrés", self)
        self.filter_dock.setFeatures(
            QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable
        )
        fw = QWidget()
        fl = QVBoxLayout(fw)
        fl.setContentsMargins(8, 8, 8, 8)
        fl.setSpacing(6)

        fl.addWidget(QLabel("<b>Műveletek</b>"))

        # 1. Alaphelyzet
        self.btn_reset = QPushButton(self.ls.get_button_label("alaphelyzet"))
        self.btn_reset.clicked.connect(self.reset_to_default_view)
        fl.addWidget(self.btn_reset)

        # 2. Kijelöltek letöltése
        self.btn_download_sel = QPushButton(self.ls.get_button_label("kijeloltek_letoltese"))
        self.btn_download_sel.clicked.connect(self.download_selected)
        fl.addWidget(self.btn_download_sel)

        # 3. Kijelölések törlése
        self.btn_clear_sel = QPushButton(self.ls.get_button_label("kijelolesek_torlese"))
        self.btn_clear_sel.clicked.connect(self.clear_marks)
        fl.addWidget(self.btn_clear_sel)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.HLine)
        sep1.setFrameShadow(QFrame.Sunken)
        fl.addWidget(sep1)

        # 4. Új könyvek
        self.btn_update = QPushButton(self.ls.get_button_label("uj_konyvek"))
        self.btn_update.clicked.connect(lambda: self.start_scraper("update"))
        fl.addWidget(self.btn_update)

        # 5. Régi könyvek
        self.btn_older = QPushButton(self.ls.get_button_label("regi_konyvek"))
        self.btn_older.clicked.connect(lambda: self.start_scraper("older"))
        fl.addWidget(self.btn_older)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setFrameShadow(QFrame.Sunken)
        fl.addWidget(sep2)

        # 6. Állj
        self.btn_stop = QPushButton(self.ls.get_button_label("allj"))
        self.btn_stop.clicked.connect(self.stop_all)
        fl.addWidget(self.btn_stop)

        # 7. Beállítások
        self.btn_settings = QPushButton(self.ls.get_button_label("beallitasok"))
        self.btn_settings.clicked.connect(self.show_settings)
        fl.addWidget(self.btn_settings)

        fl.addSpacing(12)

        # ---- Szűrés ----
        fl.addWidget(QLabel("<b>Szűrés</b>"))

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Keresés...")
        self.search_edit.textChanged.connect(lambda: self.refresh_data(reset_page=True))
        fl.addWidget(self.search_edit)

        fl.addWidget(QLabel("Formátum:"))
        self.format_combo = QComboBox()
        self.format_combo.addItem("Minden formátum")
        self._populate_formats()
        self.format_combo.currentTextChanged.connect(
            lambda: self.refresh_data(reset_page=True)
        )
        fl.addWidget(self.format_combo)

        fl.addSpacing(8)

        # ---- Kijelölt könyvek lista ----
        self.marked_label = QLabel("<b>Kijelölt könyvek</b> (0)")
        fl.addWidget(self.marked_label)

        self.marked_list = QListWidget()
        self.marked_list.setMaximumHeight(150)
        self.marked_list.setStyleSheet(
            "QListWidget { background: #1a2a1a; color: #a0d0a0; "
            "font-size: 11px; border: 1px solid #2d7a3a; border-radius: 4px; }"
        )
        fl.addWidget(self.marked_list)

        fl.addSpacing(8)

        # ---- Napló (alapból rejtett) ----
        self.log_label = QLabel("<b>Napló</b>")
        self.log_label.setVisible(False)
        fl.addWidget(self.log_label)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setVisible(False)
        self.log_text.setMaximumHeight(200)
        self.log_text.setStyleSheet(
            "QTextEdit { background: #1a1a2e; color: #c8c8c8; "
            "font-family: Consolas, monospace; font-size: 11px; "
            "border: 1px solid #444; border-radius: 4px; }"
        )
        fl.addWidget(self.log_text, 1)

        fl.addStretch()

        # Kilépés gomb - a panel legalján
        sep_exit = QFrame()
        sep_exit.setFrameShape(QFrame.HLine)
        sep_exit.setFrameShadow(QFrame.Sunken)
        fl.addWidget(sep_exit)

        self.btn_exit = QPushButton(self.ls.get_button_label("kilepes"))
        self.btn_exit.clicked.connect(self.graceful_exit)
        fl.addWidget(self.btn_exit)

        self.filter_dock.setWidget(fw)

        min_w = self.ls.get("bal_panel", "min_szelesseg", default=180)
        fw.setMinimumWidth(min_w)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.filter_dock)
        if not self.ls.get("bal_panel", "lathato", default=True):
            self.filter_dock.hide()

        # ============ JOBB OLDALI PANEL ============
        self.details_dock = QDockWidget("Részletek", self)
        self.details_dock.setFeatures(
            QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetClosable
        )
        self.details_panel = DetailsPanel()
        self.details_dock.setWidget(self.details_panel)
        self.addDockWidget(Qt.RightDockWidgetArea, self.details_dock)
        if not self.ls.get("jobb_panel", "lathato", default=True):
            self.details_dock.hide()

        # Kiválasztás figyelése (jobb oldali részletek panelhez)
        self.table_view.selectionModel().selectionChanged.connect(self.on_selection_changed)
        self.statusBar().showMessage("Kész")

    # ======================== ALAPHELYZET ========================
    def reset_to_default_view(self):
        """Alaphelyzet: minden szűrés, keresés és kijelölés törlése,
        rendezés feltöltési dátum szerint csökkenően, első oldal."""
        self.search_edit.blockSignals(True)
        self.search_edit.clear()
        self.search_edit.blockSignals(False)

        self.format_combo.blockSignals(True)
        self.format_combo.setCurrentIndex(0)
        self.format_combo.blockSignals(False)

        self.model.clear_marks()
        self.update_marked_list()

        self.order_by = "feltoltve_datum"
        self.desc = True
        self.current_page = 0
        self.reload_cache()
        self.refresh_from_cache()
        self.log("📋 Alaphelyzet - legfrissebb feltöltések")

    # ======================== OSZLOPOK ========================
    def load_columns_from_state(self):
        cols = self.ls.get_columns_for_model()
        if not cols:
            cols = [
                {"name": "ncore_id", "label": "Torrent ID"},
                {"name": "szerzo", "label": "Szerző"},
                {"name": "cim", "label": "Cím"},
                {"name": "sorozat", "label": "Sorozat"},
                {"name": "sorozat_szama", "label": "#"},
                {"name": "formatum", "label": "Formátum"},
                {"name": "kiadas_eve", "label": "Év"},
                {"name": "feltoltve_datum", "label": "Feltöltve"},
            ]
        self.model.columns = cols

    def apply_saved_sizes(self):
        widths = self.ls.get_column_widths()
        for i, w in enumerate(widths):
            if i < self.model.columnCount():
                self.table_view.setColumnWidth(i, w)
        bal_w = self.ls.get("bal_panel", "szelesseg", default=280)
        jobb_w = self.ls.get("jobb_panel", "szelesseg", default=420)
        try:
            docks, sizes = [], []
            if not self.filter_dock.isHidden():
                docks.append(self.filter_dock)
                sizes.append(bal_w)
            if not self.details_dock.isHidden():
                docks.append(self.details_dock)
                sizes.append(jobb_w)
            if docks:
                self.resizeDocks(docks, sizes, Qt.Horizontal)
        except Exception:
            pass

    # ======================== ADATBETÖLTÉS ========================
    def reload_cache(self):
        query = self.search_edit.text() if hasattr(self, 'search_edit') else ""
        fmt_text = (
            self.format_combo.currentText()
            if hasattr(self, 'format_combo')
            else "Minden formátum"
        )
        formatum = None if fmt_text == "Minden formátum" else fmt_text

        if self.use_cache:
            self.full_cache = search_books(
                query=query, formatum=formatum,
                limit=0, order_by=self.order_by, desc=self.desc
            )
            self.total_count = len(self.full_cache)
        else:
            self.full_cache = []
            self.total_count = count_books(query=query, formatum=formatum)

    def _populate_formats(self):
        """Formátumok feltöltése - csak érvényes e-book/szöveg típusok."""
        try:
            current = self.format_combo.currentText()
            self.format_combo.blockSignals(True)
            self.format_combo.clear()
            self.format_combo.addItem("Minden formátum")
            for fmt in get_formats():
                if fmt.lower().strip() in VALID_FORMATS:
                    self.format_combo.addItem(fmt)
            idx = self.format_combo.findText(current)
            if idx >= 0:
                self.format_combo.setCurrentIndex(idx)
            self.format_combo.blockSignals(False)
        except Exception:
            pass

    def on_header_clicked(self, logical_index):
        col_name = self.model.columns[logical_index]["name"]
        if self.order_by == col_name:
            self.desc = not self.desc
        else:
            self.order_by = col_name
            self.desc = True
        self.reload_cache()
        self.current_page = 0
        self.refresh_from_cache()

    def refresh_data(self, format_filter=None, reset_page=True):
        if reset_page:
            self.current_page = 0
        try:
            self.reload_cache()
            self.refresh_from_cache()
        except Exception as e:
            import logging
            logging.error(f"refresh_data - Hiba: {e}")
            self.log(f"Hiba: {e}")

    def refresh_from_cache(self):
        if self.use_cache and self.full_cache:
            start = self.current_page * self.page_size
            end = start + self.page_size
            books = self.full_cache[start:end]
        else:
            books = search_books(
                query=self.search_edit.text(),
                formatum=(
                    None if self.format_combo.currentText() == "Minden formátum"
                    else self.format_combo.currentText()
                ),
                limit=self.page_size,
                offset=self.current_page * self.page_size,
                order_by=self.order_by,
                desc=self.desc
            )
        self.model.set_books(books)
        self.update_ui()

    # ======================== UI FRISSÍTÉS ========================
    def update_ui(self):
        total_pages = max(1, (self.total_count + self.page_size - 1) // self.page_size)

        self.page_spin.blockSignals(True)
        self.slider.blockSignals(True)

        self.page_spin.setMaximum(total_pages)
        self.page_spin.setValue(self.current_page + 1)
        self.lbl_info.setText(
            f"{self.current_page+1} / {total_pages} "
            f"({self.total_count:,} könyv)".replace(",", " ")
        )

        self.slider.setMaximum(total_pages)
        self.slider.setValue(self.current_page + 1)

        self.slider.blockSignals(False)
        self.page_spin.blockSignals(False)

    def slider_preview(self, value):
        total_pages = max(1, (self.total_count + self.page_size - 1) // self.page_size)
        self.lbl_info.setText(
            f"{value} / {total_pages} "
            f"({self.total_count:,} könyv)".replace(",", " ")
        )

    def slider_released(self):
        self.current_page = self.slider.value() - 1
        self.refresh_from_cache()

    def spin_page_changed(self, value):
        new_page = value - 1
        if new_page != self.current_page:
            self.current_page = new_page
            self.refresh_from_cache()

    # ======================== HELYI MENÜ ========================
    def show_context_menu(self, pos):
        """Helyi menü: rendezés minden oszlopban,
        keresés a cella tartalmával (ncore_id, szerző, cím, sorozat)."""
        if QApplication.keyboardModifiers() & Qt.ControlModifier:
            return

        index = self.table_view.indexAt(pos)
        if not index.isValid():
            return

        src_index = self.proxy.mapToSource(index)
        col_idx = src_index.column()
        col_name = self.model.columns[col_idx]["name"]
        col_label = self.model.columns[col_idx]["label"]
        cell_value = self.model.data(src_index, Qt.DisplayRole) or ""

        menu = QMenu(self)

        menu.addAction(
            f"↑ Rendezés: {col_label} - növekvő",
            lambda cn=col_name: self._sort_column(cn, False)
        )
        menu.addAction(
            f"↓ Rendezés: {col_label} - csökkenő",
            lambda cn=col_name: self._sort_column(cn, True)
        )

        if col_name in SEARCHABLE_COLUMNS and cell_value.strip():
            menu.addSeparator()
            display = cell_value if len(cell_value) <= 40 else cell_value[:37] + "..."
            menu.addAction(
                f"🔍 Keresés erre: {display}",
                lambda val=cell_value.strip(): self._search_from_context(val)
            )

        menu.exec(self.table_view.viewport().mapToGlobal(pos))

    def _sort_column(self, col_name: str, descending: bool):
        """Rendezés a megadott oszlop szerint."""
        self.order_by = col_name
        self.desc = descending
        self.reload_cache()
        self.current_page = 0
        self.refresh_from_cache()

    def _search_from_context(self, value: str):
        """Keresés a helyi menüből - halmozódó szűrés.

        Az új kifejezés hozzáfűződik a meglévő kereséshez,
        így a szűrés egyre szűkül. Az Alaphelyzet gomb törli az összeset.
        """
        current = self.search_edit.text().strip()
        if current:
            if value.lower() in current.lower():
                return
            new_text = f"{current} {value}"
        else:
            new_text = value
        self.search_edit.setText(new_text)

    # ======================== LAPOZÁS ========================
    def first_page(self):
        self.current_page = 0
        self.refresh_from_cache()

    def prev_page(self):
        self.current_page = max(0, self.current_page - 1)
        self.refresh_from_cache()

    def next_page(self):
        total_pages = max(1, (self.total_count + self.page_size - 1) // self.page_size)
        self.current_page = min(self.current_page + 1, total_pages - 1)
        self.refresh_from_cache()

    def last_page(self):
        total_pages = max(1, (self.total_count + self.page_size - 1) // self.page_size)
        self.current_page = total_pages - 1
        self.refresh_from_cache()

    def change_page_size(self):
        self.page_size = int(self.page_size_combo.currentText())
        self.current_page = 0
        self.refresh_data(reset_page=True)

    # ======================== SCRAPER ========================
    def start_scraper(self, mode: str):
        """Scraper indítása háttérszálban."""
        if self.worker and self.worker.isRunning():
            self.log("⏳ A scraper még fut, várd meg a befejezését!")
            return

        cfg = config.load_config()
        if not cfg.get("username") or not cfg.get("password"):
            QMessageBox.warning(
                self, "Hiányzó bejelentkezési adatok",
                "Nincs megadva felhasználónév vagy jelszó!\n"
                "Add meg a Beállítások menüben."
            )
            self.show_settings()
            return

        self.worker = ScraperWorker(mode)
        self.worker.finished.connect(self.on_scraper_finished)
        self.worker.log_signal.connect(self.log)
        self.worker.start()
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.btn_update.setEnabled(False)
        self.btn_older.setEnabled(False)
        self._show_log_panel(True)
        self.log_text.clear()
        mode_name = "Új könyvek keresése" if mode == "update" else "Régi könyvek keresése"
        self.log(f"▶ {mode_name} indul...")

    def on_scraper_finished(self, count):
        self.progress_bar.setVisible(False)
        self.btn_update.setEnabled(True)
        self.btn_older.setEnabled(True)

        if count == -1:
            QMessageBox.information(
                self, "Üres adatbázis",
                "Az adatbázis üres!\n\n"
                "Először az 'Új könyvek' gombbal tölts le adatokat."
            )
        elif count == 0 and self.worker and self.worker.mode == "older":
            QMessageBox.information(
                self, "Minden megvan",
                "Nincs mit letölteni - a legkorábbi torrent adatai\n"
                "is szerepelnek már az adatbázisban."
            )
        else:
            self.log(f"✅ Kész! {count} könyv mentve.")

        self._populate_formats()
        self.refresh_data(reset_page=True)

    # ======================== MEGJELÖLÉS / KIVÁLASZTÁS ========================
    def on_selection_changed(self):
        """A tábla kiválasztás változásakor frissítjük a jobb oldali részleteket."""
        idx = self.table_view.selectionModel().selectedRows()
        if idx:
            src = self.proxy.mapToSource(idx[0])
            if src.row() < len(self.model.books):
                book = self.model.books[src.row()]
                self.details_panel.update_info(book)

    def on_double_click(self, index):
        """Dupla kattintás: megjelölés ki/be váltása."""
        src_index = self.proxy.mapToSource(index)
        self.model.toggle_mark(src_index.row())
        self.update_marked_list()

    def clear_marks(self):
        """Minden megjelölés törlése."""
        self.model.clear_marks()
        self.update_marked_list()
        self.log("Kijelölések törölve.")

    def update_marked_list(self):
        """A bal panelen lévő kijelölt könyvek lista frissítése."""
        self.marked_list.clear()
        count = len(self.model.marked_ids)
        self.marked_label.setText(f"<b>Kijelölt könyvek</b> ({count})")

        if count == 0:
            return

        # Az aktuális oldalon lévő megjelölt könyvek adatait jelenítjük meg
        for book in self.model.books:
            nid = str(book.get("ncore_id", ""))
            if nid in self.model.marked_ids:
                szerzo = book.get("szerzo", "?")
                cim = book.get("cim", "?")
                item = QListWidgetItem(f"{szerzo} - {cim}")
                self.marked_list.addItem(item)

        # Ha vannak más oldalon megjelöltek is, jelezzük
        on_page = sum(
            1 for b in self.model.books
            if str(b.get("ncore_id", "")) in self.model.marked_ids
        )
        if count > on_page:
            item = QListWidgetItem(f"... +{count - on_page} másik oldalon")
            item.setForeground(QBrush(QColor("#888")))
            self.marked_list.addItem(item)

    def download_selected(self):
        """A megjelölt (zöld) könyvek letöltése."""
        marked = self.model.marked_ids
        if not marked:
            QMessageBox.information(self, "Nincs kijelölés",
                                    "Jelölj ki legalább egy könyvet!\n\n"
                                    "Dupla kattintással vagy Ctrl+kattintással jelölhetsz.")
            return

        ncore_ids = list(marked)
        if not self.downloader.connect():
            QMessageBox.warning(self, "Hiba", "A bejelentkezés sikertelen!")
            return
        self._show_log_panel(True)
        self.log_text.clear()
        self.log(f"📥 {len(ncore_ids)} torrent letöltése indul...")
        ok = 0
        for nid in ncore_ids:
            if self.downloader.download_by_ncore_id(nid):
                ok += 1
                self.log(f"✅ {nid} letöltve ({ok}/{len(ncore_ids)})")
            else:
                self.log(f"❌ {nid} sikertelen")
        self.log(f"📥 Letöltés kész: {ok}/{len(ncore_ids)} sikeres")

    # ======================== ÁLLJ / KILÉPÉS ========================
    def stop_all(self):
        """Minden futó művelet leállítása."""
        stopped = False
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.quit()
            self.worker.wait(3000)
            self.progress_bar.setVisible(False)
            self.btn_update.setEnabled(True)
            self.btn_older.setEnabled(True)
            stopped = True

        if stopped:
            self.log("🛑 Minden művelet leállítva.")
        else:
            self.log("Nincs futó művelet.")

    def graceful_exit(self):
        """Leállít mindent, menti az állapotot, majd bezárja az alkalmazást."""
        self.stop_all()
        self.save_current_state()
        QApplication.quit()

    # ======================== BEÁLLÍTÁSOK ========================
    def _show_log_panel(self, visible: bool):
        """Napló panel megjelenítése vagy elrejtése."""
        if hasattr(self, 'log_text'):
            self.log_label.setVisible(visible)
            self.log_text.setVisible(visible)

    def show_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec():
            self.use_cache = self.ls.get("altalanos", "cache_hasznalat", default=True)
            self.refresh_data(reset_page=True)

    # ======================== ÁLLAPOT MENTÉS ========================
    def save_current_state(self):
        geo = self.geometry()
        self.ls.set("foablak", "szelesseg", geo.width())
        self.ls.set("foablak", "magassag", geo.height())
        self.ls.set("foablak", "x_pozicio", geo.x())
        self.ls.set("foablak", "y_pozicio", geo.y())
        self.ls.set("foablak", "maximalizalt", self.isMaximized())

        self.ls.set("bal_panel", "lathato", not self.filter_dock.isHidden())
        self.ls.set("bal_panel", "szelesseg", self.filter_dock.width())

        self.ls.set("jobb_panel", "lathato", not self.details_dock.isHidden())
        self.ls.set("jobb_panel", "szelesseg", self.details_dock.width())

        widths = [
            self.table_view.columnWidth(i)
            for i in range(self.model.columnCount())
        ]
        self.ls.set_column_widths(widths)

        self.ls.set("lapozas", "oldalmeret", self.page_size)
        self.ls.set("altalanos", "rendezes_oszlop", self.order_by)
        self.ls.set("altalanos", "rendezes_csokkeno", self.desc)
        self.ls.set("altalanos", "cache_hasznalat", self.use_cache)

        self.ls.save()

    def closeEvent(self, event):
        self.stop_all()
        self.save_current_state()
        event.accept()


# ====================== INDÍTÁS ======================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
