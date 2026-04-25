# KönyvtárAI 📚

Személyes könyvtárkezelő és AI asszisztens — nagy e-könyv gyűjteményekhez.

## Mit tud?

- **66 000+ könyv** metaadatait kezeli SQLite adatbázisban
- Összepárosítja a fizikai könyvfájlokat az adatbázis-bejegyzésekkel
- Gazdagítja az adatokat a [moly.hu](https://moly.hu) könyvközösségi oldalról
- Szép, gyors PyQt6-alapú felület borítóképekkel, szűrőkkel, lapozással
- AI összefoglaló és vélemény helyi Ollama modellekkel
- Könyvek másolása telefonra (USB meghajtóként csatlakoztatva)

## Felépítés

```
fazis1_meta_elemzo.py      # 1. lépés: adatbázis feltérképezése → meta.json
fazis1_fajlfelismero.py    # 2. lépés: fizikai fájlok azonosítása
fazis2_moly_scraper.py     # 3. lépés: moly.hu adatgyűjtés
konyvtar_gui.py            # Főprogram — PyQt6 GUI
minta_nezegeto.py          # Diagnosztikai segédeszköz
```

## Telepítés

```bash
pip install PyQt6 requests beautifulsoup4 rapidfuzz tqdm
```

## Beállítás

1. Másold le az `env.minta` fájlt `.env` névvel
2. Töltsd ki a moly.hu bejelentkezési adatokat
3. Az adatbázis elérési útját állítsd be a szkriptekben (`DB_PATH`)

## Futtatás

```bash
# Első indítás sorrendben:
python fazis1_meta_elemzo.py       # ~1 perc
python fazis1_fajlfelismero.py     # ~10 perc (100k fájlnál)
python fazis2_moly_scraper.py      # ~néhány óra (folytatható)

# Főprogram
python konyvtar_gui.py
```

## Fájlnév-minták amelyeket felismer

| Típus | Példa |
|-------|-------|
| Alap | `Szerző Neve - Könyv Címe.epub` |
| Torrent | `Szerzo.Neve.Konyv.Cime.HUN.EPUB.eBook.epub` |
| Z-Library | `Könyv Címe (Szerző Neve) (z-lib.org).epub` |
| Kisbetűs | `szerzo_neve_konyv_cime.epub` |

## Egyezési szintek

| Szín | Szint | Jelentés |
|------|-------|----------|
| 🟢 Zöld | pontos | Szerző + cím azonosítva, magas pontszámmal |
| 🟢 Sötétzöld | fuzzy | Közelítő szövegegyezéssel azonosítva |
| 🔵 Kék | moly_fuzzy | Moly.hu alapján azonosítva |
| 🟡 Narancs | szerzo_ismert | Csak a szerző azonosítva |
| 🔴 Piros | ismeretlen | Nem azonosítható |
| ⚫ Szürke | — | Nincs letöltött fájl |

## Technológiák

- **Python 3.11+**
- **PyQt6** — grafikus felület
- **SQLite** — adatbázis (WAL módban)
- **rapidfuzz** — fuzzy szövegegyezés
- **BeautifulSoup4** — web scraping
- **Ollama** — helyi AI modellek (opcionális)

## Megjegyzés

Az adatbázis és a borítóképek (`boritos_cache/`) nem részei a repónak — ezek méretük miatt ki vannak zárva. Az adatbázis-sémát és a feltérképező szkripteket tartalmazza a repó.
