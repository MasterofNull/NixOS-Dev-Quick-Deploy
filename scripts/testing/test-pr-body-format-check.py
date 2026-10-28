#!/usr/bin/env python3
"""Tests for scripts/governance/check-pr-body-format.py."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "governance", "check-pr-body-format.py")

PR634 = '## Details\n\n- **Scope:** 12 files, +515/-17. New `scripts/ai/aq-review-receipt`; `scripts/governance/check-review-disposition.py` now requires a receipt; `scripts/ai/delegate-to-codex --role`; docs (PR template, githooks README, delivery-workflow canon, WORKAROUND-REGISTER WR-REVIEW-1).\n- **Merge order:** merge this first. #633 and #635 run the old checker on their branches, which rejects their receipt-only commits; after this merges, update those branches from main.\n- **Tests:** `test-review-disposition-check.py` 22 OK; `test-aq-review-receipt.py` 5 OK; tier0 71 passed / 0 failed. CI `review-disposition` passes on this head.\n- **Risk:** affects every future PR. A PR without a valid receipt fails the required check. Detection-grade, not cryptographic: lanes share one Unix account, so a lane that edits the registry and output log can still forge a receipt. That is logged as WR-REVIEW-1.\n\n### Review record\nAuthor-lane: claude\nReview-Disposition: PASS\nReviewed-head-sha: 18e5671a5853197c6ab84795f82066cf5f3e4abc\nReviewed-subject-sha256: 9520ab77d40659da04b8392ca24bb5cb107fccf82bb0acfd88d7cc0a32430126\nReviewed-by: local-direct\nReview-Receipt: .agent/reviews/receipts/pr634-18e5671a5853.json\n\nReview history: Codex reviewed `ac66ac63` and requested changes (4 bypasses, listed under How). Local Qwen run `local-20261027-085914-v8n0er` reviewed the fixed head `18e5671a` and passed it, confirming each bypass closed. Codex\'s daily budget was exhausted, so local Qwen was substituted (Rule 18, recorded in PULSE.log). The receipt was added in a receipt-only commit (`8a26c97e`).\n\n## What\n\nPR descriptions now have to point to proof that an independent reviewer actually reviewed the code. Previously a PR could just say "Reviewed-by: codex" and the check believed it.\n\n## How\n\n- After a reviewer agent finishes, `aq-review-receipt mint` writes a small receipt file. The receipt records which run did the review, which exact commit it reviewed, its verdict, and a fingerprint of its output. It refuses to mint unless the run exists in the delegation registry, finished, had a review role, and wasn\'t the author\'s own lane. The output must also name the commit and end with a verdict line.\n- The PR check reads that receipt from the PR\'s own commit. It has to match the PR description, and a "request changes" verdict fails.\n- Codex\'s first review found four ways around this, all now closed:\n  - Renaming a code file into the receipts folder looked like a harmless receipt-only change.\n  - Editing a receipt\'s verdict from "request changes" to "pass" still verified.\n  - An empty review log could mint a receipt.\n  - Wrong value types were accepted.\n\n## Why\n\nAn audit on 2026-10-27 found about 85 merged PRs (#543–#632) whose descriptions claimed reviews that never happened. The old check only checked the text format, so a made-up claim passed. This makes a claimed review traceable to a real reviewer run.\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)\n'

VALID = "## Details\n- a\n### Review record\nX: y\n\n## What\nw\n\n## How\nh\n\n## Why\ny\n"


def run(body=None, payload=True):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "event.json")
        if payload:
            with open(p, "w") as f:
                json.dump({"pull_request": {"body": body}}, f)
        env = {k: v for k, v in os.environ.items() if k != "GITHUB_EVENT_PATH"}
        r = subprocess.run([sys.executable, SCRIPT, p], capture_output=True, text=True, env=env)
        return r.returncode, r.stdout


class PrBodyFormat(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(run(VALID)[0], 0)

    def test_pr634_fixture(self):
        self.assertEqual(run(PR634)[0], 0)

    def test_missing_details(self):
        self.assertEqual(run(VALID.replace("## Details", "## Summary"))[0], 1)

    def test_details_not_first(self):
        self.assertEqual(run("intro\n\n## Overview\nx\n\n" + VALID)[0], 1)

    def test_missing_why(self):
        self.assertEqual(run(VALID.split("## Why")[0])[0], 1)

    def test_out_of_order(self):
        b = "## Details\n- a\n\n## How\nh\n\n## What\nw\n\n## Why\ny\n"
        self.assertEqual(run(b)[0], 1)

    def test_empty_how(self):
        b = "## Details\n- a\n\n## What\nw\n\n## How\n\n\n## Why\ny\n"
        self.assertEqual(run(b)[0], 1)

    def test_duplicate_what(self):
        self.assertEqual(run(VALID + "\n## What\nagain\n")[0], 1)

    def test_headings_only_in_fence(self):
        b = "## Details\n- a\n\n```\n## What\nw\n## How\nh\n## Why\ny\n```\n"
        self.assertEqual(run(b)[0], 1)

    def test_no_payload(self):
        self.assertEqual(run(payload=False)[0], 2)


if __name__ == "__main__":
    unittest.main()
