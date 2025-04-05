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

# *** استفاده از URL دقیق ارائه شده توسط شما ***
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
print(f"در حال استفاده از مدل API در آدرس: {GEMINI_API_URL}") # برای تایید URL

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
        # "generationConfig": {} # می‌توانید پارامترهای پیکربندی را در صورت نیاز اضافه کنید
    }
    
    print(f"ارسال درخواست ترجمه به: {GEMINI_API_URL}") # لاگ کردن قبل از درخواست
    response = requests.post(f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", headers=headers, json=payload)
    
    print(f"کد وضعیت پاسخ API: {response.status_code}") # لاگ کردن کد وضعیت
    # print(f"پاسخ خام API: {response.text}") # برای دیباگ دقیق‌تر (در صورت نیاز از کامنت خارج کنید)

    # بررسی اولیه کد وضعیت HTTP
    if response.status_code != 200:
        raise ValueError(f"خطا در درخواست API: کد وضعیت {response.status_code}, پاسخ: {response.text}")

    result = response.json()

    # بررسی خطاهای مشخص شده در پاسخ JSON
    if 'error' in result:
        raise ValueError(f"خطا در API Gemini: {result['error'].get('message', 'جزئیات نامشخص')}")
        
    if "candidates" not in result or not result["candidates"]:
        error_details = result.get('promptFeedback', {}).get('blockReason', 'دلیل نامشخص')
        error_message = f"پاسخ نامعتبر از API Gemini. دلیل احتمالی: {error_details}. پاسخ کامل: {result}"
        print(error_message)
        raise ValueError(error_message)
        
    try:
        translated_text = result["candidates"][0]["content"]["parts"][0]["text"]
    except (IndexError, KeyError) as e:
        raise ValueError(f"ساختار پاسخ API غیرمنتظره بود: {e}. پاسخ کامل: {result}")
        
    return translated_text

# تابع حذف لینک‌های newsbtc
def remove_newsbtc_links(text):
    pattern = r'<a\s+[^>]*href=["\']https?://(www\.)?newsbtc\.com[^"\']*["\'][^>]*>(.*?)</a>'
    return re.sub(pattern, r'\2', text, flags=re.IGNORECASE)

# --- بقیه کد (گرفتن فید، پردازش محتوا، ارسال به بلاگر) ---
# (بدون تغییر نسبت به نسخه قبلی که بهبودها را داشت)

# گرفتن اخبار از RSS
print("در حال دریافت فید RSS...")
feed = feedparser.parse(RSS_FEED_URL)
if not feed.entries:
    print("هیچ پستی در فید RSS یافت نشد.")
    exit()

latest_post = feed.entries[0]
print(f"جدیدترین پست با عنوان '{latest_post.title}' پیدا شد.")

# آماده‌سازی متن پست
title = latest_post.title
content = ""

# ترجمه عنوان
print("در حال ترجمه عنوان...")
try:
    translated_title = translate_with_gemini(title)
    print("ترجمه عنوان انجام شد.")
except ValueError as e:
    print(f"خطا در ترجمه عنوان: {e}")
    translated_title = title # استفاده از عنوان اصلی در صورت خطا
except Exception as e:
    print(f"خطای غیرمنتظره در ترجمه عنوان: {e}")
    translated_title = title

# اضافه کردن عکس پوستر
thumbnail = ""
# (کد پیدا کردن تصویر بدون تغییر)
if hasattr(latest_post, 'media_content') and isinstance(latest_post.media_content, list) and latest_post.media_content:
    media = latest_post.media_content[0]
    if isinstance(media, dict) and 'url' in media:
        thumbnail_url = media['url']
        if thumbnail_url.startswith('http://') or thumbnail_url.startswith('https://'):
             thumbnail = f'<div style="text-align:center;"><img src="{thumbnail_url}" alt="{translated_title}" style="max-width:100%; height:auto;"></div>'
        else:
            print(f"URL تصویر نامعتبر یافت شد: {thumbnail_url}")
elif 'links' in latest_post:
     for link_info in latest_post.links:
         if link_info.get('rel') == 'enclosure' and link_info.get('type', '').startswith('image/'):
             thumbnail_url = link_info.get('href')
             if thumbnail_url and (thumbnail_url.startswith('http://') or thumbnail_url.startswith('https://')):
                 thumbnail = f'<div style="text-align:center;"><img src="{thumbnail_url}" alt="{translated_title}" style="max-width:100%; height:auto;"></div>'
                 break

# پردازش محتوا
print("در حال پردازش محتوا...")
processed_content_parts = []
content_source = None
if 'content' in latest_post and latest_post.content:
    content_source = latest_post.content[0]['value']
elif 'summary' in latest_post:
    content_source = latest_post.summary
elif 'description' in latest_post:
     content_source = latest_post.description

if content_source:
    content_source = re.split(r'Related Reading|Read Also|See Also', content_source, flags=re.IGNORECASE)[0].strip()
    content_source = re.sub(r'<img\s+', '<img style="display:block;margin-left:auto;margin-right:auto;max-width:100%;height:auto;" ', content_source, flags=re.IGNORECASE)
    content_source = remove_newsbtc_links(content_source)

    print("در حال ترجمه محتوا...")
    try:
        # اگر محتوا خیلی طولانی است، ممکن است نیاز به تقسیم آن باشد
        # در اینجا فرض می‌کنیم کل محتوا در یک درخواست قابل ترجمه است
        translated_content_part = translate_with_gemini(content_source)
        processed_content_parts.append(translated_content_part)
        print("ترجمه محتوا انجام شد.")
    except ValueError as e:
        print(f"خطا در ترجمه محتوا: {e}")
        processed_content_parts.append(f"<p><i>[خطا در ترجمه محتوا]</i></p><div style='text-align:left; direction:ltr; font-family:monospace;'>{content_source}</div>") # نمایش محتوای اصلی
    except Exception as e:
        print(f"خطای غیرمنتظره در ترجمه محتوا: {e}")
        processed_content_parts.append(f"<p><i>[خطای غیرمنتظره در ترجمه محتوا]</i></p><div style='text-align:left; direction:ltr; font-family:monospace;'>{content_source}</div>")

else:
    print("محتوایی برای پردازش یافت نشد.")

content = "<br>".join(processed_content_parts)

# ساختار نهایی پست
print("در حال ساختاردهی پست نهایی...")
full_content_parts = []
if thumbnail:
    full_content_parts.append(thumbnail)
    full_content_parts.append('<br>')

if content:
    full_content_parts.append(f'<div style="text-align:justify;direction:rtl;">{content}</div>')
else:
     full_content_parts.append('<div style="text-align:center;direction:rtl;">[محتوای مقاله یافت نشد یا قابل پردازش نبود]</div>')

post_link = getattr(latest_post, 'link', None)
if post_link and (post_link.startswith('http://') or post_link.startswith('https://')):
    full_content_parts.append(f'<div style="text-align:right;direction:rtl;margin-top:15px;">')
    full_content_parts.append(f'<a href="{post_link}" target="_blank" rel="noopener noreferrer">منبع</a>')
    full_content_parts.append(f'</div>')
else:
    print("لینک منبع معتبر یافت نشد.")

full_content = "".join(full_content_parts)

# ساخت و ارسال پست به بلاگر
blog_id = "764765195397447456" # مطمئن شوید این ID درست است
post_body = {
    "kind": "blogger#post",
    "blog": {"id": blog_id},
    "title": translated_title,
    "content": full_content
}

print("در حال ارسال پست به بلاگر...")
try:
    request = service.posts().insert(blogId=blog_id, body=post_body, isDraft=False)
    response = request.execute()
    print("پست با موفقیت ارسال شد:", response.get("url", "URL نامشخص"))
except Exception as e:
    # چاپ جزئیات بیشتر در صورت خطای API بلاگر
    print(f"خطا هنگام ارسال پست به بلاگر: {e}")
    # اگر خطا از نوع googleapiclient.errors.HttpError باشد، جزئیات بیشتری دارد
    if hasattr(e, 'content'):
        try:
            error_details = json.loads(e.content)
            print(f"جزئیات خطا از API بلاگر: {error_details}")
        except json.JSONDecodeError:
            print(f"محتوای خطا (غیر JSON): {e.content}")
