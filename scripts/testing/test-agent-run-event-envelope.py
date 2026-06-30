#!/usr/bin/env python3
"""Regression coverage for the Phase 93.1 agent-run event envelope."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ai" / "lib"))
os.environ.setdefault("AI_STRICT_ENV", "false")

import agent_run_events as events  # noqa: E402

SCHEMA = ROOT / "config" / "schemas" / "maeah" / "agent-run-event.schema.json"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_schema_contract() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert_true(schema["properties"]["schema_version"]["const"] == events.SCHEMA_VERSION, "schema version mismatch")
    schema_event_types = set(schema["properties"]["event_type"]["enum"])
    assert_true(schema_event_types == events.EVENT_TYPES, "event type enum mismatch")
    required = set(schema["required"])
    for key in ("schema_version", "event_id", "event_type", "timestamp", "source", "run_id", "status", "redaction"):
        assert_true(key in required, f"schema missing required key {key}")


def test_full_replay_fixture() -> None:
    run_id = "run-phase93-fixture"
    common = {
        "source": "test-agent-run-event-envelope",
        "run_id": run_id,
        "experiment_id": "exp-spec-race-fixture",
        "session_id": "session-fixture",
        "agent_id": "codex-fixture",
        "role": "implementer",
        "autonomy_boundary": "auto_ok",
        "lane_id": "markdown",
        "slice_id": "93.1",
    }
    records = [
        events.make_event("prompt_load", **common, payload={"prompt_hash": events.stable_digest("build card")}),
        events.make_event(
            "spec_variant",
            **common,
            spec={
                "variant": "markdown",
                "canonical_path": ".agents/plans/EFFECTIVENESS-CENTERED-SYSTEM-IMPROVEMENT-PRD.md",
                "source_hash": "sha256:fixture",
            },
        ),
        events.make_event("system_prompt", **common, payload={"system_prompt_hash": events.stable_digest("safe excerpt")}),
        events.make_event("memory_recall", **common, payload={"collections": ["best-practices"], "hits": 2}),
        events.make_event("skill_load", **common, payload={"skills": ["multi-agent-collab", "slice-authoring"]}),
        events.make_event(
            "planning",
            **common,
            payload={
                "plan_step": "inspect-before-edit",
                "rationale_summary": "Use deterministic file reads before patching.",
                "evidence_refs": ["fixture"],
            },
        ),
        events.make_event("model_call", **common, model="qwen3.6", route_profile="local-tool-calling", duration_ms=42),
        events.make_event(
            "thought",
            **common,
            payload={
                "kind": "local_model_reasoning_block",
                "summary": "Local model emitted an internal reasoning block; raw chain-of-thought was suppressed.",
                "char_count": 42,
                "content_hash": events.stable_digest("internal reasoning fixture"),
                "redaction_level": "raw_reasoning_suppressed",
            },
        ),
        events.make_event("tool_call", **common, tool_name="rg", payload={"args": ["rg", "agent"], "api_token": "do-not-leak"}),
        events.make_event("tool_result", **common, tool_name="rg", status="succeeded", payload={"stdout_tail": "agent"}),
        events.make_event("token_usage", **common, tokens={"input": 100, "output": 50, "tool_output": 25, "accepted_artifact": 70}),
        events.make_event("artifact", **common, artifact={"path": "dashboard.html", "kind": "ui", "hash": "sha256:artifact", "accepted": True}),
        events.make_event("validation", **common, payload={"command": "aq-qa 0", "result": "pass"}),
        events.make_event("review", **common, payload={"verdict": "PASS"}),
        events.make_event("human_control", **common, payload={"action": "approve", "operator": "human"}),
        events.make_event("final_outcome", **common, status="succeeded", payload={"final_ok": True}),
    ]

    timeline = events.reconstruct_timeline(reversed(records))
    assert_true(len(timeline) == len(events.EVENT_TYPES), "expected all fixture events in replay timeline")
    assert_true({item["event_type"] for item in timeline} == events.EVENT_TYPES, "fixture should cover every event type")

    tool_event = next(item for item in timeline if item["event_type"] == "tool_call")
    assert_true(tool_event["payload"]["api_token"] == "[REDACTED]", "expected token payload redaction")
    assert_true(tool_event["redaction"]["payload_redacted"], "expected redaction flag")
    assert_true("api_token" in tool_event["redaction"]["secret_fields"], "expected secret field path")

    token_event = next(item for item in timeline if item["event_type"] == "token_usage")
    assert_true(token_event["tokens"]["total"] == 175, "expected total token derivation")
    assert_true(token_event["tokens"]["useful_ratio"] == 0.4, "expected useful-token ratio derivation")


def test_jsonl_round_trip() -> None:
    event = events.make_event(
        "final_outcome",
        source="test-agent-run-event-envelope",
        run_id="run-jsonl-roundtrip",
        status="succeeded",
        payload={"final_ok": True},
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "agent-run-events.jsonl"
        events.append_jsonl(path, event)
        loaded = events.load_jsonl(path)
    assert_true(loaded == [event], "expected JSONL round trip to preserve event")


def test_emit_event_writes_canonical_stream_and_latest_projection() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        path = root / "events" / "agent-run-events.jsonl"
        event = events.emit_event(
            "model_call",
            root=root,
            event_path=path,
            source="test-agent-run-event-envelope",
            run_id="run/with spaces",
            status="running",
            payload={"progress": "streaming", "api_token": "do-not-leak", "tokens_out": 12, "max_tokens": 1200},
            tokens={"output": 12},
        )
        loaded = events.load_jsonl(path)
        latest = events.latest_projection_path("run/with spaces", root)
        projection = json.loads(latest.read_text(encoding="utf-8"))

    assert_true(loaded == [event], "emit_event must append to canonical stream")
    assert_true(latest.name == "run_with_spaces.json", "latest projection must sanitize run_id")
    assert_true(projection["latest_event"]["event_id"] == event["event_id"], "latest projection must track newest event")
    assert_true(projection["latest_event"]["payload"]["api_token"] == "[REDACTED]", "projection must use redacted event")
    assert_true(projection["latest_event"]["payload"]["tokens_out"] == 12, "numeric token telemetry must stay visible")
    assert_true(projection["latest_event"]["payload"]["max_tokens"] == 1200, "numeric max-token telemetry must stay visible")


def test_validation_rejects_bad_data() -> None:
    try:
        events.make_event("not_real", source="test", run_id="run")
    except ValueError as exc:
        assert_true("invalid event_type" in str(exc), "expected invalid event_type error")
    else:
        raise AssertionError("invalid event type should fail")

    try:
        events.make_event("token_usage", source="test", run_id="run", tokens={"useful_ratio": 2})
    except ValueError as exc:
        assert_true("useful_ratio" in str(exc), "expected useful_ratio bounds error")
    else:
        raise AssertionError("invalid useful_ratio should fail")


def main() -> int:
    test_schema_contract()
    test_full_replay_fixture()
    test_jsonl_round_trip()
    test_emit_event_writes_canonical_stream_and_latest_projection()
    test_validation_rejects_bad_data()
    print("PASS: agent-run event envelope schema, redaction, replay, useful-token attribution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
