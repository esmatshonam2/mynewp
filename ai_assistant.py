"""ALOO PANEL ULTIMATE — AI Assistant engine (Phase 7).

A rule-based analytical assistant that ONLY reports computed facts from the
real panel database (users, traffic, servers, xray, system, audit). It makes
no external calls, needs no API keys, and never invents data: every number in
every reply comes from `db` / psutil at answer time.

The module is deliberately isolated (like a Phase-8 plugin) so a future LLM
backend can replace `answer()` while keeping the same response contract:

  answer(db, text, lang_hint) -> {
      "reply": str,            # ready-to-display text (fa or en)
      "lang": "fa"|"en",
      "intent": str,           # detected intent code
      "cards": [ ... ],        # optional structured data for rich rendering
      "suggest": [str,...],    # follow-up question keys (i18n resolved by UI)
  }

  analyze(db) -> [ {"severity": "critical|warning|info", "code": str,
                    "params": {...}} ]   # proactive findings, i18n by UI
"""
import time

from core import users as core_users


def detect_lang(text: str) -> str:
    for ch in (text or ""):
        if "\u0600" <= ch <= "\u06FF":
            return "fa"
    return "en"


def _gb(b) -> str:
    try:
        return f"{float(b or 0) / 1024**3:.2f}GB"
    except Exception:
        return "0GB"


def _days_left(exp):
    if not exp:
        return None
    return (float(exp) - time.time()) / 86400


# ---------------------------------------------------------------- findings
def analyze(db, cpu=None, mem=None) -> list:
    """Proactive health findings from real data. Pure function of db."""
    out = []
    inbounds = db.get("inbounds") or []
    s = db.get("settings") or {}
    try:
        buckets = core_users.summarize(
            inbounds, warn_days=int(s.get("expiry_warn_days") or 3))
    except Exception:
        buckets = {}
    if buckets.get("expired"):
        out.append({"severity": "critical", "code": "users_expired",
                    "params": {"n": buckets["expired"]}})
    if buckets.get("quota_reached"):
        out.append({"severity": "critical", "code": "users_quota",
                    "params": {"n": buckets["quota_reached"]}})
    if buckets.get("near_expiry"):
        out.append({"severity": "warning", "code": "users_near_expiry",
                    "params": {"n": buckets["near_expiry"]}})
    off = [x.get("name", x.get("id")) for x in (db.get("servers") or [])
           if x.get("enabled", True) and x.get("online") is False]
    if off:
        out.append({"severity": "critical", "code": "servers_offline",
                    "params": {"n": len(off), "names": ", ".join(off[:3])}})
    if cpu is not None and cpu >= 85:
        out.append({"severity": "warning", "code": "high_cpu",
                    "params": {"v": round(cpu, 1)}})
    if mem is not None and mem >= 90:
        out.append({"severity": "warning", "code": "high_mem",
                    "params": {"v": round(mem, 1)}})
    if not (s.get("backup_enabled")):
        out.append({"severity": "info", "code": "backup_off", "params": {}})
    elif not db.get("backups"):
        out.append({"severity": "warning", "code": "backup_none", "params": {}})
    if not (s.get("telegram_bot_token") or "").strip():
        out.append({"severity": "info", "code": "telegram_off", "params": {}})
    dis = buckets.get("disabled", 0)
    if dis and buckets.get("total"):
        out.append({"severity": "info", "code": "disabled_pile",
                    "params": {"n": dis}})
    return out


# ---------------------------------------------------------------- intents
def _has(text: str, *words) -> bool:
    t = (text or "").lower()
    return any(w.lower() in t for w in words)


def detect_intent(text: str) -> str:
    import re as _re
    t = (text or "").strip().lower()
    if not t:
        return "help"
    # NOTE: short English greetings use word boundaries — "which" contains "hi".
    if (_re.search(r"\b(hi|hello|hey|help)\b", t)
            or _has(t, "سلام", "راهنما", "چیکار", "what can you")):
        # greetings that also ask for status go to briefing
        if _has(t, "وضعیت", "خلاصه", "status", "summary", "چه خبر", "اوضاع", "health", "brief"):
            return "briefing"
        return "help"
    if _has(t, "وضعیت", "خلاصه", "چه خبر", "اوضاع", "status", "summary", "health", "brief", "گزارش کلی"):
        return "briefing"
    # NOTE: "top" is checked before cpu/memory on purpose — the word
    # "پرمصرف" contains the substring "رم" which would misfire memory.
    if _has(t, "پر مصرف", "پرمصرف", "top", "بیشترین مصرف", "most used", "highest usage"):
        return "top"
    if _has(t, "تمام", "سقف حجم", "quota", "limit reached", "اتمام حجم"):
        return "quota"
    if _has(t, "انقضا", "expire", "expiry", "منقضی", "تمام شدن", "نزدیک"):
        return "expiry"
    if _has(t, "سرور", "server", "load", "لود", "کدام سرور"):
        return "servers"
    if _has(t, "ترافیک", "traffic", "مصرف کل", "دانلود", "آپلود", "download", "upload", "امروز", "today"):
        return "traffic"
    if _has(t, "cpu", "سی‌پی‌یو", "پردازنده", "processor"):
        return "cpu"
    if _has(t, "ram", "حافظه", "مموری") or " رم " in f" {t} ":
        return "memory"
    if _has(t, "xray", "ایکس‌ری", "موتور"):
        return "xray"
    if _has(t, "بکاپ", "backup", "نسخه پشتیبان"):
        return "backup"
    if _has(t, "تلگرام", "telegram", "ربات", "bot"):
        return "telegram"
    if _has(t, "هشدار", "alert", "اعلان", "notification", "مشکل", "problem", "error", "خطا"):
        return "alerts"
    if _has(t, "کاربر", "user", "یوزر", "وضعیت"):
        return "users"
    return "lookup_or_unknown"


def _find_named(db, text: str):
    """Try to match an inbound/server name inside the message."""
    t = (text or "").lower()
    for ib in db.get("inbounds") or []:
        name = (ib.get("name") or "").strip()
        if name and len(name) >= 2 and name.lower() in t:
            return ("user", ib)
    for sv in db.get("servers") or []:
        name = (sv.get("name") or "").strip()
        if name and len(name) >= 2 and name.lower() in t:
            return ("server", sv)
    return (None, None)


def _user_card(ib) -> dict:
    used = (ib.get("used_up") or 0) + (ib.get("used_down") or 0)
    q = ib.get("quota_gb") or 0
    return {"uid": ib.get("uid"), "name": ib.get("name"),
            "used": used, "quota_gb": q,
            "remaining": (max(0, q * 1024**3 - used) if q > 0 else None),
            "expire_at": ib.get("expire_at"), "enabled": bool(ib.get("enabled", True))}


# ---------------------------------------------------------------- answer
def answer(db, text: str, cpu=None, mem=None, lang_hint: str | None = None) -> dict:
    lang = lang_hint or detect_lang(text)
    fa = lang == "fa"
    intent = detect_intent(text)
    inbounds = db.get("inbounds") or []
    s = db.get("settings") or {}
    try:
        buckets = core_users.summarize(inbounds, warn_days=int(s.get("expiry_warn_days") or 3))
    except Exception:
        buckets = {}

    def top_users(n=5):
        rows = sorted(inbounds, key=lambda x: (x.get("used_up") or 0) + (x.get("used_down") or 0),
                      reverse=True)[:n]
        return [_user_card(x) for x in rows]

    cards: list = []
    suggest = ["ai_q_health", "ai_q_top", "ai_q_quota", "ai_q_servers"]

    if intent == "help":
        reply = ("👋 من دستیار ALOO هستم و فقط از روی داده‌ی واقعی پنل جواب می‌دم.\n"
                 "مثلاً بپرس: «وضعیت کلی چطوره؟» «چرا CPU بالاست؟» «کدوم سرور لود بیشتری داره؟» "
                 "«کیا نزدیک اتمام حجمن؟» «پرمصرف‌ترین‌ها کین؟»" if fa else
                 "👋 I'm the ALOO assistant and only answer from real panel data.\n"
                 "Try: overall status, CPU load, busiest server, quota warnings, top users.")
    elif intent == "briefing":
        total = buckets.get("total", 0)
        ups = (db.get("stats") or {}).get("total_up", 0) + (db.get("stats") or {}).get("total_down", 0)
        findings = analyze(db, cpu, mem)
        crit = sum(1 for f in findings if f["severity"] == "critical")
        warn = sum(1 for f in findings if f["severity"] == "warning")
        if fa:
            reply = (f"📊 خلاصه وضعیت:\n👥 کاربران: {total} (فعال {buckets.get('active', 0)}، "
                     f"منقضی {buckets.get('expired', 0)}، سقف حجم {buckets.get('quota_reached', 0)})\n"
                     f"📦 ترافیک کل: {_gb(ups)}\n"
                     f"🚨 یافته‌ها: {crit} بحرانی، {warn} هشدار")
        else:
            reply = (f"📊 Briefing:\n👥 Users: {total} (active {buckets.get('active', 0)}, "
                     f"expired {buckets.get('expired', 0)}, quota-hit {buckets.get('quota_reached', 0)})\n"
                     f"📦 Total traffic: {_gb(ups)}\n🚨 Findings: {crit} critical, {warn} warnings")
        cards = [{"type": "findings", "items": findings}]
        suggest = ["ai_q_cpu", "ai_q_top", "ai_q_alerts"]
    elif intent == "cpu":
        v = cpu if cpu is not None else -1
        if fa:
            if v < 0:
                reply = "CPU الان اندازه‌گیری نشد؛ صفحه مانیتور زنده را باز کن."
            elif v >= 85:
                top = top_users(3)
                names = "، ".join(x["name"] for x in top) if top else "—"
                reply = (f"🔥 CPU بالاست: {v:.1f}٪.\nعلت‌های محتمل (از روی داده): ترافیک همزمان بالا یا پردازش xray.\n"
                         f"پرمصرف‌ترین‌ها: {names}\nپیشنهاد: نمودار ساعتی و مانیتور زنده را چک کن؛ اگر سرور ریموت داری، best-server را ببین.")
            else:
                reply = f"✅ CPU نرمال است: {v:.1f}٪. جای نگرانی نیست."
        else:
            reply = f"CPU is {v:.1f}%" if v >= 0 else "CPU not measured right now."
        cards = [{"type": "metric", "metric": "cpu", "value": v}] if v >= 0 else []
    elif intent == "memory":
        v = mem if mem is not None else -1
        reply = (f"🧠 حافظه: {v:.1f}٪" + (" ⚠️ بالاست" if v >= 90 else " ✅ نرمال") if fa
                 else f"🧠 Memory: {v:.1f}%" if v >= 0 else "Memory not measured.")
    elif intent == "top":
        top = top_users(5)
        if not top:
            reply = "کاربری وجود ندارد." if fa else "No users yet."
        else:
            lines = [f"{i+1}. {x['name']} — {_gb(x['used'])}" for i, x in enumerate(top)]
            reply = ("🏆 پرمصرف‌ترین‌ها:\n" + "\n".join(lines) if fa else
                     "🏆 Top users:\n" + "\n".join(lines))
        cards = [{"type": "users", "items": top}]
    elif intent == "quota":
        hit = [x for x in inbounds
               if (x.get("quota_gb") or 0) > 0
               and (x.get("used_up") or 0) + (x.get("used_down") or 0) >= (x.get("quota_gb") or 0) * 1024**3]
        warn_pct = float(s.get("quota_warn_percent") or 80)
        near = [x for x in inbounds
                if (x.get("quota_gb") or 0) > 0
                and (x.get("used_up") or 0) + (x.get("used_down") or 0) >= (x.get("quota_gb") or 0) * 1024**3 * warn_pct / 100
                and x not in hit]
        cards = [{"type": "users", "items": [_user_card(x) for x in (hit + near)[:10]]}]
        if fa:
            reply = f"📊 سقف حجم: {len(hit)} کاربر تمام کرده، {len(near)} نفر نزدیک‌اند (آستانه {warn_pct:g}٪)."
        else:
            reply = f"📊 Quota: {len(hit)} hit the limit, {len(near)} near it ({warn_pct:g}% threshold)."
    elif intent == "expiry":
        wd = int(s.get("expiry_warn_days") or 3)
        now = time.time()
        exp = [x for x in inbounds if x.get("expire_at") and x["expire_at"] <= now]
        near = [x for x in inbounds if x.get("expire_at") and 0 < (x["expire_at"] - now) / 86400 <= wd]
        cards = [{"type": "users", "items": [_user_card(x) for x in (exp + near)[:10]]}]
        if fa:
            reply = f"⏳ انقضا: {len(exp)} منقضی، {len(near)} نفر در {wd} روز آینده."
        else:
            reply = f"⏳ Expiry: {len(exp)} expired, {len(near)} within {wd} days."
    elif intent == "servers":
        srvs = db.get("servers") or []
        on = [x for x in srvs if x.get("enabled", True) and x.get("online") is True]
        off = [x for x in srvs if x.get("enabled", True) and x.get("online") is False]
        # busiest by real load score
        scored = []
        for x in srvs:
            if x.get("enabled", True) and x.get("online") is True:
                m = x.get("metrics") or {}
                scored.append((x.get("name"), int(m.get("users") or 0) + float(m.get("cpu") or 0) / 2))
        scored.sort(key=lambda t: t[1], reverse=True)
        cards = [{"type": "servers", "items": [
            {"name": x.get("name"), "online": x.get("online"), "metrics": x.get("metrics") or {}} for x in srvs]}]
        if fa:
            busiest = f"پرلودترین: {scored[0][0]}" if scored else "سرور ریموتی نیست"
            reply = (f"🖥 سرورها: {len(on)} آنلاین، {len(off)} آفلاین (+ لوکال).\n{busiest}." +
                     (f"\n❌ آفلاین: {', '.join(x.get('name') for x in off)}" if off else ""))
        else:
            busiest = f"Busiest: {scored[0][0]}" if scored else "No remote servers"
            reply = f"🖥 Servers: {len(on)} online, {len(off)} offline (+ local).\n{busiest}."
    elif intent == "traffic":
        st = db.get("stats") or {}
        up, down = st.get("total_up", 0), st.get("total_down", 0)
        hourly = st.get("hourly") or []
        day = sum((h.get("up") or 0) + (h.get("down") or 0)
                  for h in hourly if h.get("t", 0) >= time.time() - 86400)
        reply = (f"📦 ترافیک کل: {_gb(up+down)} (⬆ {_gb(up)} / ⬇ {_gb(down)})\n🕐 ۲۴ ساعت اخیر: {_gb(day)}" if fa else
                 f"📦 Total: {_gb(up+down)} (⬆ {_gb(up)} / ⬇ {_gb(down)})\n🕐 Last 24h: {_gb(day)}")
    elif intent == "xray":
        reply = ("🔧 وضعیت موتور Xray را از ویوی «موتور Xray» ببین؛ اگر آفلاین است، دکمه ری‌استارت همان‌جاست." if fa else
                 "🔧 See the Xray view for engine status and restart.")
    elif intent == "backup":
        bl = db.get("backups") or []
        en = bool(s.get("backup_enabled"))
        if fa:
            reply = (f"💾 بکاپ خودکار {'فعال' if en else 'خاموش'} است؛ {len(bl)} snapshot موجود است." +
                     ("" if bl else " هنوز بکاپی گرفته نشده."))
        else:
            reply = f"💾 Auto backup is {'on' if en else 'off'}; {len(bl)} snapshots stored."
    elif intent == "telegram":
        tok = bool((s.get("telegram_bot_token") or "").strip())
        reply = ("🤖 ربات تلگرام " + ("توکن دارد" if tok else "توکن ندارد") +
                 (" و " + ("فعال" if s.get("telegram_enabled") else "خاموش") + " است." if fa else
                  (" and is " + ("on" if s.get("telegram_enabled") else "off") + ".")))
    elif intent == "alerts":
        findings = analyze(db, cpu, mem)
        cards = [{"type": "findings", "items": findings}]
        if not findings:
            reply = "🎉 هشداری نیست؛ همه‌چیز سالم است." if fa else "🎉 No alerts; all healthy."
        else:
            reply = (f"🚨 {len(findings)} یافته (جزئیات در مرکز اعلان‌ها)." if fa else
                     f"🚨 {len(findings)} findings (see Notification Center).")
    elif intent == "users":
        reply = (f"👥 {buckets.get('total', 0)} کاربر: فعال {buckets.get('active', 0)}، "
                 f"نزدیک انقضا {buckets.get('near_expiry', 0)}، منقضی {buckets.get('expired', 0)}، "
                 f"سقف حجم {buckets.get('quota_reached', 0)}، غیرفعال {buckets.get('disabled', 0)}." if fa else
                 f"👥 {buckets.get('total', 0)} users.")
        cards = [{"type": "users", "items": top_users(5)}]
    else:
        kind, obj = _find_named(db, text)
        if kind == "user":
            c = _user_card(obj)
            dl = _days_left(obj.get("expire_at"))
            exp_txt = "∞" if dl is None else ("❌" if dl <= 0 else f"{dl:.1f}d")
            rem = "∞" if c["remaining"] is None else _gb(c["remaining"])
            reply = (f"👤 {c['name']}: مصرف {_gb(c['used'])}/{c['quota_gb'] or '∞'}GB، "
                     f"باقی‌مانده {rem}، انقضا {exp_txt}، "
                     f"{'فعال ✅' if c['enabled'] else 'غیرفعال ⛔'}" if fa else
                     f"👤 {c['name']}: used {_gb(c['used'])}, left {rem}, expiry {exp_txt}.")
            cards = [{"type": "users", "items": [c]}]
            intent = "lookup_user"
        elif kind == "server":
            m = obj.get("metrics") or {}
            reply = (f"🖥 {obj.get('name')}: {'آنلاین ✅' if obj.get('online') else 'آفلاین ❌'}، "
                     f"{m.get('users', '?')} کاربر، CPU {m.get('cpu', '?')}٪" if fa else
                     f"🖥 {obj.get('name')}: {'online' if obj.get('online') else 'offline'}.")
            cards = [{"type": "servers", "items": [
                {"name": obj.get("name"), "online": obj.get("online"), "metrics": m}]}]
            intent = "lookup_server"
        else:
            reply = ("متوجه نشدم 🤔 — بپرس «وضعیت کلی»، «پرمصرف‌ترین‌ها»، «سرورها» یا اسم یک کاربر." if fa else
                     "Didn't get that 🤔 — try overall status, top users, servers, or a user name.")
            intent = "unknown"
            suggest = ["ai_q_health", "ai_q_top", "ai_q_servers"]
    return {"reply": reply, "lang": lang, "intent": intent, "cards": cards, "suggest": suggest}
