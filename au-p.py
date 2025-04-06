import feedparser
import os
import json
import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import re
from difflib import SequenceMatcher
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import time

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
def translate_with_gemini(text, target_lang="fa", retries=3, delay=5):
    headers = {"Content-Type": "application/json"}
    prompt = f"""
   Only translate the visible text content Here is the text:

    {text}
    """
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7}
    }
    for attempt in range(retries):
        try:
            response = requests.post(f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
            if "candidates" not in result:
                raise ValueError(f"خطا در پاسخ API: {result.get('error', 'مشخصات نامعلوم')}")
            translated_text = result["candidates"][0]["content"]["parts"][0]["text"]
            if translated_text.strip() == text.strip():
                raise ValueError("ترجمه انجام نشد: متن خروجی با متن ورودی یکسانه")
            print(f"ترجمه موفق: {text[:50]}... -> {translated_text[:50]}...")
            return translated_text
        except Exception as e:
            if "429" in str(e) and attempt < retries - 1:  # اگه خطای 429 بود و هنوز تلاش باقی مونده
                print(f"خطای 429: تعداد درخواست‌ها زیاد است. منتظر {delay} ثانیه برای تلاش دوباره...")
                time.sleep(delay)
                delay *= 2  # افزایش تأخیر برای تلاش بعدی
                continue
            print(f"خطا در ترجمه: {e}")
            raise ValueError(f"ترجمه ناموفق: {e}")

# تابع حذف لینک‌های newsbtc
def remove_newsbtc_links(text):
    pattern = r'<a\s+[^>]*href=["\']https?://(www\.)?newsbtc\.com[^"\']*["\'][^>]*>(.*?)</a>'
    return re.sub(pattern, r'\2', text)

# تابع بررسی شباهت دو متن
def similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

# تابع حذف تگ‌های <h1> یا <h2> که شبیه عنوان هستن
def remove_repeated_title(content, title):
    headings = re.findall(r'<h[12]>(.*?)</h[12]>', content)
    for heading in headings:
        if similarity(heading, title) > 0.7:
            content = content.replace(f'<h1>{heading}</h1>', '').replace(f'<h2>{heading}</h2>', '')
    return content

# تابع اطمینان
