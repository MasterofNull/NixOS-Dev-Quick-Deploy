#!/usr/bin/env python3
"""Static regression checks for live routing posture UI wiring."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_HTML = ROOT / "dashboard.html"
AISTACK_ROUTE = ROOT / "dashboard" / "backend" / "api" / "routes" / "aistack.py"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    html = DASHBOARD_HTML.read_text(encoding="utf-8")
    route = AISTACK_ROUTE.read_text(encoding="utf-8")

    assert_true('id="routingPostureConfig"' in html, "expected live routing posture panel in dashboard config section")
    assert_true('async function renderRoutingPosture()' in html, "expected live routing posture renderer")
    assert_true("/api/aistack/routing/summary" in html, "expected dashboard fetch for routing summary endpoint")
    assert_true("routing_windows" in html, "expected routing posture UI to render windowed routing trends")
    assert_true("failure_categories" in html, "expected routing posture UI to render routing failure categories")
    assert_true('@router.get("/routing/summary")' in route, "expected routing summary API route")
    assert_true('"recent_decisions": recent_decisions' in route or '"recent_decisions": recent_decisions,' in route, "expected routing summary to expose recent decisions")
    assert_true('"routing_windows": routing_windows' in route or '"routing_windows": routing_windows,' in route, "expected routing summary to expose routing windows")
    assert_true('"failure_categories": sorted(' in route, "expected routing summary to expose failure category mix")

    print("PASS: dashboard live routing posture UI wiring is present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
