#!/usr/bin/env python3
"""R1.2 — the training-loop scorer must now PASS the R1.3 trustworthiness gate,
closing the untrustworthy-signal finding (RSI-Readiness R1).

Run: python3 scripts/testing/test-loop-scorer-certified.py
"""

import importlib.machinery
import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "scripts" / "ai" / "lib"))

_l = importlib.machinery.SourceFileLoader("tl", str(REPO / "scripts" / "ai" / "aq-local-training-loop"))
TL = importlib.util.module_from_spec(importlib.util.spec_from_loader("tl", _l))
_l.exec_module(TL)


def test_loop_scorer_is_now_certified():
    certified, reason = TL._certify_scorer()
    assert certified, f"R1.2 goal: loop scorer must pass the gate now — {reason}"
    print(f"PASS loop scorer CERTIFIED trustworthy ({reason})")


def test_scorer_abstains_on_infra_noise():
    import json
    golden = json.loads((REPO / "data" / "golden" / "tasks.json").read_text())
    for noise in ("", "Queued behind busy local inference slot: timeout", "[Error: disk full]"):
        r = TL._score_response(noise, golden[0])
        assert r.get("abstain") and r.get("score") is None, f"must abstain on {noise!r}: {r}"
    print("PASS loop scorer abstains on infra-noise (score=None, not a false 0)")


def test_scorer_discriminates_good_from_bad():
    import json
    golden = json.loads((REPO / "data" / "golden" / "tasks.json").read_text())
    for task in golden:
        g = TL._score_response(task["reference_good"], task)
        b = TL._score_response(task["reference_bad"], task)
        assert (g["score"] or 0) > (b["score"] or 0), f"{task['id']}: good !> bad"
    print("PASS loop scorer ranks good>bad across scoring types")


def test_backward_compat_keyword_cases():
    # An existing eval-pack case (expected_keywords, no 'scoring' field) still scores.
    case = {"id": "legacy", "expected_keywords": ["nixos-rebuild", "switch"]}
    good = TL._score_response("run nixos-rebuild switch to activate", case)
    assert good["score"] == 1.0 and not good["abstain"]
    poor = TL._score_response("just reboot", case)
    assert (poor["score"] or 0) < 0.6
    print("PASS backward-compatible with legacy keyword eval cases")


if __name__ == "__main__":
    test_loop_scorer_is_now_certified()
    test_scorer_abstains_on_infra_noise()
    test_scorer_discriminates_good_from_bad()
    test_backward_compat_keyword_cases()
    print("ALL PASS")
