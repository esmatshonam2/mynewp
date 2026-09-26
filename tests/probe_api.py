#!/usr/bin/env python3
"""Live API probe: exercises every documented endpoint against a running panel.

Usage:  python tests/probe_api.py [base_url]
Writes a JSON report to tests/_probe_report.json
"""
import json
import sys
import time

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:10000"
USER = "admin"
PW = "AlooPanel#2026"

results = []


def rec(method, path, status, ok, note=""):
    results.append({"method": method, "path": path, "status": status,
                    "ok": ok, "note": note})
    flag = "OK " if ok else "FAIL"
    print(f"[{flag}] {method:6} {path:52} -> {status} {note}")


def main():
    c = httpx.Client(base_url=BASE, timeout=20.0, follow_redirects=False)

    # --- setup / login -------------------------------------------------
    r = c.get("/api/setup-status")
    if r.json().get("needs_setup"):
        r = c.post("/api/setup", json={"username": USER, "password": PW})
        rec("POST", "/api/setup", r.status_code, r.status_code == 200, r.text[:80])
    r = c.post("/api/login", json={"username": USER, "password": PW})
    rec("POST", "/api/login", r.status_code, r.status_code == 200, r.text[:80])
    if r.status_code != 200:
        print("!! cannot login, aborting")
        return

    # --- create test inbounds -----------------------------------------
    made = []
    for i in range(3):
        r = c.post("/api/inbounds", json={
            "name": f"probe-user-{i}", "quota_gb": 10 + i,
            "expire_days": 30, "max_connections": 2, "fp": "chrome", "note": "probe"})
        rec("POST", "/api/inbounds", r.status_code, r.status_code == 200, r.text[:70])
        if r.status_code == 200:
            j = r.json()
            made.append(j.get("uid") or (j.get("inbound") or {}).get("uid"))
    made = [m for m in made if m]

    uid = made[0] if made else "none"

    GETS = [
        "/api/me", "/stats", "/api/system", "/api/system/telemetry", "/api/live", "/api/online",
        "/api/inbounds", "/api/plans", "/api/servers", "/api/servers/best",
        "/api/servers/monitoring", "/api/servers/top", "/api/server-groups",
        "/api/server-events", "/api/alerts", "/api/notifications",
        "/api/analytics?range=today", "/api/ai/brief", "/api/audit",
        "/api/tokens", "/api/backups", "/api/roles", "/api/admins",
        "/api/security/overview", "/api/diagnostics/run",
        "/api/telegram/status", "/api/shop/overview", "/api/shop/users",
        "/api/shop/topups", "/api/plugins", "/api/plugins/widgets",
        "/api/xray/status", "/api/xray/config", "/api/xray/validate",
        "/api/ota/check",
        f"/api/inbounds/{uid}/links", f"/api/inbounds/{uid}/qr",
        f"/api/inbounds/{uid}/config-file", f"/api/inbounds/{uid}/sub",
        f"/api/servers/1/health", "/api/servers/1/metrics",
        "/api/servers/1/events", "/api/servers/1/alerts", "/api/servers/1/users",
        "/api/assignments",
    ]
    for p in GETS:
        try:
            r = c.get(p)
            ok = r.status_code < 500
            note = "" if ok else r.text[:90]
            if r.status_code == 404 and "not found" in r.text.lower():
                note = "404"
            rec("GET", p, r.status_code, ok, note)
        except Exception as e:
            rec("GET", p, 0, False, repr(e)[:90])

    # --- AI chat ------------------------------------------------------
    try:
        r = c.post("/api/ai/chat", json={"message": "how many users are active?"})
        rec("POST", "/api/ai/chat", r.status_code, r.status_code == 200, r.text[:70])
    except Exception as e:
        rec("POST", "/api/ai/chat", 0, False, repr(e)[:90])

    # --- inbound actions ----------------------------------------------
    if uid != "none":
        for act in ["toggle", "toggle", "clone", "extend", "reset-usage",
                    "regenerate", "regen-sub", "sub-toggle"]:
            body = {"days": 10} if act == "extend" else None
            try:
                r = c.post(f"/api/inbounds/{uid}/{act}", json=body)
                rec("POST", f"/api/inbounds/{{uid}}/{act}", r.status_code,
                    r.status_code < 500, r.text[:70])
            except Exception as e:
                rec("POST", f"/api/inbounds/{{uid}}/{act}", 0, False, repr(e)[:90])
        try:
            r = c.post(f"/api/inbounds/{uid}/adjust-traffic", json={"delta_gb": 5})
            rec("POST", "/api/inbounds/{uid}/adjust-traffic", r.status_code,
                r.status_code < 500, r.text[:70])
        except Exception as e:
            rec("POST", "/api/inbounds/{uid}/adjust-traffic", 0, False, repr(e)[:90])
        try:
            r = c.patch(f"/api/inbounds/{uid}", json={"name": "probe-renamed"})
            rec("PATCH", "/api/inbounds/{uid}", r.status_code, r.status_code < 500, r.text[:70])
        except Exception as e:
            rec("PATCH", "/api/inbounds/{uid}", 0, False, repr(e)[:90])
        try:
            r = c.get(f"/sub/{uid}")
            rec("GET", "/sub/{uid}", r.status_code, r.status_code < 500, r.text[:50])
        except Exception as e:
            rec("GET", "/sub/{uid}", 0, False, repr(e)[:90])

    # --- plans CRUD ---------------------------------------------------
    try:
        r = c.post("/api/plans", json={"name": "probe-plan", "traffic_gb": 50,
                                       "duration_days": 30, "price": 100000})
        rec("POST", "/api/plans", r.status_code, r.status_code < 500, r.text[:70])
        pid = r.json().get("id") if r.status_code == 200 else None
        if pid:
            r = c.patch(f"/api/plans/{pid}", json={"traffic_gb": 60})
            rec("PATCH", "/api/plans/{id}", r.status_code, r.status_code < 500, r.text[:70])
            r = c.delete(f"/api/plans/{pid}")
            rec("DELETE", "/api/plans/{id}", r.status_code, r.status_code < 500, r.text[:70])
    except Exception as e:
        rec("POST", "/api/plans", 0, False, repr(e)[:90])

    # --- settings -----------------------------------------------------
    try:
        r = c.post("/api/settings", json={"public_domain": "panel.local"})
        rec("POST", "/api/settings", r.status_code, r.status_code < 500, r.text[:70])
    except Exception as e:
        rec("POST", "/api/settings", 0, False, repr(e)[:90])

    # --- servers ------------------------------------------------------
    try:
        r = c.post("/api/servers", json={"name": "probe-srv", "address": "1.2.3.4",
                                         "port": 443, "enabled": True})
        rec("POST", "/api/servers", r.status_code, r.status_code < 500, r.text[:70])
        sid = r.json().get("id") if r.status_code == 200 else None
        if sid:
            r = c.post(f"/api/servers/{sid}/test")
            rec("POST", "/api/servers/{id}/test", r.status_code, r.status_code < 500, r.text[:70])
            r = c.post(f"/api/servers/{sid}/toggle-maintenance")
            rec("POST", "/api/servers/{id}/toggle-maintenance", r.status_code,
                r.status_code < 500, r.text[:70])
            r = c.delete(f"/api/servers/{sid}")
            rec("DELETE", "/api/servers/{id}", r.status_code, r.status_code < 500, r.text[:70])
    except Exception as e:
        rec("POST", "/api/servers", 0, False, repr(e)[:90])

    # --- pages --------------------------------------------------------
    for p in ["/", "/login", "/dashboard", "/setup", "/health"]:
        try:
            r = c.get(p)
            rec("GET", p, r.status_code, r.status_code < 500, "")
        except Exception as e:
            rec("GET", p, 0, False, repr(e)[:90])

    # --- cleanup ------------------------------------------------------
    for u in made:
        try:
            c.delete(f"/api/inbounds/{u}")
        except Exception:
            pass

    fails = [x for x in results if not x["ok"]]
    print("\n" + "=" * 70)
    print(f"TOTAL {len(results)}   PASS {len(results)-len(fails)}   FAIL {len(fails)}")
    print("=" * 70)
    for f in fails:
        print(f"  {f['method']:6} {f['path']:52} -> {f['status']} {f['note']}")

    with open("tests/_probe_report.json", "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)


if __name__ == "__main__":
    main()
