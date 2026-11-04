#!/usr/bin/env python3
"""Offline tests for the aq-pm-tracker activation cap (P0.9): SHIPPED needs activation signal + registered test."""
from importlib import machinery, util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRACKER = ROOT / "scripts" / "ai" / "aq-pm-tracker"
spec = util.spec_from_loader("aq_pm_tracker", machinery.SourceFileLoader("aq_pm_tracker", str(TRACKER)))
mod = util.module_from_spec(spec)
spec.loader.exec_module(mod)

GITLOG = "aaa1111 feat(x): build widget (#3)\n"
ACC = {"status": "accepted", "by": "hyperd", "date": "2026-10-06"}
THIS_TEST = "scripts/testing/test-pm-tracker-activation-cap.py"
WIRED = {"file": "scripts/ai/aq-pm-tracker", "pattern": "def project_item_full"}


def item(**det):
    return {"id": "w1", "name": "Widget", "acceptance": ACC,
            "detection": {"commit_match": ["build widget"], **det}}


def status(it, **kw):
    return mod.project_item_full(it, GITLOG, "complete", {"lanes": [], "clears": {}, "items": {}, "prs": []}, "p", None)[0]


def test_all():
    # baseline: accepted + commit evidence would have been SHIPPED; code only -> BUILT
    assert status(item()) == "BUILT"
    # activation signal + registered test -> SHIPPED
    assert status(item(wired_caller=WIRED, tests=[THIS_TEST])) == "SHIPPED"
    # activation signal without a test -> BUILT
    assert status(item(wired_caller=WIRED)) == "BUILT"
    # test without activation signal -> BUILT
    assert status(item(tests=[THIS_TEST])) == "BUILT"
    # wired caller pattern absent from the file, or test path missing -> BUILT
    assert status(item(wired_caller={**WIRED, "pattern": "NO_SUCH_SYMBOL_xyz"}, tests=[THIS_TEST])) == "BUILT"
    assert status(item(wired_caller=WIRED, tests=["scripts/testing/does-not-exist.py"])) == "BUILT"
    # a stale/verified grant is an activation signal
    assert mod._activation_signal(item(), True) and not mod._activation_signal(item(), False)
    # non-SHIPPED statuses are untouched
    assert status({"id": "d", "name": "D", "detection": {}}) == "DESIGNED"


if __name__ == "__main__":
    test_all()
    print("PASS: test-pm-tracker-activation-cap")
