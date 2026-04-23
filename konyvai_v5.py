"""
KönyvAI V5 - Nyelvváltós verzió (Magyar / English)
Ollama SDK + Streamlit + NumPy (LangChain-mentes)
"""

import streamlit as st
from PyPDF2 import PdfReader
import ollama
import numpy as np
import os
import tempfile
from io import BytesIO
import re

# ============ NYELVI FORDÍTÁSOK ============
I18N = {
    "hu": {
        "title": "📚 KönyvAI V5",
        "subtitle": "Olvass, összefoglalj és kérdezz – PDF | EPUB | DOCX | TXT | RTF",
        "settings": "⚙️ Beállítások",
        "language": "Felület nyelve",
        "llm_model": "Nyelvi modell",
        "emb_model": "Embedding modell",
        "chunk_size": "Darab méret",
        "chunk_overlap": "Átfedés",
        "temperature": "Kreativitás",
        "top_k": "Hány darabot használjon válaszhoz",
        "upload": "📎 Tölts fel egy könyvet",
        "upload_types": "PDF, EPUB, DOCX, TXT, RTF",
        "reading": "Könyv feldolgozása...",
        "pages_chars": "Beolvasva: {pages} oldal, {chars:,} karakter",
        "chunks_ready": "{count} darab készült",
        "embedding": "Embeddingek generálása (ez eltarthat egy kicsig)...",
        "ready": "🎯 Könyv készen áll!",
        "summary_tab": "📝 Összefoglalás",
        "ask_tab": "❓ Kérdezz a könyvből",
        "short_btn": "Rövid összefoglaló",
        "medium_btn": "Közepes összefoglaló",
        "detailed_btn": "Részletes összefoglaló",
        "summary_type": "Összefoglalás típusa",
        "summary_working": "{label} összefoglaló készítése...",
        "ask_placeholder": "Mire vagy kíváncsi?",
        "ask_caption": "Tegyél fel konkrét kérdéseket a könyv tartalmával kapcsolatban!",
        "clear_chat": "💬 Beszélgetés törlése",
        "active_book": "📖 Aktív könyv: **{name}**",
        "no_file": "👆 Tölts fel egy könyvet a kezdéshez!",
        "install_title": "📋 Telepítés",
        "models_title": "🤖 Ollama modellek",
        "launch_title": "🚀 Indítás",
        "supported_formats": "📚 Támogatott formátumok",
        "ollama_ok": "✅ Ollama kapcsolat aktív!",
        "ollama_error_title": "❌ Nem sikerült kapcsolódni az Ollama-hoz!",
        "ollama_error_body": "**Ellenőrizd a következőket:**\n1. Futtasd: `ollama list` egy új terminálban\n2. Indítsd el: `ollama serve` vagy a Start menüből\n3. Ellenőrizd a tűzfalat a 11434-es porton",
        "extract_error": "❌ Nem sikerült szöveget kinyerni a {fmt} fájlból.",
        "generic_error": "❌ Hiba: {error}",
        "answer_error": "Hiba: {error}",
        "thinking": "A modell a választ keresi...",
        "prompt_answer": """A következő szövegrészek alapján válaszolj magyarul a kérdésre.
Ha a válasz nem található meg a szövegben, írd azt, hogy "A szöveg alapján erre nem tudok válaszolni."

--- SZÖVEGRÉSZEK ---
{context}

--- KÉRDÉS ---
{question}

--- VÁLASZ ---""",
        "prompt_summary": """Foglald össze magyarul a következő szöveget.
Írd le a fő témákat, kulcsfogalmakat és a szerző legfontosabb állításait.
Az összefoglalás legyen tömör, de informatív (3-5 bekezdés).

--- SZÖVEG ---
{text}

--- ÖSSZEFOGLALÁS ---""",
        "tip_models": "**Tipp:** Ha még nem töltötted le a modelleket:\n```bash\nollama pull llama3.1\nollama pull nomic-embed-text\n```",
        "install_cmd": "pip install streamlit PyPDF2 numpy ollama ebooklib python-docx striprtf beautifulsoup4",
        "launch_cmd": "streamlit run konyvai_v5.py",
        "doc_note": "> ⚠️ A régi `.doc` (Word 97-2003) formátum **nem** támogatott. Mentésd át `.docx`-be!",
        "table_format": "| Formátum | Leírás |\n|----------|--------|",
        "pdf_desc": "Hordozható dokumentumformátum",
        "epub_desc": "E-könyvek standardja",
        "docx_desc": "Microsoft Word modern formátuma",
        "txt_desc": "Egyszerű szövegfájl",
        "rtf_desc": "Rich Text Format",
        "lang_names": {"hu": "Magyar", "en": "English"},
    },
    "en": {
        "title": "📚 KönyvAI V5",
        "subtitle": "Read, summarize & ask – PDF | EPUB | DOCX | TXT | RTF",
        "settings": "⚙️ Settings",
        "language": "Interface language",
        "llm_model": "Language model",
        "emb_model": "Embedding model",
        "chunk_size": "Chunk size",
        "chunk_overlap": "Overlap",
        "temperature": "Creativity (temperature)",
        "top_k": "Chunks to use for answer",
        "upload": "📎 Upload a book",
        "upload_types": "PDF, EPUB, DOCX, TXT, RTF",
        "reading": "Processing book...",
        "pages_chars": "Loaded: {pages} pages, {chars:,} characters",
        "chunks_ready": "{count} chunks created",
        "embedding": "Generating embeddings (this may take a while)...",
        "ready": "🎯 Book is ready!",
        "summary_tab": "📝 Summary",
        "ask_tab": "❓ Ask about the book",
        "short_btn": "Short summary",
        "medium_btn": "Medium summary",
        "detailed_btn": "Detailed summary",
        "summary_type": "Summary type",
        "summary_working": "Creating {label} summary...",
        "ask_placeholder": "What would you like to know?",
        "ask_caption": "Ask specific questions about the book's content!",
        "clear_chat": "💬 Clear conversation",
        "active_book": "📖 Active book: **{name}**",
        "no_file": "👆 Upload a book to get started!",
        "install_title": "📋 Installation",
        "models_title": "🤖 Ollama models",
        "launch_title": "🚀 Launch",
        "supported_formats": "📚 Supported formats",
        "ollama_ok": "✅ Ollama connection active!",
        "ollama_error_title": "❌ Failed to connect to Ollama!",
        "ollama_error_body": "**Please check:**\n1. Run: `ollama list` in a new terminal\n2. Start: `ollama serve` or from the Start Menu\n3. Check firewall on port 11434",
        "extract_error": "❌ Could not extract text from {fmt} file.",
        "generic_error": "❌ Error: {error}",
        "answer_error": "Error: {error}",
        "thinking": "The model is searching for an answer...",
        "prompt_answer": """Answer the following question in English based on the text fragments below.
If the answer is not found in the text, say "Based on the text, I cannot answer this."

--- TEXT FRAGMENTS ---
{context}

--- QUESTION ---
{question}

--- ANSWER ---""",
        "prompt_summary": """Summarize the following text in English.
Describe the main topics, key concepts, and the author's most important claims.
The summary should be concise but informative (3-5 paragraphs).

--- TEXT ---
{text}

--- SUMMARY ---""",
        "tip_models": "**Tip:** If you haven't downloaded the models yet:\n```bash\nollama pull llama3.1\nollama pull nomic-embed-text\n```",
        "install_cmd": "pip install streamlit PyPDF2 numpy ollama ebooklib python-docx striprtf beautifulsoup4",
        "launch_cmd": "streamlit run konyvai_v5.py",
        "doc_note": "> ⚠️ Legacy `.doc` (Word 97-2003) is **not** supported. Save as `.docx` instead!",
        "table_format": "| Format | Description |\n|--------|-------------|",
        "pdf_desc": "Portable Document Format",
        "epub_desc": "Standard e-book format",
        "docx_desc": "Modern Microsoft Word format",
        "txt_desc": "Plain text file",
        "rtf_desc": "Rich Text Format",
        "lang_names": {"hu": "Magyar", "en": "English"},
    }
}

# ============ OLLAMA KAPCSOLAT ============
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
try:
    client = ollama.Client(host=OLLAMA_HOST)
    client.list()
    ollama_available = True
except Exception as e:
    ollama_available = False
    ollama_error = str(e)

# ============ FORMÁTUM KEZELŐK ============

def extract_text_from_pdf(uploaded_file):
    pdf_reader = PdfReader(uploaded_file)
    text = ""
    for page in pdf_reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text

def extract_text_from_epub(uploaded_file):
    import ebooklib
    from ebooklib import epub
    from bs4 import BeautifulSoup
    with tempfile.NamedTemporaryFile(delete=False, suffix='.epub') as tmp:
        tmp.write(uploaded_file.getvalue())
        tmp_path = tmp.name
    try:
        book = epub.read_epub(tmp_path)
        texts = []
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                soup = BeautifulSoup(item.get_content(), 'html.parser')
                clean_text = re.sub(r'\s+', ' ', soup.get_text()).strip()
                if clean_text:
                    texts.append(clean_text)
        return '\n\n'.join(texts)
    finally:
        os.unlink(tmp_path)

def extract_text_from_docx(uploaded_file):
    from docx import Document
    doc = Document(BytesIO(uploaded_file.getvalue()))
    texts = [para.text for para in doc.paragraphs if para.text.strip()]
    return '\n'.join(texts)

def extract_text_from_rtf(uploaded_file):
    from striprtf.striprtf import rtf_to_text
    content = uploaded_file.getvalue().decode('utf-8', errors='ignore')
    return rtf_to_text(content)

def extract_text_from_txt(uploaded_file):
    return uploaded_file.getvalue().decode('utf-8', errors='ignore')

def detect_and_extract(uploaded_file):
    filename = uploaded_file.name.lower()
    if filename.endswith('.pdf'):
        return extract_text_from_pdf(uploaded_file), "PDF"
    elif filename.endswith('.epub'):
        return extract_text_from_epub(uploaded_file), "EPUB"
    elif filename.endswith('.docx'):
        return extract_text_from_docx(uploaded_file), "DOCX"
    elif filename.endswith('.rtf'):
        return extract_text_from_rtf(uploaded_file), "RTF"
    elif filename.endswith('.txt'):
        return extract_text_from_txt(uploaded_file), "TXT"
    else:
        raise ValueError(f"Unsupported format: {uploaded_file.name}")

# ============ SEGÉDFUNKCIÓK ============

def split_text(text, chunk_size=1000, overlap=200):
    chunks = []
    start = 0
    text_len = len(text)
    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks

def get_embedding(text, model="nomic-embed-text"):
    response = client.embeddings(model=model, prompt=text)
    return response["embedding"]

def cosine_similarity(a, b):
    a, b = np.array(a), np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10)

def get_top_chunks(query_emb, chunk_embs, chunks, k=5):
    similarities = [cosine_similarity(query_emb, emb) for emb in chunk_embs]
    top_indices = np.argsort(similarities)[-k:][::-1]
    return [chunks[i] for i in top_indices]

def ask_ollama(question, context, model="llama3.1", temperature=0.3, lang="hu"):
    prompt_template = I18N[lang]["prompt_answer"]
    prompt = prompt_template.format(context=context, question=question)
    response = client.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": temperature}
    )
    return response["message"]["content"]

def summarize_ollama(text, model="llama3.1", temperature=0.3, lang="hu"):
    prompt_template = I18N[lang]["prompt_summary"]
    prompt = prompt_template.format(text=text)
    response = client.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": temperature}
    )
    return response["message"]["content"]

# ============ STREAMLIT UI ============

st.set_page_config(page_title="KönyvAI V5", page_icon="📚", layout="wide")

# Nyelv inicializálása session state-ben
if "lang" not in st.session_state:
    st.session_state.lang = "hu"

# Nyelvváltó callback
def change_language():
    st.session_state.lang = st.session_state.lang_selector

# Sidebar NYELVVÁLTÓ (mindenek felett)
with st.sidebar:
    st.selectbox(
        "🌐 Language / Nyelv",
        options=["hu", "en"],
        format_func=lambda x: I18N[x]["lang_names"][x],
        index=0 if st.session_state.lang == "hu" else 1,
        key="lang_selector",
        on_change=change_language
    )
    st.divider()

L = I18N[st.session_state.lang]

st.title(L["title"])
st.markdown(L["subtitle"])

# Ollama állapot
if not ollama_available:
    st.error(f"""
    {L["ollama_error_title"]}

    Hiba: {ollama_error}

    {L["ollama_error_body"]}
    """)
    st.stop()
else:
    st.success(L["ollama_ok"])

# Beállítások (a kiválasztott nyelven)
with st.sidebar:
    st.header(L["settings"])

    llm_model = st.selectbox(
        L["llm_model"],
        options=["llama3.1", "llama3.2", "qwen2.5", "mistral", "deepseek-r1:14b"],
        index=0
    )

    emb_model = st.selectbox(
        L["emb_model"],
        options=["nomic-embed-text", "mxbai-embed-large"],
        index=0
    )

    chunk_size = st.slider(L["chunk_size"], 500, 2000, 1000, 100)
    chunk_overlap = st.slider(L["chunk_overlap"], 0, 500, 200, 50)
    temperature = st.slider(L["temperature"], 0.0, 1.0, 0.3, 0.1)
    top_k = st.slider(L["top_k"], 3, 10, 5, 1)

    st.divider()
    st.info(L["tip_models"])

# Session state
if "chunks" not in st.session_state:
    st.session_state.chunks = []
if "embeddings" not in st.session_state:
    st.session_state.embeddings = []
if "book_loaded" not in st.session_state:
    st.session_state.book_loaded = False
if "messages" not in st.session_state:
    st.session_state.messages = []
if "book_name" not in st.session_state:
    st.session_state.book_name = ""

# Fájl feltöltés
type_list = ["pdf", "epub", "docx", "txt", "rtf"]
uploaded_file = st.file_uploader(
    L["upload"] + f" ({L['upload_types']})",
    type=type_list
)

if uploaded_file and not st.session_state.book_loaded:
    with st.spinner(L["reading"]):
        try:
            text, fmt = detect_and_extract(uploaded_file)

            if not text.strip():
                st.error(L["extract_error"].format(fmt=fmt))
                st.stop()

            st.session_state.book_name = uploaded_file.name
            st.success(L["pages_chars"].format(pages="", chars=len(text)))

            with st.spinner(L["reading"]):
                chunks = split_text(text, chunk_size, chunk_overlap)
                st.session_state.chunks = chunks
                st.info(L["chunks_ready"].format(count=len(chunks)))

            with st.spinner(L["embedding"]):
                embeddings = []
                emb_progress = st.progress(0)
                for i, chunk in enumerate(chunks):
                    emb = get_embedding(chunk, model=emb_model)
                    embeddings.append(emb)
                    emb_progress.progress((i + 1) / len(chunks))
                st.session_state.embeddings = embeddings
                st.session_state.book_loaded = True

            st.success(L["ready"])

        except Exception as e:
            st.error(L["generic_error"].format(error=str(e)))
            st.stop()

# Funkciók
if st.session_state.book_loaded:
    st.caption(L["active_book"].format(name=st.session_state.book_name))

    tab1, tab2 = st.tabs([L["summary_tab"], L["ask_tab"]])

    with tab1:
        st.subheader(L["summary_tab"])

        col1, col2, col3 = st.columns(3)
        with col1:
            short = st.button(L["short_btn"], use_container_width=True)
        with col2:
            medium = st.button(L["medium_btn"], use_container_width=True)
        with col3:
            detailed = st.button(L["detailed_btn"], use_container_width=True)

        if short or medium or detailed:
            if short:
                n_chunks = min(10, len(st.session_state.chunks))
                label = L["short_btn"]
            elif medium:
                n_chunks = min(25, len(st.session_state.chunks))
                label = L["medium_btn"]
            else:
                n_chunks = min(50, len(st.session_state.chunks))
                label = L["detailed_btn"]

            context = "\n\n".join(st.session_state.chunks[:n_chunks])

            with st.spinner(L["summary_working"].format(label=label)):
                try:
                    summary = summarize_ollama(
                        context, model=llm_model, temperature=temperature,
                        lang=st.session_state.lang
                    )
                    st.markdown("---")
                    st.markdown(summary)
                    st.markdown("---")
                except Exception as e:
                    st.error(L["answer_error"].format(error=str(e)))

    with tab2:
        st.subheader(L["ask_tab"])
        st.caption(L["ask_caption"])

        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if question := st.chat_input(L["ask_placeholder"]):
            st.session_state.messages.append({"role": "user", "content": question})
            with st.chat_message("user"):
                st.markdown(question)

            with st.chat_message("assistant"):
                with st.spinner(L["thinking"]):
                    try:
                        q_emb = get_embedding(question, model=emb_model)
                        top_chunks = get_top_chunks(
                            q_emb,
                            st.session_state.embeddings,
                            st.session_state.chunks,
                            k=top_k
                        )
                        context = "\n\n---\n\n".join(top_chunks)
                        answer = ask_ollama(
                            question, context, model=llm_model,
                            temperature=temperature, lang=st.session_state.lang
                        )

                        st.markdown(answer)
                        st.session_state.messages.append({"role": "assistant", "content": answer})

                    except Exception as e:
                        st.error(L["answer_error"].format(error=str(e)))

        if st.button(L["clear_chat"]):
            st.session_state.messages = []
            st.rerun()

else:
    st.info(L["no_file"])

    st.markdown(f"""
    ### {L['install_title']}

    ```bash
    {L['install_cmd']}
    ```

    ### {L['models_title']}

    ```bash
    ollama pull llama3.1
    ollama pull nomic-embed-text
    ```

    ### {L['launch_title']}

    ```bash
    {L['launch_cmd']}
    ```

    ### {L['supported_formats']}

    {L['table_format']}
    | PDF | {L['pdf_desc']} |
    | EPUB | {L['epub_desc']} |
    | DOCX | {L['docx_desc']} |
    | TXT | {L['txt_desc']} |
    | RTF | {L['rtf_desc']} |

    {L['doc_note']}
    """)
