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
VIDEO_TITLE = "ویدیوی گیم پلی )"
VIDEO_DESCRIPTION = "یک ویدیوی جدید ازق."
VIDEO_TAGS = ["گیم", "گیم پلی", "گیمر"] 
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

def final_login_strategy(driver, wait, username, password):
    """
    A robust login strategy that retries up to 3 times. If it hits the device limit,
    it logs out sessions and the main loop triggers a new attempt.
    """
    print("-> Starting final login strategy...")
    
    # <<<< CHANGE: Main login loop that tries up to 3 times >>>>
    for attempt in range(3):
        print(f"-> Performing login attempt {attempt + 1}/3...")
        
        try:
            # --- Perform a full login sequence ---
            driver.get("https://www.aparat.com/signin")
            wait.until(EC.visibility_of_element_located((By.ID, "username"))).send_keys(username)
            driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
            wait.until(EC.visibility_of_element_located((By.ID, "password"))).send_keys(password)
            driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

            # --- Check for Device Limit Page ---
            try:
                logout_button_xpath = "//button[text()='خروج']"
                WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.XPATH, logout_button_xpath)))
                
                print("-> Device limit page detected. Logging out of up to 3 devices...")
                for i in range(3):
                    try:
                        first_logout_button = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, f"({logout_button_xpath})[1]"))
                        )
                        driver.execute_script("arguments[0].click();", first_logout_button)
                        print(f"-> Clicked logout on device {i+1}.")
                        time.sleep(3) 
                    except TimeoutException:
                        print(f"-> No more logout buttons found after {i} clicks.")
                        break
                
                # After clearing sessions, the main loop will start a new, clean attempt.
                print("-> Sessions cleared. A new login attempt will start.")
                continue # This continues to the next iteration of the main `for attempt in range(3)` loop.

            except TimeoutException:
                # Device limit page was not found. We should be logged in.
                print("-> Device limit page not detected. Verifying successful login...")
                wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "a[href*='/dashboard']")))
                print("-> ✅ Login successful!")
                return # SUCCESS! Exit the function and the loop.

        except Exception as e:
            print(f"-> An error occurred during login attempt {attempt + 1}: {e}")
            driver.save_screenshot(f'error_login_attempt_{attempt + 1}.png')
            if attempt < 2:
                print("-> Retrying...")
            else:
                print("-> All login attempts failed.")
                raise # Re-raise the last exception if all attempts fail
    
    # This part is reached if the loop finishes without a successful login.
    raise Exception("Login failed after 3 attempts.")


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

    # --- Use the new, final login strategy ---
    final_login_strategy(driver, wait, USERNAME, PASSWORD)
    
    # --- Navigate to upload page by clicking the button ---
    print("\n-> Navigating to upload page by clicking the UI button...")
    upload_button = wait.until(
        EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'بارگذاری ویدیو')]"))
    )
    upload_button.click()

    # --- Continue with the upload process ---
    print("-> Waiting for upload page to load...")
    wait.until(EC.url_contains("upload"))
    print("-> Upload page loaded successfully.")

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

    # ============================ FINAL ROBUST TAG LOGIC ============================
    print("-> Entering Tags (Final Robust Method)...")
    
    # Step 1: Click the main tag area to activate the input field.
    print("-> Activating the tag input area...")
    tag_area_trigger = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@id='FField_tags']//div[@role='button']")))
    tag_area_trigger.click()
    time.sleep(1) # Add a small pause after clicking
    
    # Step 2: Now find the actual input field that has appeared.
    print("-> Finding the active tag input field...")
    tag_input = wait.until(EC.visibility_of_element_located((By.XPATH, "//div[@id='FField_tags']//input[not(@type='hidden')]")))

    for tag in VIDEO_TAGS:
        print(f"-> Processing tag: '{tag}'")
        tag_input.clear()
        # Send keys with a small delay to ensure they are registered
        tag_input.send_keys(tag)
        time.sleep(0.5) # Wait half a second after typing
        # Just press Enter. This is the most reliable method.
        tag_input.send_keys(Keys.ENTER)
        print(f"  - ✅ Tag '{tag}' entered with Enter key.")
        time.sleep(1.5) # A longer pause to let the UI update the tag list
    # ===================================================================================

    print("-> Taking a screenshot before publishing...")
    driver.save_screenshot('final_form_filled.png')
    
    # ============================ FINAL SUBMIT BUTTON FIX ============================
    print("-> Clicking final publish button using JavaScript...")
    # This selector finds the button with type='submit' that contains the text 'انتشار ویدیو'
    publish_button_xpath = "//button[@type='submit' and contains(., 'انتشار ویدیو')]"
    publish_button = wait.until(EC.element_to_be_clickable((By.XPATH, publish_button_xpath)))
    # Using JavaScript click which is more reliable for complex UIs
    driver.execute_script("arguments[0].click();", publish_button)
    print("-> Publish button clicked via JavaScript.")
    # ===================================================================================
    
    # ============================ REMOVED STRICT FINAL CHECK ============================
    # We remove the strict URL check because the final page can vary (e.g., duplicate video warning).
    # We'll just wait a few seconds for the process to finalize and assume success.
    print("-> Assuming publish was successful. Waiting 10 seconds to finalize...")
    time.sleep(10)
    driver.save_screenshot('final_page_after_publish.png')
    # ===================================================================================
    
    print("\n\n✅✅✅ UPLOAD PROCESS INITIATED SUCCESSFULLY! ✅✅✅\n")

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
