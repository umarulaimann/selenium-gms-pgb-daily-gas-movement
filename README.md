# selenium-gms-pgb-daily-gas-movement
This repository is the automation for scheduled download selenium GMS PGB Daily Gas Movement

Selenium GMS PGB Daily Gas Movement Downloader
This project automates the process of downloading and organizing data from the Gas Malaysia website’s "PGB Daily Gas Movement" section. The Python script uses Selenium WebDriver to log in, navigate through dynamic dropdowns, set a dynamic date range, download Excel files for various networks and measurement points, rename the files appropriately, and finally compress them into a ZIP archive for easy artifact retrieval.

Features
Automated Login and Navigation
Automatically logs into the Gas Malaysia website and navigates to the "PGB Daily Gas Movement" page.

Dynamic Dropdown Handling
Retrieves network and measurement point options from dynamically loaded dropdowns. Incorporates retries, scrolling, and JavaScript click fallbacks to ensure robust selection—even when facing asynchronous loading issues.

Dynamic Date Range Setting
Automatically sets the start date as the first day of the current month and the end date as tomorrow’s date.

File Download and Renaming
Downloads Excel files, renames them according to the measurement point (or network) for easy identification, and organizes them in monthly folders.

Artifact Compression
Compresses the downloaded files into a ZIP archive, which can be uploaded as an artifact in CI/CD pipelines such as GitHub Actions.

Headless Operation
Designed to run in headless mode, making it ideal for continuous integration environments.

Prerequisites
Python 3.9+

Google Chrome (or a compatible Chromium-based browser)

pip (Python package installer)

Dependencies
Selenium

webdriver-manager

You can install these dependencies with:

bash
Copy
pip install selenium webdriver-manager
Installation
Clone the repository:

bash
Copy
git clone <repository_url>
cd <repository_folder>
Install the required Python packages:

bash
Copy
pip install -r requirements.txt
(Ensure that your requirements.txt includes selenium and webdriver-manager.)

Configuration
Credentials:
The script uses environment variables WEBSITE_USERNAME and WEBSITE_PASSWORD for authentication. For local testing, default credentials are set in the script. In production or CI/CD (e.g., GitHub Actions), store your credentials securely as repository secrets.

Date Range:
The date range is dynamically set in the script:

Start Date: The first day of the current month.

End Date: Tomorrow’s date.

Usage
To run the script locally, execute:

bash
Copy
python download.py
The script will:

Log in to the website.

Navigate to the "PGB Daily Gas Movement" page.

Loop through all available networks and measurement points.

Download and rename the corresponding Excel files.

Compress the downloaded files into a ZIP archive for easy retrieval.

GitHub Actions Integration
Below is an example workflow file (.github/workflows/main.yml) that sets up a CI job to run the script automatically:

yaml
Copy
name: Run Selenium Script

on:
  push:
    branches: [ main ]
  schedule:
    - cron: '0 0 * * *'  # Runs every day at midnight (UTC)

jobs:
  run-selenium:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install selenium webdriver-manager

      - name: Run Selenium Script
        env:
          WEBSITE_USERNAME: ${{ secrets.WEBSITE_USERNAME }}
          WEBSITE_PASSWORD: ${{ secrets.WEBSITE_PASSWORD }}
        run: |
          python download.py

      - name: Upload Downloads Artifact
        uses: actions/upload-artifact@v3
        with:
          name: downloads
          path: downloads/
Troubleshooting
Dropdown Selection Issues:
If options like "Batu Tiga CGS (Glenmarie)" aren’t consistently selected, consider increasing the wait time after clicking the dropdown. For example, in the select_dropdown() function, you might change:

python
Copy
dropdown.click()
time.sleep(1)
to:

python
Copy
dropdown.click()
time.sleep(2)  # or time.sleep(3) if needed
Asynchronous Loading:
The script employs retries and explicit waits to handle dynamic content. If issues persist, consider increasing the overall timeout durations.

License
[Specify your project license here, e.g., MIT License]

Acknowledgments
The Selenium and webdriver-manager communities for their excellent tools.

The GitHub Actions community for integration examples and support.
