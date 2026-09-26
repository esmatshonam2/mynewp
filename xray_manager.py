import json
import os
import subprocess
import asyncio
import logging

XRAY_CONFIG_PATH = os.environ.get("XRAY_CONFIG_PATH") or (
    "/usr/local/bin/config.json" if os.path.isdir("/usr/local/bin") else
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "xray_config.json")
)
XRAY_BIN = os.environ.get("XRAY_BIN") or "/usr/local/bin/xray"

# Access log: source of per-user IPs + last-connection times.
# Xray access lines look like: 2026/01/01 10:00:00 1.2.3.4:5678 accepted tcp:... [email]
XRAY_ACCESS_LOG = os.environ.get("XRAY_ACCESS_LOG") or (
    "/var/log/xray/access.log" if os.path.isdir("/var/log/xray") else
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "xray_access.log")
)
ACCESS_LOG_MAX_BYTES = 5 * 1024 * 1024

xray_process = None
ip_cache = {}  # uid -> {"ips": [recent unique], "last": epoch|None}

def generate_xray_config(inbounds_data, log_level="warning"):
    clients_vless = []
    clients_vmess = []

    for ib in inbounds_data:
        if not ib.get("enabled", True):
            continue

        uuid = ib["uuid"]
        uid = ib["uid"]
        clients_vless.append({"id": uuid, "email": uid})
        clients_vmess.append({"id": uuid, "email": uid})

    if log_level not in ("debug", "info", "warning", "error", "none"):
        log_level = "warning"
    _rotate_access_log()
    config = {
        "log": {"loglevel": log_level, "access": XRAY_ACCESS_LOG},
        "dns": {
            "servers": [
                "https+local://1.1.1.1/dns-query",
                "https+local://8.8.8.8/dns-query",
                "1.1.1.1",
                "8.8.8.8",
                "localhost"
            ],
            "queryStrategy": "UseIPv4"
        },
        "api": {
            "tag": "api",
            "services": ["StatsService"]
        },
        "stats": {},
        "policy": {
            "levels": {
                "0": {
                    "statsUserUplink": True,
                    "statsUserDownlink": True
                }
            },
            "system": {
                "statsInboundUplink": True,
                "statsInboundDownlink": True
            }
        },
        "inbounds": [
            {
                "listen": "127.0.0.1",
                "port": 10085,
                "protocol": "dokodemo-door",
                "settings": {"address": "127.0.0.1"},
                "tag": "api"
            },
            {
                "listen": "127.0.0.1",
                "port": 10001,
                "protocol": "vless",
                "settings": {"clients": clients_vless, "decryption": "none"},
                "streamSettings": {"network": "ws", "wsSettings": {"path": "/vl-ws"}},
                "tag": "inbound-vless-ws"
            },
            {
                "listen": "127.0.0.1",
                "port": 10002,
                "protocol": "vmess",
                "settings": {"clients": clients_vmess},
                "streamSettings": {"network": "ws", "wsSettings": {"path": "/vm-ws"}},
                "tag": "inbound-vmess-ws"
            },
            {
                "listen": "127.0.0.1",
                "port": 10004,
                "protocol": "vless",
                "settings": {"clients": clients_vless, "decryption": "none"},
                "streamSettings": {"network": "xhttp", "xhttpSettings": {"path": "/vl-xhttp"}},
                "tag": "inbound-vless-xhttp"
            }
        ],
        "outbounds": [{"protocol": "freedom"}],
        "routing": {
            "rules": [
                {
                    "inboundTag": ["api"],
                    "outboundTag": "api",
                    "type": "field"
                }
            ]
        }
    }

    try:
        parent = os.path.dirname(XRAY_CONFIG_PATH)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(XRAY_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except OSError as e:
        logging.warning("Could not write xray config to %s: %s (continuing without xray)", XRAY_CONFIG_PATH, e)

def restart_xray():
    stop_xray()
    return start_xray()


def start_xray() -> dict:
    """Start xray if not running. Returns {started, already, mock}."""
    global xray_process
    if xray_process and xray_process.poll() is None:
        return {"started": False, "already": True, "mock": False}
    if not os.path.exists(XRAY_BIN):
        logging.warning("Xray binary not found. Running in mock/dev mode.")
        return {"started": False, "already": False, "mock": True}
    try:
        xray_process = subprocess.Popen([XRAY_BIN, "run", "-c", XRAY_CONFIG_PATH])
        print("✅ Xray started")
        return {"started": True, "already": False, "mock": False}
    except Exception as e:
        logging.error("Xray start failed: %s", e)
        return {"started": False, "already": False, "mock": False, "error": str(e)[:200]}


def stop_xray() -> dict:
    """Stop our xray child process. Returns {stopped}."""
    global xray_process
    stopped = False
    if xray_process and xray_process.poll() is None:
        xray_process.terminate()
        try:
            xray_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            xray_process.kill()
        stopped = True
    xray_process = None
    return {"stopped": stopped}


def validate_config() -> dict:
    """Really parse the live config file and sanity-check its structure."""
    errors = []
    try:
        with open(XRAY_CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except FileNotFoundError:
        return {"ok": False, "errors": ["config file not found: " + XRAY_CONFIG_PATH]}
    except json.JSONDecodeError as e:
        return {"ok": False, "errors": [f"invalid JSON: {e}"]}
    if not isinstance(cfg.get("inbounds"), list) or not cfg["inbounds"]:
        errors.append("no inbounds defined")
    if not isinstance(cfg.get("outbounds"), list) or not cfg["outbounds"]:
        errors.append("no outbounds defined")
    tags = set()
    for ib in cfg.get("inbounds", []):
        if not isinstance(ib, dict):
            errors.append("inbound entry is not an object")
            continue
        if not ib.get("tag"):
            errors.append("inbound without tag")
        elif ib["tag"] in tags:
            errors.append(f"duplicate tag: {ib['tag']}")
        else:
            tags.add(ib["tag"])
        cls = ib.get("settings", {}).get("clients", [])
        for cl in cls:
            if not cl.get("id"):
                errors.append(f"client without id in {ib.get('tag')}")
    n_clients = sum(len((ib.get("settings") or {}).get("clients", []))
                    for ib in cfg.get("inbounds", []) if isinstance(ib, dict))
    return {"ok": not errors, "errors": errors[:10], "inbounds": len(tags), "clients": n_clients}


def _rotate_access_log():
    try:
        parent = os.path.dirname(XRAY_ACCESS_LOG)
        if parent:
            os.makedirs(parent, exist_ok=True)
        if os.path.isfile(XRAY_ACCESS_LOG) and os.path.getsize(XRAY_ACCESS_LOG) > ACCESS_LOG_MAX_BYTES:
            old = XRAY_ACCESS_LOG + ".old"
            try:
                os.remove(old)
            except OSError:
                pass
            os.replace(XRAY_ACCESS_LOG, old)
    except OSError:
        pass


_ACCESS_RE = None


def parse_access_log(max_lines: int = 3000) -> dict:
    """Tail the xray access log → {uid: {ips: [...], last: epoch}}.

    Xray access format: YYYY/MM/DD HH:MM:SS <ip>:<port> accepted ... [email]
    where email is the inbound uid we configured.
    """
    global ip_cache
    import re as _re
    import time as _t
    import datetime as _dt
    pat = _re.compile(r"(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})\s+\[?([0-9a-fA-F.:]+)\]?(?::\d+)?\s+\S+\s+\S+\s+\[([^\]]+)\]")
    out = {}
    try:
        with open(XRAY_ACCESS_LOG, "rb") as f:
            try:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                f.seek(max(0, size - 256 * 1024), os.SEEK_SET)
                chunk = f.read().decode("utf-8", errors="ignore")
            except OSError:
                chunk = ""
    except FileNotFoundError:
        ip_cache = {}
        return {}
    lines = chunk.splitlines()[-max_lines:]
    for line in lines:
        m = pat.search(line)
        if not m:
            continue
        ts_s, ip, email = m.groups()
        try:
            ts = _dt.datetime.strptime(ts_s, "%Y/%m/%d %H:%M:%S").timestamp()
        except ValueError:
            ts = _t.time()
        ip = ip.strip("[]")
        if ip.count(".") == 3 and ":" in ip:  # strip IPv4:port tail
            ip = ip.rsplit(":", 1)[0]
        rec = out.setdefault(email, {"ips": [], "last": 0})
        if ip and ip not in rec["ips"]:
            rec["ips"].append(ip)
            rec["ips"] = rec["ips"][-5:]
        if ts > rec["last"]:
            rec["last"] = ts
    ip_cache = out
    return out


def get_ip_info(uid: str) -> dict:
    rec = ip_cache.get(uid)
    if not rec:
        return {"ips": [], "last": None}
    return {"ips": list(rec.get("ips", [])), "last": rec.get("last") or None}

previous_stats = {}

async def get_xray_stats():
    """Query Xray stats API and return per-uid traffic deltas using JSON output."""
    global previous_stats
    if not os.path.exists(XRAY_BIN):
        return {}
        
    try:
        proc = await asyncio.create_subprocess_exec(
            XRAY_BIN, "api", "statsquery", "--server=127.0.0.1:10085",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        out = stdout.decode("utf-8")
        
        if not out.strip():
            return {}
        
        # Parse JSON output
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            # Fallback to regex if JSON fails (for older Xray versions)
            import re
            matches = re.findall(r'name:\s*"([^"]+)"\s*value:\s*(\d+)', out)
            if not matches:
                return {}
            data = {"stat": [{"name": m[0], "value": int(m[1])} for m in matches]}
        
        stat_list = data.get("stat", [])
        current_stats = {}
        for item in stat_list:
            name = item.get("name")
            value = item.get("value")
            if not name or value is None:
                continue
            parts = name.split(">>>")
            if len(parts) == 4 and parts[0] == "user" and parts[2] == "traffic":
                uid = parts[1]          # email = inbound uid
                direction = parts[3]    # uplink or downlink
                val = int(value)
                if uid not in current_stats:
                    current_stats[uid] = {"up": 0, "down": 0}
                if direction == "uplink":
                    current_stats[uid]["up"] += val
                elif direction == "downlink":
                    current_stats[uid]["down"] += val

        # Compute deltas
        deltas = {}
        for uid, stats in current_stats.items():
            prev = previous_stats.get(uid, {"up": 0, "down": 0})
            up_delta = stats["up"] - prev["up"]
            down_delta = stats["down"] - prev["down"]
            if up_delta < 0:
                up_delta = stats["up"]
            if down_delta < 0:
                down_delta = stats["down"]
            if up_delta > 0 or down_delta > 0:
                deltas[uid] = {"up": up_delta, "down": down_delta}
        
        previous_stats = current_stats
        return deltas
        
    except Exception as e:
        logging.error(f"Error querying Xray stats: {e}")
        return {}
