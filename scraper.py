"""
Scraper modul
=============
nCore e-book scraping requests + BeautifulSoup segítségével
"""

import re
import os
import time
import urllib.request
from typing import Optional, Dict, List, Callable, Generator
from bs4 import BeautifulSoup
import requests

from config import load_config, get, set as config_set
from database import save_book, get_latest_date, get_oldest_date, book_exists, count_books as db_count_books

# nCore URL-ek
BASE_URL = "https://ncore.pro"
LOGIN_URL = f"{BASE_URL}/login.php"
EBOOK_URL = f"{BASE_URL}/torrents.php?tipus=ebook_hun"


class NCoreSession:
    """nCore session kezelő."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "hu-HU,hu;q=0.9,en;q=0.8",
        })
        self.logged_in = False
    
    def login(self, username: str, password: str) -> bool:
        """Bejelentkezés az nCore-ra."""
        try:
            login_data = {
                "nev": username,
                "pass": password,
                "set_lang": "hu",
                "submitted": "1",
            }
            
            resp = self.session.post(LOGIN_URL, data=login_data, timeout=15, allow_redirects=True)
            
            if "login.php" not in resp.url:
                self.logged_in = True
                return True
            return False
            
        except requests.RequestException:
            return False
    
    def get(self, url: str) -> Optional[requests.Response]:
        """GET kérés a session-nel."""
        if not self.logged_in:
            return None
        try:
            return self.session.get(url, timeout=15)
        except requests.RequestException:
            return None


class Scraper:
    """nCore e-book scraper."""
    
    def __init__(self, log_callback: Optional[Callable[[str], None]] = None):
        self.ncore = NCoreSession()
        self.log_callback = log_callback or print
        self.config = load_config()
        self.stop_requested = False
        self.covers_path = self.config.get("covers_path", "./boritok")
        self.delay = self.config.get("request_delay", 0.5)
        
        # Covers mappa létrehozása
        if not os.path.exists(self.covers_path):
            os.makedirs(self.covers_path)
    
    def log(self, message: str):
        """Üzenet logolása."""
        self.log_callback(message)
    
    def stop(self):
        """Scraping leállítása."""
        self.stop_requested = True
    
    def connect(self) -> bool:
        """Kapcsolódás és bejelentkezés."""
        username = self.config.get("username")
        password = self.config.get("password")
        
        if not username or not password:
            self.log("❌ Nincs megadva felhasználónév/jelszó!")
            return False
        
        self.log("🔐 Bejelentkezés...")
        if self.ncore.login(username, password):
            self.log("✅ Sikeres bejelentkezés!")
            return True
        else:
            self.log("❌ Bejelentkezés sikertelen!")
            return False
    
    def get_page_torrents(self, page: int = 1) -> List[str]:
        """Egy oldal torrent linkjeinek lekérése."""
        url = f"{EBOOK_URL}&oldal={page}"
        resp = self.ncore.get(url)
        
        if not resp:
            return []
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        links = []
        
        # Torrent linkek keresése
        for div in soup.find_all("div", class_="torrent_txt"):
            a = div.find("a")
            if a and a.get("href"):
                links.append(f"{BASE_URL}/{a['href']}")
        
        # Alternatív módszer
        if not links:
            for a in soup.find_all("a", class_="torrent_txt_link"):
                if a.get("href"):
                    links.append(f"{BASE_URL}/{a['href']}")
        
        return links
    
    def parse_detail_page(self, url: str) -> Optional[Dict]:
        """Torrent adatlap feldolgozása."""
        resp = self.ncore.get(url)
        if not resp:
            return None
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # nCore ID kinyerése
        ncore_id = url.split("id=")[-1].split("&")[0]
        
        # Szerző és cím a torrent_reszletek_cim div-ből (ez MINDIG megbízható)
        cim_div = soup.find("div", class_="torrent_reszletek_cim")
        if not cim_div:
            return None
        
        cim_raw = cim_div.get_text(strip=True)
        if " - " in cim_raw:
            # Az UTOLSÓ " - " a választóvonal
            parts = cim_raw.rsplit(" - ", 1)
            szerzo = parts[0]
            cim = parts[1]
        else:
            szerzo = "Ismeretlen"
            cim = cim_raw
        
        # Leírás div (proba42 class)
        leiras_div = soup.find("div", class_="proba42")
        leiras_raw = ""
        if leiras_div:
            leiras_raw = leiras_div.get_text(separator="\n", strip=True)
        
        # Normalizáljuk a leírást (span + : összevonás)
        leiras_normalized = self._normalize_description_text(leiras_raw)
        
        # Sorozat kinyerése a "Könyv címe:" sorból (ott van a zárójelezett rész)
        sorozat, sorozat_szama = self._extract_series_from_description(leiras_normalized)
        
        # Feltöltve és méret
        feltoltve = "Ismeretlen"
        meret = "N/A"
        
        for dt in soup.find_all("div", class_="dt"):
            txt = dt.get_text(strip=True)
            dd = dt.find_next_sibling("div", class_="dd")
            if dd:
                if "Feltöltve:" in txt:
                    feltoltve = dd.get_text(strip=True)
                elif "Méret:" in txt:
                    meret = dd.get_text(strip=True).split('(')[0].strip()
        
        # Címkék
        cimkek = self._extract_tags(soup)
        
        # Metaadatok a leírásból
        meta = self._extract_metadata(leiras_normalized)
        
        # Tisztított leírás és moly.hu link
        leiras_clean, buy_link = self._clean_description(leiras_normalized)
        
        # Borítókép
        kep_utvonal = self._download_cover(soup, ncore_id)
        
        return {
            "ncore_id": ncore_id,
            "szerzo": szerzo.strip() if szerzo else "Ismeretlen",
            "cim": cim.strip() if cim else "Ismeretlen",
            "kep_utvonal": kep_utvonal,
            "meret": meret,
            "feltoltve_datum": feltoltve,
            "cimkek": cimkek,
            "leiras": leiras_clean,
            "buy_link": buy_link,
            "teljes_link": url,
            "formatum": meta.get("formatum", "N/A"),
            "kiado": meta.get("kiado", "N/A"),
            "kiadas_eve": meta.get("kiadas_eve", "N/A"),
            "isbn": meta.get("isbn", "N/A"),
            "sorozat": sorozat,
            "sorozat_szama": sorozat_szama,
        }
    
    def _extract_series_from_description(self, text: str) -> tuple:
        """Sorozat és sorszám kinyerése a 'Könyv címe:' sorból.
        
        A "Könyv címe:" sorban van a teljes cím zárójelezett sorozat infóval:
        "Könyv címe: Szerző - Cím (Sorozat X.)"
        
        Returns:
            (sorozat, sorozat_szama)
        """
        # Keressük a "Könyv címe:" sort
        match = re.search(r"Könyv\s*c[ií]me?\s*:\s*(.+?)(?:\n|$)", text, re.IGNORECASE)
        if not match:
            return "N/A", "N/A"
        
        konyv_cime_sor = match.group(1).strip()
        
        # Sorozat kinyerése: (Sorozat X.) a sor végén
        # Minta: szám + opcionális pont a zárójel végén
        series_match = re.search(r'\((.+?)\s+(\d+)\.?\s*\)$', konyv_cime_sor)
        if series_match:
            sorozat = series_match.group(1).strip()
            sorszam = series_match.group(2).strip()
            return sorozat, sorszam
        
        return "N/A", "N/A"
    
    def _extract_series(self, text: str) -> tuple:
        """Sorozat és sorszám kinyerése a címből."""
        # Minta: "Cím (Sorozat neve 3.)" vagy "Cím (Sorozat neve 3)" vagy "Cím (Alcím)"
        
        # Először próbáljuk számmal a végén: (Sorozat neve 123.) vagy (Sorozat neve 123)
        match = re.search(r'\((.+?)\s+(\d+)\.?\s*\)$', text.strip())
        if match:
            cim = re.sub(r'\s*\(.+?\s+\d+\.?\s*\)$', '', text).strip()
            sorozat = match.group(1).strip()
            sorszam = match.group(2).strip()
            return cim, sorozat, sorszam
        
        # Ha nincs szám, akkor lehet alcím - azt is kinyerjük sorozatként
        match = re.search(r'\(([^)]+)\)$', text.strip())
        if match:
            cim = re.sub(r'\s*\([^)]+\)$', '', text).strip()
            zarojeles = match.group(1).strip()
            return cim, zarojeles, "N/A"
        
        return text.strip(), "N/A", "N/A"
    
    def _extract_tags(self, soup: BeautifulSoup) -> str:
        """Címkék kinyerése."""
        # Próbálkozás onclick alapján
        cimkek = ", ".join([a.text for a in soup.find_all("a", onclick="címkék")])
        
        if not cimkek:
            # Alternatív módszer: Címkék: sor keresése
            cimke_label = soup.find(string=re.compile("Címkék:"))
            if cimke_label:
                parent = cimke_label.find_parent("tr")
                if parent:
                    cimkek = ", ".join([
                        a.text for a in parent.find_all("a") 
                        if "Címkék" not in a.text
                    ])
        
        return cimkek
    
    def _extract_description(self, soup: BeautifulSoup) -> str:
        """Leírás kinyerése."""
        # Keressük a proba42 class-t, ez a tényleges leírás div
        desc_div = soup.find("div", class_="proba42")
        if desc_div:
            text = desc_div.get_text(separator="\n", strip=True)
            text = self._clean_description_header(text)
            return text
        
        # Fallback: régi módszer
        for div in soup.find_all("div", class_="torrent_leiras"):
            text = div.get_text(separator="\n", strip=True)
            # Kiszűrjük a "seederek" típusú blokkokat és a borítós részt
            if "Akik eddig" not in text and "Címkék:" not in text:
                text = self._clean_description_header(text)
                return text
        return ""
    
    def _clean_description_header(self, text: str) -> str:
        """Metaadat fejléc eltávolítása a leírásból.
        
        Az nCore HTML-jében a <span>Label</span>: érték formátum
        get_text("\n") után így néz ki:
          Label
          : érték
        
        Ezért először összevonjuk ezeket a sorokat.
        """
        lines = text.split("\n")
        
        # Lépés 1: Összevonjuk a "Label\n: érték" mintákat
        merged_lines = []
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Ha a következő sor kettősponttal kezdődik, összevonjuk
            if i + 1 < len(lines) and lines[i + 1].strip().startswith(":"):
                merged_line = line + lines[i + 1].strip()
                merged_lines.append(merged_line)
                i += 2
            else:
                merged_lines.append(line)
                i += 1
        
        # Lépés 2: Fejléc sorok kiszűrése
        clean_lines = []
        header_patterns = [
            r"^Könyv\s*(c|C)ím[ea]?\s*:",
            r"^Eredeti\s*(c|C)ím\s*:",
            r"^Szerző\s*:",
            r"^Író\s*:",
            r"^Formátum\s*:",
            r"^Kiadó\s*:",
            r"^Kiadás\s*:",
            r"^Kiadás\s*éve\s*:",
            r"^Kiadás\s*dátuma\s*:",
            r"^Megjelenés\s*:",
            r"^ISBN\s*:",
            r"^Oldalszám\s*:",
            r"^Méret\s*:",
            r"^Nyelv\s*:",
            r"^Sorozat\s*:",
            r"^Cím\s*:",
            r"^Év\s*:",
            r"^Kérés\s*azonosító\s*:",
        ]
        
        for line in merged_lines:
            line_stripped = line.strip()
            
            # Üres sorok kihagyása az elején
            if not line_stripped and not clean_lines:
                continue
            
            # Fejléc sor ellenőrzése
            is_header = False
            for pattern in header_patterns:
                if re.match(pattern, line_stripped, re.IGNORECASE):
                    is_header = True
                    break
            
            # Ha nem fejléc, hozzáadjuk
            if not is_header:
                clean_lines.append(line_stripped)
        
        # Lépés 3: URL-ek kiszűrése a végéről (gyakran moly.hu linkek)
        while clean_lines and re.match(r'^https?://', clean_lines[-1]):
            clean_lines.pop()
        
        # Lépés 4: Üres sorok eltávolítása a végéről
        while clean_lines and not clean_lines[-1]:
            clean_lines.pop()
        
        return "\n".join(clean_lines)
    
    def _normalize_description_text(self, text: str) -> str:
        """Normalizálja a leírás szöveget, összeolvasztva a Label és : érték sorokat."""
        lines = text.split("\n")
        merged_lines = []
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if i + 1 < len(lines) and lines[i + 1].strip().startswith(":"):
                merged_line = line + lines[i + 1].strip()
                merged_lines.append(merged_line)
                i += 2
            else:
                merged_lines.append(line)
                i += 1
        return "\n".join(merged_lines)
    
    def _extract_metadata(self, text: str) -> Dict[str, str]:
        """Metaadatok kinyerése a leírásból."""
        # Előbb normalizáljuk a szöveget (Label és : összevonás)
        text = self._normalize_description_text(text)
        
        meta = {
            "formatum": "N/A",
            "kiado": "N/A",
            "kiadas_eve": "N/A",
            "isbn": "N/A",
        }
        
        def find_value(pattern: str) -> str:
            match = re.search(pattern, text, re.IGNORECASE)
            return match.group(1).strip() if match else "N/A"
        
        # Formátum
        fmt = find_value(r"Formátum\s*:\s*(.+)")
        if fmt != "N/A":
            fmt_lower = fmt.lower()
            if "pdf" in fmt_lower:
                meta["formatum"] = "pdf"
            elif "epub" in fmt_lower:
                meta["formatum"] = "epub"
            elif "mobi" in fmt_lower:
                meta["formatum"] = "mobi"
            elif "azw" in fmt_lower:
                meta["formatum"] = "azw3"
            else:
                meta["formatum"] = fmt_lower.split()[0]
        
        # Kiadó
        meta["kiado"] = find_value(r"Kiadó\s*:\s*(.+)")
        
        # Kiadás éve - többféle minta
        eve = find_value(r"Kiadás éve\s*:\s*(\d{4})")
        if eve == "N/A":
            eve = find_value(r"Kiadás dátuma\s*:\s*(\d{4})")
        if eve == "N/A":
            eve = find_value(r"Kiadás\s*:\s*(\d{4})")
        meta["kiadas_eve"] = eve
        
        # ISBN - intelligens keresés (nincs mindig címke, random helyen lehet)
        meta["isbn"] = self._extract_isbn(text)
        
        return meta
    
    def _extract_isbn(self, text: str) -> str:
        """ISBN kinyerése a szövegből - formátum alapján, nem címke alapján.
        
        Az ISBN nincs mindig jelölve, ezért a formátum alapján keressük:
        - ISBN-13: 978 vagy 979 kezdetű 13 számjegy
        - ISBN-10: 10 számjegy (régebbi könyveknél)
        """
        # 1. Először próbáljuk "ISBN" címkével
        isbn_with_label = re.search(r'ISBN[-:\s]*([0-9-]{10,17})', text, re.IGNORECASE)
        if isbn_with_label:
            isbn = isbn_with_label.group(1).replace("-", "").replace(" ", "")
            if len(isbn) in [10, 13]:
                return isbn
        
        # 2. ISBN-13: 978/979 kezdetű, kötőjelekkel vagy szóközökkel
        isbn13_match = re.search(r'\b(97[89][-\s]?[0-9]{1,5}[-\s]?[0-9]{1,7}[-\s]?[0-9]{1,6}[-\s]?[0-9])\b', text)
        if isbn13_match:
            isbn = isbn13_match.group(1).replace("-", "").replace(" ", "")
            if len(isbn) == 13:
                return isbn
        
        # 3. ISBN-13: egyszerű 13 számjegy 978/979-cel
        isbn13_simple = re.search(r'\b(97[89][0-9]{10})\b', text)
        if isbn13_simple:
            return isbn13_simple.group(1)
        
        # 4. ISBN-10: 10 számjegy (utolsó lehet X)
        isbn10_match = re.search(r'\b([0-9]{9}[0-9Xx])\b', text)
        if isbn10_match:
            return isbn10_match.group(1).upper()
        
        return "N/A"
    
    def _clean_description(self, text: str) -> tuple:
        """Leírás tisztítása: fejléc eltávolítás és vásárlási link kinyerése.
        
        A leírás elején lévő metaadat sorok (Könyv címe, Kiadás dátuma, Formátum, stb.)
        eltávolítása, és a moly.hu link kinyerése.
        """
        buy_link = "Nincs"
        
        # 1. Vásárlási link kinyerése
        links = re.findall(r'https?://\S+', text)
        for link in links:
            # Dereferer linken keresztüli moly.hu link
            if "dereferer.me" in link and "moly.hu" in link:
                moly_match = re.search(r'https?://moly\.hu/\S+', link)
                if moly_match:
                    buy_link = moly_match.group(0)
                else:
                    buy_link = link
                text = text.replace(link, "")
                break
            # Közvetlen moly.hu vagy más könyves site
            elif any(site in link for site in ["moly.hu", "libri.hu", "bookline", "lira"]):
                buy_link = link
                text = text.replace(link, "")
                break
        
        # 2. Minden maradék URL eltávolítása
        text = re.sub(r'https?://\S+', '', text)
        
        # 3. Fejléc sorok eltávolítása (Könyv címe, Formátum, stb.)
        lines = text.split("\n")
        clean_lines = []
        
        header_patterns = [
            r"^Könyv\s*c[ií]me?\s*:",
            r"^Eredeti\s*c[ií]m\s*:",
            r"^Szerző\s*:",
            r"^Író\s*:",
            r"^Formátum\s*:",
            r"^Kiadó\s*:",
            r"^Kiadás\s*:",
            r"^Kiadás\s*éve\s*:",
            r"^Kiadás\s*dátuma\s*:",
            r"^Megjelenés\s*:",
            r"^ISBN\s*:",
            r"^Oldalszám\s*:",
            r"^Méret\s*:",
            r"^Nyelv\s*:",
            r"^Sorozat\s*:",
            r"^Cím\s*:",
            r"^Év\s*:",
            r"^Kérés\s*azonosító\s*:",
        ]
        
        for line in lines:
            line_stripped = line.strip()
            
            # Üres sorok kihagyása az elején
            if not line_stripped and not clean_lines:
                continue
            
            # Fejléc sor ellenőrzése
            is_header = False
            for pattern in header_patterns:
                if re.match(pattern, line_stripped, re.IGNORECASE):
                    is_header = True
                    break
            
            if not is_header:
                clean_lines.append(line_stripped)
        
        # 4. Üres sorok eltávolítása a végéről
        while clean_lines and not clean_lines[-1]:
            clean_lines.pop()
        
        return "\n".join(clean_lines), buy_link
    
    def _download_cover(self, soup: BeautifulSoup, ncore_id: str) -> Optional[str]:
        """Borítókép letöltése."""
        img_td = soup.find("td", class_="inforbar_img")
        if not img_td:
            return None
        
        img = img_td.find("img")
        if not img or not img.get("src"):
            return None
        
        img_url = img["src"]
        
        # Alapértelmezett képek kiszűrése
        if "beer" in img_url:
            return None
        
        filepath = os.path.join(self.covers_path, f"{ncore_id}.jpg")
        
        # Ha már létezik, nem töltjük le újra
        if os.path.exists(filepath):
            return filepath
        
        try:
            req = urllib.request.Request(img_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as response:
                with open(filepath, "wb") as f:
                    f.write(response.read())
            return filepath
        except Exception:
            return None
    
    def scrape_update(self, progress_callback: Optional[Callable[[int, int], None]] = None) -> int:
        """Új könyvek scrape-elése (az utolsó ismertig)."""
        if not self.connect():
            return 0
        
        last_date = get_latest_date()
        self.log(f"📅 Utolsó ismert dátum: {last_date or 'nincs'}")
        
        total_saved = 0
        page = 1
        
        while not self.stop_requested:
            try:
                self.log(f"📄 {page}. oldal feldolgozása...")
                
                links = self.get_page_torrents(page)
                if not links:
                    self.log("🏁 Nincs több oldal.")
                    break
                
                for i, link in enumerate(links):
                    if self.stop_requested:
                        break
                    
                    if progress_callback:
                        progress_callback(i + 1, len(links))
                    
                    try:
                        book = self.parse_detail_page(link)
                        if not book:
                            continue
                        
                        # Update módban megállunk, ha régi könyvhöz értünk
                        if last_date and book["feltoltve_datum"] <= last_date:
                            self.log(f"🛑 Elértük az ismert dátumot ({book['feltoltve_datum']})")
                            return total_saved
                        
                        if save_book(book):
                            total_saved += 1
                            self.log(f"  ✅ {book['szerzo']} - {book['cim']}")
                    except Exception as e:
                        self.log(f"  ❌ Hiba a könyv feldolgozásánál: {e}")
                        continue
                    
                    time.sleep(self.delay)
                
                page += 1
                time.sleep(self.delay * 2)
                
            except Exception as e:
                self.log(f"❌ Oldal feldolgozási hiba: {e}")
                break
        
        return total_saved
    
    def scrape_history(
        self, 
        start_page: int = 1,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> int:
        """Régi könyvek scrape-elése adott oldaltól."""
        if not self.connect():
            return 0
        
        total_saved = 0
        page = start_page
        
        while not self.stop_requested:
            self.log(f"📄 {page}. oldal feldolgozása...")
            config_set("last_history_page", page)
            
            links = self.get_page_torrents(page)
            if not links:
                self.log("🏁 Nincs több oldal.")
                break
            
            for i, link in enumerate(links):
                if self.stop_requested:
                    break
                
                if progress_callback:
                    progress_callback(i + 1, len(links))
                
                # Kihagyjuk, ha már létezik
                ncore_id = link.split("id=")[-1].split("&")[0]
                if book_exists(ncore_id):
                    continue
                
                book = self.parse_detail_page(link)
                if not book:
                    continue
                
                if save_book(book):
                    total_saved += 1
                    self.log(f"  ✅ {book['szerzo']} - {book['cim']}")
                
                time.sleep(self.delay)
            
            page += 1
            time.sleep(self.delay * 2)
        
        return total_saved
    
    def scrape_full(
        self, 
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        max_pages: int = 3000
    ) -> int:
        """Teljes scrape: először újak, aztán régiek.
        
        1. Fázis: Új könyvek (1. oldaltól amíg el nem érjük az ismertet)
        2. Fázis: Régi könyvek (adatbázis méret alapján számított oldaltól)
        
        Args:
            progress_callback: (fázis, aktuális, összes) callback
            max_pages: Maximum oldalak száma a history fázisban
        
        Returns:
            Mentett könyvek száma
        """
        if not self.connect():
            return 0
        
        total_saved = 0
        
        # === 1. FÁZIS: ÚJ KÖNYVEK ===
        self.log("=" * 50)
        self.log("📥 1. FÁZIS: Új könyvek keresése...")
        self.log("=" * 50)
        
        last_date = get_latest_date()
        self.log(f"📅 Utolsó ismert dátum: {last_date or 'nincs'}")
        
        page = 1
        new_count = 0
        
        while not self.stop_requested:
            self.log(f"📄 [ÚJ] {page}. oldal...")
            
            links = self.get_page_torrents(page)
            if not links:
                break
            
            found_old = False
            for i, link in enumerate(links):
                if self.stop_requested:
                    break
                
                if progress_callback:
                    progress_callback("új", i + 1, len(links))
                
                book = self.parse_detail_page(link)
                if not book:
                    continue
                
                # Megállunk, ha régi könyvhöz értünk
                if last_date and book["feltoltve_datum"] <= last_date:
                    self.log(f"🛑 Elértük az ismert dátumot ({book['feltoltve_datum']})")
                    found_old = True
                    break
                
                if save_book(book):
                    new_count += 1
                    total_saved += 1
                    self.log(f"  ✅ {book['szerzo']} - {book['cim']}")
                
                time.sleep(self.delay)
            
            if found_old:
                break
            
            page += 1
            time.sleep(self.delay * 2)
        
        self.log(f"\n📊 1. fázis kész: {new_count} új könyv")
        
        if self.stop_requested:
            return total_saved
        
        # === 2. FÁZIS: RÉGI KÖNYVEK ===
        self.log("\n" + "=" * 50)
        self.log("📜 2. FÁZIS: Régi könyvek keresése...")
        self.log("=" * 50)
        
        # Számoljuk ki melyik oldalon kezdjük
        db_count = db_count_books()
        
        if db_count == 0:
            self.log("ℹ️ Nincs még könyv az adatbázisban.")
            return total_saved
        
        # Oldal számítás: könyvek száma / 25 - 3 (biztonsági margó)
        start_page = max(1, (db_count // 25) - 3)
        self.log(f"📊 Adatbázisban: {db_count} könyv")
        self.log(f"📍 Számított kezdő oldal: {start_page} (= {db_count} / 25 - 3)")
        
        old_count = 0
        page = start_page
        empty_pages = 0
        
        while not self.stop_requested and page < start_page + max_pages:
            self.log(f"📄 [RÉGI] {page}. oldal...")
            config_set("last_history_page", page)
            
            if progress_callback:
                progress_callback("régi", page - start_page + 1, max_pages)
            
            links = self.get_page_torrents(page)
            if not links:
                empty_pages += 1
                if empty_pages >= 3:
                    self.log("🏁 Nincs több oldal (3 üres oldal).")
                    break
                page += 1
                continue
            
            empty_pages = 0
            page_new = 0
            
            for i, link in enumerate(links):
                if self.stop_requested:
                    break
                
                # Kihagyjuk, ha már létezik
                ncore_id = link.split("id=")[-1].split("&")[0]
                if book_exists(ncore_id):
                    continue
                
                book = self.parse_detail_page(link)
                if not book:
                    continue
                
                if save_book(book):
                    old_count += 1
                    page_new += 1
                    total_saved += 1
                    self.log(f"  ✅ {book['szerzo']} - {book['cim']}")
                
                time.sleep(self.delay)
            
            if page_new > 0:
                self.log(f"  📊 Oldal összesen: {page_new} új")
            
            page += 1
            time.sleep(self.delay * 2)
        
        self.log(f"\n📊 2. fázis kész: {old_count} régi könyv")
        self.log(f"\n🎉 ÖSSZESEN: {total_saved} könyv mentve")
        
        return total_saved

    def scrape_older(
        self,
        max_pages: int = 3000,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> int:
        """Régebbi könyvek keresése az adatbázis legkorábbi dátumánál korábbiak.
        
        A torrent oldal listázása dátum szerint csökkenő (1. oldal = legújabb).
        Kiszámítjuk, hogy a DB-ben lévő könyvszám alapján hányadik oldalon
        járhatunk, és onnan indulva előre (magasabb oldalszám = régebbi torrentek)
        keresünk még ismeretlen könyveket.
        
        Ha 5 egymást követő oldalon nem talál új könyvet, megáll.
        
        Returns:
            -1: ha üres az adatbázis (nincs honnan indulni)
             0: ha nincs mit letölteni (legrégebbi is megvan)
            >0: mentett könyvek száma
        """
        # Ellenőrzés: van-e egyáltalán adat az adatbázisban?
        total_in_db = db_count_books()
        if total_in_db == 0:
            self.log("⚠️ Az adatbázis üres! Használd először az 'Új könyvek' gombot.")
            return -1
        
        oldest_date = get_oldest_date()
        self.log(f"📅 Legrégebbi ismert feltöltés: {oldest_date}")
        
        if not self.connect():
            return 0
        
        # Számított kezdő oldal: kb. ott leszünk, ahol a régi könyvek véget érnek
        start_page = max(1, (total_in_db // 25) - 3)
        self.log(f"📊 Adatbázisban: {total_in_db} könyv")
        self.log(f"📍 Keresés kezdése: {start_page}. oldaltól")
        
        total_saved = 0
        page = start_page
        consecutive_empty = 0  # Egymást követő üres oldalak számlálója
        
        while not self.stop_requested and page < start_page + max_pages:
            self.log(f"📄 [RÉGI] {page}. oldal...")
            config_set("last_history_page", page)
            
            if progress_callback:
                progress_callback(page - start_page + 1, max_pages)
            
            links = self.get_page_torrents(page)
            if not links:
                consecutive_empty += 1
                if consecutive_empty >= 3:
                    self.log("🏁 Nincs több oldal (3 üres oldal egymás után).")
                    break
                page += 1
                continue
            
            page_new = 0
            for link in links:
                if self.stop_requested:
                    break
                
                ncore_id = link.split("id=")[-1].split("&")[0]
                if book_exists(ncore_id):
                    continue
                
                book = self.parse_detail_page(link)
                if not book:
                    continue
                
                if save_book(book):
                    total_saved += 1
                    page_new += 1
                    self.log(f"  ✅ {book['szerzo']} - {book['cim']}")
                
                time.sleep(self.delay)
            
            if page_new > 0:
                self.log(f"  📊 Oldalon {page_new} új könyv")
                consecutive_empty = 0
            else:
                consecutive_empty += 1
            
            # Ha 5 egymást követő oldalon nem volt új könyv, megállunk
            if consecutive_empty >= 5:
                self.log("🏁 5 egymást követő oldalon nem volt új könyv.")
                break
            
            page += 1
            time.sleep(self.delay * 2)
        
        if total_saved > 0:
            self.log(f"\n🎉 Összesen {total_saved} régi könyv mentve.")
        else:
            self.log("\n✅ Nincs mit letölteni – a legkorábbi torrent adatai is szerepelnek az adatbázisban.")
        
        return total_saved
