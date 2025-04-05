import feedparser
import os
import json
import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import re

# تنظیمات فید RSS
RSS_FEED_URL = "https://www.newsbtc.com/feed/"

# گرفتن توکن بلاگر
creds_json = os.environ.get("CREDENTIALS")
if not creds_json:
    raise ValueError("CREDENTIALS پیدا نشد!")
creds = Credentials.from_authorized_user_info(json.loads(creds_json))
service = build("blogger", "v3", credentials=creds)

# تابع حذف لینک‌های newsbtc
def remove_newsbtc_links(text):
    pattern = r'<a\s+[^>]*href=["\']https?://(www\.)?newsbtc\.com[^"\']*["\'][^>]*>(.*?)</a>'
    return re.sub(pattern, r'\2', text)

# تابع اضافه کردن کپشن از alt تصاویر
def add_captions_from_alt(content):
    img_tags = re.findall(r'<img[^>]+>', content)
    for img in img_tags:
        alt_match = re.search(r'alt=["\'](.*?)["\']', img)
        if alt_match:
            alt_text = alt_match.group(1)
            caption = f'<div style="text-align:center;font-style:italic;">{alt_text}</div>'
            content = content.replace(img, f'{img}{caption}')
    return content

# تابع اطمینان از نمایش همه تصاویر
def ensure_images(content):
    img_tags = re.findall(r'<img[^>]+>', content)
    print(f"تعداد تصاویر توی فید: {len(img_tags)}")
    return content

# گرفتن اخبار از RSS
feed = feedparser.parse(RSS_FEED_URL)
latest_post = feed.entries[0]

# آماده‌سازی متن پست
title = latest_post.title
content = ""

# اضافه کردن عکس پوستر
thumbnail = ""
if hasattr(latest_post, 'media_content'):
    for media in latest_post.media_content:
        if 'url' in media:
            thumbnail = f'<div style="text-align:center;"><img src="{media["url"]}" alt="{title}"></div>'
            break

# فقط از content استفاده می‌کنیم
if 'content' in latest_post:
    for item in latest_post.content:
        if 'value' in item:
            value = item['value'].split("Related Reading")[0].strip()
            print("محتوای خام فید:", value)
            value = value.replace('<img ', '<img style="display:block;margin-left:auto;margin-right:auto;" ')
            value = remove_newsbtc_links(value)
            value = ensure_images(value)
            value = add_captions_from_alt(value)
            content += f"<br>{value}"
            break

# جاستیفای کردن متن
full_content = (
    f'{thumbnail}<br>'
    f'<div style="text-align:justify;">{content}</div>'
    f'<div style="text-align:right;">'
    f'<a href="{latest_post.link}">Source</a>'
    f'</div>'
) if thumbnail else (
    f'<div style="text-align:justify;">{content}</div>'
    f'<div style="text-align:right;">'
    f'<a href="{latest_post.link}">Source</a>'
    f'</div>'
)

link = latest_post.link

# ساخت پست جدید
blog_id = "764765195397447456"
post_body = {
    "kind": "blogger#post",
    "title": title,
    "content": full_content
}

# ارسال پست
request = service.posts().insert(blogId=blog_id, body=post_body)
response = request.execute()

print("پست با موفقیت ارسال شد:", response["url"])
