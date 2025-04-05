import feedparser
import os
import json
import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import re
# import time
from bs4 import BeautifulSoup, NavigableString # Import BeautifulSoup

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

# تابع ترجمه با Gemini - پرامپت ساده‌تر برای ترجمه متن خالص
def translate_with_gemini(text, target_lang="fa"):
    # اگر متن ورودی خالی یا فقط فضای خالی است، ترجمه نکن
    if not text or text.isspace():
        return text
        
    headers = {"Content-Type": "application/json"}

    # *** پرامپت ساده شده برای ترجمه متن خالص ***
    # (دستورالعمل‌های مربوط به HTML حذف شد)
    prompt = (
        f"Please translate the following English text into {target_lang} with the utmost intelligence and precision. "
        f"Pay close attention to context and nuance.\n"
        f"IMPORTANT INSTRUCTION: For technical terms or English words commonly used in the field "
        f"(like cryptocurrency, finance, technology), transliterate them into Persian script (Finglish) "
        f"instead of translating them into a potentially obscure Persian word. "
        f"Example: 'Stochastic Oscillator' should become 'اوسیلاتور استوکستیک'. "
        f"Apply this transliteration rule consistently where appropriate.\n"
        f"Ensure that any text within quotation marks (\"\") is also accurately translated.\n"
        f"OUTPUT REQUIREMENT: Do not add any explanations, comments, or options. Only return the final, high-quality translated text itself.\n\n"
        f"English Text to Translate:\n{text}"
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
             "temperature": 0.5
         }
    }

    # print(f"ارسال درخواست ترجمه برای متن: '{text[:50]}...'") # برای دیباگ
    
    max_retries = 2
    retry_delay = 5
    response = None
    for attempt in range(max_retries + 1):
        response = requests.post(f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", headers=headers, json=payload)
        # print(f"کد وضعیت پاسخ API (تلاش {attempt+1}): {response.status_code}") # کاهش لاگینگ

        if response.status_code == 200:
            break
        elif response.status_code == 429 and attempt < max_retries:
            print(f"خطای Rate Limit (429). منتظر ماندن برای {retry_delay} ثانیه...")
            # time.sleep(retry_delay)
        else:
             if attempt == max_retries or response.status_code != 429:
                print(f"خطای API در ترجمه متن: '{text[:50]}...'") # نمایش متن در صورت خطا
                raise ValueError(f"خطا در درخواست API (تلاش {attempt+1}): کد وضعیت {response.status_code}, پاسخ: {response.text}")

    if response is None or response.status_code != 200:
         raise ValueError(f"ترجمه پس از {max_retries+1} تلاش ناموفق بود.")

    result = response.json()

    if 'error' in result:
        raise ValueError(f"خطا در API Gemini: {result['error'].get('message', 'جزئیات نامشخص')}")

    try:
        if not result.get("candidates"):
             feedback = result.get('promptFeedback', {})
             block_reason = feedback.get('blockReason', 'نامشخص')
             safety_ratings = feedback.get('safetyRatings', [])
             detailed_block_msg = f"API Response without candidates. Block Reason: {block_reason}. Safety Ratings: {safety_ratings}."
             print(detailed_block_msg)
             raise ValueError(detailed_block_msg + f" Full Response: {result}")

        candidate = result["candidates"][0]
        content = candidate.get("content")
        if not content or not content.get("parts") or not content["parts"][0].get("text"):
             finish_reason = candidate.get("finishReason", "نامشخص")
             if finish_reason != "STOP" or not (content and content.get("parts") and content["parts"][0].get("text")):
                  # ممکن است پاسخ خالی برای متن ورودی خالی طبیعی باشد
                  if text and not text.isspace():
                       raise ValueError(f"ترجمه کامل نشد یا محتوای متنی در پاسخ وجود نداشت. دلیل توقف: {finish_reason}. پاسخ: {result}")
                  else: # اگر ورودی خالی بود، خروجی خالی اشکالی ندارد
                       return "" 
        
        translated_text = content["parts"][0]["text"]

    except (IndexError, KeyError, TypeError) as e:
        raise ValueError(f"ساختار پاسخ API غیرمنتظره بود: {e}. پاسخ کامل: {result}")

    return translated_text.strip()


# تابع حذف لینک‌های newsbtc (بدون تغییر)
def remove_newsbtc_links(html_content):
    # این تابع حالا روی شیء سوپ کار نمی‌کند، روی رشته HTML کار می‌کند
    # اگر روی سوپ اعمال شود باید روش تغییر کند
    pattern = r'<a\s+[^>]*href=["\']https?://(www\.)?newsbtc\.com[^"\']*["\'][^>]*>(.*?)</a>'
    # جایگزینی با متن لینک به جای حذف کامل لینک
    # return re.sub(pattern, r'\2', html_content, flags=re.IGNORECASE)
    # یا حذف کامل لینک:
    return re.sub(pattern, '', html_content, flags=re.IGNORECASE)


# --- پردازش اصلی ---

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
content_html = "" # برای نگهداری HTML نهایی محتوا

# ترجمه عنوان (فقط متن، بدون HTML)
print("در حال ترجمه عنوان...")
try:
    translated_title = translate_with_gemini(title)
    translated_title = translated_title.splitlines()[0]
    print(f"عنوان ترجمه شده: {translated_title}")
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

# *** پردازش محتوا با BeautifulSoup ***
print("در حال پردازش محتوا با BeautifulSoup...")
content_source = None
if 'content' in latest_post and latest_post.content:
    content_source = latest_post.content[0]['value']
elif 'summary' in latest_post:
    content_source = latest_post.summary
elif 'description' in latest_post:
     content_source = latest_post.description

if content_source:
    # 1. پاکسازی اولیه HTML (حذف بخش‌های اضافی، حذف لینک‌های خاص)
    content_cleaned_html = re.split(r'Related Reading|Read Also|See Also', content_source, flags=re.IGNORECASE)[0].strip()
    content_cleaned_html = remove_newsbtc_links(content_cleaned_html) # حذف لینک‌های newsbtc

    # 2. پارس کردن HTML تمیز شده
    print("پارس کردن HTML...")
    soup = BeautifulSoup(content_cleaned_html, 'html.parser')

    # 3. استخراج متن‌ها برای ترجمه
    print("استخراج متن برای ترجمه...")
    texts_to_translate = []
    nodes_to_update = [] # ذخیره نودهایی که باید محتوایشان آپدیت شود

    # تگ‌هایی که محتوای متنی آنها باید ترجمه شود
    text_tags = ['p', 'li', 'blockquote', 'figcaption', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'a', 'span', 'em', 'strong', 'td', 'th']
    
    # پیدا کردن تمام تگ‌های متنی و رشته‌های متنی قابل ترجمه
    for element in soup.find_all(text=True): # پیدا کردن تمام گره‌های متنی
        # فقط متن‌هایی که مستقیماً داخل تگ‌های مورد نظر هستند یا متن اصلی (نه داخل script/style)
        if element.parent.name in text_tags and element.strip():
            texts_to_translate.append(element.string)
            nodes_to_update.append(element) # ذخیره گره متن برای جایگزینی بعدی
        # می‌توان شرط‌های دیگری هم برای انواع دیگر متن اضافه کرد

    # 4. ترکیب متن‌ها و ترجمه یکجا (یا در چند بخش اگر خیلی طولانی است)
    if texts_to_translate:
        print(f"تعداد {len(texts_to_translate)} بخش متنی برای ترجمه یافت شد.")
        separator = " |||---||| " # جداکننده منحصر به فرد
        combined_text = separator.join(texts_to_translate)

        print("ارسال متن ترکیبی برای ترجمه...")
        try:
            translated_combined_text = translate_with_gemini(combined_text)
            translated_segments = translated_combined_text.split(separator)

            # 5. جایگزینی متن‌های اصلی با ترجمه‌ها در ساختار سوپ
            if len(translated_segments) == len(nodes_to_update):
                print("جایگزینی متن‌های ترجمه شده در ساختار HTML...")
                for i, node in enumerate(nodes_to_update):
                    # استفاده از replace_with برای جایگزینی گره متنی
                    if node and hasattr(node, 'replace_with'): 
                         node.replace_with(NavigableString(translated_segments[i]))
                    else:
                         print(f"هشدار: امکان جایگزینی گره متن شماره {i} وجود نداشت.")
            else:
                print("خطا: تعداد بخش‌های ترجمه شده با تعداد متن‌های اصلی مطابقت ندارد!")
                print(f"تعداد اصلی: {len(nodes_to_update)}, تعداد ترجمه شده: {len(translated_segments)}")
                # در این حالت، ساختار سوپ را تغییر نمی‌دهیم تا خراب نشود
                # می‌توان متن اصلی را برگرداند یا خطا داد
                content_html = content_cleaned_html # برگرداندن HTML بدون ترجمه
                raise ValueError("عدم تطابق تعداد بخش‌های متن پس از ترجمه.")

        except Exception as e:
             print(f"خطا در فرآیند ترجمه یا جایگزینی متن: {e}")
             # در صورت بروز خطا، HTML اصلی را برمی‌گردانیم
             content_html = content_cleaned_html
             # می‌توان خطا را raise کرد تا فرآیند متوقف شود
             # raise e

    else:
        print("هیچ متن قابل ترجمه‌ای در محتوا یافت نشد.")
        # اگر متنی نبود، همان HTML تمیز شده را استفاده می‌کنیم
        content_html = soup.prettify() if soup else content_cleaned_html


    # 6. اعمال استایل به عکس‌ها و بازسازی نهایی HTML (اگر ترجمه موفق بود)
    if 'translated_segments' in locals() and len(translated_segments) == len(nodes_to_update):
         print("اعمال استایل به عکس‌ها...")
         for img in soup.find_all('img'):
             img['style'] = f"display:block; margin-left:auto; margin-right:auto; max-width:100%; height:auto; {img.get('style', '')}"
             # می‌توان alt تصویر را هم ترجمه کرد اگر نیاز باشد
             # if img.get('alt'):
             #    try: img['alt'] = translate_with_gemini(img['alt'])
             #    except: pass # Ignore alt translation errors

         # بازسازی HTML از ساختار سوپ اصلاح شده
         # استفاده از prettify ممکن است قالب‌بندی ناخواسته اضافه کند، str ساده‌تر است
         content_html = str(soup)
         # یا برای خوانایی بهتر (اما با ریسک تغییرات جزئی در فضاها):
         # content_html = soup.prettify() 
         print("پردازش محتوا با BeautifulSoup کامل شد.")


else:
    print("محتوایی برای پردازش یافت نشد.")


# ساختار نهایی پست
print("در حال ساختاردهی پست نهایی...")
full_content_parts = []

# اضافه کردن تصویر شاخص (اگر وجود دارد)
if thumbnail:
    full_content_parts.append(thumbnail)
    full_content_parts.append('<br>')

# اضافه کردن محتوای اصلی پردازش شده با BeautifulSoup
if content_html:
    full_content_parts.append(f'<div style="text-align:justify;direction:rtl;">{content_html}</div>')
else:
     full_content_parts.append('<div style="text-align:center;direction:rtl;">[محتوای مقاله یافت نشد یا قابل پردازش نبود]</div>')

# اضافه کردن لینک منبع
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
    "content": full_content
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
