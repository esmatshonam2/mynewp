#!/bin/bash
# SsPanel v2.0 — Railway/Docker entrypoint
# - nginx (public $PORT) fronts the panel (127.0.0.1:10000) + xray WS paths
# - panel + xray run as plain processes inside the single service
set -eu

# Railway injects PORT; default 8000 for local `docker run` without -e PORT
PORT="${PORT:-8000}"

# Panel internal port (nginx proxies to it; keep 10000 unless you know why)
export PANEL_PORT="${PANEL_PORT:-10000}"

# Persistent data dir (mount a Railway volume at /app/data so db.json survives)
export STANNG_DATA_DIR="${STANNG_DATA_DIR:-/app/data}"
mkdir -p "${STANNG_DATA_DIR}" /var/log/nginx /var/run

echo "[entrypoint] SsPanel v2.0 starting — public PORT=${PORT}, PANEL_PORT=${PANEL_PORT}, DATA=${STANNG_DATA_DIR}"

# Point nginx at the public port (idempotent: works for the NGINX_PORT
# template on first boot and for a numeric port on restarts/redeploys)
sed -i -E "s/listen [0-9]+;|listen NGINX_PORT;/listen ${PORT};/g" /etc/nginx/nginx.conf

# Validate config before starting
nginx -t

# (Re)start nginx: stop a stale instance from a previous run, then launch fresh
nginx -s stop 2>/dev/null || true
sleep 1
nginx
echo "[entrypoint] nginx listening on ${PORT}"

# Start Python panel in foreground (Docker/Railway track this PID)
exec python3 main.py
