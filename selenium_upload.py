import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

# --- خواندن اطلاعات از سکرت‌های گیت‌هاب ---
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

    # ============================ UPLOAD PROCESS ============================
    # ۱. رفتن به صفحه آپلود
    print("-> Navigating to upload page...")
    driver.get("https://www.aparat.com/upload")
    time.sleep(5)
    
    # ۲. پیدا کردن دکمه انتخاب فایل و ارسال مسیر فایل
    print("-> Selecting video file for upload...")
    file_input = driver.find_element(By.XPATH, "//input[@type='file']")
    file_input.send_keys(video_full_path)
    print("-> File path sent to input. Waiting for processing...")
    
    # صبر می‌کنیم تا آپارات ویدیو را پردازش اولیه کند (این زمان ممکن است نیاز به تغییر داشته باشد)
    time.sleep(15) 
    driver.save_screenshot('1_after_file_select.png')
    
    # ۳. وارد کردن عنوان، توضیحات و تگ‌ها
    print("-> Entering video details...")
    driver.find_element(By.ID, "video-title").send_keys(VIDEO_TITLE)
    driver.find_element(By.ID, "video-description").send_keys(VIDEO_DESCRIPTION)
    
    # وارد کردن تگ‌ها
    tag_input = driver.find_element(By.XPATH, "//input[contains(@class, 'tag-input')]
