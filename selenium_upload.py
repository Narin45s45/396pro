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
VIDEO_TITLE = "ویدیوی گیم پلی تست (رفع خطا)"
VIDEO_DESCRIPTION = "این یک ویدیو است."
VIDEO_TAGS = ["گیم", "بازی آنلاین", "گیم پلی جدید", "تست"]
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
wait = WebDriverWait(driver, WAIT_TIMEOUT)

try:
    if not all([USERNAME, PASSWORD]):
        raise ValueError("Secrets for APARAT_USERNAME or APARAT_PASSWORD are not set.")

    video_full_path = download_video(VIDEO_URL, LOCAL_VIDEO_FILENAME)
    if not video_full_path:
        raise Exception("Failed to download the video file.")

    print("-> Opening Aparat login page...")
    driver.get("https://www.aparat.com/signin")

    print("-> Logging in...")
    wait.until(EC.visibility_of_element_located((By.NAME, "username"))).send_keys(USERNAME)
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

    wait.until(EC.visibility_of_element_located((By.NAME, "password"))).send_keys(PASSWORD)
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

    print("-> Waiting for login to complete...")
    wait.until(EC.url_contains("dashboard"))
    print("-> ✅ Login successful!")

    print("-> Navigating to upload page...")
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
    
    # ============================ راه‌حل جدید برای انتخاب دسته‌بندی ============================
    print("-> Selecting Category...")
    
    # ۱. روی دکمه بازکننده دسته‌بندی کلیک می‌کنیم.
    category_trigger = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@id='FField_category']//div[@role='button']")))
    category_trigger.click()
    print("-> Category dropdown opened.")
    
    # ۲. منتظر می‌مانیم تا گزینه مورد نظر ما در لیست ظاهر و "قابل مشاهده" شود.
    category_option_xpath = f"//li[normalize-space()='{VIDEO_CATEGORY}']"
    category_option = wait.until(EC.visibility_of_element_located((By.XPATH, category_option_xpath)))
    print(f"-> Category option '{VIDEO_CATEGORY}' is now visible.")
    
    # ۳. با استفاده از جاوا اسکریپت روی گزینه کلیک می‌کنیم. این روش بسیار قابل اعتماد است.
    driver.execute_script("arguments[0].scrollIntoView(true);", category_option) # ابتدا مطمئن می‌شویم عنصر در دید است
    driver.execute_script("arguments[0].click();", category_option)
    print(f"-> Category '{VIDEO_CATEGORY}' selected via JavaScript click.")
    time.sleep(1) # یک ثانیه وقفه کوتاه برای اطمینان از ثبت انتخاب
    # =======================================================================================

    print("-> Entering Tags...")
    tag_input = wait.until(EC.visibility_of_element_located((By.XPATH, "//div[@id='FField_tags']//input")))
    for tag in VIDEO_TAGS:
        tag_input.send_keys(tag)
        tag_input.send_keys(Keys.ENTER)
        print(f"  - Tag '{tag}' entered.")
        time.sleep(0.5)

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
    # گرفتن اسکرین‌شات در لحظه خطا برای دیباگ کردن بسیار مهم است
    driver.save_screenshot('error_screenshot.png')
    print("-> An error screenshot has been saved.")
    # در محیط CI/CD این کد را برای نشان دادن شکست فعال کنید
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
```

### خلاصه تغییرات:

1.  **باز کردن منو**: مثل قبل، روی دکمه دسته‌بندی کلیک می‌کنیم تا لیست باز شود.
2.  **انتظار برای مشاهده**: به جای انتظار برای "قابل کلیک بودن"، منتظر می‌مانیم تا گزینه مورد نظر ما (`<li>`) "قابل مشاهده" (`visibility_of_element_located`) شود. این تضمین می‌کند که عنصر واقعاً در صفحه ظاهر شده است.
3.  **کلیک با جاوا اسکریپت**: این تغییر اصلی است. به جای `category_option.click()`، از `driver.execute_script("arguments[0].click();", category_option)` استفاده می‌کنیم. این دستور مستقیماً به مرورگر می‌گوید که روی این عنصر کلیک کند و بسیاری از موانع را نادیده می‌گیرد.
4.  **اسکرول به عنصر**: قبل از کلیک، با `scrollIntoView` مطمئن می‌شویم که عنصر حتماً در محدوده دید مرورگر قرار دارد.

این روش جدید باید مشکل شما را به طور کامل حل کند. لطفاً این کد را در گیت‌هاب جایگزین کرده و دوباره اجرا کن
