import feedparser
import os
import json
import requests
# from google.oauth2.credentials import Credentials # غیرفعال شد
# from googleapiclient.discovery import build # غیرفعال شد
import re
# import time
from bs4 import BeautifulSoup, NavigableString # Import BeautifulSoup

# تنظیمات فید RSS
RSS_FEED_URL = "https://www.newsbtc.com/feed/"

# تنظیمات API Gemini - غیرفعال شد
# GEMINI_API_KEY = os.environ.get("GEMAPI"); assert GEMINI_API_KEY, "GEMAPI پیدا نشد!"
# GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
# print(f"در حال استفاده از مدل API در آدرس: {GEMINI_API_URL}")

# گرفتن توکن بلاگر - غیرفعال شد
# creds_json = os.environ.get("CREDENTIALS"); assert creds_json, "CREDENTIALS پیدا نشد!"
# creds = Credentials.from_authorized_user_info(json.loads(creds_json))
# service = build("blogger", "v3", credentials=creds)

# تابع ترجمه با Gemini - حذف شد
# def translate_with_gemini(text, target_lang="fa"):
#    ...

# تابع حذف لینک‌های newsbtc (همچنان استفاده می‌شود)
def remove_newsbtc_links(html_content):
    pattern = r'<a\s+[^>]*href=["\']https?://(www\.)?newsbtc\.com[^"\']*["\'][^>]*>(.*?)</a>'
    # حذف کامل تگ <a> که به newsbtc لینک دارد
    return re.sub(pattern, '', html_content, flags=re.IGNORECASE)

# --- پردازش اصلی ---

# گرفتن اخبار از RSS
print("در حال دریافت فید RSS...")
feed = feedparser.parse(RSS_FEED_URL)
if not feed.entries: print("هیچ پستی در فید RSS یافت نشد."); exit()
latest_post = feed.entries[0]
# استفاده از عنوان اصلی (بدون ترجمه)
original_title = latest_post.title
print(f"جدیدترین پست با عنوان '{original_title}' پیدا شد.")

# آماده‌سازی
content_html_untranslated = "[Processing Failed]" # مقدار پیش‌فرض

# اضافه کردن عکس پوستر (بدون نیاز به عنوان ترجمه شده)
thumbnail = ""
if hasattr(latest_post, 'media_content') and isinstance(latest_post.media_content, list) and latest_post.media_content:
    media=latest_post.media_content[0];
    if isinstance(media, dict) and 'url' in media:
        thumbnail_url = media['url'];
        if thumbnail_url.startswith(('http://', 'https://')):
             # استفاده از عنوان اصلی در alt
             thumbnail = f'<div style="text-align:center;"><img src="{thumbnail_url}" alt="{original_title}" style="max-width:100%; height:auto;"></div>'
elif 'links' in latest_post:
     for link_info in latest_post.links:
         if link_info.get('rel') == 'enclosure' and link_info.get('type','').startswith('image/'):
             thumbnail_url = link_info.get('href');
             if thumbnail_url and thumbnail_url.startswith(('http://', 'https://')):
                 # استفاده از عنوان اصلی در alt
                 thumbnail = f'<div style="text-align:center;"><img src="{thumbnail_url}" alt="{original_title}" style="max-width:100%; height:auto;"></div>'; break


# *** پردازش محتوا با BeautifulSoup (فقط استخراج و لاگ، بدون ترجمه) ***
print("شروع پردازش محتوا با BeautifulSoup (فقط استخراج)...")
content_source = None
# *** اصلاح تورفتگی در بلوک if بعدی ***
if 'content' in latest_post and latest_post.content:
    content_source = latest_post.content[0]['value']
elif 'summary' in latest_post:
    content_source = latest_post.summary
elif 'description' in latest_post:
    content_source = latest_post.description

if content_source:
    soup = None
    try:
        # 1. پاکسازی اولیه HTML
        print("--- پاکسازی اولیه HTML...")
        content_cleaned_html = re.split(r'Related Reading|Read Also|See Also', content_source, flags=re.IGNORECASE)[0].strip()
        content_cleaned_html = remove_newsbtc_links(content_cleaned_html)

        # 2. پارس کردن HTML
        print("--- پارس کردن HTML...")
        soup = BeautifulSoup(content_cleaned_html, 'html.parser')
        print(f"--- DEBUG: پارس HTML موفق بود.")
        # print(f"--- DEBUG: ساختار اولیه Soup: {soup.prettify()[:500]}...") # برای بررسی

        # 3. *** پیدا کردن و لاگ کردن محتوای FIGCAPTION ها ***
        print(f"--- جستجو برای {len(soup.find_all('figcaption'))} تگ <figcaption>...")
        found_caption = False
        for i, figcaption in enumerate(soup.find_all('figcaption')):
            found_caption = True
            print(f"--- FIGCAPTION [{i+1}] یافت شد! محتوای کامل تگ:")
            print(str(figcaption))
            # استخراج و چاپ متن خالص داخل آن
            caption_text = figcaption.get_text(" ", strip=True)
            print(f"--- متن خالص استخراج شده از Figcaption [{i+1}]: {caption_text}")
            # پیدا کردن و چاپ لینک‌های داخل آن
            links_in_caption = figcaption.find_all('a')
            if links_in_caption:
                 print(f"--- لینک(های) داخل Figcaption [{i+1}]:")
                 for link in links_in_caption:
                      print(f"  - HREF: {link.get('href')}, Text: {link.get_text(' ', strip=True)}")
            else:
                 print(f"--- لینکی داخل Figcaption [{i+1}] یافت نشد.")
            print("-" * 20) # جداکننده

        if not found_caption:
            print("--- هیچ تگ <figcaption> ای در این پست یافت نشد.")

        # 4. اعمال استایل به عکس‌ها (همچنان مفید است)
        print("--- اعمال استایل به عکس‌ها...")
        for img in soup.find_all('img'):
            img['style'] = f"display:block; margin-left:auto; margin-right:auto; max-width:100%; height:auto; {img.get('style', '')}"
            # می‌توان استایل کپشن را هم اینجا اضافه کرد اگر پیدا شده بود
            # figcaption_sibling = img.find_next_sibling('figcaption')
            # if figcaption_sibling :
            #      figcaption_sibling['style'] = f"text-align:center; font-size:small; direction:rtl; color:#555; margin-top: 5px; {figcaption_sibling.get('style', '')}"


        # 5. استفاده از HTML پردازش شده (ولی ترجمه نشده)
        content_html_untranslated = str(soup)
        print("--- پردازش HTML (بدون ترجمه) کامل شد.")

    except Exception as e:
         print(f"خطای شدید در پردازش محتوا با BeautifulSoup: {e}")
         content_html_untranslated = f"[خطا در پردازش HTML: {e}]" # نمایش خطا در پست
         # raise e # جلوگیری از توقف کامل اجرا

else:
    content_html_untranslated = "[محتوایی برای پردازش یافت نشد.]"
    print("محتوایی برای پردازش یافت نشد.")


# ساختار نهایی پست (با محتوای ترجمه نشده)
print("در حال ساختاردهی پست نهایی (بدون ترجمه)...")
full_content_parts = []
if thumbnail: full_content_parts.append(thumbnail); full_content_parts.append('<br>')
# استفاده از محتوای HTML پردازش شده ولی ترجمه نشده
full_content_parts.append(f'<div style="text-align:justify;direction:rtl;">{content_html_untranslated}</div>')
post_link = getattr(latest_post, 'link', None)
if post_link and post_link.startswith(('http://', 'https://')):
    full_content_parts.append(f'<div style="text-align:right;direction:rtl;margin-top:15px;">')
    full_content_parts.append(f'<a href="{post_link}" target="_blank" rel="noopener noreferrer">منبع</a>')
    full_content_parts.append(f'</div>')
else: print("لینک منبع معتبر یافت نشد.")
full_content = "".join(full_content_parts)


# ساخت و ارسال پست به بلاگر - غیرفعال شد (چون توکن نداریم و هدف فقط تست استخراج است)
blog_id = "764765195397447456" # فقط برای کامل بودن کد
post_body = {
    "kind": "blogger#post",
    "blog": {"id": blog_id},
    "title": original_title, # استفاده از عنوان اصلی
    "content": full_content
}
print("--- بدنه پست آماده شد (ارسال به بلاگر غیرفعال است) ---")
# print(f"--- عنوان: {original_title}")
# print(f"--- محتوا (اولیه): {full_content[:500]}...") # چاپ ابتدای محتوا برای بررسی

# کد ارسال به بلاگر کامنت شد
# print("در حال ارسال پست به بلاگر...")
# try:
#     request = service.posts().insert(blogId=blog_id, body=post_body, isDraft=False)
#     response = request.execute()
#     print("پست با موفقیت ارسال شد:", response.get("url", "URL نامشخص"))
# except Exception as e:
#     print(f"خطای شدید هنگام ارسال پست به بلاگر: {e}")
#     if hasattr(e, 'content'):
#         try: error_details = json.loads(e.content); print(f"جزئیات خطا از API بلاگر: {error_details}")
#         except json.JSONDecodeError: print(f"محتوای خطا (غیر JSON): {e.content}")
#     raise e

print("--- اجرای اسکریپت تست کامل شد ---")
