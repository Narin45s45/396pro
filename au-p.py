import feedparser
import os
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# تنظیمات فید RSS
RSS_FEED_URL = "https://www.newsbtc.com/feed/"

# گرفتن توکن بلاگر
creds_json = os.environ.get("CREDENTIALS")
if not creds_json:
    raise ValueError("CREDENTIALS پیدا نشد!")
creds = Credentials.from_authorized_user_info(json.loads(creds_json))
service = build("blogger", "v3", credentials=creds)

# گرفتن اخبار از RSS
feed = feedparser.parse(RSS_FEED_URL)
latest_post = feed.entries[0]

# آماده‌سازی متن پست
title = latest_post.title
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
            content = value  # فقط اینو نگه می‌داریم
            break
elif hasattr(latest_post, 'description'):  # اگه content نبود، description
    description = latest_post.description.split("Related Reading")[0].strip()
    # وسط‌چین کردن عکس‌های داخل description
    description = description.replace('<img ', '<img style="display:block;margin-left:auto;margin-right:auto;" ')
    content = description

# جاستیفای کردن متن
full_content = f'{thumbnail}<br><div style="text-align:justify;">{content}</div>' if thumbnail else f'<div style="text-align:justify;">{content}</div>'

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
