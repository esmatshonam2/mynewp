"""ALOO PANEL ULTIMATE — core.users.

Single source of truth for user-status classification.
Priority: expired > quota_reached > disabled > near_expiry > active.

Both the backend (/stats buckets) and the frontend (filter chips) must
implement exactly this logic so counts always match the table.
"""
import time

# Status codes (stable API contract, used by frontend too)
ACTIVE = "active"
NEAR_EXPIRY = "near_expiry"
EXPIRED = "expired"
DISABLED = "disabled"
QUOTA_REACHED = "quota_reached"

ALL = (ACTIVE, NEAR_EXPIRY, EXPIRED, DISABLED, QUOTA_REACHED)


def used_bytes(ib) -> int:
    try:
        return int(ib.get("used_up") or 0) + int(ib.get("used_down") or 0)
    except Exception:
        return 0


def quota_bytes(ib) -> int:
    try:
        return int(float(ib.get("quota_gb") or 0) * 1024 ** 3)
    except Exception:
        return 0


def remaining_bytes(ib):
    """None means unlimited."""
    q = quota_bytes(ib)
    if q <= 0:
        return None
    return max(0, q - used_bytes(ib))


def classify(ib, warn_days: int = 3, now: float | None = None) -> str:
    """Return the status bucket for one inbound dict."""
    now = now if now is not None else time.time()
    expire_at = ib.get("expire_at")
    if expire_at:
        try:
            if now >= float(expire_at):
                return EXPIRED
        except Exception:
            pass
    q = quota_bytes(ib)
    if q > 0 and used_bytes(ib) >= q:
        return QUOTA_REACHED
    if not ib.get("enabled", True):
        return DISABLED
    # request-cap counts as disabled (no live traffic possible)
    try:
        if (ib.get("max_requests") or 0) > 0 and (ib.get("request_count") or 0) >= ib["max_requests"]:
            return DISABLED
    except Exception:
        pass
    if expire_at:
        try:
            if (float(expire_at) - now) / 86400 <= float(warn_days):
                return NEAR_EXPIRY
        except Exception:
            pass
    return ACTIVE


def summarize(inbounds, warn_days: int = 3, now: float | None = None) -> dict:
    """Count inbounds per bucket. Keys: total + every status in ALL."""
    now = now if now is not None else time.time()
    out = {"total": 0, ACTIVE: 0, NEAR_EXPIRY: 0, EXPIRED: 0, DISABLED: 0, QUOTA_REACHED: 0}
    for ib in inbounds or []:
        try:
            out[classify(ib, warn_days, now)] += 1
            out["total"] += 1
        except Exception:
            continue
    return out
