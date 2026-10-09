#!/usr/bin/env python3
"""ci-7 wiring: inference-bench post-switch hook, aq-eval phase-0 parity, workflow/tool hint rules, audit config."""
import json
import re
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai-stack/mcp-servers/hybrid-coordinator"))
sys.path.insert(0, str(ROOT / "scripts/ai/lib"))


def test_inference_bench_hook():
    hooks = yaml.safe_load((ROOT / "config/training-manifest.yaml").read_text())["post_switch_hooks"]
    hook = next(h for h in hooks if h["id"] == "inference_bench")
    cmd = hook["command"]
    assert "scripts/ai/aq-inference-bench" in cmd and " run " in cmd
    assert "--execute" in cmd and "--backend llama-cpp-local" in cmd, cmd
    assert re.search(r"--timeout-seconds\s+\d+", cmd), "must bound per-request time"
    assert hook["background"] is True and 0 < hook["timeout_s"] <= 600
    assert not re.search(r"\bsudo\b|\brm\b|\bsystemctl\b", cmd), cmd
    bench = ROOT / "scripts/ai/aq-inference-bench"
    assert bench.exists()
    assert "inference-bench-latest.json" in cmd and "TELEMETRY_DIR" in cmd


def test_aq_eval_check_parity():
    p0 = (ROOT / "scripts/testing/harness_qa/phases/phase0.py").read_text()
    sh = (ROOT / "scripts/ai/_aq-qa-bash").read_text()
    ids = lambda t: set(re.findall(r'"(0\.10\.60)"', t))
    assert ids(p0) == ids(sh) == {"0.10.60"}
    assert "_check_aq_eval_static_suites(ctx)" in p0
    assert "aq-eval" in sh.split('"0.10.60"', 1)[1][:400]
    # WARN-class: both harnesses downgrade failure to skip, never fail, for the suite run
    assert 'skipped(1, "0.10.60"' in p0 and '_skip 1 "0.10.60"' in sh


def test_hint_rules_fire():
    from knowledge.static_rules import STATIC_RULES
    from knowledge.token_manager import _tokenize

    def fired(q):
        toks = set(_tokenize(q))
        return {r["id"] for r in STATIC_RULES if any(k in toks for k in r["keywords"])}

    for q in ("break this multi-step migration into phases", "make a plan for the refactor",
              "plan the rollout"):
        assert "use_workflow_blueprints_for_multistep" in fired(q), q
    for q in ("which tool should I use to inspect the unit", "what tools exist for graph lookups"):
        assert "use_tooling_manifest_for_tool_choice" in fired(q), q
    rules = {r["id"]: r for r in STATIC_RULES}
    assert "workflow_blueprints" in rules["use_workflow_blueprints_for_multistep"]["snippet"]
    assert "tooling_manifest" in rules["use_tooling_manifest_for_tool_choice"]["snippet"]
    assert all(k == k.lower() and k.isalnum() for r in rules.values() for k in r["keywords"]
               if r["id"].startswith("use_")), "keywords must be single [a-z0-9] tokens"


def test_aq_prime_points_at_tools():
    t = (ROOT / "scripts/ai/aq-prime").read_text()
    assert "workflow_blueprints" in t and "tooling_manifest" in t


def test_capability_audit_reads_config():
    import capability_audit as ca
    assert ca.artifact_refresh_days(ROOT)[ca.GRAPH_ARTIFACT] == json.loads(
        (ROOT / "config/understand-anything.json").read_text())["staleness"]["max_age_days"]
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "config").mkdir()
        (Path(d) / "config/understand-anything.json").write_text('{"staleness": {"max_age_days": 3}}')
        assert ca.artifact_refresh_days(Path(d))[ca.GRAPH_ARTIFACT] == 3
        (Path(d) / "config/understand-anything.json").write_text("not json")
        assert ca.artifact_refresh_days(Path(d))[ca.GRAPH_ARTIFACT] == 14  # documented fallback
    assert not hasattr(ca, "ARTIFACT_REFRESH_DAYS")


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("PASS: ci-7 wiring (inference-bench hook, aq-eval 0.10.60 parity, hint rules, aq-prime, audit config)")


if __name__ == "__main__":
    main()
