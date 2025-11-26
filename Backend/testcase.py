# Backend/testcase.py

"""
Structured test case generator for the checkout flow.

Currently rule-based (no LLM here): the test cases are manually derived
from the product specs, API docs, business rules, and UI/UX guide.

The output matches the assignment schema:
- Test_ID
- Feature
- Test_Scenario
- Expected_Result
- Grounded_In (source document names)
"""

from typing import List, Dict


TEST_CASES: List[Dict] = [
    {
        "Test_ID": "TC-001",
        "Feature": "Discount Code",
        "Test_Scenario": "Apply a valid discount code 'SAVE15' when subtotal is ≥ 100.",
        "Expected_Result": "Total price is reduced by 15% and a confirmation message is shown.",
        "Grounded_In": ["product_specs.md", "business_rules.txt", "api_endpoints.json"],
    },
    {
        "Test_ID": "TC-002",
        "Feature": "Discount Code",
        "Test_Scenario": "Enter an invalid discount code.",
        "Expected_Result": "\"Invalid discount code!\" message is displayed and total price is unchanged.",
        "Grounded_In": ["product_specs.md", "business_rules.txt"],
    },
    {
        "Test_ID": "TC-003",
        "Feature": "Discount Code",
        "Test_Scenario": "Use discount code 'SAVE15' when subtotal is less than 100.",
        "Expected_Result": "Discount is not applied according to the business rule; appropriate error or rejection message is shown.",
        "Grounded_In": ["product_specs.md", "business_rules.txt"],
    },
    {
        "Test_ID": "TC-004",
        "Feature": "Checkout Form Validations",
        "Test_Scenario": "Submit the checkout form with Name field left empty.",
        "Expected_Result": "\"Name is required.\" validation error is shown in red below the Name field; order is not submitted.",
        "Grounded_In": ["ui_ux_guide.txt", "business_rules.txt", "checkout.html"],
    },
    {
        "Test_ID": "TC-005",
        "Feature": "Checkout Form Validations",
        "Test_Scenario": "Submit the checkout form with invalid email format (e.g., 'abc@').",
        "Expected_Result": "\"Enter a valid email.\" validation error is shown in red below the Email field; order is not submitted.",
        "Grounded_In": ["ui_ux_guide.txt", "business_rules.txt", "checkout.html"],
    },
    {
        "Test_ID": "TC-006",
        "Feature": "Checkout Form Validations",
        "Test_Scenario": "Submit the checkout form with Address field left empty.",
        "Expected_Result": "\"Address is required.\" validation error is shown in red below the Address field; order is not submitted.",
        "Grounded_In": ["ui_ux_guide.txt", "business_rules.txt", "checkout.html"],
    },
    {
        "Test_ID": "TC-007",
        "Feature": "Checkout Flow – Successful Payment",
        "Test_Scenario": "Complete checkout with all required fields valid and Standard shipping selected.",
        "Expected_Result": "No validation errors; total is calculated correctly; \"Payment Successful!\" is clearly visible.",
        "Grounded_In": ["product_specs.md", "ui_ux_guide.txt", "checkout.html"],
    },
    {
        "Test_ID": "TC-008",
        "Feature": "Shipping Options",
        "Test_Scenario": "Select Express shipping.",
        "Expected_Result": "Express shipping cost of ₹200 is added to the total amount.",
        "Grounded_In": ["product_specs.md", "business_rules.txt"],
    },
]


def get_structured_testcases(feature_query: str) -> List[Dict]:
    """
    Simple filter:
    - If the feature_query mentions 'discount' -> return Discount Code cases.
    - If it mentions 'checkout', 'form', or 'validation' -> return form/checkout cases.
    - Otherwise, return all as a generic test plan.
    """
    q = feature_query.lower()

    if "discount" in q or "coupon" in q:
        return [tc for tc in TEST_CASES if "Discount Code" in tc["Feature"]]

    if "checkout" in q or "form" in q or "validation" in q or "payment" in q:
        return [tc for tc in TEST_CASES if "Checkout" in tc["Feature"] or "Shipping" in tc["Feature"]]

    # Fallback: all test cases
    return TEST_CASES
