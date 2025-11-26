# Backend/selenium_script.py

"""
Simple Selenium automation script for the positive checkout flow.

NOTE:
- You must have:
    pip install selenium
- And a ChromeDriver / EdgeDriver available in PATH.

Run with:
    python -m Backend.selenium_script
"""

from pathlib import Path
from time import sleep

from selenium import webdriver
from selenium.webdriver.common.by import By


def run_checkout_test():
    project_root = Path(__file__).resolve().parent.parent
    checkout_path = project_root / "checkout.html"
    url = checkout_path.as_uri()  # file:///...

    driver = webdriver.Chrome()  # or webdriver.Edge()
    driver.maximize_window()
    driver.get(url)

    # TODO: change these IDs/names to match *your* checkout.html elements
    driver.find_element(By.ID, "name").send_keys("Test User")
    driver.find_element(By.ID, "email").send_keys("test@example.com")
    driver.find_element(By.ID, "address").send_keys("Test Address, City")

    # Select shipping method (e.g., radio button or select)
    try:
        driver.find_element(By.ID, "shipping-standard").click()
    except Exception:
        pass  # ignore if ID different

    # Select payment method
    try:
        driver.find_element(By.ID, "payment-credit").click()
    except Exception:
        pass

    # Click Pay Now
    driver.find_element(By.ID, "pay-now-btn").click()

    sleep(2)  # wait a bit for confirmation message

    assert "Payment Successful!" in driver.page_source

    print("✅ Selenium test passed: 'Payment Successful!' message found.")
    driver.quit()


if __name__ == "__main__":
    run_checkout_test()
