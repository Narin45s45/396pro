import feedparser
import os
import json
import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import re
from difflib import SequenceMatcher

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

# تابع بررسی شباهت دو متن
def similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

# تابع حذف تگ‌های <h1> یا <h2> که شبیه عنوان هستن
def remove_repeated_title(content, title):
    headings = re.findall(r'<h[12]>(.*?)</h[12]>', content)
    for heading in headings:
        if similarity(heading, title) > 0.7:  # اگه شباهت بیشتر از 70% بود
            content = content.replace(f'<h1>{heading}</h1>', '').replace(f'<h2>{heading}</h2>', '')
    return content

# تابع اضافه کردن کپشن از تگ <figcaption>
def add_captions_from_figcaption(content):
    # پیدا کردن تمام تگ‌های <figure> که شامل <img> و <figcaption> هستن
    figure_tags = re.findall(r'<figure[^>]*>.*?</figure>', content, re.DOTALL)
    for figure in figure_tags:
        # گرفتن تگ <img> از داخل <figure>
        img_match = re.search(r'<img[^>]+>', figure)
        # گرفتن تگ <figcaption> از داخل <figure>
        figcaption_match = re.search(r'<figcaption[^>]*>(.*?)</figcaption>', figure, re.DOTALL)
        if img_match and figcaption_match:
            img_tag = img_match.group(0)
            caption_text = figcaption_match.group(1).strip()
            # اضافه کردن کپشن زیر تصویر
            new_content = f'{img_tag}<p style="text-align:center;font-style:italic;">{caption_text}</p>'
            # جایگزینی تگ <figure> با تصویر و کپشن
            content = content.replace(figure, new_content)
        elif img_match:
            # اگه <figcaption> نبود، فقط تصویر رو نگه می‌داریم
            content = content.replace(figure, img_match.group(0))
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
            value = remove_repeated_title(value, title)
            value = value.replace('<img ', '<img style="display:block;margin-left:auto;margin-right:auto;" ')
            value = remove_newsbtc_links(value)
            value = ensure_images(value)
            value = add_captions_from_figcaption(value)
            content += f"<br>{value}"
            break

# جاستیفای کردن متن
full_content = (
    f'{thumbnail}<br>'
    f'<div style="text-align:justify;">{content}</div>'
    f'<div style="text-align:right;">'
    f'<a href="{latest_post.link}" target="_blank">Source</a>'
    f'</div>'
) if thumbnail else (
    f'<div style="text-align:justify;">{content}</div>'
    f'<div style="text-align:right;">'
    f'<a href="{latest_post.link}" target="_blank">Source</a>'
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
