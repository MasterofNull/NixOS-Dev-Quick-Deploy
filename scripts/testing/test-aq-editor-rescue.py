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
        marker = root / "repair-ran.txt"

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
            """#!/usr/bin/env python3
import json
print(json.dumps({"passed": 39, "failed": 1, "skipped": 1}))
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

        env = dict(os.environ)
        env["AQ_EDITOR_RESCUE_CONTEXT_MANAGE"] = str(checkpoint_cmd)
        env["AQ_EDITOR_RESCUE_AQ_REPORT"] = str(report_cmd)
        env["AQ_EDITOR_RESCUE_AQ_QA"] = str(qa_cmd)
        env["AQ_EDITOR_RESCUE_REPAIR_CMD"] = str(repair_cmd)

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

    print("PASS: aq-editor-rescue checkpoints, diagnoses, and repairs in bounded phases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
