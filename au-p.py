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
        self.log_file = open(self.log_file_path, "a", encoding='utf-8')
        separator = f"\n\n-------------------- شروع اجرای جدید: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} --------------------\n"
        self.log_file.write(separator)
        self.flush()

    def write(self, message):
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
GEMINI_MODEL_NAME = "gemini-1.5-pro-latest"
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL_NAME}:generateContent"

# --- خواندن متغیرهای محیطی ---
GEMINI_API_KEY = os.environ.get("GEMAPI")
WORDPRESS_MAIN_URL = os.environ.get("WORDPRESS_URL")
WORDPRESS_USER = os.environ.get("WORDPRESS_USER")
WORDPRESS_PASS = os.environ.get("WORDPRESS_PASS")
IMAGE_PROXY_URL = os.environ.get("IMAGE_PROXY_URL")

# --- تنظیمات API وردپرس ---
WORDPRESS_CUSTOM_POST_API_ENDPOINT = f"{WORDPRESS_MAIN_URL}/wp-json/my-poster/v1/create"
WORDPRESS_PROCESSED_LINKS_GET_API_ENDPOINT = f"{WORDPRESS_MAIN_URL}/wp-json/my-poster/v1/processed-links"
WORDPRESS_PROCESSED_LINKS_ADD_API_ENDPOINT = f"{WORDPRESS_MAIN_URL}/wp-json/my-poster/v1/processed-links"

REQUEST_TIMEOUT = 60
GEMINI_TIMEOUT = 150
MASTER_LOG_FILE = "master_log.txt"

if not all([GEMINI_API_KEY, WORDPRESS_MAIN_URL, WORDPRESS_USER, WORDPRESS_PASS, IMAGE_PROXY_URL]):
    raise ValueError("یکی از متغیرهای محیطی ضروری (GEMAPI, WORDPRESS_URL, WORDPRESS_USER, WORDPRESS_PASS, IMAGE_PROXY_URL) تنظیم نشده است.")

# --- توابع کمکی ---
def generate_english_slug(title_str):
    if not title_str: return f"post-{uuid.uuid4().hex[:12]}"
    slug = str(title_str).lower()
    slug = re.sub(r'\s+', '-', slug); slug = re.sub(r'[^\w\-]', '', slug)
    slug = re.sub(r'-+', '-', slug); slug = slug.strip('-')
    return slug if len(slug) > 4 else f"article-{uuid.uuid4().hex[:8]}"

def replace_images_with_placeholders(html_content):
    print("--- شروع جایگزینی عکس‌ها با Placeholder (روش کامنت)...")
    sys.stdout.flush()
    if not html_content: return "", {}
    soup = BeautifulSoup(html_content, "html.parser")
    images = soup.find_all("img")
    placeholder_map = {}
    count = 0
    for i, img in enumerate(images):
        from bs4 import Comment
        placeholder_uuid = str(uuid.uuid4())
        placeholder_map[placeholder_uuid] = str(img) 
        placeholder_comment_str = f" IMG_PLACEHOLDER_{placeholder_uuid} "
        img.replace_with(Comment(placeholder_comment_str))
        count += 1
    print(f"--- {count} عکس با Placeholder نوع کامنت جایگزین شد.")
    sys.stdout.flush()
    return str(soup), placeholder_map

def restore_images_from_placeholders(html_content, placeholder_map):
    print("--- شروع بازگرداندن عکس‌ها از Placeholder (روش بهینه re)...")
    sys.stdout.flush()
    if not placeholder_map:
        return html_content
    modified_content = html_content
    count = 0
    not_found_count = 0
    for placeholder_uuid, img_tag_str in placeholder_map.items():
        placeholder_regex = re.compile(fr"")
        modified_content, num_replacements = placeholder_regex.subn(img_tag_str, modified_content, count=1)
        if num_replacements > 0:
            count += 1
        else:
            not_found_count += 1
            print(f"--- هشدار (Restore): Placeholder با شناسه '{placeholder_uuid}' یافت نشد!")
    print(f"--- {count} عکس از Placeholder بازگردانده شد.")
    if not_found_count > 0:
        print(f"--- هشدار جدی: {not_found_count} Placeholder در متن ترجمه شده برای بازگردانی یافت نشدند!")
    sys.stdout.flush()
    return modified_content

def translate_title_with_gemini(text_title):
    print(f">>> ترجمه عنوان با Gemini ({GEMINI_MODEL_NAME}): '{text_title[:50]}...'")
    sys.stdout.flush()
    if not text_title or text_title.isspace(): raise ValueError("متن عنوان برای ترجمه خالی است.")
    headers = {"Content-Type": "application/json"}
    prompt = (
        f"عنوان خبری انگلیسی زیر را به یک تیتر فارسی **بسیار جذاب، خلاقانه و بهینه شده برای موتورهای جستجو (SEO-friendly)** تبدیل کن. تیتر نهایی باید عصاره اصلی خبر را منتقل کند، کنجکاوی مخاطب علاقه‌مند به حوزه ارز دیجیتال را برانگیزد و او را به خواندن ادامه مطلب ترغیب کند. از ترجمه تحت‌اللفظی پرهیز کن و به جای آن، تیتری خلق کن که دیدگاهی نو ارائه دهد یا اهمیت کلیدی موضوع را برجسته سازد و ترجیحا از قیمت ارز در ان استفاده شود. توضیحات بی مورد و توی پرانتز نده مثلا نگو (تحلیل قیمت جدید) یا نگو (قیمت لحظه ای) .\n"
        f"**فقط و فقط تیتر فارسی ساخته شده را به صورت یک خط، بدون هیچ‌گونه توضیح اضافی، علامت نقل قول یا پیشوند بازگردان.**\n"
        f" اصطلاحات 'bear'، 'bearish' یا مشابه را به 'فروشندگان' یا 'نزولی' (بسته به زمینه) و اصطلاحات 'bull'، 'bullish' یا مشابه را به 'خریداران' یا 'صعودی' (بسته به زمینه) ترجمه کن. از کلمات 'خرس' یا 'گاو' به هیچ عنوان استفاده نکن.\n"
        f"عنوان اصلی انگلیسی: \"{text_title}\"\n"
        f"تیتر فارسی جذاب و خلاقانه:"
    )
    payload = {"contents": [{"parts": [{"text": prompt}]}],"generationConfig": {"temperature": 0.4, "topP": 0.9, "topK": 50}}
    max_retries, retry_delay = 2, 10
    for attempt in range(max_retries + 1):
        try:
            response = requests.post(f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            result = response.json()
            if result and "candidates" in result and result["candidates"] and "text" in result["candidates"][0].get("content", {}).get("parts", [{}])[0]:
                print("<<< ترجمه عنوان با Gemini موفق بود.")
                sys.stdout.flush(); return result["candidates"][0]["content"]["parts"][0]["text"].strip()
            print(f"!!! پاسخ نامعتبر از Gemini (عنوان): {str(result)[:500]}"); sys.stdout.flush()
            if attempt < max_retries: time.sleep(retry_delay); retry_delay = int(retry_delay * 1.5); continue
            raise ValueError("پاسخ نامعتبر از API Gemini برای ترجمه عنوان دریافت شد.")
        except Exception as e:
            print(f"!!! خطای پیش‌بینی نشده در ترجمه عنوان: {e}"); sys.stdout.flush()
            raise
    raise ValueError("ترجمه عنوان پس از تمام تلاش‌ها ناموفق بود.")

def translate_with_gemini(text_to_translate):
    print(f">>> ترجمه محتوای اصلی با Gemini ({GEMINI_MODEL_NAME}) (طول: {len(text_to_translate)} کاراکتر)...")
    sys.stdout.flush()
    if not text_to_translate or text_to_translate.isspace(): raise ValueError("متن محتوا برای ترجمه خالی است.")
    headers = {"Content-Type": "application/json"}
    prompt = (
        f"متن زیر یک خبر یا تحلیل در حوزه ارز دیجیتال است. من می‌خوام این متن رو به فارسی روان بازنویسی کنی به طوری که ارزش افزوده پیدا کنه و مفهوم کلی را کاملا واضح بیان کنه و طبق قوانین زیرعمل کن:\n"
        f"1. فقط متن بازنویسی شده را برگردان و هیچ توضیح اضافی (مثل 'متن بازنویسی شده' یا موارد مشابه) اضافه نکن.\n"
        f"2. **دستورالعمل بسیار مهم:** پاسخ شما باید با یک خلاصه دو خطی از کل محتوای ورودی شروع شود که حداکثر 230 کاراکتر باشد. این خلاصه را **باید** داخل یک تگ div با کلاس 'summary' قرار دهی. به این شکل: <div class=\"summary\" style=\"font-weight: bold;\">متن خلاصه اینجا قرار گیرد</div>. **این تگ div باید بلافاصله بسته شود و بقیه محتوا خارج از آن قرار گیرد.** قبل از این تگ هیچ عبارت یا کاراکتر اضافی مانند 'خلاصه:' یا بک‌تیک (`) قرار نده. بعد از این تگ div، بقیه متن را طبق قوانین زیر بازنویسی کن.\n"
        f"قوانین مهم:\n"
        f"3. در همه جا اصول سئو کامل رعایت بشه.\n"
        f"4. در انتهای متن یک نتیجه‌گیری کامل و تحلیلی ارائه کن که **نباید بیشتر از 6 خط باشد**. این نتیجه‌گیری را داخل یک تگ div با کلاس 'conclusion' قرار بده. فقط عنوان 'جمع‌بندی:' باید بولد باشد و بقیه متن باید در خط جدید و بدون بولد شروع شود. به این شکل: <div class=\"conclusion\"><strong>جمع‌بندی:</strong><br>متن نتیجه‌گیری شما در اینجا...</div>\n"        
        f"5. **اولویت بالا:** محتوای متنی داخل *تمام* تگ‌های HTML (مانند متن داخل تگ‌های <p>, <h1>, <h2>, <li>, <a>, <figcaption>) را به فارسی روان و دقیق بازنویسی کن. این شامل محتوای متنی داخل تگ‌های تو در تو نیز می‌شود.\n"
        f"5.1. **جایگزینی محتوای توییت:** برای تگ‌های <blockquote> با کلاس 'twitter-tweet'، **متن انگلیسی داخل تگ <p> را با بازنویسی روان فارسی آن جایگزین کن.** ساختار کلی <blockquote>، لینک‌های داخل آن (تگ <a>) و نام‌های کاربری را دست‌نخورده باقی بگذار، اما متن اصلی انگلیسی را *کاملاً حذف* کن. هرگز این بلاک را تکرار نکن.\n"
        f"6. اصطلاحات 'bear'، 'bearish' یا مشابه را به 'فروشندگان' یا 'نزولی' و 'bull'، 'bullish' یا مشابه را به 'خریداران' یا 'صعودی' ترجمه کن.\n"
        f"7. تاریخ‌های میلادی را به فرمت شمسی تبدیل کن (مثال: May 1, 2025 به ۱۱ اردیبهشت ۱۴۰۴).\n"
        f"8. ساختار HTML موجود (مثل تگ‌های <p>، <div>، <b>) رو دقیقاً حفظ کن و تغییر نده.\n"
        f"8.1. **حفظ کامل کدهای TradingView:** هر تگ <figure> یا <blockquote> که حاوی لینکی به 'tradingview.com' است را به طور کامل و **بدون هیچ‌گونه تغییری** (نه در ساختار و نه در محتوا) در خروجی حفظ کن. این بلوک‌ها نباید ترجمه یا دستکاری شوند.\n"
        f"9. در انتهای متن یک پاراگراف برای تحریک کاربران به نظرسنجی اضافه کن که بیشتر از یک خط نباشد.\n"
        f"10. هیچ تگ HTML جدیدی اضافه نکن، مگر اینکه در متن اصلی وجود داشته باشد.\n"
        f"11. Placeholder های تصویر (مثل ) را دقیقاً همان‌طور که هستند، بدون هیچ تغییری حفظ کن.\n"
        f"12. لینک‌ها (مقدار href در تگ <a>) و نام‌های کاربری (مثل @Steph_iscrypto) را همان‌طور که هستند نگه دار.\n"
        f"12.1. **قانون اکید:** تحت هیچ شرایطی متن اصلی انگلیسی در کنار ترجمه فارسی در خروجی نهایی وجود نداشته باشد.\n"
        f"13. **قانون فرمت‌بندی:** برای بولد کردن متن، همیشه از تگ‌های <strong> یا <b> استفاده کن و هرگز از **...** استفاده نکن.\n"
        f"--- متن انگلیسی برای بازنویسی: ---\n{text_to_translate}"
    )
    payload = {"contents": [{"parts": [{"text": prompt}]}],"generationConfig": {"temperature": 0.4, "topP": 0.9, "topK": 50}}
    max_retries, retry_delay = 2, 20
    for attempt in range(max_retries + 1):
        try:
            response = requests.post(f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", headers=headers, json=payload, timeout=GEMINI_TIMEOUT)
            response.raise_for_status()
            result = response.json()
            if result and "candidates" in result and result["candidates"] and "text" in result["candidates"][0].get("content", {}).get("parts", [{}])[0]:
                translated_text = result["candidates"][0]["content"]["parts"][0]["text"]
                print("<<< ترجمه محتوای اصلی با Gemini موفق بود."); sys.stdout.flush()
                return re.sub(r'^```html\s*|\s*```$', '', translated_text, flags=re.IGNORECASE).strip()
        except Exception as e:
            print(f"!!! خطا در ترجمه محتوا (تلاش {attempt + 1}): {e}")
            if attempt < max_retries: time.sleep(retry_delay); retry_delay = int(retry_delay * 1.5)
            else: raise
    raise ValueError("ترجمه محتوای اصلی با Gemini پس از تمام تلاش‌ها ناموفق بود.")

def translate_caption_with_gemini(text_caption):
    if not text_caption or text_caption.isspace(): return ""
    print(f">>> ترجمه کپشن با Gemini ({GEMINI_MODEL_NAME}): '{text_caption[:30]}...'")
    headers = {"Content-Type": "application/json"}
    prompt = (f"متن HTML زیر (یک کپشن تصویر) را به فارسی روان و دقیق ترجمه کن. ساختار HTML (مثل <a>, <b>) را حفظ کن. اصطلاحات 'bearish' به 'نزولی' و 'bullish' به 'صعودی' ترجمه شوند. از کلمات 'خرس' یا 'گاو' استفاده نکن. فقط و فقط متن ترجمه شده را بازگردان و هیچ توضیح اضافی مانند 'کپشن ترجمه شده:' اضافه نکن.\nکپشن اصلی: \"{text_caption}\"\nکپشن ترجمه شده به فارسی:")
    payload = {"contents": [{"parts": [{"text": prompt}]}],"generationConfig": {"temperature": 0.3}}
    try:
        response = requests.post(f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status(); result = response.json()
        if result and "candidates" in result and result["candidates"] and "text" in result["candidates"][0].get("content", {}).get("parts", [{}])[0]:
            return re.sub(r'^```html\s*|\s*```$', '', result["candidates"][0]["content"]["parts"][0]["text"], flags=re.IGNORECASE).strip()
    except Exception as e:
        print(f"!!! خطا در ترجمه کپشن: {e}")
    return ""

def remove_newsbtc_links(text):
    if not text: return ""
    return re.sub(r'<a\s+[^>]*href=["\']https?://(www\.)?newsbtc\.com[^"\']*["\'][^>]*>(.*?)</a>', r'\2', text, flags=re.IGNORECASE)

def replace_all_external_images_with_obfuscated_proxy(content_html, main_domain, proxy_subdomain_url):
    if not content_html: return ""
    print(">>> بازنویسی آدرس تمام عکس‌های خارجی به پراکسی شخصی کدگذاری‌شده...")
    sys.stdout.flush()
    soup = BeautifulSoup(content_html, "html.parser")
    images = soup.find_all("img")
    modified_flag = False
    parsed_main_domain = urlparse(main_domain).netloc.replace("www.", "")
    proxy_domain = urlparse(proxy_subdomain_url).netloc.replace("www.", "")
    for img_tag in images:
        img_src = img_tag.get("src", "")
        if not img_src or not img_src.startswith(('http://', 'https://')): continue
        img_domain = urlparse(img_src).netloc.replace("www.", "")
        if img_domain and img_domain != parsed_main_domain and img_domain != proxy_domain:
            print(f"--- عکس خارجی یافت شد ({img_src[:70]}...)، در حال کدگذاری و بازنویسی...")
            encoded_url = base64.urlsafe_b64encode(img_src.encode('utf-8')).decode('utf-8')
            proxied_url = f"{proxy_subdomain_url}?data={encoded_url}"
            img_tag['src'] = proxied_url
            modified_flag = True
    print("<<< بازنویسی آدرس‌ها تمام شد.")
    sys.stdout.flush()
    return str(soup) if modified_flag else content_html

def crawl_captions(post_url):
    print(f">>> شروع کرال و ترجمه کپشن‌ها از: {post_url}")
    captions_data_list = []
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.0.0 Safari/537.36'}
        response = requests.get(post_url, timeout=REQUEST_TIMEOUT, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        figures = soup.find_all("figure")
        for figure_element in figures:
            img_element = figure_element.find("img")
            caption_element = figure_element.find("figcaption")
            if img_element and caption_element:
                img_original_src = img_element.get("src") or img_element.get("data-src")
                if img_original_src:
                    parsed_img_url = urlparse(unquote(img_original_src))
                    normalized_img_src = parsed_img_url._replace(query='').geturl()
                    original_caption_html = str(caption_element)
                    translated_caption_html = translate_caption_with_gemini(original_caption_html)
                    if translated_caption_html:
                        captions_data_list.append({"image_url": normalized_img_src, "caption": translated_caption_html})
        unique_captions = {item['image_url']: item for item in captions_data_list}.values()
        print(f"<<< کرال و ترجمه کپشن‌ها تمام شد. {len(unique_captions)} کپشن منحصر به فرد یافت شد.")
        return list(unique_captions)
    except Exception as e_crawl:
        print(f"!!! خطا در کرال یا ترجمه کپشن‌ها: {e_crawl}")
        return []

def add_captions_to_images(content_html, crawled_captions_list):
    if not crawled_captions_list or not content_html: return content_html
    print(">>> شروع افزودن کپشن‌های ترجمه شده به تصاویر محتوا...")
    soup = BeautifulSoup(content_html, "html.parser")
    images_in_content = soup.find_all("img")
    captions_map = {item['image_url']: item['caption'] for item in crawled_captions_list}
    captions_added_count = 0
    for img_tag in images_in_content:
        current_img_src = img_tag.get("src", "")
        if not current_img_src: continue
        parsed_url = urlparse(unquote(current_img_src))
        normalized_src = parsed_url._replace(query='').geturl()
        if normalized_src in captions_map:
            if not img_tag.find_parent('figure'):
                new_figure = soup.new_tag("figure", style="margin:1em auto; text-align:center; max-width:100%;")
                img_tag.wrap(new_figure)
                caption_html = captions_map[normalized_src]
                new_figcaption = BeautifulSoup(f'<figcaption style="text-align:center; font-size:0.9em; margin-top:0.5em; color:#555; line-height:1.4;">{caption_html}</figcaption>', 'html.parser')
                new_figure.append(new_figcaption)
                captions_added_count += 1
                del captions_map[normalized_src]
    if captions_map:
        print(f"--- افزودن {len(captions_map)} کپشن باقی‌مانده به انتهای محتوا...")
        remaining_captions_html = "".join(captions_map.values())
        soup.append(BeautifulSoup(f'<div style="text-align: center; margin-top: 20px; border-top: 1px solid #eee; padding-top:15px;">{remaining_captions_html}</div>', 'html.parser'))
    print(f"<<< افزودن کپشن‌ها تمام شد. {captions_added_count} به عکس‌ها اضافه شد.")
    return str(soup)

def remove_boilerplate_sections(html_content):
    if not html_content: return ""
    soup = BeautifulSoup(html_content, 'html.parser')
    boilerplate_keywords = ['related reading', 'read also', 'see also', 'disclaimer:']
    for tag in soup.find_all(['p', 'div', 'h2', 'h3']):
        tag_text_lower = tag.get_text(strip=True).lower()
        if any(tag_text_lower.startswith(keyword) for keyword in boilerplate_keywords):
            tag.decompose()
    return str(soup)

def post_to_wordpress(title_for_wp, content_for_wp, original_english_title, thumbnail_url_for_plugin, source_url_for_post, status="publish"):
    print(f">>> شروع ارسال پست '{title_for_wp[:50]}...' به وردپرس...")
    credentials = f"{WORDPRESS_USER}:{WORDPRESS_PASS}"
    token = base64.b64encode(credentials.encode())
    headers = {'Authorization': f'Basic {token.decode("utf-8")}', 'Content-Type': 'application/json'}
    post_data = {
        "title": title_for_wp,
        "content": content_for_wp,
        "slug": generate_english_slug(original_english_title),
        "category_id": 69,
        "thumbnail_url": thumbnail_url_for_plugin or "",
        "source_url": source_url_for_post
    }
    try:
        response = requests.post(WORDPRESS_CUSTOM_POST_API_ENDPOINT, headers=headers, json=post_data, timeout=REQUEST_TIMEOUT * 3)
        response.raise_for_status()
        response_data = response.json()
        if response.status_code == 201 and response_data.get("post_id"):
            print(f"<<< پست با موفقیت ارسال شد! URL: {response_data.get('url', 'نامشخص')}")
            return response_data
        else:
            raise ValueError(f"پاسخ غیرمنتظره از وردپرس: {response_data}")
    except Exception as e:
        print(f"!!! خطا در ارسال به وردپرس: {e}")
        raise
    return None

def resolve_tradingview_links(html_content):
    if not html_content: return ""
    print(">>> شروع پردازش لینک‌های TradingView...")
    soup = BeautifulSoup(html_content, "html.parser")
    links = soup.find_all("a", href=re.compile(r"https?://(www\.)?tradingview\.com/x/"))
    for link_tag in links:
        try:
            response = requests.get(link_tag['href'], timeout=REQUEST_TIMEOUT, headers={'User-Agent': 'Mozilla/5.0'})
            response.raise_for_status()
            page_soup = BeautifulSoup(response.content, "html.parser")
            meta_tag = page_soup.find("meta", property="og:image")
            if meta_tag and meta_tag.get("content"):
                direct_image_url = meta_tag["content"]
                img_tag = link_tag.find("img")
                if img_tag: img_tag['src'] = direct_image_url
                link_tag['href'] = direct_image_url
                print(f"--- لینک TradingView با موفقیت به {direct_image_url} تصحیح شد.")
        except Exception as e:
            print(f"!!! خطا در پردازش لینک TradingView {link_tag.get('href', '')}: {e}")
    return str(soup)

def load_processed_links_from_wordpress():
    print(f"--- در حال دریافت لیست لینک‌های پردازش شده از وردپرس...")
    credentials = f"{WORDPRESS_USER}:{WORDPRESS_PASS}"
    token = base64.b64encode(credentials.encode())
    headers = {'Authorization': f'Basic {token.decode("utf-8")}'}
    try:
        response = requests.get(WORDPRESS_PROCESSED_LINKS_GET_API_ENDPOINT, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return set(response.json())
    except Exception as e:
        raise ValueError(f"امکان دریافت لیست لینک‌های پردازش شده از وردپرس وجود ندارد: {e}")

def save_processed_link_to_wordpress(link_url):
    print(">>> ذخیره کردن لینک منبع...")
    credentials = f"{WORDPRESS_USER}:{WORDPRESS_PASS}"
    token = base64.b64encode(credentials.encode())
    headers = {'Authorization': f'Basic {token.decode("utf-8")}', 'Content-Type': 'application/json'}
    try:
        response = requests.post(WORDPRESS_PROCESSED_LINKS_ADD_API_ENDPOINT, headers=headers, json={"link": link_url}, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        print("<<< لینک با موفقیت در وردپرس ثبت شد.")
    except Exception as e:
        raise ValueError(f"امکان ذخیره لینک '{link_url}' در وردپرس وجود ندارد: {e}")

# --- شروع اسکریپت اصلی ---
if __name__ == "__main__":
    logger = Logger(log_file=MASTER_LOG_FILE)
    sys.stdout = logger
    main_script_start_time = time.time()
    print(f"شروع پردازش فید RSS و ارسال به وردپرس")
    try:
        print("\n>>> مرحله ۰: بررسی پست‌های تکراری...");
        processed_links = load_processed_links_from_wordpress() 
        print(f"--- {len(processed_links)} لینک پردازش شده از قبل یافت شد.")

        print("\n>>> مرحله ۱: دریافت و تجزیه فید RSS...");
        feed_data_parsed = feedparser.parse(RSS_FEED_URL)
        if feed_data_parsed.bozo: print(f"--- هشدار در تجزیه فید: {feed_data_parsed.bozo_exception}")
        if not feed_data_parsed.entries: raise ValueError("هیچ پستی در فید RSS یافت نشد.")
        latest_post_from_feed = feed_data_parsed.entries[0]
        original_post_title_english = latest_post_from_feed.title
        post_original_link = getattr(latest_post_from_feed, 'link', None)
        if not post_original_link: raise ValueError("پست یافت شده فاقد لینک منبع است.")
        if post_original_link in processed_links:
            print(f"\n*** پست تکراری یافت شد: {post_original_link} ***\n")
            sys.exit(0)
        print(f"--- جدیدترین پست: '{original_post_title_english}'")
        print("<<< مرحله ۱ کامل شد.");

        thumbnail_url = None
        if hasattr(latest_post_from_feed, 'media_content') and latest_post_from_feed.media_content:
            thumbnail_url = latest_post_from_feed.media_content[0].get('url')
        
        print("\n>>> مرحله ۲: کرال و ترجمه کپشن‌ها...");
        crawled_captions = crawl_captions(post_original_link)
        print(f"<<< مرحله ۲ کامل شد (تعداد کپشن نهایی: {len(crawled_captions)}).");

        print("\n>>> مرحله ۳: ترجمه عنوان پست...");
        final_translated_title = translate_title_with_gemini(original_post_title_english)
        print(f"--- عنوان ترجمه‌شده نهایی: {final_translated_title}"); print("<<< مرحله ۳ کامل شد.");

        print("\n>>> مرحله ۴: پردازش کامل محتوای اصلی...");
        raw_content_html = ""
        if 'content' in latest_post_from_feed and latest_post_from_feed.content:
            raw_content_html = latest_post_from_feed.content[0]['value']
        elif 'summary' in latest_post_from_feed: raw_content_html = latest_post_from_feed.summary
        if not raw_content_html: raise ValueError("محتوای اصلی یافت نشد.")
        
        content_no_boilerplate = remove_boilerplate_sections(raw_content_html)
        content_no_links = remove_newsbtc_links(content_no_boilerplate)
        content_with_tv_resolved = resolve_tradingview_links(content_no_links)
        content_with_captions = add_captions_to_images(content_with_tv_resolved, crawled_captions)
        content_with_proxy = replace_all_external_images_with_obfuscated_proxy(content_with_captions, WORDPRESS_MAIN_URL, IMAGE_PROXY_URL)
        content_with_placeholders, placeholder_map = replace_images_with_placeholders(content_with_proxy)
        translated_content = translate_with_gemini(content_with_placeholders)
        if not translated_content: raise ValueError("ترجمه محتوای اصلی ناموفق بود.")
        restored_content = restore_images_from_placeholders(translated_content, placeholder_map)
        
        final_soup = BeautifulSoup(restored_content, "html.parser")
        for img in final_soup.find_all("img"):
            img['style'] = "max-width:100%; height:auto; display:block; margin:10px auto; border-radius:4px;"
            if not img.get('alt'): img['alt'] = final_translated_title
        for p in final_soup.find_all('p'):
            if not p.get_text(strip=True) and not p.find(['img', 'br', 'hr', 'figure', 'iframe', 'script', 'blockquote']):
                p.decompose()
        final_content_html = str(final_soup)
        print("<<< مرحله ۴ (پردازش محتوا) کامل شد.");

        print("\n>>> مرحله ۵: آماده‌سازی ساختار نهایی HTML پست...");
        disclaimer = '<strong>سلب مسئولیت:</strong> احتمال اشتباه در تحلیل ها وجود دارد و هیچ تحلیلی قطعی نیست و همه بر پایه احتمالات میباشند. لطفا در خرید و فروش خود دقت کنید.'
        disclaimer_html = f'<div style="color: #c00; font-size: 0.9em; margin-top: 25px; text-align: justify; border: 1px solid #fdd; background-color: #fff9f9; padding: 15px; border-radius: 5px;">{disclaimer}</div>'
        source_html = f'<hr style="margin-top: 25px; margin-bottom: 15px; border: 0; border-top: 1px solid #eee;"><p style="text-align:right; margin-top:15px; font-size: 0.85em; color: #555;"><em><a href="{post_original_link}" target="_blank" rel="noopener noreferrer nofollow" style="color: #1a0dab; text-decoration: none;">منبع: NewsBTC</a></em></p>'
        final_html_payload = f'<div style="line-height: 1.75; font-size: 17px; text-align: justify;">{final_content_html}</div>{disclaimer_html}{source_html}'
        print("<<< مرحله ۵ (ساختار نهایی) کامل شد.");

        print("\n>>> مرحله ۶: ارسال پست به وردپرس...");
        post_response = post_to_wordpress(
            title_for_wp=final_translated_title,
            content_for_wp=final_html_payload,
            original_english_title=original_post_title_english,
            thumbnail_url_for_plugin=thumbnail_url,
            source_url_for_post=post_original_link
        )
        print("<<< مرحله ۶ (ارسال به وردپرس) کامل شد.");

        if post_response and post_response.get("post_id"):
            save_processed_link_to_wordpress(post_original_link)
            print("<<< مرحله ۷ کامل شد.")

    except Exception as global_exception:
        print(f"\n!!! خطای کلی: {global_exception}")
        traceback.print_exc()
        sys.exit(1)
    finally:
        total_script_execution_time = time.time() - main_script_start_time
        print(f"\nاسکریپت به پایان رسید (زمان کل: {total_script_execution_time:.2f} ثانیه).")
        if 'logger' in locals() and isinstance(logger, Logger):
            logger.close()
            sys.stdout = logger.terminal
