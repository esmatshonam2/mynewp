"""SsPanel — Telegram bot integration (v2.0).

- Sends admin notifications via Bot API (no extra deps, uses httpx).
- Validates token via getMe.
- Provides a tiny long-poll command handler so the panel owner can manage
  users directly from Telegram: /start /stats /users /user <name> /create /renew /reset /delete /sub
- Polling runs as an asyncio background task started from main.py lifespan.
"""
import asyncio
import hashlib
import logging
import os
import time

import httpx

log = logging.getLogger("telegram_bot")

API = "https://api.telegram.org"

# Last long-poll outcome (surfaced in /api/telegram/status → poll).
poll_state = {"last_ts": 0.0, "ok": None, "error": ""}


def poll_state_summary() -> dict:
    import time as _t
    return {"last_ts": poll_state.get("last_ts") or 0,
            "last_ok": poll_state.get("ok"),
            "error": (poll_state.get("error") or "")[:200],
            "fresh": (_t.time() - (poll_state.get("last_ts") or 0)) < 90}


def _api_url(token: str, method: str) -> str:
    return f"{API}/bot{token}/{method}"


async def tg_call(token: str, method: str, payload: dict | None = None, timeout: float = 12.0):
    try:
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.post(_api_url(token, method), json=payload or {})
            try:
                return r.json()
            except Exception:
                return {"ok": False, "status": r.status_code}
    except Exception as e:
        return {"ok": False, "error": str(e)}


async def validate_token(token: str):
    """Return (ok, bot_info_or_error)."""
    if not token or len(token) < 20 or ":" not in token:
        return False, "bad-format"
    data = await tg_call(token, "getMe")
    if isinstance(data, dict) and data.get("ok"):
        return True, data.get("result", {})
    return False, (data.get("description") if isinstance(data, dict) else "unreachable")


async def send_message(token: str, chat_id: str, text: str, parse_mode: str = "HTML", disable_preview: bool = True, markup: dict | None = None) -> bool:
    if not token or not chat_id:
        return False
    try:
        payload = {"chat_id": chat_id, "text": text[:3900],
                   "parse_mode": parse_mode, "disable_web_page_preview": disable_preview}
        if markup is not None:
            import json as _j
            payload["reply_markup"] = _j.dumps(markup, ensure_ascii=False)
        data = await tg_call(token, "sendMessage", payload)
        return bool(data.get("ok"))
    except Exception:
        return False


async def answer_callback(token: str, cb_id: str, text: str = "") -> bool:
    try:
        data = await tg_call(token, "answerCallbackQuery",
                             {"callback_query_id": cb_id, "text": (text or "")[:190]})
        return bool(data.get("ok"))
    except Exception:
        return False


def fmt_bytes(n: float) -> str:
    try:
        n = float(n or 0)
    except Exception:
        return "0 B"
    if n <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    import math
    i = min(len(units) - 1, int(math.log(n, 1024)))
    return f"{n / (1024 ** i):.2f} {units[i]}"


def esc(s) -> str:
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


async def send_photo(token: str, chat_id: str, png: bytes, caption: str = "") -> bool:
    """Send a PNG (e.g. subscription QR) via sendPhoto multipart upload."""
    if not token or not chat_id or not png:
        return False
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(_api_url(token, "sendPhoto"),
                             data={"chat_id": chat_id, "caption": caption[:1000],
                                   "parse_mode": "HTML"},
                             files={"photo": ("qr.png", png, "image/png")})
            return bool(r.json().get("ok"))
    except Exception:
        return False


async def send_document(token: str, chat_id: str, data: bytes, filename: str, caption: str = "") -> bool:
    """Send a file (e.g. automatic DB backup) via sendDocument multipart upload."""
    if not token or not chat_id or not data or not filename:
        return False
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(_api_url(token, "sendDocument"),
                             data={"chat_id": chat_id, "caption": caption[:1000],
                                   "parse_mode": "HTML"},
                             files={"document": (filename, data, "application/json")})
            return bool(r.json().get("ok"))
    except Exception:
        return False


def make_qr_png(text: str) -> bytes | None:
    try:
        import qrcode, io
        img = qrcode.make(text, border=2)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None


async def notify(store, kind: str, text: str):
    """Fire-and-forget admin notification if telegram is enabled."""
    try:
        db = await store.get()
        s = db.get("settings", {})
        if not s.get("telegram_enabled"):
            return
        token, chat, _src = resolve_creds(s)
        if not token or not chat:
            return
        flag = {"new_user": "notify_new_user", "quota": "notify_quota",
                "expiry": "notify_expiry", "login": "notify_login",
                "server": "notify_server"}.get(kind)
        if flag and s.get(flag) is False:
            return
        await send_message(token, chat, text)
    except Exception as e:
        log.warning("telegram notify failed: %s", e)


def resolve_creds(settings: dict):
    """Bot credentials: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID env wins over DB.

    Returns (token, chat_id, source) with source in {"env", "db"}.
    """
    s = settings or {}
    env_tok = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    if env_tok:
        return env_tok, (os.environ.get("TELEGRAM_CHAT_ID") or str(s.get("telegram_chat_id") or "")).strip(), "env"
    return ((s.get("telegram_bot_token") or "").strip(),
            str(s.get("telegram_chat_id") or "").strip(), "db")


async def _handle_command(store, token: str, chat_id: str, text: str, build_links_cb=None):
    """Command router over REAL panel data (users, traffic, subscriptions)."""
    import time as _t
    parts = (text or "").strip().split()
    if not parts:
        return
    cmd = parts[0].split("@")[0].lower()
    args = parts[1:]
    db = await store.get()
    settings = db.get("settings") or {}

    async def reply(t: str):
        await send_message(token, chat_id, t)

    def public_base() -> str | None:
        dom = (settings.get("public_domain") or "").strip().rstrip("/")
        return f"https://{dom}" if dom else None

    def user_lines(ib: dict) -> str:
        used = (ib.get("used_up") or 0) + (ib.get("used_down") or 0)
        q = ib.get("quota_gb") or 0
        quota_txt = f"{used / 1024**3:.2f}/{q:g}GB" if q > 0 else f"{used / 1024**3:.2f}GB / ∞"
        exp = ib.get("expire_at")
        if exp:
            days = (exp - _t.time()) / 86400
            exp_txt = "منقضی شده ❌" if days <= 0 else f"{days:.1f} روز مانده"
        else:
            exp_txt = "بدون انقضا"
        state = "فعال ✅" if ib.get("enabled", True) else "غیرفعال ⛔"
        return (f"👤 <b>{esc(ib.get('name'))}</b> — {state}\n"
                f"📦 مصرف: {quota_txt}\n⏳ انقضا: {exp_txt}")

    if cmd in ("/start", "/help"):
        await reply("👑 <b>ALOO PANEL Bot</b>\n\n"
                    "/stats — وضعیت سرور\n/users — لیست کاربران\n"
                    "/user &lt;name&gt; — مصرف، باقی‌مانده و انقضا\n"
                    "/sub &lt;name&gt; — لینک سابسکریپشن + QR\n"
                    "/create &lt;name&gt; [quotaGB] [days] — ساخت کاربر\n"
                    "/reset &lt;name&gt; — ریست مصرف\n/delete &lt;name&gt; — حذف")
        return
    if cmd == "/stats":
        ups = db["stats"].get("total_up", 0) + db["stats"].get("total_down", 0)
        on = sum(1 for ib in db["inbounds"] if ib.get("enabled", True))
        await reply(f"📊 <b>آمار سرور</b>\n👥 کاربران: {len(db['inbounds'])} (فعال: {on})\n📦 ترافیک کل: {fmt_bytes(ups)}")
        return
    if cmd == "/users":
        if not db["inbounds"]:
            await reply("کاربری وجود ندارد.")
            return
        lines = ["👥 <b>کاربران:</b>"]
        for ib in db["inbounds"][:40]:
            used = (ib.get("used_up") or 0) + (ib.get("used_down") or 0)
            mark = "" if ib.get("enabled", True) else " ⛔"
            lines.append(f"• {esc(ib.get('name'))} — {fmt_bytes(used)}{mark}")
        await reply("\n".join(lines))
        return
    # --- user-scoped commands ---
    def find_user(q: str):
        ql = q.lower()
        for ib in db["inbounds"]:
            if ib.get("name", "").lower() == ql or ib.get("uid") == q:
                return ib
        for ib in db["inbounds"]:
            if ql in ib.get("name", "").lower():
                return ib
        return None

    def mutate_and_save(fn):
        # run through the store so writes persist + stay atomic
        return store.mutate(fn)

    if cmd == "/create":
        if not args:
            await reply("مثال: <code>/create Ali 30 30</code>")
            return
        import uuid as _uuid, secrets as _secrets
        try:
            quota = float(args[1]) if len(args) > 1 else 0
            days = int(args[2]) if len(args) > 2 else 0
        except Exception:
            await reply("مقادیر نامعتبر. مثال: <code>/create Ali 30 30</code>")
            return
        now = _t.time()
        ib = {"uid": _secrets.token_hex(8), "uuid": str(_uuid.uuid4()),
              "name": args[0][:64], "enabled": True, "created_at": now,
              "expire_days": days, "expire_at": (now + days * 86400) if days > 0 else None,
              "quota_gb": max(0, quota), "max_connections": 0, "max_requests": 0,
              "request_count": 0, "used_up": 0, "used_down": 0,
              "fp": settings.get("default_fingerprint", "chrome"),
              "strict_single_ip": False, "note": "via-bot",
              "sub_token": _secrets.token_hex(12), "sub_enabled": True,
              "plan_id": None, "plan_name": ""}

        def _add(db):
            db["inbounds"].append(ib)
        await mutate_and_save(_add)
        try:
            import main as _main
            _main.refresh_xray(_main.store.get_sync())
        except Exception:
            pass
        base = public_base()
        sub = f"{base}/s/{ib['sub_token']}" if base else f"/s/{ib['sub_token']}"
        await reply(f"✅ ساخته شد:\n{user_lines(ib)}\n🔗 <code>{esc(sub)}</code>")
        return
    if cmd in ("/user", "/sub", "/reset", "/delete"):
        if not args:
            await reply("نام کاربر را وارد کنید.")
            return
        ib = find_user(" ".join(args))
        if not ib:
            await reply("❌ کاربر یافت نشد.")
            return
        if cmd == "/user":
            q = ib.get("quota_gb") or 0
            used = (ib.get("used_up") or 0) + (ib.get("used_down") or 0)
            rem = "∞" if q <= 0 else fmt_bytes(max(0, q * 1024**3 - used))
            await reply(f"{user_lines(ib)}\n📉 باقی‌مانده: {rem}\n🆔 <code>{ib.get('uid')}</code>")
        elif cmd == "/sub":
            if ib.get("sub_enabled", True) is False:
                await reply("⛔ اشتراک این کاربر غیرفعال است.")
                return
            base = public_base()
            tok = ib.get("sub_token") or ib.get("uid")
            url = f"{base}/s/{tok}" if base else None
            if url:
                png = make_qr_png(url)
                if png:
                    await send_photo(token, chat_id, png, f"🔗 سابسکریپشن {ib.get('name')}\n<code>{esc(url)}</code>")
                else:
                    await reply(f"🔗 <code>{esc(url)}</code>")
            else:
                await reply(f"🔗 مسیر ساب: <code>/s/{tok}</code>\nℹ️ برای لینک کامل، دامنه عمومی را در تنظیمات پنل ثبت کنید.")
        elif cmd == "/reset":
            def _rst(db):
                for x in db["inbounds"]:
                    if x.get("uid") == ib.get("uid"):
                        x["used_up"] = 0
                        x["used_down"] = 0
                        x["request_count"] = 0
            await mutate_and_save(_rst)
            await reply(f"♻️ مصرف <b>{esc(ib.get('name'))}</b> ریست شد.")
        elif cmd == "/delete":
            def _del(db):
                db["inbounds"] = [x for x in db["inbounds"] if x.get("uid") != ib.get("uid")]
            await mutate_and_save(_del)
            try:
                import main as _main
                _main.refresh_xray(_main.store.get_sync())
            except Exception:
                pass
            await reply(f"🗑 کاربر <b>{esc(ib.get('name'))}</b> حذف شد.")
        return
    await reply("دستور ناشناخته. /help")


async def poll_loop(store, get_token_chat, interval: float = 2.5):
    """Long-poll getUpdates loop. get_token_chat() -> (token, admin_chat, enabled)."""
    import time as _t
    offset = 0
    # persist offset in memory only
    while True:
        try:
            token, admin_chat, enabled = get_token_chat()
            if not enabled or not token:
                await asyncio.sleep(10)
                continue
            async with httpx.AsyncClient(timeout=30) as c:
                try:
                    r = await c.post(_api_url(token, "getUpdates"),
                                     json={"offset": offset, "timeout": 20,
                                           "allowed_updates": ["message", "callback_query"]})
                    data = r.json()
                except Exception as e:
                    poll_state.update({"last_ts": _t.time(), "ok": False, "error": f"net: {e}"[:200]})
                    await asyncio.sleep(5)
                    continue
            if not data.get("ok"):
                # invalid token — back off
                poll_state.update({"last_ts": _t.time(), "ok": False,
                                   "error": str(data.get("description") or "api-error")[:200]})
                await asyncio.sleep(15)
                continue
            poll_state.update({"last_ts": _t.time(), "ok": True, "error": ""})
            for upd in data.get("result", []):
                offset = max(offset, int(upd.get("update_id", 0)) + 1)
                # ---- inline button taps ----
                cb = upd.get("callback_query")
                if cb:
                    try:
                        await handle_shop_callback(store, token, str(admin_chat or ""), cb)
                    except Exception as e:
                        log.warning("callback error: %s", e)
                    continue
                msg = upd.get("message") or {}
                chat = str((msg.get("chat") or {}).get("id", ""))
                text = msg.get("text") or ""
                tg_user = msg.get("from") or {}
                if admin_chat and chat != str(admin_chat):
                    # ---- customer (shop) mode ----
                    try:
                        db0 = await store.get()
                        shop_on = bool((db0.get("settings") or {}).get("shop_enabled", True))
                    except Exception:
                        shop_on = True
                    if shop_on:
                        # referral payload: /start ref_<tgid>
                        if text.startswith("/start"):
                            try:
                                cust = await get_customer(store, tg_user)
                                parts = text.split()
                                if len(parts) > 1 and parts[1].startswith("ref_"):
                                    ref = parts[1][4:]
                                    if ref.isdigit() and int(ref) != cust["tg_id"] and not cust.get("referred_by"):
                                        rid = int(ref)

                                        def _ref(db):
                                            u = find_customer(db, cust["tg_id"])
                                            if u and not u.get("referred_by"):
                                                # referrer must exist
                                                if find_customer(db, rid):
                                                    u["referred_by"] = rid
                                        await store.mutate(_ref)
                            except Exception:
                                pass
                            await send_message(token, chat, "👋 به فروشگاه خوش آمدی!", markup=main_menu_kb())
                            continue
                        try:
                            if await handle_shop_message(store, token, chat, tg_user, text):
                                continue
                        except Exception as e:
                            log.warning("shop error: %s", e)
                    if (text or "").startswith("/"):
                        await send_message(token, chat, "👋 برای استفاده از فروشگاه /start را بزنید.",
                                           markup=main_menu_kb() if shop_on else None)
                    continue
                if text.startswith("/"):
                    await _handle_command(store, token, chat, text)
        except asyncio.CancelledError:
            break
        except Exception as e:
            log.warning("telegram poll error: %s", e)
            await asyncio.sleep(5)


def token_fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:12]


# ================= Phase 6b: SHOP BOT (customer-facing, like the EU-vpn bots) =================
# NOTE on button colors: Telegram Bot API has no color option — the green/red/blue
# buttons in such screenshots are painted by the user's Telegram app theme.
# Labels, emoji, layout and every behavior below match 1:1 and are all real
# panel operations (create user, apply plan, quota, wallet, referrals, wheel).
BTN_BUY = "🛒 خرید کانفیگ"
BTN_MINIAPP = "✨ مینی‌اپ فروشگاه"
BTN_TEST = "🧪 کانفیگ تست رایگان"
BTN_ORDERS = "📦 سفارش‌های من"
BTN_WALLET = "👛 کیف پول من"
BTN_REF = "🤝 زیرمجموعه‌گیری من"
BTN_WHEEL = "🎡 گردونه شانس"
BTN_SUPPORT = "📞 ارتباط با پشتیبانی"

TOPUP_AMOUNTS = (50000, 100000, 200000)
WHEEL_PRIZES = ((1, 50), (2, 30), (5, 15), (10, 5))  # (GB, weight)


def main_menu_kb() -> dict:
    return {"keyboard": [
        [{"text": BTN_BUY}, {"text": BTN_MINIAPP}],
        [{"text": BTN_TEST}, {"text": BTN_ORDERS}],
        [{"text": BTN_WALLET}, {"text": BTN_REF}],
        [{"text": BTN_WHEEL}, {"text": BTN_SUPPORT}],
    ], "resize_keyboard": True}


def _shop_cfg(db) -> dict:
    s = db.get("settings") or {}
    token, admin_chat, _src = resolve_creds(s)
    return {
        "enabled": bool(s.get("shop_enabled", True)),
        "support": (s.get("support_username") or "ITSESMAT").lstrip("@"),
        "test_gb": float(s.get("shop_test_gb") or 1),
        "test_days": int(s.get("shop_test_days") or 1),
        "bonus": float(s.get("referral_bonus") or 0),
        "bot_username": (s.get("bot_username") or "").lstrip("@"),
        "domain": (s.get("public_domain") or "").strip().rstrip("/"),
        "token": token,
        "admin_chat": admin_chat,
    }


async def get_customer(store, tg_user: dict) -> dict:
    """Get-or-create the shop customer record. Returns a copy."""
    tg_id = int(tg_user.get("id") or 0)
    uname = (tg_user.get("username") or "")[:64]
    fname = (tg_user.get("first_name") or "")[:64]
    out = {}

    def _a(db):
        for u in db.get("bot_users", []):
            if int(u.get("tg_id") or 0) == tg_id:
                if uname:
                    u["username"] = uname
                out.update(u)
                return
        rec = {"tg_id": tg_id, "username": uname, "first_name": fname,
               "inbound_uids": [], "balance": 0.0, "referrals": [],
               "referred_by": None, "referral_earned": 0.0,
               "test_claimed": False, "last_spin": "", "pending_bonus": 0.0,
               "created_at": __import__("time").time()}
        db.setdefault("bot_users", []).append(rec)
        out.update(rec)
    await store.mutate(_a)
    return out


def find_customer(db, tg_id: int):
    for u in db.get("bot_users", []):
        if int(u.get("tg_id") or 0) == int(tg_id):
            return u
    return None


def _fmt_money(v) -> str:
    try:
        return f"{float(v):,.0f} تومان"
    except Exception:
        return str(v)


async def _admin_notify(store, text: str, markup: dict | None = None):
    try:
        db = await store.get()
        cfg = _shop_cfg(db)
        if cfg["token"] and cfg["admin_chat"]:
            await send_message(cfg["token"], cfg["admin_chat"], text, markup=markup)
    except Exception:
        pass


def _sub_url_for(cfg: dict, sub_token: str, uid: str) -> str | None:
    tok = sub_token or uid
    if cfg["domain"]:
        return f"https://{cfg['domain']}/s/{tok}"
    return None


async def _send_sub(store, token: str, chat_id: str, ib: dict, title: str):
    """Send subscription URL + QR photo. Falls back to path when no domain."""
    db = await store.get()
    cfg = _shop_cfg(db)
    url = _sub_url_for(cfg, ib.get("sub_token"), ib.get("uid"))
    if url:
        png = make_qr_png(url)
        cap = f"🔗 <b>{esc(title)}</b>\n<code>{esc(url)}</code>"
        if png:
            if await send_photo(token, chat_id, png, cap):
                return
        await send_message(token, chat_id, cap)
    else:
        tok = ib.get("sub_token") or ib.get("uid")
        await send_message(token, chat_id,
                           f"🔗 <b>{esc(title)}</b>\nمسیر ساب: <code>/s/{tok}</code>\n"
                           f"ℹ️ لینک کامل بعد از ثبت دامنه در پنل فعال می‌شود.")


def _make_inbound_dict(name: str, quota_gb: float, days: int, fp: str, note: str) -> dict:
    import uuid as _uuid, secrets as _secrets, time as _t
    now = _t.time()
    return {"uid": _secrets.token_hex(8), "uuid": str(_uuid.uuid4()),
            "name": name[:64], "enabled": True, "created_at": now,
            "expire_days": max(0, days), "expire_at": (now + days * 86400) if days > 0 else None,
            "quota_gb": max(0.0, quota_gb), "max_connections": 0, "max_requests": 0,
            "request_count": 0, "used_up": 0, "used_down": 0, "fp": fp or "chrome",
            "strict_single_ip": False, "note": note[:200],
            "sub_token": _secrets.token_hex(12), "sub_enabled": True,
            "plan_id": None, "plan_name": ""}


def _refresh_panel():
    try:
        import main as _main
        _main.refresh_xray(_main.store.get_sync())
    except Exception:
        pass


# ---------- customer flows (each hits the real panel store) ----------
async def shop_show_plans(store, token: str, chat_id: str):
    db = await store.get()
    plans = [p for p in db.get("plans", []) if p.get("enabled", True)]
    if not plans:
        await send_message(token, chat_id, "در حال حاضر پلنی موجود نیست. با پشتیبانی در تماس باشید.")
        return
    kb = {"inline_keyboard": [
        [{"text": f"{p.get('name')} — {p.get('traffic_gb'):g}GB / {p.get('duration_days')}d — {_fmt_money(p.get('price') or 0)}",
          "callback_data": f"buy_{p.get('id')}"[:64]}] for p in plans]}
    await send_message(token, chat_id, "🛒 <b>انتخاب پلن:</b>", markup=kb)


async def shop_buy_offer(store, token: str, chat_id: str, tg_id: int, plan_id: str):
    db = await store.get()
    plan = next((p for p in db.get("plans", []) if p.get("id") == plan_id and p.get("enabled", True)), None)
    if not plan:
        await send_message(token, chat_id, "❌ این پلن نامعتبر است.")
        return
    cust = find_customer(db, tg_id) or {}
    bal = float(cust.get("balance") or 0)
    price = float(plan.get("price") or 0)
    txt = (f"📦 <b>{esc(plan.get('name'))}</b>\n"
           f"📊 حجم: {plan.get('traffic_gb'):g}GB · ⏳ {plan.get('duration_days')} روز · 📱 {plan.get('device_limit')} دستگاه\n"
           f"💰 قیمت: {_fmt_money(price)}\n👛 موجودی شما: {_fmt_money(bal)}")
    kb = {"inline_keyboard": [[{"text": "✅ تأیید خرید", "callback_data": f"confirm_{plan_id}"[:64]}]]}
    await send_message(token, chat_id, txt, markup=kb)


async def shop_buy_confirm(store, token: str, chat_id: str, tg_user: dict, plan_id: str):
    import time as _t
    try:
        from main import apply_plan_to_inbound as _apply_plan
    except Exception:
        _apply_plan = None
    db = await store.get()
    cfg = _shop_cfg(db)
    plan = next((p for p in db.get("plans", []) if p.get("id") == plan_id and p.get("enabled", True)), None)
    cust = find_customer(db, int(tg_user.get("id") or 0))
    if not plan or not cust:
        await send_message(token, chat_id, "❌ نامعتبر است. دوباره تلاش کنید.")
        return
    price = float(plan.get("price") or 0)
    if float(cust.get("balance") or 0) < price:
        kb = {"inline_keyboard": [[{"text": "👛 شارژ کیف پول", "callback_data": "menu_wallet"}]]}
        await send_message(token, chat_id,
                           f"❌ موجودی کافی نیست.\n💰 قیمت: {_fmt_money(price)}\n👛 موجودی: {_fmt_money(cust.get('balance') or 0)}",
                           markup=kb)
        return
    n = len(cust.get("inbound_uids") or []) + 1
    ib = _make_inbound_dict(f"tg{cust['tg_id']}-{n}", float(plan.get("traffic_gb") or 0),
                            int(plan.get("duration_days") or 0),
                            (db.get("settings") or {}).get("default_fingerprint", "chrome"), "shop")
    if _apply_plan:
        _apply_plan(ib, plan, now=_t.time())
    bonus_txt = ""
    if float(cust.get("pending_bonus") or 0) > 0:
        ib["quota_gb"] = round(ib["quota_gb"] + float(cust["pending_bonus"]), 2)
        bonus_txt = f"\n🎁 جایزه گردونه اعمال شد: +{float(cust['pending_bonus']):g}GB"
    first_order = not (cust.get("inbound_uids") or [])

    def _a(db):
        u = find_customer(db, cust["tg_id"])
        u["balance"] = round(float(u.get("balance") or 0) - price, 2)
        u["pending_bonus"] = 0.0
        u.setdefault("inbound_uids", []).append(ib["uid"])
        db["inbounds"].append(ib)
        # referral: first purchase credits the inviter
        if first_order and u.get("referred_by") and cfg["bonus"] > 0:
            ref = find_customer(db, u["referred_by"])
            if ref:
                ref["balance"] = round(float(ref.get("balance") or 0) + cfg["bonus"], 2)
                ref.setdefault("referrals", [])
                ref["referral_earned"] = round(float(ref.get("referral_earned") or 0) + cfg["bonus"], 2)
    await store.mutate(_a)
    _refresh_panel()
    # notify referrer (real purses move)
    if first_order and cust.get("referred_by") and cfg["bonus"] > 0:
        try:
            await send_message(token, str(cust["referred_by"]),
                               f"🎉 زیرمجموعه شما خرید کرد!\n💰 +{_fmt_money(cfg['bonus'])} به کیف پول شما اضافه شد.")
        except Exception:
            pass
    await _admin_notify(store, f"🛒 <b>خرید جدید</b>\n👤 {esc(cust.get('first_name') or cust.get('username') or cust['tg_id'])}\n"
                               f"📦 {esc(plan.get('name'))} — {_fmt_money(price)}")
    await send_message(token, chat_id, f"✅ خرید انجام شد!{bonus_txt}")
    await _send_sub(store, token, chat_id, ib, plan.get("name"))


async def shop_free_test(store, token: str, chat_id: str, tg_user: dict):
    db = await store.get()
    cfg = _shop_cfg(db)
    cust = find_customer(db, int(tg_user.get("id") or 0)) or {}
    if cust.get("test_claimed"):
        await send_message(token, chat_id, "❌ شما قبلاً کانفیگ تست را دریافت کرده‌اید.")
        return
    ib = _make_inbound_dict(f"tg{cust.get('tg_id', chat_id)}-test",
                            cfg["test_gb"], cfg["test_days"],
                            (db.get("settings") or {}).get("default_fingerprint", "chrome"),
                            "free-test")

    def _a(db):
        u = find_customer(db, int(tg_user.get("id") or 0))
        u["test_claimed"] = True
        u.setdefault("inbound_uids", []).append(ib["uid"])
        db["inbounds"].append(ib)
    await store.mutate(_a)
    _refresh_panel()
    await send_message(token, chat_id,
                       f"🧪 <b>کانفیگ تست فعال شد</b> ({cfg['test_gb']:g}GB / {cfg['test_days']} روز)")
    await _send_sub(store, token, chat_id, ib, "تست رایگان")


async def shop_orders(store, token: str, chat_id: str, tg_id: int):
    try:
        from main import inbound_by_uid as _by_uid
    except Exception:
        _by_uid = None
    db = await store.get()
    cust = find_customer(db, tg_id)
    uids = (cust.get("inbound_uids") or []) if cust else []
    if not uids:
        await send_message(token, chat_id, "📦 سفارشی ندارید. از «🛒 خرید کانفیگ» شروع کنید.")
        return
    import time as _t
    lines = ["📦 <b>سفارش‌های من:</b>"]
    for uid in uids[-10:]:
        ib = _by_uid(db, uid) if _by_uid else next((x for x in db.get("inbounds", []) if x.get("uid") == uid), None)
        if not ib:
            continue
        used = (ib.get("used_up") or 0) + (ib.get("used_down") or 0)
        q = ib.get("quota_gb") or 0
        qt = f"{used/1024**3:.2f}/{q:g}GB" if q > 0 else f"{used/1024**3:.2f}GB/∞"
        exp = ib.get("expire_at")
        et = "∞" if not exp else ("❌" if exp <= _t.time() else f"{(exp-_t.time())/86400:.1f}d")
        st = "✅" if ib.get("enabled", True) else "⛔"
        lines.append(f"{st} <b>{esc(ib.get('name'))}</b> — {qt} — {et}")
    await send_message(token, chat_id, "\n".join(lines))


async def shop_wallet(store, token: str, chat_id: str, tg_id: int):
    db = await store.get()
    cust = find_customer(db, tg_id) or {}
    pend = [t for t in db.get("topup_requests", [])
            if int(t.get("tg_id") or 0) == int(tg_id) and t.get("status") == "pending"]
    kb = {"inline_keyboard": [
        [{"text": f"💰 {_fmt_money(a)}", "callback_data": f"topup_{a}"}] for a in TOPUP_AMOUNTS]}
    txt = f"👛 <b>کیف پول:</b> {_fmt_money(cust.get('balance') or 0)}"
    if pend:
        txt += "\n⏳ درخواست‌های در انتظار: " + ", ".join(_fmt_money(t.get("amount")) for t in pend)
    await send_message(token, chat_id, txt, markup=kb)


async def shop_topup_request(store, token: str, chat_id: str, tg_user: dict, amount: int):
    import time as _t, secrets as _secrets
    rid = "tp_" + _secrets.token_hex(6)
    rec = {"id": rid, "tg_id": int(tg_user.get("id") or 0),
           "username": (tg_user.get("username") or "")[:64],
           "first_name": (tg_user.get("first_name") or "")[:64],
           "amount": amount, "status": "pending", "ts": _t.time()}

    def _a(db):
        db.setdefault("topup_requests", []).append(rec)
    await store.mutate(_a)
    kb = {"inline_keyboard": [[
        {"text": "✅ تأیید", "callback_data": f"topup_ok_{rid}"},
        {"text": "❌ رد", "callback_data": f"topup_no_{rid}"}]]}
    await _admin_notify(store,
                        f"💰 <b>درخواست شارژ</b>\n👤 {esc(rec['first_name'] or rec['username'] or rec['tg_id'])}\n"
                        f"💵 مبلغ: {_fmt_money(amount)}\n🆔 <code>{rid}</code>", markup=kb)
    await send_message(token, chat_id,
                       f"✅ درخواست شارژ {_fmt_money(amount)} ثبت شد. پس از تأیید ادمین کیف پول شارژ می‌شود.")


async def topup_decide(store, rid: str, approve: bool, by: str = "admin"):
    """Approve/deny a pending top-up. Returns the request or None."""
    import time as _t
    found = {}

    def _a(db):
        for t in db.get("topup_requests", []):
            if t.get("id") == rid and t.get("status") == "pending":
                t["status"] = "approved" if approve else "denied"
                t["decided_by"] = str(by)[:64]
                t["decided_at"] = _t.time()
                if approve:
                    u = find_customer(db, t.get("tg_id"))
                    if u:
                        u["balance"] = round(float(u.get("balance") or 0) + float(t.get("amount") or 0), 2)
                found.update(t)
    await store.mutate(_a)
    req = found or None
    if req:
        try:
            db = await store.get()
            cfg = _shop_cfg(db)
            if cfg["token"]:
                if approve:
                    await send_message(cfg["token"], str(req["tg_id"]),
                                       f"✅ شارژ {_fmt_money(req['amount'])} تأیید و به کیف پول اضافه شد.")
                else:
                    await send_message(cfg["token"], str(req["tg_id"]),
                                       "❌ درخواست شارژ شما رد شد. با پشتیبانی در تماس باشید.")
        except Exception:
            pass
    return req


async def shop_referral(store, token: str, chat_id: str, tg_id: int):
    db = await store.get()
    cfg = _shop_cfg(db)
    cust = find_customer(db, tg_id) or {}
    link = f"https://t.me/{cfg['bot_username']}?start=ref_{tg_id}" if cfg["bot_username"] else "نام‌کاربری ربات هنوز ثبت نشده است"
    await send_message(token, chat_id,
                       f"🤝 <b>زیرمجموعه‌گیری</b>\n🔗 لینک شما:\n<code>{esc(link)}</code>\n"
                       f"👥 دعوت‌شده‌ها: {len(cust.get('referrals') or [])}\n"
                       f"💰 درآمد: {_fmt_money(cust.get('referral_earned') or 0)}\n"
                       f"🎁 پاداش هر خرید اول: {_fmt_money(cfg['bonus'])}")


async def shop_wheel(store, token: str, chat_id: str, tg_user: dict):
    import time as _t, random as _r
    import datetime as _dt
    tg_id = int(tg_user.get("id") or 0)
    today = _dt.date.today().isoformat()
    db = await store.get()
    cust = find_customer(db, tg_id) or {}
    if cust.get("last_spin") == today:
        await send_message(token, chat_id, "🎡 شانس امروز استفاده شده. فردا برگرد! 🍀")
        return
    total = sum(w for _, w in WHEEL_PRIZES)
    roll = _r.uniform(0, total)
    prize = WHEEL_PRIZES[-1][0]
    acc = 0
    for gb, w in WHEEL_PRIZES:
        acc += w
        if roll <= acc:
            prize = gb
            break
    # credit to the newest enabled inbound, else park as pending bonus
    target = None
    for uid in reversed(cust.get("inbound_uids") or []):
        ib = next((x for x in db.get("inbounds", []) if x.get("uid") == uid and x.get("enabled", True)), None)
        if ib:
            target = ib["uid"]
            break

    def _a(db):
        u = find_customer(db, tg_id)
        u["last_spin"] = today
        if target:
            for x in db.get("inbounds", []):
                if x.get("uid") == target:
                    x["quota_gb"] = round((x.get("quota_gb") or 0) + prize, 2)
        else:
            u["pending_bonus"] = round(float(u.get("pending_bonus") or 0) + prize, 2)
    await store.mutate(_a)
    if target:
        _refresh_panel()
        await send_message(token, chat_id, f"🎡🎉 تبریک! <b>{prize} گیگ</b> به حسابت اضافه شد.")
    else:
        await send_message(token, chat_id,
                           f"🎡🎉 تبریک! <b>{prize} گیگ</b> بردی؛ با اولین خرید به حسابت اضافه می‌شود.")


async def shop_support(store, token: str, chat_id: str):
    db = await store.get()
    cfg = _shop_cfg(db)
    kb = {"inline_keyboard": [[{"text": "📞 گفتگو با پشتیبانی", "url": f"https://t.me/{cfg['support']}"}]]}
    await send_message(token, chat_id, "📞 برای پشتیبانی دکمه زیر را بزنید:", markup=kb)


async def handle_shop_message(store, token: str, chat_id: str, tg_user: dict, text: str):
    """Customer router. Returns True if the message was consumed as shop flow."""
    db = await store.get()
    cfg = _shop_cfg(db)
    if not cfg["enabled"]:
        return False
    cust = await get_customer(store, tg_user)
    t = (text or "").strip()
    if t == BTN_BUY or t == BTN_MINIAPP:
        await shop_show_plans(store, token, chat_id)
        return True
    if t == BTN_TEST:
        await shop_free_test(store, token, chat_id, tg_user)
        return True
    if t == BTN_ORDERS:
        await shop_orders(store, token, chat_id, cust["tg_id"])
        return True
    if t == BTN_WALLET:
        await shop_wallet(store, token, chat_id, cust["tg_id"])
        return True
    if t == BTN_REF:
        await shop_referral(store, token, chat_id, cust["tg_id"])
        return True
    if t == BTN_WHEEL:
        await shop_wheel(store, token, chat_id, tg_user)
        return True
    if t == BTN_SUPPORT:
        await shop_support(store, token, chat_id)
        return True
    return False


async def handle_shop_callback(store, token: str, admin_chat: str, query: dict) -> bool:
    """Inline-button router (purchases, top-ups, approvals). Returns consumed."""
    cb_id = query.get("id", "")
    data = (query.get("data") or "").strip()
    msg = query.get("message") or {}
    chat = msg.get("chat") or {}
    chat_id = str(chat.get("id", ""))
    tg_user = query.get("from") or {}
    if not data or not chat_id:
        return False
    is_admin = bool(admin_chat) and chat_id == str(admin_chat)
    if data.startswith("buy_"):
        await answer_callback(token, cb_id)
        await shop_buy_offer(store, token, chat_id, int(tg_user.get("id") or 0), data[4:64])
        return True
    if data.startswith("confirm_"):
        await answer_callback(token, cb_id, "در حال پردازش...")
        await shop_buy_confirm(store, token, chat_id, tg_user, data[8:64])
        return True
    if data == "menu_wallet":
        await answer_callback(token, cb_id)
        await shop_wallet(store, token, chat_id, int(tg_user.get("id") or 0))
        return True
    if data.startswith("topup_") and data[6:].isdigit():
        await answer_callback(token, cb_id)
        await shop_topup_request(store, token, chat_id, tg_user, int(data[6:]))
        return True
    if data.startswith("topup_ok_") or data.startswith("topup_no_"):
        if not is_admin:
            await answer_callback(token, cb_id, "⛔ فقط ادمین")
            return True
        approve = data.startswith("topup_ok_")
        rid = data.split("_", 2)[-1]
        req = await topup_decide(store, rid, approve, by="admin-chat")
        await answer_callback(token, cb_id, "✅ تأیید شد" if req and approve else ("❌ رد شد" if req else "نامعتبر"))
        return True
    return False
