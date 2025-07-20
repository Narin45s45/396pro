import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options

# --- اطلاعات از سکرت‌های گیت‌هاب خوانده می‌شود ---
USERNAME = os.environ.get("APARAT_USERNAME")
PASSWORD = os.environ.get("APARAT_PASSWORD")

# --- تنظیمات ویدیو (متن‌های معمولی طبق خواسته شما) ---
VIDEO_URL = "https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/360/Big_Buck_Bunny_360_10s_1MB.mp4"
LOCAL_VIDEO_FILENAME = "video_to_upload.mp4"
VIDEO_TITLE = "ویدیوی گیم پلی"
VIDEO_DESCRIPTION = "یک ویدیوی جدید از بازی."
VIDEO_TAGS = ["گیم", "بازی آنلاین", "گیم پلی جدید"]

def download_video(url, filename):
    print("-> Downloading video...")
    try:
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print("-> ✅ Video downloaded successfully.")
        return os.path.abspath(filename)
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

    print("-> Navigating to upload page...")
    driver.get("https://www.aparat.com/upload")
    time.sleep(5)
    
    print("-> Selecting video file for upload...")
    file_input = driver.find_element(By.XPATH, "//input[@type='file']")
    file_input.send_keys(video_full_path)
    print("-> File path sent. Waiting for processing...")
    
    time.sleep(20)
    
    print("-> Entering video details...")
    driver.find_element(By.ID, "video-title").send_keys(VIDEO_TITLE)
    driver.find_element(By.ID, "video-description").send_keys(VIDEO_DESCRIPTION)
    
    # ============================ FINAL ATTEMPT BASED ON YOUR HTML ============================
    # ۱. انتخاب دسته‌بندی
    print("-> Selecting Category...")
    # پیدا کردن دکمه بازکننده دسته‌بندی بر اساس ساختار HTML که فرستادید
    category_trigger = driver.find_element(By.XPATH, "//div[@id='FField_category']//div[@role='button']")
    category_trigger.click()
    time.sleep(2)
    # انتخاب گزینه "بازی" از لیست باز شده
    driver.find_element(By.XPATH, "//li[contains(text(), 'بازی')]").click()
    time.sleep(2)

    # ۲. وارد کردن تگ‌ها
    print("-> Entering Tags...")
    # پیدا کردن دکمه بازکننده تگ‌ها
    tag_trigger = driver.find_element(By.XPATH, "//div[@id='FField_tags']//div[@role='button']")
    tag_trigger.click()
    time.sleep(2)
    # پیدا کردن فیلد ورودی تگ که بعد از کلیک ظاهر می‌شود
    tag_input = driver.find_element(By.XPATH, "//div[contains(@class, 'tag-input-container')]//input")
    for tag in VIDEO_TAGS:
        tag_input.send_keys(tag)
        tag_input.send_keys(Keys.ENTER)
        time.sleep(1)
    # =======================================================================================

    driver.save_screenshot('final_form_filled.png')
    time.sleep(5)
    
    print("-> Clicking final publish button...")
    publish_button = driver.find_element(By.XPATH, "//button[contains(., 'انتشار ویدیو')]")
    publish_button.click()
    
    print("-> Waiting for final confirmation...")
    time.sleep(15)
    driver.save_screenshot('final_page_after_publish.png')
    
    print("\n\n✅✅✅ UPLOAD PROCESS COMPLETED! ✅✅✅\n")

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
