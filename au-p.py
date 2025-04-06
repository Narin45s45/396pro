import feedparser
import os
import json
import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import re
import time # Import time for sleep
from bs4 import BeautifulSoup, NavigableString # Import BeautifulSoup

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

# تابع ترجمه با Gemini (اصلاح تورفتگی در except)
def translate_with_gemini(text, target_lang="fa"):
    if not text or text.isspace(): return text
    headers = {"Content-Type": "application/json"}
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
             # *** اصلاح تورفتگی در خط زیر ***
             time.sleep(retry_delay)
             continue # ادامه به تلاش بعدی
        except requests.exceptions.RequestException as e:
             print(f"--- خطای شبکه (تلاش {attempt+1}): {e}")
             if attempt == max_retries: raise ValueError(f"خطای شبکه پس از {max_retries+1} تلاش: {e}") from e
             # *** اصلاح تورفتگی در خط زیر ***
             time.sleep(retry_delay)
             continue # ادامه به تلاش بعدی
        # ... (مدیریت خطاهای 429 و سایر کدها مثل قبل) ...
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
    try: # ... (کد کامل بررسی پاسخ و استخراج متن ترجمه شده مثل قبل) ...
        if not result.get("candidates"): feedback = result.get('promptFeedback', {}); block_reason = feedback.get('blockReason', 'نامشخص'); raise ValueError(f"API Response without candidates. Block Reason: {block_reason}.")
        candidate = result["candidates"][0]; content = candidate.get("content");
        if not content or not content.get("parts") or not content["parts"][0].get("text"):
             finish_reason = candidate.get("finishReason", "نامشخص");
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
    if title and not title.isspace(): translated_title = translate_with_gemini(title).splitlines()[0]
    else: translated_title = ""
    print(f"عنوان ترجمه شده: {translated_title}")
except Exception as e: print(f"خطای غیرمنتظره در ترجمه عنوان: {e}")

# اضافه کردن عکس پوستر
# ... (مثل قبل) ...
thumbnail = ""
# ... (کد یافتن thumbnail) ...
if hasattr(latest_post, 'media_content') and isinstance(latest_post.media_content, list) and latest_post.media_content:
    media=latest_post.media_content[0];
    if isinstance(media, dict) and 'url' in media: thumbnail_url = media['url']; #... (بقیه کد thumbnail) ...
         if thumbnail_url.startswith(('http://', 'https://')): thumbnail = f'<div style="text-align:center;"><img src="{thumbnail_url}" alt="{translated_title}" style="max-width:100%; height:auto;"></div>'
elif 'links' in latest_post: # ... (کد thumbnail از links) ...
     for link_info in latest_post.links:
         if link_info.get('rel') == 'enclosure' and link_info.get('type','').startswith('image/'):
             thumbnail_url = link_info.get('href'); #... (بقیه کد thumbnail) ...
             if thumbnail_url and thumbnail_url.startswith(('http://', 'https://')): thumbnail = f'<div style="text-align:center;"><img src="{thumbnail_url}" alt="{translated_title}" style="max-width:100%; height:auto;"></div>'; break


# *** پردازش محتوا با BeautifulSoup (ساده‌سازی figcaption - فقط متن) ***
print("شروع پردازش محتوا با BeautifulSoup (ساده‌سازی figcaption)...")
content_source = None
# ... (گرفتن content_source مثل قبل) ...
if 'content' in latest_post and latest_post.content: content_source = latest_post.content[0]['value']
elif 'summary' in latest_post: content_source = latest_post.summary
elif 'description' in latest_post: content_source = latest_post.description

if content_source:
    content_html = content_source
    soup = None
    processed_elements = set()

    try:
        # 1. پاکسازی اولیه HTML
        print("--- پاکسازی اولیه HTML...")
        content_cleaned_html = re.split(r'Related Reading|Read Also|See Also', content_source, flags=re.IGNORECASE)[0].strip()
        content_cleaned_html = remove_newsbtc_links(content_cleaned_html)

        # 2. پارس کردن HTML
        print("--- پارس کردن HTML...")
        soup = BeautifulSoup(content_cleaned_html, 'html.parser')

        # 3. *** پردازش اختصاصی و ساده شده FIGCAPTION ها (فقط متن) ***
        print(f"--- جستجو و پردازش ساده شده {len(soup.find_all('figcaption'))} تگ <figcaption> (فقط متن)...")
        for i, figcaption in enumerate(soup.find_all('figcaption')):
            if figcaption in processed_elements: continue

            print(f"--- پردازش Figcaption [{i+1}] (فقط متن): {str(figcaption)[:100]}...")
            original_text = figcaption.get_text(" ", strip=True)

            if original_text:
                try:
                    translated_text = translate_with_gemini(original_text)
                    if figcaption.parent is not None:
                        figcaption.clear()
                        figcaption.append(NavigableString(translated_text))
                        figcaption['style'] = f"text-align:center; font-size:small; direction:rtl; color:#555; margin-top: 5px; {figcaption.get('style', '')}"
                        print(f"--- DEBUG: Figcaption [{i+1}] با متن ترجمه شده جایگزین شد (لینک‌های داخلی حذف شدند).")
                        processed_elements.add(figcaption)
                        for desc in figcaption.find_all(['a', 'strong', 'em', 'span'], string=True): # علامت‌گذاری اجزای داخلی که حذف شدند
                             processed_elements.add(desc)
                        for txt_node in figcaption.find_all(string=True): processed_elements.add(txt_node) # علامت‌گذاری متن جدید
                    else: print(f"--- هشدار: Figcaption [{i+1}] والد ندارد!")
                    time.sleep(0.2)
                except Exception as e:
                    print(f"--- خطا در ترجمه/جایگزینی متن کپشن {i+1}: {e}. استفاده از متن اصلی (با حذف لینک‌ها).")
                    if figcaption.parent is not None:
                         figcaption.clear()
                         figcaption.append(NavigableString(original_text))
                         figcaption['style'] = f"text-align:center; font-size:small; direction:rtl; color:#555; margin-top: 5px; {figcaption.get('style', '')}"
                         processed_elements.add(figcaption) # علامت‌گذاری
                    time.sleep(0.5)
            else:
                processed_elements.add(figcaption)
                print(f"--- DEBUG: Figcaption [{i+1}] متنی برای ترجمه نداشت.")


        # 4. استخراج و پردازش بقیه متن‌های معمولی و لینک‌ها
        print("--- استخراج و پردازش بقیه متن‌ها...")
        text_nodes_to_process = []
        a_tags_to_process = []
        text_parent_tags = ['p', 'li', 'blockquote', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'span', 'em', 'strong', 'td', 'th']

        # استفاده از string=True
        for element in soup.find_all(string=True):
            # بررسی دقیقتر برای رد کردن موارد پردازش شده یا داخل موارد پردازش شده
            skip = False
            curr = element
            while curr:
                if curr in processed_elements:
                    skip = True; break
                curr = curr.parent
            if skip: continue

            element_text = element.string
            if not element_text or element_text.isspace(): continue

            is_inside_a = False; curr = element.parent
            while curr:
                if curr.name == 'a': is_inside_a = True; break
                curr = curr.parent

            if not is_inside_a and element.parent.name in text_parent_tags:
                text_nodes_to_process.append((element, element_text))
                processed_elements.add(element) # علامت‌گذاری متن معمولی

        for a_tag in soup.find_all('a'):
             # بررسی دقیقتر برای رد کردن موارد پردازش شده
             if a_tag in processed_elements: continue
             skip = False
             curr = a_tag.parent
             while curr:
                 if curr in processed_elements: skip=True; break
                 curr = curr.parent
             if skip: continue

             link_text = a_tag.get_text(" ", strip=True)
             if link_text:
                 a_tags_to_process.append((a_tag, link_text))
                 processed_elements.add(a_tag) # علامت‌گذاری لینک

        print(f"--- یافت شد {len(text_nodes_to_process)} متن معمولی و {len(a_tags_to_process)} متن لینک باقیمانده.")

        # 5. ترجمه تک به تک متن‌های معمولی باقیمانده
        # ... (حلقه ترجمه متن‌های معمولی مثل قبل) ...
        successful_text_translations = 0; current_segment = 0; total_remaining = len(text_nodes_to_process) + len(a_tags_to_process)
        print(f"--- شروع ترجمه و جایگزینی {len(text_nodes_to_process)} متن معمولی باقیمانده...")
        # ... (کد کامل حلقه با try/except و time.sleep مثل قبل) ...
        for i, (node, original_text) in enumerate(text_nodes_to_process):
            current_segment+=1; print(f"--- پردازش متن معمولی {current_segment}/{total_remaining}...")
            try: translated_text = translate_with_gemini(original_text); # ... (بقیه کد جایگزینی) ...
                 if node.parent is None: print(f"--- هشدار: گره متن باقیمانده {i+1} والد ندارد!"); continue 
                 if hasattr(node, 'replace_with'): node.replace_with(NavigableString(translated_text)); successful_text_translations += 1
                 else: print(f"--- هشدار: گره متن باقیمانده {i+1} خاصیت replace_with ندارد.");
                 time.sleep(0.2) 
            except Exception as e: print(f"--- خطا در ترجمه/جایگزینی متن باقیمانده {i+1} ('{original_text[:30]}...'): {e}. استفاده از متن اصلی."); time.sleep(0.5) 
        print(f"--- ترجمه {successful_text_translations} از {len(text_nodes_to_process)} متن معمولی باقیمانده موفق بود.")


        # 6. ترجمه تک به تک متن لینک‌های باقیمانده
        # ... (حلقه ترجمه لینک‌ها مثل قبل) ...
        successful_link_translations = 0
        print(f"--- شروع ترجمه و جایگزینی {len(a_tags_to_process)} متن لینک باقیمانده...")
        # ... (کد کامل حلقه با try/except و time.sleep مثل قبل) ...
        for i, (a_tag, original_text) in enumerate(a_tags_to_process):
            current_segment+=1; print(f"--- پردازش متن لینک {current_segment}/{total_remaining}...")
            try: translated_text = translate_with_gemini(original_text); # ... (بقیه کد جایگزینی) ...
                 if a_tag.parent is not None: a_tag.clear(); a_tag.append(NavigableString(translated_text)); successful_link_translations +=1
                 else: print(f"--- هشدار: تگ لینک باقیمانده {i+1} والد ندارد!"); 
                 time.sleep(0.2) 
            except Exception as e: print(f"--- خطا در ترجمه/جایگزینی متن لینک باقیمانده {i+1} ('{original_text[:30]}...'): {e}. استفاده از متن اصلی."); # ... (کد بازگرداندن متن اصلی) ...
                 if a_tag.parent is not None: a_tag.clear(); a_tag.append(NavigableString(original_text))
                 time.sleep(0.5)
        print(f"--- ترجمه {successful_link_translations} از {len(a_tags_to_process)} متن لینک باقیمانده موفق بود.")


        # 7. اعمال استایل به عکس‌ها
        print("--- اعمال استایل به عکس‌ها...")
        for img in soup.find_all('img'):
            img['style'] = f"display:block; margin-left:auto; margin-right:auto; max-width:100%; height:auto; {img.get('style', '')}"
            # استایل figcaption در مرحله 3 اعمال شد

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
full_content_parts = []; # ... (کد کامل مثل قبل) ...
if thumbnail: full_content_parts.append(thumbnail); full_content_parts.append('<br>')
if content_html: full_content_parts.append(f'<div style="text-align:justify;direction:rtl;">{content_html}</div>')
else: full_content_parts.append('<div style="text-align:center;direction:rtl;">[محتوای مقاله یافت نشد یا قابل پردازش نبود]</div>')
post_link = getattr(latest_post, 'link', None)
if post_link and post_link.startswith(('http://', 'https://')):
    full_content_parts.append(f'<div style="text-align:right;direction:rtl;margin-top:15px;">'); # ... (بقیه کد لینک منبع) ...
    full_content_parts.append(f'<a href="{post_link}" target="_blank" rel="noopener noreferrer">منبع</a>'); full_content_parts.append(f'</div>')
else: print("لینک منبع معتبر یافت نشد.")
full_content = "".join(full_content_parts)


# ساخت و ارسال پست به بلاگر
# ... (مثل قبل) ...
blog_id = "764765195397447456"
post_body = { "kind": "blogger#post", "blog": {"id": blog_id}, "title": translated_title, "content": full_content }
print("در حال ارسال پست به بلاگر...")
# ... (کد کامل ارسال مثل قبل با raise خطا) ...
try: request = service.posts().insert(blogId=blog_id, body=post_body, isDraft=False); response = request.execute(); print("پست با موفقیت ارسال شد:", response.get("url", "URL نامشخص"))
except Exception as e: print(f"خطای شدید هنگام ارسال پست به بلاگر: {e}"); # ... (چاپ جزئیات خطا) ...
     if hasattr(e, 'content'): # ... (چاپ جزئیات) ...
        try: error_details = json.loads(e.content); print(f"جزئیات خطا از API بلاگر: {error_details}")
        except json.JSONDecodeError: print(f"محتوای خطا (غیر JSON): {e.content}")
     raise e
