# KönyvtárAI — Használati útmutató

## Rendszerkövetelmények

- Python 3.11 vagy újabb
- Windows 10/11 (a telefon fájlkezelő funkció Windows-specifikus)
- Legalább 4 GB RAM (az adatbázis memóriába töltődik)
- Ollama (opcionális, az AI funkciókhoz)

---

## Telepítés

### 1. Python csomagok

```bash
pip install PyQt6 requests beautifulsoup4 rapidfuzz tqdm
```

### 2. Bejelentkezési adatok beállítása

Másold le az `env.minta` fájlt `.env` névvel, és töltsd ki:

```
MOLY_USER=ide_az_email_cimedm
MOLY_PASS=ide_a_jelszod
```

### 3. Adatbázis elérési útja

Minden szkriptben a `DB_PATH` változó mutatja az adatbázis helyét. Állítsd be a saját útvonalad szerint:

```python
DB_PATH = r"C:\sajat\mappa\ncore_konyvtar.db"
```

---

## Az alkalmazás felépítése és futtatási sorrend

### 1. lépés — Meta-elemzés (egyszer kell futtatni)

```bash
python fazis1_meta_elemzo.py
```

**Mit csinál:** Végigolvassa az adatbázist és összesítőt készít: könyvszám, szerzők, cimkék, kiadók, évek, adatgazdagság. Eredménye a `meta.json` fájl, amelyet a főprogram minden indításkor beolvas.

**Futási idő:** 1-2 perc

---

### 2. lépés — Fájlfelismerő (egyszer kell futtatni, de folytatható)

```bash
python fazis1_fajlfelismero.py
```

**Mit csinál:** Végigmegy a megadott könyvmappán, és minden fizikai fájlt megpróbál párosítani az adatbázis egy bejegyzésével. Négy fájlnév-mintát ismer fel:

| Minta | Példa |
|-------|-------|
| Alap | `Rejtő Jenő - Piszkos Fred a kapitány.epub` |
| Torrent | `Rejto.Jeno.Piszkos.Fred.HUN.EPUB.epub` |
| Z-Library | `Piszkos Fred (Rejtő Jenő) (z-lib.org).epub` |
| Kisbetűs | `rejto_jeno_piszkos_fred.epub` |

Az eredményt a `fizikai_fajlok` táblában tárolja az adatbázisban.

**Futási idő:** 5-15 perc (100 000 fájlnál)
**Fontos:** ha megszakítják, folytatható — a már feldolgozott fájlokat kihagyja.

---

### 3. lépés — Moly.hu adatgyűjtés (opcionális, folytatható)

```bash
python fazis2_moly_scraper.py
```

**Mit csinál:** A moly.hu könyvközösségi oldalról letölti az adatbázisban szereplő szerzők könyveinek listáját — értékelésekkel, sorozatinformációkkal együtt. Bejelentkezést igényel (lásd `.env` fájl).

**Futási idő:** több óra (szerzőnként 1-3 kérés, 1-3 másodperc szünettel)
**Fontos:** folytatható — a már lekért szerzőket kihagyja.

---

### 4. lépés — Főprogram indítása

```bash
python konyvtar_gui.py
```

---

## A főprogram kezelése

### Bal oldalsáv — Szűrők

- **Keresőmező:** cím vagy szerző szerint szűr, gépelés közben azonnal
- **Státusz gombok:**
  - *Mind* — az összes könyv
  - *Van fájl* — csak amelyekhez van letöltött fájl
  - *Csak adat* — az adatbázisban van, de nincs letöltve
  - *Csak fájl* — van fájl, de hiányos az adata
- **Formátum:** EPUB, PDF, MOBI, AZW3, FB2 szűrők
- **Cimkék:** top 30 cimke kattintásra szűr
- **Szerzők:** top 50 szerző kattintásra szűr
- **Szűrők törlése:** visszaállítja az alapállapotot

### Jelmagyarázat (bal oldali színes sáv a kártyákon)

| Szín | Jelentés |
|------|----------|
| 🟢 Zöld | Pontos egyezés — szerző és cím is azonosítva |
| 🟢 Sötétzöld | Fuzzy egyezés — közelítő szövegegyezéssel azonosítva |
| 🔵 Kék | Moly.hu alapján azonosítva |
| 🟡 Narancs | Csak a szerző azonosítva |
| 🔴 Piros | Nem azonosítható fájl |
| ⚫ Szürke | Nincs letöltött fájl |

---

### Középső rész — Könyvrács

- **Kattintás** egy kártyára → megjelenik a könyv részletlapja jobbra
- **Jelölőnégyzet** (kártya jobb felső sarka) → kijelöli másoláshoz
- **☑ Mind** → az oldal összes könyvét kijelöli
- **☐ Töröl** → kijelölés megszüntetése
- **Lapozó** (alul) → oldalanként 48 könyv, előző/következő gombokkal

---

### Jobb oldal — Könyv részletei

Kattintás után megjelenik:
- Borítókép (automatikusan letöltődik, cache-elődik)
- Cím, szerző, kiadó, kiadási év, sorozat, ISBN
- Cimkék
- Moly.hu értékelés (ha elérhető)
- Fájl státusz és formátum
- Leírás szövegdoboz

---

### Jobb oldal — AI Asszisztens

Ehhez az **Ollama** helyi AI szerver szükséges (`ollama serve`).

- **📋 Összefoglaló** → rövid tartalmi összefoglaló a könyvről
- **💬 Vélemény** → kritika és ajánlás
- **📚 Hasonlók** → hasonló könyvek az adatbázisból (cimkék/szerző alapján), vagy AI-generált ajánló
- **Kérdésmező** → bármit kérdezhetsz a könyvről
- **Modellváltó** → automatikusan listázza a telepített Ollama modelleket
- **⏹ Stop** → megszakítja a generálást

Ha az Ollama nem fut, az AI panel tájékoztat — a többi funkció tőle független.

---

### Jobb oldal — Másolás telefonra

1. **Csatlakoztasd a telefont** USB-n, meghajtóként (pl. `E:\`)
2. **Válaszd ki a meghajtót** a legördülőből (↺ frissítés gomb ha nem látszik)
3. **Böngészd a mappastruktúrát** — kattintásra nyílik/csukódik
4. **Mappa műveletek:**
   - `+ Mappa` → új mappa létrehozása a kijelölt mappán belül
   - `✏ Nevez` → kijelölt mappa átnevezése
   - `🗑 Töröl` → kijelölt mappa törlése (megerősítés után)
5. **Jelöld ki a könyveket** a rácson (jelölőnégyzetek)
6. **Kattints a másolás gombra** → folyamatjelző mutatja az előrehaladást

**Megjegyzés:** csak azok a könyvek másolhatók, amelyekhez van fizikai fájl (zöld/narancs státusz).

---

## Diagnosztikai eszköz

```bash
python minta_nezegeto.py
```

Megmutatja az ismeretlen (nem azonosított) és a pontosan azonosított fájlok mintáit — hasznos ha ellenőrizni szeretnéd a fájlfelismerő eredményét.

---

## Hibaelhárítás

**„Nem találom az adatbázist"** → Ellenőrizd a `DB_PATH` értékét a szkriptekben.

**„PyQt6 nem található"** → `pip install PyQt6`

**AI panel nem válaszol** → Ellenőrizd fut-e az Ollama: `ollama serve`

**Moly.hu bejelentkezés sikertelen** → Ellenőrizd a `.env` fájlban az adatokat. Ha az email helyett felhasználónévvel kell bejelentkezni, azt írd be a `MOLY_USER` mezőbe.

**Lassú keresés** → Normális az első indításnál amíg az adatbázis cache épül. Utána gyorsabb.
