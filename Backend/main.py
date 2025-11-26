# Backend/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any

from Backend.rag_utils import build_knowledge_base, retrieve_context

app = FastAPI(title="Autonomous QA Agent Backend")

# Allow calls from Streamlit (localhost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # OK for local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    query: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/build_kb")
def build_kb():
    """
    Build the vector knowledge base from support_docs/ + checkout.html.
    """
    result = build_knowledge_base()
    return result


@app.post("/debug_retrieve")
def debug_retrieve(req: QueryRequest):
    """
    Helper endpoint to see what context is returned for a query.
    """
    ctx = retrieve_context(req.query, top_k=5)
    return {"contexts": ctx}


@app.post("/chat")
def chat(req: QueryRequest):
    """
    QA endpoint: uses RAG over the knowledge base.
    We DON'T call a big LLM here; we return an extractive answer
    using the retrieved chunks.
    """
    user_query = req.query

    # 1️⃣ Retrieve relevant chunks from the KB
    ctx = retrieve_context(user_query, top_k=5)

    if not ctx:
        answer = "I couldn't find relevant information in the uploaded documents."
    else:
        # Build a simple extractive-style answer by concatenating top chunks
        combined = "\n\n".join(c.get("text", "") for c in ctx[:3])
        answer = (
            "Here is the most relevant information I found in the documents:\n\n"
            f"{combined}"
        )

    return {
        "response": answer,
        "context": ctx,
    }
