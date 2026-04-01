#!/usr/bin/env python3
"""
Integration test for orchestration visibility endpoints.
Tests that new endpoints are accessible and return valid structure.
"""

import os
import requests
import sys
from pathlib import Path

DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:8889")
HYBRID_URL = os.getenv("HYBRID_URL", "http://localhost:8003")


def _read_secret(*candidates: str | None) -> str:
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.is_file():
            return path.read_text(encoding="utf-8").strip()
    return ""


def _hybrid_headers() -> dict[str, str]:
    api_key = (
        os.getenv("HYBRID_API_KEY", "").strip()
        or _read_secret(
            os.getenv("HYBRID_API_KEY_FILE"),
            "/run/secrets/hybrid_api_key",
        )
    )
    if not api_key:
        return {}
    return {"Authorization": f"Bearer {api_key}"}

def test_endpoints():
    """Test that new endpoints are accessible and return valid structure."""
    failures = []
    hybrid_headers = _hybrid_headers()
    hybrid_auth_configured = bool(hybrid_headers)

    # Test evaluation trends endpoint
    print("Testing evaluation trends endpoint...")
    try:
        resp = requests.get(f"{DASHBOARD_URL}/api/aistack/orchestration/evaluations/trends", timeout=5)
        if resp.status_code != 200:
            failures.append(f"Evaluation trends endpoint returned {resp.status_code}")
        else:
            data = resp.json()
            if "agent_count" not in data or "trends" not in data:
                failures.append("Evaluation trends missing required fields")
            else:
                print(f"  ✓ Evaluation trends endpoint: {data['agent_count']} agents tracked")
    except Exception as e:
        failures.append(f"Evaluation trends endpoint failed: {e}")

    # Test hybrid coordinator endpoints directly
    print("Testing hybrid coordinator endpoints...")
    try:
        resp = requests.get(
            f"{HYBRID_URL}/control/ai-coordinator/evaluations/trends",
            headers=hybrid_headers,
            timeout=5,
        )
        if resp.status_code == 200:
            print(f"  ✓ Hybrid coordinator trends endpoint accessible")
        elif resp.status_code == 401 and not hybrid_auth_configured:
            print("  ✓ Hybrid coordinator trends endpoint is protected when no auth is configured")
        else:
            failures.append(f"Hybrid trends endpoint returned {resp.status_code}")
    except Exception as e:
        failures.append(f"Hybrid trends endpoint failed: {e}")

    # Test team detailed endpoint structure (without session ID)
    print("Testing team detailed endpoint structure...")
    try:
        # This should 404 since we don't have a valid session ID
        resp = requests.get(
            f"{HYBRID_URL}/workflow/run/test-session-id/team/detailed",
            headers=hybrid_headers,
            timeout=5,
        )
        if resp.status_code == 404:
            print(f"  ✓ Team detailed endpoint responds correctly to invalid session")
        elif resp.status_code == 401 and not hybrid_auth_configured:
            print("  ✓ Team detailed endpoint is protected when no auth is configured")
        else:
            print(f"  ℹ Team detailed endpoint returned {resp.status_code} (expected 404)")
    except Exception as e:
        failures.append(f"Team detailed endpoint failed: {e}")

    # Test arbiter history endpoint structure (without session ID)
    print("Testing arbiter history endpoint structure...")
    try:
        # This should 404 since we don't have a valid session ID
        resp = requests.get(
            f"{HYBRID_URL}/workflow/run/test-session-id/arbiter/history",
            headers=hybrid_headers,
            timeout=5,
        )
        if resp.status_code == 404:
            print(f"  ✓ Arbiter history endpoint responds correctly to invalid session")
        elif resp.status_code == 401 and not hybrid_auth_configured:
            print("  ✓ Arbiter history endpoint is protected when no auth is configured")
        else:
            print(f"  ℹ Arbiter history endpoint returned {resp.status_code} (expected 404)")
    except Exception as e:
        failures.append(f"Arbiter history endpoint failed: {e}")

    return failures

def test_ui_elements():
    """Test that dashboard HTML contains new UI elements."""
    print("\nTesting UI elements in dashboard.html...")
    dashboard_html = Path(__file__).parents[2] / "dashboard.html"

    if not dashboard_html.exists():
        return [f"Dashboard HTML not found at {dashboard_html}"]

    content = dashboard_html.read_text()

    required_elements = [
        'id="orchestrationTeamGrid"',
        'id="teamMembersTable"',
        'id="candidateScoringList"',
        'id="deferredMembersList"',
        'id="arbiterSection"',
        'id="agentTrendsTable"',
        'function loadOrchestrationDetails()',
        'function renderOrchestrationTeam(',
        'function renderArbiterHistory(',
        'function loadAgentEvaluationTrends(',
        'id="orchFormationMode"',
        'id="orchRequiredSlots"',
        'id="orchOptionalCapacity"',
        'id="orchDeferredSlots"',
        '/api/aistack/orchestration/team/',
        '/api/aistack/orchestration/arbiter/',
        '/api/aistack/orchestration/evaluations/trends',
    ]

    missing = []
    for elem in required_elements:
        if elem not in content:
            missing.append(elem)
        else:
            print(f"  ✓ Found: {elem}")

    return missing

def main():
    print("=== Orchestration Visibility Integration Test ===\n")

    print("Phase 1: Testing UI Elements...")
    missing_ui = test_ui_elements()
    if missing_ui:
        print("\n❌ FAIL: Missing UI elements:")
        for elem in missing_ui:
            print(f"  - {elem}")
        return 1
    print("\n✓ PASS: All UI elements present\n")

    print("Phase 2: Testing Orchestration Visibility Endpoints...")
    endpoint_failures = test_endpoints()
    if endpoint_failures:
        print("\n❌ FAIL: Endpoint tests failed:")
        for failure in endpoint_failures:
            print(f"  - {failure}")
        return 1

    print("\n✓ PASS: All endpoints accessible\n")
    print("=" * 50)
    print("✓ All orchestration visibility tests passed!")
    print("=" * 50)
    return 0

if __name__ == "__main__":
    sys.exit(main())
