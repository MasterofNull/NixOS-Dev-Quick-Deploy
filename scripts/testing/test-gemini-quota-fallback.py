#!/usr/bin/env python3
"""Argon quota exhaustion retries once on Hydrogen; nothing else retries."""
import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ROOT / "scripts/ai/lib/gemini-quota-fallback.sh"
QUOTA = "error: Individual quota reached. RESOURCE_EXHAUSTED (code 429)"


class GeminiQuotaFallback(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.log = self.dir / "calls.jsonl"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def stub(self, argon: str, hydrogen: str) -> Path:
        """Stub CLI: behaviour per model; 'quota', 'other' or 'ok'."""
        path = self.dir / "gemini"
        path.write_text(f"""#!/usr/bin/env python3
import json, sys
a = sys.argv[1:]
m = a[a.index("--model") + 1] if "--model" in a else ""
open({str(self.log)!r}, "a").write(json.dumps(m) + "\\n")
mode = {{"": {argon!r}, "gemini-4-argon": {argon!r}, "gemini-4-hydrogen": {hydrogen!r}}}.get(m, "ok")
if mode == "quota":
    print({QUOTA!r}); sys.exit(1)
if mode == "other":
    print("error: invalid request"); sys.exit(2)
print("OK")
""")
        path.chmod(path.stat().st_mode | stat.S_IEXEC)
        return path

    def run_cli(self, stub: Path, *extra: str):
        r = subprocess.run(["bash", str(WRAPPER), str(stub), "-p", "hi", *extra],
                           capture_output=True, text=True, timeout=30, env=dict(os.environ))
        calls = [json.loads(x) for x in self.log.read_text().splitlines()] if self.log.exists() else []
        return r, calls

    def test_argon_quota_retries_on_hydrogen_and_succeeds(self):
        r, calls = self.run_cli(self.stub("quota", "ok"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(calls, ["", "gemini-4-hydrogen"])
        self.assertIn("retrying once with gemini-4-hydrogen", r.stderr)
        self.assertNotIn("GEMINI_LANE_UNAVAILABLE", r.stderr)

    def test_explicit_argon_model_also_falls_back(self):
        r, calls = self.run_cli(self.stub("quota", "ok"), "--model", "gemini-4-argon")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(calls, ["gemini-4-argon", "gemini-4-hydrogen"])

    def test_non_quota_error_does_not_retry(self):
        r, calls = self.run_cli(self.stub("other", "ok"))
        self.assertEqual(r.returncode, 2)
        self.assertEqual(calls, [""])
        self.assertNotIn("retrying", r.stderr)

    def test_other_model_quota_does_not_retry(self):
        stub = self.stub("ok", "ok")
        stub.write_text(stub.read_text().replace('mode = {', 'mode = {"gemini-3.8-flash": "quota", '))
        r, calls = self.run_cli(stub, "--model", "gemini-3.8-flash")
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(calls, ["gemini-3.8-flash"])

    def test_hydrogen_also_exhausted_marks_lane_unavailable(self):
        r, calls = self.run_cli(self.stub("quota", "quota"))
        self.assertEqual(r.returncode, 1)
        self.assertEqual(calls, ["", "gemini-4-hydrogen"])
        self.assertIn("GEMINI_LANE_UNAVAILABLE", r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
