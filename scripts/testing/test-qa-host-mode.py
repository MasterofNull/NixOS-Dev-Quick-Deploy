#!/usr/bin/env python3
"""aq-qa phase 0 host/CI determinism: host-only FAIL -> SKIP off-host, never PASS, untouched on host."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "testing"))
from harness_qa.core.host_mode import demote_host_only, host_mode  # noqa: E402
from harness_qa.core.result import Status, failed, passed, skipped  # noqa: E402


def sample():
    return [failed(1, "0.1.1:llama-cpp", "unit active", "not active"), failed(5, "0.2.1:redis", "port bound"),
            failed(4, "0.9.9", "static contract", "missing file"),   # not host-only: must stay FAIL
            passed(1, "0.1.2", "unit"), skipped(1, "0.4.1", "x", "already skipped")]


class HostMode(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.marker = Path(self.tmp.name) / "NIXOS"

    def test_detection_is_explicit(self):
        self.assertEqual(host_mode({"GITHUB_ACTIONS": "true"}, self.marker)[0], "ci")
        self.assertEqual(host_mode({"CI": "1"}, self.marker)[0], "ci")
        self.assertEqual(host_mode({}, self.marker)[0], "ci")           # no /etc/NIXOS
        self.marker.write_text("")
        self.assertEqual(host_mode({}, self.marker)[0], "host")
        self.assertEqual(host_mode({"CI": "true"}, self.marker)[0], "ci")  # CI wins over marker
        self.assertEqual(host_mode({"AQ_QA_HOST_MODE": "host", "CI": "true"}, self.marker)[0], "host")

    def test_ci_demotes_host_only_failures_to_skip_never_pass(self):
        out = demote_host_only(sample(), {"GITHUB_ACTIONS": "true"}, self.marker)
        status = {r.id: r.status for r in out}
        self.assertEqual(status["0.1.1:llama-cpp"], Status.SKIP)
        self.assertEqual(status["0.2.1:redis"], Status.SKIP)
        self.assertEqual(status["0.9.9"], Status.FAIL)       # real failure still fails
        self.assertEqual(status["0.1.2"], Status.PASS)       # genuine pass untouched
        self.assertNotIn(Status.PASS, [r.status for r in out if r.id.startswith("0.1.1")])
        self.assertIn("host-only check not run", next(r.reason for r in out if r.id == "0.2.1:redis"))

    def test_host_leaves_results_unchanged(self):
        self.marker.write_text("")
        original = sample()
        self.assertEqual(demote_host_only(original, {}, self.marker), original)

    def test_deterministic_same_input_same_output(self):
        env = {"GITHUB_ACTIONS": "true"}
        a = [(r.id, r.status) for r in demote_host_only(sample(), env, self.marker)]
        b = [(r.id, r.status) for r in demote_host_only(sample(), env, self.marker)]
        self.assertEqual(a, b)


class GateQaVerdict(unittest.TestCase):
    """tier0 phase-0 verdict regex: an unanchored "0 failed" also matched "10/20/30 failed" and
    let a red QA run pass (CI parity-scorecard-gate passed only when the failure count ended in 0)."""

    def _verdict_pattern(self):
        import re
        src = (ROOT / "scripts/governance/tier0-validation-gate.sh").read_text()
        return re.search(r'grep -qE "(\[0-9\]\+ passed[^"]*0 failed)"', src).group(1)

    def test_only_a_true_zero_failed_summary_passes(self):
        import subprocess
        pat = self._verdict_pattern()

        def verdict(summary):
            return subprocess.run(["grep", "-qE", pat], input=summary, text=True).returncode == 0

        self.assertTrue(verdict("186 passed \u00b7 0 failed \u00b7 11 skipped \u00b7 259s"))
        for n in (10, 20, 30, 100, 26):
            self.assertFalse(verdict(f"140 passed \u00b7 {n} failed \u00b7 11 skipped \u00b7 259s"), n)

    def test_ci_off_host_probes_are_host_only(self):
        # Ids that can only fail on a runner without the stack (found by replaying aq-qa 0 offline).
        from harness_qa.core.host_mode import HOST_ONLY_IDS
        for cid in ("0.5.2", "0.7.1", "0.12.1", "0.10.5", "0.152.3", "0.152.4", "0.152.9", "86.7"):
            self.assertIn(cid, HOST_ONLY_IDS)


class GateRowOrdering(unittest.TestCase):
    def test_non_live_failure_is_not_truncated_behind_host_only_rows(self):
        import subprocess
        src = (ROOT / "scripts/governance/tier0-validation-gate.sh").read_text()
        fn = src[src.index("log_failed_qa_rows() {"):src.index("\nskip() {")]
        rows = "\n".join(f"| 0.1.1:u{i} | unit | \u2717 |" for i in range(40)) + "\n| 0.9.9 | static contract | \u2717 |\n"
        out = subprocess.run(["bash", "-c", f'log(){{ echo "$*"; }}\n{fn}\nlog_failed_qa_rows "$OUT" 30'],
                             env={"OUT": rows, "PATH": "/usr/bin:/bin:/run/current-system/sw/bin"},
                             capture_output=True, text=True).stdout
        self.assertIn("0.9.9", out)
        self.assertIn("of 41", out)


if __name__ == "__main__":
    unittest.main()
