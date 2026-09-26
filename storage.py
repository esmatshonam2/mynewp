"""
StanNG - Persistent JSON storage layer.
Single-file, dependency-free storage engine (no external DB required).
Thread/async safe via an in-process lock + atomic file writes.
"""
import json
import os
import secrets
import hashlib
import time
import asyncio
from typing import Any, Dict

DATA_DIR = os.environ.get("STANNG_DATA_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
DB_PATH = os.path.join(DATA_DIR, "db.json")

_lock = asyncio.Lock()

def _default_plans():
    now = time.time()
    return [
        {"id": "plan_bronze", "name": "Bronze", "traffic_gb": 50,
         "duration_days": 30, "device_limit": 1, "price": 0,
         "description": "50GB · 30 days · 1 device",
         "enabled": True, "created_at": now},
        {"id": "plan_silver", "name": "Silver", "traffic_gb": 150,
         "duration_days": 30, "device_limit": 3, "price": 0,
         "description": "150GB · 30 days · 3 devices",
         "enabled": True, "created_at": now},
        {"id": "plan_gold", "name": "Gold", "traffic_gb": 500,
         "duration_days": 60, "device_limit": 5, "price": 0,
         "description": "500GB · 60 days · 5 devices",
         "enabled": True, "created_at": now},
    ]


DEFAULT_DB: Dict[str, Any] = {
    "schema_version": 12,  # v12: enhanced Phase 3 — agent, error_rate, events, tags
    "admin": None,          # {"username": str, "password_hash": str, "salt": str, "created_at": ts}
    "secret_key": None,     # generated on first run, used to sign session cookies
    "settings": {
        "lang": "fa",
        "theme": "dark",
        "public_domain": "",         # optional override; else derived from request Host header
        "keep_alive": True,
        # NOTE: app_version is intentionally NOT stored here. It must always
        # reflect the code actually running on disk (main.py's APP_VERSION),
        # never a stale value frozen into db.json from an earlier install —
        # that mismatch used to make the dashboard show the wrong "Current"
        # version after every update.
        # ---- advanced config defaults (applied to newly generated VLESS links) ----
        "default_fingerprint": "chrome",     # chrome | ios | firefox | edge | random
        "default_alpn": "http/1.1",          # http/1.1 | h2,http/1.1 | h3,h2,http/1.1
        "sni_override": "",                  # optional domain-fronting SNI; blank = use host
        "fragment_enabled": True,
        "fragment_packets": "tlshello",
        "fragment_length": "10-30",
        "fragment_interval": "10-20",
        # ---- Telegram bot integration ----
        "telegram_bot_token": "",
        "telegram_chat_id": "",          # admin chat id / channel id
        "telegram_enabled": False,
        "notify_new_user": True,
        "notify_quota": True,
        "notify_expiry": True,
        "notify_login": False,
        # ---- panel extras ----
        "panel_name": "",
        "sub_remark_prefix": "ALOO",
        "auto_disable_exhausted": True,  # exclude exhausted/expired users from xray config
        "quota_warn_percent": 80,
        "expiry_warn_days": 3,
        # ---- Phase 6/6b: backups, maintenance, shop ----
        "backup_enabled": False,
        "backup_hour": 4,
        "backup_minute": 0,
        "backup_keep": 7,
        "backup_send_telegram": True,
        "maintenance_enabled": False,
        "maintenance_message": "پنل در حال تعمیرات است. لطفاً دقایقی دیگر مراجعه کنید.",
        "shop_enabled": True,
        "support_username": "ITSESMAT",
        "shop_test_gb": 1,
        "shop_test_days": 1,
        "referral_bonus": 10000,
        "bot_username": "",
        "last_backup_day": "",
        "role_overrides": {},
        # ---- Phase 3: heartbeat / monitoring / load ----
        "server_offline_after": 90,
        "server_poll_interval": 30,
        "lb_strategy": "least_load",
        "history_retention_days": 7,
        "alert_cpu": 80,
        "alert_mem": 85,
        "alert_disk": 90,
        "alert_latency_ms": 1000,
        "alert_conns": 200,
        # ---- Phase 3 enhanced: agent, heartbeat ----
        "agent_auth_secret": "",
        "heartbeat_threshold": 90,
    },
    "inbounds": [],       # list of inbound/user dicts
    "plans": _default_plans(),  # plan/package templates (Bronze/Silver/Gold seeds)
    "servers": [],        # remote panel nodes (multi-server federation)
    "server_groups": [],  # {id, name, description, server_ids[]}
    "server_alerts": [],  # {id, server_id, type, severity, value, threshold, status, opened_at, resolved_at}
    "metrics_history": [],  # capped samples {server_id, ts, cpu, mem, disk, net_up, net_down, conns, latency, health}
    "server_events": [],    # {id, server_id, type, message, ts, severity} — dedicated event timeline
    "assignments": [],    # cross-server user placements {id, server_id, remote_uid, name, ...}
    "admins": [],         # extra admins: {id, username, hash, salt, role, enabled, created_at, totp_secret}
    "backups": [],        # snapshots: [{id, ts, file, size, auto}]
    "bot_users": [],      # shop customers: [{tg_id, username, inbound_uids, balance, referrals, ...}]
    "topup_requests": [],  # wallet top-ups: [{id, tg_id, amount, status, ts}]
    "api_tokens": [],     # [{"id": str, "name": str, "prefix": str, "hash": sha256, "created_at": ts, "last_used": ts|None, "note": str}]
    "audit_log": [],      # [{"ts": float, "actor": str, "action": str, "detail": str}]
    "notifications": [],  # [{"id": str, "ts": float, "severity": str, "code": str, "params": {}, "read": bool}]
    "notified": {},       # uid -> {"quota": bool, "expiry": bool} to avoid spam
    "stats": {
        "started_at": time.time(),
        "total_up": 0,
        "total_down": 0,
        "hourly": []       # [{"t": ts, "up": n, "down": n}]
    },
    "login_attempts": {}  # ip -> {"count": n, "locked_until": ts}
}


def _atomic_write(path: str, data: str):
    tmp_path = f"{path}.tmp-{secrets.token_hex(4)}"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def load_db() -> Dict[str, Any]:
    _ensure_dir()
    changed = False
    if not os.path.exists(DB_PATH):
        db = json.loads(json.dumps(DEFAULT_DB))
        db["secret_key"] = secrets.token_hex(32)
        changed = True
    else:
        try:
            with open(DB_PATH, "r", encoding="utf-8") as f:
                db = json.load(f)
        except (json.JSONDecodeError, OSError):
            db = json.loads(json.dumps(DEFAULT_DB))
            db["secret_key"] = secrets.token_hex(32)
            changed = True
    # merge defaults for forward-compat (new fields added over time)
    for k, v in DEFAULT_DB.items():
        if k not in db:
            db[k] = v
            changed = True
    if isinstance(db.get("settings"), dict):
        for k, v in DEFAULT_DB["settings"].items():
            if k not in db["settings"]:
                db["settings"][k] = v
                changed = True
        # Migration: drop any stale app_version or ota_repo previously persisted
        if "app_version" in db["settings"]:
            del db["settings"]["app_version"]
            changed = True
        if "ota_repo" in db["settings"]:
            del db["settings"]["ota_repo"]
            changed = True
    if not db.get("secret_key"):
        db["secret_key"] = secrets.token_hex(32)
        changed = True

    # ------------------- v3 migration: remove "addresses" (clean-IP) ----------------
    if "addresses" in db:
        del db["addresses"]
        changed = True
        # Optionally update schema_version to 3 if still lower
    if db.get("schema_version", 1) < 3:
        db["schema_version"] = 3
        changed = True
    # ------------------- v4 migration: telegram / tokens / audit ----------------
    for _k, _v in (("api_tokens", []), ("audit_log", []), ("notified", {}), ("plans", _default_plans()),
                   ("servers", []), ("notifications", []), ("admins", []), ("backups", []),
                   ("bot_users", []), ("topup_requests", []), ("server_groups", []),
                   ("server_alerts", []), ("metrics_history", []), ("assignments", [])):
        if _k not in db:
            db[_k] = _v
            changed = True
    if db.get("schema_version", 1) < 4:
        db["schema_version"] = 4
        changed = True
    # ------------------- v5 migration: per-user subscription tokens ----------------
    # Every user gets a stable, rotatable sub_token. Legacy /sub/{uid} URLs
    # keep working (resolved by uid OR token); canonical links use the token.
    for ib in db.get("inbounds", []):
        if not isinstance(ib, dict):
            continue
        if not ib.get("sub_token"):
            ib["sub_token"] = secrets.token_hex(12)
            changed = True
        if "sub_enabled" not in ib:
            ib["sub_enabled"] = True
            changed = True
    if db.get("schema_version", 1) < 5:
        db["schema_version"] = 5
        changed = True
    # ------------------- v6: servers registry ----------------
    if "load_balancer_enabled" not in db.get("settings", {}):
        db.setdefault("settings", {})["load_balancer_enabled"] = True
        changed = True
    if db.get("schema_version", 1) < 6:
        db["schema_version"] = 6
        changed = True
    # ------------------- v7: notification center ----------------
    s = db.setdefault("settings", {})
    if "notify_server" not in s:
        s["notify_server"] = True
        changed = True
    if db.get("schema_version", 1) < 7:
        db["schema_version"] = 7
        changed = True
    # ------------------- v8: first admin becomes owner in admins[] ----------------
    # Legacy db["admin"] sessions keep working: same username + same hash prefix.
    if not db.get("admins") and db.get("admin"):
        a = db["admin"]
        db["admins"] = [{
            "id": "admin_" + secrets.token_hex(6),
            "username": a.get("username", "admin"),
            "password_hash": a.get("password_hash", ""),
            "salt": a.get("salt", ""),
            "role": "owner",
            "enabled": True,
            "created_at": a.get("created_at") or time.time(),
            "totp_secret": a.get("totp_secret"),
        }]
        changed = True
    if db.get("schema_version", 1) < 8:
        db["schema_version"] = 8
        changed = True
    # ------------------- v9: backups / maintenance / shop defaults ----------------
    s = db.setdefault("settings", {})
    _defaults9 = {
        "backup_enabled": False, "backup_hour": 4, "backup_minute": 0,
        "backup_keep": 7, "backup_send_telegram": True,
        "maintenance_enabled": False,
        "maintenance_message": "پنل در حال تعمیرات است. لطفاً دقایقی دیگر مراجعه کنید.",
        "shop_enabled": True,
        "support_username": "ITSESMAT",
        "shop_test_gb": 1, "shop_test_days": 1,
        "referral_bonus": 10000,
        "last_backup_day": "",
    }
    for _k, _v in _defaults9.items():
        if _k not in s:
            s[_k] = _v
            changed = True
    for _p in db.get("plans", []):
        if isinstance(_p, dict) and "price" not in _p:
            _p["price"] = 0
            changed = True
    if db.get("schema_version", 1) < 9:
        db["schema_version"] = 9
        changed = True
    # ------------------- v10: role permission overrides ----------------
    if "role_overrides" not in db.get("settings", {}):
        db.setdefault("settings", {})["role_overrides"] = {}
        changed = True
    if db.get("schema_version", 1) < 10:
        db["schema_version"] = 10
        changed = True
    # ------------------- v11: extended server model + phase-3 settings ----------------
    _srv_defaults = {
        "ip": "", "port": 443, "city": "", "provider": "", "stype": "panel",
        "os": "", "arch": "", "weight": 100, "maintenance": False,
        "latency_ms": None, "last_seen": None, "last_success": None,
        "version_compat": "unknown", "health": None, "load": None,
    }
    for _srv in db.get("servers", []):
        if not isinstance(_srv, dict):
            continue
        for _k, _v in _srv_defaults.items():
            if _k not in _srv:
                _srv[_k] = _v
                changed = True
    _s11 = db.setdefault("settings", {})
    _set11 = {
        "server_offline_after": 90, "server_poll_interval": 30,
        "lb_strategy": "least_load", "history_retention_days": 7,
        "alert_cpu": 80, "alert_mem": 85, "alert_disk": 90,
        "alert_latency_ms": 1000, "alert_conns": 200,
    }
    for _k, _v in _set11.items():
        if _k not in _s11:
            _s11[_k] = _v
            changed = True
    if db.get("schema_version", 1) < 11:
        db["schema_version"] = 11
        changed = True
    # ------------------- v12: enhanced Phase 3 — agent, error_rate, events, tags ----
    _srv_defaults_v12 = {
        "error_rate": 0.0, "packet_loss": None,
        "agent_secret": "", "agent_version": "", "tags": [],
    }
    for _srv in db.get("servers", []):
        if not isinstance(_srv, dict):
            continue
        for _k, _v in _srv_defaults_v12.items():
            if _k not in _srv:
                _srv[_k] = _v
                changed = True
    _s12 = db.setdefault("settings", {})
    _set12 = {"agent_auth_secret": "", "heartbeat_threshold": 90}
    for _k, _v in _set12.items():
        if _k not in _s12:
            _s12[_k] = _v
            changed = True
    if "server_events" not in db:
        db["server_events"] = []
        changed = True
    if db.get("schema_version", 1) < 12:
        db["schema_version"] = 12
        changed = True

    if changed:
        _atomic_write(DB_PATH, json.dumps(db, ensure_ascii=False, indent=2))
    return db


def save_db(db: Dict[str, Any]):
    _ensure_dir()
    _atomic_write(DB_PATH, json.dumps(db, ensure_ascii=False, indent=2))


class Store:
    """Async-safe accessor around the JSON db."""

    def __init__(self):
        self.db = load_db()

    async def get(self) -> Dict[str, Any]:
        async with _lock:
            return self.db

    async def mutate(self, fn):
        """fn(db) -> mutates db in place. Persists after."""
        async with _lock:
            fn(self.db)
            save_db(self.db)
            return self.db

    def get_sync(self) -> Dict[str, Any]:
        return self.db


store = Store()


# ---------- password hashing (stdlib only, no extra deps) ----------

def hash_password(password: str, salt: str = None) -> Dict[str, str]:
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 260_000)
    return {"hash": dk.hex(), "salt": salt}


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 260_000)
    return secrets.compare_digest(dk.hex(), expected_hash)
