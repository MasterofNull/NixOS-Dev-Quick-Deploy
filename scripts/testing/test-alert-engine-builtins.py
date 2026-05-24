#!/usr/bin/env python3
"""Regression test for AlertEngine built-in integration wiring."""

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
OBSERVABILITY_DIR = REPO_ROOT / "ai-stack" / "observability"


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    sys.path.insert(0, str(OBSERVABILITY_DIR))
    from alert_engine import AlertEngine

    engine = AlertEngine(rules_config_path=None)

    for channel in ("email", "slack", "discord", "webhook", "primary"):
        assert_true(channel in engine.notification_handlers, f"missing notification handler: {channel}")

    for workflow in (
        "clear_cache",
        "refresh_models",
        "restart_service",
        "rotate_logs",
        "scale_resources",
    ):
        assert_true(workflow in engine.remediation_workflows, f"missing remediation workflow: {workflow}")

    stats = engine.get_stats()
    assert_true(stats["notification_handlers"] >= 5, "stats should expose notification handler count")
    assert_true(stats["remediation_workflows"] >= 5, "stats should expose remediation workflow count")

    print("PASS: AlertEngine built-in integrations registered")


if __name__ == "__main__":
    main()
