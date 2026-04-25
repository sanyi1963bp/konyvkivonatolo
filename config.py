"""
Config kezelő modul
===================
JSON alapú konfiguráció: credentials, útvonalak, beállítások
"""

import json
import os

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "username": "",
    "password": "",
    "download_path": "./torrents",
    "covers_path": "./boritok",
    "database_path": "./ncore_konyvtar.db",
    "last_history_page": 1,
    "request_delay": 0.5,  # másodperc kérések között
}


def load_config() -> dict:
    """Konfiguráció betöltése, hiányzó mezők pótlásával."""
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
        # Hiányzó kulcsok pótlása
        for key, value in DEFAULT_CONFIG.items():
            if key not in config:
                config[key] = value
        return config
    except (json.JSONDecodeError, IOError):
        return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> bool:
    """Konfiguráció mentése."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        return True
    except IOError:
        return False


def get(key: str, default=None):
    """Egy konfigurációs érték lekérése."""
    config = load_config()
    return config.get(key, default)


def set(key: str, value) -> bool:
    """Egy konfigurációs érték beállítása és mentése."""
    config = load_config()
    config[key] = value
    return save_config(config)


def ensure_directories():
    """Szükséges mappák létrehozása."""
    config = load_config()
    
    for path_key in ["download_path", "covers_path"]:
        path = config.get(path_key)
        if path and not os.path.exists(path):
            try:
                os.makedirs(path)
            except OSError:
                pass


def is_configured() -> bool:
    """Van-e beállítva username és password?"""
    config = load_config()
    return bool(config.get("username")) and bool(config.get("password"))


def setup_wizard():
    """Interaktív beállítás, ha nincs még konfigurálva."""
    print("\n" + "=" * 50)
    print("Első indítás - Konfiguráció")
    print("=" * 50)
    
    config = load_config()
    
    config["username"] = input("\nnCore felhasználónév: ").strip()
    config["password"] = input("nCore jelszó: ").strip()
    
    dl_path = input(f"Letöltési mappa [{config['download_path']}]: ").strip()
    if dl_path:
        config["download_path"] = dl_path
    
    save_config(config)
    ensure_directories()
    
    print("\n✅ Konfiguráció mentve!")
    return config
