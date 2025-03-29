#!/usr/bin/env python3
import os
import sys
import time
import shutil
import traceback
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo  # For Python 3.9+ time zone support
import zipfile

# ---------------------------------------------------------------------------
# Set system time zone to Asia/Kuala_Lumpur (for Linux/GitHub Actions)
os.environ['TZ'] = 'Asia/Kuala_Lumpur'
time.tzset()

# ---------------------------------------------------------------------------
# Configure directories for downloads and logs
base_local_dir = os.path.join(os.getcwd(), "downloads")
current_month_folder = datetime.now().strftime("%B %Y")
base_download_dir = os.path.join(base_local_dir, current_month_folder)
os.makedirs(base_download_dir, exist_ok=True)

# Setup logging: logs will be written to a file in the download directory.
log_filename = os.path.join(
    base_download_dir,
    f"Tracking Networks Downloaded and Skipped [{datetime.now().strftime('%Y-%m-%d')}].txt"
)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename=log_filename,
    filemode='w'
)
logger = logging.getLogger()
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

logger.info("Starting script...")

# ---------------------------------------------------------------------------
# Selenium and WebDriver imports
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import WebDriverException, TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

# ---------------------------------------------------------------------------
# Configure Chrome options for headless mode (GitHub Actions)
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--start-maximized")
chrome_options.add_argument("--lang=ms-MY")

chrome_prefs = {
    "download.default_directory": base_download_dir,
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
    "safebrowsing.enabled": True
}
chrome_options.add_experimental_option("prefs", chrome_prefs)

# ---------------------------------------------------------------------------
# Initialize WebDriver
def init_driver():
    global driver, wait
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    wait = WebDriverWait(driver, 30)

init_driver()

# ---------------------------------------------------------------------------
# Verification function (allows partial matching)
def verify_selection(dropdown_index, expected_text):
    try:
        dropdown = wait.until(EC.visibility_of_element_located((By.XPATH, f"(//span[@class='k-input'])[{dropdown_index}]")))
        current = dropdown.text.strip()
        # Check if the expected text is a substring of the current text.
        if expected_text in current:
            return True
        else:
            logger.warning(f"Verification failed: Expected '{expected_text}' to be in '{current}'")
            return False
    except Exception as e:
        logger.error(f"Error verifying selection: {e}")
        return False

# ---------------------------------------------------------------------------
# Utility function to select an option from a dropdown given its index and text.
def select_dropdown(dropdown_index, option_text):
    for attempt in range(3):
        try:
            dropdown = wait.until(EC.element_to_be_clickable((By.XPATH, f"(//span[@class='k-input'])[{dropdown_index}]")))
            dropdown.click()
            time.sleep(1)
            option = wait.until(EC.presence_of_element_located(
                (By.XPATH, f"//ul[contains(@id, 'listbox')]/li[contains(text(), '{option_text}')]")
            ))
            option.click()
            time.sleep(1)
            if verify_selection(dropdown_index, option_text):
                logger.info(f"Successfully selected: {option_text}")
                return
        except Exception:
            logger.info(f"Attempt {attempt+1}: Failed to select '{option_text}', retrying...")
            time.sleep(2)
    logger.error(f"Failed to select '{option_text}' after 3 attempts.")

# ---------------------------------------------------------------------------
# Utility function to set date inputs.
def set_date_input(date_str, start=True):
    try:
        date_input_id = "DataProviderDatePicker" if start else "EndDateDatePicker"
        date_input = wait.until(EC.visibility_of_element_located((By.ID, date_input_id)))
        time.sleep(1)
        date_input.clear()
        date_input.send_keys(date_str)
        logger.info(f"Set {'start' if start else 'end'} date to {date_str}")
    except Exception as e:
        logger.error(f"Failed to set {'start' if start else 'end'} date: {e}")

# ---------------------------------------------------------------------------
# Utility function to click the export button.
def click_export_button():
    try:
        export_button = wait.until(EC.element_to_be_clickable((By.ID, "PGBdailygasmovement-export")))
        driver.execute_script("arguments[0].click();", export_button)
        logger.info("Export button clicked.")
        return True
    except Exception as e:
        logger.warning(f"Export button not found or clickable: {e}. Skipping this network.")
        return False

# ---------------------------------------------------------------------------
# Wait for the page loading spinner to disappear.
def wait_for_loading(timeout=300, network_name=""):
    logger.info(f"Waiting for page to load for network '{network_name}'...")
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            loading_elements = driver.find_elements(By.CLASS_NAME, "k-loading-image")
            if not loading_elements:
                logger.info("Page loading finished. Proceeding to export.")
                return True
        except Exception:
            pass
        time.sleep(1)
    logger.warning(f"Timeout waiting for page to load for network '{network_name}'.")
    return False

# ---------------------------------------------------------------------------
# Wait for the Excel file to appear in the download folder.
def wait_for_download(old_files, timeout=120):
    end_time = time.time() + timeout
    while time.time() < end_time:
        files = [f for f in os.listdir(base_download_dir) if f.endswith(".xlsx")]
        new_files = list(set(files) - set(old_files))
        if new_files:
            downloaded_file = os.path.join(base_download_dir, new_files[0])
            logger.info(f"Detected downloaded file: {downloaded_file}")
            return downloaded_file
        time.sleep(2)
    logger.info("No downloaded file detected.")
    return None

# ---------------------------------------------------------------------------
# Utility function to rename downloaded files for measurement points.
def format_measurement_point_name(measurement_point):
    return f"PGB Daily Gas Movement - {measurement_point}.xlsx"

# ---------------------------------------------------------------------------
# Retrieve measurement point options for the currently selected network.
def get_measurement_points():
    try:
        measurement_point_dropdown = wait.until(EC.element_to_be_clickable((By.XPATH, "(//span[@class='k-input'])[2]")))
        measurement_point_dropdown.click()
        time.sleep(2)
        measurement_point_options = wait.until(
            EC.presence_of_all_elements_located((By.XPATH, "//ul[contains(@id, 'MeasurePointDropDownList_listbox')]/li"))
        )
        measurement_point_names = [option.text.strip() for option in measurement_point_options if option.text.strip()]
        measurement_point_dropdown.click()  # collapse dropdown
        return measurement_point_names
    except Exception as e:
        logger.error(f"Error retrieving measurement points: {e}")
        return []

# ---------------------------------------------------------------------------
# Login and navigate to "PGB Daily Gas Movement".
def login_and_navigate():
    try:
        driver.get("https://gms.gasmalaysia.com/pltgtm/cmd.openseal?openSEAL_ck=ViewHome")
        website_username = os.environ.get("WEBSITE_USERNAME", "pltadmin")
        website_password = os.environ.get("WEBSITE_PASSWORD", "pltadmin@2020")
        username_field = wait.until(EC.visibility_of_element_located((By.ID, "UserCtrl")))
        password_field = wait.until(EC.visibility_of_element_located((By.ID, "PwdCtrl")))
        username_field.send_keys(website_username)
        time.sleep(2)
        password_field.send_keys(website_password)
        time.sleep(2)
        login_button = wait.until(EC.element_to_be_clickable((By.NAME, "btnLogin")))
        login_button.click()
        time.sleep(2)
        # Navigate via Certification tab to PGB Daily Gas Movement.
        certification_tab = wait.until(EC.presence_of_element_located((By.LINK_TEXT, "Certification")))
        ActionChains(driver).move_to_element(certification_tab).click().perform()
        time.sleep(2)
        pgb_daily_gas_movement = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "PGB Daily Gas Movement")))
        pgb_daily_gas_movement.click()
        logger.info("Navigated to PGB Daily Gas Movement")
    except Exception as e:
        logger.error(f"Login and navigation failed: {e}")
        raise

# ---------------------------------------------------------------------------
# Reinitialize driver if needed.
def reinitialize_driver():
    global driver, wait
    logger.info("Browser closed unexpectedly. Reinitializing driver...")
    try:
        driver.quit()
    except Exception:
        pass
    init_driver()
    try:
        login_and_navigate()
        logger.info("Driver reinitialized and navigated back successfully")
    except Exception as e:
        logger.error(f"Failed to reinitialize driver: {e}")

# ---------------------------------------------------------------------------
# Calculate dynamic date range using Malaysia time zone.
malaysia_tz = ZoneInfo("Asia/Kuala_Lumpur")
now_in_malaysia = datetime.now(malaysia_tz)
start_date_str = f"01/{now_in_malaysia.month:02d}/{now_in_malaysia.year}"
end_date = now_in_malaysia + timedelta(days=1)
end_date_str = f"{end_date.day:02d}/{end_date.month:02d}/{end_date.year}"
logger.info(f"Dynamic date range - Start: {start_date_str}, End: {end_date_str}")

# ---------------------------------------------------------------------------
# Begin by logging in and navigating to the target page.
try:
    login_and_navigate()
except Exception as e:
    logger.error("Initial login failed. Exiting.")
    driver.quit()
    raise e

# Retrieve network names from the network dropdown.
try:
    network_dropdown = wait.until(EC.element_to_be_clickable((By.XPATH, "(//span[@class='k-input'])[1]")))
    network_dropdown.click()
    time.sleep(2)
    network_options = driver.find_elements(By.XPATH, "//ul[@id='NetworkCode_listbox']/li")
    network_names = [option.text for option in network_options]
    network_dropdown.click()  # collapse dropdown
    logger.info(f"Found {len(network_names)} networks: {network_names}")
except Exception as e:
    logger.error(traceback.format_exc())
    driver.quit()
    raise e

downloaded_networks = []
skipped_networks = []
timeout_networks = []

# Process each network by retrieving its measurement points and then processing each one.
for network in network_names:
    select_dropdown(1, network)
    time.sleep(2)
    measurement_point_names = get_measurement_points()
    logger.info(f"For network '{network}', found {len(measurement_point_names)} measurement points: {measurement_point_names}")
    
    if not measurement_point_names:
        logger.error(f"Measurement points not found for network '{network}'. Skipping...")
        skipped_networks.append(network)
        continue
    
    for measurement_point in measurement_point_names:
        network_retries = 0
        max_network_retries = 3
        processed = False
        while not processed and network_retries < max_network_retries:
            try:
                logger.info(f"Processing measurement point: {measurement_point} for network: {network} (Attempt {network_retries+1}/{max_network_retries})")
                old_files = os.listdir(base_download_dir)
                # Select the measurement point explicitly.
                select_dropdown(2, measurement_point)
                time.sleep(2)
                set_date_input(start_date_str, start=True)
                set_date_input(end_date_str, start=False)
                search_button = wait.until(EC.element_to_be_clickable((By.ID, "search")))
                search_button.click()
                if not wait_for_loading(timeout=300, network_name=network):
                    timeout_networks.append(f"{network} - {measurement_point}")
                if not click_export_button():
                    logger.info(f"Skipping measurement point '{measurement_point}' for network '{network}' due to no export button.")
                    skipped_networks.append(f"{network} - {measurement_point}")
                    processed = True
                    break
                downloaded_file = wait_for_download(old_files)
                if downloaded_file:
                    new_file_path = os.path.join(base_download_dir, format_measurement_point_name(measurement_point))
                    shutil.move(downloaded_file, new_file_path)
                    logger.info(f"Renamed '{downloaded_file}' to '{new_file_path}'")
                    downloaded_networks.append(f"{measurement_point}")
                else:
                    logger.info(f"No file downloaded for measurement point '{measurement_point}' of network '{network}'.")
                    skipped_networks.append(f"{network} - {measurement_point}")
                time.sleep(5)
                processed = True
            except WebDriverException as wde:
                network_retries += 1
                logger.warning(f"WebDriverException for measurement point '{measurement_point}' of network '{network}': {wde}. Reinitializing driver and retrying...")
                reinitialize_driver()
            except Exception as e:
                logger.error(f"Exception for measurement point '{measurement_point}' of network '{network}': {e}. Skipping this combination.")
                skipped_networks.append(f"{network} - {measurement_point}")
                processed = True

# ---------------------------------------------------------------------------
# Log summary of processing.
logger.info("\n=== Summary ===")
logger.info(f"Total networks processed: {len(network_names)}")
logger.info(f"Downloaded items count: {len(downloaded_networks)}")
logger.info(f"Skipped items count: {len(skipped_networks)}")
logger.info(f"Items with page load timeout: {len(timeout_networks)}")

if downloaded_networks:
    logger.info("Downloaded measurement points:")
    for item in downloaded_networks:
        logger.info(f" - {item}")
else:
    logger.info("No items were downloaded.")

if skipped_networks:
    logger.info("Skipped items:")
    for item in skipped_networks:
        logger.info(f" - {item}")
else:
    logger.info("All items were downloaded successfully.")

if timeout_networks:
    logger.info("Items that timed out on page load:")
    for item in timeout_networks:
        logger.info(f" - {item}")
else:
    logger.info("No items timed out on page load.")

driver.quit()
logger.info("Driver quit. Script finished.")

# ---------------------------------------------------------------------------
# Compress downloaded files for GitHub Actions Artifact.
def compress_downloads_dir(directory, zip_filename):
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, start=directory)
                zipf.write(file_path, arcname=arcname)
    logger.info(f"Compressed files into {zip_filename}")

zip_filename = os.path.join(base_local_dir, f"{current_month_folder}.zip")
compress_downloads_dir(base_download_dir, zip_filename)
logger.info("Artifact is ready. Use GitHub Actions 'upload-artifact' step to save the ZIP file.")
