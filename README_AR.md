# بوت عروض مصر — V1

بوت Telegram يجمع العروض من عدة متاجر مصرية، يحفظ تاريخ السعر في SQLite،
يمنع تكرار نفس العرض، ويرتب العروض قبل نشرها تلقائياً.

## المتاجر الموجودة في الهيكل

- Jumia Egypt
- B.TECH
- 2B
- Raya Shop
- Carrefour Egypt
- Dream 2000
- Amazon Egypt
- Noon Egypt
- Raneen

> Amazon / Noon / Raneen موجودون في المشروع كـ connectors مستقلة، لكن تم ضبطهم
> على fail-safe حتى لا نحاول تجاوز CAPTCHA أو أنظمة منع البوتات.
> في الإنتاج نستخدم API رسمي/affiliate إن توفر، أو Browser automation فقط على
> الصفحات العامة المسموح بها.

## 1) إنشاء البوت

من Telegram افتح @BotFather:
1. /newbot
2. اختر الاسم والـ username
3. احتفظ بالـ Token عندك ولا تنشره.

أنشئ قناة Telegram ثم أضف البوت Admin بصلاحية Post Messages.

## 2) الإعداد

انسخ:
    .env.example
إلى:
    .env

وضع القيم:
    TELEGRAM_BOT_TOKEN=...
    TELEGRAM_CHANNEL_ID=@channel_name

لا ترسل التوكن لأي شخص ولا ترفعه على GitHub.

## 3) التثبيت

### Windows / Linux / VPS / Termux
    python -m venv .venv

Linux/Termux:
    source .venv/bin/activate

Windows:
    .venv\Scripts\activate

ثم:
    pip install -r requirements.txt

## 4) اختبار المتاجر بدون نشر

    python test_once.py

## 5) تشغيل البوت

    python app.py

كل 20 دقيقة افتراضياً سيعمل Scan جديد.

## الفلاتر

في `.env`:
- CHECK_INTERVAL_MINUTES=20
- MIN_DISCOUNT_PERCENT=15
- MIN_SAVING_EGP=100
- MAX_POSTS_PER_CYCLE=25

## قاعدة البيانات

الملف `deals.db` يُنشأ تلقائياً، وفيه:
- المنتجات
- تاريخ كل سعر
- العروض التي تم نشرها

العرض لا يُعاد نشره إلا إذا تحسن السعر أو زادت نسبة الخصم بشكل واضح.

## الخطوة التالية للإنتاج

1. تثبيت selectors الخاصة بكل متجر بعد اختبار HTML الحقيقي من نفس السيرفر.
2. إضافة Playwright fallback للمتاجر الديناميكية المسموح بها.
3. إضافة affiliate links.
4. مطابقة نفس المنتج بين المتاجر (SKU / EAN / model normalization).
5. لوحة Admin Web صغيرة.
6. Docker + PostgreSQL للنشر الدائم.
