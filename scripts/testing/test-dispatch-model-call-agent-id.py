#!/usr/bin/env python3
"""Behavioural test: verify dispatch.py sets agent_id and lane_id on model_call events.

Verifies:
1. Default behavior: agent_id == 'local-qwen' and lane_id == 'local' (delegate-to-local source);
   other sources fall back to role-or-source / 'unknown'.
2. Environment overrides: AQ_AGENT_ID and AQ_LANE_ID override defaults when present.
3. Partial overrides: each env var overrides independently while the other retains default.

Exits 0 and prints PASS on success.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

# Add scripts/ai/lib to path so dispatch and agent_run_events resolve
LIB_DIR = Path(__file__).resolve().parents[1] / "ai" / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

import dispatch  # noqa: E402


def read_latest_event(event_file: Path) -> dict:
    with open(event_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    if not lines:
        raise AssertionError(f"No events written to {event_file}")
    return json.loads(lines[-1])


def run_tests() -> None:
    # Save original environment to restore afterwards
    orig_agent_id = os.environ.get("AQ_AGENT_ID")
    orig_lane_id = os.environ.get("AQ_LANE_ID")
    orig_events_path = os.environ.get("AQ_AGENT_RUN_EVENTS_PATH")
    orig_repo_root = os.environ.get("REPO_ROOT")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        event_file = tmp_path / "telemetry" / "agent-run-events.jsonl"
        os.environ["AQ_AGENT_RUN_EVENTS_PATH"] = str(event_file)
        os.environ["REPO_ROOT"] = str(tmp_path)

        # -------------------------------------------------------------
        # Test 1: Default behavior (neither AQ_AGENT_ID nor AQ_LANE_ID set)
        # -------------------------------------------------------------
        os.environ.pop("AQ_AGENT_ID", None)
        os.environ.pop("AQ_LANE_ID", None)

        progress_file1 = tmp_path / "run1.progress.json"
        dispatch._write_progress(
            progress_file=progress_file1,
            tokens_out=25,
            max_tokens=100,
            elapsed_s=1.5,
            tok_per_sec=16.7,
            eta_s=4.5,
            status="running",
            run_id="run-default-test",
            source="delegate-to-local",
        )

        event1 = read_latest_event(event_file)
        assert event1["event_type"] == "model_call", f"Expected model_call, got {event1['event_type']}"
        assert event1["run_id"] == "run-default-test", f"Unexpected run_id: {event1['run_id']}"
        assert event1["agent_id"] == "local-qwen", f"Expected agent_id == 'local-qwen', got {event1['agent_id']!r}"
        assert event1["lane_id"] == "local", f"Expected lane_id == 'local', got {event1['lane_id']!r}"
        assert event1["route_profile"] == "local-direct", f"Expected route_profile == 'local-direct', got {event1['route_profile']!r}"
        assert event1["payload"].get("agent_id") == "local-qwen", f"Expected payload.agent_id == 'local-qwen', got {event1['payload'].get('agent_id')!r}"
        assert event1["payload"].get("lane_id") == "local", f"Expected payload.lane_id == 'local', got {event1['payload'].get('lane_id')!r}"
        print("  [OK] Default: agent_id='local-qwen', lane_id='local'")

        # -------------------------------------------------------------
        # Test 2: Both environment overrides active
        # -------------------------------------------------------------
        os.environ["AQ_AGENT_ID"] = "custom-agent-42"
        os.environ["AQ_LANE_ID"] = "custom-lane-fast"

        progress_file2 = tmp_path / "run2.progress.json"
        dispatch._write_progress(
            progress_file=progress_file2,
            tokens_out=100,
            max_tokens=100,
            elapsed_s=3.0,
            tok_per_sec=33.3,
            eta_s=None,
            status="done",
            run_id="run-both-overrides",
            source="delegate-to-local",
        )

        event2 = read_latest_event(event_file)
        assert event2["event_type"] == "model_call", f"Expected model_call, got {event2['event_type']}"
        assert event2["run_id"] == "run-both-overrides", f"Unexpected run_id: {event2['run_id']}"
        assert event2["agent_id"] == "custom-agent-42", f"Expected agent_id == 'custom-agent-42', got {event2['agent_id']!r}"
        assert event2["lane_id"] == "custom-lane-fast", f"Expected lane_id == 'custom-lane-fast', got {event2['lane_id']!r}"
        assert event2["payload"].get("agent_id") == "custom-agent-42", f"Expected payload.agent_id == 'custom-agent-42', got {event2['payload'].get('agent_id')!r}"
        assert event2["payload"].get("lane_id") == "custom-lane-fast", f"Expected payload.lane_id == 'custom-lane-fast', got {event2['payload'].get('lane_id')!r}"
        print("  [OK] Overrides: agent_id='custom-agent-42', lane_id='custom-lane-fast'")

        # -------------------------------------------------------------
        # Test 3: Only AQ_AGENT_ID overridden
        # -------------------------------------------------------------
        os.environ["AQ_AGENT_ID"] = "solo-agent"
        os.environ.pop("AQ_LANE_ID", None)

        progress_file3 = tmp_path / "run3.progress.json"
        dispatch._write_progress(
            progress_file=progress_file3,
            tokens_out=50,
            max_tokens=100,
            elapsed_s=2.0,
            tok_per_sec=25.0,
            eta_s=2.0,
            status="running",
            run_id="run-agent-override-only",
        )

        event3 = read_latest_event(event_file)
        assert event3["agent_id"] == "solo-agent", f"Expected agent_id == 'solo-agent', got {event3['agent_id']!r}"
        assert event3["lane_id"] == "local", f"Expected lane_id == 'local', got {event3['lane_id']!r}"
        assert event3["payload"].get("agent_id") == "solo-agent"
        assert event3["payload"].get("lane_id") == "local"
        print("  [OK] Partial: agent_id='solo-agent', lane_id='local' (default)")

        # -------------------------------------------------------------
        # Test 4: Only AQ_LANE_ID overridden
        # -------------------------------------------------------------
        os.environ.pop("AQ_AGENT_ID", None)
        os.environ["AQ_LANE_ID"] = "lane-dedicated"

        progress_file4 = tmp_path / "run4.progress.json"
        dispatch._write_progress(
            progress_file=progress_file4,
            tokens_out=75,
            max_tokens=100,
            elapsed_s=2.5,
            tok_per_sec=30.0,
            eta_s=0.8,
            status="running",
            run_id="run-lane-override-only",
        )

        event4 = read_latest_event(event_file)
        assert event4["agent_id"] == "local-qwen", f"Expected agent_id == 'local-qwen', got {event4['agent_id']!r}"
        assert event4["lane_id"] == "lane-dedicated", f"Expected lane_id == 'lane-dedicated', got {event4['lane_id']!r}"
        assert event4["payload"].get("agent_id") == "local-qwen"
        assert event4["payload"].get("lane_id") == "lane-dedicated"
        print("  [OK] Partial: agent_id='local-qwen' (default), lane_id='lane-dedicated'")

        # -------------------------------------------------------------
        # Test 5: Non-local source falls back to role-or-source / 'unknown'
        # -------------------------------------------------------------
        os.environ.pop("AQ_AGENT_ID", None)
        os.environ.pop("AQ_LANE_ID", None)

        dispatch._write_progress(
            progress_file=tmp_path / "run5.progress.json",
            tokens_out=5, max_tokens=100, elapsed_s=1.0, tok_per_sec=5.0,
            eta_s=None, status="done", run_id="run-role-fallback",
            source="aq-chat", role="reviewer",
        )
        event5 = read_latest_event(event_file)
        assert event5["agent_id"] == "reviewer", f"got {event5['agent_id']!r}"
        assert event5["lane_id"] == "unknown", f"got {event5['lane_id']!r}"

        dispatch._write_progress(
            progress_file=tmp_path / "run6.progress.json",
            tokens_out=5, max_tokens=100, elapsed_s=1.0, tok_per_sec=5.0,
            eta_s=None, status="done", run_id="run-source-fallback",
            source="aq-chat",
        )
        event6 = read_latest_event(event_file)
        assert event6["agent_id"] == "aq-chat", f"got {event6['agent_id']!r}"
        assert event6["lane_id"] == "unknown", f"got {event6['lane_id']!r}"
        print("  [OK] Non-local source: agent_id=role-or-source, lane_id='unknown'")

    # Restore environment
    if orig_agent_id is not None:
        os.environ["AQ_AGENT_ID"] = orig_agent_id
    else:
        os.environ.pop("AQ_AGENT_ID", None)

    if orig_lane_id is not None:
        os.environ["AQ_LANE_ID"] = orig_lane_id
    else:
        os.environ.pop("AQ_LANE_ID", None)

    if orig_events_path is not None:
        os.environ["AQ_AGENT_RUN_EVENTS_PATH"] = orig_events_path
    else:
        os.environ.pop("AQ_AGENT_RUN_EVENTS_PATH", None)

    if orig_repo_root is not None:
        os.environ["REPO_ROOT"] = orig_repo_root
    else:
        os.environ.pop("REPO_ROOT", None)

    print("\nPASS")


if __name__ == "__main__":
    try:
        run_tests()
        sys.exit(0)
    except AssertionError as e:
        print(f"\nFAIL: {e}", file=sys.stderr)
        sys.exit(1)
