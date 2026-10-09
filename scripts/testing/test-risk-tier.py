#!/usr/bin/env python3
"""FT-6 tests: risk classifier tiers, never-self-lower, policy lookup."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ai" / "lib"))
import risk_tier as rt  # noqa: E402

def t(paths, **kw):
    return rt.classify(paths, **kw)

assert t(["docs/README.md"])["tier"] == "low"
assert t(["scripts/ai/some_tool.py"])["tier"] == "medium"
r = t(["nix/modules/roles/ai-stack.nix"])
assert r["tier"] == "high" and "stability" in r["tags"], r
assert t(["config/sops/secrets.yaml"])["tier"] == "high"
assert t(["ai-stack/mcp-servers/hybrid-coordinator/rsi_lifecycle.py"])["tier"] == "core"
assert t(["scripts/governance/tier0-validation-gate.sh"])["tier"] == "core"
assert t(["docs/a.md", ".githooks/pre-commit"])["tier"] == "core"  # max wins
# never self-lower; higher claim kept; unknown claim ignored
r = t(["nix/x.nix"], claimed="low")
assert r["tier"] == "high" and any("never self-lowered" in x for x in r["reasons"]), r
assert t(["docs/a.md"], claimed="core")["tier"] == "core"
assert t(["docs/a.md"], claimed="UNCLASSIFIED")["tier"] == "low"
# diff size escalates but never lowers
assert t(["docs/a.md"], diff_stats={"added": 500, "deleted": 0})["tier"] == "medium"
# policy lookup
core = t([".githooks/pre-commit"])["policy"]
assert core["min_reviewers"] == 2 and core["independent_reviewer_required"] and core["lock"] == "hash-bound"
assert "independent_verifier_signed" in core["rubric_checklist"]
low = t(["docs/a.md"])["policy"]
assert low["lock"] == "none" and low["min_reviewers"] == 0 and "rubric_checklist" not in low
assert t(["nix/x.nix"])["policy"]["lock"] == "freeze"
print("PASS")
