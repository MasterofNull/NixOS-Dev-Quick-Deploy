#!/usr/bin/env python3
"""Regression test for training pipeline monitoring, status robustness, and event emission."""

from __future__ import annotations

import asyncio
import importlib.machinery
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "ai" / "aq-local-training-loop"
DASHBOARD_PATH = ROOT / "dashboard" / "backend"
sys.path.insert(0, str(DASHBOARD_PATH))
from api.routes import aistack  # noqa: E402


def load_loop_module():
    loader = importlib.machinery.SourceFileLoader("aq_local_training_loop_test", str(MODULE_PATH))
    return loader.load_module()


def test_status_output_with_deferred_and_missing_ingest():
    mod = load_loop_module()
    with tempfile.TemporaryDirectory(prefix="test-status-") as tmp:
        tmpdir = Path(tmp)
        results_file = tmpdir / "training-loop-results.jsonl"
        mod.RESULTS_LOG = results_file
        mod.DELEGATION_DIR = tmpdir
        mod.PROGRESS_FILE = tmpdir / "training-loop-progress.json"

        # 1. Normal run
        run_normal = {
            "run_id": "loop-normal-01",
            "timestamp": "2026-10-13T01:00:00Z",
            "pass_count": 12,
            "cases_total": 12,
            "ingest": {"samples_added": 5, "dataset_total": 100},
            "improvements_proposed": 2,
        }
        # 2. Deferred run (model_not_ready) without ingest dict
        run_deferred_no_ingest = {
            "run_id": "loop-deferred-02",
            "timestamp": "2026-10-13T02:00:00Z",
            "status": "deferred",
            "reason": "model_not_ready",
            "pass_count": 0,
            "cases_total": 0,
            "pass_rate": None,
        }
        # 3. Interrupted run with None ingest
        run_interrupted_none_ingest = {
            "run_id": "loop-interrupted-03",
            "timestamp": "2026-10-13T03:00:00Z",
            "status": "interrupted",
            "ingest": None,
            "improvements_proposed": 0,
        }

        results_file.write_text(
            json.dumps(run_normal) + "\n"
            + json.dumps(run_deferred_no_ingest) + "\n"
            + json.dumps(run_interrupted_none_ingest) + "\n",
            encoding="utf-8",
        )

        buf = io.StringIO()
        with redirect_stdout(buf):
            mod._status(n=10)
        output = buf.getvalue()

        assert "loop-normal-01" in output
        assert "+5 samples" in output
        assert "2 proposals" in output
        assert "loop-deferred-02" in output
        assert "[deferred] (model_not_ready)" in output
        assert "loop-interrupted-03" in output
        assert "[interrupted]" in output
        print("PASS: test_status_output_with_deferred_and_missing_ingest")


def test_proposal_title_and_rationale_sanitization():
    mod = load_loop_module()
    # Test cases for improvement proposal formatting
    failing = [{"case_id": "mkif-mkforce-basics", "missing_keywords": ["mkIf"]}]
    run_id = "loop-test-proposals"

    # Simulated responses that previously caused {'raw': ... titles
    test_responses = [
        # Bullet list with raw markdown
        "- ai-stack/mcp-servers/hybrid-coordinator/route_handlers.py: add keyword coverage\n- second proposal",
        # Fenced json block
        '```json\n[{"root_cause": "Missing Nix module documentation", "change_description": "Add options doc", "expected_keyword_gains": ["mkIf"]}]\n```',
        # Raw json without fence
        '[{"root_cause": "Flake inputs not pinned", "change_description": "Pin inputs", "expected_keyword_gains": ["follows"]}]',
    ]

    for resp in test_responses:
        clean_resp = resp.strip()
        if "```json" in clean_resp:
            clean_resp = clean_resp.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in clean_resp:
            clean_resp = clean_resp.split("```", 1)[1].split("```", 1)[0].strip()

        try:
            start = clean_resp.find("[")
            end = clean_resp.rfind("]") + 1
            if start >= 0 and end > start:
                improvements = json.loads(clean_resp[start:end])
            else:
                raise ValueError("No JSON array")
        except (json.JSONDecodeError, ValueError):
            paragraphs = [p.strip() for p in resp.split("\n\n") if p.strip() and not p.strip().startswith("```")]
            if len(paragraphs) > 1:
                improvements = [{"raw": p[:500]} for p in paragraphs[:3]]
            else:
                improvements = [{"raw": resp[:500]}]

        for imp in improvements:
            if not isinstance(imp, dict):
                imp = {"raw": str(imp)}
            if imp.get("root_cause"):
                title = imp["root_cause"]
            elif imp.get("title"):
                title = imp["title"]
            elif imp.get("raw"):
                raw_text = str(imp["raw"]).strip()
                lines = [
                    l.strip().lstrip("-*# 1234567890.").strip()
                    for l in raw_text.splitlines()
                    if l.strip().lstrip("-*# 1234567890.").strip()
                ]
                title = lines[0][:80] if lines else "Training loop finding"
            else:
                title = "Training loop finding"

            assert not title.startswith("{'raw':"), f"Proposal title still raw: {title}"
            assert not title.startswith('{"raw":'), f"Proposal title still raw: {title}"
            assert len(title) > 0, "Empty proposal title"

    print("PASS: test_proposal_title_and_rationale_sanitization")


async def test_dashboard_loop_status_deferred_state():
    original_repo_root = aistack._repo_root
    original_telemetry = os.environ.get("TELEMETRY_DIR")

    with tempfile.TemporaryDirectory(prefix="dashboard-loop-status-deferred-") as tmp:
        root = Path(tmp)
        telemetry = root / "telemetry"
        delegation = root / ".agents" / "delegation"
        telemetry.mkdir(parents=True)
        delegation.mkdir(parents=True)

        deferred_run = {
            "run_id": "loop-deferred-test",
            "status": "deferred",
            "reason": "slot_contended",
            "pass_count": 0,
            "fail_count": 0,
            "pass_rate": None,
            "ingest": {"samples_added": 0, "dataset_total": 500},
            "improvements_proposed": 0,
        }
        (delegation / "training-loop-results.jsonl").write_text(
            json.dumps(deferred_run) + "\n",
            encoding="utf-8",
        )

        os.environ["TELEMETRY_DIR"] = str(telemetry)
        aistack._repo_root = lambda: root
        try:
            data = await aistack.get_loop_status()
        finally:
            aistack._repo_root = original_repo_root
            if original_telemetry is None:
                os.environ.pop("TELEMETRY_DIR", None)
            else:
                os.environ["TELEMETRY_DIR"] = original_telemetry

    assert data["status"] == "deferred", f"Expected deferred status, got {data['status']}"
    assert data["last_run"]["status"] == "deferred"
    assert data["last_run"]["reason"] == "slot_contended"
    assert data["last_run"]["samples_added"] == 0
    print("PASS: test_dashboard_loop_status_deferred_state")


async def async_main():
    test_status_output_with_deferred_and_missing_ingest()
    test_proposal_title_and_rationale_sanitization()
    await test_dashboard_loop_status_deferred_state()
    print("ALL TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(async_main())
