# Deployment

## Railway (recommended)

1. Push to GitHub → **New Project → Deploy from Repo**
   (`Dockerfile` + `railway.json` are picked up; health check `/health`).
2. **Volumes → + New Volume**, mount path `/app/data`
   (without this `db.json` is wiped on every redeploy).
3. Optional variables: `PANEL_NAME`, `TELEGRAM_CONTACT`.
4. Open `https://<app>.up.railway.app/setup`, create the owner account.

Traffic path: Railway edge (TLS) → `$PORT` → nginx → panel `:10000`
(`/`) and xray (`/vl-ws`, `/vm-ws`, `/vl-xhttp`). VLESS links use port
443 + TLS, matching Railway's HTTPS endpoint. Set **public domain** in
Settings so subscription/bot links use the right host.

## Render

`render.yaml` uses the Docker runtime with health check `/health`.
Attach a persistent disk at `/app/data`.

## VPS (Docker Compose)

```yaml
services:
  panel:
    build: .
    ports: ["8000:8000"]
    volumes: ["aloo-data:/app/data"]
    environment:
      PANEL_NAME: "ALOO PANEL"
volumes:
  aloo-data:
```
