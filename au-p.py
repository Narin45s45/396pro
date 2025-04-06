import feedparser
import os
import json
import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import re
from bs4 import BeautifulSoup
import time
import base64 # <-- اضافه کردن ایمپورت base64
from urllib.parse import urlparse # برای گرفتن پسوند فایل از URL

# تنظیمات فید RSS
RSS_FEED_URL = "https://www.newsbtc.com/feed/"

# تنظیمات API Gemini
GEMINI_API_KEY = os.environ.get("GEMAPI")
if not GEMINI_API_KEY:
    raise ValueError("GEMAPI پیدا نشد!")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent" # Use gemini-1.5-flash

# گرفتن توکن بلاگر
creds_json = os.environ.get("CREDENTIALS")
if not creds_json:
    raise ValueError("CREDENTIALS پیدا نشد!")
try:
    creds_info = json.loads(creds_json)
    # Ensure necessary keys are present
    if 'token' not in creds_info or 'refresh_token' not in creds_info or \
       'client_id' not in creds_info or 'client_secret' not in creds_info or \
       'scopes' not in creds_info:
        raise ValueError("فایل CREDENTIALS ناقص است. کلیدهای لازم: token, refresh_token, client_id, client_secret, scopes")
    creds = Credentials.from_authorized_user_info(creds_info)
except json.JSONDecodeError:
    raise ValueError("فرمت CREDENTIALS نامعتبر است (باید JSON باشد).")
except Exception as e:
     raise ValueError(f"خطا در بارگذاری CREDENTIALS: {e}")

service = build("blogger", "v3", credentials=creds)
blog_id = "764765195397447456" # ID بلاگ را اینجا قرار دهید

# تابع ترجمه با Gemini (بدون تغییر)
def translate_with_gemini(text, target_lang="fa"):
    headers = {"Content-Type": "application/json"}
    prompt = (
        f"Please translate the following English text (which might contain HTML tags) into {target_lang} "
        f"with the utmost intelligence and precision. Pay close attention to context and nuance.\n"
        f"IMPORTANT TRANSLATION RULES:\n"
        f"1. Translate ALL text content, including text inside HTML tags like <p>, <li>, and especially <blockquote>. Do not skip any content.\n"
        f"2. For technical terms or English words commonly used in the field (like cryptocurrency, finance, technology), "
        f"transliterate them into Persian script (Finglish) instead of translating them into a potentially obscure Persian word. "
        f"Example: 'Stochastic Oscillator' should become 'اوسیلاتور استوکستیک'. Apply consistently.\n"
        f"3. Ensure that any text within quotation marks (\"\") is also accurately translated.\n"
        f"4. Preserve the original HTML structure as much as possible, only translating the text content within the tags.\n"
        f"OUTPUT REQUIREMENT: Do not add any explanations, comments, or options. Only return the final, high-quality translated text (potentially including the original HTML tags with translated content).\n\n"
        f"English Text with HTML to Translate:\n{text}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.5}
    }
    max_retries = 3 # Increased retries
    retry_delay = 10 # Increased delay
    for attempt in range(max_retries + 1):
        try:
            response = requests.post(f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", headers=headers, json=payload, timeout=60) # Added timeout
            response.raise_for_status() # Will raise HTTPError for bad responses (4xx or 5xx)

            # Check for 429 specificially for rate limit
            if response.status_code == 429 and attempt < max_retries:
                 print(f"خطای Rate Limit (429). منتظر ماندن برای {retry_delay} ثانیه... (تلاش {attempt + 1}/{max_retries})")
                 time.sleep(retry_delay)
                 retry_delay *= 2 # Exponential backoff
                 continue # Retry the loop

            result = response.json()

            # Defensive checks for Gemini API response structure
            if not result or "candidates" not in result or not result["candidates"]:
                 raise ValueError(f"پاسخ غیرمنتظره از API Gemini دریافت شد (بدون candidates): {result}")
            if "content" not in result["candidates"][0] or "parts" not in result["candidates"][0]["content"] or not result["candidates"][0]["content"]["parts"]:
                 # Sometimes Gemini might block due to safety settings, check for that
                 if "promptFeedback" in result and "blockReason" in result["promptFeedback"]:
                      raise ValueError(f"API Gemini به دلیل {result['promptFeedback']['blockReason']} درخواست را مسدود کرد.")
                 raise ValueError(f"پاسخ غیرمنتظره از API Gemini دریافت شد (ساختار نامعتبر content/parts): {result}")
            if "text" not in result["candidates"][0]["content"]["parts"][0]:
                 raise ValueError(f"پاسخ غیرمنتظره از API Gemini دریافت شد (بدون text در part): {result}")

            translated_text = result["candidates"][0]["content"]["parts"][0]["text"]
            return translated_text.strip()

        except requests.exceptions.Timeout:
             print(f"خطا: درخواست به API Gemini زمان‌بر شد (Timeout). تلاش مجدد...")
             if attempt >= max_retries:
                 raise ValueError("API Gemini پس از چند بار تلاش پاسخ نداد (Timeout).")
             time.sleep(retry_delay)
        except requests.exceptions.RequestException as e:
            # Handle other potential network errors
            print(f"خطا در درخواست API: {e}. تلاش مجدد...")
            if attempt >= max_retries:
                 raise ValueError(f"خطا در درخواست API پس از چند بار تلاش: {e}")
            time.sleep(retry_delay)
        except (ValueError, KeyError) as e:
             # Handle errors from Gemini response parsing or explicit ValueErrors
             print(f"خطا در پردازش پاسخ Gemini: {e}")
             # Log the problematic response for debugging if possible
             try:
                 print(f"متن پاسخ مشکل‌دار: {response.text}")
             except NameError: # response might not be defined if request failed early
                 pass
             raise # Re-raise the specific error

    # If loop finishes without returning/raising, something went wrong
    raise ValueError("ترجمه با Gemini پس از چند بار تلاش ناموفق بود.")


# تابع حذف لینک‌های newsbtc (بدون تغییر)
def remove_newsbtc_links(text):
    pattern = r'<a\s+[^>]*href=["\']https?://(www\.)?newsbtc\.com[^"\']*["\'][^>]*>(.*?)</a>'
    # Make sure to handle potential None result from re.sub if input is None
    return re.sub(pattern, r'\2', text, flags=re.IGNORECASE) if text else ""

# --- تابع upload_image_to_blogger حذف شد ---

# تابع جدید برای جایگزینی URLهای twimg.com با Base64
def replace_twimg_with_base64(content):
    """
    پیدا کردن تمام تگ‌های <img> با src از twimg.com، دانلود عکس‌ها،
    و جایگزینی src با data URI حاوی محتوای base64.
    """
    if not content:
        return ""
    soup = BeautifulSoup(content, "html.parser")
    images = soup.find_all("img")
    print(f"تعداد عکس های پیدا شده برای بررسی twimg.com: {len(images)}")
    modified = False
    for img in images:
        src = img.get("src", "")
        if "twimg.com" in src:
            print(f"در حال تلاش برای تبدیل عکس twimg: {src}")
            try:
                # اضافه کردن هدر User-Agent برای جلوگیری از بلاک شدن احتمالی
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
                response = requests.get(src, stream=True, timeout=20, headers=headers)
                response.raise_for_status()

                # دریافت نوع محتوا (MIME type)
                content_type = response.headers.get('content-type')
                if not content_type or not content_type.startswith('image/'):
                    # اگر نوع محتوا عکس نیست یا مشخص نیست، سعی کن از URL حدس بزنی
                    parsed_url = urlparse(src)
                    path = parsed_url.path
                    ext = os.path.splitext(path)[1].lower()
                    if ext == '.jpg' or ext == '.jpeg':
                        content_type = 'image/jpeg'
                    elif ext == '.png':
                        content_type = 'image/png'
                    elif ext == '.gif':
                        content_type = 'image/gif'
                    elif ext == '.webp':
                         content_type = 'image/webp'
                    else:
                        print(f"هشدار: نوع محتوای نامشخص برای {src}. از image/jpeg استفاده می‌شود.")
                        content_type = 'image/jpeg' # پیش‌فرض

                image_content = response.content
                base64_encoded_data = base64.b64encode(image_content)
                base64_string = base64_encoded_data.decode('utf-8')

                data_uri = f"data:{content_type};base64,{base64_string}"
                img['src'] = data_uri
                # اضافه کردن alt اگر وجود ندارد
                if not img.get('alt'):
                    img['alt'] = "تصویر بارگذاری شده"
                print(f"عکس {src} با موفقیت به Base64 تبدیل شد.")
                modified = True

            except requests.exceptions.RequestException as e:
                print(f"خطا در دانلود عکس {src}: {e}. عکس اصلی باقی می‌ماند.")
            except Exception as e:
                print(f"خطای غیرمنتظره هنگام پردازش عکس {src}: {e}. عکس اصلی باقی می‌ماند.")

    # فقط در صورت تغییر، به رشته تبدیل کن
    return str(soup) if modified else content


# تابع کرال کردن کپشن‌ها با تطابق عکس (بدون تغییر)
def crawl_captions(post_url):
    captions_with_images = []
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(post_url, timeout=30, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")


        # کپشن‌های داخل <figure>
        figures = soup.find_all("figure")
        for figure in figures:
            img = figure.find("img")
            caption_tag = figure.find("figcaption") # Relax class requirement
            if img and caption_tag:
                img_src = img.get("src") or img.get("data-src") # Check data-src too for lazy loading
                if img_src:
                     captions_with_images.append({
                         "image_url": img_src,
                         "caption": str(caption_tag) # Keep caption as HTML string
                    })


        # کپشن‌های <p> یا <div> یا <span> که استایل مرکزی دارند و *بلافاصله بعد* از عکس یا figure هستند
        # This logic needs refinement - matching based purely on style is fragile.
        # Let's try matching <p> directly after an image container (div/figure)
        images_or_figures = soup.find_all(['img', 'figure'])
        found_standalone_captions = set()


        for item in images_or_figures:
             # Look for a <p> immediately following the element or its parent
             potential_caption = None
             if item.next_sibling and item.next_sibling.name == 'p':
                 potential_caption = item.next_sibling
             elif item.parent and item.parent.next_sibling and item.parent.next_sibling.name == 'p':
                  potential_caption = item.parent.next_sibling

             # Basic check: does it look like a caption (short, maybe centered)?
             if potential_caption and len(potential_caption.get_text(strip=True)) < 150: # Arbitrary length limit
                 img_src = None
                 if item.name == 'img':
                     img_src = item.get('src') or item.get('data-src')
                 elif item.name == 'figure':
                     img_tag = item.find('img')
                     if img_tag:
                          img_src = img_tag.get('src') or img_tag.get('data-src')

                 caption_html = str(potential_caption)
                 # Avoid adding duplicate captions found by the figure logic
                 is_duplicate = any(c['caption'] == caption_html for c in captions_with_images)

                 if img_src and not is_duplicate and caption_html not in found_standalone_captions:
                     print(f"کپشن احتمالی بعد از عکس پیدا شد: {potential_caption.get_text(strip=True)} برای عکس {img_src}")
                     captions_with_images.append({
                         "image_url": img_src,
                         "caption": caption_html
                     })
                     found_standalone_captions.add(caption_html)


        print("کپشن‌های کرال‌شده با URL عکس:")
        unique_captions = []
        seen_captions = set()
        for item in captions_with_images:
             # Ensure caption text uniqueness to avoid duplicates from different methods
             caption_text = BeautifulSoup(item['caption'], 'html.parser').get_text(strip=True)
             if caption_text not in seen_captions:
                 unique_captions.append(item)
                 seen_captions.add(caption_text)


        captions_with_images = unique_captions
        for i, item in enumerate(captions_with_images, 1):
            print(f"کپشن {i}: {BeautifulSoup(item['caption'], 'html.parser').get_text(strip=True)} (عکس: {item['image_url']})")

        return captions_with_images

    except requests.exceptions.RequestException as e:
        print(f"خطا در کرال کردن {post_url}: {e}")
        return []
    except Exception as e:
         print(f"خطای غیرمنتظره در کرال کردن کپشن ها: {e}")
         return []


# تابع قرار دادن کپشن‌ها زیر عکس‌های مرتبط (وسط‌چین) - نیازمند بهبود تطابق URL
def add_captions_to_images(content, original_captions_with_images):
    if not original_captions_with_images:
        print("هیچ کپشنی برای اضافه کردن وجود ندارد.")
        return content
    if not content:
         print("محتوای ورودی برای اضافه کردن کپشن خالی است.")
         return ""

    soup = BeautifulSoup(content, "html.parser")
    images = soup.find_all("img")
    print(f"تعداد عکس‌های پیدا شده در محتوای ترجمه‌شده: {len(images)}")
    if not images:
         print("هیچ عکسی در محتوای ترجمه شده برای افزودن کپشن یافت نشد.")
         # Add captions at the end if no images are found
         captions_html = "".join([item['caption'] for item in original_captions_with_images])
         soup.append(BeautifulSoup(f'<div style="text-align: center; direction: rtl; margin-top: 10px;">{captions_html}</div>', "html.parser"))
         return str(soup)


    used_caption_indices = set() # Track used captions by index

    for img_index, img in enumerate(images):
        img_src = img.get("src", "")
        # تطبیق باید دقیق‌تر باشد چون src ممکن است data URI باشد
        # بهترین تطبیق: سعی کنید URL اصلی را از کپشن‌های کرال شده پیدا کنید
        # که به این عکس (که الان ممکن است data URI باشد) بیشترین شباهت را دارد.
        # این بخش پیچیده است. یک راه ساده‌تر: تطابق بر اساس ترتیب ظاهر شدن.
        # فرض: ترتیب عکس‌ها در محتوای اصلی و ترجمه شده یکسان است.

        best_match_caption_index = -1

        # Try finding a caption whose original URL *might* correspond to this image
        # This is heuristic and might fail if images were reordered or removed.
        # A simple approach: match based on order if possible.
        potential_match_index = img_index # Try matching based on order first

        if potential_match_index < len(original_captions_with_images) and potential_match_index not in used_caption_indices:
             best_match_caption_index = potential_match_index
        # else:
             # Fallback: Look for the *next available* unused caption
             # for cap_idx in range(len(original_captions_with_images)):
             #      if cap_idx not in used_caption_indices:
             #           best_match_caption_index = cap_idx
             #           break


        if best_match_caption_index != -1:
             matching_caption_html = original_captions_with_images[best_match_caption_index]["caption"]
             original_url = original_captions_with_images[best_match_caption_index]["image_url"] # For logging

             # Create a figure element to wrap the image and caption
             figure = soup.new_tag("figure")
             # Center the figure itself which contains the image and caption
             figure['style'] = "margin-left: auto; margin-right: auto; text-align: center; max-width: 100%;" # Center block

             # Move the image inside the figure
             img.wrap(figure)

             # Parse the caption HTML and append it to the figure
             caption_soup = BeautifulSoup(matching_caption_html, "html.parser")
             # Ensure the caption tag (often <figcaption> or <p>) exists
             caption_content = caption_soup.find(['figcaption', 'p', 'div', 'span'])
             if caption_content:
                 # Add centering style to the caption element itself if needed, and RTL direction
                 caption_content['style'] = caption_content.get('style', '') + ' text-align: center; direction: rtl; margin-top: 5px;'
                 figure.append(caption_content) # Append the parsed caption tag
                 used_caption_indices.add(best_match_caption_index)
                 print(f"کپشن (از {original_url}) به عکس {img_index+1} (src: {img_src[:30]}...) اضافه شد.")
             else:
                  print(f"هشدار: نتوانست تگ محتوای کپشن را برای کپشن {best_match_caption_index} پیدا کند.")
                  # Fallback: append raw HTML string wrapped in a div
                  fallback_caption_div = soup.new_tag('div', style="text-align: center; direction: rtl; margin-top: 5px;")
                  fallback_caption_div.append(BeautifulSoup(matching_caption_html, 'html.parser'))
                  figure.append(fallback_caption_div)
                  used_caption_indices.add(best_match_caption_index)
                  print(f"کپشن خام (از {original_url}) به عکس {img_index+1} اضافه شد.")


    # اضافه کردن کپشن‌های استفاده نشده به انتها
    remaining_captions_html = ""
    for i, item in enumerate(original_captions_with_images):
         if i not in used_caption_indices:
              print(f"کپشن استفاده نشده (از عکس {item['image_url']}) به انتها اضافه می‌شود.")
              remaining_captions_html += item['caption']

    if remaining_captions_html:
        # Wrap remaining captions in a centered, RTL div
        remaining_div = BeautifulSoup(f'<div style="text-align: center; direction: rtl; margin-top: 15px;">{remaining_captions_html}</div>', "html.parser")
        # Add style to inner elements too if needed
        for tag in remaining_div.find_all(True):
             tag['style'] = tag.get('style', '') + ' text-align: center; direction: rtl;'
        soup.append(remaining_div)


    return str(soup)

# --- شروع اسکریپت اصلی ---

print("در حال دریافت فید RSS...")
try:
    feed = feedparser.parse(RSS_FEED_URL)
    if feed.bozo:
        print(f"هشدار: خطایی در تجزیه فید RSS وجود دارد: {feed.bozo_exception}")
    if not feed.entries:
        print("هیچ پستی در فید RSS یافت نشد.")
        exit()
except Exception as e:
     print(f"خطا در دریافت یا تجزیه فید RSS: {e}")
     exit()


latest_post = feed.entries[0]
print(f"جدیدترین پست با عنوان '{latest_post.title}' پیدا شد.")

# کرال کردن کپشن‌ها
post_link = getattr(latest_post, 'link', None)
original_captions_with_images = []
if post_link and (post_link.startswith('http://') or post_link.startswith('https://')):
    print(f"در حال کرال کردن کپشن‌ها از {post_link}...")
    original_captions_with_images = crawl_captions(post_link)
else:
    print(f"هشدار: لینک پست معتبر ({post_link}) یافت نشد.")


# آماده‌سازی متن پست
title = latest_post.title
content_html = ""


# ترجمه عنوان
print("در حال ترجمه عنوان...")
try:
    translated_title = translate_with_gemini(title).splitlines()[0]
     # Remove potential markdown like **
    translated_title = translated_title.replace("**", "")
    print(f"عنوان ترجمه‌شده: {translated_title}")
except Exception as e:
    print(f"خطا در ترجمه عنوان: {e}")
    translated_title = title # Fallback to original title

# پردازش تصویر بندانگشتی (Thumbnail)
thumbnail_html = ""
if hasattr(latest_post, 'media_content') and latest_post.media_content:
    thumbnail_url = latest_post.media_content[0].get('url', '')
    if thumbnail_url and (thumbnail_url.startswith('http://') or thumbnail_url.startswith('https://')):
        print(f"پردازش تصویر بندانگشتی: {thumbnail_url}")
        if "twimg.com" in thumbnail_url:
            print("تصویر بندانگشتی از twimg.com است، تبدیل به Base64...")
            # Use the same base64 conversion logic
            temp_html = f'<img src="{thumbnail_url}" alt="{translated_title}">' # Create temp tag
            converted_html = replace_twimg_with_base64(temp_html)
            if converted_html != temp_html : # Check if conversion happened
                 # Wrap in centered div with styles
                 thumbnail_html = f'<div style="text-align:center;"><img src="{BeautifulSoup(converted_html, "html.parser").img["src"]}" alt="{translated_title}" style="max-width:100%; height:auto; display:block; margin-left:auto; margin-right:auto;"></div>'
                 print("تصویر بندانگشتی twimg با موفقیت به Base64 تبدیل شد.")
            else:
                 print("هشدار: تبدیل تصویر بندانگشتی twimg به Base64 ناموفق بود.")
                 # Fallback to original URL but still wrap it
                 thumbnail_html = f'<div style="text-align:center;"><img src="{thumbnail_url}" alt="{translated_title}" style="max-width:100%; height:auto; display:block; margin-left:auto; margin-right:auto;"></div>'

        else:
            # Non-twimg thumbnail, just wrap it
            thumbnail_html = f'<div style="text-align:center;"><img src="{thumbnail_url}" alt="{translated_title}" style="max-width:100%; height:auto; display:block; margin-left:auto; margin-right:auto;"></div>'
    else:
         print("URL تصویر بندانگشتی نامعتبر است یا یافت نشد.")
else:
     print("هیچ تصویر بندانگشتی (media_content) در فید یافت نشد.")


# پردازش محتوا
print("در حال پردازش محتوا...")
content_source = ""
if 'content' in latest_post and latest_post.content:
     # Ensure content is a list and take the first item's value
     if isinstance(latest_post.content, list) and len(latest_post.content) > 0 and 'value' in latest_post.content[0]:
          content_source = latest_post.content[0]['value']
     # Handle cases where content might be a dictionary itself (less common in feedparser)
     elif isinstance(latest_post.content, dict) and 'value' in latest_post.content:
          content_source = latest_post.content['value']
elif 'summary' in latest_post:
     content_source = latest_post.summary
else:
     print("هشدار: نه 'content' و نه 'summary' در پست RSS یافت نشد.")


translated_html_content = ""
if content_source:
    # 1. پاکسازی اولیه (قبل از پردازش عکس و کپشن)
    content_cleaned = re.split(r'Related Reading|Read Also|See Also|Featured image from', content_source, flags=re.IGNORECASE)[0].strip()
    content_cleaned = remove_newsbtc_links(content_cleaned)

    # 2. تبدیل عکس‌های twimg.com به Base64 (روی محتوای اصلی)
    print("تبدیل عکس‌های twimg.com در محتوا...")
    content_with_base64_images = replace_twimg_with_base64(content_cleaned)

    # 3. ترجمه محتوا (که حالا شامل عکس‌های base64 است)
    print("در حال ترجمه محتوا...")
    try:
        translated_content_raw = translate_with_gemini(content_with_base64_images)

        # 4. اضافه کردن کپشن‌ها به محتوای *ترجمه شده*
        # Pass the *original* captions list for matching purposes
        print("اضافه کردن کپشن‌ها به محتوای ترجمه‌شده...")
        translated_content_with_captions = add_captions_to_images(translated_content_raw, original_captions_with_images)

        # 5. تنظیمات نهایی استایل برای عکس‌ها در محتوای نهایی
        print("اعمال استایل نهایی به عکس‌ها...")
        soup_final = BeautifulSoup(translated_content_with_captions, "html.parser")
        for img_tag in soup_final.find_all("img"):
            # Apply centering and responsive styles, ensure block display
            img_tag['style'] = img_tag.get('style', '') + ' display:block; margin-left:auto; margin-right:auto; max-width:100%; height:auto;'
            # Ensure alt text exists
            if not img_tag.get('alt'):
                img_tag['alt'] = translated_title # Use translated title as default alt text

        # Remove potentially empty <p> tags often left by translation/processing
        for p_tag in soup_final.find_all('p'):
             if not p_tag.get_text(strip=True) and not p_tag.find(['img', 'br', 'figure']):
                 p_tag.decompose()

        content_html = str(soup_final)
        print("ترجمه و پردازش محتوا کامل شد.")

    except Exception as e:
        print(f"خطا در ترجمه یا پردازش نهایی محتوا: {e}")
        # Fallback: نمایش محتوای اصلی (با عکس‌های base64) در حالت LTR
        content_html = f"<p><i>[خطا در ترجمه محتوا رخ داد. نمایش محتوای اصلی با عکس‌های تبدیل‌شده در زیر.]</i></p><div style='text-align:left; direction:ltr;'>{content_with_base64_images}</div>"

elif original_captions_with_images:
     # If no main content but captions exist, just use them
     print("محتوای اصلی یافت نشد، فقط از کپشن‌ها استفاده می‌شود.")
     captions_html = "".join([item["caption"] for item in original_captions_with_images])
     content_html = f'<div style="text-align: center; direction: rtl;">{captions_html}</div>' # Center captions
else:
    print("محتوایی برای پردازش یافت نشد.")
    content_html = "<p>محتوایی یافت نشد.</p>" # Placeholder

# ساختار نهایی پست
full_content_parts = []
if thumbnail_html:
    full_content_parts.append(thumbnail_html)
    full_content_parts.append('<br>') # Add space after thumbnail
if content_html:
    # Wrap the main translated content in a div with justify and RTL
    full_content_parts.append(f'<div style="text-align:justify; direction:rtl;">{content_html}</div>')
else:
     full_content_parts.append("<p>خطا: محتوای اصلی یا ترجمه شده یافت نشد.</p>")

# Add source link only if it was valid
if post_link and (post_link.startswith('http://') or post_link.startswith('https://')):
    full_content_parts.append(f'<br><div style="text-align:right; direction:rtl; margin-top:15px; font-size: small;"><a href="{post_link}" target="_blank" rel="noopener noreferrer nofollow">منبع: NewsBTC</a></div>') # Added nofollow

full_content = "".join(full_content_parts)

# نمایش محتوای نهایی قبل از ارسال (برای اشکال‌زدایی)
print("\n--- محتوای نهایی برای ارسال به بلاگر ---")
print(f"عنوان: {translated_title}")
# print(full_content) # Might be too long, print first/last parts
print(full_content[:500] + "..." + full_content[-500:])
print("--- پایان محتوای نهایی ---\n")

# ارسال به بلاگر
print("در حال ارسال پست به بلاگر...")
try:
    post_body = {
        "kind": "blogger#post",
        "blog": {"id": blog_id},
        "title": translated_title,
        "content": full_content
        # Add labels/tags here if needed:
        # "labels": ["خبر", "ارز دیجیتال", "ترجمه"]
    }
    request = service.posts().insert(
        blogId=blog_id,
        body=post_body,
        isDraft=False # تنظیم به True برای تست اولیه بدون انتشار
    )
    response = request.execute()
    print("پست با موفقیت ارسال شد:", response.get("url", "URL نامشخص"))

# Handle potential API errors more specifically
except googleapiclient.errors.HttpError as e:
     error_content = json.loads(e.content.decode('utf-8'))
     error_message = error_content.get('error', {}).get('message', str(e))
     status_code = error_content.get('error', {}).get('code', e.resp.status)
     print(f"خطا در API بلاگر (کد {status_code}): {error_message}")
     # Specific check for auth issues
     if status_code == 401:
         print("خطای 401 (Unauthorized): به نظر می‌رسد اعتبارنامه (Credentials) شما نامعتبر یا منقضی شده است. لطفاً CREDENTIALS را بررسی و به‌روزرسانی کنید.")
     elif status_code == 403:
          print("خطای 403 (Forbidden): دسترسی به بلاگ مورد نظر یا انجام این عملیات مجاز نیست. دسترسی‌های API و مالکیت بلاگ را بررسی کنید.")

except Exception as e:
    print(f"خطای غیرمنتظره در ارسال پست به بلاگر: {e}")

print("اسکریپت به پایان رسید.")
