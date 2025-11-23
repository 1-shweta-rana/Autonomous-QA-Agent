# Backend/rag_utils.py

from pathlib import Path
from typing import List, Dict, Any
import json

import fitz  # pymupdf
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
import chromadb

# ---------- PATHS ----------

# This assumes structure:
# AUTONOMOUS-QA-AGENT/
#   QA Agent/
#     Backend/
#     Frontend/
#     checkout.html
#     support_docs/
#     vector_store/
BASE_DIR = Path(__file__).resolve().parent.parent  # "QA Agent" folder

SUPPORT_DOCS_DIR = BASE_DIR / "support_docs"
VECTOR_STORE_DIR = BASE_DIR / "vector_store"
CHECKOUT_HTML_PATH = BASE_DIR / "checkout.html"

SUPPORT_DOCS_DIR.mkdir(exist_ok=True)
VECTOR_STORE_DIR.mkdir(exist_ok=True)

# ---------- EMBEDDINGS + VECTOR DB ----------

embed_model = SentenceTransformer("all-MiniLM-L6-v2")

chroma_client = chromadb.PersistentClient(path=str(VECTOR_STORE_DIR))
# create or get collection
collection = chroma_client.get_or_create_collection(name="qa_kb")


# ---------- HELPERS: READING FILES ----------

def _read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _read_pdf(path: Path) -> str:
    doc = fitz.open(path)
    texts = [page.get_text() for page in doc]
    doc.close()
    return "\n".join(texts)


def _read_json(path: Path) -> str:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    def flatten(obj, prefix=""):
        lines = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                lines.extend(flatten(obj[k], f"{prefix}{k}."))
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


def extract_text_from_path(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in [".txt", ".md"]:
        return _read_text_file(path)
    if ext == ".pdf":
        return _read_pdf(path)
    if ext == ".json":
        return _read_json(path)
    if ext in [".html", ".htm"]:
        return _read_html_text(path)

    # fallback: treat as text
    return _read_text_file(path)


# ---------- CHUNKING + INGESTION ----------

def chunk_text(text: str, chunk_size: int = 800, overlap: int = 200) -> List[str]:
    chunks = []
    start = 0
    n = len(text)

    while start < n:
        end = min(start + chunk_size, n)
        chunks.append(text[start:end])
        start = end - overlap
        if start < 0:
            start = 0

    return chunks


def build_knowledge_base() -> Dict[str, Any]:
    """
    Reads all files in support_docs + checkout.html,
    chunks + embeds them, and stores in ChromaDB.
    """
    global collection

    # Reset collection each time
    try:
        chroma_client.delete_collection(name="qa_kb")
    except Exception:
        # first time there is nothing to delete
        pass

    collection = chroma_client.create_collection(name="qa_kb")

    doc_paths: List[Path] = []

    # all support docs
    if SUPPORT_DOCS_DIR.exists():
        for p in SUPPORT_DOCS_DIR.iterdir():
            if p.is_file():
                doc_paths.append(p)

    # checkout.html if present
    if CHECKOUT_HTML_PATH.exists():
        doc_paths.append(CHECKOUT_HTML_PATH)

    if not doc_paths:
        return {"status": "error", "message": "No documents found to ingest."}

    all_chunks: List[str] = []
    metadatas: List[Dict[str, Any]] = []
    ids: List[str] = []

    idx = 0
    for path in doc_paths:
        raw_text = extract_text_from_path(path)
        chunks = chunk_text(raw_text)

        for ch in chunks:
            all_chunks.append(ch)
            metadatas.append({"source": path.name})
            ids.append(f"doc-{idx}")
            idx += 1

    embeddings = embed_model.encode(all_chunks).tolist()

    collection.add(
        documents=all_chunks,
        embeddings=embeddings,
        metadatas=metadatas,
        ids=ids,
    )

    return {
        "status": "ok",
        "num_documents": len(doc_paths),
        "num_chunks": len(all_chunks),
    }


def retrieve_context(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Return top_k relevant chunks for given query.
    """
    query_emb = embed_model.encode([query]).tolist()[0]
    result = collection.query(
        query_embeddings=[query_emb],
        n_results=top_k,
    )

    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]

    out = []
    for d, m in zip(docs, metas):
        out.append({"text": d, "metadata": m})
    return out
