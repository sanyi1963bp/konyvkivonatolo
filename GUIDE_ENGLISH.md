# 📚 KönyvAI V4 – English Description & User Guide

## What is KönyvAI?

**KönyvAI** is a **local, offline artificial intelligence application** that allows you to upload books, studies, and professional documents, then ask questions about their content – as if you had a personal research assistant. The program **does not send any data outside your computer**; all processing happens locally on your own machine and GPU.

---

## 🎯 Who is it for?

- **Students** who want quick summaries of textbooks
- **Researchers** looking for specific information in long professional materials
- **Journalists and writers** processing source materials
- **Anyone** who wants to use AI **without privacy concerns**

---

## 🔧 System Requirements

### Hardware

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| GPU (VRAM) | 8 GB | **16 GB** (e.g., RTX 4070/5070 Ti) |
| RAM | 16 GB | **32–64 GB** |
| Storage | 10 GB | 20 GB+ |
| OS | Windows 10 | **Windows 11** or Linux |

> 💡 **Important**: The program uses the GPU for fast processing. It can run without a GPU, but very slowly.

### Software

1. **[Ollama](https://ollama.com/download)** – local AI model runtime
2. **Python 3.10+**
3. **Streamlit and other Python packages**

---

## 📥 Step-by-Step Installation

### 1. Install Ollama

1. Download from: https://ollama.com/download
2. Install on Windows (or Linux/Mac)
3. Verify in a new terminal:
   ```bash
   ollama list
   ```
   If running, you will see an empty list or previously downloaded models.

### 2. Download AI Models

The program uses two models: one for understanding text (embedding), one for generating answers (language model).

```bash
# Basic package (fast, less VRAM)
ollama pull llama3.1
ollama pull nomic-embed-text

# OR advanced package (smarter, more VRAM needed)
ollama pull qwen2.5:14b
ollama pull nomic-embed-text
```

### 3. Install Python Packages

Open a terminal (Command Prompt or PowerShell) and run:

```bash
pip install streamlit PyPDF2 numpy ollama ebooklib python-docx striprtf beautifulsoup4
```

### 4. Download and Launch the Program

1. Download `konyvai_v4.py`
2. Save it to a folder (e.g., `D:\KonyvAI`)
3. Navigate to that folder in the terminal:
   ```bash
   cd D:\KonyvAI
   ```
4. Launch:
   ```bash
   streamlit run konyvai_v4.py
   ```

Your browser will automatically open at `http://localhost:8501`.

---

## 🖥️ Interface Elements

### Top Section – File Upload

Upload your book here. Supported formats:

| Format | Extension | Notes |
|--------|-----------|-------|
| PDF | `.pdf` | Text-layer PDFs only (scanned/image PDFs will not work) |
| EPUB | `.epub` | Most common e-book format |
| Word | `.docx` | Modern Microsoft Word documents |
| Text | `.txt` | Plain text files |
| RTF | `.rtf` | Rich Text Format |

> ⚠️ Legacy `.doc` (Word 97-2003) is **not** supported! Open in Word and "Save As" → `.docx`.

### Left Sidebar – Settings

| Setting | What it does | Recommended value |
|---------|--------------|-------------------|
| **Language Model** | The "brain": generates answers and summaries | `llama3.1` (fast) or `qwen2.5:14b` (more accurate) |
| **Embedding Model** | The "memory": understands what each text fragment is about | `nomic-embed-text` |
| **Chunk Size** | Length of one text fragment in characters | **1000** |
| **Overlap** | Shared portion between consecutive fragments | **200** |
| **Creativity (Temperature)** | 0.0 = robotic/accurate, 1.0 = creative/made-up | **0.3** (ideal for books) |
| **How many chunks to use** | How many relevant fragments the model reads for an answer | **5** |

#### Detailed Explanation of Settings

**Chunk Size (1000 characters)**
The program splits the book into smaller fragments because the AI cannot process a 500-page book at once. 1000 characters ≈ 150–200 words, roughly one paragraph. If you increase it (e.g., 1500), the model sees more context but processing becomes slower.

**Overlap (200 characters)**
There is an overlap between fragments so that sentences are not cut off at the boundary. 200 characters means two adjacent fragments share 200 characters. This preserves sentence meaning across boundaries.

**Creativity / Temperature (0.3)**
This controls how "creative" the AI is. For books and facts, **0.2–0.4** is ideal because the model sticks to the text and does not hallucinate. For creative writing (poems, stories), 0.7–0.9 is better.

**How many chunks to use (5)**
When you ask a question, the program finds the 5 most relevant fragments and only feeds those to the AI. 5 fragments ≈ 5000 characters of context. If you give it more (e.g., 8), the answer may be more accurate but slower.

---

## 📖 How to Use

### 1. Upload a Book

1. Click the "Browse files" button
2. Select your book file
3. The program automatically:
   - Extracts the text
   - Splits it into chunks
   - Generates embeddings (this may take minutes for large books)
4. When ready, a green checkmark appears

### 2. Generate a Summary

Click the **"Summary"** tab and choose:

- **Short** – summarizes the first ~10 fragments (fast, 1–2 paragraphs)
- **Medium** – summarizes the first ~25 fragments (4–5 paragraphs)
- **Detailed** – summarizes the first ~50 fragments (10+ paragraphs, but slower)

> ⏱️ A detailed summary of a 500-page book can take 5–10 minutes!

### 3. Ask Questions About the Book

Click the **"Ask about the book"** tab and type your question. Examples:

- "What is Chapter 3 about?"
- "Who is the main character and what is their goal?"
- "What economic theories does the author mention?"
- "How does the author explain quantum mechanics?"

The program finds the most relevant text fragments and answers based on those.

---

## 🧠 How Does It Work in the Background? (RAG Technology)

KönyvAI uses **RAG** (Retrieval-Augmented Generation):

1. **Extraction** → extracts text from the file
2. **Chunking** → splits it into smaller, overlapping fragments
3. **Embedding** → converts each fragment into a number sequence (vector) that preserves meaning
4. **Storage** → stores vectors in NumPy arrays
5. **Retrieval** → converts your question into a vector too, and uses cosine similarity to find the closest text fragments
6. **Generation** → the local language model (e.g., Llama 3.1) answers the question based on the selected context

---

## 🛠️ Troubleshooting

| Error | Cause | Solution |
|-------|-------|----------|
| "Failed to connect to Ollama" | Ollama is not running | Run: `ollama serve` or start from the Start Menu |
| "No module named..." | Missing Python package | `pip install [package_name]` |
| "Could not extract text" | Scanned/image PDF | Use an OCR tool first (e.g., Adobe Acrobat) |
| Very slow | Chunk size too large | Reduce to 800, overlap to 100 |
| Inaccurate answers | Context too small | Increase "How many chunks" to 7 or 10 |
| Model "hallucinates" | Temperature too high | Reduce to 0.2 |

---

## 🔒 Privacy

Since **everything runs locally on your machine**:
- ✅ Your book **never leaves** your computer
- ✅ No cloud, no external server
- ✅ No data collection, no tracking
- ✅ No internet connection required after model download

---

## 📜 License

MIT License – free to use, modify, and distribute.

---

*Made with local artificial intelligence, without privacy concerns.*
