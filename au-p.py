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
    prompt = f"""
    Translate the following text to Persian (Farsi). Keep all HTML tags, attributes, and code parameters (like style, class, href, etc.) unchanged. Only translate the visible text content, including text inside <blockquote> tags. Do not modify or translate any URLs, code, or attribute values. Here is the text:

    {text}
    """
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
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

# تابع بررسی شباهت دو متن
def similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

# تابع حذف تگ‌های <h1> یا <h2> که شبیه عنوان هستن
def remove_repeated_title(content, title):
    headings = re.findall(r'<h[12]>(.*?)</h[12]>', content)
    for heading in headings:
        if similarity(heading, title) > 0.7:  # اگه شباهت بیشتر از 70% بود
            content = content.replace(f'<h1>{heading}</h1>', '').replace(f'<h2>{heading}</h2>', '')
    return content

# تابع گرفتن نام فایل از URL
def get_filename_from_url(url):
    parsed = urlparse(url)
    return parsed.path.split('/')[-1].split('?')[0]

# تابع کرال کردن کپشن از صفحه وب
def crawl_captions(post_url, images_in_feed):
    captions = {}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        # درخواست به صفحه وب
        response = requests.get(post_url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # پیدا کردن تمام تگ‌های <figure>
        figures = soup.find_all('figure')
        print(f"تعداد تگ‌های <figure> پیدا شده توی صفحه وب: {len(figures)}")
        for figure in figures:
            img = figure.find('img')
            figcaption = figure.find('figcaption')
            if img and figcaption:
                img_src = img.get('src', '')
                caption_text = figcaption.decode_contents().strip()  # نگه داشتن تگ‌های HTML داخل کپشن
                filename = get_filename_from_url(img_src)
                captions[filename] = caption_text
                print(f"کپشن پیدا شده برای {filename}: {caption_text}")

        # تطبیق کپشن‌ها با تصاویر توی فید
        matched_captions = {}
        for img in images_in_feed:
            img_src_match = re.search(r'src=["\'](.*?)["\']', img)
            if img_src_match:
                img_src = img_src_match.group(1)
                filename = get_filename_from_url(img_src)
                for crawled_filename, caption in captions.items():
                    if filename == crawled_filename:
                        matched_captions[img] = caption
                        print(f"تطبیق موفق: {img_src} -> {caption}")
                        break
                else:
                    # اگه کپشن پیدا نشد، از alt استفاده می‌کنیم
                    alt_match = re.search(r'alt=["\'](.*?)["\']', img)
                    if alt_match and alt_match.group(1).strip():
                        alt_text = alt_match.group(1).strip()
                        if not re.match(r'[\U0001F600-\U0001F64F]', alt_text):  # اگه ایموجی نبود
                            matched_captions[img] = alt_text
                            print(f"افت‌بک به alt برای {img_src}: {alt
