import feedparser
import os
import json
import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import re
from bs4 import BeautifulSoup  # برای کرال کردن کپشن‌ها و پارس کردن محتوا

# تنظیمات فید RSS
RSS_FEED_URL = "https://www.newsbtc.com/feed/"

# تنظیمات API Gemini
GEMINI_API_KEY = os.environ.get("GEMAPI")
if not GEMINI_API_KEY:
    raise ValueError("GEMAPI پیدا نشد!")

# استفاده از URL دقیق ارائه شده توسط شما
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
print(f"در حال استفاده از مدل API در آدرس: {GEMINI_API_URL}")

# گرفتن توکن بلاگر
creds_json = os.environ.get("CREDENTIALS")
if not creds_json:
    raise ValueError("CREDENTIALS پیدا نشد!")
creds = Credentials.from_authorized_user_info(json.loads(creds_json))
service = build("blogger", "v3", credentials=creds)

# تابع ترجمه با Gemini - بدون تغییر
def translate_with_gemini(text, target_lang="fa"):
    headers = {"Content-Type": "application/json"}

    prompt = (
        f"Please translate the following English text (which might contain HTML tags) into {target_lang} "
        f"with the utmost intelligence and precision. Pay close attention to context and nuance.\n"
        f"IMPORTANT TRANSLATION RULES:\n"
        f"1. Translate ALL text content, including text inside HTML tags like <p>, <li>, and especially <blockquote>. Do not skip any content.\n"
        f"2. For technical terms or English words commonly used in the field (like cryptocurrency, finance, technology), "
        f"transliterate them into Persian script (Finglish) instead of translating them into a potentially obscure Persian word. "
        f"Example: 'Stochastic Oscillator' should become 'اوسیلاتور استوکستیک'. Apply consistently.\n"
        f"3. Ensure that any text within quotation marks (\"\") is also accurately translated.\n"
        f"4. Preserve the original HTML structure as much as possible, only translating the text content within the tags.\n"
        f"OUTPUT REQUIREMENT: Do not add any explanations, comments, or options. Only return the final, high-quality translated text (potentially including the original HTML tags with translated content).\n\n"
        f"English Text with HTML to Translate:\n{text}"
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
             "temperature": 0.5
         }
    }

    print(f"ارسال درخواست ترجمه به: {GEMINI_API_URL}")
    
    max_retries = 2
    retry_delay = 5
    response = None
    for attempt in range(max_retries + 1):
        response = requests.post(f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", headers=headers, json=payload)
        print(f"کد وضعیت پاسخ API (تلاش {attempt+1}): {response.status_code}")

        if response.status_code == 200:
            break
        elif response.status_code == 429 and attempt < max_retries:
            print(f"خطای Rate Limit (429). منتظر ماندن برای {retry_delay} ثانیه...")
            # time.sleep(retry_delay)
        else:
             if attempt == max_retries or response.status_code != 429:
                raise ValueError(f"خطا در درخواست API (تلاش {attempt+1}): کد وضعیت {response.status_code}, پاسخ: {response.text}")

    if response is None or response.status_code != 200:
         raise ValueError(f"ترجمه پس از {max_retries+1} تلاش ناموفق بود.")

    result = response.json()

    if 'error' in result:
        raise ValueError(f"خطا در API Gemini: {result['error'].get('message', 'جزئیات نامشخص')}")

    try:
        if not result.get("candidates"):
             feedback = result.get('promptFeedback', {})
             block_reason = feedback.get('blockReason', 'نامشخص')
             safety_ratings = feedback.get('safetyRatings', [])
             detailed_block_msg = f"API Response without candidates. Block Reason: {block_reason}. Safety Ratings: {safety_ratings}."
             print(detailed_block_msg)
             raise ValueError(detailed_block_msg + f" Full Response: {result}")

        candidate = result["candidates"][0]
        content = candidate.get("content")
        if not content or not content.get("parts") or not content["parts"][0].get("text"):
             finish_reason = candidate.get("finishReason", "نامشخص")
             if finish_reason != "STOP" or not (content and content.get("parts") and content["parts"][0].get("text")):
                  raise ValueError(f"ترجمه کامل نشد یا محتوای متنی در پاسخ وجود نداشت. دلیل توقف: {finish_reason}. پاسخ: {result}")
        
        translated_text = content["parts"][0]["text"]

    except (IndexError, KeyError, TypeError) as e:
        raise ValueError(f"ساختار پاسخ API غیرمنتظره بود: {e}. پاسخ کامل: {result}")

    return translated_text.strip()

# تابع حذف لینک‌های newsbtc (بدون تغییر)
def remove_newsbtc_links(text):
    pattern = r'<a\s+[^>]*href=["\']https?://(www\.)?newsbtc\.com[^"\']*["\'][^>]*>(.*?)</a>'
    return re.sub(pattern, r'\2', text, flags=re.IGNORECASE)

# تابع کرال کردن کپشن‌ها همراه با URL عکس‌ها
def crawl_captions(post_url):
    try:
        # درخواست به صفحه وب
        response = requests.get(post_url)
        response.raise_for_status()  # اگه خطایی بود، استثنا می‌ندازه
        soup = BeautifulSoup(response.content, "html.parser")

        # لیست برای ذخیره کپشن‌ها و URL عکس‌ها
        captions_with_urls = []

        # پیدا کردن تگ‌های <figure> که شامل <img> و <figcaption> هستن
        figures = soup.find_all("figure")
        for figure in figures:
            img = figure.find("img")
            figcaption = figure.find("figcaption", class_="wp-caption-text")
            if img and figcaption:
                img_url = img.get("src")
                if img_url:
                    captions_with_urls.append({
                        "url": img_url,
                        "caption": str(figcaption)
                    })

        # کپشن‌های مستقل (بدون <figure>)
        # کپشن ۱: تگ <pre> با استایل text-align: center
        pre_caption = soup.find("pre", style="text-align: center")
        if pre_caption:
            captions_with_urls.append({
                "url": None,  # این کپشن به عکس خاصی مربوط نیست
                "caption": str(pre_caption)
            })

        # کپشن ۲: تگ <p> با استایل text-align: center
        p_caption = soup.find("p", style="text-align: center")
        if p_caption:
            captions_with_urls.append({
                "url": None,  # این کپشن به عکس خاصی مربوط نیست
                "caption": str(p_caption)
            })

        # دیباگ: چاپ کپشن‌های کرال‌شده همراه با URL
        print("کپشن‌های کرال‌شده همراه با URL:")
        for i, item in enumerate(captions_with_urls, 1):
            print(f"آیتم {i}: URL={item['url']}, کپشن={item['caption']}")

        return captions_with_urls

    except requests.RequestException as e:
        print(f"خطا در کرال کردن صفحه {post_url}: {e}")
        return []
    except Exception as e:
        print(f"خطای غیرمنتظره در کرال کردن: {e}")
        return []

# تابع برای قرار دادن کپشن‌ها زیر عکس‌ها
def add_captions_to_images(content, captions_with_urls):
    if not captions_with_urls:
        print("هیچ کپشنی برای اضافه کردن وجود ندارد.")
        return content

    # پارس کردن محتوای فید
    soup = BeautifulSoup(content, "html.parser")
    images = soup.find_all("img")  # پیدا کردن همه تگ‌های <img>

    # دیباگ: چاپ تعداد عکس‌ها و URL‌هاشون
    print(f"تعداد عکس‌های پیدا شده در محتوا: {len(images)}")
    for i, img in enumerate(images, 1):
        print(f"عکس {i}: {img.get('src')}")

    # اگه هیچ عکسی توی محتوا نبود، کپشن‌ها رو به انتها اضافه می‌کنیم
    if not images:
        print("هیچ عکسی توی محتوا پیدا نشد. کپشن
