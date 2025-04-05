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
        f"Please translate the following English text into {target_lang} ... " # (پرامپت کامل مثل قبل)
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
             print(f"--- خطای Timeout (تلاش {attempt+1})"); time.sleep(retry_delay)
             if attempt == max_retries: raise ValueError(f"Timeout پس از {max_retries+1} تلاش")
             continue
        except requests.exceptions.RequestException as e:
             print(f"--- خطای شبکه (تلاش {attempt+1}): {e}"); time.sleep(retry_delay)
             if attempt == max_retries: raise ValueError(f"خطای شبکه پس از {max_retries+1} تلاش: {e}") from e
             continue
        if response.status_code == 429 and attempt < max_retries:
            wait_time = retry_delay * (attempt + 2); print(f"--- خطای Rate Limit (429). انتظار {wait_time} ثانیه..."); time.sleep(wait_time)
        elif response.status_code != 200 :
             if attempt == max_retries :
                 error_details = response.text;
                 try: error_details = response.json()['error']['message']
                 except: pass
                 print(f"--- خطای نهایی API در ترجمه متن: '{text[:70]}...'"); raise ValueError(f"خطا در درخواست API (تلاش {attempt+1}): {response.status_code}, پاسخ: {error_details}")
    if response is None or response.status_code != 200: raise ValueError(f"ترجمه پس از {max_retries+1} تلاش ناموفق بود.")
    result = response.json();
    if 'error' in result: raise ValueError(f"خطا در API Gemini: {result['error'].get('message', 'جزئیات نامشخص')}")
    try:
        if not result.get("candidates"):
             feedback = result.get('promptFeedback', {}); block_reason = feedback.get('blockReason', 'نامشخص'); raise ValueError(f"API Response without candidates. Block Reason: {block_reason}.")
        candidate = result["candidates"][0]; content = candidate.get("content")
        if not content or not content.get("parts") or not content["parts"][0].get("text"):
             finish_reason = candidate.get("finishReason", "نامشخص")
             if text and not text.isspace() and finish_reason == "STOP": print(f"--- هشدار: ترجمه '{text[:50]}...' خروجی خالی بود."); return ""
             elif text and not text.isspace(): raise ValueError(f"خروجی خالی یا ترجمه ناقص. دلیل: {finish_reason}.")
             else: return ""
        translated_text = content["parts"][0]["text"]
    except (IndexError, KeyError, TypeError, ValueError) as e: raise ValueError(f"خطای پردازش پاسخ API برای '{text[:50]}...': {e}") from e
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

# *** پردازش محتوا با BeautifulSoup (اولویت با figcaption) ***
print("شروع پردازش محتوا با BeautifulSoup (اولویت با figcaption)...")
content_source = None
# ... (گرفتن content_source مثل قبل) ...
if 'content' in latest_post and latest_post.content: content_source = latest_post.content[0]['value']
elif 'summary' in latest_post: content_source = latest_post.summary
elif 'description' in latest_post: content_source = latest_post.description

if content_source:
    content_html = content_source
    soup = None
    processed_elements = set() # نگهداری اجزایی که در مرحله کپشن پردازش شده‌اند

    try:
        # 1. پاکسازی اولیه HTML
        print("--- پاکسازی اولیه HTML...")
        content_cleaned_html = re.split(r'Related Reading|Read Also|See Also', content_source, flags=re.IGNORECASE)[0].strip()
        content_cleaned_html = remove_newsbtc_links(content_cleaned_html)

        # 2. پارس کردن HTML
        print("--- پارس کردن HTML...")
        soup = BeautifulSoup(content_cleaned_html, 'html.parser')
        # print(f"--- DEBUG: ساختار اولیه Soup: {soup.prettify()[:500]}...")

        # 3. *** پردازش اختصاصی FIGCAPTION ها (اول) ***
        print(f"--- جستجو و پردازش اختصاصی {len(soup.find_all('figcaption'))} تگ <figcaption>...")
        for i, figcaption in enumerate(soup.find_all('figcaption')):
            if figcaption in processed_elements: continue # اگر به دلیلی قبلا پردازش شده، رد شو

            print(f"--- پردازش Figcaption [{i+1}]: {str(figcaption)[:100]}...")
            caption_text_nodes = [] # (node, original_text)
            caption_a_tags = []     # (tag, original_text)

            # پیدا کردن متن‌ها و لینک‌های داخل این figcaption
            for desc in figcaption.descendants:
                if isinstance(desc, NavigableString) and desc.strip():
                    parent_a = desc.find_parent('a')
                    is_link_text = parent_a is not None and parent_a in figcaption.find_all('a') # اطمینان از اینکه لینک هم داخل همین کپشن است
                    if not is_link_text and desc not in processed_elements:
                         caption_text_nodes.append((desc, desc.string))
                         processed_elements.add(desc) # علامت زدن متن معمولی داخل کپشن
                elif desc.name == 'a' and desc in figcaption.find_all('a'): # آیا 'a' واقعا فرزند مستقیم یا نوه کپشن است؟
                     if desc not in processed_elements:
                         link_text = desc.get_text(" ", strip=True)
                         if link_text:
                             caption_a_tags.append((desc, link_text))
                         processed_elements.add(desc) # علامت زدن تگ لینک داخل کپشن

            print(f"--- یافت شد {len(caption_text_nodes)} متن و {len(caption_a_tags)} لینک داخل Figcaption [{i+1}].")

            # ترجمه و جایگزینی متن‌های معمولی داخل کپشن
            for node, original_text in caption_text_nodes:
                try:
                    translated_text = translate_with_gemini(original_text)
                    if node.parent is not None: node.replace_with(NavigableString(translated_text))
                    else: print(f"--- هشدار: گره متن کپشن {i+1} والد ندارد!")
                    time.sleep(0.2)
                except Exception as e:
                    print(f"--- خطا در ترجمه متن کپشن '{original_text[:30]}...': {e}")
                    time.sleep(0.5)

            # ترجمه و جایگزینی متن لینک‌های داخل کپشن
            for a_tag, original_text in caption_a_tags:
                try:
                    translated_text = translate_with_gemini(original_text)
                    if a_tag.parent is not None: a_tag.clear(); a_tag.append(NavigableString(translated_text))
                    else: print(f"--- هشدار: تگ لینک کپشن {i+1} والد ندارد!")
                    time.sleep(0.2)
                except Exception as e:
                    print(f"--- خطا در ترجمه متن لینک کپشن '{original_text[:30]}...': {e}")
                    if a_tag.parent is not None: a_tag.clear(); a_tag.append(NavigableString(original_text)) # بازگرداندن متن اصلی
                    time.sleep(0.5)

            # اعمال استایل به خود تگ figcaption
            figcaption['style'] = f"text-align:center; font-size:small; direction:rtl; color:#555; margin-top: 5px; {figcaption.get('style', '')}"
            processed_elements.add(figcaption) # علامت زدن خود تگ figcaption
            print(f"--- پردازش Figcaption [{i+1}] کامل شد: {str(figcaption)[:100]}...")


        # 4. استخراج و پردازش بقیه متن‌های معمولی و لینک‌ها (با رد کردن موارد پردازش شده)
        print("--- استخراج و پردازش بقیه متن‌های معمولی و لینک‌ها...")
        text_nodes_to_process = []
        a_tags_to_process = []

        text_parent_tags = ['p', 'li', 'blockquote', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'span', 'em', 'strong', 'td', 'th'] # دیگر نیازی به figcaption نیست

        # پیدا کردن متن‌های معمولی باقیمانده
        for element in soup.find_all(string=True):
            if element in processed_elements: continue # رد کردن موارد پردازش شده در کپشن
            element_text = element.string
            if not element_text or element_text.isspace(): continue
            is_inside_a = False; curr = element.parent
            while curr:
                # بررسی اینکه آیا خود 'a' پردازش شده یا والدش 'a' است
                if curr.name == 'a': 
                    if curr in processed_elements: is_inside_a = True # لینک کپشن بود
                    break # بررسی بیشتر لازم نیست
                curr = curr.parent
            
            if not is_inside_a and element.parent.name in text_parent_tags:
                text_nodes_to_process.append((element, element_text))
                processed_elements.add(element) # علامت زدن به عنوان پردازش شده

        # پیدا کردن لینک‌های باقیمانده
        for a_tag in soup.find_all('a'):
             if a_tag in processed_elements: continue # رد کردن لینک کپشن
             link_text = a_tag.get_text(" ", strip=True)
             if link_text:
                 a_tags_to_process.append((a_tag, link_text))
                 processed_elements.add(a_tag) # علامت زدن به عنوان پردازش شده


        print(f"--- یافت شد {len(text_nodes_to_process)} متن معمولی و {len(a_tags_to_process)} متن لینک باقیمانده.")
        total_remaining = len(text_nodes_to_process) + len(a_tags_to_process)
        current_remaining = 0

        # 5. ترجمه تک به تک متن‌های معمولی باقیمانده
        print(f"--- شروع ترجمه و جایگزینی {len(text_nodes_to_process)} متن معمولی باقیمانده...")
        # ... (حلقه ترجمه و جایگزینی متن‌های معمولی مثل قبل) ...
        successful_text_translations = 0
        for i, (node, original_text) in enumerate(text_nodes_to_process):
            current_remaining += 1; print(f"--- پردازش متن معمولی {current_remaining}/{total_remaining}...")
            try:
                translated_text = translate_with_gemini(original_text)
                if node.parent is None: print(f"--- هشدار: گره متن باقیمانده {i+1} والد ندارد!"); continue 
                if hasattr(node, 'replace_with'): 
                    node.replace_with(NavigableString(translated_text))
                    successful_text_translations += 1
                else: print(f"--- هشدار: گره متن باقیمانده {i+1} خاصیت replace_with ندارد.");
                time.sleep(0.2) 
            except Exception as e:
                print(f"--- خطا در ترجمه/جایگزینی متن باقیمانده {i+1} ('{original_text[:30]}...'): {e}. استفاده از متن اصلی.")
                time.sleep(0.5) 
        print(f"--- ترجمه {successful_text_translations} از {len(text_nodes_to_process)} متن معمولی باقیمانده موفق بود.")

        # 6. ترجمه تک به تک متن لینک‌های باقیمانده
        print(f"--- شروع ترجمه و جایگزینی {len(a_tags_to_process)} متن لینک باقیمانده...")
        # ... (حلقه ترجمه و جایگزینی لینک‌ها مثل قبل) ...
        successful_link_translations = 0
        for i, (a_tag, original_text) in enumerate(a_tags_to_process):
            current_remaining += 1; print(f"--- پردازش متن لینک {current_remaining}/{total_remaining}...")
            try:
                translated_text = translate_with_gemini(original_text)
                if a_tag.parent is not None:
                     a_tag.clear(); a_tag.append(NavigableString(translated_text))
                     successful_link_translations +=1
                else: print(f"--- هشدار: تگ لینک باقیمانده {i+1} والد ندارد!")
                time.sleep(0.2) 
            except Exception as e:
                print(f"--- خطا در ترجمه/جایگزینی متن لینک باقیمانده {i+1} ('{original_text[:30]}...'): {e}. استفاده از متن اصلی.")
                if a_tag.parent is not None: a_tag.clear(); a_tag.append(NavigableString(original_text))
                time.sleep(0.5)
        print(f"--- ترجمه {successful_link_translations} از {len(a_tags_to_process)} متن لینک باقیمانده موفق بود.")

        # 7. اعمال استایل به عکس‌ها (استایل figcaption در مرحله 3 اعمال شد)
        print("--- اعمال استایل به عکس‌ها...")
        for img in soup.find_all('img'):
            img['style'] = f"display:block; margin-left:auto; margin-right:auto; max-width:100%; height:auto; {img.get('style', '')}"

        # 8. تبدیل سوپ اصلاح شده به رشته HTML
        content_html = str(soup)
        # print(f"--- DEBUG: HTML نهایی: {content_html[:500]}...")
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
