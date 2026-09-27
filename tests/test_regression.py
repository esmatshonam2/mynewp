"""Regression tests: ensure Phase 1 and Phase 2 features still work."""
import asyncio
import pytest


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _client():
    from httpx import AsyncClient, ASGITransport
    from main import app
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


async def _setup(client):
    return await client.post("/api/setup", json={"username": "admin", "password": "Admin123!"})


class TestSecurityRegression:
    def test_me_redacts_secrets(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                from storage import store
                await store.mutate(lambda db: db["settings"].update({
                    "telegram_bot_token": "secret-token-value",
                    "agent_auth_secret": "agent-secret-value",
                }))
                data = (await c.get("/api/me")).json()
                assert "telegram_bot_token" not in data["settings"]
                assert "agent_auth_secret" not in data["settings"]
        run_async(_t())

    def test_ota_requires_dedicated_permission(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                from storage import store
                await store.mutate(lambda db: db["settings"].update({"role_overrides": {
                    "admin": ["analytics.read"]
                }}))
                assert (await c.get("/api/ota/check")).status_code == 403
        run_async(_t())


class TestAuthRegression:
    def test_setup_creates_owner(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.get("/api/me")
                assert r.status_code == 200
                data = r.json()
                assert data["logged_in"] is True
                assert data["username"] == "admin"
        run_async(_t())

    def test_login_works(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.post("/api/login", json={"username": "admin", "password": "Admin123!"})
                assert r.status_code == 200
                assert r.json()["ok"] is True
        run_async(_t())

    def test_wrong_password_rejected(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.post("/api/login", json={"username": "admin", "password": "wrong"})
                assert r.status_code == 401
        run_async(_t())


class TestInboundsRegression:
    def test_list_inbounds(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.get("/api/inbounds")
                assert r.status_code == 200
                assert "inbounds" in r.json()
        run_async(_t())

    def test_create_inbound(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.post("/api/inbounds", json={"name": "TestUser", "quota_gb": 10, "expire_days": 30})
                assert r.status_code == 200
                data = r.json()
                assert data["ok"] is True
                assert data["inbound"]["name"] == "TestUser"
        run_async(_t())

    def test_delete_inbound(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.post("/api/inbounds", json={"name": "ToDelete"})
                uid = r.json()["inbound"]["uid"]
                r2 = await c.delete(f"/api/inbounds/{uid}")
                assert r2.status_code == 200
        run_async(_t())

    def test_toggle_inbound(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.post("/api/inbounds", json={"name": "ToggleMe"})
                uid = r.json()["inbound"]["uid"]
                r2 = await c.post(f"/api/inbounds/{uid}/toggle")
                assert r2.status_code == 200
        run_async(_t())


class TestPlansRegression:
    def test_list_plans(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.get("/api/plans")
                assert r.status_code == 200
                assert len(r.json()["plans"]) >= 3
        run_async(_t())

    def test_create_plan(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.post("/api/plans", json={"name": "TestPlan", "traffic_gb": 100, "duration_days": 30})
                assert r.status_code == 200
        run_async(_t())


class TestXrayRegression:
    def test_xray_status(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.get("/api/xray/status")
                assert r.status_code == 200
                assert "status" in r.json()
        run_async(_t())


class TestSystemRegression:
    def test_health_endpoint(self):
        async def _t():
            async with _client() as c:
                r = await c.get("/health")
                assert r.status_code == 200
                assert r.json()["status"] == "ok"
        run_async(_t())

    def test_stats_endpoint(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.get("/stats")
                assert r.status_code == 200
                data = r.json()
                assert "cpu_percent" in data
                assert "inbounds_count" in data
        run_async(_t())

    def test_system_endpoint(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.get("/api/system")
                assert r.status_code == 200
                assert "cpu_count" in r.json()
        run_async(_t())

    def test_live_endpoint(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.get("/api/live")
                assert r.status_code == 200
                data = r.json()
                assert "cpu_percent" in data
                assert "net_up_bps" in data
        run_async(_t())


class TestAnalyticsRegression:
    def test_analytics_24h(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.get("/api/analytics?range=24h")
                assert r.status_code == 200
                data = r.json()
                assert "total_up" in data
                assert "top_users" in data
                assert "per_server" in data
                assert "top_users_by_connections" in data
        run_async(_t())


class TestNotificationsRegression:
    def test_notifications_list(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.get("/api/notifications")
                assert r.status_code == 200
                assert "notifications" in r.json()
        run_async(_t())


class TestBackupRegression:
    def test_backups_list(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.get("/api/backups")
                assert r.status_code == 200
        run_async(_t())


class TestDiagnosticsRegression:
    def test_diagnostics_run(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.get("/api/diagnostics/run")
                assert r.status_code == 200
                assert "checks" in r.json()
        run_async(_t())


class TestSecurityRegression:
    def test_security_overview(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.get("/api/security/overview")
                assert r.status_code == 200
                data = r.json()
                assert "policy" in data
                assert "admins_count" in data
        run_async(_t())


class TestRolesRegression:
    def test_roles_list(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.get("/api/roles")
                assert r.status_code == 200
                data = r.json()
                assert "roles" in data
                assert "permissions" in data
        run_async(_t())


class TestDatabaseMigration:
    def test_schema_version(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
            from storage import store
            db = await store.get()
            assert db["schema_version"] >= 12
        run_async(_t())

    def test_server_events_collection_exists(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
            from storage import store
            db = await store.get()
            assert "server_events" in db
        run_async(_t())

    def test_agent_settings_exist(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
            from storage import store
            db = await store.get()
            s = db.get("settings", {})
            assert "agent_auth_secret" in s
            assert "heartbeat_threshold" in s
        run_async(_t())


class TestProfessionalEnhancements:
    def test_dashboard_summary_requires_auth_and_returns_sections(self):
        async def _t():
            async with _client() as c:
                r = await c.get("/api/dashboard/summary")
                assert r.status_code == 401
                await _setup(c)
                r = await c.get("/api/dashboard/summary")
                assert r.status_code == 200
                data = r.json()
                assert {"users", "traffic", "servers", "services", "top_users", "alerts"} <= set(data)
                assert data["users"]["total"] == 0
        run_async(_t())

    def test_export_csv_does_not_expose_uuid_or_subscription_token(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                created = await c.post("/api/inbounds", json={"name": "CSV User", "quota_gb": 2})
                ib = created.json()["inbound"]
                r = await c.get("/api/inbounds/export.csv")
                assert r.status_code == 200
                body = r.text
                assert "CSV User" in body
                assert ib["uuid"] not in body
                assert ib["sub_token"] not in body
                assert "uid,name,enabled,status" in body
        run_async(_t())

    def test_local_scheme_uses_http_request_scheme(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                created = await c.post("/api/inbounds", json={"name": "Scheme User"})
                uid = created.json()["inbound"]["uid"]
                r = await c.get(f"/api/inbounds/{uid}/links")
                assert r.status_code == 200
                assert r.json()["sub_url"].startswith("http://testserver/")
        run_async(_t())

    def test_invalid_backup_shape_rejected(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.post("/api/backup/import", json={"db": {"inbounds": [{"uid": "x"}, {"uid": "x"}]}})
                assert r.status_code == 400
        run_async(_t())

    def test_telegram_commands_produce_operational_reports(self, monkeypatch):
        async def _t():
            from telegram_bot import _handle_command
            from storage import store
            await _setup(_client())
            sent = []
            async def fake_send(token, chat, text, *args, **kwargs):
                sent.append(text)
                return True
            monkeypatch.setattr("telegram_bot.send_message", fake_send)
            await _handle_command(store, "token", "1", "/health")
            await _handle_command(store, "token", "1", "/traffic")
            await _handle_command(store, "token", "1", "/alerts")
            assert len(sent) == 3
            assert "سلامت" in sent[0]
            assert "ترافیک" in sent[1]
            assert "هشدار" in sent[2]
        run_async(_t())
