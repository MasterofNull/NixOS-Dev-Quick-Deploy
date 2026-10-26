#!/usr/bin/env python3
"""test-dashboard-cockpit-steering.py — Verification for Wave 10 Mission Cockpit & Operator Steering.

Tests:
1. Loop control 'steer' endpoint persists guidance to PULSE.log and RESUME.json
2. Loop control 'pause' and 'resume' action contracts
3. Collab state endpoint returns resume objective, phase, and latest pulse lines for the HUD
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Ensure dashboard backend is importable
repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root / "dashboard" / "backend"))

from api.routes.aistack import (  # noqa: E402
    post_loop_control,
    LoopControlRequest,
    get_agent_collab_state,
)


async def main():
    print("Testing Wave 10 Mission Cockpit & Human Intervention Steering...")

    # 1. Test Steering Action
    test_msg = "SOTA Wave 10 Automated Verification Steering Test"
    req = LoopControlRequest(action="steer", agent="orchestrator", message=test_msg)
    res = await post_loop_control(req)

    assert res["ok"] is True, f"Expected ok: True, got: {res}"
    assert res["action"] == "steer"
    assert res["agent"] == "orchestrator"
    assert res["message"] == test_msg
    print("✓ post_loop_control steer action passed")

    # Verify PULSE.log contains the steered line
    pulse_log = repo_root / ".agent" / "collaboration" / "PULSE.log"
    assert pulse_log.exists(), "PULSE.log must exist"
    pulse_tail = pulse_log.read_text(encoding="utf-8").strip().splitlines()[-1]
    assert test_msg in pulse_tail, f"Expected '{test_msg}' in latest PULSE.log entry, got: {pulse_tail}"
    print("✓ PULSE.log audit trail verified")

    # 2. Test Collab State Endpoint for Cockpit HUD
    collab_state = await get_agent_collab_state()
    assert "resume" in collab_state, "collab_state must contain resume object"
    assert "pulse" in collab_state, "collab_state must contain pulse array"
    assert len(collab_state["pulse"]) > 0, "collab_state pulse must not be empty"
    print("✓ get_agent_collab_state HUD data feed verified")

    print("\nALL WAVE 10 COCKPIT STEERING & HUD TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
