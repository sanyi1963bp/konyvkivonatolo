# KönyvtárAI — The Story of a Project

## Where It All Began

The starting point was three separate "worlds" that knew nothing about each other.

**Physical books on a hard drive** — a large folder structure with files collected from various sources over the years. EPUB, PDF, MOBI, AZW3, FB2 formats, roughly 100,000 files in total. The filenames followed no consistent pattern — sometimes "Author - Title", sometimes dot-separated torrent style, sometimes Z-Library format, sometimes lowercase with underscores.

**A SQLite database** — assembled from a large Hungarian book catalogue. This database contained **66,876 books**, richly annotated: title, author, publisher, publication year, ISBN, description, tags, series, cover image URL. An enormous amount of valuable metadata — but it had no idea which of these books were actually downloaded and sitting on the hard drive.

**Moly.hu** — the largest Hungarian book community website, full of ratings, recommendations, and series information. A valuable supplementary source, but completely untapped.

The goal: connect these three worlds, and build a unified, intelligent library manager from them.

---

## Step 1 — Mapping the Database

Before doing anything else, we needed to understand what the database contained. We wrote the first script (`fazis1_meta_elemzo.py`), which runs once at startup and produces a complete statistical overview:

- Total books: **66,876**
- Number of unique authors
- Top 50 authors, top 30 tags, top 30 publishers, distribution of publication years
- Format breakdown
- Data completeness per field (what percentage of records have real data)
- List of series

The results are saved to a `meta.json` file that the main application reads on every launch — so it instantly "knows" what the library contains, without scanning the entire database each time.

---

## Step 2 — The File Recognition Engine

This was the most complex and intelligent piece of the project (`fazis1_fajlfelismero.py`). The task: walk through all physical files and try to match each one to a database entry.

**The challenge:** with 66,000 books and their author name variants, checking each file against all of them one by one would take hours for a 100,000-file collection.

**The solution:** load the entire database into memory once, and build two fast lookup indexes:
- Every word of every author name → which authors it belongs to (O(1) dictionary lookup)
- Author → list of their books

With these indexes, identifying a single file takes milliseconds, making it possible to process 100,000 files in 5–12 minutes.

**The four filename patterns** identified after examining real filenames:

| Pattern | Example |
|---------|---------|
| Standard | `Jenő Rejtő - Piszkos Fred the Captain.epub` |
| Torrent | `Rejto.Jeno.Piszkos.Fred.HUN.EPUB.eBook-Group.epub` |
| Z-Library | `Piszkos Fred the Captain (Jenő Rejtő) (z-lib.org).epub` |
| Lowercase | `rejto_jeno_piszkos_fred_the_captain.epub` |

**Match levels** distinguished by the system:
- **exact**: both author and title found with high similarity score
- **fuzzy**: identified via approximate text matching (rapidfuzz library)
- **author_known**: author identified, but the specific book could not be determined
- **unknown**: neither author nor title could be identified

The result is a new table in the database (`fizikai_fajlok`) where every physical file is stored with its path, format, match level, matched author and title, and — where successful — the corresponding book's database ID.

**Results after the first run:**
- Exact + fuzzy matches: ~21%
- Author known only: ~15% (10,276 files)
- Unknown: ~64% — not surprising, because the library is mixed: it contains old digitized materials, magazine pages, technical documents, not just fiction

---

## Step 3 — The Moly.hu Scraper

The "author known only" category holds 10,276 files — we know who wrote them, but not which specific book. For these, we try to gather title information from moly.hu (`fazis2_moly_scraper.py`).

**Why scraping instead of an API?** The moly.hu API is currently not publicly available.

**What the scraper does:**
1. Logs in to moly.hu (CSRF token extraction + POST)
2. Searches for every unique author
3. Extracts from results: book ID, URL, author, title, rating, series
4. Saves everything to the database
5. Logs which authors have already been fetched — making it resumable if interrupted

**Pace:** 1–3 requests per author, with 1.2–2.8 second delays between them, to avoid overloading the site. With 2,752 authors, this takes several hours — but the program runs in the background and can be resumed at any time.

---

## Step 4 — The Main Application

All three data sources are brought together in one beautiful, unified interface (`konyvtar_gui.py`). A native Windows application built with PyQt6, featuring a dark theme.

**Left sidebar:** search, status filters, format, tags, authors, legend

**Center:** book card grid with cover images, pagination (48 books per page), bulk selection. Each card has a colored stripe on the left showing the match level — from green to red.

**Right panel top:** book details — title, author, publisher, series, moly.hu rating, file status, description

**Right panel middle:** AI panel — summary, opinion, similar books, custom questions, model switcher. Powered by local Ollama models, no internet connection required.

**Right panel bottom:** phone file manager — drive selector, folder tree browser, create/rename/delete operations, book copying with a progress bar.

---

## The Result

One person. One machine. Open tools. And a library that rivals the biggest Hungarian digital platforms.

Cover image grids, intelligent search, an AI assistant, and phone synchronization.

Completely offline. Completely free. Completely yours.
