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

# استفاده از URL دقیق ارائه شده توسط شما
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
print(f"در حال استفاده از مدل API در آدرس: {GEMINI_API_URL}")

# گرفتن توکن بلاگر
creds_json = os.environ.get("CREDENTIALS")
if not creds_json:
    raise ValueError("CREDENTIALS پیدا نشد!")
creds = Credentials.from_authorized_user_info(json.loads(creds_json))
service = build("blogger", "v3", credentials=creds)

# تابع ترجمه با Gemini - با دستور دقیق‌تر
def translate_with_gemini(text, target_lang="fa"):
    headers = {"Content-Type": "application/json"}
    
    # *** دستور دقیق‌تر برای ترجمه کامل و بدون توضیح اضافه ***
    prompt = (
        f"Translate the following English text accurately and completely into {target_lang}. "
        f"Ensure that any text within quotation marks is also translated. "
        f"Do not add any explanations, comments, or options. Only return the translated text itself.\n\n"
        f"English Text:\n{text}"
    )
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        # "generationConfig": {} # تنظیمات تولید محتوا در صورت نیاز
    }
    
    print(f"ارسال درخواست ترجمه به: {GEMINI_API_URL}")
    response = requests.post(f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", headers=headers, json=payload)
    
    print(f"کد وضعیت پاسخ API: {response.status_code}")

    if response.status_code != 200:
        raise ValueError(f"خطا در درخواست API: کد وضعیت {response.status_code}, پاسخ: {response.text}")

    result = response.json()

    if 'error' in result:
        raise ValueError(f"خطا در API Gemini: {result['error'].get('message', 'جزئیات نامشخص')}")
        
    # بررسی دقیق‌تر ساختار پاسخ برای مدل‌های جدیدتر یا تغییرات احتمالی
    try:
        if not result.get("candidates"):
             # بررسی بازخورد پرامپت در صورت عدم وجود کاندیدا
             feedback = result.get('promptFeedback', {})
             block_reason = feedback.get('blockReason', 'نامشخص')
             safety_ratings = feedback.get('safetyRatings', [])
             raise ValueError(f"API پاسخی بدون کاندیدا برگرداند. دلیل بلاک شدن احتمالی: {block_reason}. رتبه‌بندی ایمنی: {safety_ratings}. پاسخ کامل: {result}")

        # اطمینان از وجود محتوا و پارت‌ها
        content = result["candidates"][0].get("content")
        if not content or not content.get("parts"):
            raise ValueError(f"ساختار 'content' یا 'parts' در پاسخ کاندیدا یافت نشد. پاسخ کامل: {result}")
            
        translated_text = content["parts"][0]["text"]
        
    except (IndexError, KeyError, TypeError) as e:
        raise ValueError(f"ساختار پاسخ API غیرمنتظره بود: {e}. پاسخ کامل: {result}")
        
    # حذف احتمالی فضاهای خالی اضافی در ابتدا یا انتهای پاسخ
    return translated_text.strip()

# تابع حذف لینک‌های newsbtc (بدون تغییر)
def remove_newsbtc_links(text):
    pattern = r'<a\s+[^>]*href=["\']https?://(www\.)?newsbtc\.com[^"\']*["\'][^>]*>(.*?)</a>'
    return re.sub(pattern, r'\2', text, flags=re.IGNORECASE)

# --- بقیه کد (گرفتن فید، پردازش محتوا، ارسال به بلاگر) ---
# (بدون تغییر نسبت به نسخه قبلی)

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
    translated_title = title 
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
    # ممکن است content[0]['value'] شامل HTML باشد
    content_source = latest_post.content[0]['value'] 
elif 'summary' in latest_post:
    content_source = latest_post.summary
elif 'description' in latest_post:
     content_source = latest_post.description

if content_source:
    # برای جلوگیری از ترجمه تگ‌های HTML، بهتر است قبل از ترجمه، متن خالص استخراج شود
    # این بخش نیاز به کتابخانه BeautifulSoup دارد (pip install beautifulsoup4)
    # from bs4 import BeautifulSoup
    # soup = BeautifulSoup(content_source, 'html.parser')
    # text_to_translate = soup.get_text(" ", strip=True) 
    # --- یا اگر می‌خواهید HTML حفظ شود و فقط متن داخل آن ترجمه شود، پیچیده‌تر است ---
    
    # ساده‌سازی فعلی: فرض می‌کنیم ترجمه روی کل HTML خام انجام می‌شود
    text_to_translate = content_source # استفاده از HTML خام برای ترجمه (ممکن است ساختار را بشکند)

    text_to_translate = re.split(r'Related Reading|Read Also|See Also', text_to_translate, flags=re.IGNORECASE)[0].strip()
    # حذف لینک‌ها بهتر است روی متن خام HTML انجام شود
    text_to_translate = remove_newsbtc_links(text_to_translate)
    # وسط‌چین کردن عکس‌ها هم روی HTML خام
    text_to_translate = re.sub(r'<img\s+', '<img style="display:block;margin-left:auto;margin-right:auto;max-width:100%;height:auto;" ', text_to_translate, flags=re.IGNORECASE)
    
    print("در حال ترجمه محتوا...")
    try:
        # ترجمه متن (که ممکن است شامل HTML باشد)
        translated_content_part = translate_with_gemini(text_to_translate)
        processed_content_parts.append(translated_content_part)
        print("ترجمه محتوا انجام شد.")
    except ValueError as e:
        print(f"خطا در ترجمه محتوا: {e}")
        # نمایش محتوای اصلی (شامل HTML) در صورت خطا
        processed_content_parts.append(f"<p><i>[خطا در ترجمه محتوا]</i></p><div style='text-align:left; direction:ltr; font-family:monospace;'>{text_to_translate}</div>") 
    except Exception as e:
        print(f"خطای غیرمنتظره در ترجمه محتوا: {e}")
        processed_content_parts.append(f"<p><i>[خطای غیرمنتظره در ترجمه محتوا]</i></p><div style='text-align:left; direction:ltr; font-family:monospace;'>{text_to_translate}</div>")

else:
    print("محتوایی برای پردازش یافت نشد.")

# توجه: اگر محتوای ترجمه شده شامل HTML باشد، ممکن است نیاز به تمیزکاری بیشتری داشته باشد
content = "<br>".join(processed_content_parts) 

# ساختار نهایی پست
print("در حال ساختاردهی پست نهایی...")
# (بقیه کد ساخت full_content و ارسال پست بدون تغییر)
full_content_parts = []
if thumbnail:
    full_content_parts.append(thumbnail)
    full_content_parts.append('<br>')

if content:
    # ممکن است نیاز باشد تگ‌های <br> اضافی که از join آمده حذف شوند اگر ترجمه خود پاراگراف‌بندی دارد
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
blog_id = "764765195397447456" 
post_body = {
    "kind": "blogger#post",
    "blog": {"id": blog_id},
    "title": translated_title,
    "content": full_content # محتوا شامل HTML ترجمه شده است
}

print("در حال ارسال پست به بلاگر...")
try:
    request = service.posts().insert(blogId=blog_id, body=post_body, isDraft=False)
    response = request.execute()
    print("پست با موفقیت ارسال شد:", response.get("url", "URL نامشخص"))
except Exception as e:
    print(f"خطا هنگام ارسال پست به بلاگر: {e}")
    if hasattr(e, 'content'):
        try:
            error_details = json.loads(e.content)
            print(f"جزئیات خطا از API بلاگر: {error_details}")
        except json.JSONDecodeError:
            print(f"محتوای خطا (غیر JSON): {e.content}")
