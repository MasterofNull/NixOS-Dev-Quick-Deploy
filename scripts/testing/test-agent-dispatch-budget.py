#!/usr/bin/env python3
"""Unit tests for agent_dispatch_budget — external-dispatch rate/budget gate."""
import json
import sys
import tempfile
from datetime import datetime, timezone
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
mod = SourceFileLoader(
    "agent_dispatch_budget", str(ROOT / "scripts" / "ai" / "lib" / "agent_dispatch_budget.py")
).load_module()

NOW = datetime(2026, 7, 6, 12, 0, 0, tzinfo=timezone.utc).timestamp()

POLICY = {
    "global": {"enabled": True, "fail_open": True, "enforcement": "block",
               "bypass_env": "A2A_BUDGET_BYPASS", "window_seconds": 300, "max_dispatches": 5},
    "agents": {
        "codex": {"window_seconds": 300, "max_dispatches": 3},
        "gemini": {"window_seconds": 300, "max_dispatches": 3},
        "antigravity": {"window_seconds": 300, "max_dispatches": 3},
    },
}


def _fail(m):
    print(f"FAIL: {m}"); sys.exit(1)


def _registry(entries):
    """entries: list of (agent, seconds_ago). Returns a temp registry path."""
    p = Path(tempfile.mkdtemp()) / "registry.jsonl"
    with open(p, "w") as fh:
        for agent, ago in entries:
            ts = datetime.fromtimestamp(NOW - ago, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            fh.write(json.dumps({"agent": agent, "created": ts}) + "\n")
    return str(p)


def test_within_budget():
    reg = _registry([("codex", 10), ("codex", 20)])  # 2 < 3
    r = mod.check("codex", registry_path=reg, policy=POLICY, now=NOW)
    if not r["ok"] or r["decision"] != "ALLOW":
        _fail(f"2/3 should ALLOW: {r}")
    print("PASS  under agent cap -> ALLOW")


def test_agent_cap_blocks():
    reg = _registry([("codex", 5), ("codex", 15), ("codex", 25)])  # 3 >= 3
    r = mod.check("codex", registry_path=reg, policy=POLICY, now=NOW)
    if r["ok"] or "agent 'codex'" not in r["reason"]:
        _fail(f"3/3 should BLOCK: {r}")
    print("PASS  agent cap reached -> BLOCK")


def test_window_expiry():
    # 3 codex dispatches but all older than the 300s window -> not counted
    reg = _registry([("codex", 400), ("codex", 500), ("codex", 600)])
    r = mod.check("codex", registry_path=reg, policy=POLICY, now=NOW)
    if not r["ok"] or r["agent_count"] != 0:
        _fail(f"expired dispatches should not count: {r}")
    print("PASS  dispatches outside window -> not counted")


def test_global_cap_blocks():
    # under each agent cap (2 each) but 6 total >= global 5
    reg = _registry([("codex", 5), ("codex", 6), ("gemini", 7), ("gemini", 8),
                     ("antigravity", 9), ("antigravity", 10)])
    r = mod.check("codex", registry_path=reg, policy=POLICY, now=NOW)
    if r["ok"] or "all external agents" not in r["reason"]:
        _fail(f"global cap should BLOCK: {r}")
    print("PASS  global cap reached -> BLOCK")


def test_warn_mode_allows():
    pol = json.loads(json.dumps(POLICY))
    pol["global"]["enforcement"] = "warn"
    reg = _registry([("codex", 5), ("codex", 15), ("codex", 25)])  # over cap
    r = mod.check("codex", registry_path=reg, policy=pol, now=NOW)
    if not r["ok"] or r["decision"] != "WARN":
        _fail(f"warn mode should ALLOW+WARN: {r}")
    print("PASS  enforcement=warn over cap -> WARN (allowed)")


def test_disabled_allows():
    pol = json.loads(json.dumps(POLICY))
    pol["global"]["enabled"] = False
    reg = _registry([("codex", 5), ("codex", 15), ("codex", 25)])
    r = mod.check("codex", registry_path=reg, policy=pol, now=NOW)
    if not r["ok"] or r["decision"] != "ALLOW":
        _fail(f"disabled should ALLOW: {r}")
    print("PASS  budget disabled -> ALLOW")


def test_missing_registry_fail_open():
    r = mod.check("codex", registry_path="/nonexistent/registry.jsonl", policy=POLICY, now=NOW)
    if not r["ok"]:
        _fail(f"missing registry should fail-open ALLOW: {r}")
    print("PASS  missing registry -> fail-open ALLOW")


def test_local_agents_not_charged():
    # local-* dispatches must not count toward the external global cap
    reg = _registry([("local-direct", 5)] * 10 + [("codex", 6)])
    r = mod.check("codex", registry_path=reg, policy=POLICY, now=NOW)
    if not r["ok"] or r["global_count"] != 1:
        _fail(f"local agents should not be charged to external budget: {r}")
    print("PASS  local-* dispatches not charged to external budget")


if __name__ == "__main__":
    test_within_budget()
    test_agent_cap_blocks()
    test_window_expiry()
    test_global_cap_blocks()
    test_warn_mode_allows()
    test_disabled_allows()
    test_missing_registry_fail_open()
    test_local_agents_not_charged()
    print("\n8/8 agent-dispatch-budget tests passed")
