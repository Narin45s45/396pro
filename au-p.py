import requests
import time
import sys
import traceback

# تنظیمات وردپرس
WORDPRESS_URL = "https://arzitals.ir/wp-json/wp/v2/posts"  # آدرس API وردپرس
WORDPRESS_USER = "alireza"  # نام کاربری
WORDPRESS_PASS = "9wDy7keQ7dUsFZbZxu0EHJad"  # رمز عبور برنامه
auth_tuple = (WORDPRESS_USER, WORDPRESS_PASS)  # برای احراز هویت

# داده‌های پست
post_data = {
    "title": "سلام دنیا",
    "content": "این یک پست آزمایشی است برای تست API وردپرس.",
    "status": "publish",  # وضعیت: منتشر شود
    "categories": [69]  # شناسه دسته‌بندی
}

# ارسال پست به وردپرس
print("==================================================")
print(">>> شروع ارسال پست به وردپرس...")
print("==================================================")

try:
    print(f"--- ارسال POST به: {WORDPRESS_URL} برای عنوان: {post_data['title'][:50]}...")
    start_time = time.time()
    response = requests.post(WORDPRESS_URL, auth=auth_tuple, json=post_data, timeout=60)
    print(f"--- درخواست ارسال شد ({time.time() - start_time:.2f} ثانیه). کد وضعیت: {response.status_code}")
    response.raise_for_status()  # بررسی خطاهای HTTP
    response_data = response.json()
    print("<<< پست با موفقیت به وردپرس ارسال شد! URL:", response_data.get("link", "نامشخص"))
except requests.exceptions.ConnectionError as e:
    print(f"!!! خطای اتصال به وردپرس: {e}. بررسی سرور یا تنظیمات شبکه.")
except requests.exceptions.Timeout:
    print("!!! خطا: Timeout ارسال به وردپرس. زمان انتظار تمام شد.")
except requests.exceptions.HTTPError as e:
    print(f"!!! خطای HTTP: {e}. کد وضعیت: {response.status_code}, پاسخ: {response.text}")
except Exception as e:
    print(f"!!! خطای پیش‌بینی نشده: {type(e).__name__} - {e}")
    traceback.print_exc()

print("==================================================")
print(">>> اسکریپت به پایان رسید.")
print("==================================================")
