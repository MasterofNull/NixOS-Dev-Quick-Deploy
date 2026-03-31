#!/usr/bin/env python3
"""Offline regression checks for dashboard rate limiting and operator audit routes."""

from __future__ import annotations

import importlib
import os
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dashboard" / "backend"))


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="dashboard-runtime-controls-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        os.environ["DASHBOARD_RATE_LIMIT_ENABLED"] = "true"
        os.environ["DASHBOARD_RATE_LIMIT_WINDOW_SECONDS"] = "60"
        os.environ["DASHBOARD_RATE_LIMIT_HEALTH_RPM"] = "2"
        os.environ["DASHBOARD_RATE_LIMIT_OPERATOR_WRITE_RPM"] = "4"
        os.environ["DASHBOARD_RATE_LIMIT_DEFAULT_RPM"] = "20"
        os.environ["DASHBOARD_OPERATOR_AUDIT_LOG_PATH"] = str(tmp_path / "operator-audit.jsonl")
        os.environ["DASHBOARD_CONTEXT_DB_PATH"] = str(tmp_path / "deployments-context.db")
        os.environ["DASHBOARD_MODE"] = "test"

        dashboard_main = importlib.import_module("api.main")
        dashboard_main = importlib.reload(dashboard_main)
        firewall_module = importlib.import_module("api.routes.firewall")
        firewall_module = importlib.reload(firewall_module)

        recorded_commands = []

        async def fake_run_command(cmd, timeout=10):
            recorded_commands.append(list(cmd))
            if cmd[:3] == ["systemctl", "is-active", "nftables"]:
                return 0, "active\n", ""
            if cmd[:3] == ["systemctl", "is-active", "firewall"]:
                return 0, "active\n", ""
            if cmd[:3] == ["systemctl", "is-active", "crowdsec-firewall-bouncer"]:
                paused = firewall_module._bypass_state["crowdsec_paused"]
                return (3, "inactive\n", "") if paused else (0, "active\n", "")
            return 0, "", ""

        async def fake_run_sudo_command(cmd, timeout=10):
            recorded_commands.append(list(cmd))
            if cmd[:5] == ["nft", "list", "chain", firewall_module.NFT_FAMILY, firewall_module.NFT_TABLE]:
                return 0, "chain output { type filter hook output priority 0; policy accept; }", ""
            if cmd[:6] == ["nft", "-a", "list", "chain", firewall_module.NFT_FAMILY, firewall_module.NFT_TABLE]:
                return 0, (
                    f'chain {firewall_module.NFT_OUTPUT_CHAIN} {{\n'
                    f'  tcp dport {{ 80, 443 }} accept comment "{firewall_module.CAPTIVE_PORTAL_RULE_COMMENT}" handle 10\n'
                    f'  udp dport 53 accept comment "{firewall_module.CAPTIVE_PORTAL_RULE_COMMENT}" handle 11\n'
                    f'  tcp dport 53 accept comment "{firewall_module.CAPTIVE_PORTAL_RULE_COMMENT}" handle 12\n'
                    f'}}\n'
                ), ""
            return 0, "", ""

        firewall_module.run_command = fake_run_command
        firewall_module.run_sudo_command = fake_run_sudo_command

        with TestClient(dashboard_main.app) as client:
            health_1 = client.get("/api/health")
            health_2 = client.get("/api/health")
            health_3 = client.get("/api/health")
            assert_true(health_1.status_code == 200, "first health request should pass")
            assert_true(health_2.status_code == 200, "second health request should pass")
            assert_true(health_3.status_code == 429, "third health request should be rate limited")
            assert_true(health_3.headers.get("x-ratelimit-category") == "health", "health limit category should be exposed")

            started = client.post(
                "/api/deployments/start",
                params={"deployment_id": "audit-test", "command": "deploy test", "user": "codex"},
            )
            assert_true(started.status_code == 200, "deployment start should succeed")

            summary = client.get("/api/audit/operator/summary")
            events = client.get("/api/audit/operator/events", params={"limit": 10})
            integrity = client.get("/api/audit/operator/integrity", params={"limit": 10})
            integrity_window = client.get("/api/audit/operator/integrity", params={"limit": 1})
            filtered = client.get(
                "/api/audit/operator/events",
                params={"limit": 10, "path_prefix": "/api/deployments", "method": "POST", "category": "operator_write"},
            )
            assert_true(summary.status_code == 200, "audit summary route should succeed")
            assert_true(events.status_code == 200, "audit events route should succeed")
            assert_true(integrity.status_code == 200, "audit integrity route should succeed")
            assert_true(integrity_window.status_code == 200, "limited audit integrity route should succeed")
            assert_true(filtered.status_code == 200, "filtered audit events route should succeed")

            summary_data = summary.json()
            events_data = events.json()
            integrity_data = integrity.json()
            integrity_window_data = integrity_window.json()
            filtered_data = filtered.json()
            assert_true(summary_data.get("append_only") is True, "audit summary should mark append-only log")
            assert_true(summary_data.get("tamper_evident") is True, "audit summary should mark tamper-evident sealing")
            assert_true(summary_data.get("total_events", 0) >= 1, "audit log should contain at least one event")
            assert_true("operator_write" in (summary_data.get("categories") or {}), "audit summary should expose category counts")
            assert_true(integrity_data.get("valid") is True, "audit integrity check should pass")
            assert_true(integrity_data.get("sealed_events", 0) >= 1, "audit integrity should report sealed events")
            assert_true(integrity_data.get("legacy_events", 0) == 0, "fresh audit log should not contain legacy events")
            assert_true(integrity_window_data.get("valid") is True, "limited integrity window should stay valid")
            assert_true(integrity_window_data.get("window_truncated") is True, "limited integrity window should report truncation")
            assert_true(integrity_window_data.get("sealed_events", 0) >= 1, "limited integrity window should report sealed events")
            assert_true(
                any(event.get("path") == "/api/deployments/start" and event.get("method") == "POST" for event in (events_data.get("events") or [])),
                "deployment start should be present in operator audit log",
            )
            assert_true(
                all(event.get("path", "").startswith("/api/deployments") for event in (filtered_data.get("events") or [])),
                "filtered audit results should respect path prefix",
            )
            assert_true(
                all(event.get("method") == "POST" for event in (filtered_data.get("events") or [])),
                "filtered audit results should respect method",
            )

            portal_enable = client.post(
                "/api/firewall/captive-portal/enable",
                json={"duration_minutes": 3, "interface": "wlan0"},
            )
            portal_status = client.get("/api/firewall/captive-portal/status")
            portal_disable = client.post("/api/firewall/captive-portal/disable")

            assert_true(portal_enable.status_code == 200, "captive portal enable should succeed")
            assert_true(portal_status.status_code == 200, "captive portal status should succeed")
            assert_true(portal_disable.status_code == 200, "captive portal disable should succeed")

            portal_enable_data = portal_enable.json()
            portal_status_data = portal_status.json()
            assert_true(portal_enable_data.get("status") == "enabled", "captive portal enable should report enabled")
            assert_true(portal_enable_data.get("interface") == "wlan0", "captive portal enable should echo interface")
            assert_true(portal_status_data.get("interface") == "wlan0", "captive portal status should expose interface")
            assert_true(
                any("oifname" in cmd and "wlan0" in cmd for cmd in recorded_commands if cmd[:4] == ["nft", "add", "rule", firewall_module.NFT_FAMILY]),
                "interface-specific portal bypass should program oifname rule",
            )
            assert_true(
                any("53" in cmd and "tcp" in cmd for cmd in recorded_commands if cmd[:4] == ["nft", "add", "rule", firewall_module.NFT_FAMILY]),
                "captive portal bypass should add TCP DNS rule",
            )

        print("PASS: dashboard runtime controls regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
