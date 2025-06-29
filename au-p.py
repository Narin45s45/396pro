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
GEMINI_MODEL_NAME = "gemini-2.5-flash-preview-05-20"
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL_NAME}:generateContent"
GEMINI_API_KEY = os.environ.get("GEMAPI")

WORDPRESS_URL = os.environ.get("WORDPRESS_URL")
WORDPRESS_USER = os.environ.get("WORDPRESS_USER")
WORDPRESS_PASS = os.environ.get("WORDPRESS_PASS")

REQUEST_TIMEOUT = 60
GEMINI_TIMEOUT = 150
PROCESSED_LINKS_FILE = "processed_links.txt"
MASTER_LOG_FILE = "master_log.txt"

if not all([GEMINI_API_KEY, WORDPRESS_URL, WORDPRESS_USER, WORDPRESS_PASS]):
    raise ValueError("یکی از متغیرهای محیطی ضروری (GEMAPI, WORDPRESS_URL, USER, PASS) تنظیم نشده است.")

WORDPRESS_API_ENDPOINT = WORDPRESS_URL.rstrip('/') + "/wp-json/my-poster/v1/create"

# --- توابع کمکی ---
def generate_english_slug(title_str):
    if not title_str: return f"post-{uuid.uuid4().hex[:12]}"
    slug = str(title_str).lower()
    slug = re.sub(r'\s+', '-', slug); slug = re.sub(r'[^\w\-]', '', slug)
    slug = re.sub(r'-+', '-', slug); slug = slug.strip('-')
    return slug if len(slug) > 4 else f"article-{uuid.uuid4().hex[:8]}"

def replace_images_with_placeholders(html_content):
    print("--- شروع جایگزینی عکس‌ها با Placeholder...")
    sys.stdout.flush()
    if not html_content: return "", {}

    soup = BeautifulSoup(html_content, "html.parser")
    images = soup.find_all("img")
    placeholder_map = {}
    count = 0
    for i, img in enumerate(images):
        img_src_for_log = img.get('src', 'NO_SRC')
        
        # یک شناسه منحصر به فرد برای هر عکس تولید می‌کنیم
        placeholder_uuid = str(uuid.uuid4())
        
        # فرمت جدید Placeholder: یک تگ div با شناسه و متن منحصر به فرد
        placeholder_div_str = f'<div class="image-placeholder-container" id="placeholder-{placeholder_uuid}">Image-Placeholder-{placeholder_uuid}</div>'
        
        # در نقشه، فقط شناسه را به عنوان کلید ذخیره می‌کنیم
        placeholder_map[placeholder_uuid] = str(img) 
        
        # تگ عکس را با تگ div جدید جایگزین می‌کنیم
        img.replace_with(BeautifulSoup(placeholder_div_str, 'html.parser'))
        count += 1
        
    print(f"--- {count} عکس با Placeholder جایگزین شد.")
    sys.stdout.flush()
    return str(soup), placeholder_map
    
    
def restore_images_from_placeholders(html_content, placeholder_map):
    print("--- شروع بازگرداندن عکس‌ها از Placeholder...")
    sys.stdout.flush()
    if not placeholder_map:
        return html_content

    soup = BeautifulSoup(html_content, 'html.parser')
    count = 0
    not_found_count = 0

    # به جای جایگزینی رشته، با شناسه منحصر به فرد تگ را پیدا می‌کنیم
    for placeholder_uuid, img_tag_str in placeholder_map.items():
        # تگ div که دارای شناسه منحصر به فرد ماست را پیدا کن
        target_div = soup.find('div', id=f"placeholder-{placeholder_uuid}")
        
        if target_div:
            # اگر پیدا شد، آن را با تگ عکس اصلی جایگزین کن
            target_div.replace_with(BeautifulSoup(img_tag_str, 'html.parser'))
            count += 1
        else:
            # اگر پیدا نشد، خطا را ثبت کن
            not_found_count += 1
            original_img_src_for_log = "نامشخص"
            try:
                temp_soup = BeautifulSoup(img_tag_str, "html.parser")
                img_in_tag = temp_soup.find("img")
                if img_in_tag: original_img_src_for_log = img_in_tag.get('src', 'NO_SRC')[:70]
            except: pass
            print(f"--- هشدار (Restore): Placeholder با شناسه 'placeholder-{placeholder_uuid}' یافت نشد! (تصویر اصلی src: '{original_img_src_for_log}...')")

    print(f"--- {count} عکس از Placeholder بازگردانده شد.")
    if not_found_count > 0:
        print(f"--- هشدار جدی: {not_found_count} Placeholder در متن ترجمه شده برای بازگردانی یافت نشدند!")
        
    sys.stdout.flush()
    return str(soup)
    
    
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
        print(f"--- تلاش {attempt + 1}/{max_retries + 1} برای ترجمه عنوان...")
        sys.stdout.flush()
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
        except requests.exceptions.Timeout: print(f"!!! Timeout در ترجمه عنوان."); sys.stdout.flush()
        except requests.exceptions.RequestException as e:
            print(f"!!! خطا در درخواست ترجمه عنوان: {e}"); sys.stdout.flush()
            if hasattr(e, 'response') and e.response is not None:
                print(f"--- جزئیات خطای درخواست (عنوان): {e.response.status_code} - {e.response.text[:300]}"); sys.stdout.flush()
        except Exception as e: print(f"!!! خطای پیش‌بینی نشده در ترجمه عنوان: {e}"); sys.stdout.flush(); raise
        if attempt < max_retries: time.sleep(retry_delay); retry_delay = int(retry_delay * 1.5); continue
    raise ValueError("ترجمه عنوان پس از تمام تلاش‌ها ناموفق بود.")

def translate_with_gemini(text_to_translate):
    print(f">>> ترجمه محتوای اصلی با Gemini ({GEMINI_MODEL_NAME}) (طول: {len(text_to_translate)} کاراکتر)...")
    sys.stdout.flush()
    if not text_to_translate or text_to_translate.isspace(): raise ValueError("متن محتوا برای ترجمه خالی است.")
    headers = {"Content-Type": "application/json"}
    prompt = (
        f"متن زیر یک خبر یا تحلیل در حوزه ارز دیجیتال است. من می‌خوام این متن رو به فارسی روان بازنویسی کنی به طوری که ارزش افزوده پیدا کنه و مفهوم کلی را کاملا واضح بیان کنه و طبق قوانین زیرعمل کن:\n"
        f"1. فقط متن بازنویسی شده را برگردان و هیچ توضیح اضافی (مثل 'متن بازنویسی شده' یا موارد مشابه) اضافه نکن.\n"
        f"2. **دستورالعمل بسیار مهم:** پاسخ شما باید با یک خلاصه دو خطی از کل محتوای ورودی شروع شود که حداکثر 230 کاراکتر باشد. این خلاصه را **باید** داخل یک تگ پاراگراف با کلاس 'summary' قرار دهی. به این شکل: <div class=\"summary\" style=\"font-weight: bold;\">متن خلاصه اینجا قرار گیرد</p>. قبل از این تگ هیچ عبارت یا کاراکتر اضافی مانند 'خلاصه:' یا بک‌تیک (`) قرار نده. بعد از این خلاصه، بقیه متن را طبق قوانین زیر بازنویسی کن.\n"
        f"قوانین مهم:\n"
        f"3. در همه جا اصول سئو کامل رعایت بشه.\n"
        f"4. در انتهای متن یک نتیجه‌گیری کامل و تحلیلی ارائه کن. این نتیجه‌گیری را داخل یک تگ div با کلاس 'conclusion' قرار بده. فقط عنوان 'جمع‌بندی:' باید بولد باشد و بقیه متن باید در خط جدید و بدون بولد شروع شود. به این شکل: <div class=\"conclusion\"><strong>جمع‌بندی:</strong><br>متن نتیجه‌گیری شما در اینجا...</div>\n"
        f"5. **اولویت بالا:** محتوای متنی داخل *تمام* تگ‌های HTML (مانند متن داخل تگ‌های <p>, <h1>, <h2>, <li>, <a>, <figcaption> و به خصوص داخل تگ‌های <blockquote> حتی اگر دارای کلاس 'twitter-tweet' یا مشابه باشند) را به فارسی روان و دقیق بازنویسی کن. این بازنویسی باید حتی اگر تگ‌ها ویژگی‌هایی مانند lang='en' یا dir='ltr' داشته باشند، انجام شود. این شامل محتوای متنی داخل تگ‌های تو در تو (مثل تگ‌های <p> یا <a> داخل <blockquote>) نیز می‌شود. هدف، ترجمه کامل متن قابل مشاهده توسط کاربر است.\n"
        f"5.1. برای تگ‌های <blockquote> با کلاس 'twitter-tweet' یا موارد مشابه که نقل قول از شبکه‌های اجتماعی هستند، تمام متن‌های داخل تگ‌های <p> در آن‌ها را به دقت به فارسی روان، خلاقانه و جذاب بازنویسی کن (نه ترجمه تحت اللفظی یا ساده). کیفیت بازنویسی باید با سایر بخش‌های متن همخوانی داشته باشد. متن اصلی انگلیسی باید *کاملاً حذف* شده و *فقط و فقط بازنویسی فارسی* آن در خروجی باشد. لینک‌های موجود در توییت (مثل لینک به خود توییت یا لینک به تصاویر/ویدیوها مانند pic.twitter.com) و نام کاربری‌ها (مثل @ray4tesla) را حفظ کن.\n"
        f"6. اصطلاحات 'bear'، 'bearish' یا مشابه را به 'فروشندگان' یا 'نزولی' (بسته به زمینه) و اصطلاحات 'bull'، 'bullish' یا مشابه را به 'خریداران' یا 'صعودی' (بسته به زمینه) ترجمه کن. از کلمات 'خرس' یا 'گاو' به هیچ عنوان استفاده نکن.\n"
        f"7. تاریخ‌های میلادی (مانند May 1, 2025) را به فرمت شمسی (مانند ۱۱ اردیبهشت ۱۴۰۴) تبدیل کن. تاریخ‌ها باید دقیق و مطابق تقویم شمسی باشند و به صورت متنی (نه عددی مثل 1404/02/11) نوشته شوند. اگر تاریخ در متن مبهم است (مثلاً فقط ماه و سال)، فقط ماه و سال را به شمسی تبدیل کن.\n"
        f"8. ساختار HTML موجود (مثل تگ‌های <p>، <div>، <b>، <blockquote>، <a>) رو دقیقاً حفظ کن و تغییر نده. این شامل خود تگ‌ها، ویژگی‌ها (attributes) و ترتیبشون می‌شه.\n"
        f"9. در انتها و در پاراگراف جداگانه کاربران رو تحریک به نظرسنجی کن و در تگ  p  باشد.\n"
        f"10. هیچ تگ HTML جدیدی (مثل <p>، <b>، <div>) به متن اضافه نکن، مگر اینکه توی متن اصلی وجود داشته باشه. اگه متن اصلی تگ HTML نداره (مثلاً یه متن ساده است)، خروجی هم باید بدون تگ HTML باشه.\n"
        f"11. Placeholder های تصویر (مثل ##IMG_PLACEHOLDER_UUID##) رو دقیقاً همون‌طور که هستن نگه دار و تغییر نده. و هیچ کاراکتری به ابتدا یا انتهای آنها اضافه یا از آنها کم نکن و فاصله‌گذاری اطراف آنها را تا حد امکان حفظ کن.\n"
        f"12. لینک‌ها (مثل آدرس‌های داخل href در تگ <a> به جز موارد ذکر شده در قانون 5.1 برای ترجمه محتوای لینک اگر متن لینک باشد) و متن‌های خاص مثل نام کاربری‌ها (مثل @Steph_iscrypto)  همون‌طور که هستن نگه دار.\n"
        f"12.1. تحت هیچ شرایطی متن اصلی انگلیسی در کنار ترجمه/بازنویسی فارسی در خروجی نهایی وجود نداشته باشد، مگر اینکه در این پرامپت به صراحت خواسته شده باشد (که در اینجا چنین درخواستی برای نمایش همزمان وجود ندارد).\n"
        f"دستورالعمل‌های کلیدی برای بازنویسی پیشرفته، ایجاد ارزش افزوده و تحلیل عمیق (علاوه بر قوانین بالا که باید همچنان رعایت شوند):\n"
        f"13. تحلیل عمیق‌تر و فراتر از بازنویسی ساده.\n"
        f"14. ایجاد جذابیت در متن و جایگزینی عناوین داخلی (عناوین و زیرعنوان‌ها بولد و برجسته).\n"
        f"15. ارائه دیدگاه‌های چندگانه و بررسی پیامدها.\n"
        f"16. افزودن نکات کلیدی، جمع‌بندی تحلیلی یا راهکارهای عملی (در صورت امکان).\n"
        f"17. طرح پرسش‌های تامل‌برانگیز و دعوت به تفکر.\n"
        f"18. ایجاد ارتباط با روندهای گسترده‌تر و ارائه تصویر بزرگتر.\n"
        f"19. **قانون بسیار مهم برای تصاویر:** تگ‌های div با کلاس 'image-placeholder-container' را دقیقاً همانطور که هستند، بدون هیچ تغییری در محتوا یا مکان، حفظ کن. این تگ‌ها جایگاه تصاویر هستند و نباید جابجا شوند.\n"
        f"20. **قانون فرمت‌بندی:** برای بولد کردن متن، همیشه و فقط از تگ‌های <strong> یا <b> در HTML استفاده کن. هرگز از سینتکس مارک‌داون مانند **...** برای بولد کردن استفاده نکن.\n"
        f"\nمتن انگلیسی برای بازنویسی:\n{text_to_translate}\n"
    )
    payload = {"contents": [{"parts": [{"text": prompt}]}],"generationConfig": {"temperature": 0.45, "topP": 0.9, "topK": 50}}
    max_retries, retry_delay = 2, 20
    for attempt in range(max_retries + 1):
        print(f"--- تلاش {attempt + 1}/{max_retries + 1} برای ترجمه محتوا...")
        sys.stdout.flush()
        try:
            response = requests.post(f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", headers=headers, json=payload, timeout=GEMINI_TIMEOUT)
            print(f"--- پاسخ اولیه از Gemini (محتوا) دریافت شد (کد: {response.status_code})"); sys.stdout.flush()
            if response.status_code == 429 and attempt < max_retries: print(f"!!! Rate Limit (محتوا). منتظر {retry_delay} ثانیه..."); sys.stdout.flush(); time.sleep(retry_delay); retry_delay = int(retry_delay * 1.5); continue
            response.raise_for_status()
            print("--- در حال پردازش پاسخ JSON از Gemini (محتوا)..."); sys.stdout.flush()
            result = response.json()
            if not result or "candidates" not in result or not result["candidates"]:
                feedback = result.get("promptFeedback", {}); block_reason = feedback.get("blockReason")
                if block_reason: print(f"!!! مسدود شد (محتوا): {block_reason}. Safety: {feedback.get('safetyRatings', [])}"); sys.stdout.flush(); raise ValueError(f"ترجمه محتوا توسط Gemini مسدود شد: {block_reason}")
                print(f"!!! پاسخ نامعتبر از Gemini (محتوا): {str(result)[:500]}"); sys.stdout.flush(); raise ValueError("پاسخ نامعتبر از API Gemini برای محتوا دریافت شد.")
            candidate = result["candidates"][0]
            if "content" not in candidate or "parts" not in candidate["content"] or not candidate["content"]["parts"]:
                finish_reason = candidate.get("finishReason", "نامشخص")
                safety_ratings_cand_str = str(candidate.get("safetyRatings", []))
                if finish_reason != "STOP":
                    print(f"!!! ترجمه محتوا کامل نشد: {finish_reason}. Safety Ratings: {safety_ratings_cand_str}"); sys.stdout.flush()
                    partial_text_node = candidate.get("content",{}).get("parts",[{}])[0]
                    if partial_text_node and "text" in partial_text_node:
                        partial_text = partial_text_node.get("text")
                        if partial_text: print(f"--- هشدار: ممکن است ترجمه محتوا ناقص باشد: {partial_text[:100]}..."); sys.stdout.flush(); return partial_text.strip()
                    raise ValueError(f"ترجمه محتوا ناقص از Gemini دریافت شد (دلیل: {finish_reason})")
                else: print(f"!!! ساختار نامعتبر در پاسخ Gemini (محتوا، STOP): {str(candidate)[:500]}"); sys.stdout.flush(); raise ValueError("ساختار نامعتبر در پاسخ Gemini (محتوا، STOP)")
            if "text" not in candidate["content"]["parts"][0]: print(f"!!! بدون 'text' در پاسخ Gemini (محتوا): {str(candidate)[:500]}"); sys.stdout.flush(); raise ValueError("بدون 'text' در پاسخ Gemini (محتوا)")
            translated_text = candidate["content"]["parts"][0]["text"]
            print("<<< ترجمه محتوای اصلی با Gemini موفق بود."); sys.stdout.flush()
            translated_text = re.sub(r'^```html\s*', '', translated_text, flags=re.IGNORECASE); translated_text = re.sub(r'\s*```$', '', translated_text)
            return translated_text.strip()
        except requests.exceptions.Timeout:
            print(f"!!! خطا: Timeout در ترجمه محتوا (تلاش {attempt + 1})."); sys.stdout.flush()
            if attempt >= max_retries: raise ValueError(f"Timeout در API Gemini برای محتوا پس از {max_retries + 1} تلاش.")
        except requests.exceptions.RequestException as e:
            print(f"!!! خطا در درخواست ترجمه محتوا به API Gemini (تلاش {attempt + 1}): {e}"); sys.stdout.flush()
            if hasattr(e, 'response') and e.response is not None:
                print(f"--- جزئیات خطای درخواست (محتوا): {e.response.status_code} - {e.response.text[:300]}"); sys.stdout.flush()
            if attempt >= max_retries: raise ValueError(f"خطا در درخواست API Gemini برای محتوا پس از {max_retries + 1} تلاش: {e}")
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            print(f"!!! خطا در پردازش پاسخ Gemini (محتوا) یا خطای داده داخلی: {e}"); sys.stdout.flush(); raise
        except Exception as e:
            print(f"!!! خطای پیش‌بینی نشده در یک تلاش ترجمه محتوا (تلاش {attempt + 1}): {type(e).__name__} - {e}"); sys.stdout.flush()
            if attempt >= max_retries: raise
        if attempt < max_retries:
            print(f"--- منتظر ماندن برای {retry_delay} ثانیه قبل از تلاش مجدد برای ترجمه محتوا..."); sys.stdout.flush()
            time.sleep(retry_delay); retry_delay = int(retry_delay * 1.5)
    raise ValueError("ترجمه محتوای اصلی با Gemini پس از تمام تلاش‌ها ناموفق بود.")

def translate_caption_with_gemini(text_caption):
    print(f">>> ترجمه کپشن با Gemini ({GEMINI_MODEL_NAME}): '{text_caption[:30]}...'")
    sys.stdout.flush()
    if not text_caption or text_caption.isspace(): return ""
    headers = {"Content-Type": "application/json"}
    prompt = (f"متن HTML زیر (یک کپشن تصویر) را به فارسی روان و دقیق ترجمه کن. ساختار HTML (مثل <a>, <b>) را حفظ کن. اصطلاحات 'bearish' به 'نزولی' و 'bullish' به 'صعودی' ترجمه شوند. از کلمات 'خرس' یا 'گاو' استفاده نکن. فقط و فقط متن ترجمه شده را بازگردان و هیچ توضیح اضافی مانند 'کپشن ترجمه شده:' اضافه نکن.\nکپشن اصلی: \"{text_caption}\"\nکپشن ترجمه شده به فارسی:")
    payload = {"contents": [{"parts": [{"text": prompt}]}],"generationConfig": {"temperature": 0.3}}
    max_retries, retry_delay = 2, 10
    for attempt in range(max_retries + 1):
        try:
            response = requests.post(f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
            response.raise_for_status(); result = response.json()
            if result and "candidates" in result and result["candidates"] and "text" in result["candidates"][0].get("content", {}).get("parts", [{}])[0]:
                return re.sub(r'\s*```$', '', re.sub(r'^```html\s*', '', result["candidates"][0]["content"]["parts"][0]["text"], flags=re.IGNORECASE)).strip()
            print(f"!!! پاسخ نامعتبر از Gemini (کپشن): {str(result)[:200]}"); sys.stdout.flush()
            if attempt < max_retries: time.sleep(retry_delay); retry_delay = int(retry_delay * 1.5); continue
            raise ValueError("پاسخ نامعتبر از API Gemini برای کپشن دریافت شد.")
        except requests.exceptions.Timeout:
            print(f"!!! Timeout در ترجمه کپشن (تلاش {attempt + 1})."); sys.stdout.flush()
            if attempt >= max_retries: raise ValueError(f"Timeout در ترجمه کپشن پس از {max_retries + 1} تلاش.")
        except requests.exceptions.RequestException as e:
            print(f"!!! خطا در درخواست ترجمه کپشن (تلاش {attempt + 1}): {e}"); sys.stdout.flush()
            if hasattr(e, 'response') and e.response is not None:
                print(f"--- جزئیات خطای درخواست (کپشن): {e.response.status_code} - {e.response.text[:300]}"); sys.stdout.flush()
            if attempt >= max_retries: raise ValueError(f"خطا در درخواست API Gemini برای کپشن پس از {max_retries + 1} تلاش: {e}")
        except Exception as e:
            print(f"!!! خطای پیش‌بینی نشده در ترجمه کپشن ({type(e).__name__}, تلاش {attempt + 1}): {e}"); sys.stdout.flush()
            if attempt >= max_retries: raise
        if attempt < max_retries:
            print(f"--- منتظر {retry_delay} ثانیه قبل از تلاش مجدد (کپشن)..."); sys.stdout.flush()
            time.sleep(retry_delay); retry_delay = int(retry_delay * 1.5)
    print(f"--- هشدار: ترجمه کپشن '{text_caption[:30]}...' ناموفق بود. خالی برگردانده شد."); sys.stdout.flush()
    return ""

def remove_newsbtc_links(text):
    if not text: return ""
    return re.sub(r'<a\s+[^>]*href=["\']https?://(www\.)?newsbtc\.com[^"\']*["\'][^>]*>(.*?)</a>', r'\2', text, flags=re.IGNORECASE)

def replace_filtered_images_in_content_with_base64(content_html):
    if not content_html: return ""
    print(">>> بررسی و تبدیل عکس‌های فیلترشده در *محتوای اصلی* به Base64...")
    sys.stdout.flush(); soup = BeautifulSoup(content_html, "html.parser"); images = soup.find_all("img")
    modified_flag = False; processed_count = 0; found_filtered_domains_count = 0
    filtered_domains_for_content = ["twimg.com", "i0.wp.com", "i1.wp.com", "i2.wp.com", "pbs.twimg.com"]
    for i, img_tag in enumerate(images):
        img_src = img_tag.get("src", "")
        if not img_src or not img_src.startswith(('http://', 'https://')):
            if not img_src.startswith('data:'): continue
        is_on_filtered_domain = any(domain_part in img_src for domain_part in filtered_domains_for_content)
        if is_on_filtered_domain:
            found_filtered_domains_count += 1
            print(f"--- عکس محتوا {i+1} از دامنه فیلتر شده ({img_src[:70]}...) در حال تبدیل به Base64...")
            sys.stdout.flush()
            try:
                headers = {'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'}
                response = requests.get(img_src, stream=True, timeout=REQUEST_TIMEOUT, headers=headers, verify=True)
                response.raise_for_status(); content_type_header = response.headers.get('content-type', '').split(';')[0].strip()
                if not content_type_header or not content_type_header.startswith('image/'):
                    file_extension = os.path.splitext(urlparse(img_src).path)[1].lower()
                    mime_map = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.gif': 'image/gif', '.webp': 'image/webp', '.avif': 'image/avif'}
                    content_type_header = mime_map.get(file_extension, 'image/jpeg')
                image_binary_content = response.content
                base64_encoded_string = base64.b64encode(image_binary_content).decode('utf-8')
                img_tag['src'] = f"data:{content_type_header};base64,{base64_encoded_string}"
                if not img_tag.get('alt'): img_tag['alt'] = "تصویر از محتوا (تبدیل شده)"
                modified_flag = True; processed_count += 1
            except Exception as e_img_conv: print(f"!!! خطا در دانلود یا تبدیل عکس محتوا {img_src[:70]}... : {e_img_conv}"); sys.stdout.flush()
    print(f"<<< تبدیل عکس‌های فیلترشده در محتوا تمام شد. {processed_count}/{found_filtered_domains_count} عکس با موفقیت تبدیل شد.")
    sys.stdout.flush(); return str(soup) if modified_flag else content_html

def crawl_captions(post_url):
    print(f">>> شروع کرال و ترجمه کپشن‌ها از: {post_url}")
    sys.stdout.flush(); captions_data_list = []
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36'}
        response = requests.get(post_url, timeout=REQUEST_TIMEOUT, headers=headers)
        response.raise_for_status(); soup = BeautifulSoup(response.content, "html.parser")
        figures = soup.find_all("figure"); print(f"--- تعداد <figure> یافت شده برای بررسی کپشن: {len(figures)}"); sys.stdout.flush()
        for fig_idx, figure_element in enumerate(figures):
            img_element = figure_element.find("img"); caption_element = figure_element.find("figcaption")
            if img_element and caption_element:
                img_original_src = img_element.get("src") or img_element.get("data-src")
                if img_original_src:
                    parsed_img_url = urlparse(unquote(img_original_src)); normalized_img_src = parsed_img_url._replace(query='').geturl()
                    original_caption_html = str(caption_element); translated_caption_html = translate_caption_with_gemini(original_caption_html)
                    if translated_caption_html and translated_caption_html.strip():
                        captions_data_list.append({"image_url": normalized_img_src, "caption": translated_caption_html, "original_alt": img_element.get("alt", "")})
        unique_captions = []; seen_caption_texts = set()
        for item in captions_data_list:
            caption_text_for_uniqueness = BeautifulSoup(item['caption'], 'html.parser').get_text(strip=True)
            if caption_text_for_uniqueness and caption_text_for_uniqueness not in seen_caption_texts:
                unique_captions.append(item); seen_caption_texts.add(caption_text_for_uniqueness)
        print(f"<<< کرال و ترجمه کپشن‌ها تمام شد. {len(unique_captions)} کپشن منحصر به فرد یافت شد."); sys.stdout.flush()
        return unique_captions
    except Exception as e_crawl: print(f"!!! خطا در کرال یا ترجمه کپشن‌ها: {e_crawl}"); sys.stdout.flush(); return []

# --- تابع هوشمندتر شده برای افزودن کپشن‌ها ---
def add_captions_to_images(content_html, crawled_captions_list):
    if not crawled_captions_list or not content_html:
        return content_html

    print(">>> شروع افزودن کپشن‌های ترجمه شده به تصاویر محتوا...")
    sys.stdout.flush()
    soup = BeautifulSoup(content_html, "html.parser")
    images_in_content = soup.find_all("img")
    print(f"--- تعداد عکس در محتوا برای بررسی کپشن: {len(images_in_content)}"); sys.stdout.flush()

    used_caption_indices = set()
    captions_directly_added_count = 0

    # اگر عکسی در محتوا نباشد، کپشن‌های باقی‌مانده را به انتها اضافه کن
    if not images_in_content and crawled_captions_list:
        print("--- هیچ عکسی در محتوا یافت نشد، کپشن‌ها به انتها اضافه می‌شوند.")
        remaining_captions_html = "".join([item['caption'] for item in crawled_captions_list])
        if remaining_captions_html.strip():
            final_captions_div_at_end = soup.new_tag('div', style="text-align: center; margin-top: 15px; font-size: small; border-top: 1px solid #eee; padding-top: 10px;")
            final_captions_div_at_end.append(BeautifulSoup(remaining_captions_html, "html.parser"))
            body_tag_found = soup.find('body') or soup
            body_tag_found.append(final_captions_div_at_end)
        return str(soup)

    for img_content_idx, img_tag_in_content in enumerate(images_in_content):
        # --- بخش کلیدی اضافه شده ---
        # بررسی می‌کنیم آیا تصویر از قبل کپشن دارد یا نه
        parent_figure = img_tag_in_content.find_parent('figure')
        if parent_figure and parent_figure.find('figcaption'):
            print(f"--- عکس {img_content_idx + 1} از قبل کپشن دارد، از آن صرف نظر می‌شود.")
            continue  # به سراغ عکس بعدی می‌رویم

        current_img_src = img_tag_in_content.get("src", "")
        if not current_img_src:
            continue

        normalized_content_img_src = ""
        if not current_img_src.startswith("data:"):
            parsed_content_img_url = urlparse(unquote(current_img_src))
            normalized_content_img_src = parsed_content_img_url._replace(query='').geturl()

        # پیدا کردن کپشن مطابق با این عکس از لیست کرال شده
        matched_caption_data = None
        matched_caption_original_index = -1
        for cap_original_idx, caption_data in enumerate(crawled_captions_list):
            if cap_original_idx in used_caption_indices:
                continue
            if normalized_content_img_src and normalized_content_img_src == caption_data["image_url"]:
                matched_caption_data = caption_data
                matched_caption_original_index = cap_original_idx
                break

        if matched_caption_data:
            print(f"--- افزودن کپشن کرال شده {matched_caption_original_index + 1} به عکس {img_content_idx + 1}")
            sys.stdout.flush()
            caption_html_to_insert = matched_caption_data["caption"]
            new_figure_tag = soup.new_tag("figure", style="margin:1em auto; text-align:center; max-width:100%;")

            # اگر عکس داخل یک تگ <p> یا <div> خالی بود، آن تگ را با figure جایگزین می‌کنیم
            img_parent = img_tag_in_content.parent
            if img_parent and img_parent.name in ['p', 'div'] and not img_parent.get_text(strip=True) and len(list(img_parent.children)) == 1:
                img_parent.replace_with(new_figure_tag)
            else:
                img_tag_in_content.wrap(new_figure_tag)

            if img_tag_in_content.parent != new_figure_tag:
                new_figure_tag.append(img_tag_in_content.extract())

            parsed_caption_for_insertion = BeautifulSoup(caption_html_to_insert, "html.parser")
            final_figcaption_element = parsed_caption_for_insertion.find('figcaption')
            if not final_figcaption_element:
                final_figcaption_element = soup.new_tag('figcaption')
                body_or_root_of_caption = parsed_caption_for_insertion.find('body') or parsed_caption_for_insertion
                for child_node_cap in body_or_root_of_caption.contents:
                    final_figcaption_element.append(child_node_cap.extract())

            # اعمال استایل به کپشن
            current_fig_style = final_figcaption_element.get('style', '')
            fig_style_dict = {s.split(':')[0].strip(): s.split(':')[1].strip() for s in current_fig_style.split(';') if ':' in s and s.strip()}
            fig_style_dict.update({"text-align": "center", "font-size": "0.9em", "margin-top": "0.5em", "color": "#555", "line-height": "1.4"})
            final_figcaption_element['style'] = '; '.join([f"{k.strip()}: {v.strip()}" for k,v in fig_style_dict.items()]) + (';' if fig_style_dict else '')

            new_figure_tag.append(final_figcaption_element)
            used_caption_indices.add(matched_caption_original_index)
            captions_directly_added_count += 1

    # افزودن کپشن‌های باقی‌مانده (که عکسی برایشان پیدا نشد) به انتهای پست
    remaining_captions_html_output = ""
    remaining_captions_added_count = 0
    for i, item_rem in enumerate(crawled_captions_list):
        if i not in used_caption_indices:
            remaining_captions_html_output += item_rem['caption']
            remaining_captions_added_count += 1

    if remaining_captions_html_output.strip():
        print(f"--- افزودن {remaining_captions_added_count} کپشن باقی‌مانده به انتهای محتوا...")
        sys.stdout.flush()
        remaining_div = soup.new_tag('div', style="text-align: center; margin-top: 20px; padding-top: 15px; border-top: 1px solid #eee;")
        remaining_div.append(BeautifulSoup(remaining_captions_html_output, "html.parser"))
        body_tag_found = soup.find('body') or soup
        body_tag_found.append(remaining_div)

    print(f"<<< افزودن کپشن‌ها تمام شد. {captions_directly_added_count} به عکس‌ها اضافه شد، {remaining_captions_added_count} به انتها."); sys.stdout.flush()
    return str(soup)

#----------------------------------


def remove_boilerplate_sections(html_content):
    """
    با استفاده از BeautifulSoup بخش‌های اضافی مانند "Related Reading" را
    بدون حذف کردن محتوای اصلی، به صورت هوشمند حذف می‌کند.
    """
    if not html_content:
        return ""
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # لیست کلمات کلیدی برای شناسایی و حذف بخش‌های اضافی
    # از حروف کوچک استفاده شده تا جستجو به حروف بزرگ و کوچک حساس نباشد
    boilerplate_keywords = [
        'related reading',
        'read also',
        'see also',
        'featured image from',
        'disclaimer:',
    
    ]
    
    # تگ‌های مختلفی که ممکن است حاوی این متون باشند را بررسی می‌کنیم
    tags_to_check = soup.find_all(['p', 'div', 'h2', 'h3'])
    
    for tag in tags_to_check:
        # متن داخل تگ را به حروف کوچک تبدیل کن تا مقایسه راحت‌تر باشد
        tag_text_lower = tag.get_text(strip=True).lower()
        
        # اگر متن تگ با یکی از کلمات کلیدی شروع می‌شد، آن تگ را حذف کن
        if any(tag_text_lower.startswith(keyword) for keyword in boilerplate_keywords):
            print(f"--- حذف بخش اضافی: {tag.get_text(strip=True)[:70]}...")
            tag.decompose() # این دستور تگ را به طور کامل از سند حذف می‌کند
            
    return str(soup)
    
    
    
    #-------------------------------------------





def post_to_wordpress(title_for_wp, content_for_wp, original_english_title, thumbnail_url_for_plugin, status="publish"):
    print(f">>> شروع ارسال پست '{title_for_wp[:50]}...' به endpoint سفارشی وردپرس...")
    sys.stdout.flush()

    english_slug = generate_english_slug(original_english_title)
    print(f"--- اسلاگ انگلیسی تولید شده: {english_slug}")

    credentials = f"{WORDPRESS_USER}:{WORDPRESS_PASS}"
    token = base64.b64encode(credentials.encode())
    headers = {
        'Authorization': f'Basic {token.decode("utf-8")}',
        'Content-Type': 'application/json',
        'User-Agent': 'Python-Rss-To-WordPress-Script/3.3-TV-Resolve'
    }

    post_data = {
        "title": title_for_wp,
        "content": content_for_wp,
        "slug": english_slug,
        "category_id": 69,
        "thumbnail_url": thumbnail_url_for_plugin if thumbnail_url_for_plugin else ""
    }

    print(f"--- در حال ارسال داده به endpoint سفارشی: {WORDPRESS_API_ENDPOINT}")

    max_retries_wp, retry_delay_wp = 2, 25
    for attempt in range(max_retries_wp + 1):
        print(f"--- تلاش {attempt + 1}/{max_retries_wp + 1} برای ارسال...")
        try:
            response = requests.post(WORDPRESS_API_ENDPOINT, headers=headers, json=post_data, timeout=REQUEST_TIMEOUT * 3)
            response.raise_for_status()
            response_data = response.json()

            if response.status_code == 201 and response_data.get("post_id"):
                post_url_wp = response_data.get("url", "نامشخص")
                print(f"<<< پست با موفقیت از طریق endpoint سفارشی ارسال شد! URL: {post_url_wp}")
                return response_data
            else:
                print(f"!!! پاسخ غیرمنتظره از endpoint سفارشی: {response_data}")
                raise ValueError("پاسخ غیرمنتظره از endpoint سفارشی دریافت شد.")

        except requests.exceptions.HTTPError as e_http:
            error_text_from_server = e_http.response.text
            error_message_detail = f"خطای HTTP در ارسال به endpoint سفارشی (کد {e_http.response.status_code}): {error_text_from_server[:500]}"
            print(f"!!! {error_message_detail}")
            if e_http.response.status_code == 404:
                print("!!! خطای 404: Endpoint سفارشی یافت نشد. آیا پلاگین 'My Custom Post Creator' در وردپرس نصب و فعال است؟")
            if attempt < max_retries_wp: time.sleep(retry_delay_wp); retry_delay_wp = int(retry_delay_wp * 1.5); continue
            raise ValueError(error_message_detail)
        except Exception as e:
            print(f"!!! خطای ناشناخته در ارسال به endpoint سفارشی: {e}")
            if attempt < max_retries_wp: time.sleep(retry_delay_wp); retry_delay_wp = int(retry_delay_wp * 1.5); continue
            raise ValueError(f"خطای ناشناخته پس از تلاش‌های مکرر: {e}")

    raise ValueError(f"ارسال پست '{title_for_wp[:50]}...' پس از تمام تلاش‌ها ناموفق بود.")

# --- تابع هوشمند برای استخراج لینک مستقیم عکس از TradingView (نسخه نهایی و جامع) ---
def resolve_tradingview_links(html_content):
    if not html_content:
        return ""

    print(">>> شروع پردازش و تصحیح لینک‌های تصاویر TradingView...")
    sys.stdout.flush()

    soup = BeautifulSoup(html_content, "html.parser")

    # لیستی برای نگهداری تگ‌های عکسی که باید اصلاح شوند و URL صفحه‌ای که باید بررسی شود
    targets_to_process = []

    # حالت اول: پیدا کردن تگ‌های <a> که به چارت لینک می‌دهند
    chart_links = soup.find_all("a", href=re.compile(r"https?://(www\.)?tradingview\.com/x/"))
    for link_tag in chart_links:
        page_url = link_tag.get('href')
        img_tag = link_tag.find("img")
        if page_url and img_tag:
            targets_to_process.append({'img_tag': img_tag, 'page_url': page_url, 'link_tag': link_tag})

    # حالت دوم: پیدا کردن تگ‌های <img> که مستقیماً به صفحه چارت لینک دارند
    direct_img_links = soup.find_all("img", src=re.compile(r"https?://(www\.)?tradingview\.com/x/"))
    for img_tag in direct_img_links:
        # برای جلوگیری از پردازش مجدد، چک می‌کنیم که قبلا اضافه نشده باشد
        is_already_targeted = any(target['img_tag'] is img_tag for target in targets_to_process)
        if not is_already_targeted:
            page_url = img_tag.get('src')
            if page_url:
                targets_to_process.append({'img_tag': img_tag, 'page_url': page_url, 'link_tag': None})

    if not targets_to_process:
        print("--- هیچ لینک TradingView برای تصحیح یافت نشد.")
        return str(soup)

    resolved_count = 0
    for target in targets_to_process:
        img_tag_to_modify = target['img_tag']
        page_url_to_scrape = target['page_url']
        link_tag_to_modify = target.get('link_tag') # ممکن است وجود نداشته باشد

        print(f"--- در حال بررسی لینک TradingView: {page_url_to_scrape[:70]}...")
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36'}
            response = requests.get(page_url_to_scrape, timeout=REQUEST_TIMEOUT, headers=headers)
            response.raise_for_status()

            page_soup = BeautifulSoup(response.content, "html.parser")
            meta_tag = page_soup.find("meta", property="og:image")

            if meta_tag and meta_tag.get("content"):
                direct_image_url = meta_tag["content"]
                print(f"--- لینک مستقیم یافت شد: {direct_image_url}")

                # آدرس عکس اصلی را اصلاح می‌کنیم
                img_tag_to_modify['src'] = direct_image_url
                resolved_count += 1

                # اگر تگ لینک والد وجود داشت، آن را هم اصلاح می‌کنیم
                if link_tag_to_modify:
                    link_tag_to_modify['href'] = direct_image_url
        except requests.exceptions.RequestException as e:
            print(f"!!! خطا در دسترسی به صفحه TradingView ({page_url_to_scrape}): {e}")
        except Exception as e:
            print(f"!!! خطای پیش‌بینی نشده در پردازش لینک TradingView: {e}")

    print(f"<<< پردازش لینک‌های TradingView تمام شد. {resolved_count}/{len(targets_to_process)} لینک با موفقیت تصحیح شد.")
    sys.stdout.flush()

    return str(soup)

def load_processed_links():
    if not os.path.exists(PROCESSED_LINKS_FILE):
        return set()
    try:
        with open(PROCESSED_LINKS_FILE, 'r', encoding='utf-8') as f:
            return {line.strip() for line in f if line.strip()}
    except Exception as e:
        print(f"--- هشدار: امکان خواندن فایل '{PROCESSED_LINKS_FILE}' وجود نداشت: {e}")
        return set()

def save_processed_link(link):
    try:
        with open(PROCESSED_LINKS_FILE, 'a', encoding='utf-8') as f:
            f.write(link + '\n')
    except Exception as e:
        print(f"!!! خطای بحرانی: امکان ذخیره لینک پردازش شده در '{PROCESSED_LINKS_FILE}' وجود نداشت: {e}")

# --- شروع اسکریپت اصلی ---
if __name__ == "__main__":
    logger = Logger(log_file=MASTER_LOG_FILE)
    sys.stdout = logger

    main_script_start_time = time.time()
    print(f"شروع پردازش فید RSS و ارسال به وردپرس")

    original_post_title_english_for_error = "نامشخص"
    final_translated_title_for_error = "نامشخص"
    post_original_link_from_feed = None

    try:
        # مرحله ۰: بارگذاری لینک‌های قبلی و بررسی تکراری بودن
        print("\n>>> مرحله ۰: بررسی پست‌های تکراری...");
        processed_links = load_processed_links()
        print(f"--- {len(processed_links)} لینک پردازش شده از قبل یافت شد.")

        # مرحله ۱: دریافت فید RSS
        print("\n>>> مرحله ۱: دریافت و تجزیه فید RSS...");
        feed_data_parsed = feedparser.parse(RSS_FEED_URL)
        if feed_data_parsed.bozo: print(f"--- هشدار در تجزیه فید: {feed_data_parsed.bozo_exception}")
        if not feed_data_parsed.entries: raise ValueError("هیچ پستی در فید RSS یافت نشد.")

        latest_post_from_feed = feed_data_parsed.entries[0]
        original_post_title_english_for_error = latest_post_from_feed.title
        post_original_link_from_feed = getattr(latest_post_from_feed, 'link', None)

        if not post_original_link_from_feed:
            raise ValueError("پست یافت شده فاقد لینک منبع (link) است. امکان بررسی تکراری بودن وجود ندارد.")

        # بررسی اصلی تکراری بودن
        if post_original_link_from_feed in processed_links:
            print("\n" + "*"*60)
            print(f"*** پست تکراری یافت شد. این پست قبلاً پردازش شده است. ***")
            print(f"*** عنوان: {original_post_title_english_for_error}")
            print(f"*** لینک: {post_original_link_from_feed}")
            print("*"*60 + "\n")
            # In a real scenario, you might want to exit gracefully.
            # For this example, we'll let it finish. In a cron job, sys.exit(0) is appropriate.
            sys.exit(0)

        print(f"--- جدیدترین پست (غیر تکراری) انتخاب شد: '{original_post_title_english_for_error}' (لینک: {post_original_link_from_feed})")
        print("<<< مرحله ۱ کامل شد.");

        # استخراج URL تصویر بندانگشتی
        thumbnail_url_for_plugin_final = None
        if hasattr(latest_post_from_feed, 'media_content') and latest_post_from_feed.media_content:
            raw_thumbnail_url = latest_post_from_feed.media_content[0].get('url', '')
            if raw_thumbnail_url and raw_thumbnail_url.startswith(('http://', 'https://')):
                thumbnail_url_for_plugin_final = raw_thumbnail_url
                print(f"--- URL تصویر بندانگشتی برای پلاگین استخراج شد: {thumbnail_url_for_plugin_final}")
            else:
                print(f"--- هشدار: URL تصویر بندانگشتی ('{raw_thumbnail_url}') از فید برای پلاگین معتبر نیست.")
        else:
            print("--- هیچ تصویر بندانگشتی (media_content) در فید برای پلاگین یافت نشد.")

        # مرحله ۲: کرال کردن و ترجمه کپشن‌ها
        print("\n>>> مرحله ۲: کرال کردن و ترجمه کپشن‌ها...");
        crawled_and_translated_captions = crawl_captions(post_original_link_from_feed)
        print(f"<<< مرحله ۲ کامل شد (تعداد کپشن نهایی: {len(crawled_and_translated_captions)}).");

        # مرحله ۳: ترجمه عنوان پست
        print("\n>>> مرحله ۳: ترجمه عنوان پست...");
        final_translated_title_for_error = translate_title_with_gemini(original_post_title_english_for_error)
        if not final_translated_title_for_error: raise ValueError("ترجمه عنوان پست ناموفق بود یا خالی بازگشت.")
        final_translated_title_for_error = final_translated_title_for_error.replace("**", "").replace("`", "")
        print(f"--- عنوان ترجمه‌شده نهایی: {final_translated_title_for_error}"); print("<<< مرحله ۳ کامل شد.");

        # مرحله ۴: پردازش کامل محتوای اصلی (با ترتیب اصلاح شده)
        print("\n>>> مرحله ۴: پردازش کامل محتوای اصلی...");
        raw_content_html_from_feed = ""
        if 'content' in latest_post_from_feed and latest_post_from_feed.content:
            if isinstance(latest_post_from_feed.content, list) and len(latest_post_from_feed.content) > 0 and 'value' in latest_post_from_feed.content[0]: raw_content_html_from_feed = latest_post_from_feed.content[0]['value']
            elif isinstance(latest_post_from_feed.content, dict) and 'value' in latest_post_from_feed.content: raw_content_html_from_feed = latest_post_from_feed.content['value']
        elif 'summary' in latest_post_from_feed: raw_content_html_from_feed = latest_post_from_feed.summary
        if not raw_content_html_from_feed: raise ValueError("محتوای اصلی (content یا summary) از فید یافت نشد.")
        print(f"--- محتوای خام از فید دریافت شد (طول: {len(raw_content_html_from_feed)} کاراکتر).");

# مرحله ۱ پاکسازی: حذف هوشمند بخش‌های "Related Reading" با تابع جدید
        content_without_boilerplate = remove_boilerplate_sections(raw_content_html_from_feed)

# مرحله ۲ پاکسازی: حذف لینک‌های داخلی از محتوای باقی‌مانده و تمیز شده
        cleaned_content_after_regex = remove_newsbtc_links(content_without_boilerplate)

# ۱. پردازش‌های اولیه تصویر (بدون تغییر لینک اصلی)
        content_after_base64_conversion = replace_filtered_images_in_content_with_base64(cleaned_content_after_regex)

        # ۲. جایگزینی تصاویر با Placeholder و ترجمه
        content_with_placeholders, placeholder_map_generated = replace_images_with_placeholders(content_after_base64_conversion)
        translated_content_main_with_placeholders = translate_with_gemini(content_with_placeholders)
        if not translated_content_main_with_placeholders: raise ValueError("ترجمه محتوای اصلی ناموفق بود یا خالی بازگشت.")

        # ۳. بازگرداندن تصاویر از Placeholder (با لینک‌های اصلی)
        translated_content_with_images_restored = restore_images_from_placeholders(translated_content_main_with_placeholders, placeholder_map_generated)

        # ۴. افزودن کپشن‌ها (در این مرحله URLها تطابق دارند)
        content_with_captions_added = add_captions_to_images(translated_content_with_images_restored, crawled_and_translated_captions)
        
        # ۵. و در نهایت، تصحیح لینک‌های TradingView پس از افزودن کپشن
        content_final_after_tv_resolve = resolve_tradingview_links(content_with_captions_added)

        # ادامه پردازش نهایی روی محتوای کاملاً درست شده
        final_processed_soup = BeautifulSoup(content_final_after_tv_resolve, "html.parser")
        for img_tag_in_final_soup in final_processed_soup.find_all("img"):
            img_tag_in_final_soup['style'] = "max-width:100%; height:auto; display:block; margin:10px auto; border-radius:4px;"
            if not img_tag_in_final_soup.get('alt'): img_tag_in_final_soup['alt'] = final_translated_title_for_error
        for p_tag_to_check in final_processed_soup.find_all('p'):
            if not p_tag_to_check.get_text(strip=True) and not p_tag_to_check.find(['img', 'br', 'hr', 'figure', 'iframe', 'script', 'blockquote']):
                p_tag_to_check.decompose()
        final_processed_content_html = str(final_processed_soup)
        print("<<< مرحله ۴ (پردازش محتوا) کامل شد.");

        # مرحله ۵: آماده‌سازی ساختار نهایی HTML پست
        print("\n>>> مرحله ۵: آماده‌سازی ساختار نهایی HTML پست...");
        list_of_html_components = []
        if final_processed_content_html: list_of_html_components.append(f'<div style="line-height: 1.75; font-size: 17px; text-align: justify;">{final_processed_content_html}</div>')
        
        # ==================== این بخش جدید را اضافه کنید ====================
# افزودن متن سلب مسئولیت (Disclaimer) در انتهای پست
# می‌توانید متن یا استایل را در اینجا به دلخواه تغییر دهید
        disclaimer_text = '<strong>سلب مسئولیت:</strong> احتمال اشتباه در تحلیل ها وجود دارد و هیچ تحلیلی قطعی نیست و همه بر پایه احتمالات میباشند. لطفا در خرید و فروش خود دقت کنید.'

        disclaimer_html_code = (
            f'<div style="color: #c00; '              # رنگ متن قرمز تیره
            'font-size: 0.9em; '                      # سایز فونت کمی کوچکتر
            'margin-top: 25px; '                      # فاصله از بالای متن
            'text-align: justify; '                   # تراز بودن متن
            'border: 1px solid #fdd; '                # یک حاشیه قرمز کم‌رنگ
            'background-color: #fff9f9; '             # یک پس‌زمینه قرمز بسیار روشن
            'padding: 15px; '                         # فاصله داخلی
            f'border-radius: 5px;">{disclaimer_text}</div>'
        )
        list_of_html_components.append(disclaimer_html_code)
# ================== پایان بخش جدیدی که باید اضافه شود ==================
        
        if post_original_link_from_feed:
            source_attribution_text = "منبع: NewsBTC"
            source_link_html_code = (f'<hr style="margin-top: 25px; margin-bottom: 15px; border: 0; border-top: 1px solid #eee;"><p style="text-align:right; margin-top:15px; font-size: 0.85em; color: #555;"><em><a href="{post_original_link_from_feed}" target="_blank" rel="noopener noreferrer nofollow" style="color: #1a0dab; text-decoration: none;">{source_attribution_text}</a></em></p>')
            list_of_html_components.append(source_link_html_code)
        final_html_payload_for_wordpress = "".join(list_of_html_components)
        print("<<< مرحله ۵ (ساختار نهایی) کامل شد.");

        # مرحله ۶: ارسال پست به وردپرس
        print("\n>>> مرحله ۶: ارسال پست به وردپرس...");
        post_response = post_to_wordpress(
            title_for_wp=final_translated_title_for_error,
            content_for_wp=final_html_payload_for_wordpress,
            original_english_title=original_post_title_english_for_error,
            thumbnail_url_for_plugin=thumbnail_url_for_plugin_final,
            status="publish"
        )
        print("<<< مرحله ۶ (ارسال به وردپرس) کامل شد.");

        # مرحله ۷: ذخیره لینک در صورت موفقیت
        if post_response and post_response.get("post_id"):
            print("\n>>> مرحله ۷: ذخیره کردن لینک منبع برای جلوگیری از تکرار...");
            save_processed_link(post_original_link_from_feed)
            print(f"--- لینک '{post_original_link_from_feed[:70]}...' با موفقیت در فایل ثبت شد.")
            print("<<< مرحله ۷ کامل شد.")

    except Exception as global_exception:
        print("\n" + "!"*70 + "\n!!! خطای کلی و بحرانی در اجرای اسکریپت رخ داد. هیچ پستی ایجاد نشد. !!!")
        print(f"!!! عنوان پست اصلی (انگلیسی): {original_post_title_english_for_error}")
        print(f"!!! لینک منبع (در صورت وجود): {post_original_link_from_feed}")
        print(f"!!! عنوان ترجمه شده (در صورت وجود): {final_translated_title_for_error}")
        print(f"!!! نوع خطا: {type(global_exception).__name__}"); print(f"!!! پیام خطا: {global_exception}")
        print("--- جزئیات Traceback (آخرین بخش‌ها) ---")
        tb_lines = traceback.format_exception(type(global_exception), global_exception, global_exception.__traceback__)
        for line in tb_lines[-15:]: print(line.strip())
        print("!"*70 + "\n");
        # sys.exit(1) # Uncomment for production to exit with an error code

    finally:
        total_script_execution_time = time.time() - main_script_start_time
        print(f"\nاسکریپت به پایان رسید (زمان کل: {total_script_execution_time:.2f} ثانیه).")
        if 'logger' in locals() and isinstance(logger, Logger):
            logger.close()
            sys.stdout = logger.terminal
