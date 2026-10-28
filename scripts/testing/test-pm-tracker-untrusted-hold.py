#!/usr/bin/env python3
"""Offline tests for the aq-pm-tracker untrusted-author hold (UNVERIFIED state)."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from importlib import machinery, util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRACKER = ROOT / "scripts" / "ai" / "aq-pm-tracker"
spec = util.spec_from_loader("aq_pm_tracker", machinery.SourceFileLoader("aq_pm_tracker", str(TRACKER)))
mod = util.module_from_spec(spec)
spec.loader.exec_module(mod)

HEAD = "a" * 40
CFG = {"lanes": [{"name": "gemini-antigravity", "pr_numbers": [10, 11], "reason": "test", "since": "2026-10-27"}],
       "clears": {}}
GITLOG_UNTRUSTED = "bbb1111 feat(x): build widget (#10)\nccc2222 docs: unrelated (#3)\n"
GITLOG_TRUSTED_LATER = "ddd3333 fix(x): widget hardening (#50)\n" + GITLOG_UNTRUSTED
ITEM = {"id": "w1", "name": "Widget", "detection": {"commit_match": ["build widget"]},
        "acceptance": {"status": "accepted", "by": "hyperd", "date": "2026-10-06"}}


def write_cfg(d: Path, cfg) -> Path:
    p = d / "cfg.json"
    p.write_text(cfg if isinstance(cfg, str) else json.dumps(cfg))
    return p


def make_receipt(repo: Path, reviewer: str, created: str, verdict="PASS") -> str:
    out = repo / "out.md"
    out.write_text(f"reviewed {HEAD}\nReview-Disposition: {verdict}\n")
    (repo / ".agents/delegation").mkdir(parents=True)
    (repo / ".agents/delegation/registry.jsonl").write_text(json.dumps(
        {"id": "run1", "status": "done", "role": "reviewer", "agent": reviewer, "output_file": "out.md"}) + "\n")
    rec = {"schema": 1, "pr": 10, "reviewed_head_sha": HEAD, "run_id": "run1", "reviewer_lane": reviewer,
           "author_lane": "gemini-antigravity", "verdict": verdict, "output_file": "out.md",
           "output_sha256": hashlib.sha256(out.read_bytes()).hexdigest(), "created_at": created}
    (repo / "receipt.json").write_text(json.dumps(rec))
    return "receipt.json"


def test_all():
    with tempfile.TemporaryDirectory() as t:
        d = Path(t)
        cfg, errs = mod.load_untrusted(write_cfg(d, CFG))
        assert cfg and not errs, errs

        # 1. only-untrusted evidence -> UNVERIFIED, not SHIPPED
        st, pct, hold = mod.project_item_full(ITEM, GITLOG_UNTRUSTED, "", "complete", cfg)
        assert st == "UNVERIFIED" and pct == 40 and hold["prs"] == [10], (st, pct, hold)

        # 2. untrusted then LATER trusted commit (log is newest-first) -> cleared, normal projection
        st, pct, hold = mod.project_item_full(ITEM, "ddd3333 fix: build widget hardening (#50)\n" + GITLOG_UNTRUSTED,
                                              "", "complete", cfg)
        assert st == "SHIPPED" and hold is None, (st, hold)

        # 2a. OLDER trusted + NEWER untrusted -> still held
        older_trusted = "bbb1111 feat(x): build widget (#10)\neee4444 feat(x): build widget v1 (#40)\n"
        st, _, hold = mod.project_item_full(ITEM, older_trusted, "", "complete", cfg)
        assert st == "UNVERIFIED" and hold["prs"] == [10], (st, hold)

        # 2b. no hold config -> normal projection (hold simply not applied)
        assert mod.project_item_full(ITEM, GITLOG_UNTRUSTED, "", "complete", None)[0] == "SHIPPED"

        # 3. valid receipt from an independent reviewer dated after the hold -> cleared
        repo = d / "repo"
        repo.mkdir()
        rel = make_receipt(repo, "codex", "2026-10-28T00:00:00Z")
        old_repo, mod.REPO = mod.REPO, repo
        try:
            item = {**ITEM, "acceptance": {**ITEM["acceptance"], "review_receipt": rel}}
            st, _, hold = mod.project_item_full(item, GITLOG_UNTRUSTED, "", "complete", cfg)
            assert st == "SHIPPED" and hold is None, (st, hold)
            # receipt predating the hold does not clear
            repo2 = d / "repo2"
            repo2.mkdir()
            mod.REPO = repo2
            rel2 = make_receipt(repo2, "codex", "2026-10-01T00:00:00Z")
            item2 = {**ITEM, "acceptance": {**ITEM["acceptance"], "review_receipt": rel2}}
            assert mod.project_item_full(item2, GITLOG_UNTRUSTED, "", "complete", cfg)[0] == "UNVERIFIED"
            # receipt by the untrusted lane itself does not clear
            repo3 = d / "repo3"
            repo3.mkdir()
            mod.REPO = repo3
            rel3 = make_receipt(repo3, "antigravity", "2026-10-28T00:00:00Z")
            item3 = {**ITEM, "acceptance": {**ITEM["acceptance"], "review_receipt": rel3}}
            assert mod.project_item_full(item3, GITLOG_UNTRUSTED, "", "complete", cfg)[0] == "UNVERIFIED"
            # tampered receipt (output hash mismatch) does not clear
            (repo / "out.md").write_text("tampered\n")
            assert mod.project_item_full(item, GITLOG_UNTRUSTED, "", "complete", cfg)[0] == "UNVERIFIED"
        finally:
            mod.REPO = old_repo

        # 4. malformed / missing config -> --check fails; plain projection still renders
        plan = d / "plan"
        plan.mkdir()
        (plan / "tracker.json").write_text(json.dumps({
            "plan": {"id": "p", "title": "P"}, "phases": [{"id": "a", "name": "A"}],
            "items": [{"id": "w1", "name": "W", "phase": "a", "goal": "g", "validation_goal": "v",
                       "detection": {"commit_match": ["zzz-never-matches-zzz"]}}]}))
        bad = write_cfg(d, '{"lanes": [{"name": "x", "pr_numbers": ["a"]}]}')
        for cfgpath in (bad, d / "missing.json"):
            env = {**os.environ, "AQ_PM_UNTRUSTED_CONFIG": str(cfgpath)}
            r = subprocess.run([sys.executable, str(TRACKER), str(plan), "--check"], capture_output=True, text=True, env=env)
            assert r.returncode == 1 and "FAIL" in r.stdout, (r.returncode, r.stdout, r.stderr)
            r = subprocess.run([sys.executable, str(TRACKER), str(plan)], capture_output=True, text=True, env=env)
            assert r.returncode == 0 and "WARNING" in r.stderr, (r.returncode, r.stderr)
        good = write_cfg(d, CFG)
        env = {**os.environ, "AQ_PM_UNTRUSTED_CONFIG": str(good)}
        r = subprocess.run([sys.executable, str(TRACKER), str(plan), "--check"], capture_output=True, text=True, env=env)
        assert r.returncode == 0, (r.stdout, r.stderr)

        # 5. the committed config is itself valid
        c, e = mod.load_untrusted(ROOT / "config" / "pm-tracker-untrusted-provenance.json")
        assert c and not e and 590 in c["prs"] and 585 in c["prs"], e


if __name__ == "__main__":
    test_all()
    print("PASS: pm-tracker untrusted-author hold")
