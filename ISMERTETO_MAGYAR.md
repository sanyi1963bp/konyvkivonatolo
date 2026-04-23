# 📚 KönyvAI V4 – Magyar nyelvű ismertető és használati útmutató

## Mi az a KönyvAI?

A **KönyvAI** egy **helyi, offline működő mesterséges intelligencia alkalmazás**, amellyel könyveket, tanulmányokat, szakmai dokumentumokat tölthetsz fel, és azok tartalmáról kérdezhetsz – mintha egy személyes kutatóasszisztensed lenne. A program **egyetlen adatot sem küld ki a gépedről**, minden feldolgozás a saját számítógépeden, a saját videókártyádon történik.

---

## 🎯 Kinek ajánlott?

- **Diákoknak és hallgatóknak**, akik gyorsan szeretnének összefoglalást kapni egy tankönyvből
- **Kutatóknak**, akik hosszú szakmai anyagokban keresnek konkrét információt
- **Újságíróknak és íróknak**, akik forrásanyagokat dolgoznak fel
- **Bárkinek**, aki szeretne **adatvédelmi aggályok nélkül** használni mesterséges intelligenciát

---

## 🔧 Mire van szükség a használathoz?

### Hardver

| Komponens | Minimum | Ajánlott |
|-----------|---------|----------|
| Videókártya (GPU) | 8 GB VRAM | **16 GB VRAM** (pl. RTX 4070/5070 Ti) |
| Operatív memória (RAM) | 16 GB | **32–64 GB** |
| Szabad tárhely | 10 GB | 20 GB+ |
| Operációs rendszer | Windows 10 | **Windows 11** vagy Linux |

> 💡 **Fontos**: A program GPU-t használ a gyors feldolgozáshoz. GPU nélkül is fut, de nagyon lassan.

### Szoftver

1. **[Ollama](https://ollama.com/download)** – a helyi AI modellek futtató környezete
2. **Python 3.10+** – programozási nyelv
3. **Streamlit és egyéb Python csomagok**

---

## 📥 Telepítés lépésről lépésre

### 1. Ollama telepítése

1. Töltsd le innen: https://ollama.com/download
2. Telepítsd Windowsra (vagy Linuxra/Mac-re)
3. Ellenőrizd egy új terminálban:
   ```bash
   ollama list
   ```
   Ha fut, üres listát vagy korábban letöltött modelleket látsz.

### 2. AI modellek letöltése

A program két modellt használ: egyet a szöveg megértéséhez (embedding), egyet a válaszokhoz (nyelvi modell).

```bash
# Alapcsomag (gyors, kevesebb VRAM)
ollama pull llama3.1
ollama pull nomic-embed-text

# VAGY erősebb csomag (okosabb, több VRAM kell)
ollama pull qwen2.5:14b
ollama pull nomic-embed-text
```

### 3. Python csomagok telepítése

Nyiss egy terminált (Command Prompt vagy PowerShell), és írd be:

```bash
pip install streamlit PyPDF2 numpy ollama ebooklib python-docx striprtf beautifulsoup4
```

### 4. A program letöltése és indítása

1. Töltsd le a `konyvai_v4.py` fájlt
2. Mentsd egy mappába (pl. `D:\KonyvAI`)
3. A terminálban navigálj abba a mappába:
   ```bash
   cd D:\KonyvAI
   ```
4. Indítsd el:
   ```bash
   streamlit run konyvai_v4.py
   ```

A böngésző automatikusan megnyílik a `http://localhost:8501` címen.

---

## 🖥️ A felület elemei

### Felső rész – Fájlfeltöltés

Itt töltheted fel a könyvedet. Támogatott formátumok:

| Formátum | Kiterjesztés | Megjegyzés |
|----------|-------------|------------|
| PDF | `.pdf` | Szöveges réteggel rendelkező fájlok (a képes PDF-eknél nem működik) |
| EPUB | `.epub` | E-könyvek leggyakoribb formátuma |
| Word | `.docx` | Modern Microsoft Word dokumentumok |
| Szöveg | `.txt` | Egyszerű szövegfájl |
| RTF | `.rtf` | Rich Text Format |

> ⚠️ A régi `.doc` (Word 97-2003) **nem** támogatott! Nyisd meg Wordben, és "Mentés másként" → `.docx`.

### Bal oldalsáv – Beállítások

| Beállítás | Mit csinál? | Ajánlott érték |
|-----------|-------------|----------------|
| **Nyelvi modell** | A "agy": ez generálja a válaszokat és az összefoglalót | `llama3.1` (gyors) vagy `qwen2.5:14b` (pontosabb) |
| **Embedding modell** | A "memória": ez értelmezi, miről szól egy-egy szövegrészlet | `nomic-embed-text` |
| **Darab méret** | Egy szövegdarab (chunk) hossza karakterben | **1000** |
| **Átfedés** | Két egymást követő darab közös része | **200** |
| **Kreativitás** | 0.0 = robotikus/pontos, 1.0 = kreatív/kitalálós | **0.3** (könyvekhez ideális) |
| **Hány darabot használjon válaszhoz** | Hány releváns szövegrészt olvasson vissza a modell | **5** |

#### A beállítások részletes magyarázata

**Darab méret (1000 karakter)**
A program a könyvet kisebb darabokra vágja, mert az AI nem tud egyszerre egy egész 500 oldalas könyvet feldolgozni. 1000 karakter kb. 150–200 szó, ami egy bekezdésnyi szöveg. Ha nagyobbra állítod (pl. 1500), több kontextust lát a modell, de lassabb lesz a feldolgozás.

**Átfedés (200 karakter)**
A darabok között van egy átfedés, hogy ne vágódjon félbe egy mondat a határon. 200 karakter azt jelenti, hogy két szomszédos darab 200 karakteren át azonos. Így biztosítjuk, hogy a mondatok értelme megmaradjon.

**Kreativitás / Temperature (0.3)**
Ez szabályozza, mennyire "kreatív" az AI. Könyvekhez, tényekhez **0.2–0.4** az ideális, mert így a modell a szövegből merítkezik, és nem talál ki dolgokat. Ha kreatív írást szeretnél (pl. vers, történet), akkor 0.7–0.9 jobb.

**Hány darabot használjon (5)**
Amikor kérdezel, a program megkeresi a 5 legrelevánsabb szövegdarabot, és csak azokat adja oda az AI-nak. 5 darab ≈ 5000 karakter kontextus. Ha többet adsz neki (pl. 8), pontosabb lehet a válasz, de lassabb.

---

## 📖 Használat

### 1. Könyv feltöltése

1. Kattints a "Browse files" gombra
2. Válaszd ki a könyvedet
3. A program automatikusan:
   - Beolvassa a szöveget
   - Feldarabolja
   - Generálja az embeddingeket (ez percekig is eltarthat nagyobb könyveknél)
4. Ha kész, zöld pipa jelenik meg

### 2. Összefoglalás készítése

Kattints az **"Összefoglalás"** fülre, és válassz:

- **Rövid** – az első ~10 darabot foglalja össze (gyors, 1–2 bekezdés)
- **Közepes** – az első ~25 darabot (4–5 bekezdés)
- **Részletes** – az első ~50 darabot (10+ bekezdés, de lassabb)

> ⏱️ Egy 500 oldalas könyv részletes összefoglalója 5–10 percig is eltarthat!

### 3. Kérdezés a könyvből

Kattints a **"Kérdezz a könyvből"** fülre, és írd be a kérdésedet. Példák:

- "Miről szól a 3. fejezet?"
- "Ki a főszereplő, és mi a célja?"
- "Milyen gazdasági elméleteket említ a szerző?"
- "Hogyan magyarázza a kvantummechanikát?"

A program megkeresi a legrelevánsabb szövegrészeket, és azok alapján válaszol.

---

## 🧠 Hogyan működik a háttérben? (RAG technológia)

A KönyvAI a **RAG** (Retrieval-Augmented Generation) módszert használja:

1. **Beolvasás** → kinyeri a szöveget a fájlból
2. **Darabolás** → kisebb, átfedő részekre bontja
3. **Embedding** → minden darabot egy számsorvá (vektorrá) alakít, ami megőrzi a jelentését
4. **Tárolás** → NumPy tömbökben tárolja a vektorokat
5. **Lekérdezés** → a kérdést is vektorrá alakítja, és koszinusz hasonlósággal megtalálja a legközelebbi szövegdarabokat
6. **Generálás** → a helyi nyelvi modell (pl. Llama 3.1) a kiválasztott kontextus alapján megválaszolja a kérdést

---

## 🛠️ Hibaelhárítás

| Hiba | Ok | Megoldás |
|------|-----|----------|
| "Failed to connect to Ollama" | Az Ollama nem fut | Futtasd: `ollama serve` vagy indítsd el a Start menüből |
| "No module named..." | Hiányzó Python csomag | `pip install [csomagnév]` |
| "Nem sikerült szöveget kinyerni" | Képes PDF (scanned) | Használj OCR-eszközt előtte (pl. Adobe Acrobat) |
| Nagyon lassú | Túl nagy a darab méret | Csökkentsd 800-ra, az átfedést 100-ra |
| Pontatlan válaszok | Túl kicsi a kontextus | Növeld a "Hány darabot" értéket 7-re vagy 10-re |
| A modell "kitalál" dolgokat | Túl magas a temperature | Csökkentsd 0.2-re |

---

## 🔒 Adatvédelem

Mivel **minden helyben fut a gépeden**:
- ✅ A könyved **soha nem hagyja el** a számítógépedet
- ✅ Nincs felhő, nincs külső szerver
- ✅ Nincs adatgyűjtés, nincs tracking
- ✅ Még internetkapcsolat sem szükséges a használathoz (a modellek letöltése után)

---

## 📜 Licenc

MIT License – szabadon használható, módosítható és terjeszthető.

---

*Készült helyi mesterséges intelligenciával, adatvédelmi aggályok nélkül.*
