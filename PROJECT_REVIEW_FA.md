# گزارش بررسی پروژه ALOO PANEL

تاریخ بررسی: 2026-09-26

## خلاصه اجرایی

این پروژه یک پنل مدیریتی فارسی/انگلیسی برای مدیریت سرویس‌های پروکسی مبتنی بر VLESS/VMess و Xray است. پنل با FastAPI نوشته شده و امکاناتی مثل موارد زیر دارد:

- مدیریت کاربران و inboundها
- ساخت لینک‌های VLESS/VMess، Clash و Sing-Box
- مدیریت چند سرور و load balancing
- گزارش مصرف ترافیک و مانیتورینگ CPU/RAM/Disk
- احراز هویت، نقش‌ها، RBAC و TOTP/2FA
- توکن‌های API و audit log
- اتصال ربات تلگرام و shop/top-up
- backup/restore و حالت maintenance
- اجرای Xray و reverse proxy با Nginx
- استقرار با Docker، Railway و Render

هسته برنامه عمدتاً در `main.py` قرار دارد و حدود ۴۵۰۰ خط است. لایه ذخیره‌سازی یک فایل JSON به‌همراه قفل async و atomic write است.

## وضعیت تست و سلامت پایه

- `compileall`: موفق
- تست‌های پروژه با Python محیط مجازی پروژه: **۸۰ تست موفق**
- اجرای `pytest` با Python عمومی محیط فعلی ممکن نشد، چون `pytest` در آن محیط نصب نیست؛ اما `.venv\\Scripts\\python.exe -m pytest -q` با موفقیت اجرا شد.

پاس شدن تست‌ها نشان می‌دهد مسیرهای اصلی CRUD، احراز هویت پایه، API سرورها، migration، مانیتورینگ و چند قابلیت Xray کار می‌کنند؛ بااین‌حال تست‌ها پوشش کافی برای امنیت، هم‌زمانی، deployment و خرابی داده ندارند.

## ایرادهای بحرانی و مهم

### 1. وجود داده حساس واقعی در workspace
**شدت: بحرانی**

فایل‌های زیر در پروژه وجود دارند:

- `data/db.json`
- `data/backups/aloo-backup-20260919-182839.json`

ساختار storage نشان می‌دهد این داده‌ها می‌توانند شامل هش و salt مدیر، `secret_key` نشست، توکن ربات تلگرام و سایر تنظیمات حساس باشند (`storage.py:37-65`). حتی اگر `data/` در `.gitignore` باشد، وجود فایل در workspace خطر commit یا انتشار اشتباهی را باقی می‌گذارد.

**اثر:** در صورت انتشار `secret_key`، امکان جعل cookie نشست وجود دارد؛ انتشار backup نیز می‌تواند اطلاعات کاربران، تنظیمات و credentialهای integration را افشا کند.

**اقدام پیشنهادی:**

1. فایل‌های داده و backup را از هر repository/آرشیو قابل انتشار حذف کنید.
2. `secret_key` را rotate کنید.
3. توکن تلگرام و credentialهای موجود را revoke و دوباره تولید کنید.
4. مطمئن شوید backupها خارج از مسیر source code نگهداری می‌شوند.

### 2. تشخیص HTTPS در cookie پشت Nginx شکننده است
**شدت: مهم امنیتی**

در `main.py:388-400`، ویژگی `Secure` کوکی بر اساس `request.url.scheme` تعیین می‌شود. Nginx هدر `X-Forwarded-Proto: https` را ارسال می‌کند (`nginx.conf:60-66`)، اما اجرای Uvicorn در `main.py:4484-4487` با `--proxy-headers` انجام نمی‌شود.

در این وضعیت، برنامه ممکن است درخواست public HTTPS را داخل backend به‌صورت HTTP ببیند و کوکی نشست را بدون `Secure` ارسال کند.

**اثر:** کوکی در صورت وجود مسیر HTTP یا اشتباه proxy می‌تواند در معرض ارسال ناامن قرار گیرد.

**اقدام پیشنهادی:** یا Uvicorn را با proxy headers قابل اعتماد اجرا کنید، یا scheme را به‌صورت صریح و امن از reverse proxy مدیریت کنید؛ همچنین در deployment واقعی HTTPS را اجباری کنید.

### 3. لینک‌های تولیدشده در اجرای محلی همیشه HTTPS هستند
**شدت: باگ عملکردی**

تابع `get_scheme` در `main.py:421-423` بدون توجه به درخواست همیشه مقدار `https` برمی‌گرداند.

درحالی‌که README اجرای محلی را با `http://localhost:10000` اعلام می‌کند (`README.md:15-22`)، لینک‌های subscription و config در اجرای مستقیم محلی با `https://` ساخته می‌شوند (`main.py:463-464` و مسیرهای subscription).

**اثر:** لینک‌های محلی معمولاً باز نمی‌شوند یا کلاینت با خطای TLS مواجه می‌شود.

**اقدام پیشنهادی:** در حالت local از scheme واقعی درخواست استفاده شود و در deployment پشت proxy از `X-Forwarded-Proto` معتبر استفاده شود.

### 4. محدود بودن validation در restore backup
**شدت: مهم عملکردی/امنیتی**

در `main.py:2516-2547` برای restore فقط بررسی می‌شود که backup یک dictionary باشد و `inbounds` آن list باشد. سپس کل DB با `db.clear(); db.update(snap)` جایگزین می‌شود.

**اثر:** یک backup ناقص یا دستکاری‌شده می‌تواند کلیدهای ضروری مانند `settings`، `stats`، `admins`، `plans` یا ساختارهای دیگر را حذف کند و باعث خرابی runtime یا رفتار غیرقابل پیش‌بینی شود. حفظ `secret_key` به‌تنهایی این مشکل را حل نمی‌کند.

**اقدام پیشنهادی:** schema validation کامل، بررسی نوع و محدوده فیلدها، merge با `DEFAULT_DB`، migration بعد از restore و ایجاد snapshot اضطراری قبل از جایگزینی.

### 5. endpoint مربوط به 2FA، IP داخل challenge را بررسی نمی‌کند
**شدت: مهم امنیتی**

در login دو مرحله‌ای، challenge شامل IP است (`main.py:1180-1184`)، اما در `/api/2fa/login` مقدار `data["ip"]` با IP فعلی مقایسه نمی‌شود (`main.py:1196-1217`).

**اثر:** اگر challenge موقت افشا شود، از IP دیگری نیز قابل استفاده است. این موضوع سطح اتصال challenge به نشست login را کاهش می‌دهد.

**اقدام پیشنهادی:** IP یا بهتر از آن یک nonce/flow state یک‌بارمصرف را باطل‌شونده و محدود به همان login نگه دارید؛ در صورت اتکا به IP، آن را با ملاحظات proxy و NAT پیاده کنید.

### 6. احتمال ثبت چند مدیر در setup هم‌زمان
**شدت: مهم هم‌زمانی**

در `main.py:1106-1142` ابتدا بیرون از mutate بررسی می‌شود که `db["admin"]` وجود نداشته باشد، سپس در mutate مدیر ساخته می‌شود. این بررسی داخل همان قفل/تابع mutation تکرار نشده است.

**اثر:** دو درخواست هم‌زمان در اولین راه‌اندازی می‌توانند هر دو از check عبور کنند و وضعیت adminها را به‌صورت رقابتی تغییر دهند.

**اقدام پیشنهادی:** check و create را در یک عملیات atomic داخل `store.mutate` انجام دهید و اگر admin ایجاد شده بود، خطای `already-configured` برگردانید.

## ایرادهای مهم عملیاتی و نگهداری

### 7. دریافت Xray با `latest` بدون pin و checksum
**شدت: مهم supply-chain**

در `Dockerfile:36-42` آخرین release از GitHub دانلود می‌شود:

- نسخه مشخصی pin نشده است.
- checksum یا امضای artifact بررسی نمی‌شود.

**اثر:** buildها reproducible نیستند و تغییر ناخواسته یا compromise در artifact می‌تواند وارد image شود.

**اقدام پیشنهادی:** نسخه دقیق، URL نسخه‌دار و SHA-256 یا signature verification استفاده شود.

### 8. اجرای container با کاربر root
**شدت: مهم امنیتی**

در Dockerfile هیچ `USER` غیر root تعریف نشده و `entrypoint.sh` برنامه را با همان user اجرا می‌کند (`entrypoint.sh:32-33`).

**اثر:** در صورت compromise شدن برنامه یا dependency، سطح دسترسی مهاجم در container بیش از حد لازم خواهد بود.

**اقدام پیشنهادی:** user غیر root بسازید، دسترسی نوشتن را فقط به `/app/data` و مسیرهای لازم محدود کنید و مسیرهای log/run را با مالکیت مناسب تنظیم کنید.

### 9. توکن تلگرام به‌صورت plaintext در DB ذخیره می‌شود
**شدت: مهم امنیتی**

توکن در settings با کلید `telegram_bot_token` نگهداری می‌شود (`storage.py:59-63`) و عملیات save نیز آن را در DB قرار می‌دهد (`main.py:2140-2170`).

**اثر:** هر دسترسی به `db.json`، backup یا export می‌تواند credential ربات را افشا کند.

**اقدام پیشنهادی:** استفاده از secret manager یا حداقل environment secret، mask کردن exportها و جدا کردن credential از backup عمومی.

### 10. backup و export حاوی اطلاعات بیش از حد حساس هستند
**شدت: مهم عملیاتی**

`/api/backup/export` کل DB را برمی‌گرداند (`main.py:2308-2312`) و backup فایل خام DB را ذخیره می‌کند (`main.py:2401-2447`).

**اثر:** backup/export علاوه بر داده کاربردی، می‌تواند secretها، tokenها و اطلاعات مدیریتی را نیز حمل کند.

**اقدام پیشنهادی:** secretها را از export قابل دانلود حذف یا رمزنگاری کنید؛ backup را encrypted-at-rest نگه دارید و برای restore از قالب versioned و signed استفاده کنید.

### 11. fail-open شدن maintenance gate
**شدت: متوسط امنیتی**

در `main.py:112-133` تمام exceptionهای middleware تعمیرات با `except Exception: pass` نادیده گرفته می‌شوند و درخواست ادامه پیدا می‌کند.

**اثر:** اگر خواندن DB یا بررسی maintenance خطا بدهد، برنامه به‌جای رفتار محافظه‌کارانه، دسترسی را باز می‌گذارد.

**اقدام پیشنهادی:** خطا را log کنید و سیاست مشخص fail-closed یا fail-safe برای endpointهای مدیریتی انتخاب کنید.

### 12. بازنویسی سراسری `listen` در entrypoint
**شدت: متوسط deployment**

در `entrypoint.sh:19-21` هر عبارت `listen <number>;` در فایل Nginx با PORT جایگزین می‌شود.

**اثر:** با اضافه شدن server block یا listener جداگانه در آینده، ممکن است پورت‌های داخلی نیز ناخواسته تغییر کنند.

**اقدام پیشنهادی:** فقط placeholder مشخص `NGINX_PORT` را جایگزین کنید، نه هر listener عددی را.

### 13. توقف ناقص taskهای background در shutdown
**شدت: متوسط reliability**

در `main.py:72-90` taskها cancel می‌شوند، اما بعد از cancel شدن await نمی‌شوند.

**اثر:** taskهای flush/backup ممکن است در حال نوشتن باشند و shutdown با نوشتن ناتمام یا warningهای pending task تمام شود.

**اقدام پیشنهادی:** پس از cancel از `await asyncio.gather(..., return_exceptions=True)` استفاده کنید و قبل از بستن resourceها flush نهایی انجام دهید.

### 14. لاگ دسترسی Nginx خاموش است
**شدت: متوسط observability**

در `nginx.conf:13-14` مقدار `access_log off` تنظیم شده است.

**اثر:** بررسی حمله، brute force، درخواست‌های غیرعادی و خطاهای routing دشوار می‌شود.

**اقدام پیشنهادی:** access log را با rotation و حذف/ماسک کردن داده حساس فعال کنید.

## ناسازگاری‌های مستندات و نسخه

نسخه‌ها و schema در چند جا یکسان نیستند:

- `README.md:1`: نسخه `3.1.0`
- `main.py:4`: docstring نسخه `3.0.0`
- `main.py:43`: `APP_VERSION = 3.1.1`
- `storage.py:37-38`: schema نسخه ۱۲
- `docs/ARCHITECTURE.md:10`: schema v9
- `docs/DATABASE.md:13`: current schema 9
- `docs/ARCHITECTURE.md:8`: حدود ۳۰۰۰ خط برای main.py، درحالی‌که فایل فعلی حدود ۴۵۰۰ خط است.

**اثر:** نمایش نسخه، راهنمای migration و تصمیم‌های deployment ممکن است اشتباه شود.

**اقدام پیشنهادی:** نسخه را از یک منبع واحد تولید کنید و مستندات را در CI با نسخه واقعی بررسی کنید.

## ضعف‌های پوشش تست

تست‌های فعلی بیشتر happy path را بررسی می‌کنند. موارد زیر تست مستقل ندارند یا پوشش آن‌ها کافی نیست:

- دو درخواست هم‌زمان برای `/api/setup`
- scheme و cookie پشت Nginx/HTTPS
- restore backup ناقص یا دارای نوع داده نادرست
- challenge مربوط به 2FA و استفاده از IP متفاوت
- افشای secretها در backup/export
- shutdown و لغو taskهای background
- migration از نسخه‌های قدیمی واقعی
- رفتار Docker با user غیر root و پورت public

## اولویت اصلاح پیشنهادی

1. حذف داده‌های حساس موجود، rotate کردن `secret_key` و توکن تلگرام.
2. اصلاح HTTPS/proxy headers و تولید scheme صحیح در لینک‌های local و production.
3. امن‌سازی restore/export و افزودن schema validation.
4. اصلاح atomic بودن setup و flow مربوط به 2FA.
5. pin و verify کردن Xray در Docker.
6. اجرای container با user غیر root.
7. اصلاح shutdown، logging و Nginx entrypoint.
8. یکسان‌سازی نسخه و schema در کد و مستندات.
9. افزودن تست‌های امنیتی و concurrency.

## جمع‌بندی نهایی

پروژه از نظر دامنه قابلیت‌ها، یک پنل نسبتاً کامل مدیریت Xray/VLESS است و تست‌های موجود نشان می‌دهند مسیرهای پایه فعلاً قابل اجرا هستند. بااین‌حال، برای production به‌خصوص روی Railway یا سرور عمومی، قبل از انتشار باید موارد مربوط به secretها، HTTPS، backup/restore، supply chain و اجرای root اصلاح شوند. مهم‌ترین ریسک فوری، وجود فایل‌های داده و backup حساس در workspace و مهم‌ترین باگ قابل مشاهده در استفاده عادی، تولید لینک HTTPS در اجرای محلی HTTP است.
