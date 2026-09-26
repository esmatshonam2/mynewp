# Installation

## Local (Windows / Linux / macOS)

Requirements: Python 3.11+.

```bash
pip install -r requirements.txt
python main.py
```

Open `http://localhost:10000` (or `$PANEL_PORT` / `$PORT`). On first run
open `/setup` and create the owner account (min 8-char password).

Without the `xray` binary the panel runs in **mock mode**: everything works
except real VPN traffic and live per-user stats (see TROUBLESHOOTING.md).

## Docker

```bash
docker build -t aloo-panel .
docker run -p 8000:8000 -v aloo-data:/app/data aloo-panel
```

The image installs `xray-core`, `nginx` (public `$PORT` → panel `:10000` +
xray WS paths) and runs `entrypoint.sh`. Health check: `/health`.
