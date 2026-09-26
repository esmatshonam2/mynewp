# Remote servers (multi-server federation)

The panel manages other ALOO PANELs through their real HTTP APIs —
no agents to install.

## Adding a server

1. On the **remote** panel: API Tokens → New Token (copy it once).
2. On this panel: Servers → Add Server → name, `https://remote-host`,
   the token, country. The connection is really tested on save
   (`/api/me` + `/stats` with the token); unreachable hosts are rejected.
3. Metrics (users, traffic, CPU/RAM/disk, network rates, version, xray,
   uptime, location) refresh every
   30s. After 2 consecutive failures the server is marked **offline**
   (audit + notification + optional Telegram alert).

The local panel always appears as **Local Server**. **Best server**
ranks candidates by `users + cpu/2` (toggle: load balancer switch).
Remote API tokens act with owner scope — create a dedicated token per
controller panel and revoke it when decommissioning.

## Health scoring (Phase 3)

Each server receives a 0–100 health score computed from:

| Factor | Deduction |
|---|---|
| CPU > 70% | up to −20 |
| RAM > 80% | up to −15 |
| Disk > 80% | up to −15 |
| Latency > 500ms | up to −15 |
| Xray not running | −10 (mock) / −25 (real) |
| Uptime < 99% | up to −10 |
| Error rate > 5% | up to −20 |
| Packet loss > 5% | up to −20 |

Servers in maintenance mode are excluded from load balancing.

## Server groups (Phase 3)

Organize servers into named groups (e.g. by region, provider, or tier).
Groups are used for filtering in the monitoring and events views.

## Monitoring view (Phase 3)

The **Monitoring** page shows:
- Aggregate cards: online/offline/maintenance counts, active alerts, averages
- **Top servers** table: ranked by health/load/latency/uptime (sortable)
- **Traffic per server**: upload/download/total/connections

## Events timeline (Phase 3)

The **Events** page shows a chronological event log across all servers,
filterable by server. Event types: `server_added`, `server_updated`,
`server_online`, `server_offline`, `maintenance_on`, `maintenance_off`.

## Agent heartbeat (Phase 3)

Remote servers can optionally report metrics via agent heartbeat
(`POST /api/agent/heartbeat`) using a shared secret configured in
Settings → Agent. This is an alternative to the polling-based approach.
