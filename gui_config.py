"""
GUI Konfiguráció kezelő
=======================
Témák, ablak pozíciók és táblázat stílusok tárolása.
"""

import json
import os
from typing import Any, Dict, Optional
from pathlib import Path

# Színsémák definiálása
THEMES = {
    "midnight": {
        "name": "Éjféli (Narancs)",
        "background": "#0d0d0d",
        "background_alt": "#1a1a1a",
        "foreground": "#f0f0f0",
        "foreground_dim": "#888888",
        "accent": "#ff6b35",
        "accent_hover": "#ff8c5a",
        "accent_text": "#000000",
        "success": "#00e676",
        "warning": "#ffc107",
        "error": "#ff1744",
        "border": "#333333",
        "selection": "#ff6b35",
        "table_row_alt": "#141414",
        "scrollbar": "#444444",
        "scrollbar_hover": "#555555",
    },
    "ocean": {
        "name": "Óceán Kék",
        "background": "#0a192f",
        "background_alt": "#112240",
        "foreground": "#ccd6f6",
        "foreground_dim": "#8892b0",
        "accent": "#64ffda",
        "accent_hover": "#89ffea",
        "accent_text": "#0a192f",
        "success": "#64ffda",
        "warning": "#ffd54f",
        "error": "#ff5370",
        "border": "#233554",
        "selection": "#1d4a6e",
        "table_row_alt": "#0f2444",
        "scrollbar": "#233554",
        "scrollbar_hover": "#2d4a6a",
    },
    "forest": {
        "name": "Erdei Zöld",
        "background": "#1b261e",
        "background_alt": "#25332a",
        "foreground": "#e0e0e0",
        "foreground_dim": "#90a090",
        "accent": "#81c784",
        "accent_hover": "#a5d6a7",
        "accent_text": "#1b261e",
        "success": "#a5d6a7",
        "warning": "#fff59d",
        "error": "#ef9a9a",
        "border": "#2e3d32",
        "selection": "#388e3c",
        "table_row_alt": "#202b22",
        "scrollbar": "#2e3d32",
        "scrollbar_hover": "#3e4d42",
    },
    "classic_dark": {
        "name": "Klasszikus Sötét",
        "background": "#1e1e1e",
        "background_alt": "#2d2d2d",
        "foreground": "#d4d4d4",
        "foreground_dim": "#808080",
        "accent": "#007acc",
        "accent_hover": "#1e90ff",
        "accent_text": "#ffffff",
        "success": "#6a9955",
        "warning": "#d7ba7d",
        "error": "#f44747",
        "border": "#3e3e42",
        "selection": "#264f78",
        "table_row_alt": "#252526",
        "scrollbar": "#3e3e42",
        "scrollbar_hover": "#4e4e52",
    }
}

DEFAULT_CONFIG = {
    "theme": "midnight",
    "font": {
        "family": "Segoe UI",
        "size": 10,
        "table_size": 9
    }
}

class GUIConfig:
    def __init__(self, config_path: Optional[str] = None):
        if config_path:
            self.config_path = Path(config_path)
        else:
            self.config_path = Path(__file__).parent / "gui_config.json"
        
        self.config: Dict[str, Any] = {}
        self.load()

    def load(self):
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.config = DEFAULT_CONFIG.copy()
        else:
            self.config = DEFAULT_CONFIG.copy()

    def save(self):
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except IOError:
            pass

    def get(self, *keys, default=None):
        value = self.config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

    def set(self, *keys_and_value):
        if len(keys_and_value) < 2: return
        keys = keys_and_value[:-1]
        value = keys_and_value[-1]
        target = self.config
        for key in keys[:-1]:
            if key not in target: target[key] = {}
            target = target[key]
        target[keys[-1]] = value

    def get_theme(self):
        theme_name = self.get("theme", default="midnight")
        return THEMES.get(theme_name, THEMES["midnight"])

    def generate_stylesheet(self) -> str:
        t = self.get_theme()
        font_family = self.get("font", "family", default="Segoe UI")
        font_size = self.get("font", "size", default=10)
        
        return f"""
        QWidget {{
            background-color: {t['background']};
            color: {t['foreground']};
            font-family: "{font_family}";
            font-size: {font_size}pt;
        }}
        QMainWindow, QDialog {{
            background-color: {t['background']};
        }}
        QHeaderView::section {{
            background-color: {t['background_alt']};
            color: {t['foreground']};
            padding: 5px;
            border: 1px solid {t['border']};
            font-weight: bold;
        }}
        QTableView {{
            background-color: {t['background']};
            gridline-color: {t['border']};
            selection-background-color: {t['selection']};
            alternate-background-color: {t['table_row_alt']};
        }}
        QPushButton {{
            background-color: {t['accent']};
            color: {t['accent_text']};
            border-radius: 4px;
            padding: 6px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: {t['accent_hover']};
        }}
        QLineEdit, QTextEdit, QComboBox, QSpinBox {{
            background-color: {t['background_alt']};
            border: 1px solid {t['border']};
            border-radius: 3px;
            padding: 4px;
        }}
        QTabWidget::pane {{
            border: 1px solid {t['border']};
        }}
        QTabBar::tab {{
            background: {t['background_alt']};
            padding: 8px;
            margin-right: 2px;
        }}
        QTabBar::tab:selected {{
            background: {t['accent']};
            color: {t['accent_text']};
        }}
        """

_config_instance: Optional[GUIConfig] = None

def get_config() -> GUIConfig:
    global _config_instance
    if _config_instance is None:
        _config_instance = GUIConfig()
    return _config_instance

def init_config(config_path: Optional[str] = None) -> GUIConfig:
    global _config_instance
    _config_instance = GUIConfig(config_path)
    return _config_instance