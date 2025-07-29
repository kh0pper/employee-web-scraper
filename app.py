from flask import Flask, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import re
import difflib
import os

app = Flask(__name__)

# ... (keep ALLOWED_JOB_TITLES, CAMPUSES, CAMPUS_MAPPINGS, match_campus, scroll_to_bottom as-is)

def scrape_aisd_directory_selenium():
    options = Options()
    options.add_argument("--headless=new")  # Use new headless mode for better stability
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")  # Add to prevent rendering issues
    
    driver = webdriver.Chrome(options=options)  # Let Selenium manage the driver
    driver.set_script_timeout(60)
    driver.get("https://www.austinisd.org/directory")
    
    # ... (keep the rest of the function as-is, including try/except/finally)

@app.route('/scrape', methods=['GET'])
def scrape():
    try:
        data = scrape_aisd_directory_selenium()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
