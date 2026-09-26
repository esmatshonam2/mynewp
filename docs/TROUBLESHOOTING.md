# Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `xray_config.json` FileNotFound on Windows | Fixed in v2+: config falls back to `./data/`. On servers the Dockerfile path is used. |
| Panel shows raw keys (`nav_plans`) | Stale browser cache. Static files are versioned (`?v=`); hard-refresh with `Ctrl+Shift+R`. |
| Locked out (`locked:N`) | 6 failed logins → 5-min IP lock. Wait, or unblock from another session (Security view), or delete the IP in `db.json → login_attempts` while stopped. |
| Telegram test fails | Wrong token/chat or bot never started (press Start on the bot). Poll state in Telegram view shows the last error. |
| Remote server rejected (502) | Remote unreachable, wrong token, or remote panel older than API used. Test `https://host/health` in a browser. |
| Sub links 403 | Subscription disabled for that user (Links → enable) or regenerated token (use the new link). |
| Empty traffic stats locally | Mock mode without xray binary; live counters need the binary + traffic. |
| High memory on tiny VPS | Normal for the free tier (~90% shown); alerts fire at 90%+. |
| After restore, users missing | Expected: restore rolls back to the snapshot time. |
| `forbidden` (403) as staff | Your role lacks the permission — ask an owner (Roles matrix in Security view). |

Still stuck? Run **Diagnostics** and read each check's hint.
