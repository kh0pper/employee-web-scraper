from flask import Flask, jsonify
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

# List of job titles to scrape (unchanged)
ALLOWED_JOB_TITLES = {
    "Academy Director", "Administrative Assistant", "Advisor College and Career", "Assistant Data Processing",
    "Assistant Principal ES", "Assistant Principal HS", "Assistant Principal MS", "Clerk",
    "Counselor ES", "Counselor ES Bilingual", "Counselor HS", "Counselor HS Bilingual",
    "Counselor MS", "Counselor MS Bilingual", "Counselor Wellness", "GF Academic Dean",
    "GF Academy Director", "GF Specialist Parent Support", "Guidance Secretary", "Part Time Counselor ES", "Part Time Counselor MS", "Part Time Counselor HS",
    "Principal ES", "Principal HS", "Principal HS Interim", "Principal ES Interim",
    "Principal MS", "Principal MS Interim", "Principal SSC", "Registrar",
    "Registrar SSC", "School Nurse", "Specialist Attendance",
    "Licensed Mental Health Professional"
}

# List of campuses for matching (unchanged)
CAMPUSES = [
    "Akins Early College High School", "Allison Elementary School", "Anderson High School",
    # ... (keep full list as before)
    "Zilker Elementary School", "ALC"
]

# Predefined campus name mappings (unchanged)
CAMPUS_MAPPINGS = {
    "Alternative Learning Center": "ALC",
    "Travis County Juvenile Detention Center": "JJAEP (Juvenile Justice Educ Pro)"
}

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
    
    if best_ratio >= 0.5:
        return best_match
    else:
        return campus_name  # No input in web app, keep raw name

def scroll_to_bottom(driver):
    for _ in range(3):
        last_height = driver.execute_script("return document.body.scrollHeight")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break

def scrape_aisd_directory_selenium():
    print("Initializing Selenium WebDriver...")
    options = Options()
    options.binary_location = '/usr/bin/google-chrome'
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    
    service = Service(executable_path='/usr/local/bin/chromedriver')
    driver = webdriver.Chrome(service=service, options=options)
    print("WebDriver initialized, navigating to directory...")

    driver.set_script_timeout(300)  # Increase to 5 min to handle long loads
    driver.get("https://www.austinisd.org/directory")
    
    wait = WebDriverWait(driver, 60)  # Increase wait to 60 sec
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    print("Page loaded, starting scrape...")

    employees = []

    try:
        for idx, letter in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
            print(f"Starting scrape for letter: {letter}")
            if idx > 0 and idx % 5 == 0:
                print("Refreshing page to reset session...")
                driver.get("https://www.austinisd.org/directory")
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                time.sleep(10)

            letter_id = f"edit-letters-{letter.lower()}"
            
            letter_radio = wait.until(EC.presence_of_element_located((By.ID, letter_id)))
            
            for attempt in range(3):
                driver.execute_script("arguments[0].scrollIntoView(true);", letter_radio)
                driver.execute_script("arguments[0].click();", letter_radio)
                print(f"Attempt {attempt + 1} to select {letter}")
                
                time.sleep(5)
                is_selected = driver.execute_script("return arguments[0].checked;", letter_radio)
                table_loaded = len(driver.find_elements(By.XPATH, "//table[starts-with(@id, 'edit-directory')]")) > 0
                if is_selected or table_loaded:
                    print(f"Successfully selected {letter}")
                    break
                if attempt == 2:
                    raise Exception(f"Failed to select radio button for {letter} after 3 attempts")

            time.sleep(10)
            table = wait.until(EC.visibility_of_element_located((By.XPATH, "//table[starts-with(@id, 'edit-directory')]")))
            print(f"Table loaded for {letter}")

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
                            print(f"Added entry: {name} - {job_title}")
                except Exception as e:
                    print(f"Error parsing row for {letter}: {str(e)}")

            print(f"Completed scrape for {letter}, found {len(rows)} rows")

    except Exception as e:
        print(f"Scraping error: {str(e)}")
    
    finally:
        driver.quit()
        print("WebDriver quit, scrape finished.")

    return employees

@app.route('/scrape', methods=['GET'])
def scrape():
    print("Received /scrape request")
    try:
        data = scrape_aisd_directory_selenium()
        print(f"Scrape completed, returning {len(data)} records")
        return jsonify(data)
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"Error in scrape: {str(e)}\n{error_trace}")
        return jsonify({"error": str(e), "traceback": error_trace}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
