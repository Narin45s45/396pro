import feedparser
import os
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# تنظیمات فید RSS
RSS_FEED_URL = "https://www.newsbtc.com/feed/"

# گرفتن توکن از متغیر محیطی
creds_json = os.environ.get("CREDENTIALS")
if not creds_json:
    raise ValueError("CREDENTIALS پیدا نشد!")

# ساخت Credentials
creds = Credentials.from_authorized_user_info(json.loads(creds_json))

# اتصال به Blogger API
service = build("blogger", "v3", credentials=creds)

# گرفتن اخبار از RSS
feed = feedparser.parse(RSS_FEED_URL)
latest_post = feed.entries[0]  # آخرین خبر

# آماده‌سازی متن پست
title = latest_post.title
content = ""

# اضافه کردن description (اگه تگ <img> داشته باشه، خودش میاد)
if hasattr(latest_post, 'description'):
    content += latest_post.description

# اضافه کردن محتوای کامل (اگه توی فید باشه)
if 'content' in latest_post:
    for item in latest_post.content:
        if 'value' in item:
            content += f"<br>{item['value']}"

# اضافه کردن تصاویر از media_content (مثل پوستر)
if hasattr(latest_post, 'media_content'):
    for media in latest_post.media_content:
        if 'url' in media:
            content += f'<br><img src="{media["url"]}" alt="{title}">'

link = latest_post.link

# ساخت پست جدید
blog_id = "YOUR_BLOG_ID"  # آیدی وبلاگتون
post_body = {
    "kind": "blogger#post",
    "title": title,
    "content": f"{content}<br><a href='{link}'>ادامه مطلب</a>"
}

# ارسال پست به بلاگر
request = service.posts().insert(blogId=blog_id, body=post_body)
response = request.execute()

print("پست با موفقیت ارسال شد:", response["url"])
