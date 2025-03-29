# Selenium GMS PGB Daily Gas Movement Downloader

This project automates the process of downloading and organizing data from the Gas Malaysia website’s "PGB Daily Gas Movement" section. The Python script uses Selenium WebDriver to log in, navigate dynamic dropdowns, set a dynamic date range, download Excel files for various networks and measurement points, rename the files appropriately, and finally compress them into a ZIP archive for artifact retrieval.

## Features

- **Automated Login and Navigation**  
  Automatically logs into the Gas Malaysia website and navigates to the "PGB Daily Gas Movement" page.

- **Dynamic Dropdown Handling**  
  Retrieves network and measurement point options from dynamically loaded dropdowns. The script uses multiple strategies (including ActionChains, JavaScript clicks, scrolling into view, and retries) to ensure robust selection even with asynchronous loading issues.

- **Dynamic Date Range Setting**  
  Automatically sets the start date as the first day of the current month and the end date as tomorrow’s date.

- **File Download and Renaming**  
  Downloads Excel files, renames them according to the measurement point (or network) for easy identification, and organizes them in monthly folders.

- **Artifact Compression**  
  Compresses the downloaded files into a ZIP archive, which can be uploaded as an artifact in CI/CD pipelines such as GitHub Actions.

- **Headless Operation**  
  Designed to run in headless mode, making it ideal for continuous integration environments.
