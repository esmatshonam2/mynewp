"""ALOO PANEL ULTIMATE — core.security.

Password policy + HTTP security headers. Framework-free so both the
FastAPI backend and (via the mirrored JS heuristic) the frontend can
share the same rules.
"""
import re

MIN_PASSWORD_LEN = 8
USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,32}$")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}

# ------------------------- Phase 5: roles & permissions -------------------------
ROLES = ("owner", "admin", "support", "viewer")

PERMISSIONS = (
    "users.read", "users.create", "users.edit", "users.delete",
    "servers.read", "servers.manage",
    "settings.manage", "telegram.manage", "security.manage",
    "analytics.read", "backup.manage", "admins.manage",
)

ROLE_PERMS = {
    "owner": {"*"},
    "admin": set(PERMISSIONS) - {"admins.manage"},
    "support": {"users.read", "users.create", "users.edit", "analytics.read"},
    "viewer": {"users.read", "servers.read", "analytics.read"},
}


def role_perms(role: str, overrides: dict | None = None) -> set:
    if overrides and isinstance(overrides, dict) and role in overrides:
        try:
            custom = set(overrides[role])
            return {p for p in custom if p in PERMISSIONS}
        except Exception:
            pass
    return set(ROLE_PERMS.get(role or "", set()))


def has_perm(role: str, perm: str, overrides: dict | None = None) -> bool:
    perms = role_perms(role, overrides)
    return perm in perms or "*" in perms


# ------------------------- Phase 5: TOTP 2FA (RFC 6238, stdlib only) -------------------------
def gen_totp_secret() -> str:
    import secrets as _secrets
    import base64 as _b64
    return _b64.b32encode(_secrets.token_bytes(20)).decode().rstrip("=")


def _hotp(secret: str, counter: int, digits: int = 6) -> str:
    import base64 as _b64
    import hashlib as _hl
    import hmac as _hm
    import struct as _st
    pad = "=" * (-len(secret) % 8)
    key = _b64.b32decode(secret.upper() + pad)
    msg = _st.pack(">Q", counter)
    mac = _hm.new(key, msg, _hl.sha1).digest()
    o = mac[-1] & 15
    code = _st.unpack(">I", mac[o:o + 4])[0] & 0x7FFFFFFF
    return str(code % (10 ** digits)).zfill(digits)


def verify_totp(secret: str, code: str, window: int = 1, step: int = 30) -> bool:
    import time as _t
    code = (code or "").strip()
    if not code.isdigit():
        return False
    t = int(_t.time()) // step
    for d in range(-window, window + 1):
        if _hotp(secret, t + d) == code:
            return True
    return False


def otpauth_url(secret: str, account: str, issuer: str = "ALOO PANEL") -> str:
    from urllib.parse import quote as _q
    return (f"otpauth://totp/{_q(issuer + ':' + account)}"
            f"?secret={secret}&issuer={_q(issuer)}&digits=6&period=30")


def valid_username(username: str) -> bool:
    return bool(USERNAME_RE.match(username or ""))


def password_strength(password: str) -> dict:
    """Score 0..4 + human-readable label key. Mirrors the JS meter."""
    pw = password or ""
    score = 0
    if len(pw) >= 8:
        score += 1
    if len(pw) >= 12:
        score += 1
    if re.search(r"[a-z]", pw) and re.search(r"[A-Z]", pw):
        score += 1
    if re.search(r"\d", pw) and re.search(r"[^a-zA-Z0-9]", pw):
        score += 1
    # common-password penalty
    if pw.lower() in ("password", "12345678", "qwerty123", "admin123", "aloo1234"):
        score = 0
    score = max(0, min(4, score))
    labels = ["pw_very_weak", "pw_weak", "pw_ok", "pw_strong", "pw_very_strong"]
    return {"score": score, "label": labels[score], "ok": len(pw) >= MIN_PASSWORD_LEN}
