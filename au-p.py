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
    return result["candidates"][0]["content"]["parts"][0]["text"]

# گرفتن اخبار از RSS
feed = feedparser.parse(RSS_FEED_URL)
latest_post = feed.entries[0]

# آماده‌سازی عنوان (کامل و ترجمه‌شده)
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

# گرفتن محتوا از content و ترجمه
if hasattr(latest_post, 'content') and latest_post.content:
    for item in latest_post.content:
        if 'value' in item:
            content = item['value']
            # وسط‌چین کردن عکس‌ها
            content = content.replace('<img ', '<img style="display:block;margin-left:auto;margin-right:auto;" ')
            content = translate_with_gemini(content)  # ترجمه کل محتوا
            break
else:
    content = translate_with_gemini("محتوای اصلی پیدا نشد.")

# اضافه کردن فقط جمله آخر از description اگه توی content نباشه
if hasattr(latest_post, 'description'):
    description = latest_post.description
    content_text = " ".join(content.replace('<', ' <').split()).replace('>', '').strip()
    if "Featured image" in description and "Featured image" not in content_text:
        last_sentence = description[description.find("Featured image"):].strip()
        translated_last_sentence = translate_with_gemini(last_sentence)
        content += f"<br><p>{translated_last_sentence}</p>"

# راست‌چین کردن متن
full_content = f'{thumbnail}<br><div style="text-align:right; direction:rtl;">{content}</div>' if thumbnail else f'<div style="text-align:right; direction:rtl;">{content}</div>'

link = latest_post.link

# ساخت پست جدید
blog_id = "764765195397447456"
post_body = {
    "kind": "blogger#post",
    "title": title,
    "content": f'{full_content}<br><a href="{link}" style="font-family: \'IRANSansfanum\';">منبع</a>'
}

# ارسال پست
request = service.posts().insert(blogId=blog_id, body=post_body)
response = request.execute()

print("پست با موفقیت ارسال شد:", response["url"])
