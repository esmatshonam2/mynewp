# Monitoring & Alerts (Phase 3)

## Overview

ALOO PANEL Phase 3 adds real-time multi-server monitoring, server events
timeline, and configurable alert thresholds — all visible from the
dashboard UI.

## Monitoring view

Access: **Sidebar → Monitoring**

### Aggregate cards

| Card | Description |
|---|---|
| Online / Offline / Maintenance | Server counts by status |
| Active Alerts | Unresolved alert count |
| Avg Health | Mean health score across servers (0–100%) |
| Avg Load | Mean load percentage |
| Avg Latency | Mean latency in ms |
| Total Connections | Sum of active connections |

### Top servers table

Ranked by health, load, latency, or uptime (use the sort dropdown).

| Column | Description |
|---|---|
| Health | Color-coded pill (green ≥70, yellow ≥40, red <40) |
| Load | CPU/RAM composite percentage |
| CPU / RAM | Live values from last poll |
| Latency | Round-trip time in ms |
| Error Rate | Percentage of failed requests |
| Uptime | Duration since last restart |

### Traffic per server

| Column | Description |
|---|---|
| Status | Online/Offline indicator |
| Upload / Download | Total bytes since server start |
| Total | Upload + Download |
| Users | Active user count |

## Events timeline

Access: **Sidebar → Events**

Shows a chronological log of server events across all servers. Filter by
server using the dropdown. Events include:

- `server_added` — new server registered
- `server_updated` — server config changed
- `server_online` / `server_offline` — status transitions
- `maintenance_on` / `maintenance_off` — maintenance mode toggled

Each event shows server name, type, message, severity (info/warning/error),
and timestamp.

## Alert thresholds

Configured in **Settings → Alerts**:

| Threshold | Default | Triggers when |
|---|---|---|
| CPU | 80% | Server CPU exceeds threshold |
| Memory | 85% | Server RAM exceeds threshold |
| Disk | 90% | Server disk exceeds threshold |
| Latency | 1000ms | Server latency exceeds threshold |
| Connections | 200 | Active connections exceed threshold |

Alerts are stored in `server_alerts[]` and visible on the **Alerts** page.

## Agent heartbeat

An alternative to polling: remote servers can push metrics to the
controller panel using `POST /api/agent/heartbeat` with a Bearer token.

Setup:
1. Set **Agent Auth Secret** in Settings → Agent
2. Configure the remote agent to POST to `/api/agent/heartbeat` with the
   secret as Bearer token
3. Set **Heartbeat Threshold** (default: 90s) — servers that miss a
   heartbeat within this window are marked offline

## Health formula

```
score = 100
- cpu_penalty        (up to -20)
- mem_penalty        (up to -15)
- disk_penalty       (up to -15)
- latency_penalty    (up to -15)
- xray_penalty       (-10 mock / -25 real)
- uptime_penalty     (up to -10)
- error_rate_penalty (up to -20, if error_rate > 5%)
- packet_loss_penalty(up to -20, if packet_loss > 5%)
```

Clamped to [0, 100]. Servers in maintenance mode are excluded from
load-balancing rankings.
