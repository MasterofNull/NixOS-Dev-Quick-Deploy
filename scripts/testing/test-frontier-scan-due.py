#!/usr/bin/env python3
"""W3-S5: scan-due — fake clock + fake fetcher; no network."""
import json, sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "ai" / "lib"))
import frontier_backlog as fb  # noqa: E402
import frontier_scan as fsc  # noqa: E402

DAY = 86400
NOW = 1_800_000_000.0


def cat(*rows):
    return {"sources": [dict({"name": r[0], "url": f"https://x.test/{r[0]}", "pillar": "p", "trust_tier": "primary",
                              "cadence": "weekly"}, id=r[0], **(r[1] if len(r) > 1 else {})) for r in rows]}


class Fetch:
    def __init__(self, pages): self.pages, self.calls = pages, []
    def __call__(self, url, timeout=0, etag=None):
        self.calls.append(url)
        v = self.pages[url.rsplit("/", 1)[1]]
        if isinstance(v, Exception): raise v
        return {"text": v, "etag": None}


class T(unittest.TestCase):
    def setUp(self):
        d = tempfile.mkdtemp(); self.state = f"{d}/s.json"; self.store = f"{d}/b.jsonl"

    def run_scan(self, c, pages, now=NOW, **kw):
        f = Fetch(pages)
        return fsc.scan_due(c, state_path=self.state, store=self.store, fetcher=f, now=now, **kw), f

    def seed(self, sid, fp, age_days):
        fsc.save_state(self.state, {**fsc.load_state(self.state),
                       sid: {"last_scan": fsc._iso(NOW - age_days * DAY), "fingerprint": fp}})

    def fp(self, text):
        import hashlib; return hashlib.sha256(fsc.normalize(text).encode()).hexdigest()

    def test_not_due_skipped(self):
        self.seed("a", "x", 2)
        out, f = self.run_scan(cat(("a",)), {"a": "t"})
        self.assertEqual(f.calls, []); self.assertFalse(out["sources"][0]["due"])
        self.assertEqual(out["sources"][0]["last_scan_age_days"], 2.0)

    def test_secondary_never_fetched(self):
        out, f = self.run_scan(cat(("a", {"trust_tier": "secondary"})), {"a": "t"})
        self.assertEqual(f.calls, [])

    def test_unchanged_no_candidate_and_first_scan_baseline(self):
        out, _ = self.run_scan(cat(("a",)), {"a": "<p>hi</p>"})
        self.assertEqual(out["results"][0]["outcome"], "baseline")
        self.seed("a", self.fp("<b>hi</b>"), 8)
        out, _ = self.run_scan(cat(("a",)), {"a": "<p>hi</p>"})
        self.assertEqual(out["results"][0]["outcome"], "unchanged")
        self.assertEqual(fb.load(self.store), [])

    def test_changed_files_exactly_one_candidate_dedup(self):
        self.seed("a", "oldhash00", 8)
        out, _ = self.run_scan(cat(("a",)), {"a": "new text"})
        self.assertEqual(out["results"][0]["outcome"], "candidate_filed")
        recs = fb.load(self.store)
        self.assertEqual(len(recs), 1); self.assertEqual(recs[0]["status"], "new"); self.assertEqual(recs[0]["verdict"], "monitor")
        # same change re-detected later (state lost) -> deduped
        self.seed("a", "oldhash00", 8)
        out, _ = self.run_scan(cat(("a",)), {"a": "new text"}, now=NOW + 99)
        self.assertEqual(out["results"][0]["outcome"], "candidate_duplicate")
        self.assertEqual(len(fb.load(self.store)), 1)
        # normal rerun: not due now
        out, f = self.run_scan(cat(("a",)), {"a": "new text"}, now=NOW + 100)
        self.assertEqual(f.calls, [])

    def test_fetch_error_recorded(self):
        out, _ = self.run_scan(cat(("a",), ("b",)), {"a": OSError("boom"), "b": "ok"})
        o = {r["id"]: r for r in out["results"]}
        self.assertEqual(o["a"]["outcome"], "error"); self.assertEqual(o["b"]["outcome"], "baseline")
        self.assertIn("boom", fsc.load_state(self.state)["a"]["last_error"])

    def test_caps(self):
        pages = {k: "t" for k in "abcd"}
        out, f = self.run_scan(cat(("a",), ("b",), ("c",), ("d",)), pages, max_sources=2)
        self.assertEqual(len(f.calls), 2); self.assertEqual(out["deferred_by_cap"], 2)
        Path(self.state).unlink()
        t = iter(range(0, 1000, 100))
        out, f = self.run_scan(cat(("a",), ("b",), ("c",)), pages, total_budget=150, clock=lambda: next(t))
        self.assertLess(len(f.calls), 3); self.assertGreater(out["deferred_by_cap"], 0)

    def test_dry_run_no_fetch_no_write(self):
        out, f = self.run_scan(cat(("a",)), {"a": "t"}, dry_run=True)
        self.assertEqual(f.calls, []); self.assertFalse(Path(self.state).exists())
        self.assertEqual(out["results"][0]["outcome"], "would_scan")


if __name__ == "__main__":
    unittest.main(verbosity=1)
