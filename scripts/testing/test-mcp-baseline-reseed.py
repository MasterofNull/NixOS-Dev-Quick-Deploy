#!/usr/bin/env python3
"""Audited baseline reseeding with temporary sources; no sudo or live services."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
UPDATER = ROOT / "scripts/security/update-mcp-integrity-baseline.sh"
DEPLOY = ROOT / "scripts/maintenance/aq-deploy-current"


class BaselineReseedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "MCP sources"
        self.source.mkdir()
        self.baseline = self.root / "state" / "baseline.sha256"
        self.audit = self.root / "audit" / "events.jsonl"
        self.env = {
            **os.environ,
            "MCP_SERVER_DIR": str(self.source),
            "MCP_INTEGRITY_BASELINE": str(self.baseline),
            "MCP_INTEGRITY_AUDIT_LOG": str(self.audit),
            "MCP_BASELINE_GIT_REV": "a" * 40,
            "SUDO_USER": "fixture-owner",
        }

    def seed(self, success=True, env=None):
        result = subprocess.run(
            ["bash", str(UPDATER)], env=env or self.env,
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def records(self):
        return [json.loads(line) for line in self.audit.read_text().splitlines()]

    def test_first_seed_and_exact_diff(self):
        changed = self.source / "changed.py"
        removed = self.source / "removed.py"
        unchanged = self.source / "unchanged.py"
        for path in (changed, removed, unchanged):
            path.write_text("pass\n")
        self.seed()
        first = self.records()
        self.assertEqual(len(first), 1)
        self.assertEqual(first[0]["added"], sorted(map(str, (changed, removed, unchanged))))
        self.assertEqual(first[0]["counts"], {"added": 3, "changed": 0, "removed": 0})
        self.assertEqual(first[0]["actor"], "fixture-owner")
        self.assertEqual(first[0]["git_rev"], "a" * 40)
        self.assertTrue(first[0]["ts"].endswith("+00:00"))
        changed.write_text("print('changed')\n")
        removed.rename(self.root / "archived-removed.py")
        added = self.source / "added.py"
        added.write_text("pass\n")
        result = self.seed()
        records = self.records()
        self.assertEqual(len(records), 2)
        for kind, path in (("changed", changed), ("added", added), ("removed", removed)):
            self.assertEqual(records[-1][kind], [str(path)])
        self.assertEqual(records[-1]["counts"], {"changed": 1, "added": 1, "removed": 1})
        self.assertIn("1 changed, 1 added, 1 removed", result.stdout)
        verify = subprocess.run(["sha256sum", "--check", str(self.baseline)], capture_output=True, text=True)
        self.assertEqual(verify.returncode, 0, verify.stdout + verify.stderr)
        self.assertEqual(self.baseline.stat().st_mode & 0o777, 0o644)

    def test_empty_refusal_preserves_baseline_and_audit(self):
        source = self.source / "only.py"
        source.write_text("pass\n")
        self.seed()
        before = self.baseline.read_bytes(), self.audit.read_bytes()
        source.rename(self.root / "archived-only.py")
        result = self.seed(success=False)
        self.assertIn("NOT updated", result.stderr)
        self.assertEqual(before, (self.baseline.read_bytes(), self.audit.read_bytes()))

    def test_audit_failure_preserves_baseline(self):
        source = self.source / "only.py"
        source.write_text("pass\n")
        self.seed()
        before = self.baseline.read_bytes()
        source.write_text("print('changed')\n")
        self.seed(success=False, env={**self.env, "MCP_INTEGRITY_AUDIT_LOG": str(self.root)})
        self.assertEqual(before, self.baseline.read_bytes())

    def test_default_audit_location_and_escaped_paths(self):
        path = self.source / "a\\b\nc.py"
        path.write_text("pass\n")
        env = dict(self.env)
        env.pop("MCP_INTEGRITY_AUDIT_LOG")
        self.seed(env=env)
        path.write_text("print('changed')\n")
        self.seed(env=env)
        records = [json.loads(line) for line in (self.baseline.parent / "mcp-baseline-audit.jsonl").read_text().splitlines()]
        self.assertEqual(records[-1]["changed"], [str(path)])

    def test_deploy_guard_order_and_dry_run(self):
        text = DEPLOY.read_text()
        block = text.split("# 8b.", 1)[1].split("# 9.", 1)[0]
        self.assertTrue(block.lstrip().splitlines()[1].startswith("if ((rc == 0)); then"))
        self.assertTrue(block.rstrip().endswith("fi"))
        self.assertEqual(text.count("bash scripts/security/update-mcp-integrity-baseline.sh"), 1)
        self.assertLess(text.index("# 8b."), text.index("scripts/ai/aq-qa 0 --machine"))
        self.assertLess(text.index("bash scripts/security/update-mcp-integrity-baseline.sh"), text.index("sudo systemctl start ai-mcp-integrity-check.service"))
        dry = text.split("if ((DRY)); then", 1)[1].split("# 7.", 1)[0]
        self.assertIn("8b would reseed", dry)
        self.assertIn("exit 0", dry)

    def test_deploy_block_with_stubbed_commands(self):
        block = DEPLOY.read_text().split("# 8b.", 1)[1].split("# 9.", 1)[0]
        block = "\n".join(block.splitlines()[1:])
        # Functions intercept both commands; nothing reaches sudo or systemd.
        fixture = r'''
set -euo pipefail
TAG=fixture
want=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
rc="$FIXTURE_RC"
systemctl() { printf '%s' "$FIXTURE_ENV"; }
sudo() { printf 'STUB_CALL'; printf ' <%s>' "$@"; printf '\n'; return "$FIXTURE_SUDO_RC"; }
'''
        for rc, environment, sudo_rc, calls, final in (
            (1, "MCP_SERVER_DIR=/src MCP_INTEGRITY_BASELINE=/state", 0, 0, 1),
            (0, "", 0, 0, 0),
            (0, "MCP_SERVER_DIR=/src", 0, 0, 0),
            (0, '\"MCP_SERVER_DIR=/src path\" \"MCP_INTEGRITY_BASELINE=/state path\"', 0, 2, 0),
            (0, "MCP_SERVER_DIR=/src MCP_INTEGRITY_BASELINE=/state", 1, 1, 1),
        ):
            result = subprocess.run(
                ["bash", "-c", fixture + block + '\nprintf "FINAL_RC=%s\n" "$rc"'],
                env={**os.environ, "FIXTURE_RC": str(rc), "FIXTURE_ENV": environment, "FIXTURE_SUDO_RC": str(sudo_rc)},
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.count("STUB_CALL"), calls, result.stdout)
            self.assertIn(f"FINAL_RC={final}", result.stdout)
            if calls == 2:
                self.assertIn("<MCP_SERVER_DIR=/src path>", result.stdout)
                self.assertIn("<MCP_INTEGRITY_BASELINE=/state path>", result.stdout)
                self.assertIn("MCP_BASELINE_GIT_REV=" + "a" * 40, result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
