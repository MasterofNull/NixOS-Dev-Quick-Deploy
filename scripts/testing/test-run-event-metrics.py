#!/usr/bin/env python3
"""
Tests for run_event_metrics module

Tests fixture JSONL with various scenarios:
- In-window and out-of-window events
- Malformed lines
- Empty timestamps
- Duplicate event_ids
- Local and remote lane events
- Succeeded and failed events
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add ai-stack/autonomous-improvement to path
_REPO_ROOT = Path(__file__).resolve().parents[2]
_AI_STACK = _REPO_ROOT / "ai-stack" / "autonomous-improvement"
if str(_AI_STACK) not in sys.path:
    sys.path.insert(0, str(_AI_STACK))

from run_event_metrics import collect_run_event_metrics


def make_event(
    event_id: str,
    event_type: str = "model_call",
    status: str = "succeeded",
    timestamp: str | None = None,
    source: str = "delegate-to-remote",
    lane_id: str | None = None,
    model: str | None = None,
    duration_ms: float | None = None,
    tokens: dict | None = None,
) -> dict:
    """Helper to create minimal valid agent-run event."""
    now = datetime.now(timezone.utc)
    ts = timestamp or now.isoformat().replace("+00:00", "Z")

    event = {
        "schema_version": "maeah.agent-run-event.v1",
        "event_id": event_id,
        "event_type": event_type,
        "timestamp": ts,
        "source": source,
        "run_id": "test-run-001",
        "status": status,
        "redaction": {
            "payload_redacted": False,
            "secret_fields": [],
        },
    }

    if lane_id is not None:
        event["lane_id"] = lane_id
    if model is not None:
        event["model"] = model
    if duration_ms is not None:
        event["duration_ms"] = duration_ms
    if tokens:
        event["tokens"] = tokens

    return event


def test_fixture_basic():
    """Test basic in-window events with metrics."""
    with tempfile.TemporaryDirectory() as tmpdir:
        fixture_path = Path(tmpdir) / "test-events.jsonl"

        now = datetime.now(timezone.utc)
        in_window = now - timedelta(hours=12)
        out_of_window = now - timedelta(hours=36)

        events = [
            # In-window succeeded events (source-based lane derivation)
            make_event("evt-001", source="delegate-to-local", status="succeeded", timestamp=in_window.isoformat().replace("+00:00", "Z"), duration_ms=100.0, tokens={"total": 1000, "accepted_artifact": 500}),
            make_event("evt-002", source="delegate-to-codex", status="succeeded", timestamp=in_window.isoformat().replace("+00:00", "Z"), duration_ms=200.0, tokens={"total": 2000, "accepted_artifact": 1500}),
            # In-window failed event
            make_event("evt-003", source="delegate-to-local", status="failed", timestamp=in_window.isoformat().replace("+00:00", "Z"), duration_ms=50.0, tokens={"total": 500, "accepted_artifact": 0}),
            # Out-of-window (should be skipped)
            make_event("evt-004", source="delegate-to-local", status="succeeded", timestamp=out_of_window.isoformat().replace("+00:00", "Z"), duration_ms=150.0),
        ]

        # Write events
        with fixture_path.open("w") as f:
            for event in events:
                f.write(json.dumps(event) + "\n")

        # Collect metrics
        snapshots, stats = collect_run_event_metrics(fixture_path, since_hours=24)

        # Verify collection stats
        assert stats.lines_read == 4, f"Expected 4 lines, got {stats.lines_read}"
        assert stats.events_validated == 4, f"Expected 4 validated, got {stats.events_validated}"
        assert stats.terminal_model_calls == 3, f"Expected 3 terminal calls (out-of-window skipped), got {stats.terminal_model_calls}"
        assert stats.local_lane_count == 2, f"Expected 2 local, got {stats.local_lane_count}"
        assert stats.remote_lane_count == 1, f"Expected 1 remote, got {stats.remote_lane_count}"
        assert stats.succeeded_count == 2, f"Expected 2 succeeded, got {stats.succeeded_count}"
        assert stats.failed_count == 1, f"Expected 1 failed, got {stats.failed_count}"

        # Verify metrics
        assert len(snapshots) == 4, f"Expected 4 snapshots, got {len(snapshots)}"

        metrics_by_name = {s.metric_name: s for s in snapshots}

        # local_routing_pct: 2 local out of 3 = 0.6667 (fraction, not percentage)
        local_pct = metrics_by_name.get("local_routing_pct")
        assert local_pct is not None, "Missing local_routing_pct metric"
        assert 0.65 < local_pct.metric_value < 0.68, f"Expected ~0.6667, got {local_pct.metric_value}"
        assert local_pct.metric_unit == "fraction", f"Expected unit 'fraction', got {local_pct.metric_unit}"

        # routing_success_rate: 2 succeeded out of 3 = 0.6667 (fraction, not percentage)
        success_rate = metrics_by_name.get("routing_success_rate")
        assert success_rate is not None, "Missing routing_success_rate metric"
        assert 0.65 < success_rate.metric_value < 0.68, f"Expected ~0.6667, got {success_rate.metric_value}"
        assert success_rate.metric_unit == "fraction", f"Expected unit 'fraction', got {success_rate.metric_unit}"

        # routing_latency_ms: mean of [100, 200, 50] = 116.67
        latency = metrics_by_name.get("routing_latency_ms")
        assert latency is not None, "Missing routing_latency_ms metric"
        assert 115.0 < latency.metric_value < 118.0, f"Expected ~116.67 ms, got {latency.metric_value}"

        # token_efficiency: (500 + 1500 + 0) / (1000 + 2000 + 500) = 2000 / 3500 = 0.571
        token_eff = metrics_by_name.get("token_efficiency")
        assert token_eff is not None, "Missing token_efficiency metric"
        assert 0.55 < token_eff.metric_value < 0.60, f"Expected ~0.571, got {token_eff.metric_value}"

        print("✅ test_fixture_basic PASSED")


def test_fixture_malformed():
    """Test handling of malformed lines and edge cases."""
    with tempfile.TemporaryDirectory() as tmpdir:
        fixture_path = Path(tmpdir) / "test-events.jsonl"

        now = datetime.now(timezone.utc)
        in_window = now - timedelta(hours=12)

        with fixture_path.open("w") as f:
            # Valid event (production source)
            f.write(json.dumps(make_event("evt-001", source="delegate-to-local", status="succeeded", timestamp=in_window.isoformat().replace("+00:00", "Z"))) + "\n")

            # Malformed JSON
            f.write("{ this is not valid json\n")

            # Valid event with missing timestamp (should skip)
            event_no_ts = make_event("evt-002", source="delegate-to-codex", status="succeeded")
            del event_no_ts["timestamp"]
            f.write(json.dumps(event_no_ts) + "\n")

            # Empty line
            f.write("\n")

            # Valid event (production source)
            f.write(json.dumps(make_event("evt-003", source="delegate-to-local", status="failed", timestamp=in_window.isoformat().replace("+00:00", "Z"))) + "\n")

        # Collect metrics
        snapshots, stats = collect_run_event_metrics(fixture_path, since_hours=24)

        assert stats.lines_read == 5, f"Expected 5 lines, got {stats.lines_read}"
        # Malformed JSON (1) + event without timestamp (2) = 2 malformed
        assert stats.lines_malformed == 2, f"Expected 2 malformed, got {stats.lines_malformed}"
        assert stats.lines_skipped >= 1, f"Expected >= 1 skipped (empty line), got {stats.lines_skipped}"
        assert stats.terminal_model_calls == 2, f"Expected 2 valid terminal calls, got {stats.terminal_model_calls}"

        print("✅ test_fixture_malformed PASSED")


def test_fixture_dedup():
    """Test deduplication by event_id."""
    with tempfile.TemporaryDirectory() as tmpdir:
        fixture_path = Path(tmpdir) / "test-events.jsonl"

        now = datetime.now(timezone.utc)
        in_window = now - timedelta(hours=12)

        with fixture_path.open("w") as f:
            # Same event_id written twice (source-based lane derivation)
            event = make_event("evt-001", source="delegate-to-local", status="succeeded", timestamp=in_window.isoformat().replace("+00:00", "Z"), duration_ms=100.0)
            f.write(json.dumps(event) + "\n")
            f.write(json.dumps(event) + "\n")

            # Different event_id
            f.write(json.dumps(make_event("evt-002", source="delegate-to-codex", status="succeeded", timestamp=in_window.isoformat().replace("+00:00", "Z"), duration_ms=200.0)) + "\n")

        # Collect metrics
        snapshots, stats = collect_run_event_metrics(fixture_path, since_hours=24)

        assert stats.terminal_model_calls == 2, f"Expected 2 (after dedup), got {stats.terminal_model_calls}"
        assert stats.deduped_count == 1, f"Expected 1 deduped, got {stats.deduped_count}"

        print("✅ test_fixture_dedup PASSED")


def test_fixture_non_production_exclusion():
    """Test exclusion of non-production cohorts (fixtures, test runs, etc.)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        fixture_path = Path(tmpdir) / "test-events.jsonl"

        now = datetime.now(timezone.utc)
        in_window = now - timedelta(hours=12)

        with fixture_path.open("w") as f:
            # Production event (should count)
            f.write(json.dumps(make_event("evt-001", source="delegate-to-local", status="succeeded", timestamp=in_window.isoformat().replace("+00:00", "Z"))) + "\n")

            # Non-production: race-harness-fixture (should be excluded)
            f.write(json.dumps(make_event("evt-002", source="race-harness-fixture", status="succeeded", timestamp=in_window.isoformat().replace("+00:00", "Z"))) + "\n")

            # Non-production: test-agent (should be excluded)
            f.write(json.dumps(make_event("evt-003", source="test-agent", status="succeeded", timestamp=in_window.isoformat().replace("+00:00", "Z"))) + "\n")

            # Production event (should count)
            f.write(json.dumps(make_event("evt-004", source="delegate-to-codex", status="failed", timestamp=in_window.isoformat().replace("+00:00", "Z"))) + "\n")

            # Non-production: replay-events (should be excluded)
            f.write(json.dumps(make_event("evt-005", source="replay-events", status="succeeded", timestamp=in_window.isoformat().replace("+00:00", "Z"))) + "\n")

        # Collect metrics
        snapshots, stats = collect_run_event_metrics(fixture_path, since_hours=24)

        assert stats.lines_read == 5, f"Expected 5 lines, got {stats.lines_read}"
        assert stats.terminal_model_calls == 2, f"Expected 2 terminal calls (after exclusion), got {stats.terminal_model_calls}"
        assert stats.excluded_non_production == 3, f"Expected 3 excluded, got {stats.excluded_non_production}"
        assert stats.local_lane_count == 1, f"Expected 1 local, got {stats.local_lane_count}"
        assert stats.remote_lane_count == 1, f"Expected 1 remote, got {stats.remote_lane_count}"
        assert "delegate-to-local" in stats.per_source_counts, "Missing delegate-to-local in per_source_counts"
        assert stats.per_source_counts["delegate-to-local"] == 1, f"Expected 1 for delegate-to-local, got {stats.per_source_counts.get('delegate-to-local', 0)}"

        print("✅ test_fixture_non_production_exclusion PASSED")


def test_fixture_zero_eligible():
    """Test zero-eligible fixture (no metrics produced)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        fixture_path = Path(tmpdir) / "test-events.jsonl"

        # Write only non-model_call events
        with fixture_path.open("w") as f:
            event = make_event("evt-001", event_type="tool_call", source="delegate-to-local")
            f.write(json.dumps(event) + "\n")

        # Collect metrics
        snapshots, stats = collect_run_event_metrics(fixture_path, since_hours=24)

        assert len(snapshots) == 0, f"Expected 0 snapshots, got {len(snapshots)}"
        assert stats.terminal_model_calls == 0, f"Expected 0 terminal calls, got {stats.terminal_model_calls}"

        print("✅ test_fixture_zero_eligible PASSED")


def test_smoke_real_file():
    """Smoke test against real agent-run-events.jsonl if readable (< 20s)."""
    import os

    events_path = Path(os.environ.get(
        "AQ_AGENT_RUN_EVENTS_PATH",
        "/var/lib/ai-stack/hybrid/telemetry/agent-run-events.jsonl"
    ))

    if not events_path.exists():
        print("⏭️  Skipping smoke test (real file not found)")
        return

    if not os.access(str(events_path), os.R_OK):
        print("⏭️  Skipping smoke test (real file not readable)")
        return

    print(f"🔄 Smoke test against: {events_path}")

    start = time.time()
    snapshots, stats = collect_run_event_metrics(events_path, since_hours=24)
    elapsed = time.time() - start

    assert elapsed < 20.0, f"Collection took {elapsed:.1f}s (must be < 20s)"

    print(f"   ✅ Completed in {elapsed:.1f}s")
    print(f"   Terminal model_call events: {stats.terminal_model_calls}")
    print(f"   Excluded (non-production): {stats.excluded_non_production}")
    print(f"   Metrics produced: {len(snapshots)}")
    print(f"   Lane breakdown: local={stats.local_lane_count}, remote={stats.remote_lane_count}, unknown={stats.unknown_lane_count}")

    if stats.terminal_model_calls > 0:
        success_rate = stats.succeeded_count / (stats.succeeded_count + stats.failed_count) if (stats.succeeded_count + stats.failed_count) > 0 else 0
        print(f"   Success rate: {success_rate:.1%} ({stats.succeeded_count} succeeded, {stats.failed_count} failed)")

    if stats.per_source_counts:
        print(f"   Per-source breakdown:")
        for source, count in sorted(stats.per_source_counts.items(), key=lambda x: -x[1])[:5]:
            print(f"      {source}: {count}")

    print("✅ test_smoke_real_file PASSED")


def main():
    """Run all tests."""
    print("🧪 Running run_event_metrics tests\n")

    try:
        test_fixture_basic()
        test_fixture_malformed()
        test_fixture_dedup()
        test_fixture_non_production_exclusion()
        test_fixture_zero_eligible()
        test_smoke_real_file()

        print("\n✅ All tests passed!")
        return 0
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
