#!/usr/bin/env python3
"""Hermetic checks for monitored Claude model-tier resolution."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class ClaudeModelRoutingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        (self.repo / "scripts/ai/lib").mkdir(parents=True)
        (self.repo / "config").mkdir()
        (self.repo / ".agents/delegation/outputs").mkdir(parents=True)
        self.wrapper = self.repo / "scripts/ai/delegate-to-claude"
        shutil.copy2(ROOT / "scripts/ai/delegate-to-claude", self.wrapper)
        shutil.copy2(ROOT / "config/model-coordinator.json", self.repo / "config")
        (self.repo / "scripts/ai/lib/audit-write.sh").write_text(
            "audit_event_start() { :; }\n"
            "audit_event_end() { :; }\n"
            "audit_save_session() { :; }\n",
            encoding="utf-8",
        )
        (self.repo / "scripts/ai/lib/harness-grounding.sh").write_text(
            "harness_grounding() { :; }\n", encoding="utf-8"
        )
        self.argv_log = Path(self.temp.name) / "claude-argv.json"
        self.fake_claude = Path(self.temp.name) / "claude"
        self.fake_claude.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, sys\n"
            "from pathlib import Path\n"
            "Path(os.environ['FAKE_CLAUDE_ARGV']).write_text(json.dumps(sys.argv[1:]))\n"
            "print('FAKE_CLAUDE_OK')\n",
            encoding="utf-8",
        )
        self.fake_claude.chmod(0o755)
        self.env = {
            **os.environ,
            "CLAUDE_BIN": str(self.fake_claude),
            "FAKE_CLAUDE_ARGV": str(self.argv_log),
            "HOME": self.temp.name,
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_wrapper(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(self.wrapper), *args],
            cwd=self.repo,
            env=self.env,
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )

    def registry(self) -> list[dict]:
        path = self.repo / ".agents/delegation/registry.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text().splitlines() if line]

    def test_flagship_resolves_and_is_recorded(self) -> None:
        result = self.run_wrapper(
            "--wait", "--model-tier", "flagship", "--role", "plan",
            "--prompt", "bounded architecture review",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        argv = json.loads(self.argv_log.read_text())
        self.assertEqual(argv[argv.index("--model") + 1], "claude-fable-5")
        row = self.registry()[-1]
        self.assertEqual(row["requested_model_tier"], "flagship")
        self.assertEqual(row["resolved_model"], "claude-fable-5")
        self.assertEqual(row["status"], "done")

    def test_no_tier_preserves_cli_default_behavior(self) -> None:
        result = self.run_wrapper("--wait", "--role", "review", "--prompt", "compat")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("--model", json.loads(self.argv_log.read_text()))
        row = self.registry()[-1]
        self.assertIsNone(row["requested_model_tier"])
        self.assertIsNone(row["resolved_model"])

    def test_unknown_tier_fails_before_launch_or_registry_write(self) -> None:
        before = len(self.registry())
        self.argv_log.unlink(missing_ok=True)
        result = self.run_wrapper(
            "--wait", "--model-tier", "invented", "--prompt", "must not launch"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.argv_log.exists())
        self.assertEqual(len(self.registry()), before)

    def test_invalid_coordinator_model_fails_closed(self) -> None:
        config_path = self.repo / "config/model-coordinator.json"
        config = json.loads(config_path.read_text())
        config["tiers"]["anthropic"]["flagship"] = "not-a-claude-model"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        self.argv_log.unlink(missing_ok=True)
        result = self.run_wrapper(
            "--wait", "--model-tier", "flagship", "--prompt", "must not launch"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.argv_log.exists())
        self.assertEqual(self.registry(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
