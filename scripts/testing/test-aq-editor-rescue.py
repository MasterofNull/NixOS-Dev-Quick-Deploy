#!/usr/bin/env python3
"""Regression checks for aq-editor-rescue bounded rescue workflow."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ai" / "aq-editor-rescue"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def write_executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aq-editor-rescue-") as tmpdir:
        root = Path(tmpdir)
        checkpoint_cmd = root / "checkpoint.py"
        report_cmd = root / "aq-report.py"
        qa_cmd = root / "aq-qa"
        repair_cmd = root / "repair.sh"
        regenerate_cmd = root / "hm-switch.sh"
        history_path = root / "editor-rescue-history.jsonl"
        marker = root / "repair-ran.txt"
        regenerate_marker = root / "home-manager-ran.txt"

        write_executable(
            checkpoint_cmd,
            """#!/usr/bin/env python3
import json
print(json.dumps({"ok": True, "fact_count": 5}))
""",
        )
        write_executable(
            report_cmd,
            """#!/usr/bin/env python3
import json
print(json.dumps({
  "continue_editor": {
    "state_budget": {
      "available": True,
      "healthy": False,
      "total_checks": 5,
      "passed_n": 4,
      "failed_n": 1,
      "checks": [{"id": "continue_hot_corpus", "status": "FAIL", "details": "oversized active sessions"}]
    }
  }
}))
""",
        )
        write_executable(
            qa_cmd,
            f"""#!/usr/bin/env python3
import json
from pathlib import Path
marker = Path({str(regenerate_marker)!r})
if marker.exists():
    print(json.dumps({{"passed": 40, "failed": 0, "skipped": 1, "tests": []}}))
else:
    print(json.dumps({{
        "passed": 39,
        "failed": 1,
        "skipped": 1,
        "tests": [{{
            "id": "0.5.2",
            "status": "FAIL",
            "description": "Continue config targets switchboard ingress with local harness chat lane and continue-local tab lane"
        }}]
    }}))
""",
        )
        write_executable(
            repair_cmd,
            f"""#!/usr/bin/env bash
set -euo pipefail
printf 'ran' > "{marker}"
echo '[repair] ok'
""",
        )
        write_executable(
            regenerate_cmd,
            f"""#!/usr/bin/env bash
set -euo pipefail
printf 'ran' > "{regenerate_marker}"
echo '[home-manager] ok'
""",
        )
        repair_fallback = root / "repair-fallback"
        repair_fallback.write_text(f"printf 'fallback' > \"{root / 'repair-fallback-ran.txt'}\"\n", encoding="utf-8")
        repair_fallback.chmod(repair_fallback.stat().st_mode | stat.S_IXUSR)

        env = dict(os.environ)
        env["AQ_EDITOR_RESCUE_CONTEXT_MANAGE"] = str(checkpoint_cmd)
        env["AQ_EDITOR_RESCUE_AQ_REPORT"] = str(report_cmd)
        env["AQ_EDITOR_RESCUE_AQ_QA"] = str(qa_cmd)
        env["AQ_EDITOR_RESCUE_REPAIR_CMD"] = str(repair_cmd)
        env["AQ_EDITOR_RESCUE_REGENERATE_CONTINUE_CONFIG_CMD"] = str(regenerate_cmd)
        env["AQ_EDITOR_RESCUE_HISTORY_PATH"] = str(history_path)

        plan = subprocess.run(
            ["python3", str(SCRIPT), "--task", "Continue editor is freezing", "--format", "json"],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        assert_true(plan.returncode == 0, f"plan mode failed: {(plan.stderr or plan.stdout).strip()}")
        plan_payload = json.loads(plan.stdout)
        assert_true(not plan_payload["summary"]["state_budget"]["healthy"], "expected degraded editor-state budget in plan output")
        assert_true(plan_payload["repair"].get("skipped"), "expected plan mode to skip repair execution")
        assert_true(any("aq-memory search" in cmd for cmd in plan_payload.get("resume_commands") or []), "expected aq-memory resume guidance")

        execute = subprocess.run(
            ["python3", str(SCRIPT), "--task", "Continue editor is freezing", "--format", "json", "--execute"],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        assert_true(execute.returncode == 0, f"execute mode failed: {(execute.stderr or execute.stdout).strip()}")
        execute_payload = json.loads(execute.stdout)
        assert_true(execute_payload["repair"].get("ok"), "expected repair command to run successfully")
        assert_true(marker.exists(), "expected execute mode to run the repair command")
        assert_true(execute_payload["regenerate_continue_config"].get("skipped"), "expected regeneration to stay skipped unless requested")

        env_fallback = dict(env)
        env_fallback["AQ_EDITOR_RESCUE_REPAIR_CMD"] = str(repair_fallback)
        fallback = subprocess.run(
            ["python3", str(SCRIPT), "--task", "Continue editor is freezing", "--format", "json", "--execute"],
            capture_output=True,
            text=True,
            check=False,
            env=env_fallback,
        )
        assert_true(fallback.returncode == 0, f"fallback repair mode failed: {(fallback.stderr or fallback.stdout).strip()}")
        fallback_payload = json.loads(fallback.stdout)
        assert_true(fallback_payload["repair"].get("ok"), "expected bash fallback repair execution to succeed")
        assert_true((root / "repair-fallback-ran.txt").exists(), "expected bash fallback repair command to run")

        regen = subprocess.run(
            [
                "python3",
                str(SCRIPT),
                "--task",
                "Continue editor is freezing",
                "--format",
                "json",
                "--execute",
                "--regenerate-continue-config",
            ],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        assert_true(regen.returncode == 0, f"regen mode failed: {(regen.stderr or regen.stdout).strip()}")
        regen_payload = json.loads(regen.stdout)
        assert_true(regen_payload["repair"].get("ok"), "expected repair to succeed before regeneration")
        assert_true(regen_payload["regenerate_continue_config"].get("ok"), "expected Continue config regeneration to succeed")
        assert_true(regenerate_marker.exists(), "expected regeneration command to run")
        assert_true(
            regen_payload["summary"]["qa_phase_0"] == {"passed": 40, "failed": 0, "skipped": 1},
            "expected aq-qa to be re-run after Continue regeneration",
        )
        history_lines = [line for line in history_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert_true(len(history_lines) >= 4, "expected aq-editor-rescue to persist telemetry for each run")
        latest_history = json.loads(history_lines[-1])
        assert_true(latest_history.get("regenerate_requested") is True, "expected rescue telemetry to record regeneration intent")
        assert_true(latest_history.get("regenerate_ok") is True, "expected rescue telemetry to record regeneration success")
        assert_true(latest_history.get("qa_failed") == 0, "expected rescue telemetry to record post-regeneration QA success")

    print("PASS: aq-editor-rescue checkpoints, diagnoses, and repairs in bounded phases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
