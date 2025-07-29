from flask import Flask, jsonify, request
import traceback

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

# ... (Keep ALLOWED_JOB_TITLES, CAMPUSES, CAMPUS_MAPPINGS unchanged)

def match_campus(campus_name):
    if campus_name in CAMPUS_MAPPINGS:
        return CAMPUS_MAPPINGS[campus_name]
    
    best_match = None
    best_ratio = 0
    for known_campus in CAMPUSES:
        ratio = difflib.SequenceMatcher(None, campus_name.lower(), known_campus.lower()).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = known_campus
    
    return best_match if best_ratio >= 0.5 else campus_name

def scroll_to_bottom(driver):
    print("Scrolling to bottom...")
    for _ in range(3):
        last_height = driver.execute_script("return document.body.scrollHeight")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            print("Scroll complete.")
            break

def scrape_aisd_directory_selenium(letters_range):
    print(f"Initializing Selenium driver for range {letters_range}...")
    options = Options()
    options.binary_location = '/usr/bin/google-chrome'
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,720")  # Smaller window to reduce memory
    options.add_argument("--disable-extensions")

    service = Service(executable_path='/usr/local/bin/chromedriver')
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_script_timeout(300)
    print("Navigating to directory...")
    driver.get("https://www.austinisd.org/directory")
    
    wait = WebDriverWait(driver, 60)
    print("Waiting for page to load...")
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    time.sleep(5)

    employees = []

    try:
        start_idx, end_idx = letters_range.split('-')
        start_idx = ord(start_idx.upper()) - ord('A')
        end_idx = min(ord(end_idx.upper()) - ord('A') + 1, 26)  # Ensure within alphabet
        letters = [chr(i + ord('A')) for i in range(start_idx, end_idx)]

        for idx, letter in enumerate(letters):
            print(f"Starting scrape for letter {letter} (index {idx})...")
            if idx > 0:
                print("Refreshing page...")
                driver.get("https://www.austinisd.org/directory")
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                time.sleep(5)

            letter_id = f"edit-letters-{letter.lower()}"
            print(f"Locating radio button for {letter_id}...")
            
            letter_radio = wait.until(EC.presence_of_element_located((By.ID, letter_id)), message=f"Timeout waiting for {letter_id}")
            print(f"Found radio button for {letter}...")
            
            for attempt in range(3):
                print(f"Attempt {attempt + 1} to select {letter}...")
                driver.execute_script("arguments[0].scrollIntoView(true);", letter_radio)
                driver.execute_script("arguments[0].click();", letter_radio)
                
                time.sleep(3)
                is_selected = driver.execute_script("return arguments[0].checked;", letter_radio)
                table_loaded = len(driver.find_elements(By.XPATH, "//table[starts-with(@id, 'edit-directory')]")) > 0
                if is_selected or table_loaded:
                    print(f"Successfully selected {letter} (checked: {is_selected}, table loaded: {table_loaded})")
                    break
                if attempt == 2:
                    print(f"Failed to select {letter} after 3 attempts.")
                    raise Exception(f"Failed to select {letter}")

            time.sleep(5)
            print("Waiting for table to load...")
            table = wait.until(EC.visibility_of_element_located((By.XPATH, "//table[starts-with(@id, 'edit-directory')]")))
            print(f"Table loaded with ID: {table.get_attribute('id')}")

            scroll_to_bottom(driver)
            rows = table.find_elements(By.TAG_NAME, "tr")[1:]
            print(f"Found {len(rows)} rows for {letter}...")

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
                            print(f"Added entry: {name}, {job_title}, {campus}")
                except Exception as e:
                    print(f"Error parsing row for {letter}: {str(e)}")

            print(f"Completed scrape for {letter}, found {len(rows)} rows")

    except Exception as e:
        print(f"Scraping error: {str(e)}")
    
    finally:
        print("Quitting driver...")
        driver.quit()
    
    print(f"Scrape complete for range {letters_range}. Total entries: {len(employees)}")
    return employees

@app.route('/scrape', methods=['GET'])
def scrape():
    print("Received /scrape request...")
    range_param = request.args.get('range', 'A-Z')  # Default to A-Z, e.g., ?range=A-E
    print(f"Processing range: {range_param}")
    try:
        data = scrape_aisd_directory_selenium(range_param)
        print(f"Returning data with {len(data)} entries...")
        return jsonify(data)
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"Error in /scrape: {str(e)}\n{error_trace}")
        return jsonify({"error": str(e), "traceback": error_trace}), 500

@app.route('/health', methods=['GET'])
def health():
    print("Health check passed")
    return jsonify({"status": "healthy"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting app on port {port}...")
    app.run(host="0.0.0.0", port=port)
