import feedparser
import os
import json
import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import re
# import time
from bs4 import BeautifulSoup, NavigableString # Import BeautifulSoup

# ... (تنظیمات اولیه و گرفتن توکن بدون تغییر) ...
# تنظیمات فید RSS
RSS_FEED_URL = "https://www.newsbtc.com/feed/"
# تنظیمات API Gemini
GEMINI_API_KEY = os.environ.get("GEMAPI"); assert GEMINI_API_KEY, "GEMAPI پیدا نشد!"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
print(f"در حال استفاده از مدل API در آدرس: {GEMINI_API_URL}")
# گرفتن توکن بلاگر
creds_json = os.environ.get("CREDENTIALS"); assert creds_json, "CREDENTIALS پیدا نشد!"
creds = Credentials.from_authorized_user_info(json.loads(creds_json))
service = build("blogger", "v3", credentials=creds)

# تابع ترجمه با Gemini - با دستور برای تکرار جداکننده
def translate_with_gemini(text, target_lang="fa", separator=""):
    # این تابع حالا متن ترکیبی را می‌گیرد
    if not text or text.isspace():
        return text
        
    headers = {"Content-Type": "application/json"}

    # *** دستور جدید با تاکید بر تکرار دقیق جداکننده ***
    prompt = (
        f"Please translate the following English text segments (separated by '{separator}') into {target_lang} "
        f"with the utmost intelligence and precision. Pay close attention to context and nuance.\n"
        f"VERY IMPORTANT INSTRUCTION: Maintain the exact separator '{separator}' between each translated segment in your output. "
        f"The number of separators in your output MUST match the number of separators in the input.\n"
        f"FURTHER INSTRUCTIONS:\n"
        f"- For technical terms or English words commonly used in the field (like cryptocurrency, finance, technology), "
        f"transliterate them into Persian script (Finglish) instead of translating them. Example: 'Stochastic Oscillator' -> 'اوسیلاتور استوکستیک'. Apply consistently.\n"
        f"- Ensure that any text within quotation marks (\"\") is also accurately translated.\n"
        f"OUTPUT REQUIREMENT: Do not add any explanations, comments, or options. Only return the translated segments separated by the exact separator '{separator}'.\n\n"
        f"English Text Segments with Separator:\n{text}"
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
             "temperature": 0.5 # دمای پایین‌تر ممکن است به دنبال کردن دستورات کمک کند
         }
    }

    print(f"--- ارسال متن ترکیبی برای ترجمه (با جداکننده)...")
    max_retries = 1
    retry_delay = 5
    response = None
    # ... (کد ارسال درخواست، تلاش مجدد و مدیریت خطای پایه مثل قبل) ...
    for attempt in range(max_retries + 1):
        try:
            response = requests.post(f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", headers=headers, json=payload, timeout=90) 
            # print(f"--- کد وضعیت API (تلاش {attempt+1}): {response.status_code}") 
            response.raise_for_status() 
            if response.status_code == 200: break 
        except requests.exceptions.Timeout:
             print(f"--- خطای Timeout در درخواست API (تلاش {attempt+1})")
             if attempt == max_retries: raise ValueError(f"Timeout پس از {max_retries+1} تلاش")
             # time.sleep(retry_delay)
             continue
        except requests.exceptions.RequestException as e:
             print(f"--- خطای شبکه در درخواست API (تلاش {attempt+1}): {e}")
             if attempt == max_retries: raise ValueError(f"خطای شبکه پس از {max_retries+1} تلاش: {e}") from e
             # time.sleep(retry_delay) 
             continue 
        if response.status_code == 429 and attempt < max_retries:
            print(f"--- خطای Rate Limit (429). انتظار...")
            # time.sleep(retry_delay * (attempt + 1)) 
        elif response.status_code != 200 : 
             if attempt == max_retries :
                 error_details = response.text
                 try: error_details = response.json()['error']['message'] 
                 except: pass
                 print(f"--- خطای نهایی API در ترجمه متن ترکیبی") 
                 raise ValueError(f"خطا در درخواست API (تلاش {attempt+1}): کد وضعیت {response.status_code}, پاسخ: {error_details}")

    if response is None or response.status_code != 200: raise ValueError(f"ترجمه پس از {max_retries+1} تلاش ناموفق بود.")
    result = response.json()
    if 'error' in result: raise ValueError(f"خطا در API Gemini: {result['error'].get('message', 'جزئیات نامشخص')}")
    try:
        # ... (بررسی candidates و content مثل قبل) ...
        if not result.get("candidates"):
             feedback = result.get('promptFeedback', {})
             block_reason = feedback.get('blockReason', 'نامشخص')
             raise ValueError(f"API Response without candidates. Block Reason: {block_reason}.")
        candidate = result["candidates"][0]
        content = candidate.get("content")
        if not content or not content.get("parts") or not content["parts"][0].get("text"):
             finish_reason = candidate.get("finishReason", "نامشخص")
             if text and not text.isspace():
                  raise ValueError(f"ترجمه کامل نشد یا خروجی خالی بود. دلیل توقف: {finish_reason}.")
             else: return "" # ورودی خالی، خروجی خالی طبیعی است
        
        translated_text = content["parts"][0]["text"]
        print(f"--- متن ترکیبی ترجمه شده دریافت شد.")
    except (IndexError, KeyError, TypeError, ValueError) as e: 
        print(f"--- خطای پردازش پاسخ API برای متن ترکیبی: {e}")
        raise ValueError(f"ساختار پاسخ API نامعتبر یا خطا در بررسی آن: {e}. پاسخ کامل: {result}") from e
    return translated_text.strip() # متن ترجمه شده ترکیبی را برمی‌گرداند


# تابع حذف لینک‌های newsbtc (بدون تغییر)
def remove_newsbtc_links(html_content):
    pattern = r'<a\s+[^>]*href=["\']https?://(www\.)?newsbtc\.com[^"\']*["\'][^>]*>(.*?)</a>'
    return re.sub(pattern, '', html_content, flags=re.IGNORECASE)

# --- پردازش اصلی ---

# گرفتن اخبار از RSS
print("در حال دریافت فید RSS...")
feed = feedparser.parse(RSS_FEED_URL)
if not feed.entries: print("هیچ پستی در فید RSS یافت نشد."); exit()
latest_post = feed.entries[0]
print(f"جدیدترین پست با عنوان '{latest_post.title}' پیدا شد.")

# آماده‌سازی
title = latest_post.title
content_html = ""
translated_title = title 

# ترجمه عنوان (تک به تک)
print("در حال ترجمه عنوان...")
try:
    if title and not title.isspace():
        # برای عنوان، همچنان از ترجمه تک استفاده می‌کنیم
        translated_title = translate_with_gemini(title, separator=None) # بدون جداکننده بفرست
        translated_title = translated_title.splitlines()[0]
    else: translated_title = "" 
    print(f"عنوان ترجمه شده: {translated_title}")
except Exception as e:
    print(f"خطای غیرمنتظره در ترجمه عنوان: {e}")
    # raise e # توقف اجرا در صورت خطای عنوان

# اضافه کردن عکس پوستر
# ... (مثل قبل) ...
thumbnail = ""
if hasattr(latest_post, 'media_content') and isinstance(latest_post.media_content, list) and latest_post.media_content:
    media=latest_post.media_content[0]; 
    if isinstance(media, dict) and 'url' in media:
        thumbnail_url = media['url']
        if thumbnail_url.startswith(('http://', 'https://')):
             thumbnail = f'<div style="text-align:center;"><img src="{thumbnail_url}" alt="{translated_title}" style="max-width:100%; height:auto;"></div>'
elif 'links' in latest_post:
     for link_info in latest_post.links:
         if link_info.get('rel') == 'enclosure' and link_info.get('type','').startswith('image/'):
             thumbnail_url = link_info.get('href')
             if thumbnail_url and thumbnail_url.startswith(('http://', 'https://')):
                 thumbnail = f'<div style="text-align:center;"><img src="{thumbnail_url}" alt="{translated_title}" style="max-width:100%; height:auto;"></div>'; break


# *** پردازش محتوا با BeautifulSoup (روش ترکیب و درخواست تکرار جداکننده) ***
print("شروع پردازش محتوا با BeautifulSoup (روش تکرار جداکننده)...")
content_source = None
# ... (گرفتن content_source مثل قبل) ...
if 'content' in latest_post and latest_post.content: content_source = latest_post.content[0]['value']
elif 'summary' in latest_post: content_source = latest_post.summary
elif 'description' in latest_post: content_source = latest_post.description

if content_source:
    content_html = content_source # مقدار پیش‌فرض
    soup = None
    
    try:
        # 1. پاکسازی اولیه HTML
        print("--- پاکسازی اولیه HTML...")
        content_cleaned_html = re.split(r'Related Reading|Read Also|See Also', content_source, flags=re.IGNORECASE)[0].strip()
        content_cleaned_html = remove_newsbtc_links(content_cleaned_html)

        # 2. پارس کردن HTML
        print("--- پارس کردن HTML...")
        soup = BeautifulSoup(content_cleaned_html, 'html.parser')

        # 3. استخراج متن‌ها و گره‌ها
        print("--- استخراج متن‌ها و گره‌ها برای ترجمه...")
        texts_to_translate = []
        text_nodes_to_update = [] 
        a_tags_to_update = []     
        separator = "" # جداکننده جدید

        text_parent_tags = ['p', 'li', 'blockquote', 'figcaption', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'span', 'em', 'strong', 'td', 'th']
        # استفاده از string=True
        for element in soup.find_all(string=True): 
            element_text = element.string 
            if not element_text or element_text.isspace(): continue
            is_inside_a = False; curr = element.parent
            while curr:
                if curr.name == 'a': is_inside_a = True; break
                curr = curr.parent
            if not is_inside_a and element.parent.name in text_parent_tags:
                # اطمینان از اینکه خود جداکننده در متن اصلی نیست (خیلی بعید)
                if separator in element_text:
                     print(f"هشدار: جداکننده در متن اصلی یافت شد! متن: {element_text[:50]}...")
                     # جایگزینی موقت جداکننده در متن اصلی
                     element_text = element_text.replace(separator, "---") 
                texts_to_translate.append(element_text)
                text_nodes_to_update.append(element)

        for a_tag in soup.find_all('a'):
            link_text = a_tag.get_text(" ", strip=True)
            if link_text: 
                if separator in link_text:
                     print(f"هشدار: جداکننده در متن لینک یافت شد! متن: {link_text[:50]}...")
                     link_text = link_text.replace(separator, "---") 
                texts_to_translate.append(link_text)
                a_tags_to_update.append(a_tag)

        # 4. ترجمه متن‌های ترکیبی با درخواست تکرار جداکننده
        if texts_to_translate:
            print(f"--- تعداد {len(texts_to_translate)} بخش متنی یافت شد.")
            combined_text = separator.join(texts_to_translate)
            
            # فراخوانی تابع ترجمه که حالا باید جداکننده را برگرداند
            translated_combined_text = translate_with_gemini(combined_text, separator=separator)
            
            # 5. تقسیم پاسخ بر اساس جداکننده
            # استفاده از regex برای تقسیم دقیق‌تر و حذف فضاهای خالی احتمالی اطراف جداکننده
            # translated_segments = translated_combined_text.split(separator)
            translated_segments = re.split(r'\s*' + re.escape(separator) + r'\s*', translated_combined_text)

            print(f"--- تعداد بخش‌های ترجمه شده پس از تقسیم: {len(translated_segments)}")
            
            # 6. بررسی تطابق تعداد و جایگزینی
            if len(translated_segments) == len(texts_to_translate):
                print("--- تعداد بخش‌ها مطابقت دارد. شروع جایگزینی...")
                segment_index = 0
                # جایگزینی متن‌های معمولی
                for node in text_nodes_to_update:
                    if node and hasattr(node, 'replace_with'):
                        node.replace_with(NavigableString(translated_segments[segment_index]))
                    else: print(f"هشدار: گره متن معمولی {segment_index} برای جایگزینی معتبر نبود.");
                    segment_index += 1
                # جایگزینی متن لینک‌ها
                for a_tag in a_tags_to_update:
                    a_tag.clear() 
                    a_tag.append(NavigableString(translated_segments[segment_index]))
                    segment_index += 1
                print("--- جایگزینی متن کامل شد.")

                # 7. اعمال استایل به عکس‌ها
                print("--- اعمال استایل به عکس‌ها...")
                for img in soup.find_all('img'):
                    img['style'] = f"display:block; margin-left:auto; margin-right:auto; max-width:100%; height:auto; {img.get('style', '')}"

                # 8. تبدیل سوپ اصلاح شده به رشته HTML
                content_html = str(soup)
                print("--- پردازش محتوا با BeautifulSoup کامل شد.")

            else:
                # اگر تعداد مطابقت نداشت، یعنی مدل جداکننده را رعایت نکرده
                error_message = f"خطا: عدم تطابق تعداد بخش‌ها! مدل جداکننده را رعایت نکرد. اصلی: {len(texts_to_translate)}, ترجمه شده: {len(translated_segments)}"
                print(error_message)
                print(f"--- متن اصلی ترکیبی (اولیه): {combined_text[:200]}...")
                print(f"--- متن ترجمه شده ترکیبی (دریافتی): {translated_combined_text[:200]}...")
                # استفاده از HTML تمیز شده بدون ترجمه
                content_html = content_cleaned_html 
                # توقف اجرا
                raise ValueError(error_message) 

        else:
            print("--- هیچ متن قابل ترجمه‌ای در محتوا یافت نشد.")
            content_html = soup.prettify() if soup else content_cleaned_html

    except Exception as e:
         print(f"خطای شدید و غیرمنتظره در پردازش محتوا با BeautifulSoup: {e}")
         # خطا را دوباره ایجاد می‌کنیم تا اجرای اکشن متوقف شود
         raise e

else:
    print("محتوایی برای پردازش یافت نشد.")

# ساختار نهایی پست
# ... (مثل قبل) ...
print("در حال ساختاردهی پست نهایی...")
full_content_parts = []
if thumbnail: full_content_parts.append(thumbnail); full_content_parts.append('<br>')
if content_html: full_content_parts.append(f'<div style="text-align:justify;direction:rtl;">{content_html}</div>')
else: full_content_parts.append('<div style="text-align:center;direction:rtl;">[محتوای مقاله یافت نشد یا قابل پردازش نبود]</div>')
post_link = getattr(latest_post, 'link', None)
if post_link and post_link.startswith(('http://', 'https://')):
    full_content_parts.append(f'<div style="text-align:right;direction:rtl;margin-top:15px;">')
    full_content_parts.append(f'<a href="{post_link}" target="_blank" rel="noopener noreferrer">منبع</a>')
    full_content_parts.append(f'</div>')
else: print("لینک منبع معتبر یافت نشد.")
full_content = "".join(full_content_parts)

# ساخت و ارسال پست به بلاگر
# ... (مثل قبل، با raise خطا در صورت مشکل) ...
blog_id = "764765195397447456"
post_body = { "kind": "blogger#post", "blog": {"id": blog_id}, "title": translated_title, "content": full_content }
print("در حال ارسال پست به بلاگر...")
try:
    request = service.posts().insert(blogId=blog_id, body=post_body, isDraft=False)
    response = request.execute()
    print("پست با موفقیت ارسال شد:", response.get("url", "URL نامشخص"))
except Exception as e:
    print(f"خطای شدید هنگام ارسال پست به بلاگر: {e}")
    if hasattr(e, 'content'):
        try: error_details = json.loads(e.content); print(f"جزئیات خطا از API بلاگر: {error_details}")
        except json.JSONDecodeError: print(f"محتوای خطا (غیر JSON): {e.content}")
    raise e
