"""
Elrendezés állapotkezelő modul
===============================
Az alkalmazás összes vizuális állapotát tárolja és kezeli.

Két fájl:
  - layout_state.json     = aktuális (futó) állapot, minden kilépéskor frissül
  - layout_default.json   = felhasználó által mentett alapértelmezett állapot

Működés:
  - Induláskor: layout_state.json-ból tölt be (ha van), különben beépített default
  - Kilépéskor: layout_state.json-ba ment
  - "Mentés defaultként": layout_state.json → layout_default.json másolás
  - "Default visszaállítása": layout_default.json → layout_state.json másolás + újratöltés
"""

import json
import os
import shutil
from typing import Any, Dict, Optional
from pathlib import Path


# ============================================================
#  BEÉPÍTETT ALAPÉRTELMEZETT ÁLLAPOT
#  (Ha sem state, sem default fájl nem létezik)
# ============================================================
BUILTIN_DEFAULT: Dict[str, Any] = {

    # ----------------------------------------------------------
    #  FŐABLAK
    #  Az alkalmazás fő ablakának mérete és pozíciója.
    #  "maximized": ha True, a többi érték figyelmen kívül marad.
    # ----------------------------------------------------------
    "foablak": {
        "szelesseg": 1780,
        "magassag": 1080,
        "x_pozicio": 100,
        "y_pozicio": 50,
        "maximalizalt": False
    },

    # ----------------------------------------------------------
    #  BAL OLDALI PANEL (Szűrés + Műveletek)
    #  A QDockWidget szélessége és láthatósága.
    #  "min_szelesseg": az összehúzás alsó határa pixelben.
    # ----------------------------------------------------------
    "bal_panel": {
        "lathato": True,
        "szelesseg": 280,
        "min_szelesseg": 180
    },

    # ----------------------------------------------------------
    #  JOBB OLDALI PANEL (Részletek / Borító / Leírás)
    #  Ugyanúgy QDockWidget, méretezhetően.
    # ----------------------------------------------------------
    "jobb_panel": {
        "lathato": True,
        "szelesseg": 420,
        "min_szelesseg": 250
    },

    # ----------------------------------------------------------
    #  TÁBLÁZAT OSZLOPOK
    #  Minden oszlop neve, címkéje, szélessége és láthatósága.
    #  A "szelessegek" lista a tényleges pixel-szélességeket tartalmazza
    #  az oszlopok sorrendjében.
    # ----------------------------------------------------------
    "tablazat": {
        "oszlopok": [
            {"nev": "ncore_id",        "cimke": "Torrent ID", "szelesseg": 90,  "lathato": True},
            {"nev": "szerzo",          "cimke": "Szerző",     "szelesseg": 180, "lathato": True},
            {"nev": "cim",             "cimke": "Cím",        "szelesseg": 300, "lathato": True},
            {"nev": "sorozat",         "cimke": "Sorozat",    "szelesseg": 140, "lathato": True},
            {"nev": "sorozat_szama",   "cimke": "#",          "szelesseg": 50,  "lathato": True},
            {"nev": "formatum",        "cimke": "Formátum",   "szelesseg": 80,  "lathato": True},
            {"nev": "kiadas_eve",      "cimke": "Év",         "szelesseg": 60,  "lathato": True},
            {"nev": "meret",           "cimke": "Méret",      "szelesseg": 80,  "lathato": True},
            {"nev": "feltoltve_datum", "cimke": "Feltöltve",  "szelesseg": 100, "lathato": True},
            {"nev": "cimkek",          "cimke": "Címkék",     "szelesseg": 150, "lathato": False}
        ],
        "sor_magassag": 28,
        "valtakozo_sorok": True,
        "racs_lathato": False
    },

    # ----------------------------------------------------------
    #  LAPOZÁS
    #  Az oldalméret (hány sor jelenik meg egyszerre),
    #  és a csúszka stílusa.
    # ----------------------------------------------------------
    "lapozas": {
        "oldalmeret": 100,
        "csuszka_magassag": 38
    },

    # ----------------------------------------------------------
    #  GOMBOK (bal panelen)
    #  Minden gomb felirata és ikonja.
    #  A funkció a kódban van hozzárendelve, itt csak a feliratok.
    # ----------------------------------------------------------
    "gombok": {
        "alaphelyzet":            "📋 Alaphelyzet",
        "kijeloltek_letoltese":   "📥 Kijelöltek letöltése",
        "kijelolesek_torlese":    "✖ Kijelölések törlése",
        "uj_konyvek":             "🚀 Új könyvek",
        "regi_konyvek":           "📜 Régi könyvek",
        "allj":                   "🛑 Állj",
        "beallitasok":            "⚙️ Beállítások",
        "kilepes":                "🚪 Kilépés"
    },

    # ----------------------------------------------------------
    #  CSÚSZKA STÍLUS
    #  A vízszintes oldal-csúszka CSS-szerű megjelenése.
    # ----------------------------------------------------------
    "csuszka_stilus": {
        "groove_szin": "#333",
        "groove_magassag": 16,
        "handle_szin": "#ff6b35",
        "handle_keret_szin": "#fff",
        "handle_meret": 32,
        "handle_keret_vastagsag": 3
    },

    # ----------------------------------------------------------
    #  ÁLTALÁNOS
    #  Egyéb beállítások, amelyek nem illeszkednek más szekcióba.
    # ----------------------------------------------------------
    "altalanos": {
        "cache_hasznalat": True,
        "rendezes_oszlop": "feltoltve_datum",
        "rendezes_csokkeno": True
    }
}


# ============================================================
#  LayoutState osztály
# ============================================================
class LayoutState:
    """Az alkalmazás teljes vizuális állapotát kezeli."""

    def __init__(self, base_dir: Optional[str] = None):
        d = Path(base_dir) if base_dir else Path(__file__).parent
        self.state_path = d / "layout_state.json"
        self.default_path = d / "layout_default.json"
        self.state: Dict[str, Any] = {}
        self.load()

    # ---- Betöltés / Mentés ----

    def load(self):
        """Állapot betöltése: state → default → beépített."""
        self.state = self._read_json(self.state_path)
        if not self.state:
            self.state = self._read_json(self.default_path)
        if not self.state:
            self.state = self._deep_copy(BUILTIN_DEFAULT)

    def save(self):
        """Aktuális állapot mentése a state fájlba."""
        self._write_json(self.state_path, self.state)

    def save_as_default(self):
        """Aktuális állapot mentése alapértelmezettként is."""
        self._write_json(self.default_path, self.state)

    def restore_default(self):
        """Alapértelmezett állapot visszaállítása.
        Ha van mentett default, azt használja; különben a beépítettet.
        """
        default = self._read_json(self.default_path)
        if default:
            self.state = default
        else:
            self.state = self._deep_copy(BUILTIN_DEFAULT)
        self.save()

    # ---- Getter / Setter ----

    def get(self, *keys, default=None):
        """Érték lekérése pont-szeparált kulcsokkal.
        Pl.: get("foablak", "szelesseg")
        """
        value = self.state
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

    def set(self, *keys_and_value):
        """Érték beállítása.
        Pl.: set("foablak", "szelesseg", 1920)
        """
        if len(keys_and_value) < 2:
            return
        keys = keys_and_value[:-1]
        value = keys_and_value[-1]
        target = self.state
        for key in keys[:-1]:
            if key not in target:
                target[key] = {}
            target = target[key]
        target[keys[-1]] = value

    # ---- Segéd: oszlopok konvertálása a BookTableModel-hez ----

    def get_columns_for_model(self):
        """Visszaadja az oszlopokat a model számára [{name, label}, ...].
        
        Ha a mentett állapotban nincs ncore_id oszlop, automatikusan
        hozzáadja elsőként (régi layout_state.json kompatibilitás).
        """
        cols = self.get("tablazat", "oszlopok", default=[])
        result = [{"name": c["nev"], "label": c["cimke"]} for c in cols if c.get("lathato", True)]
        
        # Biztosítjuk, hogy ncore_id mindig az első oszlop legyen
        has_ncore = any(c["name"] == "ncore_id" for c in result)
        if not has_ncore and result:
            result.insert(0, {"name": "ncore_id", "label": "Torrent ID"})
            # Frissítjük a mentett állapotot is
            saved_cols = self.get("tablazat", "oszlopok", default=[])
            has_saved = any(c["nev"] == "ncore_id" for c in saved_cols)
            if not has_saved:
                saved_cols.insert(0, {
                    "nev": "ncore_id", "cimke": "Torrent ID",
                    "szelesseg": 90, "lathato": True
                })
                self.set("tablazat", "oszlopok", saved_cols)
        
        return result

    def get_column_widths(self):
        """Visszaadja a látható oszlopok szélességét listában."""
        cols = self.get("tablazat", "oszlopok", default=[])
        return [c["szelesseg"] for c in cols if c.get("lathato", True)]

    def set_column_widths(self, widths: list):
        """Frissíti a látható oszlopok szélességeit."""
        cols = self.get("tablazat", "oszlopok", default=[])
        visible = [c for c in cols if c.get("lathato", True)]
        for i, w in enumerate(widths):
            if i < len(visible):
                visible[i]["szelesseg"] = w

    # ---- Gombok feliratai ----

    def get_button_label(self, key: str) -> str:
        """Egy gomb feliratának lekérése a kulcs alapján."""
        return self.get("gombok", key, default=key)

    # ---- Csúszka stílus ----

    def get_slider_stylesheet(self) -> str:
        """CSS stylesheet generálása a csúszka beállításaiból."""
        s = self.get("csuszka_stilus", default={})
        g_color = s.get("groove_szin", "#333")
        g_h = s.get("groove_magassag", 16)
        h_color = s.get("handle_szin", "#ff6b35")
        h_border = s.get("handle_keret_szin", "#fff")
        h_size = s.get("handle_meret", 32)
        h_bw = s.get("handle_keret_vastagsag", 3)
        r = g_h // 2
        hr = h_size // 2
        margin = -(h_size - g_h) // 2
        return (
            f"QSlider::groove:horizontal {{ height: {g_h}px; background: {g_color}; border-radius: {r}px; }}\n"
            f"QSlider::handle:horizontal {{ background: {h_color}; border: {h_bw}px solid {h_border}; "
            f"width: {h_size}px; height: {h_size}px; margin: {margin}px 0; border-radius: {hr}px; }}"
        )

    # ---- Belső segéd ----

    @staticmethod
    def _read_json(path: Path) -> dict:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {}

    @staticmethod
    def _write_json(path: Path, data: dict):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except IOError:
            pass

    @staticmethod
    def _deep_copy(d: dict) -> dict:
        return json.loads(json.dumps(d))


# ============================================================
#  Singleton hozzáférés
# ============================================================
_instance: Optional[LayoutState] = None

def get_layout_state() -> LayoutState:
    global _instance
    if _instance is None:
        _instance = LayoutState()
    return _instance

def init_layout_state(base_dir: Optional[str] = None) -> LayoutState:
    global _instance
    _instance = LayoutState(base_dir)
    return _instance
