#!/usr/bin/env python3
"""FT-6 risk classifier (report-only). classify(paths, diff_stats) -> {tier, reasons, policy}.

Composes on PRSI: the low/medium/high baseline comes from prsi-orchestrator.py `_risk_tier()`
(loaded by file path -- the name has a hyphen, so it cannot be a normal import; falls back to the
same mapping when unloadable). `core` is the extra top tier above PRSI's vocabulary. The PRSI
high-risk rubric checklist is attached to high/core policies. Tier never self-lowers: callers
passing a claimed tier get max(claimed, computed).
"""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
POLICY_PATH = ROOT / "config/factory/risk-tier-policy.json"
PRSI_PATH = ROOT / "scripts/automation/prsi-orchestrator.py"


def load_policy(path: Path = POLICY_PATH) -> dict:
    return json.loads(Path(path).read_text())


def _prsi_baseline(kind: str) -> str:
    """kind: low-class -> safe knowledge action, medium -> safe routing action, high -> unsafe."""
    action = {"low": {"safe": True, "type": "knowledge"},
              "medium": {"safe": True, "type": "routing"},
              "high": {"safe": False}}[kind]
    try:
        spec = importlib.util.spec_from_file_location("_prsi_orch", PRSI_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod._risk_tier(action)
    except Exception:
        return kind  # identical to PRSI's mapping above


def _any(patterns, path):
    return any(re.search(p, path) for p in patterns)


def _max_tier(order, *tiers):
    return max(tiers, key=order.index)


def classify(paths, diff_stats=None, claimed=None, policy=None) -> dict:
    pol = policy or load_policy()
    order = pol["tier_order"]
    rules = pol["rules"]
    reasons, kinds, tags = [], set(), set()
    paths = [p for p in (paths or []) if p]
    for p in paths:
        if _any(rules["core"]["patterns"], p):
            kinds.add("core"); tags.add("core-piece"); reasons.append(f"core-piece: {p}")
            continue
        hit = [t for t, pats in rules["high"].items() if _any(pats, p)]
        if hit:
            kinds.add("high"); tags.update(hit); reasons.append(f"{'+'.join(sorted(hit))}: {p}")
        elif _any(rules["low"]["patterns"], p):
            kinds.add("low")
        else:
            kinds.add("medium"); reasons.append(f"code/config: {p}")
    if "core" in kinds:
        tier = "core"
    elif "high" in kinds:
        tier = _prsi_baseline("high")
    elif "medium" in kinds:
        tier = _prsi_baseline("medium")
    else:
        tier = _prsi_baseline("low")
    stats = diff_stats or {}
    esc = pol["diff_escalation"]
    changed = int(stats.get("added", 0)) + int(stats.get("deleted", 0))
    if tier in ("low", "medium") and (changed >= esc["changed_lines"] or int(stats.get("files", len(paths))) >= esc["files"]):
        tier = order[order.index(tier) + 1]
        reasons.append(f"diff size escalation ({changed} lines)")
    if claimed:
        if claimed not in order:
            reasons.append(f"ignored unknown claimed tier {claimed!r}")
        elif order.index(claimed) > order.index(tier):
            tier = claimed
            reasons.append(f"claimed tier {claimed} kept (higher than computed)")
        elif order.index(claimed) < order.index(tier):
            reasons.append(f"claimed tier {claimed} rejected: never self-lowered")
    policy_out = dict(pol["tiers"][tier])
    if tier in pol.get("rubric_tiers", []):
        try:
            policy_out["rubric_checklist"] = json.loads((ROOT / pol["rubric"]).read_text()).get("required_checklist", [])
        except Exception:
            policy_out["rubric_checklist"] = []
    return {"tier": tier, "tags": sorted(tags), "reasons": reasons, "policy": policy_out,
            "mode": pol.get("mode", "report-only")}
