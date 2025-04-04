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
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"

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
        "contents": [{"parts": [{"text": f"Translate this to {target_lang}: {text}"}]}],
        "generationConfig": {"temperature": 0.7}
    }
    response = requests.post(f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", headers=headers, json=payload)
    result = response.json()
    print("API Response:", json.dumps(result, indent=2))  # پاسخ کامل رو چاپ می‌کنه
    if "candidates" not in result:
        raise ValueError(f"خطا در پاسخ API: {result.get('error', 'مشخصات نامعلوم')}")
    return result["candidates"][0]["content"]["parts"][0]["text"]

# گرفتن اخبار از RSS
feed = feedparser.parse(RSS_FEED_URL)
latest_post = feed.entries[0]

# آماده‌سازی متن پست
title = latest_post.title
content = ""

# ترجمه عنوان
translated_title = translate_with_gemini(title)

# اضافه کردن عکس پوستر
thumbnail = ""
if hasattr(latest_post, 'media_content'):
    for media in latest_post.media_content:
        if 'url' in media:
            thumbnail = f'<div style="text-align:center;"><img src="{media["url"]}" alt="{translated_title}"></div>'
            break

# اضافه کردن و ترجمه description
if hasattr(latest_post, 'description'):
    description = latest_post.description.split("Related Reading")[0].strip()
    content += translate_with_gemini(description)

# اضافه کردن و ترجمه content
if 'content' in latest_post:
    for item in latest_post.content:
        if 'value' in item:
            value = item['value'].split("Related Reading")[0].strip()
            content += f"<br>{translate_with_gemini(value)}"

# جاستیفای کردن متن
full_content = f'{thumbnail}<br><div style="text-align:justify;">{content}</div>' if thumbnail else f'<div style="text-align:justify;">{content}</div>'

link = latest_post.link

# ساخت پست جدید
blog_id = "764765195397447456"
post_body = {
    "kind": "blogger#post",
    "title": translated_title,
    "content": f"{full_content}<br><a href='{link}'>ادامه مطلب</a>"
}

# ارسال پست
request = service.posts().insert(blogId=blog_id, body=post_body)
response = request.execute()

print("پست با موفقیت ارسال شد:", response["url"])
