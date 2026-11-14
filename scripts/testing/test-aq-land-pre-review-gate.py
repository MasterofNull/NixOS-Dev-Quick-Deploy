#!/usr/bin/env python3
"""aq-land runs the deterministic tier0 gate before any reviewer is dispatched (stubbed tier0 and delegates)."""
import importlib.util
import pathlib
import unittest

HERE = pathlib.Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("test_aq_land", HERE / "test-aq-land.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


def sh_ls(t):
    return _mod.sh(t.S, "git", "--git-dir", str(t.origin), "for-each-ref", "refs/heads/feat")


class PreReviewGate(_mod.Base):
    def _staged(self):
        self.change("scripts/bar.py", "print(2)\n", commit=False)
        msg = self.S / "msg.txt"
        msg.write_text("feat(x): bar\n")
        return msg

    def test_failing_gate_stops_before_any_reviewer(self):
        msg = self._staged()
        (self.S / "tier0.fail").write_text("")
        line = self.stop_line(self.land("--commit-msg-file", str(msg), expect=1))
        self.assertIn("STOP tier0", line)
        for lane in ("gemini", "codex", "local"):
            self.assertEqual(self.calls(lane), [], lane)
        self.assertFalse([c for c in self.ghs().get("calls", []) if c.startswith(("pr create", "pr edit"))])
        self.assertEqual(sh_ls(self), "")  # nothing pushed
        self.assertEqual(self.published(), [])

    def test_passing_gate_proceeds_to_review(self):
        msg = self._staged()
        self.land("--commit-msg-file", str(msg), expect=0)
        self.assertIn("tier0", (self.S / "tier0.log").read_text())
        self.assertEqual(len(self.calls("gemini")), 1)


if __name__ == "__main__":
    unittest.main()
