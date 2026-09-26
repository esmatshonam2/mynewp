"""ALOO PANEL ULTIMATE — core.servers (Phase 3).

Pure, testable math for multi-server management. No I/O, no framework.

Health formula (documented in docs/SERVERS.md, shown as tooltip in UI):
  start 100; offline -> 0
  cpu > 70          : -(cpu-70) * 1.5
  mem > 80          : -(mem-80) * 2
  disk > 90         : -(disk-90) * 3   (80..90 : -5)
  latency > 1000ms  : -20             (500..1000 : -10)
  xray != online    : -30  (mock/unknown : -10)
  uptime < 1h       : -5
  error_rate > 5%   : -(error_rate-5) * 4  (max -20)
  packet_loss > 5%  : -10             (>15% : -20)
  clamp 0..100, rounded. Maintenance does NOT change the score —
  the MAINTENANCE state is displayed separately.

Load formula: load = 0.5*cpu + 0.3*mem + 0.2*min(100, connections).
All inputs are real polled metrics; None in -> None out.
"""
import re


def _num(v, default=None):
    try:
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def health_score(metrics: dict | None, online) -> int | None:
    if online is not True:
        return 0 if online is False else None
    m = metrics or {}
    cpu = _num(m.get("cpu"))
    mem = _num(m.get("mem"))
    disk = _num(m.get("disk_percent"))
    lat = _num(m.get("latency_ms"))
    err = _num(m.get("error_rate"), 0)
    pkt = _num(m.get("packet_loss"))
    if cpu is None and mem is None:
        return None
    score = 100.0
    if cpu is not None and cpu > 70:
        score -= (cpu - 70) * 1.5
    if mem is not None and mem > 80:
        score -= (mem - 80) * 2
    if disk is not None:
        if disk > 90:
            score -= (disk - 90) * 3
        elif disk > 80:
            score -= 5
    if lat is not None:
        if lat > 1000:
            score -= 20
        elif lat > 500:
            score -= 10
    xray = (m.get("xray") or "?")
    if xray == "mock" or xray == "?":
        score -= 10
    elif xray != "online":
        score -= 30
    up = _num(m.get("uptime_seconds"))
    if up is not None and up < 3600:
        score -= 5
    # error_rate: >5% penalizes, max -20
    if err is not None and err > 5:
        score -= min(20, (err - 5) * 4)
    # packet_loss: >5% penalizes
    if pkt is not None:
        if pkt > 15:
            score -= 20
        elif pkt > 5:
            score -= 10
    return max(0, min(100, round(score)))


def load_pct(metrics: dict | None) -> float | None:
    m = metrics or {}
    cpu = _num(m.get("cpu"))
    mem = _num(m.get("mem"))
    conns = _num(m.get("active_connections"), 0) or 0
    if cpu is None and mem is None:
        return None
    return round(0.5 * (cpu or 0) + 0.3 * (mem or 0) + 0.2 * min(100.0, conns), 1)


def _ver_tuple2(v: str):
    parts = re.findall(r"\d+", v or "")
    if len(parts) < 2:
        return None
    try:
        return (int(parts[0]), int(parts[1]))
    except ValueError:
        return None


def version_compat(panel_v: str, agent_v: str) -> str:
    """compatible | warning | incompatible | unknown (documented in SERVERS.md)."""
    pv, av = _ver_tuple2(panel_v), _ver_tuple2(agent_v)
    if not pv or not av:
        return "unknown"
    if pv[0] != av[0]:
        return "incompatible"
    if pv[1] != av[1]:
        return "warning"
    return "compatible"
