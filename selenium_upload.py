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
VIDEO_TITLE = "GitHub Actions Final Test"
VIDEO_DESCRIPTION = "This video was uploaded via a script running on GitHub Actions using the correct element ID."

def download_video(url, filename):
    """Downloads a video from a URL."""
    print(f"-> Downloading video from: {url}")
    try:
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print("-> ✅ Video downloaded successfully.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"-> ❌ Error downloading video: {e}")
        return False

# --- تنظیمات سلنیوم برای اجرا در گیت‌هاب ---
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")

driver = webdriver.Chrome(options=chrome_options)

try:
    if not all([USERNAME, PASSWORD]):
        raise ValueError("APARAT_USERNAME or APARAT_PASSWORD secrets not set in GitHub.")

    if not download_video(VIDEO_URL, LOCAL_VIDEO_FILENAME):
        raise Exception("Failed to download the video file.")

    print("-> Opening Aparat login page...")
    driver.get("https://www.aparat.com/signin")
    time.sleep(3)

    # ============================ THE FIX FOR GITHUB ACTIONS ============================
    # استفاده از ID برای پیدا کردن فیلدها که شما از اینسپکت پیدا کردید
    print("-> Locating and entering username using ID...")
    username_field = driver.find_element(By.ID, "username")
    username_field.send_keys(USERNAME)

    # فرض می‌کنیم فیلد پسورد هم id="password" دارد
    print("-> Locating and entering password using ID...")
    password_field = driver.find_element(By.ID, "password")
    password_field.send_keys(PASSWORD)
    # ====================================================================================
    
    driver.save_screenshot('1_before_login_click.png')
    print("-> Submitting login form...")
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    time.sleep(5)
    
    driver.save_screenshot('2_after_login_click.png')
    print("-> Checking login status by inspecting URL...")
    if "signin" in driver.current_url:
        raise Exception("Login failed, still on signin page. Check screenshot '2_after_login_click.png'. A CAPTCHA is likely.")

    print("-> ✅ Login appears to be successful!")
    
    print("\n\n✅✅✅ TEST SUCCEEDED: Login was successful! ✅✅✅\n\n")

except Exception as e:
    print(f"\n❌ SCRIPT FAILED: {e}")
    driver.save_screenshot('error_screenshot.png')
    print("-> An error screenshot has been saved.")
    exit(1)

finally:
    print("-> Closing browser.")
    driver.quit()
