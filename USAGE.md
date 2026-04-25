# KönyvtárAI — User Guide

## System Requirements

- Python 3.11 or newer
- Windows 10/11 (the phone file manager feature is Windows-specific)
- At least 4 GB RAM (the database is loaded into memory)
- Ollama (optional, for AI features)

---

## Installation

### 1. Python packages

```bash
pip install PyQt6 requests beautifulsoup4 rapidfuzz tqdm
```

### 2. Setting up login credentials

Copy the `env.minta` file as `.env` and fill in your details:

```
MOLY_USER=your_email_here
MOLY_PASS=your_password_here
```

### 3. Database path

Each script has a `DB_PATH` variable pointing to the database location. Set it to match your own path:

```python
DB_PATH = r"C:\your\folder\ncore_konyvtar.db"
```

---

## Application Structure and Execution Order

### Step 1 — Meta Analysis (run once)

```bash
python fazis1_meta_elemzo.py
```

**What it does:** Reads through the database and creates a summary: book count, authors, tags, publishers, years, data completeness. The result is a `meta.json` file that the main application reads on every startup.

**Runtime:** 1–2 minutes

---

### Step 2 — File Scanner (run once, resumable)

```bash
python fazis1_fajlfelismero.py
```

**What it does:** Walks through the specified book folder and attempts to match every physical file to a database entry. Recognizes four filename patterns:

| Pattern | Example |
|---------|---------|
| Standard | `Author Name - Book Title.epub` |
| Torrent | `Author.Name.Book.Title.HUN.EPUB.epub` |
| Z-Library | `Book Title (Author Name) (z-lib.org).epub` |
| Lowercase | `author_name_book_title.epub` |

Results are stored in the `fizikai_fajlok` table in the database.

**Runtime:** 5–15 minutes (for 100,000 files)
**Important:** Resumable — already processed files are skipped if interrupted.

---

### Step 3 — Moly.hu Data Collection (optional, resumable)

```bash
python fazis2_moly_scraper.py
```

**What it does:** Downloads book lists for each author from moly.hu (the largest Hungarian book community site), including ratings and series information. Requires login (see `.env` file).

**Runtime:** Several hours (1–3 requests per author, with 1–3 second delays)
**Important:** Resumable — already fetched authors are skipped.

---

### Step 4 — Launch the Main Application

```bash
python konyvtar_gui.py
```

---

## Using the Main Application

### Left Sidebar — Filters

- **Search box:** filters by title or author, updates instantly while typing
- **Status buttons:**
  - *All* — every book in the database
  - *Has file* — only books with a downloaded file
  - *Data only* — in the database but not downloaded
  - *File only* — has a file but incomplete metadata
- **Format:** EPUB, PDF, MOBI, AZW3, FB2 filters
- **Tags:** top 30 tags, click to filter
- **Authors:** top 50 authors, click to filter
- **Clear filters:** resets to default state

### Legend (colored stripe on the left of each card)

| Color | Meaning |
|-------|---------|
| 🟢 Green | Exact match — author and title both identified |
| 🟢 Dark green | Fuzzy match — identified via approximate text matching |
| 🔵 Blue | Identified via moly.hu data |
| 🟡 Orange | Author identified only |
| 🔴 Red | Unidentifiable file |
| ⚫ Grey | No downloaded file exists |

---

### Center — Book Grid

- **Click** a card → the book's detail panel opens on the right
- **Checkbox** (top-right corner of card) → marks it for copying
- **☑ All** → selects all books on the current page
- **☐ Clear** → deselects all
- **Pagination** (bottom) → 48 books per page, previous/next buttons

---

### Right Panel — Book Details

After clicking a book:
- Cover image (automatically downloaded and cached)
- Title, author, publisher, year, series, ISBN
- Tags
- Moly.hu rating (if available)
- File status and format
- Description text box

---

### Right Panel — AI Assistant

Requires **Ollama** local AI server (`ollama serve`).

- **📋 Summary** → brief content summary of the book
- **💬 Opinion** → critique and recommendation
- **📚 Similar** → similar books from the database (by tags/author), or AI-generated recommendations
- **Question field** → ask anything about the book
- **Model selector** → automatically lists installed Ollama models
- **⏹ Stop** → interrupts generation

If Ollama is not running, the AI panel will inform you — all other features work independently.

---

### Right Panel — Copy to Phone

1. **Connect your phone** via USB as a drive (e.g., `E:\`)
2. **Select the drive** from the dropdown (↺ refresh button if not visible)
3. **Browse the folder structure** — click to expand/collapse
4. **Folder operations:**
   - `+ Folder` → create a new folder inside the selected one
   - `✏ Rename` → rename the selected folder
   - `🗑 Delete` → delete the selected folder (with confirmation)
5. **Select books** in the grid (using checkboxes)
6. **Click the copy button** → a progress bar shows the transfer

**Note:** Only books with a physical file (green/orange status) can be copied.

---

## Diagnostic Tool

```bash
python minta_nezegeto.py
```

Shows sample unknown (unidentified) and exactly matched files — useful for verifying the file scanner's results.

---

## Troubleshooting

**"Database not found"** → Check the `DB_PATH` value in the scripts.

**"PyQt6 not found"** → `pip install PyQt6`

**AI panel not responding** → Check if Ollama is running: `ollama serve`

**Moly.hu login fails** → Check your credentials in the `.env` file. If the site requires a username instead of email, enter the username in `MOLY_USER`.

**Slow search** → Normal on first launch while the database cache is being built. Subsequent searches are faster.
