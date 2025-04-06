# -*- coding: utf-8 -*-
import feedparser
import os
import json
import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build, HttpError
import re
from bs4 import BeautifulSoup
import time
import base64
from urllib.parse import urlparse
import sys # برای flush کردن خروجی

# --- تنظیمات ---
RSS_FEED_URL = "https://www.newsbtc.com/feed/"
GEMINI_API_KEY = os.environ.get("GEMAPI")
if not GEMINI_API_KEY:
    raise ValueError("!متغیر محیطی GEMAPI پیدا نشد")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

creds_json = os.environ.get("CREDENTIALS")
if not creds_json:
    raise ValueError("!متغیر محیطی CREDENTIALS پیدا نشد")
try:
    creds_info = json.loads(creds_json)
    if not all(k in creds_info for k in ['token', 'refresh_token', 'client_id', 'client_secret', 'scopes']):
        raise ValueError("فایل CREDENTIALS ناقص است. کلیدهای لازم: token, refresh_token, client_id, client_secret, scopes")
    creds = Credentials.from_authorized_user_info(creds_info)
except Exception as e:
     raise ValueError(f"خطا در بارگذاری CREDENTIALS: {e}")

print(">>> آماده‌سازی سرویس بلاگر...")
sys.stdout.flush() # اطمینان از چاپ شدن فوری
try:
    service = build("blogger", "v3", credentials=creds)
    print("<<< سرویس بلاگر با موفقیت آماده شد.")
    sys.stdout.flush()
except Exception as e:
    print(f"!!! خطا در ساخت سرویس بلاگر: {e}")
    sys.stdout.flush()
    exit(1)

BLOG_ID = "764765195397447456"
REQUEST_TIMEOUT = 45
GEMINI_TIMEOUT = 90

# --- تابع ترجمه با Gemini (با لاگ و بهبود مدیریت خطا) ---
def translate_with_gemini(text, target_lang="fa"):
    print(f">>> شروع ترجمه متن با Gemini (طول متن: {len(text)} کاراکتر)...")
    sys.stdout.flush()
    if not text or text.isspace():
         print("--- متن ورودی برای ترجمه خالی است. رد شدن از ترجمه.")
         sys.stdout.flush()
         return ""

    headers = {"Content-Type": "application/json"}
    # Prompt remains the same as before
    prompt = (
         f"Please translate the following English text (which might contain HTML tags) into {target_lang} "
         f"with the utmost intelligence and precision. Pay close attention to context and nuance.\n"
         f"IMPORTANT TRANSLATION RULES:\n"
         f"1. Translate ALL text content, including text inside HTML tags like <p>, <li>, <blockquote>, <a>, <img> (alt text), etc. Do not skip any content.\n"
         f"2. For technical terms or English words commonly used in the field (like Bitcoin, Ethereum, NFT, Blockchain, Stochastic Oscillator, MACD, RSI, AI, API), "
         f"transliterate them into Persian script (Finglish) instead of translating them into a potentially obscure Persian word. "
         f"Example: 'Stochastic Oscillator' should become 'اوسیلاتور استوکستیک'. Apply consistently.\n"
         f"3. Ensure that any text within quotation marks (\"\") is also accurately translated.\n"
         f"4. Preserve the original HTML structure (tags and attributes) as much as possible, only translating the text content within the tags and relevant attributes like 'alt' or 'title'.\n" # Removed RTL mention here
         f"OUTPUT REQUIREMENT: Only return the final, high-quality translated text with its original HTML structure. Do not add any explanations, comments, apologies, or options like '[Option 1]: ...'. Provide only the single best translation embedded in the HTML.\n\n"
         f"English Text with HTML to Translate:\n{text}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.5, "topP": 0.95, "topK": 40}
    }
    max_retries = 2
    retry_delay = 15

    for attempt in range(max_retries + 1):
        print(f"--- تلاش {attempt + 1}/{max_retries + 1} برای تماس با API Gemini...")
        sys.stdout.flush()
        try:
            response = requests.post(
                f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
                headers=headers,
                json=payload,
                timeout=GEMINI_TIMEOUT
            )
            print(f"--- پاسخ اولیه از Gemini دریافت شد (کد وضعیت: {response.status_code})")
            sys.stdout.flush()

            if response.status_code == 429 and attempt < max_retries:
                print(f"!!! خطای Rate Limit (429) از Gemini. منتظر ماندن برای {retry_delay} ثانیه...")
                sys.stdout.flush()
                time.sleep(retry_delay)
                retry_delay *= 1.5
                continue

            response.raise_for_status()

            print("--- در حال پردازش پاسخ JSON از Gemini...")
            sys.stdout.flush()
            result = response.json()

            if not result or "candidates" not in result or not result["candidates"]:
                feedback = result.get("promptFeedback", {})
                block_reason = feedback.get("blockReason")
                safety_ratings = feedback.get("safetyRatings")
                if block_reason:
                    print(f"!!! Gemini درخواست را مسدود کرد: {block_reason}. جزئیات ایمنی: {safety_ratings}")
                    sys.stdout.flush()
                    raise ValueError(f"ترجمه توسط Gemini مسدود شد: {block_reason}")
                else:
                    print(f"!!! پاسخ غیرمنتظره از API Gemini (ساختار نامعتبر candidates): {result}")
                    sys.stdout.flush()
                    raise ValueError("پاسخ غیرمنتظره از API Gemini (ساختار نامعتبر candidates)")

            candidate = result["candidates"][0]
            if "content" not in candidate or "parts" not in candidate["content"] or not candidate["content"]["parts"]:
                 finish_reason = candidate.get("finishReason", "نامشخص")
                 if finish_reason != "STOP":
                      print(f"!!! Gemini ترجمه را کامل نکرد: دلیل پایان = {finish_reason}")
                      sys.stdout.flush()
                      partial_text = candidate.get("content",{}).get("parts",[{}])[0].get("text")
                      if partial_text:
                           print("--- هشدار: ممکن است ترجمه ناقص باشد.")
                           sys.stdout.flush()
                           return partial_text.strip()
                      raise ValueError(f"ترجمه ناقص از Gemini دریافت شد (دلیل: {finish_reason})")
                 else:
                    print(f"!!! پاسخ غیرمنتظره از API Gemini (ساختار نامعتبر content/parts): {candidate}")
                    sys.stdout.flush()
                    raise ValueError("پاسخ غیرمنتظره از API Gemini (ساختار نامعتبر content/parts)")

            if "text" not in candidate["content"]["parts"][0]:
                 print(f"!!! پاسخ غیرمنتظره از API Gemini (بدون text در part): {candidate}")
                 sys.stdout.flush()
                 raise ValueError("پاسخ غیرمنتظره از API Gemini (بدون text در part)")

            translated_text = candidate["content"]["parts"][0]["text"]
            print("<<< ترجمه متن با Gemini با موفقیت انجام شد.")
            sys.stdout.flush()
            translated_text = re.sub(r'^```html\s*', '', translated_text, flags=re.IGNORECASE)
            translated_text = re.sub(r'\s*```$', '', translated_text)
            return translated_text.strip()

        except requests.exceptions.Timeout:
            print(f"!!! خطا: درخواست به API Gemini زمان‌بر شد (Timeout پس از {GEMINI_TIMEOUT} ثانیه).")
            sys.stdout.flush()
            if attempt >= max_retries:
                print("!!! تلاش‌های مکرر برای Gemini ناموفق بود (Timeout).")
                sys.stdout.flush()
                raise ValueError("API Gemini پس از چند بار تلاش پاسخ نداد (Timeout).")
            print(f"--- منتظر ماندن برای {retry_delay} ثانیه قبل از تلاش مجدد...")
            sys.stdout.flush()
            time.sleep(retry_delay)
            retry_delay *= 1.5
        except requests.exceptions.RequestException as e:
            print(f"!!! خطا در درخواست به API Gemini: {e}")
            sys.stdout.flush()
            if attempt >= max_retries:
                print("!!! تلاش‌های مکرر برای Gemini ناموفق بود (خطای شبکه).")
                sys.stdout.flush()
                raise ValueError(f"خطا در درخواست API Gemini پس از چند بار تلاش: {e}")
            print(f"--- منتظر ماندن برای {retry_delay} ثانیه قبل از تلاش مجدد...")
            sys.stdout.flush()
            time.sleep(retry_delay)
            retry_delay *= 1.5
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            print(f"!!! خطا در پردازش پاسخ Gemini یا خطای داده: {e}")
            sys.stdout.flush()
            raise
        except Exception as e:
             print(f"!!! خطای پیش‌بینی نشده در تابع ترجمه: {e}")
             sys.stdout.flush()
             raise

    print("!!! ترجمه با Gemini پس از تمام تلاش‌ها ناموفق بود.")
    sys.stdout.flush()
    raise ValueError("ترجمه با Gemini پس از تمام تلاش‌ها ناموفق بود.")


# --- تابع حذف لینک‌های newsbtc ---
def remove_newsbtc_links(text):
    if not text: return ""
    print("--- حذف لینک‌های داخلی newsbtc...")
    sys.stdout.flush()
    pattern = r'<a\s+[^>]*href=["\']https?://(www\.)?newsbtc\.com[^"\']*["\'][^>]*>(.*?)</a>'
    cleaned = re.sub(pattern, r'\2', text, flags=re.IGNORECASE)
    print(f"--- حذف لینک کامل شد.")
    sys.stdout.flush()
    return cleaned

# --- تابع جایگزینی URLهای twimg.com با Base64 ---
def replace_twimg_with_base64(content):
    if not content: return ""
    print(">>> شروع بررسی و تبدیل عکس‌های twimg.com به Base64...")
    sys.stdout.flush()
    soup = BeautifulSoup(content, "html.parser")
    images = soup.find_all("img")
    print(f"--- تعداد کل عکس‌های یافت شده: {len(images)}")
    sys.stdout.flush()
    modified = False
    processed_count = 0
    twimg_count = 0
    for i, img in enumerate(images):
        src = img.get("src", "")
        # print(f"--- بررسی عکس {i+1}/{len(images)}: src='{src[:100]}...'") # Log might be too verbose
        # sys.stdout.flush()
        if "twimg.com" in src:
            twimg_count += 1
            print(f"--- عکس {i+1} از twimg.com است. شروع دانلود و تبدیل...")
            sys.stdout.flush()
            try:
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
                # print(f"---   در حال دانلود از: {src}") # Verbose log
                # sys.stdout.flush()
                response = requests.get(src, stream=True, timeout=REQUEST_TIMEOUT, headers=headers)
                response.raise_for_status()
                # print(f"---   دانلود کامل شد (وضعیت: {response.status_code}).") # Verbose log
                # sys.stdout.flush()

                content_type = response.headers.get('content-type', '').split(';')[0].strip()
                if not content_type or not content_type.startswith('image/'):
                    # print(f"---   هشدار: نوع محتوا نامعتبر ({content_type}). تلاش برای حدس زدن از URL...") # Verbose log
                    # sys.stdout.flush()
                    parsed_url = urlparse(src)
                    path = parsed_url.path
                    ext = os.path.splitext(path)[1].lower()
                    mime_map = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.gif': 'image/gif', '.webp': 'image/webp'}
                    content_type = mime_map.get(ext, 'image/jpeg')
                    # print(f"---   نوع محتوای حدس زده شده: {content_type}") # Verbose log
                    # sys.stdout.flush()

                # print(f"---   در حال خواندن محتوای عکس...") # Verbose log
                # sys.stdout.flush()
                image_content = response.content
                # print(f"---   خواندن کامل شد (حجم: {len(image_content)} بایت).") # Verbose log
                # sys.stdout.flush()
                # print(f"---   در حال تبدیل به Base64...") # Verbose log
                # sys.stdout.flush()
                base64_encoded_data = base64.b64encode(image_content)
                base64_string = base64_encoded_data.decode('utf-8')
                # print(f"---   تبدیل Base64 کامل شد.") # Verbose log
                # sys.stdout.flush()

                data_uri = f"data:{content_type};base64,{base64_string}"
                img['src'] = data_uri
                if not img.get('alt'):
                    img['alt'] = "تصویر جایگزین شده از توییتر"
                print(f"---   عکس {i+1} با موفقیت به Base64 تبدیل و جایگزین شد.")
                sys.stdout.flush()
                modified = True
                processed_count += 1

            except requests.exceptions.Timeout:
                print(f"!!!   خطا: Timeout هنگام دانلود عکس {i+1} از {src}")
                sys.stdout.flush()
            except requests.exceptions.RequestException as e:
                print(f"!!!   خطا در دانلود عکس {i+1} ({src}): {e}")
                sys.stdout.flush()
            except Exception as e:
                print(f"!!!   خطای غیرمنتظره هنگام پردازش عکس {i+1} ({src}): {e}")
                sys.stdout.flush()
            # print("-" * 20) # Separator # Verbose log
            # sys.stdout.flush()

    print(f"<<< بررسی عکس‌های twimg.com تمام شد. {processed_count}/{twimg_count} عکس با موفقیت تبدیل شد.")
    sys.stdout.flush()
    return str(soup) if modified else content


# --- تابع کرال کردن کپشن‌ها ---
def crawl_captions(post_url):
    print(f">>> شروع کرال کردن کپشن‌ها از: {post_url}")
    sys.stdout.flush()
    captions_with_images = []
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        print("--- ارسال درخواست GET برای دریافت صفحه...")
        sys.stdout.flush()
        response = requests.get(post_url, timeout=REQUEST_TIMEOUT, headers=headers)
        response.raise_for_status()
        print(f"--- صفحه با موفقیت دریافت شد (وضعیت: {response.status_code}).")
        sys.stdout.flush()
        print("--- در حال تجزیه HTML صفحه...")
        sys.stdout.flush()
        soup = BeautifulSoup(response.content, "html.parser")
        print("--- تجزیه HTML کامل شد.")
        sys.stdout.flush()

        print("--- جستجو برای کپشن‌ها در تگ‌های <figure>...")
        sys.stdout.flush()
        figures = soup.find_all("figure")
        figure_captions_found = 0
        for figure in figures:
            img = figure.find("img")
            caption_tag = figure.find("figcaption")
            if img and caption_tag:
                img_src = img.get("src") or img.get("data-src")
                if img_src:
                    caption_html = str(caption_tag)
                    captions_with_images.append({"image_url": img_src, "caption": caption_html})
                    figure_captions_found += 1
        print(f"--- {figure_captions_found} کپشن در تگ <figure> یافت شد.")
        sys.stdout.flush()

        print("--- حذف کپشن‌های تکراری احتمالی...")
        sys.stdout.flush()
        unique_captions = []
        seen_caption_texts = set()
        for item in captions_with_images:
            caption_text = BeautifulSoup(item['caption'], 'html.parser').get_text(strip=True)
            if caption_text and caption_text not in seen_caption_texts:
                unique_captions.append(item)
                seen_caption_texts.add(caption_text)

        print(f"<<< کرال کردن کپشن‌ها تمام شد. {len(unique_captions)} کپشن منحصر به فرد یافت شد.")
        sys.stdout.flush()
        return unique_captions

    except requests.exceptions.Timeout:
        print(f"!!! خطا: Timeout هنگام کرال کردن {post_url}")
        sys.stdout.flush()
        return []
    except requests.exceptions.RequestException as e:
        print(f"!!! خطا در کرال کردن {post_url}: {e}")
        sys.stdout.flush()
        return []
    except Exception as e:
         print(f"!!! خطای غیرمنتظره در کرال کردن کپشن ها: {e}")
         sys.stdout.flush()
         return []

# --- تابع قرار دادن کپشن‌ها زیر عکس‌ها (بدون استایل RTL اضافی) ---
def add_captions_to_images(content, original_captions_with_images):
    if not original_captions_with_images:
        print("--- هیچ کپشنی برای اضافه کردن وجود ندارد. رد شدن...")
        sys.stdout.flush()
        return content
    if not content:
         print("--- محتوای ورودی برای اضافه کردن کپشن خالی است. رد شدن...")
         sys.stdout.flush()
         return ""
    print(">>> شروع اضافه کردن کپشن‌ها به محتوای ترجمه‌شده...")
    sys.stdout.flush()

    soup = BeautifulSoup(content, "html.parser")
    images = soup.find_all("img")
    print(f"--- تعداد عکس‌های یافت شده در محتوای ترجمه‌شده: {len(images)}")
    sys.stdout.flush()

    if not images:
        print("--- هیچ عکسی در محتوا یافت نشد. کپشن‌ها در انتها اضافه می‌شوند.")
        sys.stdout.flush()
        captions_html = "".join([item['caption'] for item in original_captions_with_images])
        # افزودن کپشن ها در انتها - با استایل ساده مرکزی
        final_captions_div = soup.new_tag('div', style="text-align: center; margin-top: 15px; font-size: small;")
        final_captions_div.append(BeautifulSoup(captions_html, "html.parser"))
        soup.append(final_captions_div)
        return str(soup)

    used_caption_indices = set()
    captions_added_count = 0

    for img_index, img in enumerate(images):
        # print(f"--- پردازش عکس {img_index + 1}/{len(images)}...") # Verbose log
        # sys.stdout.flush()
        potential_match_index = img_index

        if potential_match_index < len(original_captions_with_images) and potential_match_index not in used_caption_indices:
            matching_caption_data = original_captions_with_images[potential_match_index]
            matching_caption_html = matching_caption_data["caption"]
            original_url = matching_caption_data["image_url"]
            # print(f"---   تلاش برای افزودن کپشن {potential_match_index + 1} (از عکس اصلی: {original_url[:60]}...)") # Verbose log
            # sys.stdout.flush()

            figure = soup.new_tag("figure")
            # استایل مرکزی برای figure
            figure['style'] = "margin: 1em auto; text-align: center; max-width: 100%;"

            parent = img.parent
            if parent.name == 'p' or parent.name == 'div':
                 parent.replace_with(figure)
                 figure.append(img)
            else:
                 img.wrap(figure)

            caption_soup = BeautifulSoup(matching_caption_html, "html.parser")
            caption_content = caption_soup.find(['figcaption', 'p', 'div', 'span'])

            if caption_content:
                # استایل ساده برای کپشن (بدون direction اجباری)
                caption_content['style'] = caption_content.get('style', '') + ' text-align: center; font-size: small; margin-top: 5px; color: #555;'
                figure.append(caption_content)
                used_caption_indices.add(potential_match_index)
                captions_added_count += 1
                # print(f"---   کپشن {potential_match_index + 1} با موفقیت به عکس {img_index + 1} اضافه شد.") # Verbose log
                # sys.stdout.flush()
            else:
                # print(f"---   هشدار: تگ اصلی کپشن {potential_match_index + 1} یافت نشد. افزودن به صورت خام.") # Verbose log
                # sys.stdout.flush()
                fallback_caption_div = soup.new_tag('div', style="text-align: center; font-size: small; margin-top: 5px; color: #555;")
                fallback_caption_div.append(BeautifulSoup(matching_caption_html, 'html.parser'))
                figure.append(fallback_caption_div)
                used_caption_indices.add(potential_match_index)
                captions_added_count += 1
                # print(f"---   کپشن خام {potential_match_index + 1} به عکس {img_index + 1} اضافه شد.") # Verbose log
                # sys.stdout.flush()
        # else:
             # print(f"---   کپشن متناظری برای عکس {img_index + 1} یافت نشد (یا قبلاً استفاده شده).") # Verbose log
             # sys.stdout.flush()


    remaining_captions_html = ""
    remaining_count = 0
    for i, item in enumerate(original_captions_with_images):
         if i not in used_caption_indices:
              # print(f"--- کپشن استفاده نشده {i+1} (از عکس {item['image_url'][:60]}) به انتها اضافه می‌شود.") # Verbose log
              # sys.stdout.flush()
              remaining_captions_html += item['caption']
              remaining_count += 1

    if remaining_captions_html:
        print(f"--- افزودن {remaining_count} کپشن باقی‌مانده به انتهای محتوا...")
        sys.stdout.flush()
        remaining_div = soup.new_tag('div', style="text-align: center; margin-top: 15px; font-size: small; border-top: 1px solid #eee; padding-top: 10px;")
        remaining_div.append(BeautifulSoup(remaining_captions_html, "html.parser"))
        soup.append(remaining_div)

    print(f"<<< اضافه کردن کپشن‌ها تمام شد. {captions_added_count} کپشن به عکس‌ها اضافه شد، {remaining_count} به انتها.")
    sys.stdout.flush()
    return str(soup)

# --- شروع اسکریپت اصلی ---
print("\n" + "="*50)
print(">>> شروع پردازش فید RSS و ارسال به بلاگر...")
print("="*50)
sys.stdout.flush()

# 1. دریافت فید RSS
print("\n>>> مرحله ۱: دریافت و تجزیه فید RSS...")
sys.stdout.flush()
try:
    print(f"--- در حال دریافت فید از: {RSS_FEED_URL}")
    sys.stdout.flush()
    start_time = time.time()
    feed = feedparser.parse(RSS_FEED_URL)
    end_time = time.time()
    print(f"--- فید دریافت شد (در زمان {end_time - start_time:.2f} ثانیه).")
    sys.stdout.flush()
    if feed.bozo:
        print(f"--- هشدار: خطای احتمالی در تجزیه فید: {feed.bozo_exception}")
        sys.stdout.flush()
    if not feed.entries:
        print("!!! هیچ پستی در فید RSS یافت نشد. خروج.")
        sys.stdout.flush()
        exit()
    print(f"--- {len(feed.entries)} پست در فید یافت شد.")
    sys.stdout.flush()
    latest_post = feed.entries[0]
    print(f"--- جدیدترین پست انتخاب شد: '{latest_post.title}'")
    sys.stdout.flush()
except Exception as e:
     print(f"!!! خطا در دریافت یا تجزیه فید RSS: {e}")
     sys.stdout.flush()
     exit(1)
print("<<< مرحله ۱ کامل شد.")
sys.stdout.flush()

# 2. کرال کردن کپشن‌ها
print("\n>>> مرحله ۲: کرال کردن کپشن‌ها از لینک پست اصلی...")
sys.stdout.flush()
post_link = getattr(latest_post, 'link', None)
original_captions_with_images = []
if post_link and post_link.startswith(('http://', 'https://')):
    original_captions_with_images = crawl_captions(post_link)
else:
    print(f"--- هشدار: لینک پست اصلی معتبر ({post_link}) یافت نشد. کپشن‌ها کرال نمی‌شوند.")
    sys.stdout.flush()
print(f"<<< مرحله ۲ کامل شد (تعداد کپشن یافت شده: {len(original_captions_with_images)}).")
sys.stdout.flush()


# 3. ترجمه عنوان
print("\n>>> مرحله ۳: ترجمه عنوان پست...")
sys.stdout.flush()
title = latest_post.title
translated_title = title
try:
    translated_title = translate_with_gemini(title).splitlines()[0]
    translated_title = translated_title.replace("**", "").replace("`", "")
    print(f"--- عنوان ترجمه‌شده: {translated_title}")
    sys.stdout.flush()
except Exception as e:
    print(f"!!! خطا در ترجمه عنوان: {e}. از عنوان اصلی استفاده می‌شود.")
    sys.stdout.flush()
print("<<< مرحله ۳ کامل شد.")
sys.stdout.flush()

# 4. پردازش تصویر بندانگشتی (Thumbnail)
print("\n>>> مرحله ۴: پردازش تصویر بندانگشتی...")
sys.stdout.flush()
thumbnail_html = ""
thumbnail_processed = False
try:
    if hasattr(latest_post, 'media_content') and latest_post.media_content:
        thumbnail_url = latest_post.media_content[0].get('url', '')
        if thumbnail_url and thumbnail_url.startswith(('http://', 'https://')):
            print(f"--- تصویر بندانگشتی یافت شد: {thumbnail_url}")
            sys.stdout.flush()
            temp_img_tag = f'<img src="{thumbnail_url}" alt="{translated_title}">'
            final_src = thumbnail_url # Default to original URL
            if "twimg.com" in thumbnail_url:
                print("--- تصویر بندانگشتی از twimg.com است، تبدیل به Base64...")
                sys.stdout.flush()
                converted_html = replace_twimg_with_base64(temp_img_tag)
                if converted_html != temp_img_tag:
                     final_src = BeautifulSoup(converted_html, "html.parser").img.get("src", thumbnail_url)
                     print("--- تصویر بندانگشتی twimg با موفقیت به Base64 تبدیل شد.")
                     sys.stdout.flush()
                else:
                     print("--- هشدار: تبدیل تصویر بندانگشتی twimg ناموفق بود. از URL اصلی استفاده می‌شود.")
                     sys.stdout.flush()

            # Create the final HTML with centering
            thumbnail_html = f'<div style="text-align:center; margin-bottom: 15px;"><img src="{final_src}" alt="{translated_title}" style="max-width:100%; height:auto; display:block; margin-left:auto; margin-right:auto; border-radius: 5px;"></div>'
            thumbnail_processed = True
        else:
            print("--- URL تصویر بندانگشتی نامعتبر است.")
            sys.stdout.flush()
    else:
        print("--- هیچ تصویر بندانگشتی (media_content) در فید یافت نشد.")
        sys.stdout.flush()
except Exception as e:
     print(f"!!! خطای پیش‌بینی نشده در پردازش تصویر بندانگشتی: {e}")
     sys.stdout.flush()

if thumbnail_processed: print("<<< مرحله ۴ کامل شد.")
else: print("<<< مرحله ۴ رد شد (تصویر بندانگشتی یافت نشد یا پردازش نشد).")
sys.stdout.flush()

# 5. پردازش محتوای اصلی
print("\n>>> مرحله ۵: پردازش محتوای اصلی...")
sys.stdout.flush()
content_html = ""
final_content_for_post = "<p>خطا: محتوای نهایی ایجاد نشد.</p>" # Default error message

try:
    # دریافت محتوای خام
    content_source = ""
    if 'content' in latest_post and latest_post.content:
        if isinstance(latest_post.content, list) and len(latest_post.content) > 0 and 'value' in latest_post.content[0]:
            content_source = latest_post.content[0]['value']
        elif isinstance(latest_post.content, dict) and 'value' in latest_post.content:
            content_source = latest_post.content['value']
    elif 'summary' in latest_post:
        content_source = latest_post.summary

    if content_source:
        print(f"--- محتوای خام یافت شد (طول: {len(content_source)} کاراکتر).")
        sys.stdout.flush()
        # 5.1 پاکسازی اولیه
        print("--- 5.1 پاکسازی اولیه محتوا...")
        sys.stdout.flush()
        content_cleaned = re.split(r'Related Reading|Read Also|See Also|Featured image from', content_source, flags=re.IGNORECASE)[0].strip()
        content_cleaned = remove_newsbtc_links(content_cleaned)
        print("--- پاکسازی اولیه کامل شد.")
        sys.stdout.flush()

        # 5.2 تبدیل عکس‌های twimg.com به Base64
        print("--- 5.2 تبدیل عکس‌های twimg.com در محتوای اصلی...")
        sys.stdout.flush()
        content_with_base64_images = replace_twimg_with_base64(content_cleaned)
        print("--- تبدیل عکس‌های twimg کامل شد.")
        sys.stdout.flush()

        # 5.3 ترجمه محتوا
        print("--- 5.3 ترجمه محتوای پردازش شده...")
        sys.stdout.flush()
        translated_content_raw = translate_with_gemini(content_with_base64_images)
        print("--- ترجمه محتوا کامل شد.")
        sys.stdout.flush()

        # 5.4 اضافه کردن کپشن‌ها به محتوای ترجمه شده
        print("--- 5.4 اضافه کردن کپشن‌ها به محتوای ترجمه شده...")
        sys.stdout.flush()
        translated_content_with_captions = add_captions_to_images(translated_content_raw, original_captions_with_images)
        print("--- اضافه کردن کپشن‌ها کامل شد.")
        sys.stdout.flush()

        # 5.5 تنظیمات نهایی استایل (فقط عکس‌ها) و پاکسازی
        print("--- 5.5 اعمال استایل نهایی به عکس‌ها و پاکسازی HTML...")
        sys.stdout.flush()
        soup_final = BeautifulSoup(translated_content_with_captions, "html.parser")
        for img_tag in soup_final.find_all("img"):
            # استایل مرکزی و ریسپانسیو برای همه عکس‌ها
            img_tag['style'] = img_tag.get('style', '') + ' max-width:100%; height:auto; display:block; margin-left:auto; margin-right:auto; border-radius: 3px;'
            if not img_tag.get('alt'):
                img_tag['alt'] = translated_title

        # حذف تگ‌های p خالی
        for p_tag in soup_final.find_all('p'):
            if not p_tag.get_text(strip=True) and not p_tag.find(['img', 'br', 'figure', 'iframe']):
                p_tag.decompose()

        content_html = str(soup_final)
        print("--- استایل‌دهی نهایی و پاکسازی کامل شد.")
        sys.stdout.flush()
        # Wrapper اصلی - بدون direction اجباری
        final_content_for_post = f'<div style="line-height: 1.7;">{content_html}</div>'

    elif original_captions_with_images:
        print("--- هشدار: محتوای اصلی یافت نشد، فقط از کپشن‌ها استفاده می‌شود.")
        sys.stdout.flush()
        captions_html = "".join([item["caption"] for item in original_captions_with_images])
        final_content_for_post = f'<div style="text-align: center; font-size: small;">{captions_html}</div>' # فقط مرکزی
    else:
        print("!!! محتوایی برای پردازش یافت نشد (نه محتوای اصلی، نه کپشن).")
        sys.stdout.flush()
        final_content_for_post = "<p style='text-align: center;'>محتوایی برای نمایش یافت نشد.</p>"

except Exception as e:
    print(f"!!! خطای جدی در پردازش محتوای اصلی (مرحله ۵): {e}")
    sys.stdout.flush()
    # Fallback logic
    if 'content_with_base64_images' in locals() and content_with_base64_images:
         print("--- استفاده از محتوای انگلیسی پردازش شده به عنوان جایگزین...")
         sys.stdout.flush()
         final_content_for_post = f"<p style='color: red;'><i>[خطا در ترجمه یا پردازش نهایی رخ داد. محتوای اصلی (انگلیسی) در زیر نمایش داده می‌شود.]</i></p><div style='text-align:left; direction:ltr;'>{content_with_base64_images}</div>"
    else:
         final_content_for_post = f"<p style='text-align: center; color: red;'>خطای جدی در پردازش محتوا: {e}</p>"

print("<<< مرحله ۵ کامل شد.")
sys.stdout.flush()


# 6. ساختار نهایی پست
print("\n>>> مرحله ۶: آماده‌سازی ساختار نهایی پست HTML...")
sys.stdout.flush()
full_content_parts = []
if thumbnail_html:
    full_content_parts.append(thumbnail_html)
    # full_content_parts.append('<br>') # Add space only if needed

if final_content_for_post:
    full_content_parts.append(final_content_for_post)

# Add source link only if it was valid
if post_link and post_link.startswith(('http://', 'https://')):
    # لینک منبع - بدون direction اجباری، فقط کمی استایل
    full_content_parts.append(f'<div style="text-align:right; margin-top:15px; font-size: small; color: #777;"><a href="{post_link}" target="_blank" rel="noopener noreferrer nofollow">منبع: NewsBTC</a></div>')

full_content = "".join(full_content_parts)
print("<<< مرحله ۶ کامل شد.")
sys.stdout.flush()

# نمایش بخش کوچکی از محتوای نهایی (برای بررسی سریع)
print("\n--- بخش ابتدایی محتوای نهایی برای ارسال ---")
print(full_content[:500] + "...")
print("--- پایان بخش ابتدایی ---")
sys.stdout.flush()

# 7. ارسال به بلاگر
print("\n>>> مرحله ۷: ارسال پست به بلاگر...")
sys.stdout.flush()
try:
    post_body = {
        "kind": "blogger#post",
        "blog": {"id": BLOG_ID},
        "title": translated_title,
        "content": full_content
        # "labels": ["خبر", "ارز دیجیتال", "ترجمه"] # Add labels if needed
    }
    print(f"--- در حال فراخوانی service.posts().insert برای بلاگ {BLOG_ID}...")
    sys.stdout.flush()
    start_time = time.time()
    request = service.posts().insert(
        blogId=BLOG_ID,
        body=post_body,
        isDraft=False # تنظیم به True برای تست اولیه بدون انتشار واقعی
    )
    response = request.execute()
    end_time = time.time()
    print(f"--- فراخوانی insert کامل شد (در زمان {end_time - start_time:.2f} ثانیه).")
    sys.stdout.flush()
    print("<<< پست با موفقیت ارسال شد! URL:", response.get("url", "نامشخص"))
    sys.stdout.flush()

except HttpError as e:
     # Parse HttpError content for better messages
     try:
          error_content = json.loads(e.content.decode('utf-8'))
          error_details = error_content.get('error', {})
          status_code = error_details.get('code', e.resp.status)
          error_message = error_details.get('message', str(e))
          print(f"!!! خطا در API بلاگر (کد {status_code}): {error_message}")
          sys.stdout.flush()
          if status_code == 401:
              print("!!! خطای 401 (Unauthorized): اعتبارنامه (CREDENTIALS) نامعتبر یا منقضی شده است.")
              sys.stdout.flush()
          elif status_code == 403:
               print("!!! خطای 403 (Forbidden): دسترسی به بلاگ یا انجام عملیات مجاز نیست.")
               sys.stdout.flush()
     except (json.JSONDecodeError, AttributeError):
          # Fallback if parsing error content fails
          print(f"!!! خطا در API بلاگر (وضعیت {e.resp.status}): {e}")
          sys.stdout.flush()

except Exception as e:
    print(f"!!! خطای پیش‌بینی نشده در ارسال پست به بلاگر: {type(e).__name__} - {e}")
    import traceback
    print("Traceback:")
    traceback.print_exc() # Print full traceback for unexpected errors
    sys.stdout.flush()

print("\n" + "="*50)
print(">>> اسکریپت به پایان رسید.")
print("="*50)
sys.stdout.flush()
