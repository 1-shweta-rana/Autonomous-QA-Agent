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

# ------------ Build KB ------------
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

# ================== PHASE 2: QA OVER KB ==================

st.markdown("---")
st.markdown("### Phase 2 – Query the Knowledge Base")
st.markdown("Use the built knowledge base to ask questions about the workflow, rules, APIs, and UI.")

user_query = st.text_input(
    "💬 Ask a question based on the uploaded documents:",
    placeholder="Example: What are the main validation rules in the checkout flow?",
)

if st.button("❓ Ask"):
    if not user_query.strip():
        st.warning("Please type a question first.")
    else:
        with st.spinner("Searching in the knowledge base..."):
            try:
                resp = requests.post(
                    f"{BASE_BACKEND_URL}/chat",
                    json={"query": user_query},
                )

                if resp.status_code == 200:
                    data = resp.json()
                    answer = data.get("response", "")
                    context = data.get("context", [])

                    # 🔹 Pretty formatting for the main question
                    uq = user_query.lower()
                    if "fields" in uq and "checkout" in uq:
                        st.markdown("### ✅ Answer – Required Checkout Fields")
                        st.markdown(
                            "- Name  \n"
                            "- Email  \n"
                            "- Address  \n"
                            "- Shipping Method  \n"
                            "- Payment Method"
                        )
                    else:
                        st.markdown("### ✅ Answer (from documents)")
                        st.write(answer)

                    # Always show retrieved chunks for viva
                    if context:
                        st.markdown("### 🔍 Retrieved Context Chunks")
                        for c in context:
                            src = c.get("metadata", {}).get("source", "Unknown")
                            st.write(f"**Source:** {src}")
                            st.write(c.get("text", ""))
                            st.markdown("---")
                    else:
                        st.info("No context chunks were returned.")
                else:
                    st.error(f"Backend HTTP error from /chat: {resp.status_code}")
            except Exception as e:
                st.error(f"Could not reach backend /chat: {e}")

# ================== PHASE 3: TEST CASE GENERATION ==================

st.markdown("---")
st.markdown("### Phase 3 – Generate Test Plans from Documentation")

feature_text = st.text_input(
    "🧪 Describe the feature or scenario for which you want test cases:",
    placeholder="Examples: 'discount code', 'checkout form validations', 'shipping rules'",
    key="feature_input",
)

if st.button("🧾 Generate Test Cases"):
    if not feature_text.strip():
        st.warning("Please describe a feature or scenario first.")
    else:
        with st.spinner("Generating structured test cases..."):
            try:
                resp = requests.post(
                    f"{BASE_BACKEND_URL}/generate_testcases",
                    json={"feature": feature_text},
                )

                if resp.status_code == 200:
                    data = resp.json()
                    tcs = data.get("testcases", [])

                    if not tcs:
                        st.info("No test cases found for this feature.")
                    else:
                        st.success(f"Generated {len(tcs)} test case(s).")

                        # Save testcases for Phase 4
                        st.session_state["last_testcases"] = tcs

                        # JSON Output
                        st.markdown("#### 📦 JSON Output")
                        st.json(tcs)

                        # Markdown Table Output
                        st.markdown("#### 📋 Markdown Table")
                        header = "| Test_ID | Feature | Test_Scenario | Expected_Result | Grounded_In |\n"
                        header += "|--------|---------|---------------|-----------------|-------------|\n"

                        rows = ""
                        for tc in tcs:
                            grounded = ", ".join(tc.get("Grounded_In", []))
                            rows += (
                                f"| {tc['Test_ID']} | {tc['Feature']} | "
                                f"{tc['Test_Scenario']} | {tc['Expected_Result']} | "
                                f"{grounded} |\n"
                            )

                        st.markdown(header + rows)
                else:
                    st.error(f"Backend HTTP error from /generate_testcases: {resp.status_code}")
            except Exception as e:
                st.error(f"Could not reach backend /generate_testcases: {e}")


# ================== PHASE 4: SELENIUM SCRIPT GENERATION ==================

st.markdown("---")
st.markdown("### Phase 4 – Generate Selenium Script from a Test Case")

if "last_testcases" in st.session_state and st.session_state["last_testcases"]:
    tcs = st.session_state["last_testcases"]

    option_labels = [f"{tc['Test_ID']} – {tc['Feature']}" for tc in tcs]

    selected_label = st.selectbox(
        "Select a test case to automate:",
        option_labels,
        index=0,
        key="selenium_tc_select",
    )

    if st.button("⚙️ Generate Selenium Script"):
        # Find which test case was chosen
        selected_index = option_labels.index(selected_label)
        selected_tc = tcs[selected_index]

        with st.spinner("Asking Gemini to generate Selenium code..."):
            try:
                resp = requests.post(
                    f"{BASE_BACKEND_URL}/generate_selenium_script",
                    json={"test_case": selected_tc},
                )

                if resp.status_code == 200:
                    data = resp.json()
                    script = data.get("script", "")

                    if not script:
                        st.warning("Backend did not return any script.")
                    else:
                        st.markdown("#### 🧾 Generated Selenium Python Script")
                        st.code(script, language="python")
                else:
                    st.error(
                        f"Backend HTTP error from /generate_selenium_script: {resp.status_code}"
                    )
            except Exception as e:
                st.error(f"Could not reach backend /generate_selenium_script: {e}")
else:
    st.info("First generate test cases above, then you can select one here to generate a Selenium script.")
