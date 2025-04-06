import feedparser
import os
import json
import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import re
from bs4 import BeautifulSoup
import time
import base64

# تنظیمات
RSS_FEED_URL = "https://www.newsbtc.com/feed/"
GEMINI_API_KEY = os.environ.get("GEMAPI")
if not GEMINI_API_KEY:
    raise ValueError("GEMAPI پیدا نشد!")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
creds_json = os.environ.get("CREDENTIALS")
if not creds_json:
    raise ValueError("CREDENTIALS پیدا نشد!")
creds = Credentials.from_authorized_user_info(json.loads(creds_json))
service = build("blogger", "v3", credentials=creds)
blog_id = "764765195397447456"

# تابع ترجمه با Gemini
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
    max_retries = 2
    retry_delay = 5
    for attempt in range(max_retries + 1):
        response = requests.post(f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", headers=headers, json=payload)
        if response.status_code == 200:
            break
        elif response.status_code == 429 and attempt < max_retries:
            print(f"خطای Rate Limit (429). منتظر ماندن برای {retry_delay} ثانیه...")
            time.sleep(retry_delay)
        else:
            raise ValueError(f"خطا در درخواست API: کد وضعیت {response.status_code}, پاسخ: {response.text}")
    result = response.json()
    if 'error' in result:
        raise ValueError(f"خطا در API Gemini: {result['error'].get('message', 'جزئیات نامشخص')}")
    translated_text = result["candidates"][0]["content"]["parts"][0]["text"]
    return translated_text.strip()

# تابع حذف لینک‌های newsbtc
def remove_newsbtc_links(text):
    pattern = r'<a\s+[^>]*href=["\']https?://(www\.)?newsbtc\.com[^"\']*["\'][^>]*>(.*?)</a>'
    return re.sub(pattern, r'\2', text, flags=re.IGNORECASE)

# تابع آپلود عکس به بلاگر و برگرداندن URL
def upload_image_to_blogger(image_url):
    try:
        response = requests.get(image_url, stream=True)
        response.raise_for_status()
        image_content = response.content
        image_name = image_url.split('/')[-1]
        
        # بلاگر API مستقیم برای آپلود عکس نداره، پس از base64 توی محتوا استفاده می‌کنیم
        base64_image = base64.b64encode(image_content).decode('utf-8')
        uploaded_html = f'<img src="data:image/jpeg;base64,{base64_image}" alt="{image_name}" style="max-width:100%; height:auto;">'
        
        # تست آپلود توی پست موقت برای گرفتن URL واقعی (اختیاری)
        temp_post = {
            "kind": "blogger#post",
            "blog": {"id": blog_id},
            "title": "Temporary Image Upload",
            "content": uploaded_html
        }
        request = service.posts().insert(blogId=blog_id, body=temp_post, isDraft=True)
        temp_response = request.execute()
        
        soup = BeautifulSoup(temp_response['content'], "html.parser")
        uploaded_url = soup.find("img")["src"]
        
        service.posts().delete(blogId=blog_id, postId=temp_response['id']).execute()
        
        print(f"عکس {image_url} به {uploaded_url} آپلود شد.")
        return uploaded_url
    except Exception as e:
        print(f"خطا در آپلود عکس {image_url}: {e}")
        return image_url

# تابع جایگزینی URLهای twimg.com
def replace_twimg_urls(content):
    soup = BeautifulSoup(content, "html.parser")
    images = soup.find_all("img")
    for img in images:
        src = img.get("src", "")
        print(f"بررسی عکس: {src}")
        if "twimg.com" in src:
            new_url = upload_image_to_blogger(src)
            print(f"جایگزینی {src} با {new_url}")
            img["src"] = new_url
    return str(soup)

# تابع کرال کردن کپشن‌ها
def crawl_captions(post_url):
    try:
        response = requests.get(post_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        captions_with_images = []

        figures = soup.find_all("figure")
        for figure in figures:
            img = figure.find("img")
            caption = figure.find("figcaption", class_="wp-caption-text")
            if img and caption:
                captions_with_images.append({"image_url": img.get("src"), "caption": str(caption)})

        centered_elements = soup.find_all(["pre", "p"], style="text-align: center")
        for elem in centered_elements:
            prev_sibling = elem.find_previous("img")
            if prev_sibling:
                captions_with_images.append({"image_url": prev_sibling.get("src"), "caption": str(elem)})

        print("کپشن‌های کرال‌شده:")
        for i, item in enumerate(captions_with_images, 1):
            print(f"کپشن {i}: {item['caption']} (عکس: {item['image_url']})")
        return captions_with_images
    except Exception as e:
        print(f"خطا در کرال کردن {post_url}: {e}")
        return []

# تابع اضافه کردن کپشن‌ها (وسط‌چین)
def add_captions_to_images(content, captions_with_images):
    if not captions_with_images:
        print("هیچ کپشنی وجود ندارد.")
        return content
    soup = BeautifulSoup(content, "html.parser")
    images = soup.find_all("img")
    print(f"تعداد عکس‌ها در محتوا: {len(images)}")
    used_captions = set()

    for img in images:
        img_url = img.get("src")
        matching_caption = next((item["caption"] for item in captions_with_images if item["image_url"] in img_url), None)
        if matching_caption and matching_caption not in used_captions:
            parent = img.parent
            if parent.name != "figure":
                figure = soup.new_tag("figure")
                figure["style"] = "text-align: center;"
                img.wrap(figure)
                parent = img.parent
            caption_tag = BeautifulSoup(matching_caption, "html.parser")
            parent.append(caption_tag)
            used_captions.add(matching_caption)
            print(f"کپشن وسط‌چین به {img_url}: {matching_caption}")

    remaining_captions = [item["caption"] for item in captions_with_images if item["caption"] not in used_captions]
    if remaining_captions:
        print("کپشن‌های اضافی:")
        for caption in remaining_captions:
            print(caption)
        soup.append(BeautifulSoup(f'<div style="text-align: center;">{"".join(remaining_captions)}</div>', "html.parser"))

    return str(soup)

# پردازش RSS
print("دریافت فید RSS...")
feed = feedparser.parse(RSS_FEED_URL)
if not feed.entries:
    print("پستی یافت نشد.")
    exit()

latest_post = feed.entries[0]
print(f"پست جدید: '{latest_post.title}'")

# کرال کپشن‌ها
post_link = getattr(latest_post, 'link', None)
captions_with_images = crawl_captions(post_link) if post_link and post_link.startswith('http') else []

# ترجمه عنوان
print("ترجمه عنوان...")
try:
    translated_title = translate_with_gemini(latest_post.title).splitlines()[0]
    print(f"عنوان: {translated_title}")
except Exception as e:
    print(f"خطا در ترجمه عنوان: {e}")
    translated_title = latest_post.title

# عکس پوستر
thumbnail = ""
if hasattr(latest_post, 'media_content') and latest_post.media_content:
    thumbnail_url = latest_post.media_content[0].get('url', '')
    if thumbnail_url.startswith('http'):
        if "twimg.com" in thumbnail_url:
            thumbnail_url = upload_image_to_blogger(thumbnail_url)
        thumbnail = f'<div style="text-align:center;"><img src="{thumbnail_url}" alt="{translated_title}" style="max-width:100%; height:auto;"></div>'
    print(f"عکس پوستر: {thumbnail_url}")

# پردازش محتوا
print("پردازش محتوا...")
content_source = latest_post.content[0]['value'] if 'content' in latest_post else latest_post.summary if 'summary' in latest_post else ""
if content_source:
    content_cleaned = re.split(r'Related Reading|Read Also|See Also', content_source, flags=re.IGNORECASE)[0].strip()
    content_cleaned = remove_newsbtc_links(content_cleaned)
    content_with_captions = add_captions_to_images(content_cleaned, captions_with_images)
    content_with_uploaded_images = replace_twimg_urls(content_with_captions)
    
    print("ترجمه محتوا...")
    try:
        translated_html_content = translate_with_gemini(content_with_uploaded_images)
        content_html = re.sub(
            r'<img\s+', 
            '<img style="display:block;margin-left:auto;margin-right:auto;max-width:100%;height:auto;" ',
            translated_html_content,
            flags=re.IGNORECASE
        )
        print("ترجمه انجام شد.")
    except Exception as e:
        print(f"خطا در ترجمه: {e}")
        content_html = f"<p><i>[خطا در ترجمه]</i></p><div style='text-align:left; direction:ltr;'>{content_with_uploaded_images}</div>"
else:
    print("محتوایی یافت نشد.")
    content_html = "\n".join([item["caption"] for item in captions_with_images]) if captions_with_images else ""

# ساختار پست
full_content_parts = []
if thumbnail:
    full_content_parts.append(thumbnail)
    full_content_parts.append('<br>')
if content_html:
    full_content_parts.append(f'<div style="text-align:justify;direction:rtl;">{content_html}</div>')
if post_link:
    full_content_parts.append(f'<div style="text-align:right;direction:rtl;margin-top:15px;"><a href="{post_link}" target="_blank" rel="noopener noreferrer">منبع</a></div>')

full_content = "".join(full_content_parts)

# ارسال به بلاگر
print("ارسال به بلاگر...")
try:
    request = service.posts().insert(blogId=blog_id, body={"kind": "blogger#post", "blog": {"id": blog_id}, "title": translated_title, "content": full_content}, isDraft=False)
    response = request.execute()
    print("پست ارسال شد:", response.get("url", "URL نامشخص"))
except Exception as e:
    print(f"خطا در ارسال: {e}")
