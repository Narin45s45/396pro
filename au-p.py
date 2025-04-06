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

# تابع کرال کردن کپشن‌ها با BeautifulSoup
def crawl_captions(post_url):
    try:
        # درخواست به صفحه وب
        response = requests.get(post_url)
        response.raise_for_status()  # اگه خطایی بود، استثنا می‌ندازه
        soup = BeautifulSoup(response.content, "html.parser")

        # لیست برای ذخیره کپشن‌ها
        captions = []

        # کپشن ۱: تگ <pre> با استایل text-align: center
        pre_caption = soup.find("pre", style="text-align: center")
        if pre_caption:
            captions.append(str(pre_caption))

        # کپشن ۲: تگ <figcaption> با کلاس wp-caption-text
        figcaptions = soup.find_all("figcaption", class_="wp-caption-text")
        for figcaption in figcaptions:
            captions.append(str(figcaption))

        # کپشن ۳: تگ <p> با استایل text-align: center
        p_caption = soup.find("p", style="text-align: center")
        if p_caption:
            captions.append(str(p_caption))

        return captions

    except requests.RequestException as e:
        print(f"خطا در کرال کردن صفحه {post_url}: {e}")
        return []
    except Exception as e:
        print(f"خطای غیرمنتظره در کرال کردن: {e}")
        return []

# تابع برای قرار دادن کپشن‌ها زیر عکس‌ها
def add_captions_to_images(content, captions):
    if not captions:
        return content

    # پارس کردن محتوای فید
    soup = BeautifulSoup(content, "html.parser")
    images = soup.find_all("img")  # پیدا کردن همه تگ‌های <img>

    # اگه هیچ عکسی توی محتوا نبود، کپشن‌ها رو به انتها اضافه می‌کنیم
    if not images:
        print("هیچ عکسی توی محتوا پیدا نشد. کپشن‌ها به انتها اضافه می‌شن.")
        return content + "\n" + "\n".join(captions)

    # قرار دادن کپشن‌ها زیر عکس‌ها
    caption_index = 0
    for img in images:
        if caption_index >= len(captions):
            break  # اگه کپشن‌ها تموم شدن، ادامه نمی‌دیم

        # ساخت تگ <figure> اگه وجود نداشته باشه
        parent = img.parent
        if parent.name != "figure":
            figure = soup.new_tag("figure")
            img.wrap(figure)
            parent = img.parent

        # اضافه کردن کپشن به <figure>
        caption_tag = BeautifulSoup(captions[caption_index], "html.parser")
        parent.append(caption_tag)
        caption_index += 1

    # اگه کپشن‌های اضافی موندن، به انتها اضافه می‌کنیم
    if caption_index < len(captions):
        remaining_captions = "\n".join(captions[caption_index:])
        soup.append(BeautifulSoup(remaining_captions, "html.parser"))

    return str(soup)

# گرفتن اخبار از RSS
print("در حال دریافت فید RSS...")
feed = feedparser.parse(RSS_FEED_URL)
if not feed.entries:
    print("هیچ پستی در فید RSS یافت نشد.")
    exit()

latest_post = feed.entries[0]
print(f"جدیدترین پست با عنوان '{latest_post.title}' پیدا شد.")

# کرال کردن کپشن‌ها از صفحه پست
post_link = getattr(latest_post, 'link', None)
if post_link and (post_link.startswith('http://') or post_link.startswith('https://')):
    print(f"در حال کرال کردن کپشن‌ها از {post_link}...")
    additional_captions = crawl_captions(post_link)
    if not additional_captions:
        print("هیچ کپشنی پیدا نشد.")
else:
    print("لینک پست معتبر نیست. کرال کردن کپشن‌ها انجام نشد.")
    additional_captions = []

# آماده‌سازی متن پست
title = latest_post.title
content_html = ""

# ترجمه عنوان
print("در حال ترجمه عنوان...")
try:
    translated_title = translate_with_gemini(title)
    translated_title = translated_title.splitlines()[0]
    print(f"عنوان ترجمه شده: {translated_title}")
except ValueError as e:
    print(f"خطا در ترجمه عنوان: {e}")
    translated_title = title
except Exception as e:
    print(f"خطای غیرمنتظره در ترجمه عنوان: {e}")
    translated_title = title

# اضافه کردن عکس پوستر
thumbnail = ""
if hasattr(latest_post, 'media_content') and isinstance(latest_post.media_content, list) and latest_post.media_content:
    media = latest_post.media_content[0]
    if isinstance(media, dict) and 'url' in media:
        thumbnail_url = media['url']
        if thumbnail_url.startswith('http://') or thumbnail_url.startswith('https://'):
             thumbnail = f
