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
        "contents": [{"parts": [{"text": f"Translate all plain text to {target_lang}, preserving all HTML tags exactly as they are, including text inside <blockquote> and other tags: {text}"}]}],
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

# تابع حذف تگ‌های <h2> که عنوان رو تکرار می‌کنن
def remove_repeated_title(content, title):
    # فرض می‌کنیم عنوان توی <h2> یا <h1> تکرار شده
    pattern = r'<h[12]>[^<]*' + re.escape(title) + '[^<]*</h[12]>'
    return re.sub(pattern, '', content, flags=re.IGNORECASE)

# تابع اضافه کردن کپشن از alt تصاویر
def add_captions_from_alt(content):
    # پیدا کردن همه تگ‌های <img>
    img_tags = re.findall(r'<img[^>]+>', content)
    for img in img_tags:
        # گرفتن متن alt
        alt_match = re.search(r'alt=["\'](.*?)["\']', img)
        if alt_match:
            alt_text = alt_match.group(1)
            # ترجمه متن alt
            translated_alt = translate_with_gemini(alt_text)
            # اضافه کردن کپشن زیر تصویر
            caption = f'<div style="text-align:center;direction:rtl;font-style:italic;">{translated_alt}</div>'
            content = content.replace(img, f'{img}{caption}')
    return content

# گرفتن اخبار از RSS
feed = feedparser.parse(RSS_FEED_URL)
latest_post = feed.entries[0]

# آماده‌سازی متن پست
title = latest_post.title
content = ""

# ترجمه عنوان
translated_title = translate_with_gemini(title)
# حذف تگ‌های احتمالی از عنوان
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
            # چاپ خام محتوا برای دیباگ
            print("محتوای خام فید:", value)
            # حذف تگ‌های <h2> که عنوان رو تکرار می‌کنن
            value = remove_repeated_title(value, title)
            # وسط‌چین کردن عکس‌های داخل متن
            value = value.replace('<img ', '<img style="display:block;margin-left:auto;margin-right:auto;" ')
            # حذف لینک‌های newsbtc
            value = remove_newsbtc_links(value)
            # ترجمه با حفظ تگ‌ها
            translated_content = translate_with_gemini(value)
            # اضافه کردن کپشن از alt تصاویر
            content += f"<br>{add_captions_from_alt(translated_content)}"
            break

# جاستیفای کردن متن
full_content = (
    f'{thumbnail}<br>'
    f'<div style="text-align:justify;direction:rtl;">{content}</div>'
    f'<div style="text-align:right;direction:rtl;">'
    f'<a href="{latest_post.link}">منبع</a>'
    f'</div>'
) if thumbnail else (
    f'<div style="text-align:justify;direction:rtl;">{content}</div>'
    f'<div style="text-align:right;direction:rtl;">'
    f'<a href="{latest_post.link}">منبع</a>'
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
