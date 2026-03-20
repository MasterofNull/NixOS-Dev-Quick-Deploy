#!/usr/bin/env python3
"""Regression for secrets rotation planning report generation."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="secrets-rotation-plan-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        status_json = tmp_path / "status.json"
        report_json = tmp_path / "latest-secrets-rotation-plan.json"

        status_json.write_text(
            json.dumps(
                {
                    "host": "nixos",
                    "bundle": "/tmp/secrets.sops.yaml",
                    "age_key_file": "/tmp/keys.txt",
                    "local_override": "/tmp/deploy-options.local.nix",
                    "core_ready": True,
                    "all_managed_ready": False,
                    "missing_by_scope": {
                        "core": [],
                        "optional": ["nixos_docs_api_key"],
                        "remote": ["remote_llm_api_key"],
                    },
                    "next_steps": ["Run manage-secrets validate"],
                    "secrets": [
                        {"name": "hybrid_coordinator_api_key", "scope": "core", "services": "hybrid-coordinator, harness", "present": True},
                        {"name": "postgres_password", "scope": "core", "services": "postgres, aidb, hybrid-coordinator", "present": True},
                        {"name": "remote_llm_api_key", "scope": "optional", "services": "switchboard remote routing", "present": False},
                    ],
                }
            ),
            encoding="utf-8",
        )

        subprocess.run(
            [
                "bash",
                str(ROOT / "scripts" / "security" / "secrets-rotation-plan.sh"),
                "--status-json",
                str(status_json),
                "--output",
                str(report_json),
            ],
            check=True,
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

        report = json.loads(report_json.read_text(encoding="utf-8"))
        assert_true(report.get("rotation_ready") is True, "rotation plan should mark ready when core wiring exists")
        assert_true(report.get("summary", {}).get("total_managed_secrets") == 3, "plan should summarize secret count")
        secrets = {item["name"]: item for item in report.get("secrets", [])}
        assert_true("hybrid_coordinator_api_key" in secrets, "plan should include hybrid secret")
        assert_true(
            "ai-hybrid-coordinator.service" in secrets["hybrid_coordinator_api_key"].get("restart_groups", []),
            "hybrid secret should include restart impact",
        )
        assert_true(
            secrets["remote_llm_api_key"].get("disruption") == "low",
            "remote routing key should remain low disruption",
        )

    print("PASS: secrets rotation plan regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
