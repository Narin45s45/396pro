import feedparser
import requests
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# تنظیمات فید RSS
RSS_FEED_URL = "https://www.newsbtc.com/feed/"

# تنظیمات OAuth برای Blogger
SCOPES = ["https://www.googleapis.com/auth/blogger"]
CLIENT_SECRETS_FILE = "client_secrets.json"  # فایل JSON که از Google Cloud گرفتید

# گرفتن اخبار از RSS
feed = feedparser.parse(RSS_FEED_URL)
latest_post = feed.entries[0]  # آخرین خبر

# آماده‌سازی متن پست
title = latest_post.title
content = latest_post.description
link = latest_post.link

# اتصال به Blogger API
flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
creds = flow.run_local_server(port=0)
service = build("blogger", "v3", credentials=creds)

# ساخت پست جدید
blog_id = "YOUR_BLOG_ID"  # آیدی وبلاگتون رو از تنظیمات بلاگر پیدا کنید
post_body = {
    "kind": "blogger#post",
    "title": title,
    "content": f"{content}<br><a href='{link}'>ادامه مطلب</a>"
}

# ارسال پست به بلاگر
request = service.posts().insert(blogId=blog_id, body=post_body)
response = request.execute()

print("پست با موفقیت ارسال شد:", response["url"])
