import os
import sys
import time
import shutil
import traceback
import logging
import zipfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo  # Python 3.9+ time zone support

# Force system time zone to Asia/Kuala_Lumpur (required for GitHub Actions)
os.environ['TZ'] = 'Asia/Kuala_Lumpur'
time.tzset()

# Configure logging: logs will be written to a file in the download directory.
base_local_dir = os.path.join(os.getcwd(), "downloads")
current_month_folder = datetime.now().strftime("%B %Y")
base_download_dir = os.path.join(base_local_dir, current_month_folder)
os.makedirs(base_download_dir, exist_ok=True)

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
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

logger.info("Starting script...")

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import WebDriverException, TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

# Configure Chrome options for automatic downloading in headless mode
chrome_options = Options()
chrome_options.add_argument("--headless")  # Remove if you wish to see the browser
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

# Use fixed ChromeDriver version (adjust if needed)
DRIVER_PATH = ChromeDriverManager(driver_version="134.0.6998.88").install()

def init_driver():
    global driver, wait
    service = Service(DRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    wait = WebDriverWait(driver, 30)

init_driver()

def login_and_navigate():
    try:
        driver.get("https://gms.gasmalaysia.com/pltgtm/cmd.openseal?openSEAL_ck=ViewHome")
        website_username = os.environ.get("WEBSITE_USERNAME")
        website_password = os.environ.get("WEBSITE_PASSWORD")
        username_field = wait.until(EC.visibility_of_element_located((By.ID, "UserCtrl")))
        password_field = wait.until(EC.visibility_of_element_located((By.ID, "PwdCtrl")))
        username_field.send_keys(website_username)
        time.sleep(2)
        password_field.send_keys(website_password)
        time.sleep(2)
        login_button = wait.until(EC.element_to_be_clickable((By.NAME, "btnLogin")))
        login_button.click()
        time.sleep(2)
        scheduling_tab = wait.until(EC.presence_of_element_located((By.LINK_TEXT, "Scheduling")))
        ActionChains(driver).move_to_element(scheduling_tab).click().perform()
        time.sleep(2)
        scheduling_results_by_path = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Scheduling Results By Path")))
        scheduling_results_by_path.click()
        logger.info("Successfully navigated to Scheduling Results By Path")
    except Exception as e:
        logger.error(f"Login and navigation failed: {e}")
        raise

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

def wait_for_loading():
    logger.info("Waiting for page to load...")
    while True:
        try:
            loading_elements = driver.find_elements(By.CLASS_NAME, "k-loading-image")
            if not loading_elements:
                logger.info("Loading finished!")
                return
        except Exception:
            pass
        time.sleep(1)

# NEW: Wait for data to load in the results table using the provided HTML structure.
def wait_for_data(timeout=120):
    logger.info("Waiting for data to load in the results table...")
    end_time = time.time() + timeout
    # Use the provided HTML structure: rows inside the div with class "k-grid-content"
    data_xpath = "//div[contains(@class, 'k-grid-content')]//table//tbody//tr"
    while time.time() < end_time:
        try:
            rows = driver.find_elements(By.XPATH, data_xpath)
            # Assume that if at least 1 row exists, data is present.
            if len(rows) >= 1:
                logger.info("Data loaded in the results table!")
                return True
        except Exception as e:
            logger.error(f"Error while waiting for data: {e}")
        time.sleep(1)
    logger.warning("Timeout waiting for data to load in the results table.")
    return False

def wait_for_download(old_files):
    timeout = 120
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

def format_measurement_point_name(measurement_point):
    return f"PGB Daily Gas Movement - {measurement_point}.xlsx"

def select_dropdown(dropdown_index, option_text):
    for attempt in range(3):
        try:
            dropdown = wait.until(EC.element_to_be_clickable((By.XPATH, f"(//span[@class='k-input'])[{dropdown_index}]")))
            dropdown.click()
            time.sleep(1)
            option = wait.until(EC.presence_of_element_located((By.XPATH, f"//li[contains(text(), '{option_text}')]")))
            option.click()
            logger.info(f"Successfully selected: {option_text}")
            return
        except Exception:
            logger.info(f"Attempt {attempt+1}: Failed to select '{option_text}', retrying...")
            time.sleep(2)
    logger.error(f"Failed to select '{option_text}' after 3 attempts.")

def set_date_input(date_str, start=True):
    try:
        date_input_id = "startdatepicker" if start else "enddatepicker"
        date_input = driver.find_element(By.ID, date_input_id)
        date_input.clear()
        date_input.send_keys(date_str)
        logger.info(f"Set {'start' if start else 'end'} date to {date_str}")
    except Exception as e:
        logger.error(f"Failed to set {'start' if start else 'end'} date: {e}")

def click_export_button():
    try:
        export_button = wait.until(EC.element_to_be_clickable((By.ID, "delivery-export")))
        driver.execute_script("arguments[0].click();", export_button)
        logger.info("Export button clicked.")
        return True
    except Exception as e:
        logger.info(f"Export button not found or clickable: {e}. Skipping this network.")
        return False

# Calculate dynamic dates: start date = first day of current month, end date = tomorrow’s date.
malaysia_tz = ZoneInfo("Asia/Kuala_Lumpur")
now_in_malaysia = datetime.now(malaysia_tz)
base_start_date = now_in_malaysia.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
base_end_date = now_in_malaysia + timedelta(days=1)
start_date_str = base_start_date.strftime("%d/%m/%Y")
end_date_str = base_end_date.strftime("%d/%m/%Y")
logger.info(f"Dynamic date range (natural) - Start: {start_date_str}, End: {end_date_str}")

# Retrieve network names and process each network with measurement point(s)
downloaded_items = []
skipped_items = []
timeout_items = []

try:
    login_and_navigate()
    
    network_dropdown = wait.until(EC.element_to_be_clickable((By.XPATH, "(//span[@class='k-input'])[1]")))
    network_dropdown.click()
    time.sleep(2)
    network_options = driver.find_elements(By.XPATH, "//ul[@id='NetworkCode_listbox']/li")
    network_names = [option.text for option in network_options]
    network_dropdown.click()  # Close dropdown
    logger.info(f"Found {len(network_names)} networks: {network_names}")
except Exception as e:
    logger.error(traceback.format_exc())
    driver.quit()
    raise e

# Process each network – if measurement points exist then process each; else process network only.
for network in network_names:
    select_dropdown(1, network)
    time.sleep(2)
    try:
        measurement_point_dropdown = wait.until(EC.element_to_be_clickable((By.XPATH, "(//span[@class='k-input'])[2]")))
        measurement_point_dropdown.click()
        measurement_point_options = wait.until(EC.presence_of_all_elements_located(
            (By.XPATH, "//ul[@id='MeasurePointDropDownList_listbox']/li")))
        # Filter out empty entries
        measurement_point_names = [option.text.strip() for option in measurement_point_options if option.text.strip()]
        measurement_point_dropdown.click()  # collapse dropdown
        logger.info(f"For network '{network}', found {len(measurement_point_names)} measurement points: {measurement_point_names}")
    except Exception as e:
        logger.error(f"Error retrieving measurement points for network '{network}': {e}")
        measurement_point_names = []
    
    if measurement_point_names:
        for measurement_point in measurement_point_names:
            retries = 0
            max_retries = 3
            processed = False
            while not processed and retries < max_retries:
                try:
                    logger.info(f"Processing measurement point: {measurement_point} for network: {network} (Attempt {retries+1}/{max_retries})")
                    old_files = os.listdir(base_download_dir)
                    select_dropdown(2, measurement_point)
                    time.sleep(2)
                    set_date_input(start_date_str, start=True)
                    set_date_input(end_date_str, start=False)
                    search_button = wait.until(EC.element_to_be_clickable((By.ID, "search")))
                    search_button.click()
                    wait_for_loading()
                    if not wait_for_data():
                        logger.warning(f"No data loaded for measurement point '{measurement_point}' of network '{network}'.")
                        skipped_items.append(f"{network} - {measurement_point}")
                        processed = True
                        break
                    if not click_export_button():
                        logger.info(f"Skipping measurement point '{measurement_point}' for network '{network}' due to no export button.")
                        skipped_items.append(f"{network} - {measurement_point}")
                        processed = True
                        break
                    downloaded_file = wait_for_download(old_files)
                    if downloaded_file:
                        new_file_path = os.path.join(base_download_dir, format_measurement_point_name(measurement_point))
                        shutil.move(downloaded_file, new_file_path)
                        logger.info(f"Renamed '{downloaded_file}' to '{new_file_path}'")
                        downloaded_items.append(f"{network} - {measurement_point}")
                    else:
                        logger.info(f"No file downloaded for measurement point '{measurement_point}' of network '{network}'.")
                        skipped_items.append(f"{network} - {measurement_point}")
                    time.sleep(5)
                    processed = True
                except WebDriverException as wde:
                    retries += 1
                    logger.warning(f"WebDriverException for measurement point '{measurement_point}' of network '{network}': {wde}. Reinitializing driver and retrying...")
                    reinitialize_driver()
                except Exception as e:
                    logger.error(f"Exception for measurement point '{measurement_point}' of network '{network}': {e}. Skipping this combination.")
                    skipped_items.append(f"{network} - {measurement_point}")
                    processed = True
    else:
        retries = 0
        max_retries = 3
        processed = False
        while not processed and retries < max_retries:
            try:
                logger.info(f"Processing network: {network} with no measurement point (Attempt {retries+1}/{max_retries})")
                old_files = os.listdir(base_download_dir)
                time.sleep(2)
                set_date_input(start_date_str, start=True)
                set_date_input
