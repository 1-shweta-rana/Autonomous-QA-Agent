# Autonomous QA Agent for Checkout Flow

This project implements an **Autonomous QA Agent** that can:
1. Build a **knowledge base** from support documents (product specs, business rules, API docs, UI/UX guide, and `checkout.html`).
2. Perform **question answering** over the knowledge base using semantic search (RAG-style).
3. Provide **test cases** and an example **Selenium automation script** for the checkout flow.

---

## 🧱 Project Structure

```text
AUTONOMOUS-QA-AGENT/
│
├── Backend/
│   ├── main.py              # FastAPI backend (build KB + QA endpoints)
│   ├── rag_utils.py         # Text extraction, chunking, Gemini embeddings, Chroma vector DB
│   ├── testcase.py          # Test cases derived from docs
│   └── selenium_script.py   # Example Selenium automation for checkout flow
│
├── Frontend/
│   └── streamlit.py         # Streamlit UI (upload docs, build KB, query KB)
│
├── support_docs/            # Uploaded support documents
├── vector_store/            # Persistent Chroma DB
├── checkout.html            # Checkout page under test
└── README.md
