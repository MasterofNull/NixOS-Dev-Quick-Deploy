#!/usr/bin/env python3
"""Regression checks for aq-operational-perspective evidence bundles."""

from __future__ import annotations

import importlib.util
import io
import json
import contextlib
from pathlib import Path
from importlib.machinery import SourceFileLoader


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "ai" / "aq-operational-perspective"


def _load_module():
    loader = SourceFileLoader("aq_operational_perspective_test", str(MODULE_PATH))
    spec = importlib.util.spec_from_loader("aq_operational_perspective_test", loader)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    module = _load_module()

    observed = module._build_observed_signals(
        {"passed": 40, "failed": 1, "skipped": 0},
        {
            "continue_editor": {"available": True, "healthy": False, "failure_categories": [["state_budget", 1]], "state_budget": {"status": "warn"}},
            "rag_posture": {
                "memory_recall_share_pct": 8.0,
                "memory_recall_miss_pct": 55.0,
                "memory_recall_diagnosis": "weak",
                "memory_recall_actions": ["refresh summaries"],
            },
            "tool_performance": {
                "qa_check": {"p95_ms": 9500, "ok_pct": 100.0, "calls": 3, "client_error_count": 0, "server_error_count": 0, "unknown_count": 0},
            },
            "route_search_latency_decomposition": {"overall_p95_ms": 8200, "actionable_p95_ms": 6100, "client_error_count": 1, "backend_unclassified_count": 0},
            "remote_profile_utilization": {"available": True, "total_calls": 4, "success_pct": 50.0, "fallback_applied": 2, "top_profiles": [["remote-coding", 3]], "top_backend_reason_classes": [["rate_limit", 2]]},
            "delegated_prompt_failures": {"available": True, "total_failures": 2, "salvageable_pct": 50.0, "recovered_failures": 1, "top_failure_classes": [["schema_mismatch", 2]]},
            "delegated_prompt_failure_windows": {"trend": {"status": "warn", "summary": "failures rising"}},
            "provider_fallback_recovery": {"recovered_count": 2, "recovered_pct": 25.0, "diagnosis": "provider_fallback_pressure", "actions": ["tighten retries"]},
            "llama_benchmark_summary": {"latest_run": {"run_id": "bench-1", "avg_warm_latency_s": 2.4, "peak_rss_mb": 24500, "avg_gpu_busy_percent": 61}},
        },
        {"recommended_scope": "context-offload", "preflight_commands": ["aq-qa 0 --json"]},
        {"items": [{"fact_id": "abc", "content": "resume checkpoint"}]},
        {"summary_lines": ["Latest checkpoint event: resume checkpoint"]},
    )
    constraints = module._build_inferred_constraints(observed)
    unknowns = module._build_unknowns(observed)

    assert_true(any("Phase-0 harness health" in item for item in constraints), "expected QA constraint")
    assert_true(any("Memory recall remains a bottleneck" in item for item in constraints), "expected memory recall constraint")
    assert_true(any("Delegated remote failures are present" in item for item in constraints), "expected delegated failure constraint")
    assert_true(any("Remote-provider fallback recovery is active" in item for item in constraints), "expected provider fallback constraint")
    assert_true(any("Exact context-window usage" in item for item in unknowns), "expected context usage unknown")
    assert_true(observed["remote_collaboration"]["memory_sync_policy"].startswith("checkpoint-first"), "expected explicit memory sync policy")

    fake_payload = {
        "observed_signals": observed,
        "inferred_constraints": constraints,
        "evidence_sources": [{"command": ["aq-qa", "0", "--json"], "status": "ok"}],
        "unknowns_or_next_checks": unknowns,
    }
    rendered = module._render_text(fake_payload)
    assert_true("observed_signals:" in rendered, "expected observed_signals section")
    assert_true("unknowns_or_next_checks:" in rendered, "expected unknowns section")

    original_parse_args = module.parse_args
    original_run_json = module._run_json
    try:
        module.parse_args = lambda: type("Args", (), {"task": "inspect local agent state", "since": "1h", "memory_limit": 3, "fmt": "json"})()

        def _fake_run_json(cmd, timeout=120):
            joined = " ".join(cmd)
            if "aq-qa" in joined:
                return {"passed": 41, "failed": 0, "skipped": 0}, {"command": cmd, "status": "ok"}
            if "aq-report" in joined:
                return {
                    "tool_performance": {},
                    "rag_posture": {},
                    "remote_profile_utilization": {"available": True, "total_calls": 2, "success_pct": 50.0, "fallback_applied": 1, "top_profiles": [["remote-gemini", 2]], "top_backend_reason_classes": [["cooldown", 1]]},
                    "delegated_prompt_failures": {"available": True, "total_failures": 1, "salvageable_pct": 100.0, "recovered_failures": 1, "top_failure_classes": [["schema_mismatch", 1]]},
                    "delegated_prompt_failure_windows": {"trend": {"status": "warn", "summary": "recent failures above baseline"}},
                    "provider_fallback_recovery": {"recovered_count": 1, "recovered_pct": 50.0, "diagnosis": "provider_fallback_pressure", "actions": ["tighten retries"]},
                }, {"command": cmd, "status": "ok"}
            if "aq-feedback-loop" in joined:
                return {"recommended_scope": "harness-first", "preflight_commands": ["aq-qa 0 --json"], "context_assist_profiles": ["embedded-assist"]}, {"command": cmd, "status": "ok"}
            if "aq-context-manage" in joined:
                return {"summary_lines": ["Latest checkpoint event: prior context"], "resume_commands": ["aq-context-manage summary --task \"inspect local agent state\" --json"]}, {"command": cmd, "status": "ok"}
            if "aq-memory" in joined:
                return [{"fact_id": "1", "content": "prior context"}], {"command": cmd, "status": "ok"}
            raise AssertionError(f"unexpected command: {cmd}")

        module._run_json = _fake_run_json
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = module.main()
        assert_true(rc == 0, "expected main to succeed")
        payload = json.loads(buf.getvalue())
        assert_true("observed_signals" in payload, "expected observed_signals payload")
        assert_true(payload["observed_signals"]["preflight"]["recommended_scope"] == "harness-first", "expected feedback loop preflight inclusion")
        assert_true(payload["observed_signals"]["preflight"]["context_assist_profiles"] == ["embedded-assist"], "expected embedded assist helper lane")
        assert_true(payload["observed_signals"]["recent_session_summary"]["summary_lines"][0].startswith("Latest checkpoint event:"), "expected compact session summary inclusion")
        assert_true(payload["observed_signals"]["memory_recall_hits"]["items"][0]["fact_id"] == "1", "expected memory recall inclusion")
        assert_true(payload["observed_signals"]["remote_collaboration"]["provider_fallback_recovery"]["recovered_count"] == 1, "expected remote fallback recovery inclusion")
    finally:
        module.parse_args = original_parse_args
        module._run_json = original_run_json

    print("PASS: aq-operational-perspective builds bounded evidence bundles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
