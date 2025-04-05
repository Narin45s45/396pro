import feedparser
import os
import json
import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import re

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

# تابع جدا کردن و ترجمه متن با حفظ تگ‌ها
def preserve_html_tags(raw_content):
    # جدا کردن تگ‌های figcaption و a
    figcaption_tags = re.findall(r'<figcaption[^>]*>.*?</figcaption>', raw_content, re.DOTALL)
    a_tags = re.findall(r'<a[^>]*>.*?</a>', raw_content, re.DOTALL)
    
    # جایگزینی موقت با placeholder
    temp_content = raw_content
    for i, fig in enumerate(figcaption_tags):
        temp_content = temp_content.replace(fig, f"[[FIG{i}]]")
    for i, a in enumerate(a_tags):
        temp_content = temp_content.replace(a, f"[[A{i}]]")
    
    # ترجمه متن بدون تگ‌ها
    translated_content = translate_with_gemini(temp_content)
    
    # برگرداندن تگ‌ها با ترجمه متن داخلشون
    for i, fig in enumerate(figcaption_tags):
        fig_text = re.sub(r'<[^>]+>', '', fig)  # متن داخل figcaption
        translated_fig_text = translate_with_gemini(fig_text)
        translated_content = translated_content.replace(f"[[FIG{i}]]", f'<figcaption>{translated_fig_text}</figcaption>')
    for i, a in enumerate(a_tags):
        if 'newsbtc.com' in a:
            a_text = re.sub(r'<[^>]+>', '', a)  # متن داخل <a>
            translated_content = translated_content.replace(f"[[A{i}]]", a_text)  # لینک newsbtc خاموش می‌مونه
        else:
            a_text = re.sub(r'<[^>]+>', '', a)
            translated_a_text = translate_with_gemini(a_text)
            translated_content = translated_content.replace(f"[[A{i}]]", f'<a href="{a.split(\'href="\')[1].split(\'"\')[0]}">{translated_a_text}</a>')
    
    return translated_content

# تابع حذف لینک‌های newsbtc (برای اطمینان بیشتر)
def remove_newsbtc_links(text):
    pattern = r'<a\s+[^>]*href=["\']https?://(www\.)?newsbtc\.com[^"\']*["\'][^>]*>(.*?)</a>'
    return re.sub(pattern, r'\2', text)

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

# فقط از content استفاده می‌کنیم
if 'content' in latest_post:
    for item in latest_post.content:
        if 'value' in item:
            value = item['value'].split("Related Reading")[0].strip()
            # وسط‌چین کردن عکس‌های داخل متن
            value = value.replace('<img ', '<img style="display:block;margin-left:auto;margin-right:auto;" ')
            # حذف لینک‌های newsbtc و ترجمه با حفظ تگ‌ها
            value = remove_newsbtc_links(value)
            content += f"<br>{preserve_html_tags(value)}"
            break

# جاستیفای کردن متن
full_content = (
    f'{thumbnail}<br>'
    f'<div style="text-align:justify;direction:rtl;">{content}</div>'
    f'<div style="text-align:right;direction:rtl;">'
    f'<a href="{latest_post.link}">منبع</a>'
    f'</div>'
) if thumbnail else (
    f'<div style="text-align:justify;direction:rtl;">{content}</div>'
    f'<div style="text-align:right;direction:rtl;">'
    f'<a href="{latest_post.link}">منبع</a>'
    f'</div>'
)

link = latest_post.link

# ساخت پست جدید
blog_id = "764765195397447456"
post_body = {
    "kind": "blogger#post",
    "title": translated_title,  # عنوان توی پیش‌نمایش
    "content": full_content
}

# ارسال پست
request = service.posts().insert(blogId=blog_id, body=post_body)
response = request.execute()

print("پست با موفقیت ارسال شد:", response["url"])
