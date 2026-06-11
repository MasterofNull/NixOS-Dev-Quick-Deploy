#!/usr/bin/env python3
"""Phase 149: verify token_usage observability coverage for hybrid-coordinator delegations.

Pass criteria: ≥50% of coordinator model_call events in the last 100 coordinator events
have non-null tokens.total (real or estimated via char_count//4 fallback).
"""
import json
import sys
from pathlib import Path

EVENTS_PATH = Path("/var/lib/ai-stack/hybrid/telemetry/agent-run-events.jsonl")
MIN_EVENTS = 5
COVERAGE_THRESHOLD = 0.50
WINDOW = 100


def main() -> int:
    if not EVENTS_PATH.exists():
        print(f"SKIP: {EVENTS_PATH} not found (service not running)")
        return 0

    events: list[dict] = []
    with EVENTS_PATH.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    coordinator_model_calls = [
        e for e in events
        if e.get("source") == "hybrid-coordinator" and e.get("event_type") == "model_call"
    ]

    if len(coordinator_model_calls) < MIN_EVENTS:
        print(
            f"SKIP: only {len(coordinator_model_calls)} coordinator model_call events "
            f"(need ≥{MIN_EVENTS})"
        )
        return 0

    window = coordinator_model_calls[-WINDOW:]
    with_data = [
        e for e in window
        if (e.get("tokens") or {}).get("total") is not None
    ]
    coverage = len(with_data) / len(window)

    print(
        f"coordinator model_call events (last {len(window)}): "
        f"{len(with_data)} with tokens.total — coverage {coverage:.0%}"
    )

    if coverage < COVERAGE_THRESHOLD:
        print(
            f"FAIL: token_usage coverage {coverage:.0%} < {COVERAGE_THRESHOLD:.0%} threshold"
        )
        return 1

    print(f"PASS: token_usage coverage {coverage:.0%} ≥ {COVERAGE_THRESHOLD:.0%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
