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
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro-latest:generateContent"

# گرفتن توکن بلاگر
creds_json = os.environ.get("CREDENTIALS")
if not creds_json:
    raise ValueError("CREDENTIALS پیدا نشد!")
creds = Credentials.from_authorized_user_info(json.loads(creds_json))
service = build("blogger", "v3", credentials=creds)

# تابع تبدیل اعداد لاتین به فارسی
def to_persian_numbers(text):
    persian_nums = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
    return text.translate(persian_nums)

# تابع ترجمه با Gemini
def translate_with_gemini(text, target_lang="fa"):
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": f"Translate this to {target_lang}: {text}"}]}],
        "generationConfig": {"temperature": 0.7}
    }
    response = requests.post(f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", headers=headers, json=payload)
    result = response.json()
    if "candidates" not in result:
        raise ValueError(f"خطا در پاسخ API: {result.get('error', 'مشخصات نامعلوم')}")
    translated_text = result["candidates"][0]["content"]["parts"][0]["text"]
    return to_persian_numbers(translated_text)

# تابع جدا کردن و بازگرداندن تگ‌های HTML
def preserve_html_tags(raw_content):
    # جدا کردن تگ‌های img و h2
    img_tags = re.findall(r'<img[^>]+>', raw_content)
    h2_tags = re.findall(r'<h2[^>]*>.*?</h2>', raw_content, re.DOTALL)
    
    # جایگزینی موقت تگ‌ها با placeholder
    temp_content = raw_content
    for i, img in enumerate(img_tags):
        temp_content = temp_content.replace(img, f"[[IMG{i}]]")
    for i, h2 in enumerate(h2_tags):
        temp_content = temp_content.replace(h2, f"[[H2{i}]]")
    
    # ترجمه متن بدون تگ‌ها
    translated_content = translate_with_gemini(temp_content)
    
    # برگرداندن تگ‌ها
    for i, img in enumerate(img_tags):
        translated_content = translated_content.replace(f"[[IMG{i}]]", img.replace('<img ', '<img style="display:block;margin-left:auto;margin-right:auto;" '))
    for i, h2 in enumerate(h2_tags):
        # فقط متن داخل h2 رو ترجمه می‌کنیم
        h2_text = re.search(r'<h2[^>]*>(.*?)</h2>', h2, re.DOTALL).group(1)
        translated_h2_text = translate_with_gemini(h2_text)
        translated_content = translated_content.replace(f"[[H2{i}]]", f'<h2>{translated_h2_text}</h2>')
    
    return translated_content

# گرفتن اخبار از RSS
feed = feedparser.parse(RSS_FEED_URL)
latest_post = feed.entries[0]

# آماده‌سازی عنوان (ترجمه‌شده، بدون بولد)
title = translate_with_gemini(latest_post.title)

# آماده‌سازی متن پست
content = ""

# اضافه کردن عکس پوستر (وسط‌چین و راست‌چین عنوان)
thumbnail = ""
if hasattr(latest_post, 'media_content'):
    for media in latest_post.media_content:
        if 'url' in media:
            thumbnail = f'<div style="text-align:center;"><img src="{media["url"]}" alt="{title}" style="direction:rtl;"></div>'
            break

# گرفتن محتوا فقط از content و ترجمه با حفظ تگ‌ها
if hasattr(latest_post, 'content') and latest_post.content:
    for item in latest_post.content:
        if 'value' in item:
            raw_content = item['value']
            content = preserve_html_tags(raw_content)  # ترجمه با حفظ تگ‌ها
            break
else:
    content = translate_with_gemini("محتوای اصلی پیدا نشد.")

# جاستیفای و راست‌چین کردن متن با فونت IRANSans
full_content = (
    f'<div style="text-align:justify; direction:rtl; font-family:\'IRANSans\';">'
    f'{title}<br>'  # عنوان بدون بولد
    f'{thumbnail}<br>'
    f'{content}'
    f'</div>'
)

link = latest_post.link

# ساخت پست جدید
blog_id = "764765195397447456"
post_body = {
    "kind": "blogger#post",
    "title": title,  # عنوان ساده
    "content": f'{full_content}<br><a href="{link}" style="font-family:\'IRANSans\';">منبع</a>'
}

# ارسال پست
request = service.posts().insert(blogId=blog_id, body=post_body)
response = request.execute()

print("پست با موفقیت ارسال شد:", response["url"])
