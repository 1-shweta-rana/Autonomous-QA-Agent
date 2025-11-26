# Backend/main.py

import os
from typing import Dict, Any

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from Backend.rag_utils import build_knowledge_base, retrieve_context, CHECKOUT_HTML_PATH
from Backend.testcase import get_structured_testcases

app = FastAPI(title="Autonomous QA Agent Backend")

# Allow Streamlit (localhost) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # fine for local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    query: str


class TestcaseRequest(BaseModel):
    feature: str


class SeleniumScriptRequest(BaseModel):
    test_case: Dict[str, Any]


# ---------- Helpers for Selenium script generation ----------

def _build_selenium_prompt(
    test_id: str,
    feature: str,
    scenario: str,
    expected: str,
    html: str,
    ctx_text: str,
) -> str:
    return f"""
You are an expert QA automation engineer writing Python Selenium scripts.

You are testing a single-page checkout form. Use the following HTML and documentation context
to select correct locators (ids, names, CSS selectors) that actually exist in the HTML.

HTML (checkout.html)
--------------------
{html}

Additional context from documentation
-------------------------------------
{ctx_text}

Test case to automate
---------------------
Test_ID: {test_id}
Feature: {feature}
Scenario: {scenario}
Expected_Result: {expected}

Requirements:
- Write a complete, runnable Python script using Selenium and Chrome WebDriver.
- Import the necessary modules (selenium.webdriver, selenium.webdriver.common.by.By, time/sleep if needed).
- Open the local checkout.html using a file:// URL (assume the user will adjust the path).
- Use element ids or names from the HTML whenever possible; otherwise use reasonable CSS selectors.
- Implement the test steps that match this scenario.
- Add at least one assertion that checks the expected result (e.g., 'Payment Successful!' message or a specific validation error text).
- Wrap everything in a function run_test() and call it from if __name__ == "__main__".
- Output ONLY Python code, no explanations, no markdown, no backticks.
"""


def _local_selenium_script(
    test_id: str,
    feature: str,
    scenario: str,
    expected: str,
) -> str:
    """
    Local fallback script generator.
    This is used if Gemini is unavailable or errors.
    """
    s_lower = scenario.lower()

    if "invalid discount code" in s_lower:
        assertion_comment = "# Assert that invalid discount message is displayed"
        assertion_line = (
            "assert 'Invalid discount code' in driver.page_source, "
            "'Expected invalid discount message not found'"
        )
    elif "subtotal is less than 100" in s_lower:
        assertion_comment = "# Assert that discount is NOT applied"
        assertion_line = (
            "assert 'SAVE15' not in driver.page_source, "
            "'Discount should not be applied for subtotal < 100'"
        )
    else:
        assertion_comment = "# Assert that payment success message is visible"
        assertion_line = (
            "assert 'Payment Successful' in driver.page_source, "
            "'Expected success message not found'"
        )

    # A generic Selenium script template using ids from typical checkout.html structure
    script = f'''import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service


def run_test():
    # Adjust this path to point to your local checkout.html
    checkout_path = Path(__file__).resolve().parent.parent / "checkout.html"
    url = checkout_path.as_uri()

    service = Service()  # Assumes chromedriver is in PATH
    driver = webdriver.Chrome(service=service)

    try:
        driver.get(url)
        time.sleep(1)

        # --- Fill basic checkout fields ---
        name_input = driver.find_element(By.ID, "name")
        email_input = driver.find_element(By.ID, "email")
        address_input = driver.find_element(By.ID, "address")
        shipping_standard = driver.find_element(By.ID, "shipping-standard")
        pay_button = driver.find_element(By.ID, "pay-btn")

        name_input.clear()
        name_input.send_keys("Test User")

        email_input.clear()
        email_input.send_keys("test@example.com")

        address_input.clear()
        address_input.send_keys("123 Test Street")

        shipping_standard.click()

        # --- Discount code scenario (if applicable) ---
        try:
            coupon_input = driver.find_element(By.ID, "discount-code")
            apply_button = driver.find_element(By.ID, "apply-discount-btn")
        except Exception:
            coupon_input = None
            apply_button = None

        # Test case:
        # {test_id} – {feature}
        # Scenario: {scenario}
        # Expected: {expected}

        if coupon_input and apply_button:
            coupon_input.clear()
            coupon_input.send_keys("SAVE15")
            apply_button.click()
            time.sleep(1)

        # Submit payment
        pay_button.click()
        time.sleep(2)

        {assertion_comment}
        {assertion_line}
    finally:
        time.sleep(2)
        driver.quit()


if __name__ == "__main__":
    run_test()
'''
    return script


# ---------- Endpoints ----------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/build_kb")
def build_kb():
    """
    Build the vector knowledge base from support_docs/ + checkout.html.
    """
    return build_knowledge_base()


@app.post("/debug_retrieve")
def debug_retrieve(req: QueryRequest):
    """
    Return top-k chunks for a query (for debugging / Phase 2 UI).
    """
    ctx = retrieve_context(req.query, top_k=5)
    return {"contexts": ctx}


@app.post("/chat")
def chat(req: QueryRequest):
    """
    Simple QA endpoint.
    We DO NOT call any chat LLM here, we just use retrieved chunks as the answer.
    """
    user_query = req.query

    ctx = retrieve_context(user_query, top_k=5)

    if not ctx:
        answer = "I couldn't find relevant information in the uploaded documents."
    else:
        combined = "\n\n".join(c.get("text", "") for c in ctx[:3])
        answer = (
            "Here is the most relevant information I found in the documents:\n\n"
            f"{combined}"
        )

    return {
        "response": answer,
        "context": ctx,
    }


@app.post("/generate_testcases")
def generate_testcases(req: TestcaseRequest):
    """
    Generate structured test cases for a given feature/scenario.
    Output is JSON with fields:
    - Test_ID
    - Feature
    - Test_Scenario
    - Expected_Result
    - Grounded_In
    """
    tcs = get_structured_testcases(req.feature)
    return {"feature": req.feature, "testcases": tcs}


@app.post("/generate_selenium_script")
def generate_selenium_script(req: SeleniumScriptRequest):
    """
    Generate a runnable Selenium Python script for a selected test case.

    Primary path: Use Gemini LLM (via REST API) with:
      - checkout.html contents
      - retrieved documentation context
      - structured test case

    Fallback: If Gemini is not available or errors, return a
    rule-based Selenium script so the endpoint still works.
    """
    tc = req.test_case
    test_id = tc.get("Test_ID", "TC-XXX")
    feature = tc.get("Feature", "")
    scenario = tc.get("Test_Scenario", "")
    expected = tc.get("Expected_Result", "")

    # 1) Read checkout.html
    try:
        html = CHECKOUT_HTML_PATH.read_text(encoding="utf-8")
    except Exception:
        html = ""

    # 2) Retrieve documentation context relevant to this test
    query = f"{feature}. {scenario}"
    contexts = retrieve_context(query, top_k=5)
    ctx_text = "\n\n".join(c.get("text", "") for c in contexts)

    # 3) Build prompt for LLM
    prompt = _build_selenium_prompt(test_id, feature, scenario, expected, html, ctx_text)

    gemini_key = os.environ.get("GEMINI_API_KEY")
    script_from_llm = None

    if gemini_key:
        try:
            # Use current Gemini text model endpoint
            url = "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent"
            res = requests.post(
                url=f"{url}?key={gemini_key}",
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=60,
            )

            if res.status_code == 200:
                data = res.json()
                parts = data["candidates"][0]["content"]["parts"]
                script_from_llm = "".join(p.get("text", "") for p in parts)
            else:
                print("Gemini API error:", res.status_code, res.text)
        except Exception as e:
            print("Exception while calling Gemini:", e)

    else:
        print("GEMINI_API not set; using local fallback for Selenium generation.")

    # If LLM failed or key missing, use local fallback
    if not script_from_llm:
        script_from_llm = _local_selenium_script(test_id, feature, scenario, expected)

    return {"script": script_from_llm, "test_id": test_id}
