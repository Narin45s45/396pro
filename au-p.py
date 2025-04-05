import feedparser
import os
import json
import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import re

# تنظیمات فید RSS
RSS_FEED_URL = "https://www.newsbtc.com/feed/"

# تنظیمات API Gemini
GEMINI_API_KEY = os.environ.get("GEMAPI")
if not GEMINI_API_KEY:
    raise ValueError("GEMAPI پیدا نشد!")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# گرفتن توکن بلاگر
creds_json = os.environ.get("CREDENTIALS")
if not creds_json:
    raise ValueError("CREDENTIALS پیدا نشد!")
creds = Credentials.from_authorized_user_info(json.loads(creds_json))
service = build("blogger", "v3", credentials=creds)

# تابع ترجمه با Gemini
def translate_with_gemini(text, target_lang="fa"):
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": f"Translate this text to {target_lang}: {text}"}]}],
        "generationConfig": {"temperature": 0.7}
    }
    try:
        response = requests.post(f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", headers=headers, json=payload)
        result = response.json()
        if "candidates" not in result:
            raise ValueError(f"خطا در پاسخ API: {result.get('error', 'مشخصات نامعلوم')}")
        return result["candidates"][0]["content"]["parts"][0]["text"]
    except ValueError as e:
        if "code': 429" in str(e):
            return text
        raise

# تابع حذف لینک‌های newsbtc
def remove_newsbtc_links(text):
    pattern = r'<a\s+[^>]*href=["\']https?://(www\.)?newsbtc\.com[^"\']*["\'][^>]*>(.*?)</a>'
    return re.sub(pattern, r'\2', text)

# تابع جدا کردن و ترجمه محتوا
def translate_content(content):
    # جدا کردن تگ‌های HTML
    parts = re.split(r'(<[^>]+>)', content)
    translated_parts = []
    for part in parts:
        if re.match(r'<[^>]+>', part):  # اگه تگ HTML بود
            translated_parts.append(part)
        else:  # اگه متن بود
            translated_text = translate_with_gemini(part.strip())
            translated_parts.append(translated_text)
    return ''.join(translated_parts)

# تابع اضافه کردن کپشن از alt تصاویر و ترجمه
def add_captions_from_alt(content):
    img_tags = re.findall(r'<img[^>]+>', content)
    print(f"تصاویر پیدا شده: {img_tags}")
    for img in img_tags:
        alt_match = re.search(r'alt=["\'](.*?)["\']', img)
        if alt_match:
            alt_text = alt_match.group(1).strip()
            print(f"متن alt برای تصویر: {alt_text}")
            if alt_text and not re.match(r'[\U0001F600-\U0001F64F]', alt_text):  # اگه alt خالی نیست و ایموجی نیست
                translated_alt = translate_with_gemini(alt_text)
                caption = f'<p styl
