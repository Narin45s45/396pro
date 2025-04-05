import feedparser
import os
import json
import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import re
import time # Import time for sleep
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

# تابع ترجمه با Gemini (بدون تغییر)
def translate_with_gemini(text, target_lang="fa"):
    # ... (کد کامل تابع مثل نسخه قبل) ...
    if not text or text.isspace(): return text
    headers = {"Content-Type": "application/json"}
    prompt = (
        f"Please translate the following English text into {target_lang} with the utmost intelligence and precision. ... " # (پرامپت کامل مثل قبل)
        f"English Text to Translate:\n{text}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.5}
    }
    print(f"--- ارسال برای ترجمه: '{text[:70]}...'")
    max_retries = 1; retry_delay = 3; response = None
    for attempt in range(max_retries + 1):
        try:
            response = requests.post(f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", headers=headers, json=payload, timeout=90) 
            response.raise_for_status() 
            if response.status_code == 200: break 
        except requests.exceptions.Timeout:
             print(f"--- خطای Timeout (تلاش {attempt+1})")
             if attempt == max_retries: raise ValueError(f"Timeout پس از {max_retries+1} تلاش")
             time.sleep(retry_delay); continue
        except requests.exceptions.RequestException as e:
             print(f"--- خطای شبکه (تلاش {attempt+1}): {e}")
             if attempt == max_retries: raise ValueError(f"خطای شبکه پس از {max_retries+1} تلاش: {e}") from e
             time.sleep(retry_delay); continue 
        if response.status_code == 429 and attempt < max_retries:
            wait_time = retry_delay * (attempt + 2) 
            print(f"--- خطای Rate Limit (429). انتظار {wait_time} ثانیه...")
            time.sleep(wait_time) 
        elif response.status_code != 200 : 
             if attempt == max_retries :
                 error_details = response.text; 
                 try: error_details = response.json()['error']['message'] 
                 except: pass
                 print(f"--- خطای نهایی API در ترجمه متن: '{text[:70]}...'") 
                 raise ValueError(f"خطا در درخواست API (تلاش {attempt+1}): کد وضعیت {response.status_code}, پاسخ: {error_details}")
    if response is None or response.status_code != 200: raise ValueError(f"ترجمه پس از {max_retries+1} تلاش ناموفق بود.")
    result = response.json(); 
    if 'error' in result: raise ValueError(f"خطا در API Gemini: {result['error'].get('message', 'جزئیات نامشخص')}")
    try:
        if not result.get("candidates"):
             feedback = result.get('promptFeedback', {}); block_reason = feedback.get('blockReason', 'نامشخص')
             raise ValueError(f"API Response without candidates. Block Reason: {block_reason}.")
        candidate = result["candidates"][0]; content = candidate.get("content")
        if not content or not content.get("parts") or not content["parts"][0].get("text"):
             finish_reason = candidate.get("finishReason", "نامشخص")
             if text and not text.isspace() and finish_reason == "STOP":
                 print(f"--- هشدار: ترجمه متنی برای '{text[:50]}...' برنگرداند (خروجی خالی).")
                 return "" 
             elif text and not text.isspace(): raise ValueError(f"ترجمه کامل نشد یا خروجی خالی بود. دلیل توقف: {finish_reason}.")
             else: return "" 
        translated_text = content["parts"][0]["text"]
    except (IndexError, KeyError, TypeError, ValueError) as e: 
        print(f"--- خطای پردازش پاسخ API برای متن '{text[:50]}...': {e}")
        raise ValueError(f"ساختار پاسخ API نامعتبر یا خطا در بررسی آن: {e}. پاسخ کامل: {result}") from e
    return translated_text.strip()


# تابع حذف لینک‌های newsbtc (بدون تغییر)
def remove_newsbtc_links(html_content):
    pattern = r'<a\s+[^>]*href=["\']https?://(www\.)?newsbtc\.com[^"\']*["\'][^>]*>(.*?)</a>'
    return re.sub(pattern, '', html_content, flags=re.IGNORECASE)

# --- پردازش اصلی ---

# گرفتن اخبار از RSS
# ... (مثل قبل) ...
print("در حال دریافت فید RSS...")
feed = feedparser.parse(RSS_FEED_URL)
if not feed.entries: print("هیچ پستی در فید RSS یافت نشد."); exit()
latest_post = feed.entries[0]
print(f"جدیدترین پست با عنوان '{latest_post.title}' پیدا شد.")

# آماده‌سازی
title = latest_post.title
content_html = ""
translated_title = title 

# ترجمه عنوان
# ... (مثل قبل) ...
print("در حال ترجمه عنوان...")
try:
    if title and not title.isspace():
        translated_title = translate_with_gemini(title) 
        translated_title = translated_title.splitlines()[0]
    else: translated_title = "" 
    print(f"عنوان ترجمه شده: {translated_title}")
except Exception as e:
    print(f"خطای غیرمنتظره در ترجمه عنوان: {e}")

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

# *** پردازش محتوا با BeautifulSoup (شناسایی کپشن <p>) ***
print("شروع پردازش محتوا با BeautifulSoup (شناسایی کپشن p)...")
content_source = None
# ... (گرفتن content_source مثل قبل) ...
if 'content' in latest_post and latest_post.content: content_source = latest_post.content[0]['value']
elif 'summary' in latest_post: content_source = latest_post.summary
elif 'description' in latest_post: content_source = latest_post.description

if content_source:
    content_html = content_source 
    soup = None
    
    try:
        # 1. پاکسازی اولیه HTML
        print("--- پاکسازی اولیه HTML...")
        content_cleaned_html = re.split(r'Related Reading|Read Also|See Also', content_source, flags=re.IGNORECASE)[0].strip()
        content_cleaned_html = remove_newsbtc_links(content_cleaned_html)

        # 2. پارس کردن HTML
        print("--- پارس کردن HTML...")
        soup = BeautifulSoup(content_cleaned_html, 'html.parser')

        # *** مرحله جدید: شناسایی و جداسازی کپشن‌های احتمالی (<p> بعد از <img>) ***
        print("--- جستجو برای کپشن‌های احتمالی (<p> یا <figcaption>)...")
        caption_tags_to_process = [] # List of (tag, original_text)
        processed_caption_elements = set() # نگهداری تگ‌هایی که به عنوان کپشن پردازش می‌شوند

        # ابتدا دنبال figcaption می‌گردیم
        for figcaption in soup.find_all('figcaption'):
             # بررسی اینکه قبلا پردازش نشده باشد (اگر داخل figure باشد ممکن است تکراری شود)
             if figcaption not in processed_caption_elements:
                 caption_text = figcaption.get_text(" ", strip=True)
                 if caption_text:
                     print(f"--- DEBUG: کپشن <figcaption> یافت شد: '{caption_text[:50]}...'")
                     caption_tags_to_process.append((figcaption, caption_text))
                     processed_caption_elements.add(figcaption)

        # سپس دنبال p بعد از img یا figure می‌گردیم
        potential_caption_parents = soup.find_all(['img', 'figure'])
        for element in potential_caption_parents:
            # پیدا کردن اولین تگ p بعدی (نه لزوما sibling مستقیم)
            # next_sibling_p = element.find_next_sibling('p') 
            # یا پیدا کردن اولین sibling که p باشد
            sibling = element.next_sibling
            while sibling and isinstance(sibling, NavigableString) and sibling.strip() == '': # رد کردن فضاهای خالی
                sibling = sibling.next_sibling
            
            if sibling and sibling.name == 'p' and sibling not in processed_caption_elements:
                 # بررسی کلاس یا طول متن به عنوان معیار
                 is_caption = False
                 if 'wp-caption-text' in sibling.get('class', []):
                     is_caption = True
                     print(f"--- DEBUG: کپشن <p> با کلاس 'wp-caption-text' یافت شد.")
                 elif len(sibling.get_text(strip=True)) < 250: # معیار: متن نسبتا کوتاه
                     is_caption = True
                     print(f"--- DEBUG: کپشن <p> (متن کوتاه) یافت شد.")
                 
                 if is_caption:
                     caption_text = sibling.get_text(" ", strip=True)
                     if caption_text:
                         caption_tags_to_process.append((sibling, caption_text))
                         processed_caption_elements.add(sibling) # علامت‌گذاری برای عدم پردازش مجدد

        print(f"--- تعداد {len(caption_tags_to_process)} کپشن احتمالی یافت شد.")

        # 3. استخراج متن‌های معمولی و لینک‌ها (با رد کردن کپشن‌های شناسایی شده)
        print("--- استخراج متن‌های معمولی و لینک‌ها...")
        text_nodes_to_process = [] 
        a_tags_to_process = []    

        text_parent_tags = ['p', 'li', 'blockquote', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'span', 'em', 'strong', 'td', 'th'] # figcaption و p کپشن نباید اینجا باشند
        
        # استفاده از string=True
        for element in soup.find_all(string=True): 
            element_text = element.string 
            if not element_text or element_text.isspace(): continue

            # بررسی اینکه آیا والدش جزو کپشن‌های پردازش شده است؟
            is_inside_processed_caption = False
            curr = element.parent
            while curr:
                if curr in processed_caption_elements:
                    is_inside_processed_caption = True; break
                curr = curr.parent
            if is_inside_processed_caption: continue # رد کردن متن داخل کپشن

            # بررسی اینکه آیا داخل لینک است؟
            is_inside_a = False; curr = element.parent
            while curr:
                if curr.name == 'a': is_inside_a = True; break
                curr = curr.parent
            
            # افزودن متن معمولی اگر والد مجاز است و داخل لینک/کپشن نیست
            if not is_inside_a and element.parent.name in text_parent_tags:
                text_nodes_to_process.append((element, element_text))

        # استخراج لینک‌ها (به شرطی که داخل کپشن نباشند)
        for a_tag in soup.find_all('a'):
            is_inside_processed_caption = False; curr = a_tag.parent
            while curr:
                if curr in processed_caption_elements: is_inside_processed_caption = True; break
                curr = curr.parent
            if is_inside_processed_caption: continue # رد کردن لینک داخل کپشن

            link_text = a_tag.get_text(" ", strip=True)
            if link_text: 
                a_tags_to_process.append((a_tag, link_text))

        print(f"--- یافت شد {len(text_nodes_to_process)} متن معمولی و {len(a_tags_to_process)} متن لینک (بدون احتساب کپشن).")
        total_segments = len(caption_tags_to_process) + len(text_nodes_to_process) + len(a_tags_to_process)
        current_segment = 0

        # 4. ترجمه و جایگزینی تک به تک کپشن‌ها
        print(f"--- شروع ترجمه و جایگزینی {len(caption_tags_to_process)} کپشن...")
        for i, (tag, original_text) in enumerate(caption_tags_to_process):
            current_segment += 1
            print(f"--- پردازش کپشن {current_segment}/{total_segments}...")
            try:
                translated_text = translate_with_gemini(original_text)
                if tag.parent is not None: # بررسی وجود والد
                     tag.clear()
                     # اگر لینک داخل کپشن بود، ترجمه لینک را هم باید هندل کرد - اینجا ساده‌سازی شده و فقط متن می‌گذاریم
                     tag.append(NavigableString(translated_text))
                     # اعمال استایل کپشن
                     tag['style'] = f"text-align:center; font-size:small; direction:rtl; color:#555; {tag.get('style', '')}" # استایل دلخواه
                else: print(f"--- هشدار: تگ کپشن {i+1} والد ندارد!")
                time.sleep(0.2) 
            except Exception as e:
                print(f"--- خطا در ترجمه/جایگزینی کپشن {i+1}: {e}. استفاده از متن اصلی.")
                if tag.parent is not None:
                     tag.clear()
                     tag.append(NavigableString(original_text)) # بازگرداندن متن اصلی
                time.sleep(0.5)

        # 5. ترجمه و جایگزینی تک به تک متن‌های معمولی
        print(f"--- شروع ترجمه و جایگزینی {len(text_nodes_to_process)} متن معمولی...")
        # ... (حلقه ترجمه متن‌های معمولی مثل قبل، با آپدیت شماره سگمنت) ...
        successful_text_translations = 0
        for i, (node, original_text) in enumerate(text_nodes_to_process):
            current_segment += 1
            print(f"--- پردازش متن معمولی {current_segment}/{total_segments}...")
            try:
                translated_text = translate_with_gemini(original_text)
                if node.parent is None: print(f"--- هشدار: گره متن معمولی {i+1} والد ندارد!"); continue 
                if hasattr(node, 'replace_with'): 
                    node.replace_with(NavigableString(translated_text))
                    successful_text_translations += 1
                else: print(f"--- هشدار: گره متن معمولی {i+1} خاصیت replace_with ندارد.")
                time.sleep(0.2) 
            except Exception as e:
                print(f"--- خطا در ترجمه/جایگزینی متن معمولی {i+1}: {e}. استفاده از متن اصلی.")
                time.sleep(0.5) 
        print(f"--- ترجمه {successful_text_translations} از {len(text_nodes_to_process)} متن معمولی موفق بود.")


        # 6. ترجمه و جایگزینی تک به تک متن لینک‌ها
        print(f"--- شروع ترجمه و جایگزینی {len(a_tags_to_process)} متن لینک...")
        # ... (حلقه ترجمه لینک‌ها مثل قبل، با آپدیت شماره سگمنت) ...
        successful_link_translations = 0
        for i, (a_tag, original_text) in enumerate(a_tags_to_process):
            current_segment += 1
            print(f"--- پردازش متن لینک {current_segment}/{total_segments}...")
            try:
                translated_text = translate_with_gemini(original_text)
                if a_tag.parent is not None:
                     a_tag.clear() 
                     a_tag.append(NavigableString(translated_text))
                     successful_link_translations +=1
                else: print(f"--- هشدار: تگ لینک {i+1} والد ندارد!")
                time.sleep(0.2) 
            except Exception as e:
                print(f"--- خطا در ترجمه/جایگزینی متن لینک {i+1}: {e}. استفاده از متن اصلی.")
                if a_tag.parent is not None:
                     a_tag.clear(); a_tag.append(NavigableString(original_text))
                time.sleep(0.5)
        print(f"--- ترجمه {successful_link_translations} از {len(a_tags_to_process)} متن لینک موفق بود.")

        # 7. اعمال استایل به عکس‌ها
        print("--- اعمال استایل به عکس‌ها...")
        # ... (مثل قبل) ...
        for img in soup.find_all('img'): img['style'] = f"display:block; margin-left:auto; margin-right:auto; max-width:100%; height:auto; {img.get('style', '')}"


        # 8. تبدیل سوپ اصلاح شده به رشته HTML
        content_html = str(soup)
        print("--- پردازش محتوا با BeautifulSoup کامل شد.")

    except Exception as e:
         print(f"خطای شدید و غیرمنتظره در پردازش محتوا با BeautifulSoup: {e}")
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
# ... (مثل قبل) ...
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
