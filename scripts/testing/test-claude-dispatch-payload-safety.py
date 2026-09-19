#!/usr/bin/env python3
"""Hermetic proof that background Claude dispatch treats prompts as argv data."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class ClaudeDispatchPayloadSafetyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        library = self.repo / "scripts/ai/lib"
        library.mkdir(parents=True)
        (self.repo / "config").mkdir()
        (self.repo / ".agents/delegation/outputs").mkdir(parents=True)
        shutil.copy2(ROOT / "scripts/ai/delegate-to-claude", self.repo / "scripts/ai")
        shutil.copy2(ROOT / "scripts/ai/lib/claude-background-worker.sh", library)
        shutil.copy2(ROOT / "config/model-coordinator.json", self.repo / "config")
        (library / "audit-write.sh").write_text(
            "audit_event_start() { :; }\naudit_event_end() { :; }\naudit_save_session() { :; }\n",
            encoding="utf-8",
        )
        (library / "audit-post.sh").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        (library / "harness-grounding.sh").write_text("harness_grounding() { :; }\n", encoding="utf-8")
        self.marker = Path(self.temp.name) / "payload-executed"
        self.wrapper = self.repo / "scripts/ai/delegate-to-claude"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def fake_claude(self, name: str, exit_code: int) -> tuple[Path, Path]:
        argv_log = Path(self.temp.name) / f"{name}-argv.json"
        binary = Path(self.temp.name) / name
        binary.write_text(
            "#!/usr/bin/env python3\n"
            "import json\n"
            "import sys\n"
            "from pathlib import Path\n"
            f"Path({str(argv_log)!r}).write_text(json.dumps(sys.argv[1:]), encoding='utf-8')\n"
            "print('FAKE_CLAUDE_OUTPUT')\n"
            "print('STDIN_EMPTY=' + str(sys.stdin.read() == ''))\n"
            f"raise SystemExit({exit_code})\n",
            encoding="utf-8",
        )
        binary.chmod(0o755)
        return binary, argv_log

    def run_background(self, binary: Path, *args: str) -> str:
        result = subprocess.run(
            [str(self.wrapper), *args],
            cwd=self.repo,
            env={**os.environ, "CLAUDE_BIN": str(binary), "HOME": self.temp.name},
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.splitlines()[-1]

    def completed_row(self, task_id: str, status: str) -> dict:
        registry = self.repo / ".agents/delegation/registry.jsonl"
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if registry.exists():
                rows = [json.loads(line) for line in registry.read_text().splitlines() if line]
                for row in rows:
                    if row["id"] == task_id and row["status"] == status:
                        return row
            time.sleep(0.05)
        self.fail(f"task {task_id} did not reach {status}")

    def test_background_payload_is_inert_and_model_role_are_preserved(self) -> None:
        binary, argv_log = self.fake_claude("success-claude", 0)
        prompt = (
            f'quotes "double" and \'single\'\n$(touch {self.marker})\n'
            f'`touch {self.marker}`\n$HOME ${{UNSET:-value}}'
        )
        task_id = self.run_background(binary, "--role", "review", "--model-tier", "flagship", "--prompt", prompt)
        row = self.completed_row(task_id, "done")
        argv = json.loads(argv_log.read_text(encoding="utf-8"))
        self.assertEqual(argv[argv.index("-p") + 1], f"[ROLE: review]\n\n{prompt}")
        self.assertEqual(argv[argv.index("--model") + 1], "claude-fable-5")
        self.assertFalse(self.marker.exists())
        self.assertEqual(row["role"], "review")
        self.assertEqual(row["resolved_model"], "claude-fable-5")
        output = (self.repo / row["output_file"]).read_text(encoding="utf-8")
        self.assertIn("FAKE_CLAUDE_OUTPUT", output)
        self.assertIn("STDIN_EMPTY=True", output)

    def test_background_failure_captures_output_and_marks_registry_failed(self) -> None:
        binary, _ = self.fake_claude("failing-claude", 7)
        task_id = self.run_background(binary, "--role", "research", "--prompt", "return nonzero")
        row = self.completed_row(task_id, "failed")
        output = (self.repo / row["output_file"]).read_text(encoding="utf-8")
        self.assertIn("FAKE_CLAUDE_OUTPUT", output)
        self.assertIn("STDIN_EMPTY=True", output)
        self.assertEqual(row["role"], "research")


if __name__ == "__main__":
    unittest.main(verbosity=2)
