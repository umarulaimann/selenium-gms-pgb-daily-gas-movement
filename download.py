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
base_local_dir = r"C:\Users\umarul\OneDrive - Gas Malaysia Berhad\GMS Manual\PGB Daily Gas Movement (Billing)"
current_month_folder = datetime.now().strftime("%B %Y")
# Adjust folder structure as needed.
base_download_dir = os.path.join(base_local_dir, "PGB Daily Gas Movement", f"3. March {datetime.now().year} - Test Umarul")
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
logger = logging.getLogger("CVDownloader")
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
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

# Configure Chrome options for automatic downloading (GUI mode enabled)
chrome_options = Options()
# Uncomment the next line if you want to run headless
# chrome_options.add_argument("--headless")
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

FIXED_CHROME_DRIVER_VERSION = "134.0.6998.88"
DRIVER_PATH = ChromeDriverManager(driver_version=FIXED_CHROME_DRIVER_VERSION).install()

def init_driver():
    global driver, wait
    service = Service(DRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    wait = WebDriverWait(driver, 30)

init_driver()

def login_and_navigate():
    try:
        driver.get("https://gms.gasmalaysia.com/pltgtm/cmd.openseal?openSEAL_ck=ViewHome")
        username_field = wait.until(EC.visibility_of_element_located((By.ID, "UserCtrl")))
        password_field = wait.until(EC.visibility_of_element_located((By.ID, "PwdCtrl")))
        username_field.send_keys("pltadmin")
        time.sleep(2)
        password_field.send_keys("pltadmin@2020")
        time.sleep(2)
        login_button = wait.until(EC.element_to_be_clickable((By.NAME, "btnLogin")))
        login_button.click()
        time.sleep(2)
        certification_tab = wait.until(EC.presence_of_element_located((By.LINK_TEXT, "Certification")))
        ActionChains(driver).move_to_element(certification_tab).click().perform()
        time.sleep(2)
        pgb_daily_gas_movement = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "PGB Daily Gas Movement")))
        pgb_daily_gas_movement.click()
        logger.info("Navigated to PGB Daily Gas Movement")
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

def wait_for_loading(timeout=3600, network_name=""):
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

# Wait for data to load in the results table using the provided HTML structure.
def wait_for_data(timeout=120):
    logger.info("Waiting for data to load in the results table...")
    end_time = time.time() + timeout
    data_xpath = "//div[contains(@class, 'k-grid-content')]//table//tbody//tr"
    while time.time() < end_time:
        try:
            rows = driver.find_elements(By.XPATH, data_xpath)
            if len(rows) >= 1:
                logger.info("Data loaded in the results table!")
                return True
        except Exception as e:
            logger.error(f"Error while waiting for data: {e}")
        time.sleep(1)
    logger.warning("Timeout waiting for data to load in the results table.")
    return False

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

def format_measurement_point_name(measurement_point):
    return f"PGB Daily Gas Movement - {measurement_point}.xlsx"

def select_dropdown(dropdown_index, option_text):
    for attempt in range(3):
        try:
            dropdown = wait.until(EC.element_to_be_clickable(
                (By.XPATH, f"(//span[@class='k-input'])[{dropdown_index}]")))
            dropdown.click()
            time.sleep(1)
            option = wait.until(EC.presence_of_element_located(
                (By.XPATH, f"//li[contains(text(), '{option_text}')]")))
            option.click()
            logger.info(f"Successfully selected: {option_text}")
            return
        except Exception:
            logger.info(f"Attempt {attempt+1}: Failed to select '{option_text}', retrying...")
            time.sleep(2)
    logger.error(f"Failed to select '{option_text}' after 3 attempts.")

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

def click_export_button():
    try:
        export_button = wait.until(EC.element_to_be_clickable((By.ID, "PGBdailygasmovement-export")))
        driver.execute_script("arguments[0].click();", export_button)
        logger.info("Export button clicked.")
        return True
    except Exception as e:
        logger.warning(f"Export button not found or clickable: {e}. Skipping this network.")
        return False

# Calculate dynamic dates: start date = first day of current month, end date = tomorrow’s date.
current_date = datetime.now()
start_date_str = f"01/{current_date.month:02d}/{current_date.year}"
end_date = current_date + timedelta(days=1)
end_date_str = f"{end_date.day:02d}/{end_date.month:02d}/{end_date.year}"
logger.info(f"Dynamic date range - Start: {start_date_str}, End: {end_date_str}")

try:
    login_and_navigate()
except Exception as e:
    logger.error("Initial login failed. Exiting.")
    driver.quit()
    raise e

# Retrieve network names.
try:
    network_dropdown = wait.until(EC.element_to_be_clickable((By.XPATH, "(//span[@class='k-input'])[1]")))
    network_dropdown.click()
    time.sleep(2)
    network_options = driver.find_elements(By.XPATH, "//ul[@id='NetworkCode_listbox']/li")
    network_names = [option.text for option in network_options]
    network_dropdown.click()  # Collapse dropdown.
    logger.info(f"Found {len(network_names)} networks: {network_names}")
except Exception as e:
    logger.error(traceback.format_exc())
    driver.quit()
    raise e

downloaded_items = []
skipped_items = []
timeout_networks = []

# Process each network – if measurement points exist, process each; otherwise, process the network.
for network in network_names:
    select_dropdown(1, network)
    time.sleep(2)
    try:
        # Retrieve measurement point options using the correct XPath.
        measurement_point_dropdown = wait.until(EC.element_to_be_clickable((By.XPATH, "(//span[@class='k-input'])[2]")))
        measurement_point_dropdown.click()
        measurement_point_options = wait.until(EC.presence_of_all_elements_located(
            (By.XPATH, "//ul[@id='MeasurePointDropDownList_listbox']/li")))
        measurement_point_names = [option.text.strip() for option in measurement_point_options if option.text.strip()]
        measurement_point_dropdown.click()  # Collapse dropdown.
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
                    wait_for_loading(timeout=300, network_name=network)
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
                set_date_input(end_date_str, start=False)
                search_button = wait.until(EC.element_to_be_clickable((By.ID, "search")))
                search_button.click()
                wait_for_loading(timeout=300, network_name=network)
                if not click_export_button():
                    logger.info(f"Skipping network '{network}' due to no export button.")
                    skipped_items.append(network)
                    processed = True
                    break
                downloaded_file = wait_for_download(old_files)
                if downloaded_file:
                    new_file_path = os.path.join(base_download_dir, f"PGB Daily Gas Movement - {network}.xlsx")
                    shutil.move(downloaded_file, new_file_path)
                    logger.info(f"Renamed '{downloaded_file}' to '{new_file_path}'")
                    downloaded_items.append(network)
                else:
                    logger.info(f"No file downloaded for network '{network}'.")
                    skipped_items.append(network)
                time.sleep(5)
                processed = True
            except WebDriverException as wde:
                retries += 1
                logger.warning(f"WebDriverException for network '{network}': {wde}. Reinitializing driver and retrying...")
                reinitialize_driver()
            except Exception as e:
                logger.error(f"Exception for network '{network}': {e}. Skipping network.")
                skipped_items.append(network)
                processed = True

logger.info("\n=== Summary ===")
logger.info(f"Total networks processed: {len(network_names)}")
logger.info(f"Downloaded items count: {len(downloaded_items)}")
logger.info(f"Skipped items count: {len(skipped_items)}")
if downloaded_items:
    logger.info("Downloaded measurement points:")
    for item in downloaded_items:
        if " - " in item:
            mp = item.split(" - ")[1]
            logger.info(f" - {mp}")
        else:
            logger.info(f" - {item}")
else:
    logger.info("No items were downloaded.")
if skipped_items:
    logger.info("Skipped items:")
    for item in skipped_items:
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
logger.info("Artifact is ready.")
