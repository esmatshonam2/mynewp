# API reference (roles in parentheses)

Auth: session cookie or `Authorization: Bearer <token>` (owner scope).
Error shape: `{"detail": "<code>"}`.

## System
- `GET /health` — `{status, version}` (public)
- `GET /stats` (analytics.read) — system + buckets + services + alerts + activity
- `GET /api/dashboard/summary` (analytics.read) — compact dashboard summary, traffic, servers, top users and alerts
- `GET /api/me` — session, role, settings
- `GET /api/system` (analytics.read) · `GET /api/system/telemetry` (analytics.read; live psutil/process/database measurements)
  · `GET /api/live` (analytics.read) · `GET /api/online` (analytics.read)

## Users & plans
- `GET/POST /api/inbounds` (read/create) · `PATCH/DELETE /api/inbounds/{uid}` (edit/delete)
- `GET /api/inbounds/export.csv` (users.read) — operational CSV export without UUID/subscription secrets
- `POST /api/inbounds/{uid}/{toggle,clone,extend,reset-usage,regenerate,adjust-traffic,apply-plan,regen-sub,sub-toggle}` (edit)
- `POST /api/inbounds/{bulk,reset-all-usage,cleanup}` (create/edit/delete)
- `GET /api/inbounds/{uid}/{links,qr,config-file,sub}` (read)
- `GET/POST/PATCH/DELETE /api/plans[/{id}]` (read/edit)

## Subscriptions (public, uid-or-token; 403 when disabled)
- `GET /sub/{ref}` · `/s/{ref}` · `/sub/{ref}/{json,clash,singbox}` · `/s/{ref}/json`
- `GET /api/status/{uid}` · `/status/{uid}` page · `/dns-query` (DoH)

## Servers / analytics / AI
- `GET/POST /api/servers` (read/manage) · `PATCH/DELETE /api/servers/{id}` (manage)
  · `POST /api/servers/{id}/test` (manage) · `GET /api/servers/best` (read)
- `GET /api/servers/{id}/health` (read) — health score for a server
- `GET /api/servers/{id}/metrics?range=24h` (read) — metrics history
- `GET /api/servers/{id}/events` (read) — server event timeline
- `GET /api/servers/{id}/alerts` (read) — server-specific alerts
- `POST /api/servers/{id}/toggle-maintenance` (manage) — toggle maintenance mode
- `GET /api/servers/monitoring` (read) — aggregated multi-server monitoring overview
- `GET /api/servers/top?sort_by=health|load|latency|uptime` (read) — top servers ranking
- `GET /api/analytics?range=today|yesterday|24h|7d|30d|custom&from_ts&to_ts` (analytics.read)
- `GET /api/ai/brief` · `POST /api/ai/chat {message}` (analytics.read)

## Telegram / shop / notifications
- `GET /api/telegram/status` · `POST /api/telegram/{save,test}` (manage)
- `GET /api/shop/{overview,users,topups}` · `POST /api/shop/{adjust-balance,topups/{id}/decide}` (telegram.manage)
- `GET /api/notifications` · `POST /api/notifications/read`

## Security / admins / xray / backups / system
- `POST /api/login` (+`need_2fa`) · `POST /api/2fa/login`
- `POST /api/change-password` · `GET /api/roles`
- `GET/POST /api/admins` · `PATCH/DELETE /api/admins/{id}` (admins.manage)
- `POST /api/2fa/{setup,verify,disable}` · `GET /api/2fa/qr`
- `GET /api/security/overview` · `POST /api/security/unblock` · `POST /api/sessions/revoke-all` (security.manage)
- `GET /api/xray/{status,config,validate}` (servers.read) · `POST /api/xray/{restart,start,stop}` (servers.manage)
- `GET/POST /api/backups` · `GET /api/backups/{id}/download` · `POST /api/backups/restore` · `DELETE /api/backups/{id}` (backup.manage)
- `GET /api/backup/{export}` · `POST /api/backup/import` (backup.manage)
- `GET /api/tokens` · `POST/DELETE /api/tokens[/{id}]` (security.manage)
- `GET /api/audit[?action=]` (security.manage) — includes per-entry `ip` (populated for auth flows) and `actions` list for the UI filter
- `GET /api/roles` · `PATCH /api/roles/{role} {permissions}` (admins.manage; `owner` locked to `*`)
- `GET /api/diagnostics/run` (security.manage)
- `GET /api/plugins[/widgets]` · `POST /api/plugins/{id}/toggle` (settings.manage)
- `POST /api/settings` (settings.manage) · `POST /api/ota/{check,update}` (settings.manage)

## Server groups (Phase 3)
- `GET /api/server-groups` (read) — list all groups
- `POST /api/server-groups` (manage) — create group `{name, description?, server_ids?}`
- `DELETE /api/server-groups/{id}` (manage) — delete group

## Server events (Phase 3)
- `GET /api/server-events?limit=200&server_id=` (read) — global event timeline across all servers

## Agent heartbeat (Phase 3)
- `POST /api/agent/heartbeat` (Bearer auth) — remote agent self-report `{server_id, cpu, mem, disk, net_up, net_down, conns, latency, xray_running, uptime}`
