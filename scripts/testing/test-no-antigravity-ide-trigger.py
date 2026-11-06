#!/usr/bin/env python3
"""The retired Antigravity IDE lane must not be triggerable, and the Gemini seat is headless.

Owner directive 2026-11-05: RSI/collab rounds were waking the Antigravity IDE; the seat now runs
through the headless Gemini CLI (scripts/ai/delegate-to-gemini). Offline: stubs only, no network.
"""
import importlib.machinery
import importlib.util
import json
import os
import re
import stat
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN = re.compile(
    r"antigravity chat|aq-antigravity-inbox|delegate-to-antigravity|aq-antigravity-agent|"
    r"antigravityAutoWake|antigravity-auto-wake|\.agent/collaboration/antigravity-inbox")
SCAN_DIRS = ("scripts", "nix", "config", "ai-stack", "canon", ".githooks")
SKIP_PARTS = {"testing", "__pycache__", "node_modules", ".git"}
SELF = Path(__file__).resolve()


def live_files():
    for top in SCAN_DIRS:
        base = ROOT / top
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if not p.is_file() or SKIP_PARTS & set(p.relative_to(ROOT).parts):
                continue
            if p.stat().st_size > 2_000_000:
                continue
            yield p


class NoIdeTriggerTests(unittest.TestCase):
    def test_no_live_reference_to_ide_wake_or_inbox(self):
        hits = []
        for p in live_files():
            try:
                text = p.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for n, line in enumerate(text.splitlines(), 1):
                if FORBIDDEN.search(line):
                    hits.append(f"{p.relative_to(ROOT)}:{n}: {line.strip()[:120]}")
        self.assertEqual(hits, [], "live code still references the retired Antigravity IDE lane")

    def test_retired_artifacts_are_archived_not_live(self):
        for rel in ("scripts/ai/delegate-to-antigravity", "scripts/ai/aq-antigravity-inbox",
                    "scripts/ai/aq-antigravity-agent", "nix/modules/services/antigravity-auto-wake.nix"):
            self.assertFalse((ROOT / rel).exists(), rel)
            self.assertTrue((ROOT / ".agents/archive/20261105-antigravity-lane" / rel).exists(), rel)

    def test_auto_wake_not_enabled_or_imported(self):
        self.assertNotIn("antigravityAutoWake", (ROOT / "nix/modules/profiles/ai-dev.nix").read_text())
        self.assertNotIn("antigravity-auto-wake", (ROOT / "nix/modules/services/default.nix").read_text())


class GeminiSeatTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        loader = importlib.machinery.SourceFileLoader("collab_round_t", str(ROOT / "scripts/ai/aq-collab-round"))
        spec = importlib.util.spec_from_loader("collab_round_t", loader)
        self.m = importlib.util.module_from_spec(spec)
        loader.exec_module(self.m)
        # Stub delegate-to-gemini records argv; an `antigravity` stub on PATH records any IDE launch.
        stubs = self.dir / "stubs"
        stubs.mkdir()
        self.argv_log = self.dir / "argv.txt"
        gem = stubs / "delegate-to-gemini"
        gem.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "' + str(self.argv_log) + '"\n'
                       'echo "[delegate-to-gemini] Delegating task: gemini-20261105-120000-abc123"\n')
        self.ide_marker = self.dir / "ide-launched"
        ide = stubs / "antigravity"
        ide.write_text('#!/usr/bin/env bash\ntouch "' + str(self.ide_marker) + '"\n')
        for f in (gem, ide):
            f.chmod(f.stat().st_mode | stat.S_IXUSR)
        self.m.SCRIPTS = stubs
        old_path = os.environ["PATH"]
        os.environ["PATH"] = f"{stubs}:{old_path}"
        self.addCleanup(os.environ.__setitem__, "PATH", old_path)
        self.m.OUTPUTS = self.dir / "outputs"
        self.m.OUTPUTS.mkdir()
        self.m.DELEGATION_REGISTRY = self.dir / "registry.jsonl"

    def test_seat_names(self):
        self.assertIn("gemini", self.m.ALL_AGENTS)
        self.assertNotIn("antigravity", self.m.ALL_AGENTS)
        self.assertNotIn("antigravity", self.m.PROCESS_AGENTS)

    def test_gemini_dispatch_uses_delegate_to_gemini_plan_mode(self):
        pf = self.dir / ".round-prompt.txt"
        pf.write_text("task")
        tid = self.m._dispatch_process("gemini", pf, 60)
        self.assertEqual(tid, "gemini-20261105-120000-abc123")
        argv = self.argv_log.read_text().split("\n")
        for flag, val in (("--role", "reviewer"), ("--mode", "plan")):
            self.assertEqual(argv[argv.index(flag) + 1], val)
        self.assertFalse(self.ide_marker.exists(), "Antigravity IDE binary was launched")

    def test_collect_records_gemini_reply_as_gemini_md(self):
        rd = self.dir / "round"
        rd.mkdir()
        tid = "gemini-20261105-120000-abc123"
        (rd / ".round-dispatch.json").write_text(json.dumps({"dispatch": {"gemini": tid}}))
        self.m.DELEGATION_REGISTRY.write_text(json.dumps({"id": tid, "status": "done"}) + "\n")
        (self.m.OUTPUTS / f"{tid}.log").write_text(
            "Warning: noise\nVerdict: ship it; one concern about X.\n")
        self.assertEqual(self.m._extract_gemini_contribution(rd), "recorded")
        text = (rd / "gemini.md").read_text()
        self.assertIn("ship it", text)
        self.assertNotIn("Warning: noise", text)
        self.assertEqual(self.m._extract_gemini_contribution(rd), "present")

    def test_collect_waits_for_terminal_status(self):
        rd = self.dir / "round2"
        rd.mkdir()
        tid = "gemini-20261105-120000-def456"
        (rd / ".round-dispatch.json").write_text(json.dumps({"dispatch": {"gemini": tid}}))
        self.m.DELEGATION_REGISTRY.write_text(json.dumps({"id": tid, "status": "running"}) + "\n")
        self.assertTrue(self.m._extract_gemini_contribution(rd).startswith("not-terminal"))
        self.assertFalse((rd / "gemini.md").exists())

    def test_legacy_antigravity_round_still_loads(self):
        rd = self.dir / "legacy"
        rd.mkdir()
        (rd / "antigravity.md").write_text("old IDE contribution")
        self.assertEqual(self.m._round_agents(rd), self.m.ALL_AGENTS + ["antigravity"])
        self.assertEqual(self.m._round_agents(self.dir / "fresh"), self.m.ALL_AGENTS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
