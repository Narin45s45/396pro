import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

# --- اطلاعات از سکرت‌های گیت‌هاب خوانده می‌شود ---
USERNAME = os.environ.get("APARAT_USERNAME")
PASSWORD = os.environ.get("APARAT_PASSWORD")

# --- تنظیمات ویدیو ---
VIDEO_URL = "https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/360/Big_Buck_Bunny_360_10s_1MB.mp4"
LOCAL_VIDEO_FILENAME = "video_to_upload.mp4"
VIDEO_TITLE = "ویدیوی تستی از گیت‌هاب"
VIDEO_DESCRIPTION = "این ویدیو به صورت کاملاً خودکار توسط یک اسکریپت پایتون در محیط GitHub Actions آپلود شد."
VIDEO_TAGS = "گیت‌هاب, پایتون, اتوماسیون, سلنیوم"

def download_video(url, filename):
    """Downloads a video from a URL."""
    print("-> Downloading video...")
    try:
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print("-> ✅ Video downloaded successfully.")
        return os.path.abspath(filename) # مسیر کامل فایل را برمی‌گرداند
    except Exception as e:
        print(f"-> ❌ Error downloading video: {e}")
        return None

# --- تنظیمات سلنیوم برای گیت‌هاب ---
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")

driver = webdriver.Chrome(options=chrome_options)

try:
    if not all([USERNAME, PASSWORD]):
        raise ValueError("Secrets for USERNAME or PASSWORD are not set.")

    video_full_path = download_video(VIDEO_URL, LOCAL_VIDEO_FILENAME)
    if not video_full_path:
        raise Exception("Failed to download the video file.")

    print("-> Opening Aparat login page...")
    driver.get("https://www.aparat.com/signin")
    time.sleep(3)

    # --- فرآیند لاگین ---
    print("-> Logging in...")
    driver.find_element(By.ID, "username").send_keys(USERNAME)
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    time.sleep(4)
    driver.find_element(By.ID, "password").send_keys(PASSWORD)
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    time.sleep(5)

    if "signin" in driver.current_url:
        raise Exception("Login failed. Check credentials or CAPTCHA.")
    print("-> ✅ Login successful!")

    # --- فرآیند آپلود ---
    print("-> Navigating to upload page...")
    driver.get("https://www.aparat.com/upload")
    time.sleep(5)
    
    print("-> Selecting video file for upload...")
    file_input = driver.find_element(By.XPATH, "//input[@type='file']")
    file_input.send_keys(video_full_path)
    print("-> File path sent to input. Waiting for processing...")
    
    time.sleep(15) 
    driver.save_screenshot('1_after_file_select.png')
    
    print("-> Entering video details...")
    driver.find_element(By.ID, "video-title").send_keys(VIDEO_TITLE)
    driver.find_element(By.ID, "video-description").send_keys(VIDEO_DESCRIPTION)
    
    # ============================ THE FIX IS HERE ============================
    # خط زیر اصلاح شد. " و ) در انتهای آن جا افتاده بود
    tag_input = driver.find_element(By.XPATH, "//input[contains(@class, 'tag-input')]")
    # =======================================================================
    tag_input.send_keys(VIDEO_TAGS)

    driver.save_screenshot('2_after_details_filled.png')
    
    time.sleep(5)
    print("-> Clicking final publish button...")
    publish_button = driver.find_element(By.ID, "video-submit-btn")
    publish_button.click()
    
    print("-> Waiting for final confirmation...")
    time.sleep(10)
    driver.save_screenshot('3_final_page.png')
    
    print("\n\n✅✅✅ UPLOAD PROCESS COMPLETED! ✅✅✅\nCheck your Aparat channel.")

except Exception as e:
    print(f"\n❌ SCRIPT FAILED: {e}")
    driver.save_screenshot('error_screenshot.png')
    print("-> An error screenshot has been saved.")
    exit(1)

finally:
    print("-> Closing browser.")
    driver.quit()
    if os.path.exists(LOCAL_VIDEO_FILENAME):
        os.remove(LOCAL_VIDEO_FILENAME)
        print(f"-> Temporary file '{LOCAL_VIDEO_FILENAME}' has been deleted.")
