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
VIDEO_TITLE = "GitHub Actions Final Attempt"
VIDEO_DESCRIPTION = "Final attempt to upload via GitHub Actions."

def download_video(url, filename):
    print(f"-> Downloading video from: {url}")
    try:
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print("-> ✅ Video downloaded successfully.")
        return True
    except Exception as e:
        print(f"-> ❌ Error downloading video: {e}")
        return False

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

    if not download_video(VIDEO_URL, LOCAL_VIDEO_FILENAME):
        raise Exception("Download failed.")

    print("-> Opening Aparat login page...")
    driver.get("https://www.aparat.com/signin")
    time.sleep(3)

    # --- شبیه‌سازی لاگین دو مرحله‌ای ---
    # 1. وارد کردن نام کاربری
    print("-> Step 1: Entering username...")
    username_field = driver.find_element(By.ID, "username")
    username_field.send_keys(USERNAME)
    time.sleep(1)
    
    # 2. کلیک روی دکمه "ادامه"
    print("-> Step 2: Clicking the 'Continue' button...")
    continue_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
    continue_button.click()
    
    # 3. صبر برای ظاهر شدن کادر رمز عبور
    print("-> Waiting for the password field to appear...")
    time.sleep(4)
    driver.save_screenshot('1_after_continue_click.png')

    # 4. وارد کردن رمز عبور
    print("-> Step 3: Entering password...")
    password_field = driver.find_element(By.ID, "password")
    password_field.send_keys(PASSWORD)
    time.sleep(1)

    # 5. کلیک روی دکمه نهایی ورود
    print("-> Step 4: Clicking the final login button...")
    final_login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
    final_login_button.click()
    time.sleep(5)
    
    driver.save_screenshot('2_after_final_login.png')
    print("-> Checking final login status...")
    if "signin" in driver.current_url:
        raise Exception("Login failed, possibly due to CAPTCHA. Check screenshots.")

    print("\n\n✅✅✅ TEST SUCCEEDED: Login was successful! ✅✅✅\n\n")

except Exception as e:
    print(f"\n❌ SCRIPT FAILED: {e}")
    driver.save_screenshot('error_screenshot.png')
    print("-> An error screenshot has been saved.")
    exit(1)

finally:
    print("-> Closing browser.")
    driver.quit()
