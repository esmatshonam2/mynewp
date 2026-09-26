# Architecture

```
                ┌──────────── nginx :$PORT ────────────┐
                │  / → panel:10000   /vl-ws /vm-ws     │
Internet ──TLS──┤  /vl-xhttp → xray (10001/10002/10004)│
                └──────────────────────────────────────┘
main.py (FastAPI, ~3000 lines of routes)
 ├── core/            users classifier, security (RBAC/TOTP), shared rules
 ├── storage.py       JSON store + migrations (schema v9)
 ├── xray_manager.py  config gen, process mgmt, stats API
 ├── telegram_bot.py  admin commands + shop bot + notifiers
 ├── ai_assistant.py  rule-based analyst (real-data only)
 ├── plugins/         manifest registry + widget hooks (dynamic import)
 └── static|templates dependency-free UI (fa/en, dark/light)
```

Auth: signed cookies (7d) + TOTP; Bearer API tokens (SHA-256, owner
scope). RBAC enforced per endpoint (`require_perm`). Background loops:
traffic flush (5s), housekeeping/alerts (30s), keep-alive (10m),
telegram long-poll, server poll (30s), backup scheduler (30s).

Data flow for traffic: xray StatsService → deltas → per-user counters →
hourly buckets (72h) → dashboard/analytics/subs (`Subscription-Userinfo`).
