"""
Downloader modul - Javított URL kezeléssel
=========================================
"""

import os
import time
import re
from typing import List, Optional, Callable
from bs4 import BeautifulSoup

from config import load_config
from database import get_book_by_id, get_book_by_ncore_id
from scraper import NCoreSession, BASE_URL # BASE_URL importálása a scraperből

class Downloader:
    """Torrent fájlok letöltése."""
    
    def __init__(self, log_callback: Optional[Callable[[str], None]] = None):
        self.ncore = NCoreSession()
        self.log_callback = log_callback or print
        self.config = load_config()
        self.download_path = self.config.get("torrent_watch_folder", self.config.get("download_path", "./torrents"))
        
        if not os.path.exists(self.download_path):
            try:
                os.makedirs(self.download_path)
            except:
                pass
    
    def log(self, message: str):
        self.log_callback(message)
    
    def connect(self) -> bool:
        username = self.config.get("username")
        password = self.config.get("password")
        if not username or not password:
            return False
        return self.ncore.login(username, password)
    
    def _get_torrent_download_url(self, page_url: str) -> Optional[str]:
        """Torrent letöltési URL kinyerése és validálása."""
        resp = self.ncore.get(page_url)
        if not resp:
            return None
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        download_div = soup.find("div", class_="download")
        if download_div:
            a = download_div.find("a")
            if a and a.get("href"):
                url = a["href"]
                # JAVÍTÁS: Ha a link relatív (nincs benne http), hozzáadjuk a bázis URL-t
                if url.startswith("torrents.php") or url.startswith("/torrents.php"):
                    if not url.startswith("/"):
                        url = "/" + url
                    url = f"{BASE_URL}{url}"
                return url
        
        return None
    
    def _sanitize_filename(self, name: str) -> str:
        name = re.sub(r'[<>:"/\\|?*]', '', name)
        return name.strip()[:200]
    
    def download_by_ncore_id(self, ncore_id: str) -> bool:
        book = get_book_by_ncore_id(ncore_id)
        if not book: return False
        
        url = book.get("teljes_link")
        filename = self._sanitize_filename(f"{book.get('szerzo', 'Ism')} - {book.get('cim', 'Ism')}")
        
        dl_url = self._get_torrent_download_url(url)
        if not dl_url:
            self.log("❌ Letöltési link nem található!")
            return False
            
        try:
            resp = self.ncore.session.get(dl_url, timeout=30)
            if resp.status_code == 200:
                filepath = os.path.join(self.download_path, f"{filename}.torrent")
                with open(filepath, "wb") as f:
                    f.write(resp.content)
                return True
        except Exception as e:
            self.log(f"❌ Hiba: {e}")
            
        return False