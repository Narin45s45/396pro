# -*- coding: utf-8 -*-
import feedparser
import os
import json
import requests
import re
from bs4 import BeautifulSoup
import time
import base64
from urllib.parse import urlparse, unquote
import sys
import uuid
import traceback
from datetime import datetime

# --- کلاس مدیریت لاگ ---
class Logger:
    def __init__(self, log_file="master_log.txt"):
        self.log_file_path = log_file
        self.terminal = sys.stdout
        # باز کردن فایل با encoding='utf-8' برای پشتیبانی از کاراکترهای فارسی
        self.log_file = open(self.log_file_path, "a", encoding='utf-8')
        separator = f"\n\n-------------------- شروع اجرای جدید: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} --------------------\n"
        self.log_file.write(separator)
        self.flush()

    def write(self, message):
        # جلوگیری از نوشتن خطوط خالی در ترمینال و فایل
        if message.strip() != "":
            self.terminal.write(message)
            self.log_file.write(message)
            self.flush()
        else:
            self.terminal.write(message)

    def flush(self):
        self.terminal.flush()
        self.log_file.flush()

    def close(self):
        end_separator = f"\n-------------------- پایان اجرا: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} --------------------\n"
        self.log_file.write(end_separator)
        self.log_file.close()

# --- تنظیمات اصلی ---
RSS_FEED_URL = "https://www.newsbtc.com/feed/"
GEMINI_MODEL_NAME = "gemini-2.5-pro"
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL_NAME}:generateContent"
IMAGE_PROXY_BASE_URL = "https://img.arzitals.ir/" # آدرس پراکسی شخصی شما

# --- خواندن متغیرهای محیطی ---
GEMINI_API_KEY = os.environ.get("GEMAPI")
WORDPRESS_MAIN_URL = os.environ.get("WORDPRESS_URL")
WORDPRESS_USER = os.environ.get("WORDPRESS_USER")
WORDPRESS_PASS = os.environ.get("WORDPRESS_PASS")

# --- تنظیمات API وردپرس ---
WORDPRESS_CUSTOM_POST_API_ENDPOINT = f"{WORDPRESS_MAIN_URL}/wp-json/my-poster/v1/create"
WORDPRESS_PROCESSED_LINKS_GET_API_ENDPOINT = f"{WORDPRESS_MAIN_URL}/wp-json/my-poster/v1/processed-links"
WORDPRESS_PROCESSED_LINKS_ADD_API_ENDPOINT = f"{WORDPRESS_MAIN_URL}/wp-json/my-poster/v1/processed-links"

# --- تنظیمات زمانبندی درخواست‌ها ---
REQUEST_TIMEOUT = 60
GEMINI_TIMEOUT = 150
MASTER_LOG_FILE = "master_log.txt"

# --- بررسی وجود متغیرهای محیطی ضروری ---
if not all([GEMINI_API_KEY, WORDPRESS_MAIN_URL, WORDPRESS_USER, WORDPRESS_PASS]):
    raise ValueError("یکی از متغیرهای محیطی ضروری (GEMAPI, WORDPRESS_URL, WORDPRESS_USER, WORDPRESS_PASS) تنظیم نشده است.")

# --- توابع کمکی ---

def generate_english_slug(title_str):
    """تولید اسلاگ انگلیسی مناسب برای URL از روی عنوان پست."""
    if not title_str: return f"post-{uuid.uuid4().hex[:12]}"
    slug = str(title_str).lower()
    slug = re.sub(r'\s+', '-', slug)
    slug = re.sub(r'[^\w\-]', '', slug)
    slug = re.sub(r'-+', '-', slug)
    slug = slug.strip('-')
    return slug if len(slug) > 4 else f"article-{uuid.uuid4().hex[:8]}"

def replace_images_with_placeholders(html_content):
    """جایگزینی تگ‌های <img> با Placeholderهای div برای ارسال به Gemini."""
    print("--- شروع جایگزینی عکس‌ها با Placeholder...")
    sys.stdout.flush()
    if not html_content: return "", {}

    soup = BeautifulSoup(html_content, "html.parser")
    images = soup.find_all("img")
    placeholder_map = {}
    count = 0
    for img in images:
        placeholder_uuid = str(uuid.uuid4())
        placeholder_div_str = f'<div class="image-placeholder-container" id="placeholder-{placeholder_uuid}">Image-Placeholder-{placeholder_uuid}</div>'
        placeholder_map[placeholder_uuid] = str(img)
        img.replace_with(BeautifulSoup(placeholder_div_str, 'html.parser'))
        count += 1
        
    print(f"--- {count} عکس با Placeholder جایگزین شد.")
    sys.stdout.flush()
    return str(soup), placeholder_map

def restore_images_from_placeholders(html_content, placeholder_map):
    """بازگرداندن تگ‌های <img> از Placeholderها بعد از ترجمه."""
    print("--- شروع بازگرداندن عکس‌ها از Placeholder...")
    sys.stdout.flush()
    if not placeholder_map: return html_content

    soup = BeautifulSoup(html_content, 'html.parser')
    count = 0
    not_found_count = 0
    for placeholder_uuid, img_tag_str in placeholder_map.items():
        target_div = soup.find('div', id=f"placeholder-{placeholder_uuid}")
        if target_div:
            target_div.replace_with(BeautifulSoup(img_tag_str, 'html.parser'))
            count += 1
        else:
            not_found_count += 1
            print(f"--- هشدار (Restore): Placeholder با شناسه 'placeholder-{placeholder_uuid}' یافت نشد!")

    print(f"--- {count} عکس از Placeholder بازگردانده شد.")
    if not_found_count > 0:
        print(f"--- هشدار جدی: {not_found_count} Placeholder در متن ترجمه شده برای بازگردانی یافت نشدند!")
    
    sys.stdout.flush()
    return str(soup)

def translate_with_gemini_api(prompt_text, timeout, max_retries=2):
    """تابع عمومی برای ارسال درخواست به Gemini API با مدیریت خطا."""
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt_text}]}],
        "generationConfig": {"temperature": 0.4, "topP": 0.9, "topK": 50}
    }
    retry_delay = 10
    for attempt in range(max_retries + 1):
        try:
            response = requests.post(f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", headers=headers, json=payload, timeout=timeout)
            if response.status_code == 429 and attempt < max_retries:
                print(f"!!! Rate Limit. منتظر {retry_delay} ثانیه...")
                time.sleep(retry_delay)
                retry_delay *= 1.5
                continue
            response.raise_for_status()
            result = response.json()

            if "candidates" in result and result["candidates"] and "text" in result["candidates"][0].get("content", {}).get("parts", [{}])[0]:
                return result["candidates"][0]["content"]["parts"][0]["text"].strip()
            else:
                raise ValueError(f"پاسخ نامعتبر از Gemini: {str(result)[:500]}")
        except requests.exceptions.RequestException as e:
            print(f"!!! خطا در درخواست به Gemini (تلاش {attempt + 1}): {e}")
            if attempt >= max_retries: raise
            time.sleep(retry_delay)
        except Exception as e:
            print(f"!!! خطای پیش‌بینی نشده در API Gemini: {e}")
            raise
    raise ValueError("ارسال به Gemini پس از تمام تلاش‌ها ناموفق بود.")


def translate_title_with_gemini(text_title):
    """ترجمه عنوان پست."""
    print(f">>> ترجمه عنوان با Gemini ({GEMINI_MODEL_NAME}): '{text_title[:50]}...'")
    prompt = (
        f"عنوان خبری انگلیسی زیر را به یک تیتر فارسی بسیار جذاب، خلاقانه و بهینه شده برای موتورهای جستجو (SEO-friendly) تبدیل کن. تیتر نهایی باید عصاره اصلی خبر را منتقل کند و کنجکاوی مخاطب را برانگیزد. از ترجمه تحت‌اللفظی پرهیز کن.\n"
        f"**فقط و فقط تیتر فارسی ساخته شده را به صورت یک خط، بدون هیچ‌گونه توضیح اضافی، علامت نقل قول یا پیشوند بازگردان.**\n"
        f"عنوان اصلی انگلیسی: \"{text_title}\"\n"
        f"تیتر فارسی:"
    )
    return translate_with_gemini_api(prompt, REQUEST_TIMEOUT)


def translate_content_with_gemini(text_to_translate):
    """ترجمه محتوای اصلی پست."""
    print(f">>> ترجمه محتوای اصلی با Gemini ({GEMINI_MODEL_NAME}) (طول: {len(text_to_translate)} کاراکتر)...")
    prompt = (
        f"متن خبر زیر را به فارسی روان بازنویسی کن. ساختار HTML و Placeholderهای تصویر (مثل <div ... id='placeholder-...') را دست نخورده باقی بگذار.\n"
        f"1. یک خلاصه دو خطی (حداکثر 230 کاراکتر) در ابتدای متن داخل تگ <div class=\"summary\" style=\"font-weight: bold;\">...</div> قرار بده.\n"
        f"2. در انتهای متن، یک نتیجه‌گیری تحلیلی (حداکثر 6 خط) داخل تگ <div class=\"conclusion\"><strong>جمع‌بندی:</strong><br>...</div> ارائه کن.\n"
        f"3. محتوای متنی توییت‌ها (تگ <blockquote> با کلاس 'twitter-tweet') را به فارسی بازنویسی کن و متن انگلیسی را حذف کن.\n"
        f"4. اصطلاحات 'bearish' و 'bullish' را به 'نزولی' و 'صعودی' ترجمه کن.\n"
        f"5. برای بولد کردن فقط از تگ <strong> یا <b> استفاده کن.\n"
        f"--- متن انگلیسی برای بازنویسی: ---\n{text_to_translate}"
    )
    translated_html = translate_with_gemini_api(prompt, GEMINI_TIMEOUT)
    # پاکسازی بک‌تیک‌های احتمالی از خروجی Gemini
    return re.sub(r'^```html\s*|\s*```$', '', translated_html, flags=re.IGNORECASE | re.DOTALL)


def translate_caption_with_gemini(text_caption):
    """ترجمه کپشن تصاویر."""
    print(f">>> ترجمه کپشن با Gemini: '{text_caption[:30]}...'")
    prompt = (
        f"کپشن تصویر زیر را به فارسی روان ترجمه کن. ساختار HTML را حفظ کن.\n"
        f"کپشن اصلی: \"{text_caption}\"\nکپشن ترجمه شده:"
    )
    return translate_with_gemini_api(prompt, REQUEST_TIMEOUT, max_retries=1)


def proxy_image_url(image_url):
    """ساخت URL پراکسی شده برای یک تصویر."""
    encoded_url = base64.urlsafe_b64encode(image_url.encode('utf-8')).decode('utf-8')
    return f"{IMAGE_PROXY_BASE_URL}?data={encoded_url}"


def replace_all_external_images_with_proxy(content_html, main_domain):
    """جایگزینی آدرس تمام تصاویر خارجی با پراکسی شخصی."""
    if not content_html: return ""
    print(">>> بازنویسی آدرس تمام عکس‌های خارجی به پراکسی شخصی...")
    soup = BeautifulSoup(content_html, "html.parser")
    images = soup.find_all("img")
    parsed_main_domain = urlparse(main_domain).netloc.replace("www.", "")
    proxy_domain = urlparse(IMAGE_PROXY_BASE_URL).netloc.replace("www.", "")

    for img_tag in images:
        img_src = img_tag.get("src", "")
        if not img_src or not img_src.startswith(('http://', 'https://')): continue
        
        img_domain = urlparse(img_src).netloc.replace("www.", "")
        if img_domain and img_domain != parsed_main_domain and img_domain != proxy_domain:
            print(f"--- عکس خارجی یافت شد ({img_src[:70]}...)، در حال بازنویسی...")
            img_tag['src'] = proxy_image_url(img_src)
            
    return str(soup)


def crawl_captions(post_url):
    """کرال کردن صفحه اصلی پست برای استخراج و ترجمه کپشن‌ها."""
    print(f">>> شروع کرال و ترجمه کپشن‌ها از: {post_url}")
    captions_data = []
    try:
        response = requests.get(post_url, timeout=REQUEST_TIMEOUT, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        figures = soup.find_all("figure")
        print(f"--- تعداد <figure> یافت شده برای بررسی کپشن: {len(figures)}")

        for figure in figures:
            img = figure.find("img")
            figcaption = figure.find("figcaption")
            if img and figcaption and img.get("src"):
                normalized_img_src = urlparse(unquote(img["src"]))._replace(query='').geturl()
                translated_caption = translate_caption_with_gemini(str(figcaption))
                if translated_caption:
                    captions_data.append({"image_url": normalized_img_src, "caption": translated_caption})
        
        # حذف کپشن‌های تکراری
        unique_captions = list({v['caption']: v for v in captions_data}.values())
        print(f"<<< کرال و ترجمه کپشن‌ها تمام شد. {len(unique_captions)} کپشن منحصر به فرد یافت شد.")
        return unique_captions
    except Exception as e:
        print(f"!!! خطا در کرال یا ترجمه کپشن‌ها: {e}")
        return []


def add_captions_to_images(content_html, captions_list):
    """افزودن کپشن‌های ترجمه شده به تگ‌های figure یا به انتهای پست."""
    if not captions_list or not content_html: return content_html
    print(">>> شروع افزودن کپشن‌های ترجمه شده به محتوا...")
    soup = BeautifulSoup(content_html, "html.parser")
    images = soup.find_all("img")
    
    used_captions = set()
    for img in images:
        img_src = img.get("src", "")
        if not img_src: continue
        
        # برای تطابق، آدرس پراکسی شده را به آدرس اصلی برمی‌گردانیم
        try:
            if IMAGE_PROXY_BASE_URL in img_src:
                base64_str = urlparse(img_src).query.split('data=')[-1]
                original_src = base64.urlsafe_b64decode(base64_str).decode('utf-8')
            else:
                original_src = img_src
            normalized_src = urlparse(unquote(original_src))._replace(query='').geturl()
        except Exception:
            continue

        for i, cap_data in enumerate(captions_list):
            if i not in used_captions and cap_data["image_url"] == normalized_src:
                parent_p = img.find_parent('p')
                new_figure = soup.new_tag("figure", style="margin:1em auto; text-align:center; max-width:100%;")
                img.wrap(new_figure)
                new_figure.append(BeautifulSoup(cap_data["caption"], 'html.parser'))
                if parent_p and not parent_p.get_text(strip=True):
                    parent_p.unwrap()
                used_captions.add(i)
                break
                
    # افزودن کپشن‌های باقی‌مانده به انتهای پست
    remaining_captions_html = "".join([c['caption'] for i, c in enumerate(captions_list) if i not in used_captions])
    if remaining_captions_html:
        print(f"--- افزودن {len(captions_list) - len(used_captions)} کپشن باقی‌مانده به انتهای محتوا...")
        soup.append(BeautifulSoup(f'<div style="text-align: center; margin-top: 20px;">{remaining_captions_html}</div>', "html.parser"))
        
    return str(soup)


def post_to_wordpress(post_data):
    """ارسال پست نهایی به وردپرس از طریق endpoint سفارشی."""
    print(f">>> شروع ارسال پست '{post_data['title'][:50]}...' به وردپرس...")
    credentials = f"{WORDPRESS_USER}:{WORDPRESS_PASS}"
    token = base64.b64encode(credentials.encode()).decode('utf-8')
    headers = {
        'Authorization': f'Basic {token}',
        'Content-Type': 'application/json',
        'User-Agent': 'Rss-To-WordPress-Script/4.0'
    }
    
    max_retries, retry_delay = 2, 25
    for attempt in range(max_retries + 1):
        print(f"--- تلاش {attempt + 1}/{max_retries + 1} برای ارسال...")
        try:
            response = requests.post(WORDPRESS_CUSTOM_POST_API_ENDPOINT, headers=headers, json=post_data, timeout=REQUEST_TIMEOUT * 2)
            response.raise_for_status()
            response_data = response.json()
            if response.status_code == 201 and response_data.get("post_id"):
                print(f"<<< پست با موفقیت ارسال شد! URL: {response_data.get('url', 'نامشخص')}")
                return response_data
            else:
                raise ValueError(f"پاسخ غیرمنتظره از وردپرس: {response_data}")
        except requests.exceptions.HTTPError as e:
            error_text = e.response.text
            raise ValueError(f"خطای HTTP در ارسال به وردپرس (کد {e.response.status_code}): {error_text[:500]}")
        except Exception as e:
            print(f"!!! خطای ناشناخته در ارسال به وردپرس: {e}")
            if attempt >= max_retries: raise
            time.sleep(retry_delay)
    raise ValueError("ارسال پست پس از تمام تلاش‌ها ناموفق بود.")


def manage_processed_links(action, link_url=None):
    """مدیریت لینک‌های پردازش شده (دریافت لیست یا افزودن لینک جدید)."""
    credentials = f"{WORDPRESS_USER}:{WORDPRESS_PASS}"
    token = base64.b64encode(credentials.encode()).decode('utf-8')
    headers = {'Authorization': f'Basic {token}', 'Content-Type': 'application/json'}
    
    try:
        if action == 'get':
            print("--- در حال دریافت لیست لینک‌های پردازش شده از وردپرس...")
            response = requests.get(WORDPRESS_PROCESSED_LINKS_GET_API_ENDPOINT, headers=headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            links = response.json()
            print(f"--- {len(links)} لینک پردازش شده از وردپرس دریافت شد.")
            return set(links)
        
        elif action == 'add' and link_url:
            print(f"--- در حال افزودن لینک '{link_url}' به لیست پردازش شده...")
            response = requests.post(WORDPRESS_PROCESSED_LINKS_ADD_API_ENDPOINT, headers=headers, json={"link": link_url}, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            print(f"--- لینک با موفقیت در وردپرس اضافه شد: {response.json().get('message', '')}")
            return True
            
    except Exception as e:
        raise ValueError(f"خطا در ارتباط با API لینک‌های پردازش شده وردپرس: {e}")

# --- شروع اسکریپت اصلی ---
if __name__ == "__main__":
    logger = Logger(log_file=MASTER_LOG_FILE)
    sys.stdout = logger
    main_start_time = time.time()
    
    print("شروع پردازش فید RSS و ارسال به وردپرس")
    
    try:
        # مرحله ۰: بررسی پست‌های تکراری
        print("\n>>> مرحله ۰: بررسی پست‌های تکراری...")
        processed_links = manage_processed_links('get')

        # مرحله ۱: دریافت و تجزیه فید RSS
        print("\n>>> مرحله ۱: دریافت و تجزیه فید RSS...")
        feed = feedparser.parse(RSS_FEED_URL)
        if feed.bozo: print(f"--- هشدار در تجزیه فید: {feed.bozo_exception}")
        if not feed.entries: raise ValueError("هیچ پستی در فید RSS یافت نشد.")

        latest_post = feed.entries[0]
        post_link = getattr(latest_post, 'link', None)
        if not post_link: raise ValueError("پست یافت شده فاقد لینک منبع است.")

        if post_link in processed_links:
            print("\n*** پست تکراری یافت شد. پردازش متوقف شد. ***")
            sys.exit(0)
            
        post_title = latest_post.title
        print(f"--- جدیدترین پست (غیر تکراری) انتخاب شد: '{post_title}'")

        # --- پردازش و پراکسی کردن تصویر شاخص ---
        thumbnail_url = None
        if hasattr(latest_post, 'media_content') and latest_post.media_content:
            raw_thumbnail = latest_post.media_content[0].get('url', '')
            if raw_thumbnail and raw_thumbnail.startswith(('http://', 'https://')):
                print(f"--- URL خام تصویر شاخص یافت شد: {raw_thumbnail}")
                thumbnail_url = proxy_image_url(raw_thumbnail)
                print(f"--- URL پراکسی شده نهایی برای تصویر شاخص: {thumbnail_url}")
            else:
                print(f"--- هشدار: URL تصویر بندانگشتی معتبر نیست: '{raw_thumbnail}'")
        else:
            print("--- هیچ تصویر بندانگشتی (media_content) در فید یافت نشد.")
        print("<<< مرحله ۱ کامل شد.")

        # مرحله ۲: کرال و ترجمه کپشن‌ها
        print("\n>>> مرحله ۲: کرال و ترجمه کپشن‌ها...")
        captions = crawl_captions(post_link)
        print(f"<<< مرحله ۲ کامل شد (تعداد کپشن نهایی: {len(captions)}).")

        # مرحله ۳: ترجمه عنوان
        print("\n>>> مرحله ۳: ترجمه عنوان پست...")
        translated_title = translate_title_with_gemini(post_title)
        print(f"--- عنوان ترجمه‌شده نهایی: {translated_title}")
        print("<<< مرحله ۳ کامل شد.")

        # مرحله ۴: پردازش کامل محتوای اصلی
        print("\n>>> مرحله ۴: پردازش کامل محتوای اصلی...")
        raw_content = latest_post.get('content', [{}])[0].get('value', '') or latest_post.get('summary', '')
        if not raw_content: raise ValueError("محتوای اصلی یافت نشد.")
        print(f"--- محتوای خام از فید دریافت شد (طول: {len(raw_content)} کاراکتر).")

        # پراکسی کردن تصاویر داخل محتوا
        content_with_proxied_images = replace_all_external_images_with_proxy(raw_content, WORDPRESS_MAIN_URL)
        
        # جایگزینی تصاویر با Placeholder برای ترجمه
        content_with_placeholders, placeholder_map = replace_images_with_placeholders(content_with_proxied_images)
        
        # ترجمه محتوا
        translated_content_with_placeholders = translate_content_with_gemini(content_with_placeholders)
        
        # بازگرداندن تصاویر از Placeholder
        translated_content_with_images = restore_images_from_placeholders(translated_content_with_placeholders, placeholder_map)

        # افزودن کپشن‌های ترجمه شده
        final_content = add_captions_to_images(translated_content_with_images, captions)
        print("<<< مرحله ۴ (پردازش محتوا) کامل شد.")

        # مرحله ۵: آماده‌سازی ساختار نهایی HTML
        print("\n>>> مرحله ۵: آماده‌سازی ساختار نهایی HTML پست...")
        disclaimer = '<strong>سلب مسئولیت:</strong> احتمال اشتباه در تحلیل ها وجود دارد و هیچ تحلیلی قطعی نیست. لطفا در خرید و فروش خود دقت کنید.'
        disclaimer_html = f'<div style="color:#c00;font-size:0.9em;margin-top:25px;text-align:justify;border:1px solid #fdd;background-color:#fff9f9;padding:15px;border-radius:5px;">{disclaimer}</div>'
        source_html = f'<hr style="margin-top:25px;border:0;border-top:1px solid #eee;"><p style="text-align:right;font-size:0.85em;color:#555;"><em><a href="{post_link}" target="_blank" rel="noopener noreferrer nofollow" style="color:#1a0dab;text-decoration:none;">منبع: NewsBTC</a></em></p>'
        
        full_html_content = f'<div style="line-height:1.75;font-size:17px;text-align:justify;">{final_content}</div>{disclaimer_html}{source_html}'
        print("<<< مرحله ۵ (ساختار نهایی) کامل شد.")
        
        # مرحله ۶: ارسال پست به وردپرس
        print("\n>>> مرحله ۶: ارسال پست به وردپرس...")
        post_data_payload = {
            "title": translated_title,
            "content": full_html_content,
            "slug": generate_english_slug(post_title),
            "category_id": 69, # آیدی دسته بندی مورد نظر
            "thumbnail_url": thumbnail_url or "",
            "source_url": post_link
        }
        post_to_wordpress(post_data_payload)
        print("<<< مرحله ۶ (ارسال به وردپرس) کامل شد.")

        # مرحله ۷: ذخیره کردن لینک منبع
        print("\n>>> مرحله ۷: ذخیره کردن لینک منبع برای جلوگیری از تکرار...")
        manage_processed_links('add', link_url=post_link)
        print("<<< مرحله ۷ کامل شد.")

    except Exception as e:
        print("\n" + "!"*70 + "\n!!! خطای کلی و بحرانی در اجرای اسکریپت رخ داد. !!!")
        print(f"!!! نوع خطا: {type(e).__name__}");
        print(f"!!! پیام خطا: {e}")
        print("--- جزئیات Traceback ---")
        traceback.print_exc()
        print("!"*70 + "\n")
        sys.exit(1)

    finally:
        total_time = time.time() - main_start_time
        print(f"\nاسکریپت به پایان رسید (زمان کل: {total_time:.2f} ثانیه).")
        if 'logger' in locals() and isinstance(logger, Logger):
            logger.close()
            # بازگرداندن خروجی استاندارد به حالت اولیه
            sys.stdout = logger.terminal
