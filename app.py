from flask import Flask, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
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
    "Andrews Elementary School", "Ann Richards School for Young Women Leaders",
    "Austin High School", "Austin ISD PreK Partnership PKP", "Bailey Middle School",
    "Baldwin Elementary School", "Baranoff Elementary School", "Barrington Elementary School",
    "Barton Hills Elementary School", "Bear Creek Elementary School", "Becker Elementary School",
    "Bedichek Middle School", "Bertha Sadler Means Young Women's Leadership Academy",
    "Blackshear Elementary School", "Blanton Elementary School", "Blazier Elementary School",
    "Boone Elementary School", "Bowie High School", "Brentwood Elementary School",
    "Bryker Woods Elementary School", "Burnet Middle School", "Campbell Elementary School",
    "Casey Elementary School", "Casis Elementary School", "Clayton Elementary School",
    "Clifton Career Center", "Cook Elementary School", "Counseling & Mental Health", "Covington Middle School",
    "Cowan Elementary School", "Crockett Early College High School", "Cunningham Elementary School",
    "Davis Elementary School", "Dawson Elementary School", "Dobie Middle School",
    "Doss Elementary School", "Early Referral Center", "Eastside Early College High School",
    "Galindo Elementary School", "Garza Independence High School", "Gorzycki Middle School",
    "Govalle Elementary School", "Graduation Preparatory Academy at Navarro",
    "Graduation Preparatory Academy at Travis", "Graham Elementary School", "Greenleaf NCC",
    "Guerrero-Thompson Elementary School", "Gullett Elementary School",
    "Gus Garcia Young Men's Leadership Academy", "Harris Elementary School",
    "Hart Elementary School", "Health Services and Nursing", "Highland Park Elementary School", "Hill Elementary School",
    "Houston Elementary School", "International High School", "JJAEP (Juvenile Justice Educ Pro)",
    "Jordan Elementary School", "Joslin Elementary School", "Kealing Middle School",
    "Kiker Elementary School", "Kocurek Elementary School", "Lamar Middle School",
    "Langford Elementary School", "LBJ Early College High School", "Leadership Academy",
    "Lee Elementary School", "Liberal Arts and Science Academy", "Linder Elementary School",
    "Lively Middle School", "Maplewood Elementary School", "General Marshall Middle School",
    "Martin Middle School", "Mathews Elementary School", "McBee Elementary School",
    "McCallum High School", "Menchaca Elementary School", "Mendez Middle School",
    "Mills Elementary School", "Murchison Middle School", "Navarro Early College High School",
    "Norman-Sims Elementary School", "Northeast Early College High School", "O. Henry Middle School",
    "Oak Hill Elementary School", "Oak Springs Elementary School", "Odom Elementary School",
    "Ortega Elementary School", "Overton Elementary School", "Padrón Elementary School",
    "Palm Elementary School", "Paredes Middle School", "Patton Elementary School",
    "Pecan Springs Elementary School", "Perez Elementary School", "Pickle Elementary School",
    "Pillow Elementary School", "Pleasant Hill Elementary School", "Reilly Elementary School",
    "Ridgetop Elementary School", "Rodriguez Elementary School", "Rosedale School",
    "Sánchez Elementary School", "Small Middle School", "St. Elmo Elementary School",
    "Summitt Elementary School", "Sunset Valley Elementary School", "T.A. Brown Elementary School",
    "Travis Early College High School", "Travis Heights Elementary School",
    "Uphaus Early Childhood Center", "Walnut Creek Elementary School", "Webb Middle School",
    "Widén Elementary School", "Williams Elementary School", "Winn Montessori School",
    "Wooldridge Elementary School", "Wooten Elementary School", "Zavala Elementary School",
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
        # No match: Keep raw name (no input possible in web app)
        return campus_name

def scroll_to_bottom(driver):
    for _ in range(3):
        last_height = driver.execute_script("return document.body.scrollHeight")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break

def scrape_aisd_directory_selenium():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    
    service = Service(ChromeDriverManager().install())
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
        pass  # Return what we have on error
    
    finally:
        driver.quit()
    
    return employees

@app.route('/scrape', methods=['GET'])
def scrape():
    data = scrape_aisd_directory_selenium()
    return jsonify(data)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)