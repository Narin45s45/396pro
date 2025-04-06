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
    Translate the following text to Persian (Farsi). Do not modify any HTML tags, attributes, or code parameters (like style, class, href, etc.). Only translate the visible text content. Here is the text:

    {text}
    """
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7}
    }
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
        print(f"خطا در ترجمه: {e}")
        raise ValueError(f"ترجمه ناموفق: {e}")

# تابع جدا کردن و ترجمه محتوا
def translate_content(content):
    parts = re.split(r'(<[^>]+>)', content)
    translated_parts = []
    for part in parts:
        if re.match(r'<[^>]+>', part):
            translated_parts.append(part)
        else:
            if part.strip():
                translated_text = translate_with_gemini(part.strip())
                translated_parts.append(translated_text)
            else:
                translated_parts.append(part)
    return ''.join(translated_parts)

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

# تابع اطمینان از بولد بودن تگ‌های <h2>
def ensure_h2_bold(content):
    h2_tags = re.findall(r'<h2[^>]*>(.*?)</h2>', content)
    for h2_content in h2_tags:
        old_h2 = f'<h2>{h2_content}</h2>'
        new_h2 = f'<h2 style="font-weight: bold;">{h2_content}</h2>'
        content = content.replace(old_h2, new_h2)
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
        response = requests.get(post_url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        figures = soup.find_all('figure')
        print(f"تعداد تگ‌های <figure> پیدا شده توی صفحه وب: {len(figures)}")
        for figure in figures:
            img = figure.find('img')
            figcaption = figure.find('figcaption')
            if img and figcaption:
                img_src = img.get('src', '')
                caption_text = figcaption.decode_contents().strip()
                filename = get_filename_from_url(img_src)
                captions[filename] = caption_text
                print(f"کپشن پیدا شده برای {filename}: {caption_text}")
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
                    print(f"کپشن برای {img_src} پیدا نشد")
        return matched_captions
    except Exception as e:
        print(f"خطا در کرال کردن کپشن‌ها: {e}")
        return {}

# تابع اضافه کردن کپشن‌های کرال‌شده
def add_crawled_captions(content, captions):
    for img, caption in captions.items():
        translated_caption = translate_content(caption)
        new_content = f'{img}<p style="text-align:center;font-style:italic;">{translated_caption}</p>'
        content = content.replace(img, new_content)
    return content

# تابع اطمینان از نمایش همه تصاویر
def ensure_images(content):
    img_tags = re.findall(r'<img[^>]+>', content)
    print(f"تعداد تصاویر توی فید: {len(img_tags)}")
    return content, img_tags

# گرفتن اخبار از RSS
feed = feedparser.parse(RSS_FEED_URL)
latest_post = feed.entries[0]

# آماده‌سازی متن پست
title = latest_post.title
content = ""

# ترجمه عنوان
translated_title = translate_content(title)
translated_title = re.sub(r'<[^>]+>', '', translated_title)

# اضافه کردن عکس پوستر
thumbnail = ""
if hasattr(latest_post, 'media_content'):
    for media in latest_post.media_content:
        if 'url' in media:
            thumbnail = f'<div style="text-align:center;"><img src="{media["url"]}" alt="{translated_title}"></div>'
            break

# فقط از content استفاده می‌کنیم
if 'content' in latest_post:
    for item in latest_post.content:
        if 'value' in item:
            value = item['value'].split("Related Reading")[0].strip()
            print("محتوای خام فید:", value)
            value = remove_repeated_title(value, title)
            value = value.replace('<img ', '<img style="display:block;margin-left:auto;margin-right:auto;" ')
            value = remove_newsbtc_links(value)
            value = ensure_h2_bold(value)
            value, images = ensure_images(value)
            captions = crawl_captions(latest_post.link, images)
            translated_value = translate_content(value)
            translated_content = add_crawled_captions(translated_value, captions)
            content += f"<br>{translated_content}"
            break

# جاستیفای کردن متن
full_content = (
    f'{thumbnail}<br>'
    f'<div style="text-align:justify;">{content}</div>'
    f'<div style="text-align:right;">'
    f'<a href="{latest_post.link}" target="_blank">Source</a>'
    f'</div>'
) if thumbnail else (
    f'<div style="text-align:justify;">{content}</div>'
    f'<div style="text-align:right;">'
    f'<a href="{latest_post.link}" target="_blank">Source</a>'
    f'</div>'
)

# ساخت پست جدید
blog_id = "764765195397447456"
post_body = {
    "kind": "blogger#post",
    "title": translated_title,
    "content": full_content
}

# ارسال پست
request = service.posts().insert(blogId=blog_id, body=post_body)
response = request.execute()

print("پست با موفقیت ارسال شد:", response["url"])
