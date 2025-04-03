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
content = latest_post.description
link = latest_post.link

# ساخت پست جدید
blog_id = "764765195397447456"  # آیدی وبلاگتون رو بذارید
post_body = {
    "kind": "blogger#post",
    "title": title,
    "content": f"{content}<br><a href='{link}'>ادامه مطلب</a>"
}

# ارسال پست به بلاگر
request = service.posts().insert(blogId=blog_id, body=post_body)
response = request.execute()

print("پست با موفقیت ارسال شد:", response["url"])
