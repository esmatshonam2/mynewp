"""ALOO PANEL example plugin: extra host cards, computed live from psutil.

Contract: get_cards(db) -> [{"title": {"fa":..,"en":..}, "value": str, "hint": str}]
Any exception is swallowed by the registry; keep it dependency-free.
"""
import datetime
import time


def get_cards(db):
    import psutil
    cards = []
    try:
        boot = datetime.datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M")
        up_h = (time.time() - psutil.boot_time()) / 3600
        cards.append({
            "title": {"fa": "آپتایم هاست", "en": "Host uptime"},
            "value": f"{up_h:.1f}h",
            "hint": f"boot: {boot}",
        })
    except Exception:
        pass
    try:
        cards.append({
            "title": {"fa": "پردازش‌ها", "en": "Processes"},
            "value": str(len(psutil.pids())),
            "hint": "",
        })
    except Exception:
        pass
    try:
        if hasattr(psutil, "getloadavg"):
            la = psutil.getloadavg()
            cards.append({
                "title": {"fa": "میانگین بار", "en": "Load average"},
                "value": f"{la[0]:.2f} / {la[1]:.2f} / {la[2]:.2f}",
                "hint": "1m / 5m / 15m",
            })
    except Exception:
        pass
    return cards
