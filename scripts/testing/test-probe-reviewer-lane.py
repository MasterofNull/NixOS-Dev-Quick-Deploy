#!/usr/bin/env python3
"""Offline tests for scripts/ai/probe-reviewer-lane: stub transport, no network, no real token."""
from __future__ import annotations

import importlib.machinery
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_loader = importlib.machinery.SourceFileLoader("probe_reviewer_lane", str(ROOT / "scripts/ai/probe-reviewer-lane"))
_spec = importlib.util.spec_from_loader("probe_reviewer_lane", _loader)
assert _spec is not None
P = importlib.util.module_from_spec(_spec)
sys.modules["probe_reviewer_lane"] = P
_loader.exec_module(P)

TOKEN = "gho_FAKESYNTHETICTOKEN0123456789abcdef"
LANE = {"catalog": "https://x.invalid/catalog", "chat": "https://x.invalid/chat", "model": "toy/m", "token_cmd": "true"}


def reply(text: str, status: int = 200, hdrs: dict | None = None):
    body = json.dumps({"choices": [{"message": {"content": text}}]}) if status == 200 else text
    return status, hdrs or {}, body


def make_transport(defect_verdict: str = "REQUEST_CHANGES", clean_verdict: str = "PASS", catalog_status: int = 200, chat_status: int = 200, echo_token: bool = False):
    def t(method, url, headers, body):
        assert headers["Authorization"] == f"Bearer {TOKEN}"
        if "catalog" in url:
            return catalog_status, {}, json.dumps([{"id": "toy/m"}, {"id": "toy/n"}])
        if chat_status != 200:
            return chat_status, {}, ("denied " + TOKEN) if echo_token else "nope"
        prompt = json.loads(body)["messages"][1]["content"]
        if "exactly: ok" in prompt:
            return reply("ok", hdrs={"x-ratelimit-remaining": "9", "x-ratelimit-limit": "10"})
        clean = "toy/util.py" in prompt or "toy/cfg.py" in prompt
        return reply("finding\nReview-Disposition: " + (clean_verdict if clean else defect_verdict))
    return t


class Tests(unittest.TestCase):
    def test_parser(self):
        self.assertEqual(P.parse_disposition("x\nReview-Disposition: PASS\n"), "PASS")
        self.assertIsNone(P.parse_disposition("no line"))
        self.assertIsNone(P.parse_disposition("Review-Disposition: PASS\nReview-Disposition: REQUEST_CHANGES"))
        self.assertIsNone(P.parse_disposition("Review-Disposition: MAYBE"))

    def test_corpus_shape(self):
        self.assertEqual(sum(1 for c in P.CASES if c.defect), 8)
        self.assertEqual(sum(1 for c in P.CASES if not c.defect), 2)
        blob = "".join(c.diff for c in P.CASES)
        for bad in ("/home/", "hyperd", "gho_"):
            self.assertNotIn(bad, blob)

    def test_scoring_pass_and_fail(self):
        ok = P.probe("ghm", LANE, "toy/m", make_transport(), TOKEN)
        self.assertEqual(ok["status"], "ok")
        self.assertTrue(ok["capability"]["passed"])
        self.assertEqual(ok["capability"]["hits"], 8)
        self.assertEqual(ok["rate_limit"]["x-ratelimit-remaining"], "9")
        weak = P.probe("ghm", LANE, "toy/m", make_transport(defect_verdict="PASS"), TOKEN)
        self.assertFalse(weak["capability"]["passed"])
        self.assertEqual(weak["capability"]["misses"], 8)
        noisy = P.probe("ghm", LANE, "toy/m", make_transport(clean_verdict="REQUEST_CHANGES"), TOKEN)
        self.assertEqual(noisy["capability"]["false_request_changes"], 2)
        self.assertFalse(noisy["capability"]["passed"])

    def test_one_false_rc_allowed_boundary(self):
        rows = [{"defect": "d", "disposition": "REQUEST_CHANGES"}] * 4 + [{"defect": "d", "disposition": None}] \
            + [{"defect": None, "disposition": "REQUEST_CHANGES"}, {"defect": None, "disposition": "PASS"}]
        s = P.score(rows)
        self.assertEqual((s["hits"], s["misses"], s["no_verdict"], s["false_request_changes"]), (4, 1, 1, 1))
        self.assertTrue(s["passed"])  # 0.8 hit rate, 1 false RC

    def test_failures_are_unavailable_not_verdicts(self):
        kws: list[dict] = [{"catalog_status": 403}, {"catalog_status": 401}, {"catalog_status": 500}, {"chat_status": 429}, {"chat_status": 503}]
        for kw in kws:
            r = P.probe("ghm", LANE, "toy/m", make_transport(**kw), TOKEN)
            self.assertEqual(r["status"], "lane_unavailable", kw)
            self.assertNotIn("capability", r)
            self.assertNotIn("disposition", json.dumps(r).replace("Review-Disposition", ""))

    def test_catalog_200_non_list_is_not_entitlement(self):
        def t(method, url, headers, body):
            return 200, {}, "OK\r\n"
        r = P.probe("ghm", LANE, "toy/m", t, TOKEN)
        self.assertEqual((r["status"], r["entitled"]), ("lane_unavailable", False))

    def test_transport_exception_is_unavailable(self):
        def boom(*a):
            raise P.LaneUnavailable("transport error (URLError)")
        self.assertEqual(P.probe("ghm", LANE, "toy/m", boom, TOKEN)["status"], "lane_unavailable")

    def test_token_never_in_output_or_files(self):
        r = P.probe("ghm", LANE, "toy/m", make_transport(chat_status=500, echo_token=True), TOKEN)
        self.assertNotIn(TOKEN, json.dumps(r))
        with tempfile.TemporaryDirectory() as d:
            path = P.write_result(r, TOKEN, Path(d))
            self.assertNotIn(TOKEN, path.read_text())
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(RuntimeError):
                P.write_result({"lane": "ghm", "leak": TOKEN}, TOKEN, Path(d))
            self.assertEqual(len(list(Path(d).iterdir())), 1)

    def test_main_end_to_end_no_token_in_stdout_or_files(self):
        with tempfile.TemporaryDirectory() as d:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = P.main(["--lane", "ghm", "--token-cmd", f"echo {TOKEN}", "--out-dir", d], transport=make_transport())
            self.assertEqual(rc, 0)
            self.assertNotIn(TOKEN, buf.getvalue())
            for f in Path(d).iterdir():
                self.assertNotIn(TOKEN, f.read_text())

    def test_no_token_is_unavailable(self):
        with tempfile.TemporaryDirectory() as d:
            with redirect_stdout(io.StringIO()):
                rc = P.main(["--token-cmd", "false", "--out-dir", d], transport=make_transport())
            self.assertEqual(rc, 3)


if __name__ == "__main__":
    unittest.main()
