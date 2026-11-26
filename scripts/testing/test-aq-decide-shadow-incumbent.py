#!/usr/bin/env python3
"""aq-decide shadow stage: the caller's incumbent answer is logged beside the T0.5 shadow so agreement is measurable."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ai" / "lib"))
from aq_decide import Decider  # noqa: E402


class ShadowIncumbent(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name)
        self.d = Decider(state_dir=self.state)

    def tearDown(self):
        self.tmp.cleanup()

    def rows(self):
        return [json.loads(ln) for ln in (self.state / "decisions.jsonl").read_text().splitlines() if ln.strip()]

    def test_incumbent_logged_and_never_acted_on(self):
        req = {"state": {"text": "write a python function that sorts an array", "mode": "auto"},
               "questions": {"task_profile": {"type": "choice"}}, "incumbent": {"task_profile": "code"}}
        res = self.d.decide(req, caller="test")
        self.assertEqual(res["answers"]["task_profile"]["outcome"], "abstain")  # shadow: nothing acted on
        row = self.rows()[-1]
        self.assertEqual(row["incumbent"], "code")
        self.assertFalse(row["shadow"]["acted_on"])

    def test_bad_incumbent_ignored(self):
        req = {"state": {"text": "hello", "mode": "auto"}, "questions": {"task_profile": {"type": "choice"}},
               "incumbent": {"task_profile": {"x": 1}}}
        self.d.decide(req, caller="test")
        self.assertNotIn("incumbent", self.rows()[-1])

    def test_report_agreement_uses_incumbent(self):
        req = {"state": {"text": "write a python function that sorts an array", "mode": "auto"},
               "questions": {"task_profile": {"type": "choice"}}, "incumbent": {"task_profile": "code"}}
        self.d.decide(req, caller="test")
        shadow_ans = self.rows()[-1]["shadow"]["answer"]
        out = subprocess.run([sys.executable, str(ROOT / "scripts/ai/aq-decide"), "shadow-report"],
                             capture_output=True, text=True, env={"AQ_DECIDE_STATE_DIR": str(self.state), "PATH": "/usr/bin:/bin"})
        self.assertEqual(out.returncode, 0, out.stderr)
        rep = json.loads(out.stdout)
        self.assertEqual(rep["compared_decisions"], 1)
        self.assertEqual(rep["agreement_rate"], 1.0 if shadow_ans == "code" else 0.0)

    def test_dispatch_passes_incumbent(self):
        src = (ROOT / "scripts/ai/lib/dispatch.py").read_text()
        self.assertIn('"incumbent": {"task_profile": heuristic}', src)


class NixBatchB(unittest.TestCase):
    """Static wiring of the batch-B profile entries (the live proof is `nix eval`, see the evidence file)."""

    def test_profile_stages_aqdecide_in_shadow(self):
        prof = (ROOT / "nix/modules/profiles/ai-dev.nix").read_text()
        self.assertIn("mySystem.aiStack.aqDecide.enable = lib.mkDefault true;", prof)
        self.assertIn('mySystem.aiStack.aqDecide.mode = lib.mkDefault "shadow";', prof)
        self.assertIn('mySystem.aiStack.aqDecide.integrations.taskProfile.mode = lib.mkDefault "shadow";', prof)
        # held items stay off: embedder needs a model fetch unit, headroom has no package, broker waits on C2
        for held in ("aqDecide.embedder.enable", "headroomProxy.enable", "workflowDeviationBroker.enable"):
            self.assertNotIn(f"mySystem.aiStack.{held} = lib.mkDefault true", prof)

    def test_decorative_flags_removed(self):
        for rel in ("ai-stack/mcp-servers/hybrid-coordinator/core/config.py", "config/feature-defaults.yaml",
                    "ai-stack/trading-agents/config.py"):
            txt = (ROOT / rel).read_text()
            for dead in ("QUERY_EXPANSION_ENABLED", "MULTI_TURN_QUERY_EXPANSION", "TRADING_ENABLE_CHECKPOINTS"):
                self.assertNotIn(dead, txt, f"{dead} still in {rel}")


if __name__ == "__main__":
    unittest.main()
