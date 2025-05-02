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
import sys
import uuid # برای ساخت placeholder های منحصر به فرد

# --- تنظیمات ---
RSS_FEED_URL = "https://www.newsbtc.com/feed/"
GEMINI_API_KEY = os.environ.get("GEMAPI")
if not GEMINI_API_KEY:
    raise ValueError("!متغیر محیطی GEMAPI پیدا نشد")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

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
sys.stdout.flush()
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
GEMINI_TIMEOUT = 120 # افزایش بیشتر Timeout برای احتیاط

# --- تابع جایگزینی عکس با Placeholder ---
def replace_images_with_placeholders(html_content):
    """
    تمام تگ های <img> را با placeholder جایگزین می کند و نقشه آن را برمی گرداند.
    """
    print("--- شروع جایگزینی عکس‌ها با Placeholder...")
    sys.stdout.flush()
    if not html_content:
        return "", {}

    soup = BeautifulSoup(html_content, "html.parser")
    images = soup.find_all("img")
    placeholder_map = {}
    placeholder_prefix = "##IMG_PLACEHOLDER_"
    count = 0

    for img in images:
        placeholder = f"{placeholder_prefix}{uuid.uuid4()}##" # Placeholder منحصر به فرد
        # ذخیره کل تگ img به صورت رشته
        placeholder_map[placeholder] = str(img)
        # جایگزینی تگ img با متن placeholder
        img.replace_with(placeholder)
        count += 1

    modified_html = str(soup)
    print(f"--- {count} عکس با Placeholder جایگزین شد.")
    sys.stdout.flush()
    return modified_html, placeholder_map

# --- تابع بازگرداندن عکس از Placeholder ---
def restore_images_from_placeholders(html_content, placeholder_map):
    """
    Placeholder ها را با تگ های <img> اصلی جایگزین می کند.
    """
    print("--- شروع بازگرداندن عکس‌ها از Placeholder...")
    sys.stdout.flush()
    if not placeholder_map:
        return html_content

    restored_content = html_content
    count = 0
    for placeholder, img_tag_str in placeholder_map.items():
        # از replace استفاده می کنیم چون ممکن است ترجمه کمی ساختار را تغییر دهد
        if placeholder in restored_content:
             restored_content = restored_content.replace(placeholder, img_tag_str, 1) # فقط یکبار جایگزین کن
             count += 1
        else:
             print(f"--- هشدار: Placeholder '{placeholder}' در متن ترجمه شده یافت نشد!")
             sys.stdout.flush()


    print(f"--- {count} عکس از Placeholder بازگردانده شد.")
    sys.stdout.flush()
    return restored_content
    
def call_gemini(prompt):
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0, "topP": 0.95, "topK": 40}
    }
    response = requests.post(
        f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
        headers=headers,
        json=payload,
        timeout=GEMINI_TIMEOUT
    )
    response.raise_for_status()
    result = response.json()
    if not result or "candidates" not in result or not result["candidates"]:
        raise ValueError("پاسخ غیرمنتظره از API Gemini")
    candidate = result["candidates"][0]
    if "content" not in candidate or "parts" not in candidate["content"] or not candidate["content"]["parts"]:
        raise ValueError("ترجمه ناقص از Gemini دریافت شد")
    return candidate["content"]["parts"][0]["text"]

# --- تابع بازنویسی با Gemini ---
def translate_with_gemini(text, target_lang="fa"):  # اسم تابع رو تغییر ندادم چون توی جاهای دیگه کد استفاده شده
    print(f">>> شروع بازنویسی متن با Gemini (طول متن: {len(text)} کاراکتر)...")
    sys.stdout.flush()
    if not text or text.isspace():
        print("--- متن ورودی برای بازنویسی خالی است. رد شدن از بازنویسی.")
        sys.stdout.flush()
        return ""

    prompt = f"""
    متن زیر را به فارسی روان و ساده بازنویسی کن تا برای خوانندگان عمومی قابل فهم باشد.
    از کلمات پیچیده استفاده نکن و مفهوم اصلی را حفظ کن:
    {text}
    """
    try:
        rewritten_text = call_gemini(prompt)
        print("<<< بازنویسی متن با Gemini با موفقیت انجام شد.")
        sys.stdout.flush()
        return rewritten_text.strip()
    except Exception as e:
        print(f"!!! خطا در بازنویسی با Gemini: {e}")
        sys.stdout.flush()
        raise

# --- بقیه توابع (remove_newsbtc_links, replace_twimg_with_base64, crawl_captions, add_captions_to_images) ---
# این توابع تقریباً بدون تغییر باقی می‌مانند، فقط لاگ‌ها حفظ می‌شوند.
# (برای اختصار از تکرار کد کامل آنها خودداری می شود، فرض بر این است که از نسخه قبلی استفاده می شود)
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
        if "twimg.com" in src:
            twimg_count += 1
            print(f"--- عکس {i+1} از twimg.com است. شروع دانلود و تبدیل...")
            sys.stdout.flush()
            try:
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
                response = requests.get(src, stream=True, timeout=REQUEST_TIMEOUT, headers=headers)
                response.raise_for_status()
                content_type = response.headers.get('content-type', '').split(';')[0].strip()
                if not content_type or not content_type.startswith('image/'):
                    parsed_url = urlparse(src)
                    path = parsed_url.path
                    ext = os.path.splitext(path)[1].lower()
                    mime_map = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.gif': 'image/gif', '.webp': 'image/webp'}
                    content_type = mime_map.get(ext, 'image/jpeg')

                image_content = response.content
                base64_encoded_data = base64.b64encode(image_content)
                base64_string = base64_encoded_data.decode('utf-8')
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
                    # ترجمه کپشن
                    print(f"--- ترجمه کپشن برای تصویر: {img_src[:60]}...")
                    sys.stdout.flush()
                    translated_caption = translate_with_gemini(caption_html)
                    captions_with_images.append({"image_url": img_src, "caption": translated_caption})
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
        # Print final captions found
        print("--- کپشن‌های نهایی یافت شده:")
        for i, item in enumerate(unique_captions):
            print(f"    کپشن {i+1}: (عکس: {item['image_url'][:60]}...) متن: {BeautifulSoup(item['caption'], 'html.parser').get_text(strip=True)[:80]}...")
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
        print(f"!!! خطای غیرمنتظره در کرال کردن کپشن‌ها: {e}")
        sys.stdout.flush()
        return []

# --- تابع قرار دادن کپشن‌ها زیر عکس‌ها ---
def add_captions_to_images(content, original_captions_with_images):
    if not original_captions_with_images:
        print("--- هیچ کپشنی برای اضافه کردن وجود ندارد. رد شدن...")
        sys.stdout.flush()
        return content
    if not content:
        print("--- محتوای ورودی برای اضافه کردن کپشن خالی است. رد شدن...")
        sys.stdout.flush()
        return ""

    print(">>> شروع اضافه کردن کپشن‌ها به محتوای (احتمالا ترجمه‌شده)...")
    sys.stdout.flush()

    soup = BeautifulSoup(content, "html.parser")
    images = soup.find_all("img")  # پیدا کردن دوباره عکس‌ها بعد از بازیابی احتمالی
    print(f"--- تعداد عکس‌های یافت شده در محتوا: {len(images)}")
    sys.stdout.flush()

    if not images:
        print("--- هیچ عکسی در محتوا یافت نشد. کپشن‌ها در انتها اضافه می‌شوند.")
        sys.stdout.flush()
        captions_html = "".join([item['caption'] for item in original_captions_with_images])
        final_captions_div = soup.new_tag('div', style="text-align: center; margin-top: 15px; font-size: small;")
        final_captions_div.append(BeautifulSoup(captions_html, "html.parser"))
        soup.append(final_captions_div)
        return str(soup)

    used_caption_indices = set()
    captions_added_count = 0

    for img_index, img in enumerate(images):
        img_src = img.get("src", "")
        if not img_src:
            print(f"--- هشدار: عکس {img_index + 1} بدون src است. رد شدن...")
            sys.stdout.flush()
            continue

        # پیدا کردن کپشن مطابق با URL تصویر
        matching_caption_data = None
        matching_caption_index = -1
        for idx, caption_data in enumerate(original_captions_with_images):
            if idx in used_caption_indices:
                continue
            original_url = caption_data["image_url"]
            # مقایسه URLها (ممکنه URLها کمی تغییر کرده باشن، پس فقط بخش اصلی رو مقایسه می‌کنیم)
            original_url_base = urlparse(original_url).path
            img_src_base = urlparse(img_src).path if not img_src.startswith("data:") else ""
            if original_url_base and img_src_base and original_url_base in img_src_base:
                matching_caption_data = caption_data
                matching_caption_index = idx
                break
            # اگه تصویر به Base64 تبدیل شده، مستقیماً نمی‌تونیم URL رو مقایسه کنیم
            # در این صورت، باید یه روش دیگه برای مطابقت پیدا کنیم (مثلاً از alt یا ترتیب به عنوان fallback)
            elif img_src.startswith("data:"):
                # برای تصاویر Base64، از alt یا ترتیب به عنوان fallback استفاده می‌کنیم
                img_alt = img.get("alt", "")
                caption_text = BeautifulSoup(caption_data['caption'], 'html.parser').get_text(strip=True)
                if img_alt and caption_text and caption_text.lower() in img_alt.lower():
                    matching_caption_data = caption_data
                    matching_caption_index = idx
                    break

        if matching_caption_data and matching_caption_index >= 0:
            print(f"--- افزودن کپشن {matching_caption_index + 1} به عکس {img_index + 1} (URL: {img_src[:60]}...)")
            sys.stdout.flush()
            matching_caption_html = matching_caption_data["caption"]

            # ساخت تگ figure برای کپشن و عکس
            figure = soup.new_tag("figure")
            figure['style'] = "margin: 1em auto; text-align: center; max-width: 100%;"

            parent = img.parent
            if parent.name in ['p', 'div'] and not parent.get_text(strip=True):  # فقط اگه والد یه wrapper ساده باشه
                parent.replace_with(figure)
                figure.append(img)
            else:
                img.wrap(figure)  # در غیر این صورت فقط wrap کن

            caption_soup = BeautifulSoup(matching_caption_html, "html.parser")
            caption_content = caption_soup.find(['figcaption', 'p', 'div', 'span'])
            if not caption_content:  # اگه فقط متن باشه
                caption_content = soup.new_tag('figcaption')
                caption_content.string = caption_soup.get_text(strip=True)
            elif caption_content.name != 'figcaption':
                new_figcaption = soup.new_tag('figcaption')
                new_figcaption.contents = caption_content.contents
                new_figcaption['style'] = caption_content.get('style', '')
                caption_content = new_figcaption

            if caption_content:
                caption_content['style'] = caption_content.get('style', '') + ' text-align: center; font-size: small; margin-top: 5px; color: #555;'
                figure.append(caption_content)
                used_caption_indices.add(matching_caption_index)
                captions_added_count += 1
                print(f"---   کپشن {matching_caption_index + 1} اضافه شد.")
                sys.stdout.flush()
            else:
                print(f"---   هشدار: محتوای کپشن {matching_caption_index + 1} یافت نشد.")
                sys.stdout.flush()
        else:
            print(f"--- هشدار: هیچ کپشن مطابق برای عکس {img_index + 1} یافت نشد (URL: {img_src[:60]}...)")
            sys.stdout.flush()

    # اضافه کردن کپشن‌های استفاده‌نشده به انتها
    remaining_captions_html = ""
    remaining_count = 0
    for i, item in enumerate(original_captions_with_images):
        if i not in used_caption_indices:
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
# ... (کد مانند قبل) ...
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
# ... (کد مانند قبل) ...
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
# ... (کد مانند قبل) ...
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
# ... (کد مانند قبل، از replace_twimg_with_base64 استفاده می‌کند) ...
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
                # Use the base64 function directly here as well
                converted_soup = BeautifulSoup(replace_twimg_with_base64(temp_img_tag), "html.parser")
                img_tag_after_conversion = converted_soup.find("img")
                if img_tag_after_conversion and img_tag_after_conversion.get("src", "").startswith("data:"):
                     final_src = img_tag_after_conversion["src"]
                     print("--- تصویر بندانگشتی twimg با موفقیت به Base64 تبدیل شد.")
                     sys.stdout.flush()
                else:
                     print("--- هشدار: تبدیل تصویر بندانگشتی twimg ناموفق بود. از URL اصلی استفاده می‌شود.")
                     sys.stdout.flush()

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
else: print("<<< مرحله ۴ رد شد.")
sys.stdout.flush()


# 5. پردازش محتوای اصلی (با Placeholder)
print("\n>>> مرحله ۵: پردازش محتوای اصلی...")
sys.stdout.flush()
content_html = ""
final_content_for_post = "<p>خطا: محتوای نهایی ایجاد نشد.</p>"
placeholder_map_global = {} # برای استفاده در حالت خطا

try:
    content_source = ""
    # ... (کد دریافت content_source مانند قبل) ...
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

        # 5.3 **جایگزینی همه عکس‌ها با Placeholder**
        print("--- 5.3 جایگزینی همه عکس‌ها با Placeholder قبل از ترجمه...")
        sys.stdout.flush()
        content_with_placeholders, placeholder_map_global = replace_images_with_placeholders(content_with_base64_images)
        print("--- جایگزینی با Placeholder کامل شد.")
        sys.stdout.flush()

        # 5.4 ترجمه محتوا (حالا با Placeholderها)
        print("--- 5.4 ترجمه محتوای حاوی Placeholder...")
        sys.stdout.flush()
        translated_content_with_placeholders = translate_with_gemini(content_with_placeholders)
        print("--- ترجمه محتوای حاوی Placeholder کامل شد.")
        sys.stdout.flush()

        # 5.5 **بازگرداندن عکس‌ها از Placeholder**
        print("--- 5.5 بازگرداندن عکس‌ها از Placeholder در متن ترجمه شده...")
        sys.stdout.flush()
        translated_content_restored = restore_images_from_placeholders(translated_content_with_placeholders, placeholder_map_global)
        print("--- بازگرداندن عکس‌ها کامل شد.")
        sys.stdout.flush()

        # 5.6 اضافه کردن کپشن‌ها به محتوای ترجمه شده و بازیابی شده
        print("--- 5.6 اضافه کردن کپشن‌ها به محتوای نهایی...")
        sys.stdout.flush()
        content_with_captions = add_captions_to_images(translated_content_restored, original_captions_with_images)
        print("--- اضافه کردن کپشن‌ها کامل شد.")
        sys.stdout.flush()

        # 5.7 تنظیمات نهایی استایل و پاکسازی
        print("--- 5.7 اعمال استایل نهایی به عکس‌ها و پاکسازی HTML...")
        sys.stdout.flush()
        soup_final = BeautifulSoup(content_with_captions, "html.parser")
        for img_tag in soup_final.find_all("img"):
            img_tag['style'] = img_tag.get('style', '') + ' max-width:100%; height:auto; display:block; margin-left:auto; margin-right:auto; border-radius: 3px;'
            if not img_tag.get('alt'):
                img_tag['alt'] = translated_title

        for p_tag in soup_final.find_all('p'):
            if not p_tag.get_text(strip=True) and not p_tag.find(['img', 'br', 'figure', 'iframe']):
                p_tag.decompose()

        content_html = str(soup_final)
        print("--- استایل‌دهی نهایی و پاکسازی کامل شد.")
        sys.stdout.flush()
        final_content_for_post = f'<div style="line-height: 1.7;">{content_html}</div>' # Wrapper بدون direction

    elif original_captions_with_images:
         # ... (مانند قبل) ...
        print("--- هشدار: محتوای اصلی یافت نشد، فقط از کپشن‌ها استفاده می‌شود.")
        sys.stdout.flush()
        captions_html = "".join([item["caption"] for item in original_captions_with_images])
        final_content_for_post = f'<div style="text-align: center; font-size: small;">{captions_html}</div>'
    else:
        # ... (مانند قبل) ...
        print("!!! محتوایی برای پردازش یافت نشد.")
        sys.stdout.flush()
        final_content_for_post = "<p style='text-align: center;'>محتوایی برای نمایش یافت نشد.</p>"

except Exception as e:
    print(f"!!! خطای جدی در پردازش محتوای اصلی (مرحله ۵): {type(e).__name__} - {e}")
    import traceback
    print("Traceback:")
    traceback.print_exc()
    sys.stdout.flush()
    # Fallback: نمایش محتوای اصلی انگلیسی، اما سعی کن عکس ها را از placeholder بازگردانی کنی
    if 'content_with_base64_images' in locals() and content_with_base64_images:
         print("--- استفاده از محتوای انگلیسی پردازش شده به عنوان جایگزین...")
         sys.stdout.flush()
         # حتی در حالت خطا، سعی کن کپشن ها را اضافه کنی
         try:
              content_fallback_with_captions = add_captions_to_images(content_with_base64_images, original_captions_with_images)
              final_content_for_post = f"<p style='color: red;'><i>[خطا در ترجمه محتوا رخ داد ({e}). محتوای اصلی (انگلیسی) با کپشن‌ها در زیر نمایش داده می‌شود.]</i></p><div style='text-align:left; direction:ltr;'>{content_fallback_with_captions}</div>"
         except Exception as fallback_e:
              print(f"!!! خطا در افزودن کپشن به محتوای جایگزین: {fallback_e}")
              final_content_for_post = f"<p style='color: red;'><i>[خطا در ترجمه محتوا رخ داد ({e}). محتوای اصلی (انگلیسی) در زیر نمایش داده می‌شود.]</i></p><div style='text-align:left; direction:ltr;'>{content_with_base64_images}</div>"

    else:
         final_content_for_post = f"<p style='text-align: center; color: red;'>خطای جدی در پردازش محتوا: {e}</p>"

print("<<< مرحله ۵ کامل شد.")
sys.stdout.flush()


# 6. ساختار نهایی پست
print("\n>>> مرحله ۶: آماده‌سازی ساختار نهایی پست HTML...")
# ... (کد مانند قبل) ...
sys.stdout.flush()
full_content_parts = []
if thumbnail_html:
    full_content_parts.append(thumbnail_html)
if final_content_for_post:
    full_content_parts.append(final_content_for_post)
if post_link and post_link.startswith(('http://', 'https://')):
    full_content_parts.append(f'<div style="text-align:right; margin-top:15px; font-size: small; color: #777;"><a href="{post_link}" target="_blank" rel="noopener noreferrer nofollow">منبع: NewsBTC</a></div>')

full_content = "".join(full_content_parts)
print("<<< مرحله ۶ کامل شد.")
sys.stdout.flush()

# 7. ارسال به بلاگر
print("\n>>> مرحله ۷: ارسال پست به بلاگر...")
# ... (کد مانند قبل با لاگ و مدیریت خطا) ...
sys.stdout.flush()
try:
    post_body = {
        "kind": "blogger#post",
        "blog": {"id": BLOG_ID},
        "title": translated_title,
        "content": full_content
        # "labels": ["خبر", "ارز دیجیتال", "ترجمه"]
    }
    print(f"--- در حال فراخوانی service.posts().insert برای بلاگ {BLOG_ID}...")
    sys.stdout.flush()
    start_time = time.time()
    request = service.posts().insert(
        blogId=BLOG_ID,
        body=post_body,
        isDraft=False
    )
    response = request.execute()
    end_time = time.time()
    print(f"--- فراخوانی insert کامل شد (در زمان {end_time - start_time:.2f} ثانیه).")
    sys.stdout.flush()
    print("<<< پست با موفقیت ارسال شد! URL:", response.get("url", "نامشخص"))
    sys.stdout.flush()

except HttpError as e:
     # ... (مدیریت خطای HttpError مانند قبل) ...
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
          print(f"!!! خطا در API بلاگر (وضعیت {e.resp.status}): {e}")
          sys.stdout.flush()

except Exception as e:
    # ... (مدیریت خطای عمومی مانند قبل) ...
    print(f"!!! خطای پیش‌بینی نشده در ارسال پست به بلاگر: {type(e).__name__} - {e}")
    import traceback
    print("Traceback:")
    traceback.print_exc()
    sys.stdout.flush()


print("\n" + "="*50)
print(">>> اسکریپت به پایان رسید.")
print("="*50)
sys.stdout.flush()
