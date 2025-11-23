# Frontend/streamlit.py

import streamlit as st
from pathlib import Path
import requests

BASE_BACKEND_URL = "http://127.0.0.1:8000"

# project root = folder that has Backend/, Frontend/, support_docs/, checkout.html
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SUPPORT_DOCS_DIR = PROJECT_ROOT / "support_docs"
CHECKOUT_HTML_PATH = PROJECT_ROOT / "checkout.html"


def save_uploaded_file(uploaded_file, target_dir: Path):
    target_dir.mkdir(exist_ok=True)
    dest = target_dir / uploaded_file.name
    with open(dest, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return dest


st.set_page_config(page_title="Autonomous QA Agent", layout="wide")
st.title("🧪 Autonomous QA Agent")
st.markdown("### Phase 1 – Build Knowledge Base")


# ------------ Upload docs ------------
st.subheader("1️⃣ Upload Support Documents")
support_files = st.file_uploader(
    "Upload 3–5 support documents (MD, TXT, JSON, PDF, etc.)",
    type=["md", "txt", "json", "pdf"],
    accept_multiple_files=True,
)

st.subheader("2️⃣ Upload checkout.html")
checkout_file = st.file_uploader(
    "Upload the checkout.html file",
    type=["html"],
    accept_multiple_files=False,
)

if st.button("💾 Save Files Locally"):
    saved_any = False

    if support_files:
        for f in support_files:
            save_uploaded_file(f, SUPPORT_DOCS_DIR)
        st.success(f"Saved {len(support_files)} support document(s) to support_docs/.")
        saved_any = True
    else:
        st.warning("No support documents uploaded.")

    if checkout_file:
        with open(CHECKOUT_HTML_PATH, "wb") as f:
            f.write(checkout_file.getbuffer())
        st.success("Saved checkout.html.")
        saved_any = True
    else:
        st.warning("No checkout.html uploaded.")

    if not saved_any:
        st.info("Upload at least one file and try again.")


st.subheader("3️⃣ Build Knowledge Base")

if st.button("🚀 Build Knowledge Base"):
    try:
        resp = requests.post(f"{BASE_BACKEND_URL}/build_kb")
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "ok":
                st.success(
                    f"Knowledge Base Built ✅ "
                    f"Documents: {data.get('num_documents')} | "
                    f"Chunks: {data.get('num_chunks')}"
                )
            else:
                st.error(f"Backend responded with error: {data}")
        else:
            st.error(f"Backend HTTP error: {resp.status_code}")
    except Exception as e:
        st.error(f"Could not reach backend: {e}")
