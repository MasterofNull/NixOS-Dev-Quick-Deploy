#!/usr/bin/env python3
"""Persona P2: instance labels in PULSE, a2a events and review receipts (additive)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/ai/lib"))
import event_log  # noqa: E402
import resume_projector as rp  # noqa: E402
from instance_label import agent_slot, build_label  # noqa: E402

TOOL = ROOT / "scripts/ai/aq-review-receipt"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), "-c", "commit.gpgsign=false", *args],
                          capture_output=True, text=True, check=True).stdout.strip()


class Helper(unittest.TestCase):
    def test_format(self) -> None:
        with mock.patch.dict(os.environ, {"PERSONA": "1"}):
            self.assertEqual(build_label("claude", "opus-5.5", "06eebc53"), "Simurg@claude/opus-5.5#06eebc53")
            self.assertEqual(build_label("Codex", "gpt", "0123456789ab"), "Simurg@codex/gpt#01234567")
            self.assertEqual(build_label("local", ""), "Simurg@local/unknown")

    def test_kill_switch_is_plain_identity(self) -> None:
        with mock.patch.dict(os.environ, {"PERSONA": "0"}):
            self.assertEqual(build_label("claude", "opus-5.5", "06eebc53"), "claude/opus-5.5")


class DirectWriterSlot(unittest.TestCase):
    def test_label_when_model_known(self) -> None:
        with mock.patch.dict(os.environ, {"PERSONA": "1", "AQ_INSTANCE_MODEL": "opus-5.5",
                                          "AQ_INSTANCE_SESSION": "0123456789ab"}):
            self.assertEqual(agent_slot("claude-hook", "claude"), "Simurg@claude/opus-5.5#01234567")

    def test_unchanged_when_model_unknown(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "AQ_INSTANCE_MODEL"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(agent_slot("claude-hook", "claude"), "claude-hook")

    def test_persona_off_plain_identity(self) -> None:
        with mock.patch.dict(os.environ, {"PERSONA": "0", "AQ_INSTANCE_MODEL": "opus-5.5"}):
            self.assertEqual(agent_slot("claude-hook", "claude"), "claude/opus-5.5")

    def test_hook_writes_line(self) -> None:
        hook = ROOT / "scripts/ai/aq-hook-post-tool"
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / ".agent/collaboration").mkdir(parents=True)
            base = {**os.environ, "CLAUDE_PROJECT_DIR": td, "CLAUDE_TOOL_NAME": "Edit"}
            base.pop("AQ_INSTANCE_MODEL", None)
            log = Path(td) / ".agent/collaboration/PULSE.log"
            subprocess.run([sys.executable, str(hook)], env=base, check=True)
            subprocess.run([sys.executable, str(hook)], env={**base, "AQ_INSTANCE_MODEL": "opus-5.5", "PERSONA": "1"}, check=True)
            a, b = log.read_text().splitlines()
            self.assertIn("] [claude-hook] [post-tool]: Edit executed", a)
            self.assertIn("] [Simurg@claude/opus-5.5] [post-tool]: Edit executed", b)


class PulseAndEvents(unittest.TestCase):
    def test_instance_additive_and_old_events_parse(self) -> None:
        with tempfile.TemporaryDirectory() as td, mock.patch.dict(os.environ, {"A2A_EVENT_LOG": f"{td}/e.jsonl"}):
            event_log.emit("claude", "pulse.append", payload={"action": "old"})
            event_log.emit("claude", "pulse.append", payload={"action": "new"},
                           instance="Simurg@claude/opus-5.5#06eebc53")
            evs = event_log.read_all()
            self.assertNotIn("instance", evs[0].payload)
            self.assertEqual(evs[1].payload["instance"], "Simurg@claude/opus-5.5#06eebc53")
            lines = rp.project_pulse(evs).splitlines()
            self.assertIn("[claude] [old]", lines[0])
            self.assertIn("[Simurg@claude/opus-5.5#06eebc53] [new]", lines[1])


class Receipts(unittest.TestCase):
    def setUp(self) -> None:
        self._t = tempfile.TemporaryDirectory()
        self.d = Path(self._t.name)
        (self.d / "out").mkdir()
        _git(self.d, "init", "-q")
        _git(self.d, "-c", "user.name=t", "-c", "user.email=t@x.io", "commit", "--allow-empty", "-q", "-m", "x")
        self.head = _git(self.d, "rev-parse", "HEAD")
        (self.d / "out/rev.log").write_text(f"reviewed {self.head[:12]}\nReview-Disposition: PASS\n")
        self.reg = self.d / "registry.jsonl"
        entry = {"id": "run12345678", "agent": "codex", "role": "reviewer", "output_file": "out/rev.log",
                 "status": "done", "model_effective": "gpt-5"}
        self.reg.write_text(json.dumps(entry) + "\n")

    def tearDown(self) -> None:
        self._t.cleanup()

    def run_tool(self, *a: str, persona: str = "1") -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(TOOL), "--root", str(self.d), "--registry", str(self.reg), *a],
                              capture_output=True, text=True, env={**os.environ, "PERSONA": persona})

    def mint(self, author: str = "claude", persona: str = "1") -> subprocess.CompletedProcess[str]:
        return self.run_tool("mint", "--run-id", "run12345678", "--pr", "7", "--head", self.head,
                             "--author-lane", author, "--author-model", "opus-5.5", "--author-session", "06eebc53",
                             "--repo", "o/r", "--base", self.head, "--out", str(self.d / "r.json"), persona=persona)

    def receipt(self) -> dict:
        return json.loads((self.d / "r.json").read_text())

    def test_both_labels_from_provenance(self) -> None:
        r = self.mint()
        self.assertEqual(r.returncode, 0, r.stderr)
        rec = self.receipt()
        self.assertEqual(rec["author_instance"], "Simurg@claude/opus-5.5#06eebc53")
        self.assertEqual(rec["reviewer_instance"], "Simurg@codex/gpt-5#run12345")
        self.assertEqual(self.run_tool("verify", str(self.d / "r.json")).returncode, 0)

    def test_persona_off_plain_labels(self) -> None:
        self.assertEqual(self.mint(persona="0").returncode, 0)
        self.assertEqual(self.receipt()["reviewer_instance"], "codex/gpt-5")

    def test_verify_independent_of_verifier_persona_env(self) -> None:
        for mint_p, verify_p in (("0", "1"), ("1", "0")):
            self.assertEqual(self.mint(persona=mint_p).returncode, 0)
            r = self.run_tool("verify", str(self.d / "r.json"), persona=verify_p)
            self.assertEqual(r.returncode, 0, f"mint={mint_p} verify={verify_p}: {r.stderr}")

    def test_blank_or_null_reviewer_instance_fails_verify(self) -> None:
        self.mint()
        for bad in ("", None):
            rec = self.receipt()
            rec["reviewer_instance"] = bad
            (self.d / "r.json").write_text(json.dumps(rec))
            self.assertNotEqual(self.run_tool("verify", str(self.d / "r.json")).returncode, 0, repr(bad))

    def test_old_receipt_without_labels_verifies(self) -> None:
        self.mint()
        rec = self.receipt()
        del rec["reviewer_instance"], rec["author_instance"]
        (self.d / "r.json").write_text(json.dumps(rec))
        r = self.run_tool("verify", str(self.d / "r.json"))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_forged_reviewer_instance_fails_verify(self) -> None:
        self.mint()
        rec = self.receipt()
        rec["reviewer_instance"] = "Simurg@codex/other#run12345"
        (self.d / "r.json").write_text(json.dumps(rec))
        self.assertNotEqual(self.run_tool("verify", str(self.d / "r.json")).returncode, 0)

    def test_same_lane_rejected_despite_shared_persona(self) -> None:
        r = self.mint(author="codex")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("equals author lane", r.stderr)
        self.assertFalse((self.d / "r.json").exists())


if __name__ == "__main__":
    unittest.main()
