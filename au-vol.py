import os
import requests
import feedparser
import google.generativeai as genai

# --- بخش ۱: بارگذاری تنظیمات ---
def load_config():
    config = {
        'wp_url': os.getenv('WP_URL'),
        'wp_user': os.getenv('WP_USER'),
        'wp_password': os.getenv('WP_PASSWORD'),
        'gemini_api_key': os.getenv('GEMINI_API_KEY'),
        'rss_url': os.getenv('RSS_URL'),
        'post_status': os.getenv('POST_STATUS', 'draft'), # پیش‌نویس برای تست امن‌تر است
    }
    for key, value in config.items():
        if not value:
            raise ValueError(f"خطا: متغیر محیطی {key} تعریف نشده است.")
    return config

# --- بخش ۲: مدیریت آیتم‌های تکراری ---
PROCESSED_ITEMS_FILE = 'processed_items.txt'

def get_processed_items():
    if not os.path.exists(PROCESSED_ITEMS_FILE):
        return set()
    with open(PROCESSED_ITEMS_FILE, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f)

def save_processed_item(item_link):
    with open(PROCESSED_ITEMS_FILE, 'a', encoding='utf-8') as f:
        f.write(item_link + '\n')

# --- بخش ۳: ترجمه ساده با Gemini ---
def translate_content_with_gemini(api_key, title, html_content):
    print(f"  -> Translating: {title}")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    
    prompt = f"""
    Translate the following HTML content and its title to fluent Persian.
    Preserve the original HTML structure, including all tags like <iframe>, <p>, <img>, and <a>, as much as possible.
    Only provide the translated version of the title and the content. Do not add any extra explanations.
    Return the output ONLY in JSON format with two keys: "translated_title" and "translated_content".

    Original Title:
    {title}

    Original HTML Content:
    {html_content}
    """
    try:
        response = model.generate_content(prompt)
        # The response should be a JSON string, so we directly try to load it.
        return response.json()
    except Exception as e:
        print(f"  [Error] Gemini API call failed or returned invalid JSON: {e}")
        # Fallback for non-JSON responses
        try:
            cleaned_response = response.text.strip().replace('```json', '').replace('```', '')
            return json.loads(cleaned_response)
        except Exception as json_e:
            print(f"  [Error] Could not parse Gemini response as JSON: {json_e}")
            return None


# --- بخش ۴: مدیریت وردپرس ---
def get_or_create_category_id(config, auth):
    cat_api_url = f"{config['wp_url']}/wp-json/wp/v2/categories"
    cat_slug = 'game'
    
    try:
        response = requests.get(cat_api_url, params={'slug': cat_slug}, auth=auth)
        response.raise_for_status()
        data = response.json()
        if data:
            return data[0]['id']
    except requests.exceptions.RequestException:
        pass # Ignore error and proceed to create

    print(f"  [Info] Category '{cat_slug}' not found. Creating it...")
    try:
        response = requests.post(cat_api_url, auth=auth, json={'name': 'بازی', 'slug': cat_slug})
        response.raise_for_status()
        return response.json()['id']
    except requests.exceptions.RequestException as e:
        print(f"  [Error] Failed to create category: {e}")
        return None

def post_to_wordpress(config, auth, data, category_id):
    api_url = f"{config['wp_url']}/wp-json/wp/v2/posts"
    
    post_data = {
        'title': data['translated_title'],
        'content': data['translated_content'], # ارسال مستقیم HTML ترجمه شده
        'status': config['post_status'],
        'categories': [category_id]
    }
    
    headers = {'Content-Type': 'application/json'}
    
    try:
        response = requests.post(api_url, auth=auth, headers=headers, json=post_data, timeout=30)
        response.raise_for_status()
        print(f"  [Success] Post '{data['translated_title']}' created successfully.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"  [Error] Failed to post to WordPress: {e}")
        if e.response: print(f"  Response Body: {e.response.text}")
        return False

# --- بخش ۵: منطق اصلی برنامه ---
def main():
    try:
        config = load_config()
    except ValueError as e:
        print(e)
        return

    print("--- Starting Simple Feed Translator Script ---")
    
    auth = (config['wp_user'], config['wp_password'])
    game_category_id = get_or_create_category_id(config, auth)
    if not game_category_id:
        print("[Fatal] Could not secure 'game' category ID. Aborting.")
        return

    processed_items = get_processed_items()
    
    print(f"Fetching RSS feed from: {config['rss_url']}")
    feed = feedparser.parse(config['rss_url'])

    if feed.bozo:
        print(f"Error reading RSS feed: {feed.bozo_exception}")
        return
        
    for entry in reversed(feed.entries):
        item_link = entry.get('link')
        item_title = entry.get('title', 'No Title')
        
        if not item_link or item_link in processed_items:
            continue
            
        print(f"\nProcessing new item: {item_title}")
        
        # پیدا کردن کامل‌ترین محتوای موجود در فید
        content = ""
        if 'content' in entry:
            content = entry.content[0].value
        elif 'summary' in entry:
            content = entry.summary
        
        if not content:
            print("  [Warning] No content found in feed item. Skipping.")
            save_processed_item(item_link)
            continue

        # ترجمه محتوای خام
        translated_data = translate_content_with_gemini(config['gemini_api_key'], item_title, content)
        if not translated_data:
            save_processed_item(item_link)
            continue
            
        # انتشار در وردپرس
        if post_to_wordpress(config, auth, translated_data, game_category_id):
            save_processed_item(item_link)

    print("\n--- Script finished. ---")

if __name__ == "__main__":
    main()
