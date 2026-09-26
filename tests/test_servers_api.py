"""Tests for Phase 3: Multi-Server API endpoints, monitoring, alerts, agent, groups."""
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
    """Create owner via /api/setup, return the response."""
    return await client.post("/api/setup", json={"username": "admin", "password": "Admin123!"})


class TestMultiServerCRUD:
    def test_servers_list_empty(self):
        async def _t():
            async with _client() as c:
                r = await _setup(c)
                assert r.status_code == 200
                r2 = await c.get("/api/servers")
                assert r2.status_code == 200
                assert "servers" in r2.json()
        run_async(_t())

    def test_local_server_always_present(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.get("/api/servers")
                data = r.json()
                local = [s for s in data["servers"] if s.get("local")]
                assert len(local) == 1
                assert local[0]["id"] == "local"
        run_async(_t())

    def test_add_server_missing_fields(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.post("/api/servers", json={"name": "Test"})
                assert r.status_code == 400
        run_async(_t())

    def test_add_server_bad_host(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.post("/api/servers", json={"name": "Bad", "host": "", "token": "abc"})
                assert r.status_code == 400
        run_async(_t())

    def test_update_server_not_found(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.patch("/api/servers/srv_nonexistent", json={"name": "X"})
                assert r.status_code == 404
        run_async(_t())

    def test_delete_server_not_found(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.delete("/api/servers/srv_nonexistent")
                assert r.status_code == 404
        run_async(_t())


class TestServerGroups:
    def test_create_group(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.post("/api/server-groups", json={"name": "Europe", "description": "European servers"})
                assert r.status_code == 200
                assert r.json()["ok"] is True
        run_async(_t())

    def test_list_groups(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                await c.post("/api/server-groups", json={"name": "TestGroup"})
                r = await c.get("/api/server-groups")
                assert r.status_code == 200
                assert len(r.json()["groups"]) >= 1
        run_async(_t())

    def test_duplicate_group_name(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                await c.post("/api/server-groups", json={"name": "Dup"})
                r = await c.post("/api/server-groups", json={"name": "Dup"})
                assert r.status_code == 409
        run_async(_t())

    def test_delete_group(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.post("/api/server-groups", json={"name": "Del"})
                gid = r.json()["group"]["id"]
                r2 = await c.delete(f"/api/server-groups/{gid}")
                assert r2.status_code == 200
        run_async(_t())

    def test_delete_group_not_found(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.delete("/api/server-groups/grp_nonexistent")
                assert r.status_code == 404
        run_async(_t())


class TestServerHealth:
    def test_local_health(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.get("/api/servers/local/health")
                assert r.status_code == 200
                assert r.json()["health"] == 100
        run_async(_t())

    def test_remote_health_not_found(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.get("/api/servers/srv_nonexistent/health")
                assert r.status_code == 404
        run_async(_t())


class TestServerMetrics:
    def test_local_metrics(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.get("/api/servers/local/metrics?range=24h")
                assert r.status_code == 200
                assert r.json()["id"] == "local"
        run_async(_t())


class TestServerEvents:
    def test_global_events_empty(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.get("/api/server-events")
                assert r.status_code == 200
                assert "events" in r.json()
        run_async(_t())

    def test_local_events(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.get("/api/servers/local/events")
                assert r.status_code == 200
        run_async(_t())


class TestServerAlerts:
    def test_global_alerts(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.get("/api/alerts")
                assert r.status_code == 200
                assert "alerts" in r.json()
        run_async(_t())

    def test_local_alerts(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.get("/api/servers/local/alerts")
                assert r.status_code == 200
        run_async(_t())


class TestMonitoring:
    def test_monitoring_overview(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.get("/api/servers/monitoring")
                assert r.status_code == 200
                data = r.json()
                assert "total_servers" in data
                assert "online" in data
        run_async(_t())

    def test_top_servers(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.get("/api/servers/top")
                assert r.status_code == 200
                assert "servers" in r.json()
        run_async(_t())


class TestAgentHeartbeat:
    def test_heartbeat_no_token(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.post("/api/agent/heartbeat", json={})
                assert r.status_code == 401
        run_async(_t())

    def test_heartbeat_bad_token(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.post("/api/agent/heartbeat",
                    json={}, headers={"Authorization": "Bearer wrong"})
                assert r.status_code in (401, 400)
        run_async(_t())


class TestServerBest:
    def test_best_server(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.get("/api/servers/best")
                assert r.status_code == 200
                data = r.json()
                assert "candidates" in data
                assert len(data["candidates"]) >= 1
        run_async(_t())


class TestAssignments:
    def test_assignments_list(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.get("/api/assignments")
                assert r.status_code == 200
                assert "assignments" in r.json()
        run_async(_t())


class TestSettingsAPI:
    def test_get_settings(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.get("/api/me")
                assert r.status_code == 200
                s = r.json()["settings"]
                assert "server_offline_after" in s
                assert "alert_cpu" in s
                assert "agent_auth_secret" in s
                assert "heartbeat_threshold" in s
        run_async(_t())

    def test_save_agent_settings(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.post("/api/settings", json={
                    "agent_auth_secret": "mysecret123",
                    "heartbeat_threshold": 120,
                })
                assert r.status_code == 200
                r2 = await c.get("/api/me")
                s = r2.json()["settings"]
                assert s["agent_auth_secret"] == "mysecret123"
                assert s["heartbeat_threshold"] == 120
        run_async(_t())

    def test_save_alert_thresholds(self):
        async def _t():
            async with _client() as c:
                await _setup(c)
                r = await c.post("/api/settings", json={
                    "alert_cpu": 90, "alert_mem": 95, "alert_disk": 98,
                })
                assert r.status_code == 200
        run_async(_t())
