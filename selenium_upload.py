import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
# WebDriverWait را فقط برای بخش‌های ضروری اضافه می‌کنیم
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- اطلاعات از سکرت‌های گیت‌هاب خوانده می‌شود ---
USERNAME = os.environ.get("APARAT_USERNAME")
PASSWORD = os.environ.get("APARAT_PASSWORD")

# --- تنظیمات ویدیو ---
VIDEO_URL = "https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/360/Big_Buck_Bunny_360_10s_1MB.mp4"
LOCAL_VIDEO_FILENAME = "video_to_upload.mp4"
VIDEO_TITLE = "ویدیوی گیم پلی (کد اصلی)"
VIDEO_DESCRIPTION = "این یک ویدیوی تستشده است."
VIDEO_TAGS = ["گیم", "بازی آنلاین", "گیم پلی جدید"]
VIDEO_CATEGORY = "ویدئو گیم" 

# --- ثابت‌های سلنیوم ---
WAIT_TIMEOUT = 45 # ثانیه

def download_video(url, filename):
    """یک ویدیو را از URL داده شده دانلود و به صورت محلی ذخیره می‌کند."""
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

# --- تنظیمات سلنیوم ---
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

driver = webdriver.Chrome(options=chrome_options)
# WebDriverWait را برای استفاده در بخش‌های خاص مقداردهی می‌کنیم
wait = WebDriverWait(driver, WAIT_TIMEOUT)

try:
    if not all([USERNAME, PASSWORD]):
        raise ValueError("Secrets for APARAT_USERNAME or APARAT_PASSWORD are not set.")

    video_full_path = download_video(VIDEO_URL, LOCAL_VIDEO_FILENAME)
    if not video_full_path:
        raise Exception("Failed to download the video file.")

    # ============================ بازگشت به بلوک ورود اصلی شما که کار می‌کرد ============================
    print("-> Opening Aparat login page...")
    driver.get("https://www.aparat.com/signin")
    time.sleep(4) # استفاده از sleep اصلی شما

    print("-> Logging in...")
    driver.find_element(By.ID, "username").send_keys(USERNAME)
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    time.sleep(4) # استفاده از sleep اصلی شما
    driver.find_element(By.ID, "password").send_keys(PASSWORD)
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    time.sleep(6) # افزایش زمان برای اطمینان از بارگذاری داشبورد

    if "signin" in driver.current_url:
        raise Exception("Login failed. Check credentials or CAPTCHA.")
    print("-> ✅ Login successful!")
    # =======================================================================================

    print("-> Navigating to upload page...")
    driver.get("https://www.aparat.com/upload")
    time.sleep(5)
    
    print("-> Selecting video file for upload...")
    # منتظر می‌مانیم تا دکمه آپلود آماده شود
    file_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='file']")))
    file_input.send_keys(video_full_path)
    print("-> File path sent. Waiting for processing...")
    
    # منتظر می‌مانیم تا فیلد عنوان ظاهر شود
    title_field = wait.until(EC.visibility_of_element_located((By.ID, "video-title")))
    
    print("-> Entering video details...")
    title_field.send_keys(VIDEO_TITLE)
    driver.find_element(By.ID, "video-description").send_keys(VIDEO_DESCRIPTION)
    
    # ============================ تنها بخش اصلاح شده: انتخاب دسته‌بندی ============================
    print("-> Selecting Category (Robust Method)...")
    # ۱. روی دکمه بازکننده دسته‌بندی کلیک می‌کنیم.
    category_trigger = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@id='FField_category']//div[@role='button']")))
    category_trigger.click()
    
    # ۲. منتظر می‌مانیم تا گزینه مورد نظر ما در لیست ظاهر شود.
    category_option_xpath = f"//li[normalize-space()='{VIDEO_CATEGORY}']"
    category_option = wait.until(EC.visibility_of_element_located((By.XPATH, category_option_xpath)))
    
    # ۳. با استفاده از جاوا اسکریپت کلیک می‌کنیم.
    driver.execute_script("arguments[0].click();", category_option)
    print(f"-> Category '{VIDEO_CATEGORY}' selected.")
    time.sleep(2) # وقفه کوتاه برای اطمینان
    # =======================================================================================
    
    print("-> Entering Tags...")
    # پیدا کردن فیلد ورودی تگ‌ها
    tag_input = driver.find_element(By.XPATH, "//div[@id='FField_tags']//input")
    for tag in VIDEO_TAGS:
        tag_input.send_keys(tag)
        tag_input.send_keys(Keys.ENTER)
        time.sleep(1)

    driver.save_screenshot('final_form_filled.png')
    time.sleep(2)
    
    print("-> Clicking final publish button...")
    publish_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'انتشار ویدیو')]")))
    publish_button.click()
    
    print("-> Waiting for final confirmation...")
    # منتظر می‌مانیم تا به صفحه مدیریت ویدیوها منتقل شویم
    wait.until(EC.url_contains("manage/videos"))
    driver.save_screenshot('final_page_after_publish.png')
    
    print("\n\n✅✅✅ UPLOAD PROCESS COMPLETED! ✅✅✅\n")

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
