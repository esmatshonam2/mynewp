"""ALOO PANEL ULTIMATE — plugin registry (Phase 8).

Scans `plugins/*/manifest.json` and returns the list of installed
extensions. Plugins are admin-installed code (trusted): each plugin may
ship an optional `widget.py` exposing:

    def get_cards(db: dict) -> list[dict]

where each card is {"title": {"fa":..,"en":..} | str, "value": str, "hint": str}.
`load_widgets(db)` imports every *enabled* plugin's widget in isolation
(per-plugin try/except) and returns live cards for the Extensions view.

manifest.json schema:
  {"id": "my-plugin", "name": "My Plugin", "version": "1.0.0",
   "author": "...", "description": "...", "enabled": true}
"""
import importlib
import json
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _manifest_path(pid: str):
    return os.path.join(BASE_DIR, pid, "manifest.json")


def list_plugins():
    out = []
    try:
        entries = sorted(os.listdir(BASE_DIR))
    except OSError:
        return out
    for name in entries:
        if name.startswith(("_", ".")) or not _ID_RE.match(name):
            continue
        mpath = _manifest_path(name)
        if not os.path.isfile(mpath):
            continue
        try:
            with open(mpath, "r", encoding="utf-8") as f:
                m = json.load(f)
            if not isinstance(m, dict) or not m.get("id"):
                continue
            out.append({
                "id": str(m.get("id"))[:64],
                "name": str(m.get("name") or m.get("id"))[:80],
                "version": str(m.get("version") or "0.0.0")[:32],
                "author": str(m.get("author") or "")[:80],
                "description": str(m.get("description") or "")[:300],
                "enabled": bool(m.get("enabled", True)),
                "has_widget": os.path.isfile(os.path.join(BASE_DIR, name, "widget.py")),
            })
        except Exception:
            continue
    return out


def set_enabled(pid: str, enabled: bool):
    """Persist the enabled flag inside the plugin manifest. Returns the manifest."""
    if not _ID_RE.match(pid or ""):
        raise ValueError("bad-id")
    mpath = _manifest_path(pid)
    if not os.path.isfile(mpath):
        raise FileNotFoundError(pid)
    with open(mpath, "r", encoding="utf-8") as f:
        m = json.load(f)
    if not isinstance(m, dict):
        raise ValueError("bad-manifest")
    m["enabled"] = bool(enabled)
    tmp = mpath + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=2)
    os.replace(tmp, mpath)
    return m


def load_widgets(db) -> list:
    """Call get_cards(db) of every enabled plugin widget. Never raises."""
    cards = []
    for p in list_plugins():
        if not p["enabled"] or not p["has_widget"]:
            continue
        pid = p["id"]
        if not _ID_RE.match(pid):
            continue
        try:
            mod = importlib.import_module(f"plugins.{pid}.widget")
            fn = getattr(mod, "get_cards", None)
            if not callable(fn):
                continue
            items = fn(db) or []
            for c in items if isinstance(items, list) else []:
                if not isinstance(c, dict):
                    continue
                title = c.get("title", "")
                cards.append({
                    "plugin": pid,
                    "title": title if isinstance(title, dict) else {"fa": str(title), "en": str(title)},
                    "value": str(c.get("value", ""))[:120],
                    "hint": str(c.get("hint", ""))[:200],
                })
        except Exception:
            continue
    return cards
