# Backend/rag_utils.py

from pathlib import Path
from typing import List, Dict, Any
import json
import os
import logging

import pypdf
from bs4 import BeautifulSoup
import chromadb
from chromadb.config import Settings
import google.generativeai as genai

logging.basicConfig(level=logging.INFO)

# ---------- GEMINI CONFIG ----------

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set in environment variables.")
genai.configure(api_key=GEMINI_API_KEY)

EMBED_MODEL = "models/text-embedding-004"


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed each text with Gemini. Looping is simpler and safe for small datasets."""
    embeddings: List[List[float]] = []
    for t in texts:
        content = t if t.strip() else " "  # avoid empty
        result = genai.embed_content(
            model=EMBED_MODEL,
            content=content,
        )
        # result is dict-like: {"embedding": [...]}
        embeddings.append(result["embedding"])
    return embeddings


# ---------- PATHS ----------

BASE_DIR = Path(__file__).resolve().parent.parent

SUPPORT_DOCS_DIR = BASE_DIR / "support_docs"
VECTOR_STORE_DIR = BASE_DIR / "vector_store"
CHECKOUT_HTML_PATH = BASE_DIR / "checkout.html"

SUPPORT_DOCS_DIR.mkdir(exist_ok=True)
VECTOR_STORE_DIR.mkdir(exist_ok=True)

# ---------- CHROMA CLIENT ----------

chroma_client = chromadb.PersistentClient(
    path=str(VECTOR_STORE_DIR),
    settings=Settings(anonymized_telemetry=False),
)
collection = chroma_client.get_or_create_collection(
    name="qa_kb",
    metadata={"hnsw:space": "cosine"},
)


# ---------- FILE READERS ----------

def _read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _read_pdf_pages(path: Path) -> List[str]:
    """Return a list of page texts (one string per page)."""
    reader = pypdf.PdfReader(str(path))
    pages: List[str] = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return pages


def _read_json(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return _read_text_file(path)

    def flatten(obj, prefix: str = "") -> List[str]:
        lines: List[str] = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                lines.extend(flatten(v, f"{prefix}{k}."))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                lines.extend(flatten(v, f"{prefix}[{i}]."))
        else:
            lines.append(f"{prefix}: {obj}")
        return lines

    return "\n".join(flatten(data))


def _read_html_text(path: Path) -> str:
    html = path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator="\n")


def extract_text_from_path(path: Path) -> List[str]:
    """
    Return a list of page-level texts.
    For text-like files, it's a single-element list.
    For PDFs, it's one string per page.
    """
    ext = path.suffix.lower()
    if ext in [".txt", ".md"]:
        return [_read_text_file(path)]
    if ext == ".pdf":
        return _read_pdf_pages(path)
    if ext == ".json":
        return [_read_json(path)]
    if ext in [".html", ".htm"]:
        return [_read_html_text(path)]
    return [_read_text_file(path)]


# ---------- CHUNKING ----------

def chunk_text(text: str, chunk_size: int = 500) -> List[str]:
    """
    Simple non-overlapping chunking to avoid MemoryError.
    """
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


# ---------- BUILD KB ----------

def build_knowledge_base() -> Dict[str, Any]:
    """
    Reads all files in support_docs + checkout.html,
    splits into small chunks, embeds via Gemini, and stores in ChromaDB.
    """
    global collection

    # reset collection
    try:
        chroma_client.delete_collection("qa_kb")
    except Exception:
        pass
    collection = chroma_client.create_collection(
        name="qa_kb", metadata={"hnsw:space": "cosine"}
    )

    doc_paths: List[Path] = []
    if SUPPORT_DOCS_DIR.exists():
        for p in SUPPORT_DOCS_DIR.iterdir():
            if p.is_file():
                doc_paths.append(p)
    if CHECKOUT_HTML_PATH.exists():
        doc_paths.append(CHECKOUT_HTML_PATH)

    if not doc_paths:
        return {"status": "error", "message": "No documents found."}

    ids: List[str] = []
    docs: List[str] = []
    metas: List[Dict[str, Any]] = []

    idx = 0
    for path in doc_paths:
        logging.info(f"📄 Processing {path.name}")
        page_texts = extract_text_from_path(path)

        for page_text in page_texts:
            # skip extremely huge pages
            if len(page_text) > 400_000:
                logging.warning(f"⚠️ Skipping very large page in {path.name}")
                continue

            for chunk in chunk_text(page_text):
                docs.append(chunk)
                metas.append({"source": path.name})
                ids.append(f"chunk-{idx}")
                idx += 1

    if not docs:
        return {"status": "error", "message": "No text chunks created."}

    logging.info(f"✨ Embedding {len(docs)} chunks via Gemini...")
    embeddings = embed_texts(docs)

    collection.add(
        documents=docs,
        embeddings=embeddings,
        metadatas=metas,
        ids=ids,
    )

    return {
        "status": "ok",
        "num_documents": len(doc_paths),
        "num_chunks": len(docs),
    }


# ---------- RETRIEVAL ----------

def retrieve_context(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Return top_k relevant chunks for a query using the same Gemini embeddings.
    """
    query_emb = embed_texts([query])[0]
    result = collection.query(
        query_embeddings=[query_emb],
        n_results=top_k,
    )

    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]

    out: List[Dict[str, Any]] = []
    for d, m in zip(docs, metas):
        out.append({"text": d, "metadata": m})
    return out
