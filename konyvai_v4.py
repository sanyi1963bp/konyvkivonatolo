"""
KönyvAI V4 - Többformátumú könyvolvasó és kérdező alkalmazás
Támogatott formátumok: PDF, EPUB, DOCX, TXT, RTF
Ollama SDK + Streamlit + NumPy
"""

import streamlit as st
from PyPDF2 import PdfReader
import ollama
import numpy as np
import os
import tempfile
from io import BytesIO
import re

# ============ OLLAMA KAPCSOLAT BEÁLLÍTÁSA ============
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
    """PDF szöveg kinyerése."""
    pdf_reader = PdfReader(uploaded_file)
    text = ""
    for page in pdf_reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text


def extract_text_from_epub(uploaded_file):
    """EPUB szöveg kinyerése ebooklib + BeautifulSoup segítségével."""
    import ebooklib
    from ebooklib import epub
    from bs4 import BeautifulSoup

    # Ideiglenes fájl létrehozása (az ebooklib fájlútvonalat vár)
    with tempfile.NamedTemporaryFile(delete=False, suffix='.epub') as tmp:
        tmp.write(uploaded_file.getvalue())
        tmp_path = tmp.name

    try:
        book = epub.read_epub(tmp_path)
        texts = []
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                soup = BeautifulSoup(item.get_content(), 'html.parser')
                # Felesleges whitespace eltávolítása
                clean_text = re.sub(r'\s+', ' ', soup.get_text()).strip()
                if clean_text:
                    texts.append(clean_text)
        return '\n\n'.join(texts)
    finally:
        os.unlink(tmp_path)


def extract_text_from_docx(uploaded_file):
    """DOCX szöveg kinyerése."""
    from docx import Document
    doc = Document(BytesIO(uploaded_file.getvalue()))
    texts = [para.text for para in doc.paragraphs if para.text.strip()]
    return '\n'.join(texts)


def extract_text_from_rtf(uploaded_file):
    """RTF szöveg kinyerése."""
    from striprtf.striprtf import rtf_to_text
    content = uploaded_file.getvalue().decode('utf-8', errors='ignore')
    return rtf_to_text(content)


def extract_text_from_txt(uploaded_file):
    """TXT szöveg kinyerése."""
    return uploaded_file.getvalue().decode('utf-8', errors='ignore')


def detect_and_extract(uploaded_file):
    """Automatikusan felismeri a formátumot és kinyeri a szöveget."""
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
        raise ValueError(f"Nem támogatott fájlformátum: {uploaded_file.name}")


# ============ SEGÉDFUNKCIÓK (RAG) ============

def split_text(text, chunk_size=1000, overlap=200):
    """Egyszerű szövegdarabolás átfedéssel."""
    chunks = []
    start = 0
    text_len = len(text)
    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


def get_embedding(text, model="nomic-embed-text"):
    """Embedding generálása Ollama-val."""
    response = client.embeddings(model=model, prompt=text)
    return response["embedding"]


def cosine_similarity(a, b):
    """Koszinusz hasonlóság két vektor között."""
    a, b = np.array(a), np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10)


def get_top_chunks(query_emb, chunk_embs, chunks, k=5):
    """Visszaadja a k legrelevánsabb szövegdarabot."""
    similarities = [cosine_similarity(query_emb, emb) for emb in chunk_embs]
    top_indices = np.argsort(similarities)[-k:][::-1]
    return [chunks[i] for i in top_indices]


def ask_ollama(question, context, model="llama3.1", temperature=0.3):
    """Kérdés megválaszolása a megadott kontextus alapján."""
    prompt = f"""A következő szövegrészek alapján válaszolj magyarul a kérdésre.
Ha a válasz nem található meg a szövegben, írd azt, hogy "A szöveg alapján erre nem tudok válaszolni."

--- SZÖVEGRÉSZEK ---
{context}

--- KÉRDÉS ---
{question}

--- VÁLASZ ---"""

    response = client.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": temperature}
    )
    return response["message"]["content"]


def summarize_ollama(text, model="llama3.1", temperature=0.3):
    """Szöveg összefoglalása."""
    prompt = f"""Foglald össze magyarul a következő szöveget.
Írd le a fő témákat, kulcsfogalmakat és a szerző legfontosabb állításait.
Az összefoglalás legyen tömör, de informatív (3-5 bekezdés).

--- SZÖVEG ---
{text}

--- ÖSSZEFOGLALÁS ---"""

    response = client.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": temperature}
    )
    return response["message"]["content"]


# ============ STREAMLIT UI ============

st.set_page_config(page_title="KönyvAI V4 - Többformátum", page_icon="📚", layout="wide")

st.title("📚 KönyvAI V4")
st.markdown("**Olvass, összefoglalj és kérdezz – PDF | EPUB | DOCX | TXT | RTF**")

# Ollama állapot ellenőrzése
if not ollama_available:
    st.error(f"""
    ❌ **Nem sikerült kapcsolódni az Ollama-hoz!**

    Hiba: {ollama_error}

    **Ellenőrizd a következőket:**
    1. Futtasd: `ollama list` egy új terminálban
    2. Indítsd el: `ollama serve` vagy a Start menüből
    3. Ellenőrizd a tűzfalat a 11434-es porton
    """)
    st.stop()
else:
    st.success("✅ Ollama kapcsolat aktív!")

# Oldalsáv
with st.sidebar:
    st.header("⚙️ Beállítások")

    llm_model = st.selectbox(
        "Nyelvi modell",
        ["llama3.1", "llama3.2", "qwen2.5", "mistral", "deepseek-r1:14b"],
        index=0
    )

    emb_model = st.selectbox(
        "Embedding modell",
        ["nomic-embed-text", "mxbai-embed-large"],
        index=0
    )

    chunk_size = st.slider("Darab méret", 500, 2000, 1000, 100)
    chunk_overlap = st.slider("Átfedés", 0, 500, 200, 50)
    temperature = st.slider("Kreativitás", 0.0, 1.0, 0.3, 0.1)
    top_k = st.slider("Hány darabot használjon válaszhoz", 3, 10, 5, 1)

    st.divider()
    st.info("""
    **Szükséges modellek:**
    ```bash
    ollama pull llama3.1
    ollama pull nomic-embed-text
    ```
    """)

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

# Fájl feltöltés – több formátum
type_list = ["pdf", "epub", "docx", "txt", "rtf"]
uploaded_file = st.file_uploader(
    f"📎 Tölts fel egy könyvet ({', '.join(type_list).upper()})",
    type=type_list
)

if uploaded_file and not st.session_state.book_loaded:
    with st.spinner("Könyv feldolgozása..."):
        try:
            # Formátum detektálás és szöveg kinyerés
            text, fmt = detect_and_extract(uploaded_file)

            if not text.strip():
                st.error(f"❌ Nem sikerült szöveget kinyerni a {fmt} fájlból. Lehet, hogy képes/alapvetően üres?")
                st.stop()

            st.session_state.book_name = uploaded_file.name
            st.success(f"✅ Beolvasva: {uploaded_file.name} ({fmt}), {len(text):,} karakter")

            # Darabolás
            with st.spinner("Szöveg darabolása..."):
                chunks = split_text(text, chunk_size, chunk_overlap)
                st.session_state.chunks = chunks
                st.info(f"📄 {len(chunks)} darab készült")

            # Embedding generálás
            with st.spinner("Embeddingek generálása (ez eltarthat egy kicsig)..."):
                embeddings = []
                emb_progress = st.progress(0)
                for i, chunk in enumerate(chunks):
                    emb = get_embedding(chunk, model=emb_model)
                    embeddings.append(emb)
                    emb_progress.progress((i + 1) / len(chunks))
                st.session_state.embeddings = embeddings
                st.session_state.book_loaded = True

            st.success("🎯 Könyv készen áll! Töltsd be az Összefoglalás vagy Kérdezz fület.")

        except Exception as e:
            st.error(f"❌ Hiba: {str(e)}")
            st.stop()

# Funkciók
if st.session_state.book_loaded:
    st.caption(f"📖 Aktív könyv: **{st.session_state.book_name}**")

    tab1, tab2 = st.tabs(["📝 Összefoglalás", "❓ Kérdezz a könyvből"])

    with tab1:
        st.subheader("Könyv tartalmi összefoglalása")

        col1, col2, col3 = st.columns(3)
        with col1:
            short = st.button("Rövid összefoglaló", use_container_width=True)
        with col2:
            medium = st.button("Közepes összefoglaló", use_container_width=True)
        with col3:
            detailed = st.button("Részletes összefoglaló", use_container_width=True)

        if short or medium or detailed:
            if short:
                n_chunks = min(10, len(st.session_state.chunks))
                label = "Rövid"
            elif medium:
                n_chunks = min(25, len(st.session_state.chunks))
                label = "Közepes"
            else:
                n_chunks = min(50, len(st.session_state.chunks))
                label = "Részletes"

            context = "\n\n".join(st.session_state.chunks[:n_chunks])

            with st.spinner(f"{label} összefoglaló készítése..."):
                try:
                    summary = summarize_ollama(context, model=llm_model, temperature=temperature)
                    st.markdown("---")
                    st.markdown(summary)
                    st.markdown("---")
                except Exception as e:
                    st.error(f"Hiba: {str(e)}")

    with tab2:
        st.subheader("Interaktív kérdezés")
        st.caption("Tegyél fel konkrét kérdéseket a könyv tartalmával kapcsolatban!")

        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if question := st.chat_input("Mire vagy kíváncsi?"):
            st.session_state.messages.append({"role": "user", "content": question})
            with st.chat_message("user"):
                st.markdown(question)

            with st.chat_message("assistant"):
                with st.spinner("Válasz keresése..."):
                    try:
                        q_emb = get_embedding(question, model=emb_model)
                        top_chunks = get_top_chunks(
                            q_emb, 
                            st.session_state.embeddings, 
                            st.session_state.chunks, 
                            k=top_k
                        )
                        context = "\n\n---\n\n".join(top_chunks)
                        answer = ask_ollama(question, context, model=llm_model, temperature=temperature)

                        st.markdown(answer)
                        st.session_state.messages.append({"role": "assistant", "content": answer})

                    except Exception as e:
                        st.error(f"Hiba: {str(e)}")

        if st.button("💬 Beszélgetés törlése"):
            st.session_state.messages = []
            st.rerun()

else:
    st.info("👆 Tölts fel egy könyvet a kezdéshez!")

    st.markdown("""
    ### 📋 Telepítés

    ```bash
    pip install streamlit PyPDF2 numpy ollama ebooklib python-docx striprtf beautifulsoup4
    ```

    ### 🤖 Ollama modellek

    ```bash
    ollama pull llama3.1
    ollama pull nomic-embed-text
    ```

    ### 🚀 Indítás

    ```bash
    streamlit run konyvai_v4.py
    ```

    ### 📚 Támogatott formátumok

    | Formátum | Leírás |
    |----------|--------|
    | **PDF** | Hordozható dokumentumformátum |
    | **EPUB** | E-könyvek standardja (pl. Kindle kivételével) |
    | **DOCX** | Microsoft Word modern formátuma |
    | **TXT** | Egyszerű szövegfájl |
    | **RTF** | Rich Text Format |

    > ⚠️ A régi `.doc` (Word 97-2003) formátum **nem** támogatott. Mentésd át `.docx`-be!
    """)
