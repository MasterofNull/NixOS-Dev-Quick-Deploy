#!/usr/bin/env python3
"""
scripts/testing/test-aq-decide-s8.py - Unit test suite for DEC-S8.

Verifies:
1. compute_psi calculation accuracy and baseline symmetry.
2. check_calibration_drift threshold detection.
3. agent-auth-policy 'decide' scope definition and /decide endpoint restriction.
4. dashboard DEC-S8 elements integration.
"""

import json
import math
import sys
from pathlib import Path

# Ensure library path is available
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "ai" / "lib"))

import aq_decide  # noqa: E402


def test_compute_psi():
    # Identical distributions have 0 PSI
    p1 = {"a": 0.5, "b": 0.5}
    assert aq_decide.compute_psi(p1, p1) == 0.0, "Identical distributions must have 0.0 PSI"

    # Shifted distribution
    actual = {"a": 0.8, "b": 0.2}
    baseline = {"a": 0.2, "b": 0.8}
    psi = aq_decide.compute_psi(actual, baseline)
    assert psi > 1.0, f"Significant shift should produce PSI > 1.0, got {psi}"
    print(f"PASS: compute_psi verified (psi={psi})")


def test_calibration_drift():
    # Gap within threshold
    drifted, gap = aq_decide.check_calibration_drift(0.85, 0.82, threshold=0.15)
    assert not drifted, "Gap within threshold must not report drift"
    assert gap == 0.03, f"Expected gap 0.03, got {gap}"

    # Gap exceeding threshold
    drifted, gap = aq_decide.check_calibration_drift(0.90, 0.65, threshold=0.15)
    assert drifted, "Gap exceeding threshold must report drift"
    assert gap == 0.25, f"Expected gap 0.25, got {gap}"
    print(f"PASS: check_calibration_drift verified (gap={gap}, drifted={drifted})")


def test_decide_scope_policy():
    policy_path = REPO_ROOT / "config" / "agent-auth-policy.json"
    assert policy_path.exists(), "agent-auth-policy.json must exist"
    with open(policy_path, "r", encoding="utf-8") as f:
        policy = json.load(f)

    assert "decide" in policy.get("scopes", {}), "'decide' scope must be declared in agent-auth policy"
    rules = [r for r in policy.get("rules", []) if r.get("scope") == "decide"]
    assert len(rules) > 0, "A routing rule for 'decide' scope must exist"
    assert any("/decide" in r.get("prefixes", []) for r in rules), "Prefix '/decide' must be mapped to decide scope"

    # Must NOT be granted to untrusted/legacy classes by default
    legacy_grants = policy.get("classes", {}).get("legacy-loopback", [])
    assert "decide" not in legacy_grants, "'decide' scope must not be granted to legacy-loopback by default"
    print("PASS: agent-auth 'decide' policy restriction verified")


def test_dashboard_integration():
    dash_html = (REPO_ROOT / "dashboard.html").read_text(encoding="utf-8")
    assert "section-aq-decide" in dash_html, "dashboard.html must contain section-aq-decide"
    assert "decideEngineStatus" in dash_html, "dashboard.html must contain decideEngineStatus element"
    assert "decidePsiDrift" in dash_html, "dashboard.html must contain decidePsiDrift element"

    dash_js = (REPO_ROOT / "assets" / "dashboard.js").read_text(encoding="utf-8")
    assert "loadAqDecide" in dash_js, "dashboard.js must define loadAqDecide"
    print("PASS: dashboard DEC-S8 integration verified")


def main():
    print("Running DEC-S8 validation suite...")
    test_compute_psi()
    test_calibration_drift()
    test_decide_scope_policy()
    test_dashboard_integration()
    print("ALL DEC-S8 TESTS PASSED (4/4)")


if __name__ == "__main__":
    main()
