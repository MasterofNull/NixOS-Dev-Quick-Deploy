#!/usr/bin/env python3
"""Regression checks for deterministic local discovery opportunity generation."""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai-stack" / "local-agents"))

from discovery_agent import DiscoveryAgent


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


async def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        feedback = repo / "delegation-feedback.jsonl"
        output = repo / ".agents" / "improvement" / "candidates.json"

        _write(
            repo / ".agent" / "memory" / "issues-backlog.md",
            """[OPEN] discovery-agent-stub — proactive discovery agent is not doing opportunity analysis yet — Root cause: stub pass.
  Severity: high
  Action: Implement deterministic scanner.
  File: ai-stack/local-agents/discovery_agent.py
""",
        )
        _write(
            repo / ".agents" / "telemetry" / "hybrid-events.jsonl",
            json.dumps({
                "event_type": "health_spider_dashboard_degraded",
                "zone": "dashboard",
                "probe": "routing-analytics",
                "reason": "missing_keys=logic_discipline",
            }) + "\n",
        )
        _write(
            feedback,
            json.dumps({
                "timestamp": "2026-06-03T20:05:41Z",
                "failure_class": "json_contract_failed",
                "failure_classes": ["json_contract_failed"],
                "task_excerpt": "Reply with only the word PONG",
            }) + "\n",
        )
        _write(
            repo / "config" / "model-profile.json",
            json.dumps({
                "_meta": {"last_updated": "2026-05-01"},
                "model_id": "active.gguf",
                "probe_model_id": "active.gguf",
                "probed_at": "2026-05-01T00:00:00Z",
                "freshness_max_age_days": 1,
            }),
        )

        agent = DiscoveryAgent(
            tool_registry=object(),
            repo_root=repo,
            output_path=output,
            delegation_feedback_path=feedback,
        )
        payload = await agent.discover_opportunities()

        assert_true(output.exists(), "discovery agent should persist candidates.json")
        persisted = json.loads(output.read_text(encoding="utf-8"))
        assert_true(payload == persisted, "persisted payload should match returned payload")
        assert_true(payload.get("schema_version") == "discovery-candidates.v1", "schema version should be explicit")
        assert_true(payload.get("total_candidates", 0) >= 4, "expected issue, health, delegation, and model candidates")

        categories = {item.get("category") for item in payload.get("candidates", [])}
        assert_true("system-fix" in categories, "open issues should create system-fix candidates")
        assert_true("health-spider" in categories, "health-spider anomalies should create health candidates")
        assert_true("delegation-quality" in categories, "delegation feedback should create quality candidates")
        assert_true("model-catalog" in categories, "stale model profile should create model-catalog candidate")

        first = payload["candidates"][0]
        assert_true({"title", "category", "priority", "estimated_impact", "effort", "related_files"} <= set(first), "candidate should match dashboard summary contract")

    print("PASS: discovery agent emits deterministic improvement candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
