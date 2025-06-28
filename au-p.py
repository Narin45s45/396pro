import requests
import time
import sys
import traceback

# تنظیمات وردپرس
WORDPRESS_URL = "https://arzitals.ir/wp-json/wp/v2/posts"  # آدرس API وردپرس
WORDPRESS_USER = "alireza"  # نام کاربری
WORDPRESS_PASS = "9wDy7keQ7dUsFZbZxu0EHJad"  # رمز عبور برنامه
auth_tuple = (WORDPRESS_USER, WORDPRESS_PASS)  # برای احراز هویت

# داده‌های پست (با داده‌های حداقل برای تست بیشتر)
post_data = {
    "title": "تست دیباگ از گیت‌هاب", # عنوان جدید برای تشخیص
    "content": "این یک پست آزمایشی دیباگ برای بررسی مشکل اتصال است.",
    "status": "publish",  # وضعیت: منتشر شود
    "categories": [69]  # شناسه دسته‌بندی
}

# هدرهای سفارشی برای شناسایی درخواست در لاگ‌های سرور (اختیاری)
# اگر سرور شما لاگ‌های access را ثبت می‌کند، این هدر می‌تواند به شناسایی درخواست شما کمک کند.
headers = {
    "User-Agent": "PythonRequestsScript/1.0 (Debug-Mode)",
    "X-Debug-Source": "GitHub-Action-Test" # یک هدر سفارشی برای دیباگ
}

# ارسال پست به وردپرس
print("==================================================")
print(">>> شروع ارسال پست به وردپرس (حالت دیباگ)...")
print("==================================================")

print(f"--- اطلاعات درخواست:")
print(f"    URL: {WORDPRESS_URL}")
print(f"    کاربر: {WORDPRESS_USER}")
print(f"    عنوان پست: {post_data['title']}")
print(f"    داده‌های ارسالی (json): {post_data}")
print(f"    هدرهای ارسالی: {headers}") # نمایش هدرها
print(f"    مهلت زمانی (timeout): 60 ثانیه")

try:
    print(f"--- تلاش برای ارسال POST به: {WORDPRESS_URL}...")
    start_request_time = time.time()
    response = requests.post(WORDPRESS_URL, auth=auth_tuple, json=post_data, timeout=60, headers=headers)
    
    request_duration = time.time() - start_request_time
    print(f"--- درخواست ارسال شد ({request_duration:.2f} ثانیه).")
    print(f"--- کد وضعیت HTTP دریافتی: {response.status_code}")
    print(f"--- هدرهای پاسخ: {response.headers}") # نمایش هدرهای پاسخ

    # تلاش برای چاپ پاسخ خام، حتی اگر خطا باشد
    print(f"--- متن خام پاسخ (response.text):")
    print(response.text[:500] + "..." if len(response.text) > 500 else response.text) # فقط 500 کاراکتر اول

    response.raise_for_status()  # بررسی خطاهای HTTP (4xx یا 5xx)

    # اگر کد وضعیت 200 OK باشد و raise_for_status خطایی ندهد
    try:
        response_data = response.json()
        print("<<< پست با موفقیت به وردپرس ارسال شد!")
        print("    URL پست:", response_data.get("link", "نامشخص"))
        print("    ID پست:", response_data.get("id", "نامشخص"))
    except ValueError:
        print("!!! خطا: پاسخ دریافتی JSON معتبر نیست، اما کد وضعیت موفقیت‌آمیز است.")
        print("    این ممکن است نشان دهد سرور پاسخ JSON استاندارد نمی‌دهد.")

except requests.exceptions.ConnectionError as e:
    print(f"!!! خطای اتصال به وردپرس: {e}")
    print("    این خطا معمولاً به دلیل مشکلات شبکه، فایروال یا سرور است که اتصال را قبل از تکمیل درخواست قطع می‌کند.")
    print("    بررسی کنید آیا IP گیت‌هاب در ایران مسدود شده است یا سرور وردپرس شما اتصال را بلافاصله قطع می‌کند.")
    print(f"    نوع خطا: {type(e).__name__}")
    print(f"    جزئیات خطا: {e.args}")

except requests.exceptions.Timeout as e:
    print(f"!!! خطا: Timeout ارسال به وردپرس. زمان انتظار تمام شد. ({e})")
    print("    این نشان می‌دهد درخواست ارسال شده اما پاسخی در 60 ثانیه دریافت نشده است.")
    print("    ممکن است به دلیل کندی شدید سرور یا مسدودسازی درخواست باشد که پاسخ به شما نمی‌رسد.")
    print(f"    نوع خطا: {type(e).__name__}")

except requests.exceptions.HTTPError as e:
    print(f"!!! خطای HTTP: {e}")
    print(f"    کد وضعیت: {response.status_code}")
    print(f"    پاسخ کامل سرور (response.text):")
    print(response.text) # چاپ پاسخ کامل در صورت خطای HTTP
    print("    این خطا نشان می‌دهد سرور درخواست شما را دریافت کرده و با یک کد وضعیت خطا (مانند 401, 403, 404, 500) پاسخ داده است.")
    print("    پاسخ سرور در بالا حاوی جزئیات بیشتری درباره خطا است.")
    print(f"    نوع خطا: {type(e).__name__}")

except Exception as e:
    print(f"!!! خطای پیش‌بینی نشده: {type(e).__name__} - {e}")
    print("    این یک خطای کلی است که نشان دهنده مشکلی خارج از خطاهای معمول درخواست HTTP است.")
    traceback.print_exc() # چاپ کامل traceback برای دیباگ دقیق‌تر

print("==================================================")
print(">>> اسکریپت به پایان رسید.")
print("==================================================")
