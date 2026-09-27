# ALOO PANEL ULTIMATE

پنل حرفه‌ای مدیریت سرویس‌های **Xray، VLESS و VMess** با رابط فارسی/انگلیسی، داشبورد زنده، مدیریت کاربران، مدیریت چندسرور و ابزارهای عملیاتی.

این پروژه برای تیم‌هایی ساخته شده است که می‌خواهند کاربران، اشتراک‌ها، حجم مصرفی، سرورها و وضعیت سرویس Xray را از یک پنل واحد مدیریت کنند.

> وضعیت فعلی: نسخه‌ی توسعه‌یافته‌ی پروژه با **۸۵ تست موفق**، API خلاصه‌ی داشبورد، خروجی CSV کاربران، Telegram polling مقاوم، گزارش‌های عملیاتی ربات، اعتبارسنجی امن backup، setup اتمیک، shutdown تمیز و اصلاح تولید لینک‌های local/production.

---

## فهرست مطالب

- [معرفی سریع](#معرفی-سریع)
- [قابلیت‌ها](#قابلیت‌ها)
- [معماری](#معماری)
- [پیش‌نیازها](#پیشنیازها)
- [اجرای محلی](#اجرای-محلی)
- [تنظیمات محیطی](#تنظیمات-محیطی)
- [ساختار پروژه](#ساختار-پروژه)
- [مدیریت کاربران و اشتراک‌ها](#مدیریت-کاربران-و-اشتراکها)
- [داشبورد و مانیتورینگ](#داشبورد-و-مانیتورینگ)
- [مدیریت چندسرور](#مدیریت-چندسرور)
- [امنیت](#امنیت)
- [Backup و Restore](#backup-و-restore)
- [API](#api)
- [تست](#تست)
- [Docker](#docker)
- [Deploy روی Railway](#deploy-روی-railway)
- [Deploy روی Render](#deploy-روی-render)
- [عیب‌یابی](#عیبیابی)
- [راهنمای توسعه](#راهنمای-توسعه)
- [مجوز](#مجوز)

---

## معرفی سریع

ALOO PANEL یک پنل وب FastAPI است که در کنار Xray اجرا می‌شود و از طریق Nginx ترافیک عمومی و مسیرهای WebSocket را مدیریت می‌کند.

جریان کلی سرویس:

```text
Client
  │
  ▼
Nginx / Public Port
  ├── /vl-ws     → Xray VLESS WebSocket
  ├── /vm-ws     → Xray VMess WebSocket
  ├── /vl-xhttp  → Xray VLESS XHTTP
  └── /          → FastAPI Panel
                         │
                         ├── JSON Store: data/db.json
                         ├── Xray Manager
                         ├── Telegram Bot
                         ├── Monitoring
                         └── Plugin Registry
```

اجرای محلی پنل:

```text
http://localhost:10000
```

در اولین اجرا، مسیر `/setup` برای ساخت حساب مدیر نمایش داده می‌شود.

---

## قابلیت‌ها

### مدیریت کاربران

- ساخت، ویرایش، حذف و غیرفعال‌سازی کاربر
- سهمیه‌ی حجمی و مدت اعتبار
- محدودیت اتصال هم‌زمان
- محدودیت تعداد درخواست
- قفل روی اولین IP
- ریست مصرف
- تغییر UUID برای ابطال لینک‌های قدیمی
- چرخش subscription token
- ساخت گروهی کاربران
- جست‌وجو، مرتب‌سازی، فیلتر وضعیت و صفحه‌بندی
- خروجی CSV عملیاتی بدون UUID و subscription token

### اشتراک‌ها و لینک‌ها

- VLESS TLS
- VMess WebSocket
- VLESS XHTTP
- subscription متنی
- JSON subscription
- Clash
- Sing-Box
- لینک وضعیت مصرف برای کاربر
- QR Code
- DoH داخلی با fallback

### داشبورد پیشرفته

- تعداد کاربران فعال، نزدیک به انقضا، منقضی و تمام‌شده
- کل ترافیک upload/download
- نمودار ترافیک ساعتی
- وضعیت Xray، Database و Telegram
- آخرین فعالیت‌ها و audit eventها
- خلاصه‌ی cache-friendly از مسیر زیر:

```http
GET /api/dashboard/summary
```

خلاصه‌ی داشبورد شامل کاربران، ترافیک، سرورها، سرویس‌ها، کاربران پرمصرف و هشدارهاست.

### مانیتورینگ حرفه‌ای

- CPU، RAM، Disk و Network
- process telemetry
- health score برای سرورها
- latency و load
- history برای metrics
- server alerts
- event timeline
- تشخیص online/offline
- agent heartbeat برای گزارش‌گیری از سرورهای راه دور
- انتخاب بهترین سرور بر اساس load، latency، health یا connections

### مدیریت چندسرور

- افزودن پنل‌های راه دور
- اعتبارسنجی اتصال و token هنگام افزودن سرور
- گروه‌بندی سرورها
- maintenance mode برای هر سرور
- failover و load balancing
- رتبه‌بندی سرورها
- ثبت رویدادهای server lifecycle

### مدیریت و عملیات

- Telegram admin bot
- shop و top-up
- notification center
- API tokens
- audit log
- backup زمان‌بندی‌شده
- maintenance mode
- diagnostics
- plugin system
- command palette با `Ctrl+K`
- تغییر زبان FA/EN
- تم روشن/تیره
- طراحی responsive برای موبایل

---

## معماری

| بخش | مسئولیت |
|---|---|
| `main.py` | FastAPI app، routeها، middleware، lifecycle و APIها |
| `storage.py` | JSON storage، migration، lock و atomic write |
| `core/security.py` | password policy، TOTP، role و permission |
| `core/users.py` | منبع واحد طبقه‌بندی وضعیت کاربران |
| `core/servers.py` | health score، load و version compatibility |
| `xray_manager.py` | ساخت config، start/stop/restart و آمار Xray |
| `vless_engine.py` | ساخت لینک‌ها و تنظیمات VLESS/VMess |
| `telegram_bot.py` | polling، اعلان‌ها و shop bot |
| `ai_assistant.py` | brief و دستیار عملیاتی |
| `plugins/` | بارگذاری extension و widgetها |
| `templates/` | قالب‌های Jinja2 |
| `static/css/` | theme، layout و UI components |
| `static/js/` | dashboard controller، chart، i18n و premium features |
| `tests/` | تست‌های API، regression، migration و core logic |

### ذخیره‌سازی

پروژه از یک فایل JSON استفاده می‌کند:

```text
data/db.json
```

نوشتن فایل با temporary file، `fsync` و `os.replace` انجام می‌شود. برای deployment واقعی باید مسیر `data/` روی volume پایدار قرار گیرد.

---

## پیش‌نیازها

- Python 3.11 یا بالاتر
- pip
- در deployment کانتینری: Docker
- برای Xray واقعی: باینری Xray و دسترسی اجرای process

---

## اجرای محلی

### Windows PowerShell

```powershell
cd my-project-main
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

### Linux/macOS

```bash
cd my-project-main
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

سپس باز کنید:

```text
http://localhost:10000/setup
```

### اجرای Uvicorn

```bash
uvicorn main:app --host 127.0.0.1 --port 10000
```

برای reverse proxy باید scheme اصلی درخواست به‌درستی با `X-Forwarded-Proto` منتقل شود.

---

## تنظیمات محیطی

| متغیر | مقدار پیش‌فرض | توضیح |
|---|---:|---|
| `PANEL_PORT` | `10000` | پورت داخلی FastAPI |
| `PORT` | `8000` در Docker | پورت عمومی Nginx یا پلتفرم cloud |
| `STANNG_DATA_DIR` | `./data` | محل DB و backup |
| `PANEL_NAME` | `ALOO PANEL` | نام نمایشی پنل |
| `TELEGRAM_CONTACT` | لینک پشتیبانی | لینک پشتیبانی UI |
| `XRAY_BIN` | auto-detect | مسیر باینری Xray |
| `XRAY_CONFIG_PATH` | auto-detect | مسیر config Xray |

نمونه:

```powershell
$env:PANEL_PORT = "10000"
$env:STANNG_DATA_DIR = "C:\aloo-data"
$env:PANEL_NAME = "My ALOO PANEL"
python main.py
```

---

## مدیریت کاربران و اشتراک‌ها

### وضعیت کاربران

طبقه‌بندی backend و frontend از یک قرارداد مشترک استفاده می‌کند:

```text
expired > quota_reached > disabled > near_expiry > active
```

این ترتیب باعث می‌شود تعداد کارت‌های داشبورد با فیلترهای جدول کاربران هماهنگ بماند.

### خروجی CSV

مسیر زیر اطلاعات عملیاتی کاربران را برمی‌گرداند و credentialهای حساس را شامل نمی‌شود:

```http
GET /api/inbounds/export.csv
```

خروجی شامل نام، وضعیت، حجم، مصرف، انقضا، محدودیت اتصال و یادداشت است؛ UUID و subscription token عمداً حذف شده‌اند.

---

## داشبورد و مانیتورینگ

### خلاصه‌ی داشبورد

```http
GET /api/dashboard/summary
```

Permission موردنیاز: `analytics.read`

نمونه‌ی ساختار پاسخ:

```json
{
  "generated_at": 0,
  "users": {
    "total": 0,
    "buckets": {}
  },
  "traffic": {
    "upload": 0,
    "download": 0,
    "total": 0
  },
  "servers": {
    "total": 1,
    "online": 1,
    "offline": 0,
    "alerts": 0
  },
  "services": {
    "xray": {"status": "mock"},
    "telegram": false,
    "database": "ok"
  },
  "top_users": [],
  "alerts": []
}
```

### گزارش‌های ربات تلگرام

در حالت ادمین، ربات این گزارش‌های عملیاتی را نیز ارائه می‌کند:

```text
/health    سلامت Xray، Telegram و تعداد کاربران
/traffic   آپلود، دانلود و مجموع ترافیک
/alerts    کاربران منقضی، تمام‌شده، نزدیک انقضا و غیرفعال
/stats     آمار کلی سرور
/users     فهرست کاربران
```

ربات بدون `Chat ID` ادمین، هیچ کاربر ناشناسی را وارد مسیر دستورات مدیریتی نمی‌کند و فقط مسیر فروشگاه را در صورت فعال بودن ارائه می‌دهد.

### Telemetry زنده

```http
GET /api/system/telemetry
GET /api/live
GET /api/online
```

### مانیتورینگ سرورها

```http
GET /api/servers/monitoring
GET /api/servers/top?sort_by=health
GET /api/servers/{id}/metrics?range=24h
GET /api/servers/{id}/events
GET /api/alerts
```

---

## امنیت

امکانات امنیتی فعلی:

- password hashing با PBKDF2-HMAC-SHA256
- session cookie امضاشده
- TOTP 2FA
- RBAC با roleهای owner، admin، support و viewer
- permissionهای تفکیک‌شده برای کاربران، سرورها، backup، امنیت و تنظیمات
- API token با نگهداری hash به‌جای raw token
- login rate limit
- security headers
- audit log
- امکان revoke کردن sessionها
- CSV export بدون credentialهای اتصال
- restore با validation ساختاری

### توصیه‌های production

1. فایل‌های `data/` را در repository عمومی قرار ندهید.
2. `secret_key` و Telegram token را در صورت افشا rotate کنید.
3. برای Docker از user غیر root استفاده کنید.
4. نسخه‌ی Xray را pin و checksum آن را verify کنید.
5. backup را encrypted-at-rest نگه دارید.
6. HTTPS را در reverse proxy اجباری کنید.
7. دسترسی Railway volume را محدود کنید.
8. tokenهای API را فقط یک‌بار نمایش دهید و در secret manager ذخیره کنید.

---

## Backup و Restore

### Backup دستی

```http
POST /api/backups
```

### لیست backupها

```http
GET /api/backups
```

### Restore

```http
POST /api/backups/restore
```

Restore فقط پس از بررسی رمز عبور مدیر و validation ساختاری انجام می‌شود. snapshot قدیمی با defaultهای فعلی merge می‌شود تا نبودن کلیدهای جدید باعث crash نشود.

### Export/Import ساده

```http
GET  /api/backup/export
POST /api/backup/import
```

به‌دلیل حساس بودن این endpointها، دسترسی آن‌ها را فقط به مدیران مورداعتماد بدهید.

---

## API

فهرست کامل endpointها در فایل زیر قرار دارد:

- [`docs/API.md`](docs/API.md)

گروه‌های اصلی API:

| گروه | مسیر |
|---|---|
| Health | `/health` |
| Auth | `/api/setup`، `/api/login`، `/api/logout` |
| Users | `/api/inbounds` |
| Plans | `/api/plans` |
| Dashboard | `/stats`، `/api/dashboard/summary` |
| Analytics | `/api/analytics`، `/api/live` |
| Servers | `/api/servers` |
| Monitoring | `/api/servers/monitoring`، `/api/alerts` |
| Xray | `/api/xray/*` |
| Telegram | `/api/telegram/*` |
| Security | `/api/security/*`، `/api/tokens` |
| Backup | `/api/backups/*`، `/api/backup/*` |
| Plugins | `/api/plugins/*` |

احراز هویت از یکی از دو روش انجام می‌شود:

```http
Cookie: stanng_session=<signed-cookie>
```

یا:

```http
Authorization: Bearer <api-token>
```

---

## تست

اجرای تست‌ها با محیط مجازی پروژه:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

بررسی syntax:

```powershell
.\.venv\Scripts\python.exe -m compileall -q .
```

وضعیت آخر بررسی:

```text
84 passed
```

پوشش تست شامل موارد زیر است:

- login و setup
- password rejection
- CRUD کاربران
- plans
- health و stats
- analytics و notifications
- backup endpoints
- roles و migration
- server CRUD و groups
- health score و load calculation
- heartbeat authentication
- dashboard summary
- CSV export
- local HTTP scheme
- invalid backup rejection

برای production بهتر است CI شامل این مراحل باشد:

```text
compileall → pytest → Docker build → health check → deploy
```

---

## Docker

ساخت image:

```bash
docker build -t aloo-panel .
```

اجرای محلی:

```bash
docker run --rm \
  -p 8000:8000 \
  -v aloo-data:/app/data \
  -e PANEL_NAME="ALOO PANEL" \
  aloo-panel
```

بررسی health:

```text
http://localhost:8000/health
```

در Docker، Nginx پورت عمومی را می‌گیرد و پنل داخلی روی `PANEL_PORT` اجرا می‌شود.

---

## Deploy روی Railway

### روش پیشنهادی

1. یک repository گیت‌هاب به پروژه متصل کنید.
2. در Railway یک Project بسازید.
3. از **New Service → GitHub Repo** استفاده کنید.
4. repository و branch را انتخاب کنید.
5. Railway از `Dockerfile` و `railway.json` استفاده می‌کند.
6. یک Volume با mount path زیر بسازید:

```text
/app/data
```

7. متغیرهای محیطی را تنظیم کنید:

```text
STANNG_DATA_DIR=/app/data
PANEL_NAME=ALOO PANEL
```

8. health check باید به این مسیر اشاره کند:

```text
/health
```

### نکات Railway

- بدون volume، فایل DB با redeploy از بین می‌رود.
- `PORT` توسط Railway تزریق می‌شود.
- TLS در لبه‌ی Railway terminate می‌شود؛ Nginx باید scheme اصلی را دریافت کند.
- قبل از deploy نهایی، logs، health check و persistence را بررسی کنید.

---

## Deploy روی Render

فایل `render.yaml` برای Docker runtime آماده شده است.

مراحل کلی:

1. repository را به Render متصل کنید.
2. سرویس Web را از blueprint بسازید.
3. health check را روی `/health` قرار دهید.
4. `STANNG_DATA_DIR` را روی مسیر volume تنظیم کنید.
5. قبل از تولید، persistence و restart behavior را آزمایش کنید.

---

## عیب‌یابی

### پنل باز نمی‌شود

- بررسی کنید `PANEL_PORT` آزاد باشد.
- خروجی اجرای `python main.py` را بررسی کنید.
- مسیر `/health` را تست کنید.

### Xray آفلاین است

- مقدار `XRAY_BIN` را بررسی کنید.
- config تولیدشده را از `/api/xray/config` ببینید.
- `/api/xray/validate` را اجرا کنید.
- لاگ process را بررسی کنید.

### کاربران بعد از deploy ناپدید شدند

احتمالاً volume روی `/app/data` متصل نشده است. بدون volume، `data/db.json` پایدار نیست.

### لینک local کار نمی‌کند

در اجرای محلی باید لینک‌ها با `http://` ساخته شوند. در production پشت HTTPS، هدر `X-Forwarded-Proto` باید مقدار درست داشته باشد.

### Telegram کار نمی‌کند

- token و chat ID را بررسی کنید.
- `telegram_enabled` را فعال کنید.
- از صفحه‌ی Telegram گزینه‌ی Test را اجرا کنید.
- token را در log یا commit ذخیره نکنید.

---

## راهنمای توسعه

قواعد پیشنهادی:

1. منطق طبقه‌بندی کاربران را فقط در `core/users.py` تغییر دهید.
2. برای endpoint جدید permission مشخص تعریف کنید.
3. هر قابلیت API باید تست regression داشته باشد.
4. credential را در کد، README، log یا fixture قرار ندهید.
5. تغییرات DB باید migration داشته باشد.
6. endpointهای destructive باید audit شوند.
7. قابلیت‌های frontend باید در هر دو زبان ترجمه داشته باشند.
8. بعد از تغییر API، `docs/API.md` و README را به‌روزرسانی کنید.
9. قبل از commit این دستورات را اجرا کنید:

```bash
python -m compileall -q .
python -m pytest -q
```

---

## فایل‌های مستندات

- [`docs/INSTALL.md`](docs/INSTALL.md)
- [`docs/CONFIG.md`](docs/CONFIG.md)
- [`docs/DATABASE.md`](docs/DATABASE.md)
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)
- [`docs/SERVERS.md`](docs/SERVERS.md)
- [`docs/TELEGRAM.md`](docs/TELEGRAM.md)
- [`docs/BACKUP.md`](docs/BACKUP.md)
- [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md)
- [`docs/API.md`](docs/API.md)
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

---

## مجوز

مجوز پروژه در فایل [`LICENSE`](LICENSE) قرار دارد.
