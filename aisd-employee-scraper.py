from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time
import re
import difflib

# Google Sheets setup
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
CREDS_FILE = "~/path-to-credentials.json"
SHEET_NAME = "AISD Employees"

# List of job titles to scrape
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

# List of campuses for matching
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

# Predefined campus name mappings from manual inputs
CAMPUS_MAPPINGS = {
    "Alternative Learning Center": "ALC",
    "Travis County Juvenile Detention Center": "JJAEP (Juvenile Justice Educ Pro)"
}

def setup_google_sheets():
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).sheet1
    return sheet

def scroll_to_bottom(driver):
    for _ in range(3):  # Retry scrolling 3 times
        last_height = driver.execute_script("return document.body.scrollHeight")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

def save_to_sheets(employee_data, clear=False):
    sheet = setup_google_sheets()
    if clear:
        sheet.clear()
        headers = ["Name", "Job Title", "Campus", "Email", "Phone Number"]
        sheet.append_row(headers)
    print(f"{'Writing' if clear else 'Appending'} {len(employee_data)} records to Google Sheets...")
    sheet.append_rows(employee_data)
    print("Data successfully written to Google Sheets!")

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
        print(f"\nNo campus match found for '{campus_name}' (best match: '{best_match}', similarity: {best_ratio:.2f})")
        new_name = input(f"Please enter the correct campus name for '{campus_name}' (or press Enter to keep '{campus_name}'): ")
        return new_name.strip() if new_name.strip() else campus_name

def scrape_aisd_directory_selenium():
    chromium_path = "/usr/lib/chromium/chromium"
    chrome_options = Options()
    chrome_options.binary_location = chromium_path

    service = Service(executable_path="/usr/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_script_timeout(60)  # Increase script timeout to 60 seconds
    driver.get("https://www.austinisd.org/directory")
    
    wait = WebDriverWait(driver, 40)
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    time.sleep(10)

    employees = []

    try:
        for idx, letter in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
            if idx > 0 and idx % 5 == 0:
                print("Refreshing page to reset session...")
                driver.get("https://www.austinisd.org/directory")
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                time.sleep(10)

            letter_id = f"edit-letters-{letter.lower()}"
            print(f"Scraping letter: {letter}")
            
            letter_radio = wait.until(EC.presence_of_element_located((By.ID, letter_id)))
            print(f"Found radio button with ID: {letter_id}")
            
            for attempt in range(3):
                driver.execute_script("arguments[0].scrollIntoView(true);", letter_radio)
                driver.execute_script("arguments[0].click();", letter_radio)
                print(f"Clicked radio button for {letter} via JavaScript (attempt {attempt + 1})")
                
                time.sleep(5)
                is_selected = driver.execute_script("return arguments[0].checked;", letter_radio)
                table_loaded = len(driver.find_elements(By.XPATH, "//table[starts-with(@id, 'edit-directory')]")) > 0
                if is_selected or table_loaded:
                    break
                print(f"Selection check failed for {letter} on attempt {attempt + 1}")
                if attempt == 2:
                    raise Exception(f"Failed to select radio button for {letter} after 3 attempts")
                time.sleep(5)

            print(f"Confirmed {letter} is selected (checked: {is_selected}, table loaded: {table_loaded})")

            time.sleep(10)
            table = wait.until(EC.visibility_of_element_located((By.XPATH, "//table[starts-with(@id, 'edit-directory')]")))
            print(f"Table loaded with ID: {table.get_attribute('id')}")

            scroll_to_bottom(driver)
            rows = table.find_elements(By.TAG_NAME, "tr")[1:]

            for row in rows:
                try:
                    cols = row.find_elements(By.TAG_NAME, "td")  # Fixed: By.TAG_NAME
                    if len(cols) >= 4:
                        name = cols[0].text.strip()
                        job_title = cols[1].text.strip()

                        if job_title not in ALLOWED_JOB_TITLES:
                            continue

                        campus_raw = cols[2].find_element(By.TAG_NAME, "span").text.strip() if cols[2].find_elements(By.TAG_NAME, "span") else cols[2].text.strip()  # Fixed: By.TAG_NAME
                        campus = match_campus(campus_raw)
                        contact = cols[3].text.strip()
                        email_elem = cols[3].find_element(By.CLASS_NAME, "sr-only") if cols[3].find_elements(By.CLASS_NAME, "sr-only") else None
                        email = email_elem.text.strip() if email_elem else "N/A"
                        
                        phone_match = re.search(r"\d{3}-\d{3}-\d{4}", contact)
                        phone = phone_match.group(0) if phone_match else "N/A"

                        entry = [name, job_title, campus, email, phone]
                        if entry not in employees:
                            employees.append(entry)
                except Exception as e:
                    print(f"Error parsing row for {letter}: {str(e)}")

            print(f"Found {len(rows)} contacts for letter {letter}, added {len(employees) - (len(employees) - sum(1 for e in employees if e[0].startswith(letter)))} matching job titles")

            if (idx + 1) % 5 == 0:
                save_to_sheets(employees, clear=(idx == 4))
                employees = []

    except Exception as e:
        print(f"Error during scraping: {str(e)}")
        if employees:
            save_to_sheets(employees, clear=False)
        driver.quit()
        return employees
    
    driver.quit()
    if employees:
        save_to_sheets(employees, clear=False)
    return employees

def main():
    print("Scraping Austin ISD directory with Selenium (Last Name Alpha) for specific job titles...")
    employee_data = scrape_aisd_directory_selenium()
    if not employee_data:
        print("No additional data scraped in final batch.")
    
if __name__ == "__main__":
    main()
