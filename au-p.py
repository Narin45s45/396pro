import feedparser
import os
import json
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

# تنظیمات فید RSS
RSS_FEED_URL = "https://www.newsbtc.com/feed/"

# تنظیمات OAuth برای Blogger
SCOPES = ["https://www.googleapis.com/auth/blogger"]

# گرفتن اطلاعات از متغیر محیطی
client_secrets_json = os.environ.get("CLIENT_SECRETS")
if not client_secrets_json:
    raise ValueError("CLIENT_SECRETS پیدا نشد!")

# تبدیل JSON به دیکشنری
client_config = json.loads(client_secrets_json)

# اتصال به Blogger API
flow = Flow.from_client_config(client_config, SCOPES)
flow.redirect_uri = "http://localhost"  # برای تست کافیه
creds = flow.run_local_server(port=0)
service = build("blogger", "v3", credentials=creds)

# گرفتن اخبار از RSS
feed = feedparser.parse(RSS_FEED_URL)
latest_post = feed.entries[0]  # آخرین خبر

# آماده‌سازی متن پست
title = latest_post.title
content = latest_post.description
link = latest_post.link

# ساخت پست جدید
blog_id = "YOUR_BLOG_ID"  # آیدی وبلاگتون رو بذارید
post_body = {
    "kind": "blogger#post",
    "title": title,
    "content": f"{content}<br><a href='{link}'>ادامه مطلب</a>"
}

# ارسال پست به بلاگر
request = service.posts().insert(blogId=blog_id, body=post_body)
response = request.execute()

print("پست با موفقیت ارسال شد:", response["url"])
