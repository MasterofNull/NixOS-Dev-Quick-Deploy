#!/usr/bin/env python3
"""aq-land outcome receipt hook: one receipt per landing, write failure only warns, REQUEST_CHANGES is counted."""
import importlib.util
import json
import pathlib
import unittest

HERE = pathlib.Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("test_aq_land", HERE / "test-aq-land.py")
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


class Outcome(_mod.Base):
    def _log(self):
        return self.S / "deleg" / "outcome-receipts.jsonl"

    def test_successful_landing_appends_exactly_one_receipt(self):
        self.env["AQ_DELEGATION_DIR"] = str(self.S / "deleg")
        self.land(expect=0)
        recs = [json.loads(x) for x in self._log().read_text().splitlines()]
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["author_lane"], "claude")
        self.assertEqual(recs[0]["reviewer_lanes"], ["gemini"])
        self.assertEqual(recs[0]["request_changes_rounds"], 0)

    def test_write_failure_warns_and_landing_still_succeeds(self):
        blocker = self.S / "not-a-dir"
        blocker.write_text("x")
        self.env["AQ_DELEGATION_DIR"] = str(blocker / "deleg")
        r = self.land(expect=0)
        self.assertIn("WARN outcome receipt not written", r.stderr)
        self.assertEqual(self.ghs()["prs"][0]["state"], "MERGED")

    def test_request_changes_stop_increments_checkpoint_counter(self):
        self.env["AQ_DELEGATION_DIR"] = str(self.S / "deleg")
        self.cfg({"gemini": {"mode": "negative"}})
        self.land(expect=1)
        cp = json.loads((self.S / "state" / "feat_x" / "checkpoint.json").read_text())
        self.assertEqual(cp["rc_rounds"], 1)
        self.assertFalse(self._log().exists())


if __name__ == "__main__":
    unittest.main()
