import feedparser
import os
import json
import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

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

# گرفتن اخبار از RSS
feed = feedparser.parse(RSS_FEED_URL)
latest_post = feed.entries[0]

# آماده‌سازی عنوان (ترجمه‌شده به فارسی)
title = translate_with_gemini(latest_post.title)

# آماده‌سازی متن پست
content = ""

# اضافه کردن عکس پوستر (وسط‌چین)
thumbnail = ""
if hasattr(latest_post, 'media_content'):
    for media in latest_post.media_content:
        if 'url' in media:
            thumbnail = f'<div style="text-align:center;"><img src="{media["url"]}" alt="{title}"></div>'
            break

# اضافه کردن محتوا (فقط یکی از description یا content برای جلوگیری از تکرار)
if hasattr(latest_post, 'content') and latest_post.content:  # اولویت با content
    for item in latest_post.content:
        if 'value' in item:
            value = item['value'].split("Related Reading")[0].strip()
            # وسط‌چین کردن عکس‌های داخل محتوا
            value = value.replace('<img ', '<img style="display:block;margin-left:auto;margin-right:auto;" ')
            content = translate_with_gemini(value)  # ترجمه به فارسی
            break
elif hasattr(latest_post, 'description'):  # اگه content نبود، description
    description = latest_post.description.split("Related Reading")[0].strip()
    # وسط‌چین کردن عکس‌های داخل description
    description = description.replace('<img ', '<img style="display:block;margin-left:auto;margin-right:auto;" ')
    content = translate_with_gemini(description)  # ترجمه به فارسی

# جاستیفای و راست‌چین کردن متن (برای فارسی)
full_content = f'{thumbnail}<br><div style="text-align:justify; direction:rtl;">{content}</div>' if thumbnail else f'<div style="text-align:justify; direction:rtl;">{content}</div>'

link = latest_post.link

# ساخت پست جدید
blog_id = "764765195397447456"
post_body = {
    "kind": "blogger#post",
    "title": title,
    "content": f"{full_content}<br><a href='{link}'>ادامه مطلب</a>"
}

# ارسال پست
request = service.posts().insert(blogId=blog_id, body=post_body)
response = request.execute()

print("پست با موفقیت ارسال شد:", response["url"])
