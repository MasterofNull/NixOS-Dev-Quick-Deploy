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


def make_receipt(repo: Path, reviewer: str, created: str, verdict="PASS", pr: int = 50) -> str:
    out = repo / "out.md"
    out.write_text(f"reviewed {HEAD}\nReview-Disposition: {verdict}\n")
    (repo / ".agents/delegation").mkdir(parents=True)
    (repo / ".agents/delegation/registry.jsonl").write_text(json.dumps(
        {"id": "run1", "status": "done", "role": "reviewer", "agent": reviewer, "output_file": "out.md"}) + "\n")
    rec = {"schema": 1, "pr": pr, "reviewed_head_sha": HEAD, "run_id": "run1", "reviewer_lane": reviewer,
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
        st, pct, h = mod.project_item_full(ITEM, GITLOG_UNTRUSTED, "", "complete", None)
        assert st == "UNKNOWN" and pct is None and h["degraded"], (st, pct, h)

        # 3. valid receipt from an independent reviewer dated after the hold -> cleared
        repo = d / "repo"
        repo.mkdir()
        rel = make_receipt(repo, "codex", "2026-10-28T00:00:00Z")
        old_repo, mod.REPO = mod.REPO, repo
        old_env = os.environ.get("AQ_DELEGATION_DIR")
        old_cf = mod._commit_files
        mod._commit_files = lambda c: {".agents/plans/p/tracker.json"} if c == "eee4444" else set()
        os.environ["AQ_DELEGATION_DIR"] = str(repo / ".agents/delegation")
        # receipt PR #50 is a trusted PR whose commit matches the item's detection (older than the untrusted one)
        BOUND_LOG = GITLOG_UNTRUSTED + "eee4444 feat(x): build widget v1 (#50)\n"
        try:
            item = {**ITEM, "acceptance": {**ITEM["acceptance"], "review_receipt": rel}}
            st, _, hold = mod.project_item_full(item, BOUND_LOG, "", "complete", cfg, "p")
            assert st == "SHIPPED" and hold is None, (st, hold)
            # unrelated valid receipt (its PR commit does not match this item) does not clear
            assert mod.project_item_full(item, GITLOG_UNTRUSTED + "eee4444 feat(y): other thing (#50)\n",
                                         "", "complete", cfg, "p")[0] == "UNVERIFIED"
            assert mod.project_item_full(item, GITLOG_UNTRUSTED, "", "complete", cfg, "p")[0] == "UNVERIFIED"
            # bound PR commit that does not touch the item's tracker does not clear
            mod._commit_files = lambda c: {"docs/other.md"}
            assert mod.project_item_full(item, BOUND_LOG, "", "complete", cfg, "p")[0] == "UNVERIFIED"
            mod._commit_files = lambda c: {".agents/plans/p/tracker.json"} if c == "eee4444" else set()
            # receipt for an untrusted PR never binds
            # malformed date does not clear
            rm = json.loads((repo / "receipt.json").read_text())
            for bad_date in ("not-a-date", "2026-13-45T00:00:00Z", ""):
                (repo / "receipt.json").write_text(json.dumps({**rm, "created_at": bad_date}))
                assert mod.project_item_full(item, BOUND_LOG, "", "complete", cfg, "p")[0] == "UNVERIFIED", bad_date
            (repo / "receipt.json").write_text(json.dumps(rm))
            # config `clears` naming this exact plan/item clears without PR binding; wrong key does not
            cfg_cl = {**cfg, "clears": {"p/w1": "receipt.json"}}
            plain = {**ITEM}
            assert mod.project_item_full(plain, BOUND_LOG, "", "complete", cfg_cl, "p")[0] == "SHIPPED"
            # unbound `clears` receipt (its PR commit matches nothing for this item) is rejected
            assert mod.project_item_full(plain, GITLOG_UNTRUSTED, "", "complete", cfg_cl, "p")[0] == "UNVERIFIED"
            assert mod.project_item_full(plain, BOUND_LOG, "", "complete", cfg_cl, "q")[0] == "UNVERIFIED"
            # receipt predating the hold does not clear
            repo2 = d / "repo2"
            repo2.mkdir()
            mod.REPO = repo2
            os.environ["AQ_DELEGATION_DIR"] = str(repo2 / ".agents/delegation")
            rel2 = make_receipt(repo2, "codex", "2026-10-01T00:00:00Z")
            item2 = {**ITEM, "acceptance": {**ITEM["acceptance"], "review_receipt": rel2}}
            assert mod.project_item_full(item2, BOUND_LOG, "", "complete", cfg, "p")[0] == "UNVERIFIED"
            # receipt by the untrusted lane itself does not clear
            repo3 = d / "repo3"
            repo3.mkdir()
            mod.REPO = repo3
            os.environ["AQ_DELEGATION_DIR"] = str(repo3 / ".agents/delegation")
            rel3 = make_receipt(repo3, "antigravity", "2026-10-28T00:00:00Z")
            item3 = {**ITEM, "acceptance": {**ITEM["acceptance"], "review_receipt": rel3}}
            assert mod.project_item_full(item3, BOUND_LOG, "", "complete", cfg, "p")[0] == "UNVERIFIED"
            # tampered receipt (output hash mismatch) does not clear
            os.environ["AQ_DELEGATION_DIR"] = str(repo / ".agents/delegation")
            (repo / "out.md").write_text("tampered\n")
            assert mod.project_item_full(item, BOUND_LOG, "", "complete", cfg, "p")[0] == "UNVERIFIED"
        finally:
            mod.REPO = old_repo
            mod._commit_files = old_cf
            if old_env is None:
                os.environ.pop("AQ_DELEGATION_DIR", None)
            else:
                os.environ["AQ_DELEGATION_DIR"] = old_env

        # 3a. systemd/command items are NOT exempt when a matching commit is untrusted
        for det in ({"systemd_unit": "x.service"}, {"command": "sh"}):
            it = {**ITEM, "detection": {**det, "commit_match": ["build widget"]}}
            real = mod.project_item
            mod.project_item = lambda *a, **k: ("SHIPPED", 100)
            try:
                st, _, h = mod.project_item_full(it, GITLOG_UNTRUSTED, "", "complete", cfg)
            finally:
                mod.project_item = real
            assert st == "UNVERIFIED" and h["prs"] == [10], (det, st, h)

        # 3b. frozen `items` list: detection edited away from the untrusted commit -> still held;
        # unlisted with same edit -> not held (proves the list is what holds it)
        cfg_items = {**CFG, "items": {"p/w1": {"commit_match": ["build widget"]}}}
        cfgl, e = mod.load_untrusted(write_cfg(d, cfg_items))
        assert cfgl and not e, e
        edited = {**ITEM, "detection": {"commit_match": ["zzz-no-match"]}, "acceptance": {"status": "accepted", "by": "hyperd"}}
        assert mod.project_item_full(edited, GITLOG_UNTRUSTED, "", "complete", cfgl, "p")[0] == "UNVERIFIED"
        assert mod.project_item_full(edited, GITLOG_UNTRUSTED, "", "complete", cfgl, "other")[0] == "SHIPPED"
        # listed item is not cleared by a merely newer trusted commit (receipt only)
        assert mod.project_item_full(ITEM, GITLOG_TRUSTED_LATER.replace("widget hardening", "build widget hardening"),
                                     "", "complete", cfgl, "p")[0] == "UNVERIFIED"
        # detection edited to match an UNRELATED trusted PR (touching the tracker) with a valid receipt for it:
        # binding uses the frozen patterns, so the item stays held
        mod._commit_files = lambda c: {".agents/plans/p/tracker.json"}
        edited2 = {**ITEM, "detection": {"commit_match": ["unrelated thing"]}}
        log2 = GITLOG_UNTRUSTED + "eee4444 feat(y): unrelated thing (#50)\n"
        mod.REPO = repo
        os.environ["AQ_DELEGATION_DIR"] = str(repo / ".agents/delegation")
        (repo / "out.md").write_text(f"reviewed {HEAD}\nReview-Disposition: PASS\n")
        rec = json.loads((repo / "receipt.json").read_text())
        rec["output_sha256"] = hashlib.sha256((repo / "out.md").read_bytes()).hexdigest()
        (repo / "receipt.json").write_text(json.dumps(rec))
        edited2["acceptance"] = {"status": "accepted", "by": "hyperd", "review_receipt": "receipt.json"}
        try:
            assert mod.project_item_full(edited2, log2, "", "complete", cfgl, "p")[0] == "UNVERIFIED"
        finally:
            mod.REPO = old_repo
            mod._commit_files = old_cf
            os.environ.pop("AQ_DELEGATION_DIR", None)
        # direct (no `(#N)`) commit newer than the untrusted one does not clear an unlisted item
        direct = "fff9999 fix: build widget direct\n" + GITLOG_UNTRUSTED
        assert mod.project_item_full(ITEM, direct, "", "complete", cfg)[0] == "UNVERIFIED"
        # malformed items list / dates fail config load
        for badcfg in ({**CFG, "items": {"noslash": {"commit_match": []}}}, {**CFG, "items": ["p/w1"]},
                       {"lanes": [{**CFG["lanes"][0], "since": "2026-13-45"}]}):
            c2, e2 = mod.load_untrusted(write_cfg(d, badcfg))
            assert c2 is None and e2, badcfg

        # 3c. removing a listed item without a cleared hold -> --check-untrusted-items fails
        import contextlib
        import io
        tr_repo = d / "tr"
        (tr_repo / ".agents/plans/p").mkdir(parents=True)
        (tr_repo / ".agents/plans/p/tracker.json").write_text(json.dumps({"items": [ITEM]}))
        base_text = json.dumps({**CFG, "items": {"p/w1": {"commit_match": ["build widget"]}}})
        stale_text = json.dumps(CFG)  # pre-freeze config, no items
        class R:  # minimal CompletedProcess stand-in; no real git is touched
            def __init__(self, rc=0, out=""):
                self.returncode, self.stdout, self.stderr = rc, out, ""
        def fake_git(*a):
            if a[0] == "rev-parse":
                return R()
            if a[0] == "merge-base":
                return R(0, "base\n")
            if a[0] == "ls-tree":
                return R(0, "100644 blob x\tf\n")
            if a[0] == "show":
                return R(0, stale_text if a[1].startswith("base:") else base_text)
            return R(1)
        old = (mod.REPO, mod.UNTRUSTED_CONFIG, mod._git_log)
        mod.REPO = tr_repo
        mod.UNTRUSTED_CONFIG = tr_repo / "config" / "pm-tracker-untrusted-provenance.json"
        mod.UNTRUSTED_CONFIG.parent.mkdir()
        mod.UNTRUSTED_CONFIG.write_text(json.dumps({**CFG, "items": {}}))
        mod._git_log = lambda: (GITLOG_UNTRUSTED, "complete")
        try:
            with contextlib.redirect_stdout(io.StringIO()) as out:
                rc = mod.check_untrusted_items(fake_git)
            assert rc == 1 and "not cleared" in out.getvalue(), out.getvalue()
            # keeping the entry (or adding) passes
            mod.UNTRUSTED_CONFIG.write_text(json.dumps({**CFG, "items": {"p/w1": {"commit_match": ["build widget"]}, "p/w2": {"commit_match": ["x"]}}}))
            with contextlib.redirect_stdout(io.StringIO()) as out:
                assert mod.check_untrusted_items(fake_git) == 0, out.getvalue()
        finally:
            mod.REPO, mod.UNTRUSTED_CONFIG, mod._git_log = old

        # 4. malformed / missing config -> --check fails; plain projection still renders
        plan = d / "plan"
        plan.mkdir()
        (plan / "tracker.json").write_text(json.dumps({
            "plan": {"id": "p", "title": "P"}, "phases": [{"id": "a", "name": "A"}],
            "items": [{"id": "w1", "name": "W", "phase": "a", "goal": "g", "validation_goal": "v",
                       "detection": {"commit_match": ["zzz-never-matches-zzz"]}}]}))
        bad = write_cfg(d, '{"lanes": [{"name": "x", "pr_numbers": ["a"]}]}')
        for cfgpath in (bad, d / "missing.json"):
            env = {**{k: v for k, v in os.environ.items() if not k.startswith("GIT_")}, "AQ_PM_UNTRUSTED_CONFIG": str(cfgpath)}
            r = subprocess.run([sys.executable, str(TRACKER), str(plan), "--check"], capture_output=True, text=True, env=env)
            assert r.returncode == 1 and "FAIL" in r.stdout, (r.returncode, r.stdout, r.stderr)
            r = subprocess.run([sys.executable, str(TRACKER), str(plan)], capture_output=True, text=True, env=env)
            assert r.returncode == 0 and "WARNING" in r.stderr and "DEGRADED" in r.stdout, (r.returncode, r.stderr)
            r = subprocess.run([sys.executable, str(TRACKER), str(plan), "--json"], capture_output=True, text=True, env=env)
            assert json.loads(r.stdout)["hold_degraded"] is True and json.loads(r.stdout)["rollup_authoritative"] is False
        good = write_cfg(d, CFG)
        env = {**{k: v for k, v in os.environ.items() if not k.startswith("GIT_")}, "AQ_PM_UNTRUSTED_CONFIG": str(good)}
        r = subprocess.run([sys.executable, str(TRACKER), str(plan), "--check"], capture_output=True, text=True, env=env)
        assert r.returncode == 0, (r.stdout, r.stderr)

        # 5. the committed config is itself valid
        c, e = mod.load_untrusted(ROOT / "config" / "pm-tracker-untrusted-provenance.json")
        assert c and not e and 590 in c["prs"] and 585 in c["prs"], e


if __name__ == "__main__":
    test_all()
    print("PASS: pm-tracker untrusted-author hold")
