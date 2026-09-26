# Configuration — environment variables

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8000` | Public web port (injected by Railway; nginx listens here) |
| `PANEL_PORT` | `10000` (`PORT` fallback) | Internal panel port |
| `STANNG_DATA_DIR` | `./data` (`/app/data` in Docker) | Persistent data dir (`db.json`, backups, xray config) |
| `PANEL_NAME` | `ALOO PANEL` | Displayed product name |
| `TELEGRAM_CONTACT` | `https://t.me/ITSESMAT` | Support link in UI |
| `XRAY_BIN` / `XRAY_CONFIG_PATH` | auto-detected | Override xray paths |
| `XRAY_ACCESS_LOG` | auto (`/var/log/xray/` or data dir) | Xray access log (per-user IPs); rotated at 5 MB |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | — (DB otherwise) | Override bot credentials; panel shows source `env` |

Everything else (panel settings, bot token, plans, users) lives in the
database and is edited from the UI (Settings view). Secrets are never
hard-coded: the session secret is generated into `db.json` on first run;
use **Sessions → Revoke All** to rotate it.

## Database schema (Phase 3 — v12)

The database now includes:
- `server_events[]` — event timeline `{id, server_id, server_name, type, message, ts, severity}`
- Per-server fields: `error_rate`, `packet_loss`, `agent_secret`, `agent_version`, `tags[]`
- Settings: `agent_auth_secret`, `heartbeat_threshold` (30–600s)

## Settings (UI — Settings view)

### Agent / Heartbeat (Phase 3)
| Setting | Default | Purpose |
|---|---|---|
| `agent_auth_secret` | `""` | Shared secret for agent heartbeat auth (Bearer token) |
| `heartbeat_threshold` | `90` | Seconds after which a server is considered offline (clamped 30–600) |

### Alert Thresholds (Phase 3)
| Setting | Default | Purpose |
|---|---|---|
| `alert_cpu` | `80` | CPU % threshold for alerts |
| `alert_mem` | `85` | RAM % threshold for alerts |
| `alert_disk` | `90` | Disk % threshold for alerts |
| `alert_latency_ms` | `1000` | Latency (ms) threshold for alerts |
| `alert_conns` | `200` | Connections threshold for alerts |

### Monitoring (Phase 3)
| Setting | Default | Purpose |
|---|---|---|
| `server_offline_after` | `90` | Seconds before marking server offline |
| `server_poll_interval` | `30` | Seconds between metric polls |
| `lb_strategy` | `least_load` | Load-balancer strategy |
| `history_retention_days` | `7` | Days to keep metrics history |
