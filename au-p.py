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
                caption = f'<p style="text-align:center;direction:rtl;font-style:italic;">{translated_alt}</p>'
                content = content.replace(img, f'{img}{caption}')
        else:
            print("متن alt پیدا نشد برای:", img)
    return content

# تابع اطمینان از نمایش همه تصاویر
def ensure_images(content):
    img_tags = re.findall(r'<img[^>]+>', content)
    print(f"تعداد تصاویر توی فید: {len(img_tags)}")
    return content

# گرفتن اخبار از RSS
feed = feedparser.parse(RSS_FEED_URL)
latest_post = feed.entries[0]

# آماده‌سازی متن پست
title = latest_post.title
content = ""

# ترجمه عنوان
translated_title = translate_with_gemini(title)
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
            value = value.replace('<img ', '<img style="display:block;margin-left:auto;margin-right:auto;" ')
            value = remove_newsbtc_links(value)
            value = ensure_images(value)
            translated_content = translate_content(value)
            content += f"<br>{add_captions_from_alt(translated_content)}"
            break

# جاستیفای کردن متن
full_content = (
    f'{thumbnail}<br>'
    f'<div style="text-align:justify;direction:rtl;">{content}</div>'
    f'<div style="text-align:right;direction:rtl;">'
    f'<a href="{latest_post.link}" target="_blank">منبع</a>'
    f'</div>'
) if thumbnail else (
    f'<div style="text-align:justify;direction:rtl;">{content}</div>'
    f'<div style="text-align:right;direction:rtl;">'
    f'<a href="{latest_post.link}" target="_blank">منبع</a>'
    f'</div>'
)

link = latest_post.link

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
