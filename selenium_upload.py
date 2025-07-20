import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# --- اطلاعات از سکرت‌های گیت‌هاب خوانده می‌شود ---
USERNAME = os.environ.get("APARAT_USERNAME")
PASSWORD = os.environ.get("APARAT_PASSWORD")

# --- تنظیمات ویدیو ---
VIDEO_URL = "https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/360/Big_Buck_Bunny_360_10s_1MB.mp4"
LOCAL_VIDEO_FILENAME = "video_to_upload.mp4"
VIDEO_TITLE = "ویدیوی گیم پلی (ورود هوشمند)"
VIDEO_DESCRIPTION = "یک ویدیوی جدید از بازی با اسکریپت کامل و ورود هوشمند."
VIDEO_TAGS = ["گیم", "بازی آنلاین", "گیم پلی جدید"]
VIDEO_CATEGORY = "ویدئو گیم" 

# --- ثابت‌های سلنیوم ---
WAIT_TIMEOUT = 45 # seconds

def download_video(url, filename):
    """Downloads a video from a given URL and saves it locally."""
    print("-> Downloading video...")
    try:
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print("-> ✅ Video downloaded successfully.")
        return os.path.abspath(filename)
    except requests.exceptions.RequestException as e:
        print(f"-> ❌ Error downloading video: {e}")
        return None

def smart_login(driver, wait, username, password):
    """
    Handles the login process, including the 'device limit' error page, by automatically
    logging out one device and retrying.
    """
    MAX_LOGIN_ATTEMPTS = 5 # Tries to log in up to 5 times
    for attempt in range(MAX_LOGIN_ATTEMPTS):
        print(f"-> Starting login attempt {attempt + 1}/{MAX_LOGIN_ATTEMPTS}...")
        driver.get("https://www.aparat.com/signin")
        
        try:
            # --- Step 1: Enter Credentials ---
            wait.until(EC.visibility_of_element_located((By.ID, "username"))).send_keys(username)
            driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

            wait.until(EC.visibility_of_element_located((By.ID, "password"))).send_keys(password)
            driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

            # --- Step 2: Check Login Outcome ---
            # Wait up to 15 seconds to see if we land on the dashboard (success) or the device limit page (error)
            outcome_wait = WebDriverWait(driver, 15)
            outcome_wait.until(EC.any_of(
                EC.url_contains("dashboard"),
                EC.presence_of_element_located((By.XPATH, "//button[text()='خروج']")) # Checks for the logout button on the error page
            ))

            # --- Step 3: Handle Outcome ---
            if "dashboard" in driver.current_url:
                print("-> ✅ Login successful!")
                return # Exit the function on success

            else:
                print("-> Device limit page detected. Attempting to log out one session...")
                # Find the *first* logout button on the page and click it
                first_logout_button = wait.until(EC.element_to_be_clickable((By.XPATH, "(//button[text()='خروج'])[1]")))
                driver.execute_script("arguments[0].click();", first_logout_button)
                
                print("-> Clicked logout on one session. Retrying login...")
                time.sleep(3) # Wait a bit for the page to refresh
                continue # This will start the next iteration of the for loop

        except TimeoutException:
            driver.save_screenshot(f'error_login_attempt_{attempt + 1}.png')
            if attempt < MAX_LOGIN_ATTEMPTS - 1:
                print("-> Login attempt failed (timeout). Retrying...")
                continue
            else:
                raise Exception("Login failed after multiple retries. Neither dashboard nor device limit page was detected.")

    raise Exception("Could not log in after all attempts.")


# --- Selenium Setup ---
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

driver = webdriver.Chrome(options=chrome_options)
wait = WebDriverWait(driver, WAIT_TIMEOUT)

try:
    if not all([USERNAME, PASSWORD]):
        raise ValueError("Secrets for APARAT_USERNAME or APARAT_PASSWORD are not set.")

    video_full_path = download_video(VIDEO_URL, LOCAL_VIDEO_FILENAME)
    if not video_full_path:
        raise Exception("Failed to download the video file.")

    # --- Use the new smart login function ---
    smart_login(driver, wait, USERNAME, PASSWORD)
    
    # --- Continue with the upload process ---
    print("\n-> Navigating to upload page...")
    driver.get("https://www.aparat.com/upload")

    print("-> Selecting video file for upload...")
    file_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='file']")))
    file_input.send_keys(video_full_path)
    print("-> File path sent. Waiting for upload to process...")

    title_field = wait.until(EC.visibility_of_element_located((By.ID, "video-title")))
    print("-> Upload processing complete. Entering details...")
    
    title_field.clear()
    title_field.send_keys(VIDEO_TITLE)
    
    description_field = driver.find_element(By.ID, "video-description")
    description_field.clear()
    description_field.send_keys(VIDEO_DESCRIPTION)
    
    print("-> Selecting Category (Robust Method)...")
    category_trigger = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@id='FField_category']//div[@role='button']")))
    category_trigger.click()
    
    category_option_xpath = f"//li[normalize-space()='{VIDEO_CATEGORY}']"
    category_option = wait.until(EC.visibility_of_element_located((By.XPATH, category_option_xpath)))
    
    driver.execute_script("arguments[0].click();", category_option)
    print(f"-> Category '{VIDEO_CATEGORY}' selected.")
    time.sleep(2)

    print("-> Entering Tags...")
    tag_input = wait.until(EC.visibility_of_element_located((By.XPATH, "//div[@id='FField_tags']//input")))
    for tag in VIDEO_TAGS:
        tag_input.send_keys(tag)
        tag_input.send_keys(Keys.ENTER)
        print(f"  - Tag '{tag}' entered.")
        time.sleep(1)

    print("-> Taking a screenshot before publishing...")
    driver.save_screenshot('final_form_filled.png')
    
    print("-> Clicking final publish button...")
    publish_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'انتشار ویدیو')]")))
    publish_button.click()
    
    print("-> Waiting for final confirmation...")
    wait.until(EC.url_contains("manage/videos"))
    driver.save_screenshot('final_page_after_publish.png')
    
    print("\n\n✅✅✅ UPLOAD PROCESS COMPLETED SUCCESSFULLY! ✅✅✅\n")

except Exception as e:
    print(f"\n❌ SCRIPT FAILED: {e}")
    driver.save_screenshot('error_screenshot.png')
    print("-> An error screenshot has been saved.")
    # exit(1) 

finally:
    print("-> Closing browser.")
    driver.quit()
    if os.path.exists(LOCAL_VIDEO_FILENAME):
        try:
            os.remove(LOCAL_VIDEO_FILENAME)
            print(f"-> Temporary file '{LOCAL_VIDEO_FILENAME}' has been deleted.")
        except OSError as e:
            print(f"-> Error deleting file {LOCAL_VIDEO_FILENAME}: {e}")
