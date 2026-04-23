# 📚 KönyvAI V4

**Helyi, offline könyvolvasó és kérdező alkalmazás** mesterséges intelligenciával.  
Tölts fel bármilyen könyvet (PDF, EPUB, DOCX, TXT, RTF), és kérdezz tőle magyarul!

---

## ✨ Funkciók

- 📖 **Több formátum támogatása**: PDF, EPUB, DOCX, TXT, RTF
- 🧠 **Helyi AI**: Semmilyen adat nem hagyja el a gépedet – teljesen offline működés
- 📝 **Automatikus összefoglalás**: Rövid, közepes vagy részletes tartalmi kivonat
- ❓ **Interaktív kérdezés**: Tegyél fel konkrét kérdéseket a könyv tartalmával kapcsolatban
- ⚙️ **Testreszabható beállítások**: Modellválasztás, darabméret, kreativitás (temperature)

---

## 🚀 Telepítés

### 1. Ollama telepítése

Töltsd le és telepítsd az Ollamát: [https://ollama.com/download](https://ollama.com/download)

### 2. Szükséges modellek letöltése

```bash
ollama pull llama3.1
ollama pull nomic-embed-text
```

> 💡 **Tipp**: Ha erősebb géped van (pl. 16 GB+ VRAM), próbáld ki a `qwen2.5:14b` vagy `deepseek-r1:14b` modelleket is!

### 3. Python csomagok telepítése

```bash
pip install streamlit PyPDF2 numpy ollama ebooklib python-docx striprtf beautifulsoup4
```

---

## 🖥️ Indítás

```bash
streamlit run konyvai_v4.py
```

Ezután nyisd meg a böngészőben: [http://localhost:8501](http://localhost:8501)

---

## ⚙️ Beállítások magyarázata

| Beállítás | Leírás | Ajánlott érték |
|-----------|--------|----------------|
| **Nyelvi modell** | A válaszokat generáló AI | `llama3.1` (gyors) vagy `qwen2.5:14b` (pontosabb) |
| **Embedding modell** | Szöveg értelmezése/indexelése | `nomic-embed-text` |
| **Darab méret** | Egy szövegdarab hossza | 1000 karakter |
| **Átfedés** | Két darab közös része | 200 karakter |
| **Kreativitás** | 0.0 = pontos, 1.0 = kreatív | 0.3 (könyvekhez ideális) |
| **Hány darabot használjon** | Kontextus mérete válasznál | 5 |

---

## 📂 Támogatott formátumok

| Formátum | Kiterjesztés | Megjegyzés |
|----------|-------------|------------|
| PDF | `.pdf` | Szöveges réteggel rendelkező PDF-ek |
| EPUB | `.epub` | E-könyvek standard formátuma |
| Word | `.docx` | Modern Microsoft Word dokumentumok |
| Szöveg | `.txt` | Egyszerű szövegfájlok |
| RTF | `.rtf` | Rich Text Format |

> ⚠️ A régi `.doc` (Word 97-2003) formátum **nem** támogatott. Mentésd át `.docx`-be!

---

## 🛠️ Hogyan működik?

1. **Beolvasás**: A program kinyeri a szöveget a feltöltött fájlból
2. **Darabolás**: A szöveget ~1000 karakteres darabokra vágja átfedéssel
3. **Embedding**: Minden darabot számsorokká (vektorokká) alakít az AI segítségével
4. **Indexelés**: NumPy koszinusz hasonlósággal keresi a releváns részeket
5. **Válasz/Összefoglalás**: A helyi LLM (pl. Llama 3.1) feldolgozza a kontextust

---

## 💻 Ajánlott rendszerkövetelmények

| Komponens | Minimum | Ajánlott |
|-----------|---------|----------|
| GPU VRAM | 8 GB | 16 GB+ (RTX 4070/5070 Ti vagy jobb) |
| RAM | 16 GB | 32–64 GB |
| Tárhely | 10 GB | 20 GB+ (modelleknek) |
| OS | Windows 10/11 | Windows 11 / Linux |

---

## 📝 Licenc

MIT License – szabadon használható, módosítható és terjeszthető.

---

Készült ❤️-vel helyi AI-val, adatvédelmi aggályok nélkül.
