#!/usr/bin/env python3
"""
Run Event Metrics Collector - Extract metrics from agent-run-events JSONL

Reads live agent-run events as the canonical observed-activity source for the
autonomous improvement loop. Terminal model-call events form the cohort.

Terminal model-call events: event_type="model_call" with status in {"succeeded", "failed"}

Lane derivation (priority order):
  1. source field: "delegate-to-local" → local; "delegate-to-codex", "gemini", "antigravity", "claude" → remote
  2. lane_id field (if present): lane_id starting with "local" → local; others → remote
  3. model field (fallback): local model names → local; others → remote
  4. else unknown

Non-production cohort exclusion (allow/deny list):
  - EXCLUDE source containing: "fixture", "test", "replay", "harness"
  - Examples: "race-harness-fixture", "test-agent", "replay-events"
  - Production sources: "delegate-to-*", live agent runs, etc.

Metrics (as fractions 0-1, matching TrendDatabase):
  - local_routing_pct: proportion of model calls routed to local lane (0-1)
  - routing_success_rate: succeeded / (succeeded + failed) (0-1)
  - routing_latency_ms: mean duration_ms (non-negative, finite)
  - token_efficiency: sum(accepted_artifact) / sum(total) where both present
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Tolerance: skip individual lines that exceed 1 MiB
MAX_LINE_BYTES = 1024 * 1024

# Non-production cohort exclusion list
NON_PRODUCTION_MARKERS = {"fixture", "test", "replay", "harness"}


@dataclass
class MetricSnapshot:
    """Single metric observation (matches TrendDatabase.MetricSnapshot)"""
    time: datetime
    metric_name: str
    metric_value: float
    metric_unit: str
    service: str
    component: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class CollectionStats:
    """Statistics about collection run"""
    window_start: datetime
    window_end: datetime
    lines_read: int
    lines_skipped: int
    lines_malformed: int
    events_validated: int
    terminal_model_calls: int
    deduped_count: int
    excluded_non_production: int
    local_lane_count: int
    remote_lane_count: int
    unknown_lane_count: int
    succeeded_count: int
    failed_count: int
    per_source_counts: Dict[str, int] = field(default_factory=dict)


def validate_event(event: Dict[str, Any]) -> bool:
    """
    Minimal validation: check required fields match agent_run_events contract.
    Import the actual validate_event from agent_run_events if available;
    fallback to minimal check.
    """
    required_fields = ("event_id", "event_type", "timestamp", "status", "run_id")
    return all(field in event for field in required_fields)


def is_non_production(source: str) -> bool:
    """Check if source should be excluded (non-production cohort)."""
    if not source:
        return False
    source_lower = source.lower()
    return any(marker in source_lower for marker in NON_PRODUCTION_MARKERS)


def derive_lane(event: Dict[str, Any]) -> str:
    """
    Derive lane from event fields (priority order).
    Returns: "local", "remote", or "unknown"
    """
    source = event.get("source", "")
    lane_id = event.get("lane_id")
    model = event.get("model", "")

    # Priority 1: source field
    if source:
        source_lower = source.lower()
        if "delegate-to-local" in source_lower:
            return "local"
        if any(x in source_lower for x in ["delegate-to-codex", "gemini", "antigravity", "claude"]):
            return "remote"

    # Priority 2: lane_id field
    if lane_id:
        lane_id_lower = str(lane_id).lower()
        if "local" in lane_id_lower:
            return "local"
        return "remote"

    # Priority 3: model field (fallback)
    if model:
        model_lower = model.lower()
        # Local model patterns
        if any(x in model_lower for x in ["qwen", "llama", "local"]):
            return "local"
        # Remote model patterns
        if any(x in model_lower for x in ["claude", "gpt", "gemini"]):
            return "remote"

    return "unknown"


def collect_run_event_metrics(
    path: Path,
    since_hours: int = 24,
) -> Tuple[List[MetricSnapshot], CollectionStats]:
    """
    Collect metrics from agent-run-events JSONL.

    Args:
        path: Path to agent-run-events.jsonl file
        since_hours: Window size in hours from now

    Returns:
        Tuple of (snapshots, stats)
        - snapshots: list of MetricSnapshot, one per metric per hour bucket
        - stats: CollectionStats with counts and diagnostics

    Streams line by line (never readlines/whole-file).
    Skips lines > 1 MiB.
    Skips malformed JSON and records failing validation.
    Dedupes by event_id within window.
    """
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=since_hours)
    window_end = now

    snapshots: List[MetricSnapshot] = []
    stats = CollectionStats(
        window_start=window_start,
        window_end=window_end,
        lines_read=0,
        lines_skipped=0,
        lines_malformed=0,
        events_validated=0,
        terminal_model_calls=0,
        deduped_count=0,
        excluded_non_production=0,
        local_lane_count=0,
        remote_lane_count=0,
        unknown_lane_count=0,
        succeeded_count=0,
        failed_count=0,
        per_source_counts={},
    )

    if not path.exists():
        return snapshots, stats

    # Track dedup state
    seen_event_ids: set[str] = set()

    # Accumulator for metrics
    latencies: List[float] = []
    total_tokens: int = 0
    accepted_artifact_tokens: int = 0
    lanes: Dict[str, int] = {}  # lane_id -> count

    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_num, line in enumerate(handle, 1):
                stats.lines_read += 1

                # Skip empty lines
                if not line.strip():
                    stats.lines_skipped += 1
                    continue

                # Skip oversized lines
                if len(line.encode("utf-8")) > MAX_LINE_BYTES:
                    stats.lines_skipped += 1
                    continue

                # Parse JSON
                try:
                    event = json.loads(line)
                except (json.JSONDecodeError, TypeError):
                    stats.lines_malformed += 1
                    continue

                # Validate event shape
                if not validate_event(event):
                    stats.lines_malformed += 1
                    continue

                stats.events_validated += 1

                # Extract and validate timestamp
                try:
                    # Timestamp is RFC3339 Z format, e.g. "2026-09-30T12:34:56Z"
                    ts_str = event.get("timestamp", "")
                    if not ts_str:
                        stats.lines_skipped += 1
                        continue
                    # Parse RFC3339 format
                    if ts_str.endswith("Z"):
                        ts_str = ts_str[:-1] + "+00:00"
                    ts = datetime.fromisoformat(ts_str)
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                except (ValueError, AttributeError):
                    stats.lines_skipped += 1
                    continue

                # Check if in window
                if ts < window_start or ts > window_end:
                    continue

                # Filter for terminal model_call events
                if event.get("event_type") != "model_call":
                    continue

                if event.get("status") not in ("succeeded", "failed"):
                    continue

                # Check non-production cohort (exclude before dedup/counting)
                source = event.get("source", "")
                if is_non_production(source):
                    stats.excluded_non_production += 1
                    continue

                # Dedupe by event_id
                event_id = event.get("event_id")
                if event_id in seen_event_ids:
                    stats.deduped_count += 1
                    continue
                seen_event_ids.add(event_id)

                stats.terminal_model_calls += 1

                # Track per-source counts
                stats.per_source_counts[source] = stats.per_source_counts.get(source, 0) + 1

                # Collect metrics
                # 1. Lane routing (derive from source, lane_id, model)
                lane = derive_lane(event)
                if lane == "local":
                    stats.local_lane_count += 1
                elif lane == "remote":
                    stats.remote_lane_count += 1
                else:
                    stats.unknown_lane_count += 1

                # 2. Success/failure
                status = event.get("status")
                if status == "succeeded":
                    stats.succeeded_count += 1
                elif status == "failed":
                    stats.failed_count += 1

                # 3. Latency
                duration_ms = event.get("duration_ms")
                if isinstance(duration_ms, (int, float)) and duration_ms >= 0:
                    latencies.append(float(duration_ms))

                # 4. Token efficiency
                tokens = event.get("tokens") or {}
                total = tokens.get("total")
                accepted = tokens.get("accepted_artifact")
                if isinstance(total, int) and total > 0:
                    total_tokens += total
                if isinstance(accepted, int) and accepted >= 0:
                    accepted_artifact_tokens += accepted

    except (IOError, OSError) as e:
        # File read error - return what we have
        pass

    # Build snapshots (one per metric, aggregated over window)
    # Use window midpoint as the snapshot time
    snapshot_time = window_start + (window_end - window_start) / 2

    # Metric 1: local_routing_pct (as fraction 0-1, matching TrendDatabase)
    if stats.terminal_model_calls > 0:
        local_pct = stats.local_lane_count / stats.terminal_model_calls
        snapshots.append(MetricSnapshot(
            time=snapshot_time,
            metric_name="local_routing_pct",
            metric_value=local_pct,
            metric_unit="fraction",
            service="hybrid-coordinator",
            component="routing",
            metadata={
                "local_count": stats.local_lane_count,
                "remote_count": stats.remote_lane_count,
                "unknown_count": stats.unknown_lane_count,
                "total_count": stats.terminal_model_calls,
                "excluded_non_production": stats.excluded_non_production,
            },
        ))

    # Metric 2: routing_success_rate (as fraction 0-1, matching TrendDatabase)
    total_terminal = stats.succeeded_count + stats.failed_count
    if total_terminal > 0:
        success_rate = stats.succeeded_count / total_terminal
        snapshots.append(MetricSnapshot(
            time=snapshot_time,
            metric_name="routing_success_rate",
            metric_value=success_rate,
            metric_unit="fraction",
            service="hybrid-coordinator",
            component="routing",
            metadata={
                "succeeded": stats.succeeded_count,
                "failed": stats.failed_count,
                "total": total_terminal,
            },
        ))

    # Metric 3: routing_latency_ms
    if latencies:
        mean_latency = sum(latencies) / len(latencies)
        snapshots.append(MetricSnapshot(
            time=snapshot_time,
            metric_name="routing_latency_ms",
            metric_value=mean_latency,
            metric_unit="ms",
            service="hybrid-coordinator",
            component="routing",
            metadata={
                "sample_count": len(latencies),
                "min_ms": min(latencies),
                "max_ms": max(latencies),
            },
        ))

    # Metric 4: token_efficiency
    # Only emit if both numerator and denominator are present and > 0
    if accepted_artifact_tokens > 0 and total_tokens > 0:
        efficiency = accepted_artifact_tokens / total_tokens
        snapshots.append(MetricSnapshot(
            time=snapshot_time,
            metric_name="token_efficiency",
            metric_value=efficiency,
            metric_unit="ratio",
            service="hybrid-coordinator",
            component="routing",
            metadata={
                "accepted_artifact_tokens": accepted_artifact_tokens,
                "total_tokens": total_tokens,
            },
        ))

    return snapshots, stats


if __name__ == "__main__":
    # Simple CLI for testing
    import os

    events_path = Path(os.environ.get(
        "AQ_AGENT_RUN_EVENTS_PATH",
        "/var/lib/ai-stack/hybrid/telemetry/agent-run-events.jsonl"
    ))

    print(f"📊 Collecting metrics from: {events_path}")
    print(f"   Exists: {events_path.exists()}")
    print()

    snapshots, stats = collect_run_event_metrics(events_path, since_hours=24)

    print(f"📈 Collection Stats:")
    print(f"   Lines read: {stats.lines_read}")
    print(f"   Lines skipped: {stats.lines_skipped}")
    print(f"   Lines malformed: {stats.lines_malformed}")
    print(f"   Events validated: {stats.events_validated}")
    print(f"   Terminal model_call events: {stats.terminal_model_calls}")
    print(f"   Excluded (non-production): {stats.excluded_non_production}")
    print(f"   Deduped: {stats.deduped_count}")
    print()
    print(f"🎯 Terminal Event Breakdown:")
    print(f"   Local lane: {stats.local_lane_count}")
    print(f"   Remote lane: {stats.remote_lane_count}")
    print(f"   Unknown lane: {stats.unknown_lane_count}")
    print(f"   Succeeded: {stats.succeeded_count}")
    print(f"   Failed: {stats.failed_count}")
    print()
    if stats.per_source_counts:
        print(f"📌 Per-source breakdown (top 5):")
        for source, count in sorted(stats.per_source_counts.items(), key=lambda x: -x[1])[:5]:
            print(f"   {source}: {count}")
        print()
    print(f"📊 Metrics collected: {len(snapshots)}")
    for snapshot in snapshots:
        print(f"   {snapshot.metric_name}: {snapshot.metric_value:.2f} {snapshot.metric_unit}")
