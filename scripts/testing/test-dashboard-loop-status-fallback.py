#!/usr/bin/env python3
"""Regression: /api/loop/status must read training-loop fallback results."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dashboard" / "backend"))

from api.routes import aistack  # noqa: E402


async def main() -> int:
    original_repo_root = aistack._repo_root
    original_telemetry = os.environ.get("TELEMETRY_DIR")

    with tempfile.TemporaryDirectory(prefix="dashboard-loop-status-") as tmp:
        root = Path(tmp)
        telemetry = root / "telemetry"
        delegation = root / ".agents" / "delegation"
        telemetry.mkdir(parents=True)
        delegation.mkdir(parents=True)

        (telemetry / "training-loop-results.jsonl").write_text("", encoding="utf-8")
        (telemetry / "training-loop-progress.json").write_text(
            json.dumps({"phase": "complete"}),
            encoding="utf-8",
        )
        fallback_run = {
            "run_id": "loop-test",
            "pass_count": 12,
            "fail_count": 0,
            "pass_rate": 1.0,
            "ingest": {"samples_added": 3, "dataset_total": 831},
            "improvements_proposed": 0,
        }
        (delegation / "training-loop-results.jsonl").write_text(
            json.dumps(fallback_run) + "\n",
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

    assert data["status"] == "healthy", data
    assert data["last_run"]["run_id"] == "loop-test", data
    assert data["last_run"]["samples_added"] == 3, data
    assert data["last_run"]["dataset_total"] == 831, data
    assert data["last_run"]["pass_rate"] == 1.0, data

    with tempfile.TemporaryDirectory(prefix="dashboard-loop-status-interrupted-") as tmp:
        root = Path(tmp)
        telemetry = root / "telemetry"
        delegation = root / ".agents" / "delegation"
        telemetry.mkdir(parents=True)
        delegation.mkdir(parents=True)

        (telemetry / "training-loop-results.jsonl").write_text("", encoding="utf-8")
        (telemetry / "training-loop-progress.json").write_text(
            json.dumps({"run_id": "loop-current", "phase": "stopping"}),
            encoding="utf-8",
        )
        (delegation / "training-loop-results.jsonl").write_text(
            json.dumps(fallback_run) + "\n",
            encoding="utf-8",
        )
        (delegation / "training-loop-checkpoint.json").write_text(
            json.dumps(
                {
                    "loop-current": {
                        "case-a": {"pass": False},
                        "case-b": {"pass": True},
                    }
                }
            ),
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

    assert data["status"] == "interrupted", data
    assert data["checkpoint"]["run_id"] == "loop-current", data
    assert data["checkpoint"]["case_count"] == 2, data
    assert data["checkpoint"]["failed_cases"] == 1, data

    with tempfile.TemporaryDirectory(prefix="dashboard-loop-status-failed-") as tmp:
        root = Path(tmp)
        telemetry = root / "telemetry"
        delegation = root / ".agents" / "delegation"
        telemetry.mkdir(parents=True)
        delegation.mkdir(parents=True)

        failed_run = dict(fallback_run)
        failed_run.update({"run_id": "loop-failed", "pass_count": 0, "fail_count": 12, "pass_rate": 0.0})
        (delegation / "training-loop-results.jsonl").write_text(
            json.dumps(failed_run) + "\n",
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

    assert data["status"] == "eval_failed", data
    assert data["last_run"]["fail_count"] == 12, data
    print("PASS: dashboard loop status reads non-empty delegation fallback results")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
