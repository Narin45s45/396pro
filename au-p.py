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
import uuid

# --- تنظیمات و توابع اولیه (translate_with_gemini, remove_newsbtc_links, replace_twimg_with_base64, crawl_captions, replace_images_with_placeholders, restore_images_from_placeholders) ---
# این بخش ها مانند کد قبلی هستند و برای اختصار تکرار نمی شوند.
# فرض کنید تمام توابع لازم از پاسخ قبلی اینجا کپی شده اند.

# --- تابع ترجمه با Gemini (مانند قبل) ---
# ... (کد کامل تابع translate_with_gemini) ...
def translate_with_gemini(text, target_lang="fa"):
    # ... (کد کامل تابع از پاسخ قبلی) ...
    # Ensure the print statements and sys.stdout.flush() are kept
    print(f">>> شروع ترجمه متن با Gemini (طول متن: {len(text)} کاراکتر)...")
    sys.stdout.flush()
    if not text or text.isspace():
         print("--- متن ورودی برای ترجمه خالی است. رد شدن از ترجمه.")
         sys.stdout.flush()
         return ""
    # ... بقیه کد تابع ...
    # Make sure to handle errors and return translated text or raise exception

# --- تابع حذف لینک‌های newsbtc (مانند قبل) ---
def remove_newsbtc_links(text):
    # ... (کد کامل تابع از پاسخ قبلی) ...
    pass

# --- تابع جایگزینی URLهای twimg.com با Base64 (مانند قبل) ---
def replace_twimg_with_base64(content):
    # ... (کد کامل تابع از پاسخ قبلی) ...
    pass

# --- تابع کرال کردن کپشن‌ها (مانند قبل) ---
def crawl_captions(post_url):
    # ... (کد کامل تابع از پاسخ قبلی) ...
    pass

# --- تابع جایگزینی عکس با Placeholder (مانند قبل) ---
def replace_images_with_placeholders(html_content):
    # ... (کد کامل تابع از پاسخ قبلی) ...
    pass

# --- تابع بازگرداندن عکس از Placeholder (مانند قبل) ---
def restore_images_from_placeholders(html_content, placeholder_map):
    # ... (کد کامل تابع از پاسخ قبلی) ...
    pass


# --- تابع قرار دادن کپشن‌ها زیر عکس‌ها (با تغییر جزئی برای استفاده از کپشن ترجمه شده) ---
def add_captions_to_images(content, captions_data_list): # تغییر نام پارامتر برای وضوح
    if not captions_data_list:
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
    images = soup.find_all("img")
    print(f"--- تعداد عکس‌های یافت شده در محتوا: {len(images)}")
    sys.stdout.flush()

    if not images:
        print("--- هیچ عکسی در محتوا یافت نشد. کپشن‌ها در انتها اضافه می‌شوند.")
        sys.stdout.flush()
        # استفاده از کپشن ترجمه شده در صورت وجود
        captions_html = "".join([item.get('translated_caption', item['caption']) for item in captions_data_list])
        final_captions_div = soup.new_tag('div', style="text-align: center; margin-top: 15px; font-size: small;")
        final_captions_div.append(BeautifulSoup(captions_html, "html.parser"))
        soup.append(final_captions_div)
        return str(soup)

    used_caption_indices = set()
    captions_added_count = 0

    for img_index, img in enumerate(images):
        potential_match_index = img_index
        if potential_match_index < len(captions_data_list) and potential_match_index not in used_caption_indices:
            matching_caption_data = captions_data_list[potential_match_index]
            # *** تغییر اصلی اینجاست: استفاده از کپشن ترجمه شده در صورت وجود ***
            caption_html_to_use = matching_caption_data.get('translated_caption', matching_caption_data['caption'])
            # ****************************************************************
            original_url = matching_caption_data["image_url"] # برای لاگ

            print(f"--- تلاش برای افزودن کپشن {potential_match_index + 1} (از عکس اصلی: {original_url[:60]}) به عکس {img_index + 1}...")
            sys.stdout.flush()

            figure = soup.new_tag("figure")
            figure['style'] = "margin: 1em auto; text-align: center; max-width: 100%;"

            parent = img.parent
            if parent.name in ['p', 'div'] and not parent.get_text(strip=True):
                 parent.replace_with(figure)
                 figure.append(img)
            else:
                 img.wrap(figure)

            # Parse the caption HTML (which might be translated or original)
            caption_soup = BeautifulSoup(caption_html_to_use, "html.parser")
            caption_content = caption_soup.find(['figcaption', 'p', 'div', 'span'])
            if not caption_content:
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
                used_caption_indices.add(potential_match_index)
                captions_added_count += 1
                print(f"---   کپشن {potential_match_index + 1} اضافه شد.")
                sys.stdout.flush()
            else:
                 print(f"---   هشدار: محتوای کپشن {potential_match_index + 1} یافت نشد.")
                 sys.stdout.flush()

    # اضافه کردن کپشن‌های استفاده نشده به انتها (با استفاده از ترجمه شده در صورت وجود)
    remaining_captions_html = ""
    remaining_count = 0
    for i, item in enumerate(captions_data_list):
         if i not in used_caption_indices:
              remaining_captions_html += item.get('translated_caption', item['caption']) # استفاده از ترجمه
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
# ... (مانند قبل) ...
print("\n>>> مرحله ۱: دریافت و تجزیه فید RSS...")
sys.stdout.flush()
feed = feedparser.parse(RSS_FEED_URL) # Assuming success based on previous run
latest_post = feed.entries[0]
print(f"--- جدیدترین پست انتخاب شد: '{latest_post.title}'")
sys.stdout.flush()
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
    print(f"--- هشدار: لینک پست اصلی معتبر ({post_link}) یافت نشد.")
    sys.stdout.flush()
print(f"<<< مرحله ۲ کامل شد (تعداد کپشن یافت شده: {len(original_captions_with_images)}).")
sys.stdout.flush()

# *********** مرحله جدید: ترجمه کپشن‌ها ***********
print("\n>>> مرحله ۲.۵: ترجمه کپشن‌های استخراج شده...")
sys.stdout.flush()
translated_caption_count = 0
if original_captions_with_images:
    for i, item in enumerate(original_captions_with_images):
        caption_html = item.get('caption', '')
        print(f"--- ترجمه کپشن {i+1}/{len(original_captions_with_images)} (طول: {len(caption_html)})...")
        sys.stdout.flush()
        if caption_html:
            try:
                # توجه: ترجمه کپشن ممکن است تگ اصلی (مثلا figcaption) را برگرداند یا نه
                # باید مطمئن شویم فقط محتوای متنی ترجمه می شود اگر تگ حذف شد
                translated_caption_html = translate_with_gemini(caption_html)
                item['translated_caption'] = translated_caption_html # ذخیره نتیجه
                print(f"---   ترجمه کپشن {i+1} انجام شد.")
                sys.stdout.flush()
                translated_caption_count += 1
            except Exception as e:
                print(f"!!!   خطا در ترجمه کپشن {i+1}: {e}. از کپشن اصلی استفاده خواهد شد.")
                sys.stdout.flush()
                item['translated_caption'] = caption_html # Fallback to original
        else:
            print(f"---   کپشن {i+1} خالی است، رد شدن از ترجمه.")
            sys.stdout.flush()
            item['translated_caption'] = '' # Ensure key exists
    print(f"<<< مرحله ۲.۵ کامل شد ({translated_caption_count}/{len(original_captions_with_images)} کپشن ترجمه شد).")
else:
    print("--- هیچ کپشنی برای ترجمه وجود ندارد.")
sys.stdout.flush()
# **************************************************

# 3. ترجمه عنوان
# ... (مانند قبل) ...
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
# ... (مانند قبل) ...
print("\n>>> مرحله ۴: پردازش تصویر بندانگشتی...")
sys.stdout.flush()
thumbnail_html = ""
# ... (کد کامل پردازش thumbnail با استفاده از replace_twimg_with_base64 مانند قبل) ...
print("<<< مرحله ۴ کامل شد.") # فرض موفقیت یا رد شدن
sys.stdout.flush()

# 5. پردازش محتوای اصلی (با Placeholder)
# ... (مانند قبل، فقط تابع add_captions_to_images حالا از لیست کپشن‌های آپدیت شده استفاده می‌کند) ...
print("\n>>> مرحله ۵: پردازش محتوای اصلی...")
sys.stdout.flush()
# ... (کد کامل مرحله 5 از دریافت content_source تا ساخت final_content_for_post مانند قبل) ...
# ... (شامل پاکسازی، تبدیل base64، جایگزینی placeholder، ترجمه، بازگردانی placeholder) ...
# ... (فقط توجه شود که حالا add_captions_to_images کپشن‌های ترجمه شده را استفاده می‌کند) ...
print("<<< مرحله ۵ کامل شد.")
sys.stdout.flush()


# 6. ساختار نهایی پست
# ... (مانند قبل) ...
print("\n>>> مرحله ۶: آماده‌سازی ساختار نهایی پست HTML...")
sys.stdout.flush()
# ... (کد کامل مرحله 6 مانند قبل) ...
print("<<< مرحله ۶ کامل شد.")
sys.stdout.flush()


# 7. ارسال به بلاگر
# ... (مانند قبل) ...
print("\n>>> مرحله ۷: ارسال پست به بلاگر...")
sys.stdout.flush()
# ... (کد کامل مرحله 7 با لاگ و مدیریت خطا مانند قبل) ...

print("\n" + "="*50)
print(">>> اسکریپت به پایان رسید.")
print("="*50)
sys.stdout.flush()
