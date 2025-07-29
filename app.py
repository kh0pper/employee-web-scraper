from flask import Flask, jsonify
import traceback  # For better error traces
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import re
import difflib
import os

app = Flask(__name__)

# ... (Keep ALLOWED_JOB_TITLES, CAMPUSES, CAMPUS_MAPPINGS, match_campus, scroll_to_bottom unchanged)

def scrape_aisd_directory_selenium():
    options = Options()
    options.binary_location = '/usr/bin/google-chrome'  # Explicit Chrome path
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    
    service = Service(executable_path='/usr/local/bin/chromedriver')  # Explicit driver path
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_script_timeout(60)
    driver.get("https://www.austinisd.org/directory")
    
    wait = WebDriverWait(driver, 40)
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    time.sleep(10)

    employees = []

    try:
        for idx, letter in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
            if idx > 0 and idx % 5 == 0:
                driver.get("https://www.austinisd.org/directory")
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                time.sleep(10)

            letter_id = f"edit-letters-{letter.lower()}"
            
            letter_radio = wait.until(EC.presence_of_element_located((By.ID, letter_id)))
            
            for attempt in range(3):
                driver.execute_script("arguments[0].scrollIntoView(true);", letter_radio)
                driver.execute_script("arguments[0].click();", letter_radio)
                
                time.sleep(5)
                is_selected = driver.execute_script("return arguments[0].checked;", letter_radio)
                table_loaded = len(driver.find_elements(By.XPATH, "//table[starts-with(@id, 'edit-directory')]")) > 0
                if is_selected or table_loaded:
                    break
                if attempt == 2:
                    raise Exception(f"Failed to select {letter}")

            time.sleep(10)
            table = wait.until(EC.visibility_of_element_located((By.XPATH, "//table[starts-with(@id, 'edit-directory')]")))

            scroll_to_bottom(driver)
            rows = table.find_elements(By.TAG_NAME, "tr")[1:]

            for row in rows:
                try:
                    cols = row.find_elements(By.TAG_NAME, "td")
                    if len(cols) >= 4:
                        name = cols[0].text.strip()
                        job_title = cols[1].text.strip()

                        if job_title not in ALLOWED_JOB_TITLES:
                            continue

                        campus_raw = cols[2].find_element(By.TAG_NAME, "span").text.strip() if cols[2].find_elements(By.TAG_NAME, "span") else cols[2].text.strip()
                        campus = match_campus(campus_raw)
                        contact = cols[3].text.strip()
                        email_elem = cols[3].find_element(By.CLASS_NAME, "sr-only") if cols[3].find_elements(By.CLASS_NAME, "sr-only") else None
                        email = email_elem.text.strip() if email_elem else "N/A"
                        
                        phone_match = re.search(r"\d{3}-\d{3}-\d{4}", contact)
                        phone = phone_match.group(0) if phone_match else "N/A"

                        entry = {"name": name, "job_title": job_title, "campus": campus, "email": email, "phone": phone}
                        if entry not in employees:
                            employees.append(entry)
                except Exception:
                    pass  # Skip bad rows

    except Exception as e:
        print(f"Scraping error: {str(e)}")  # Log for Render console

    finally:
        driver.quit()
    
    return employees

@app.route('/scrape', methods=['GET'])
def scrape():
    try:
        data = scrape_aisd_directory_selenium()
        return jsonify(data)
    except Exception as e:
        error_trace = traceback.format_exc()
        print(error_trace)  # Log to Render console
        return jsonify({"error": str(e), "traceback": error_trace}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
