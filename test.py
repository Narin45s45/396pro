# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
import sys

# تابع پراکسی که در کد اصلی قرار دادیم
def replace_filtered_images_with_proxy(content_html):
    if not content_html:
        return ""
    print(">>> بررسی و بازنویسی آدرس عکس‌های فیلتر شده با پراکسی...")
    sys.stdout.flush()
    soup = BeautifulSoup(content_html, "html.parser")
    images = soup.find_all("img")
    modified_flag = False
    processed_count = 0
    found_filtered_domains_count = 0
    filtered_domains_for_content = ["twimg.com", "i0.wp.com", "i1.wp.com", "i2.wp.com", "pbs.twimg.com"]
    
    for i, img_tag in enumerate(images):
        img_src = img_tag.get("src", "")
        if not img_src or not img_src.startswith(('http://', 'https://')):
            continue
        is_on_filtered_domain = any(domain_part in img_src for domain_part in filtered_domains_for_content)
        if is_on_filtered_domain:
            found_filtered_domains_count += 1
            print(f"--- عکس محتوا {i+1} از دامنه فیلتر شده ({img_src[:70]}...) در حال بازنویسی با پراکسی...")
            sys.stdout.flush()
            proxied_url = f"https://wsrv.nl/?url={img_src}"
            img_tag['src'] = proxied_url
            if not img_tag.get('alt'):
                img_tag['alt'] = "تصویر پراکسی شده از محتوا"
            modified_flag = True
            processed_count += 1
            
    print(f"<<< بازنویسی آدرس‌ها تمام شد. {processed_count}/{found_filtered_domains_count} عکس با موفقیت پراکسی شد.")
    sys.stdout.flush()
    return str(soup) if modified_flag else content_html

# --- بخش تست ---
if __name__ == "__main__":
    # 1. یک نمونه کد HTML با دو عکس ایجاد می‌کنیم
    #    - یکی از یک دامنه عادی (که نباید تغییر کند)
    #    - یکی از دامنه توییتر (که باید آدرسش پراکسی شود)
    sample_html_content = """
    <h2>این یک پست آزمایشی است</h2>
    <p>این یک عکس عادی است که نباید تغییر کند:</p>
    <img src="https://example.com/images/normal_photo.jpg" alt="عکس عادی">
    <hr>
    <p>و این یک عکس از توییتر است که فیلتر شده و باید پراکسی شود:</p>
    <img src="https://pbs.twimg.com/media/F8fX-b_XgAAg3Et.jpg" alt="عکس توییتری">
    """

    print("="*60)
    print("محتوای HTML اولیه:")
    print("="*60)
    print(sample_html_content)
    
    # 2. تابع را با محتوای نمونه فراخوانی می‌کنیم
    processed_html = replace_filtered_images_with_proxy(sample_html_content)

    print("\n" + "="*60)
    print("محتوای HTML نهایی پس از پردازش:")
    print("="*60)
    print(processed_html)
