import json
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import time
import sys

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    driver = webdriver.Chrome(options=chrome_options)
    print("درایور Selenium راه‌اندازی شد.")
    sys.stdout.flush()
    return driver

def scrape_latest_article():
    url = "https://bingx.com/en/news/"
    driver = setup_driver()
    try:
        print(f"در حال باز کردن صفحه: {url}")
        sys.stdout.flush()
        driver.get(url)
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(10)
        
        print("جستجوی مقاله...")
        sys.stdout.flush()
        article = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, "//li[descendant::span[@class='title']]"))
        )
        print("مقاله پیدا شد.")
        sys.stdout.flush()
        
        driver.execute_script("arguments[0].scrollIntoView(true);", article)
        time.sleep(5)
        
        article_html = article.get_attribute('outerHTML')
        print("HTML مقاله برای دیباگ:")
        print(article_html[:1000])
        sys.stdout.flush()
        
        # پیدا کردن لینک مقاله از تگ <a>
        try:
            link_tag = article.find_element(By.TAG_NAME, "a")
            article_url = link_tag.get_attribute("href")
            print(f"لینک مقاله استخراج‌شده: {article_url}")
        except Exception as e:
            article_url = url
            print(f"لینک مقاله پیدا نشد، بازگشت به URL پیش‌فرض: {str(e)}")
        sys.stdout.flush()
        
        with open("debug_news_page.html", "w", encoding="utf-8") as f:
            f.write(BeautifulSoup(driver.page_source, 'html.parser').prettify())
        print("HTML کل صفحه در 'debug_news_page.html' ذخیره شد.")
        sys.stdout.flush()
        
        try:
            img_tag = article.find_element(By.TAG_NAME, "img")
            image_url = img_tag.get_attribute("src") if img_tag else "عکس پیدا نشد"
            print(f"لینک عکس: {image_url}")
        except Exception as e:
            image_url = "عکس پیدا نشد"
            print(f"خطا در پیدا کردن عکس: {str(e)}")
        sys.stdout.flush()
        
        summary_tag = article.find_element(By.CLASS_NAME, "desc")
        summary = summary_tag.text.strip() if summary_tag else "خلاصه پیدا نشد"
        print(f"خلاصه: {summary}")
        sys.stdout.flush()
        
        driver.quit()
        return article_url, image_url, summary
    except Exception as e:
        print(f"خطا در استخراج مقاله جدید: {str(e)}")
        sys.stdout.flush()
        driver.quit()
        return None, None, None

def scrape_full_article(url):
    driver = setup_driver()
    try:
        print(f"در حال باز کردن صفحه: {url}")
        sys.stdout.flush()
        driver.get(url)
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CLASS_NAME, "content"))
        )
        print("تگ content پیدا شد، صفحه باید کامل بارگذاری شده باشد.")
        sys.stdout.flush()
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        with open("debug_article.html", "w", encoding="utf-8") as f:
            f.write(soup.prettify())
        print("HTML صفحه مقاله در 'debug_article.html' ذخیره شد.")
        sys.stdout.flush()
        
        title_tag = soup.find('h1')
        title = title_tag.get_text(strip=True) if title_tag else "بدون عنوان"
        print(f"عنوان مقاله: {title}")
        sys.stdout.flush()
        
        content_div = soup.find('div', class_='content')
        if content_div:
            content = ''
            for tag in content_div.find_all(['p', 'h1', 'h2', 'h3', 'img'], recursive=True):
                if tag.get('class') and any(cls in ['ad', 'footer', 'sidebar', 'related'] for cls in tag.get('class')):
                    continue
                for a_tag in tag.find_all('a'):
                    a_tag.replace_with(a_tag.get_text(strip=True))
                content += str(tag)
            if not content.strip():
                content = "محتوای قابل استخراج پیدا نشد"
            print("محتوای نهایی فقط با تگ‌های اصلی:")
            print(content[:2000])
        else:
            content = "محتوا پیدا نشد"
            print("محتوا پیدا نشد، بخشی از HTML برای دیباگ:")
            print(soup.prettify()[:3000])
        sys.stdout.flush()
        
        driver.quit()
        print("درایور بسته شد.")
        sys.stdout.flush()
        return {'title': title, 'content': content, 'url': url}
    except Exception as e:
        print(f"خطا رخ داد: {str(e)}")
        sys.stdout.flush()
        driver.quit()
        return None

def authenticate_blogger():
    SCOPES = ['https://www.googleapis.com/auth/blogger']
    try:
        creds_json = os.environ.get('BLOGGER_CREDENTIALS')
        if not creds_json:
            raise Exception("متغیر محیطی BLOGGER_CREDENTIALS تنظیم نشده است.")
        
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_authorized_user_info(creds_dict, SCOPES)
        
        if creds and creds.expired and creds.refresh_token:
            print("توکن منقضی شده، در حال رفرش...")
            creds.refresh(Request())
        print("احراز هویت بلاگر با موفقیت انجام شد.")
        sys.stdout.flush()
        return build('blogger', 'v3', credentials=creds)
    except Exception as e:
        print(f"خطا در احراز هویت بلاگر: {str(e)}")
        sys.stdout.flush()
        return None

def post_to_blogger(blog_id, title, content, image_url, article_url, summary):
    service = authenticate_blogger()
    if not service:
        print("ارسال به بلاگر ناموفق بود: مشکل در احراز هویت.")
        sys.stdout.flush()
        return
    try:
        print(f"Blog ID استفاده‌شده: {blog_id}")
        sys.stdout.flush()
        posts = service.posts()
        full_content = f"<p>{summary}</p><!--more-->"
        if image_url != "عکس پیدا نشد":
            full_content += f'<img src="{image_url}" alt="{title}" style="max-width:100%;width:740px;height:auto;display:block;margin:0 auto;" /><br>'
        full_content += content
        full_content += f'<p>منبع: <a href="{article_url}" target="_blank">BingX</a></p>'
        
        body = {"kind": "blogger#post", "title": title, "content": full_content}
        print("در حال ارسال به بلاگر...")
        sys.stdout.flush()
        response = posts.insert(blogId=blog_id, body=body, isDraft=False).execute()
        print(f"پست با عنوان '{title}' با موفقیت ارسال شد. ID پست: {response['id']}")
        sys.stdout.flush()
    except Exception as e:
        print(f"خطا در ارسال به بلاگر: {str(e)}")
        sys.stdout.flush()

def main():
    print("شروع فرآیند...")
    sys.stdout.flush()
    article_url, image_url, summary = scrape_latest_article()
    if article_url:
        print(f"لینک مقاله استخراج‌شده: {article_url}")
        sys.stdout.flush()
        article = scrape_full_article(article_url)
        if article:
            blog_id = os.environ.get('BLOG_ID', "764765195397447456")
            post_to_blogger(blog_id, article['title'], article['content'], image_url, article['url'], summary)
        else:
            print("استخراج محتوای کامل مقاله ناموفق بود.")
            sys.stdout.flush()
    else:
        print("استخراج مقاله اولیه ناموفق بود.")
        sys.stdout.flush()

if __name__ == "__main__":
    main()
