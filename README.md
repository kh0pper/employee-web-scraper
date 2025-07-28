# employee-directory-web-scraper
Selenium based Python web scraper to create an employee directory in Google Sheets

Update System:
sudo apt update && sudo apt upgrade -y
Ensures your system is up to date.

Install Chromium and ChromeDriver:
sudo apt install -y chromium-browser chromium-chromedriver
Installs Chromium and ChromeDriver. Verify paths: /usr/lib/chromium/chromium and /usr/bin/chromedriver.

Install Python and Dependencies:
sudo apt install -y python3 python3-pip
pip3 install selenium gspread oauth2client
Installs Python 3, pip, and libraries for Selenium and Google Sheets.

Create Working Directory:
mkdir -p ~/aisd_scraper
cd ~/aisd_scraper
Sets up your project folder.

Step 2: Set Up Google Cloud API and Service Account

Go to Google Cloud Console:
Open a browser: https://console.cloud.google.com/
Sign in with your Google account (the one you want tied to this project).

Create a Project:
Click the project dropdown at the top left, then "New Project."
Name it (e.g., "AISD-Employees-Scraper").
Click "Create." Note the project ID —it’ll appear in your JSON file.
Wait a few seconds, then select this project from the dropdown.

Enable Google Sheets API:
Go to "APIs & Services" > "Library" in the left menu.
Search for "Google Sheets API."
Click it, then "Enable." Wait a minute for activation.

Enable Google Drive API:
In "Library," search for "Google Drive API."
Click it, then "Enable." (Required for gspread to access sheets.) Wait another minute.

Create a Service Account:
Go to "IAM & Admin" > "Service Accounts."
Click "Create Service Account."
Name it (e.g., "aisd-scraper"), add a description (optional), then click "Create and Continue."
Grant it "Editor" role (under "Role" dropdown), then click "Continue."
Skip optional steps, click "Done."
Find your new service account in the list.

Download the JSON Key File:
Click your service account, go to "Keys" tab.
Click "Add Key" > "Create new key" > "JSON."
Download the file.

Move it to your Linux system:
mv ~/Downloads/credentials.json ~/path-to-credentials.json
chmod 600 ~/aisd-employees-scraper-3b5aecf6c6c0.json
Replace your existing file if prompted, ensuring the path matches the script.

Create and Share a Google Sheet:
Go to Google Drive (https://drive.google.com).
Click "New" > "Google Sheets," name it "AISD Employees."
Click "Share," enter the service account email.
Set as "Editor," click "Share."

Wait for Propagation:
Wait 5-10 minutes after enabling APIs and sharing the sheet for Google’s systems to sync.
Step 3: The Python Script
Save the contents of aisd-employee-scraper.py in ~/aisd_scraper:

    
Step 4: Save and Run the Script

Save the Script:
cd ~/aisd_scraper
nano aisd-employee-scraper.py
Paste the code, save (Ctrl+O, Enter), exit (Ctrl+X).

Run It:
python3 aisd-employee-scraper.py
Wait 5-10 minutes after enabling APIs and sharing the sheet before running. Expect 30-60 minutes total runtime.

Step 5: Key Script Explanations

Reliable Clicking:
Retries: for attempt in range(3) tries clicking 3 times with 5-second delays, checking both checked and table presence (table_loaded). This handles AJAX delays or attribute quirks.
Why: The site’s radio buttons might not update checked instantly, but table loading confirms success.

Full Table Loading:
Scrolling: scroll_to_bottom runs up to 3 times, waiting 3 seconds each, to load all entries (e.g., 623 for A).
Why: The directory uses dynamic loading—scrolling ensures all rows are captured.

Incremental Saving:
Logic: if (idx + 1) % 5 == 0 triggers save_to_sheets every 5 letters, clearing only for A-E (idx == 4).
Why: Prevents data loss if the script fails mid-run and manages memory.

Error Handling:
Try-Except: Catches failures (e.g., table not loading) and saves collected data before quitting.
Why: Ensures partial results are preserved (e.g., if it stops at "U").

Step 6: Verify Results

Output: Look for "Found 623 contacts for A, added 46 matches" and batch writes (e.g., "Writing 221 records..." after E).
Google Sheets: Check "AISD Employees" for ~842 entries across 6 batches (A-E: 221, F-J: 173, K-O: 176, P-T: 213, U-Y: 59, Z: 7).

Troubleshooting: If you get an API error (e.g., 403), verify API enablement, sheet sharing, and JSON file path. Rerun after 10 minutes.
Why This Works First Try
Comprehensive Setup: Includes project creation, API enablement (Sheets and Drive), and service account steps, avoiding auth pitfalls.
Specific Requirements: Details URL, job titles, columns, batching, and environment, reducing guesswork.
