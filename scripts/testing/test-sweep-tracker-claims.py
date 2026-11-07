#!/usr/bin/env python3
"""Offline test for sweep-tracker-claims: each finding class fires on a fixture, a clean item stays clean."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SWEEP = ROOT / "scripts" / "governance" / "sweep-tracker-claims.py"
PROJECTOR = ROOT / "scripts" / "ai" / "aq-pm-tracker"


def w(base, rel, text):
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text if isinstance(text, str) else json.dumps(text))


def item(iid, det, **extra):
    return {"id": iid, "name": iid, "phase": "p", "kind": "slice", "goal": "g", "validation_goal": "v",
            "deps": [], "detection": det, **extra}


def tracker(pid, items):
    return {"plan": {"id": pid, "title": pid}, "phases": [{"id": "p", "name": "p", "goal": "g", "order": 1}], "items": items}


def build(base):
    w(base, "scripts/testing/test-clean.py", "pass\n")
    w(base, "scripts/testing/test-orphan.py", "pass\n")
    w(base, "live/wired.sh", "run clean-widget\n")
    w(base, "live/other.sh", "nothing\n")
    w(base, "config/ci-checks.json", {"checks": [{"id": "c", "cmd": "scripts/testing/test-clean.py"}]})
    w(base, ".agents/plans/widget-clean/tracker.json", tracker("widget-clean", [
        item("clean", {"commit_match": ["build clean widget"], "wired_caller": {"file": "live/wired.sh", "pattern": "clean-widget"},
                       "tests": ["scripts/testing/test-clean.py"]})]))
    w(base, ".agents/plans/widget-claims/tracker.json", tracker("widget-claims", [
        item("noco", {"commit_match": ["zzz never committed"]}, editorial_note="SHIPPED and merged to main"),
        item("typed", {"commit_match": ["build clean widget"]}, status="SHIPPED"),
        item("orphan", {"commit_match": ["build clean widget"], "tests": ["scripts/testing/test-orphan.py"]}),
        item("dorm", {"commit_match": ["build clean widget"], "wired_caller": {"file": "live/other.sh", "pattern": "dorm-feature"}})]))
    w(base, ".agents/plans/herdr-demo/tracker.json", tracker("herdr-demo", [
        item("h0-intake", {"commit_match": ["build clean widget"]}, acceptance={"status": "accepted", "by": "o", "date": "2026-01-01", "note": ""}),
        item("h3-run", {"commit_match": ["build clean widget"]}, status="SHIPPED")]))
    w(base, "nix/home/herdr.nix", "{ config, ... }: let cfg = config.programs.aqHerdr; in {\n"
       "  config.assertions = [{ assertion = !cfg.runtimeEnable; message = \"off\"; }];\n}\n")
    w(base, "config/agent-capability-intake-candidates.json", {"candidates": [
        {"id": "herdr-mux", "state": "proposed", "review_status": "incomplete"}]})
    w(base, "nix/mod.nix", "{ options.services.aiGhost.enable = mkEnableOption \"x\"; services.aiLive.enable = true; }\n")
    w(base, "config/activation-manifest.json", {"features": [
        {"feature": "ghost", "entrypoint": "live/ghost", "live_caller": "live/wired.sh", "enable": "services.aiGhost.enable"},
        {"feature": "stale", "entrypoint": "live/clean-widget", "live_caller": "live/wired.sh", "enable": "services.aiLive.enable",
         "deferral": {"date": "2026-01-01", "reason": "r"}}]})
    for a in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "feat: build clean widget"]):
        subprocess.run(["git", "-C", str(base), *a], check=True, capture_output=True)


def run(base, *extra):
    return subprocess.run([sys.executable, str(SWEEP), "--repo", str(base), "--ref", "HEAD", "--projector", str(PROJECTOR),
                           *extra], capture_output=True, text=True)


def main():
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        build(base)
        r = run(base, "--json")
        assert r.returncode == 0, ("report-only mode must exit 0", r.stderr)
        res = json.loads(r.stdout)
        got = {(f["class"], f["plan"], f["item"]) for f in res["findings"]}
        want = {
            ("CLAIM_NO_CODE", "widget-claims", "noco"),
            ("HAND_TYPED_STATUS", "widget-claims", "typed"),
            ("DORMANT", "widget-claims", "dorm"),
            ("SHIPPED_NOT_ACTIVE", "herdr-demo", "h3-run"),
            ("STALE_RECORD", "herdr-demo", "h0-intake"),
            ("DORMANT", None, "ghost"),
            ("STALE_RECORD", None, "stale"),
        }
        assert want <= got, ("missing findings", sorted(want - got, key=str))
        assert not [g for g in got if g[1] == "widget-clean"], ("clean item flagged", got)
        ev = next(f["evidence"] for f in res["findings"] if f["class"] == "SHIPPED_NOT_ACTIVE" and f["item"] == "h3-run")
        assert "stays false" in ev, ev
        rec = next(i for i in res["items"] if i["item"] == "clean")
        assert (rec["code_on_main"], rec["wired"], rec["tested"]) == ("yes", "yes", "yes"), rec
        orphan = next(i for i in res["items"] if i["item"] == "orphan")
        assert orphan["tested"] == "no" and "not in ci-checks.json" in orphan["evidence"]["tested"], orphan
        assert rec["enabled"] == "unknown" and rec["observable"] == "unknown", "undeterminable must stay unknown"
        assert run(base, "--fail-on", "DORMANT").returncode == 1
        assert run(base, "--fail-on", "CLAIM_NO_CODE,STALE_RECORD").returncode == 1
        assert run(base, "--fail-on", "BOGUS").returncode == 2
        rep = base / "report.md"
        assert run(base, "--report", str(rep)).returncode == 0 and "| CLAIM_NO_CODE | 1 |" in rep.read_text()
        # a repo with only the clean plan has nothing to fail on
        for p in ("widget-claims", "herdr-demo"):
            (base / ".agents/plans" / p / "tracker.json").unlink()
        for rel in ("config/activation-manifest.json", "nix/home/herdr.nix"):
            (base / rel).unlink()
        clean = json.loads(run(base, "--json", "--fail-on", "CLAIM_NO_CODE,SHIPPED_NOT_ACTIVE,DORMANT,STALE_RECORD,HAND_TYPED_STATUS").stdout)
        assert clean["findings"] == [], clean["findings"]
    print("PASS: sweep-tracker-claims detects each class, keeps unknown as unknown, leaves a clean item unflagged")


if __name__ == "__main__":
    main()
