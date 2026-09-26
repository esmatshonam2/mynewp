"""Tests for core/servers.py — health, load, version_compat math."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.servers import health_score, load_pct, version_compat


class TestHealthScore:
    def test_offline_returns_zero(self):
        assert health_score({}, False) == 0

    def test_unknown_online_returns_none(self):
        assert health_score({}, None) is None

    def test_perfect_metrics(self):
        m = {"cpu": 30, "mem": 50, "disk_percent": 40, "latency_ms": 50, "xray": "online", "uptime_seconds": 86400}
        assert health_score(m, True) == 100

    def test_high_cpu_deducts(self):
        m = {"cpu": 90, "mem": 50, "xray": "online", "uptime_seconds": 86400}
        score = health_score(m, True)
        assert score < 100
        assert score > 0

    def test_high_mem_deducts(self):
        m = {"cpu": 30, "mem": 95, "xray": "online", "uptime_seconds": 86400}
        score = health_score(m, True)
        assert score < 100

    def test_high_disk_deducts(self):
        m = {"cpu": 30, "mem": 50, "disk_percent": 95, "xray": "online", "uptime_seconds": 86400}
        score = health_score(m, True)
        assert score < 100

    def test_disk_80_90_small_deduction(self):
        m1 = {"cpu": 30, "mem": 50, "disk_percent": 85, "xray": "online", "uptime_seconds": 86400}
        m2 = {"cpu": 30, "mem": 50, "disk_percent": 40, "xray": "online", "uptime_seconds": 86400}
        s1 = health_score(m1, True)
        s2 = health_score(m2, True)
        assert s1 < s2

    def test_high_latency_deducts(self):
        m = {"cpu": 30, "mem": 50, "latency_ms": 1500, "xray": "online", "uptime_seconds": 86400}
        score = health_score(m, True)
        assert score < 100

    def test_medium_latency_deducts(self):
        m1 = {"cpu": 30, "mem": 50, "latency_ms": 700, "xray": "online", "uptime_seconds": 86400}
        m2 = {"cpu": 30, "mem": 50, "latency_ms": 100, "xray": "online", "uptime_seconds": 86400}
        assert health_score(m1, True) < health_score(m2, True)

    def test_xray_offline_deducts(self):
        m = {"cpu": 30, "mem": 50, "xray": "offline", "uptime_seconds": 86400}
        score = health_score(m, True)
        assert score <= 70

    def test_xray_mock_small_deduction(self):
        m = {"cpu": 30, "mem": 50, "xray": "mock", "uptime_seconds": 86400}
        score = health_score(m, True)
        assert score < 100
        assert score > 85

    def test_low_uptime_deducts(self):
        m = {"cpu": 30, "mem": 50, "xray": "online", "uptime_seconds": 1800}
        score = health_score(m, True)
        assert score < 100

    def test_high_error_rate_deducts(self):
        m = {"cpu": 30, "mem": 50, "xray": "online", "uptime_seconds": 86400, "error_rate": 10}
        score = health_score(m, True)
        assert score < 100

    def test_error_rate_below_threshold_no_deduction(self):
        m1 = {"cpu": 30, "mem": 50, "xray": "online", "uptime_seconds": 86400, "error_rate": 3}
        m2 = {"cpu": 30, "mem": 50, "xray": "online", "uptime_seconds": 86400, "error_rate": 0}
        assert health_score(m1, True) == health_score(m2, True)

    def test_high_packet_loss_deducts(self):
        m = {"cpu": 30, "mem": 50, "xray": "online", "uptime_seconds": 86400, "packet_loss": 20}
        score = health_score(m, True)
        assert score <= 80

    def test_medium_packet_loss_deducts(self):
        m1 = {"cpu": 30, "mem": 50, "xray": "online", "uptime_seconds": 86400, "packet_loss": 10}
        m2 = {"cpu": 30, "mem": 50, "xray": "online", "uptime_seconds": 86400}
        assert health_score(m1, True) < health_score(m2, True)

    def test_clamped_to_100(self):
        m = {"cpu": 10, "mem": 10, "disk_percent": 10, "latency_ms": 5, "xray": "online", "uptime_seconds": 86400}
        assert health_score(m, True) == 100

    def test_clamped_to_0(self):
        m = {"cpu": 100, "mem": 100, "disk_percent": 100, "latency_ms": 5000, "xray": "offline", "uptime_seconds": 100, "error_rate": 50, "packet_loss": 50}
        score = health_score(m, True)
        assert score == 0

    def test_none_metrics_returns_none(self):
        assert health_score(None, True) is None

    def test_empty_metrics_returns_none(self):
        assert health_score({}, True) is None


class TestLoadPct:
    def test_basic_load(self):
        m = {"cpu": 50, "mem": 60, "active_connections": 20}
        load = load_pct(m)
        assert load is not None
        assert 0 <= load <= 100

    def test_cpu_mem_only(self):
        m = {"cpu": 80, "mem": 80}
        load = load_pct(m)
        assert load == 64.0

    def test_connections_capped_at_100(self):
        m = {"cpu": 50, "mem": 50, "active_connections": 500}
        load = load_pct(m)
        assert load is not None

    def test_none_metrics(self):
        assert load_pct(None) is None

    def test_empty_metrics(self):
        assert load_pct({}) is None


class TestVersionCompat:
    def test_same_version(self):
        assert version_compat("3.1.0", "3.1.0") == "compatible"

    def test_different_minor(self):
        assert version_compat("3.1.0", "3.2.0") == "warning"

    def test_different_major(self):
        assert version_compat("3.1.0", "4.1.0") == "incompatible"

    def test_empty_versions(self):
        assert version_compat("", "") == "unknown"

    def test_partial_version(self):
        assert version_compat("3", "3") == "unknown"
