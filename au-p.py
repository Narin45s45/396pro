# --- تابع ترجمه با Gemini (بدون تغییر زیاد، فقط لاگ) ---
def translate_with_gemini(text, target_lang="fa"):
    print(f">>> شروع ترجمه متن با Gemini (طول متن: {len(text)} کاراکتر)...")
    sys.stdout.flush()
    if not text or text.isspace():
        print("--- متن ورودی برای ترجمه خالی است. رد شدن از ترجمه.")
        sys.stdout.flush()
        return ""

    headers = {"Content-Type": "application/json"}
    prompt = (
        f"Please translate the following English text (which might contain HTML tags AND special placeholders like ##IMG_PLACEHOLDER_...##) into {target_lang} "
        f"with the utmost intelligence and precision. Pay close attention to context and nuance.\n"
        f"IMPORTANT TRANSLATION RULES:\n"
        f"1. Translate ALL text content, including text inside HTML tags like <p>, <li>, <blockquote>, <a>, etc. Do not skip any content.\n"
        f"2. !!! IMPORTANT: Preserve the image placeholders (e.g., ##IMG_PLACEHOLDER_uuid##) EXACTLY as they appear in the original text. DO NOT translate them, modify them, or add/remove spaces around them. They must remain identical.\n"
        f"3. For technical terms or English words commonly used in the field (like Bitcoin, Ethereum, NFT, Blockchain, Stochastic Oscillator, MACD, RSI, AI, API), "
        f"transliterate them into Persian script (Finglish) instead of translating them into a potentially obscure Persian word. "
        f"Example: 'Stochastic Oscillator' should become 'اوسیلاتور استوکستیک'. Apply consistently.\n"
        f"4. Ensure that any text within quotation marks (\"\") is also accurately translated.\n"
        f"5. Preserve the original HTML structure (tags and attributes) as much as possible, only translating the text content within the tags and relevant attributes like 'alt' or 'title'.\n"
        f"6. Rewrite the translated text in colloquial and common Persian (فارسی عامیانه و رایج).\n"
        f"OUTPUT REQUIREMENT: Only return the final, high-quality translated text with its original HTML structure AND the preserved placeholders. Do not add any explanations, comments, apologies, or options. Provide only the single best translation.\n\n"
        f"English Text with HTML and Placeholders to Translate:\n{text}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.5, "topP": 0.95, "topK": 40}
    }
    max_retries = 2  # خط ۱۳۴: حالا با ۴ فاصله تنظیم شده
    retry_delay = 15

    for attempt in range(max_retries + 1):
        print(f"--- تلاش {attempt + 1}/{max_retries + 1} برای تماس با API Gemini...")
        sys.stdout.flush()
        try:
            response = requests.post(
                f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
                headers=headers,
                json=payload,
                timeout=GEMINI_TIMEOUT  # Timeout بیشتر
            )
            print(f"--- پاسخ اولیه از Gemini دریافت شد (کد وضعیت: {response.status_code})")
            sys.stdout.flush()

            if response.status_code == 429 and attempt < max_retries:
                print(f"!!! خطای Rate Limit (429) از Gemini. منتظر ماندن برای {retry_delay} ثانیه...")
                sys.stdout.flush()
                time.sleep(retry_delay)
                retry_delay *= 1.5
                continue

            response.raise_for_status()

            print("--- در حال پردازش پاسخ JSON از Gemini...")
            sys.stdout.flush()
            result = response.json()

            # ... (بقیه بررسی‌های پاسخ Gemini مانند قبل) ...
            if not result or "candidates" not in result or not result["candidates"]:
                feedback = result.get("promptFeedback", {})
                block_reason = feedback.get("blockReason")
                if block_reason:
                    print(f"!!! Gemini درخواست را مسدود کرد: {blockReason}")
                    sys.stdout.flush()
                    raise ValueError(f"ترجمه توسط Gemini مسدود شد: {block_reason}")
                else:
                    print(f"!!! پاسخ غیرمنتظره از API Gemini (ساختار نامعتبر candidates): {result}")
                    sys.stdout.flush()
                    raise ValueError("پاسخ غیرمنتظره از API Gemini (ساختار نامعتبر candidates)")

            candidate = result["candidates"][0]
            if "content" not in candidate or "parts" not in candidate["content"] or not candidate["content"]["parts"]:
                finish_reason = candidate.get("finishReason", "نامشخص")
                if finish_reason != "STOP":
                    print(f"!!! Gemini ترجمه را کامل نکرد: دلیل پایان = {finish_reason}")
                    sys.stdout.flush()
                    partial_text = candidate.get("content", {}).get("parts", [{}])[0].get("text")
                    if partial_text:
                        print("--- هشدار: ممکن است ترجمه ناقص باشد.")
                        sys.stdout.flush()
                        return partial_text.strip()
                    raise ValueError(f"ترجمه ناقص از Gemini دریافت شد (دلیل: {finish_reason})")
                else:
                    print(f"!!! پاسخ غیرمنتظره از API Gemini (ساختار نامعتبر content/parts): {candidate}")
                    sys.stdout.flush()
                    raise ValueError("پاسخ غیرمنتظره از API Gemini (ساختار نامعتبر content/parts)")

            if "text" not in candidate["content"]["parts"][0]:
                print(f"!!! پاسخ غیرمنتظره از API Gemini (بدون text در part): {candidate}")
                sys.stdout.flush()
                raise ValueError("پاسخ غیرمنتظره از API Gemini (بدون text در part)")

            translated_text = candidate["content"]["parts"][0]["text"]
            print("<<< ترجمه متن با Gemini با موفقیت انجام شد.")
            sys.stdout.flush()
            translated_text = re.sub(r'^```html\s*', '', translated_text, flags=re.IGNORECASE)
            translated_text = re.sub(r'\s*```$', '', translated_text)
            return translated_text.strip()

        except requests.exceptions.Timeout:
            print(f"!!! خطا: درخواست به API Gemini زمان‌بر شد (Timeout پس از {GEMINI_TIMEOUT} ثانیه).")
            sys.stdout.flush()
            if attempt >= max_retries:
                print("!!! تلاش‌های مکرر برای Gemini ناموفق بود (Timeout).")
                sys.stdout.flush()
                raise ValueError(f"API Gemini پس از چند بار تلاش پاسخ نداد (Timeout در تلاش {attempt+1}).")
            print(f"--- منتظر ماندن برای {retry_delay} ثانیه قبل از تلاش مجدد...")
            sys.stdout.flush()
            time.sleep(retry_delay)
            retry_delay *= 1.5
        except requests.exceptions.RequestException as e:
            print(f"!!! خطا در درخواست به API Gemini: {e}")
            sys.stdout.flush()
            if attempt >= max_retries:
                print("!!! تلاش‌های مکرر برای Gemini ناموفق بود (خطای شبکه).")
                sys.stdout.flush()
                raise ValueError(f"خطا در درخواست API Gemini پس از چند بار تلاش: {e}")
            print(f"--- منتظر ماندن برای {retry_delay} ثانیه قبل از تلاش مجدد...")
            sys.stdout.flush()
            time.sleep(retry_delay)
            retry_delay *= 1.5
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            print(f"!!! خطا در پردازش پاسخ Gemini یا خطای داده: {e}")
            sys.stdout.flush()
            raise
        except Exception as e:
            print(f"!!! خطای پیش‌بینی نشده در تابع ترجمه: {e}")
            sys.stdout.flush()
            raise

    print("!!! ترجمه با Gemini پس از تمام تلاش‌ها ناموفق بود.")
    sys.stdout.flush()
    raise ValueError("ترجمه با Gemini پس از تمام تلاش‌ها ناموفق بود.")
