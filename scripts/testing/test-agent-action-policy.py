#!/usr/bin/env python3
"""Unit tests for agent_action_policy — delegation-boundary mode gate."""
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
mod = SourceFileLoader(
    "agent_action_policy", str(ROOT / "scripts" / "ai" / "lib" / "agent_action_policy.py")
).load_module()

BASE = {
    "global": {"privileged_requires_authorization": False,
               "authorization_env": "A2A_ALLOW_PRIVILEGED", "fail_open": True},
    "agents": {
        "codex": {"allowed_modes": ["safe", "edit"], "privileged_modes": ["edit"],
                  "blocked_modes": []},
        "gemini": {"allowed_modes": ["auto_edit", "yolo"], "privileged_modes": ["yolo"],
                   "blocked_modes": []},
    },
}


def _fail(m):
    print(f"FAIL: {m}"); sys.exit(1)


def _clone(**overrides):
    import copy
    p = copy.deepcopy(BASE)
    for path, val in overrides.items():
        cur = p
        keys = path.split(".")
        for k in keys[:-1]:
            cur = cur[k]
        cur[keys[-1]] = val
    return p


def test_safe_mode_allowed():
    r = mod.evaluate("codex", "safe", policy=BASE)
    if not r["ok"] or r["privileged"]:
        _fail(f"safe should be allowed non-privileged: {r}")
    print("PASS  codex safe -> ALLOW (non-privileged)")


def test_privileged_allowed_by_default():
    # default posture: privileged allowed (+audited), automation not broken
    r = mod.evaluate("codex", "edit", policy=BASE)
    if not r["ok"] or not r["privileged"]:
        _fail(f"edit should be allowed+privileged by default: {r}")
    print("PASS  codex edit -> ALLOW+privileged (default posture)")


def test_invalid_mode_blocked():
    r = mod.evaluate("codex", "rm-rf", policy=BASE)
    if r["ok"] or "not in" not in r["reason"]:
        _fail(f"unknown mode should BLOCK: {r}")
    print("PASS  codex bogus mode -> BLOCK (not in allowed_modes)")


def test_kill_switch():
    pol = _clone(**{"agents.gemini.blocked_modes": ["yolo"]})
    r = mod.evaluate("gemini", "yolo", policy=pol)
    if r["ok"] or "kill-switch" not in r["reason"]:
        _fail(f"blocked_modes kill-switch should BLOCK: {r}")
    print("PASS  gemini yolo in blocked_modes -> BLOCK (kill-switch)")


def test_privileged_requires_auth_when_hardened():
    pol = _clone(**{"global.privileged_requires_authorization": True})
    # not authorized -> BLOCK
    r = mod.evaluate("gemini", "yolo", authorized=False, policy=pol)
    if r["ok"] or "requires authorization" not in r["reason"]:
        _fail(f"hardened privileged without auth should BLOCK: {r}")
    # authorized -> ALLOW
    r2 = mod.evaluate("gemini", "yolo", authorized=True, policy=pol)
    if not r2["ok"]:
        _fail(f"hardened privileged WITH auth should ALLOW: {r2}")
    print("PASS  hardened: privileged needs auth (BLOCK w/o, ALLOW w/)")


def test_unknown_agent_fail_open():
    r = mod.evaluate("mystery", "whatever", policy=BASE)
    if not r["ok"] or "not in policy" not in r["reason"]:
        _fail(f"unknown agent should fail-open ALLOW: {r}")
    print("PASS  unknown agent -> fail-open ALLOW")


def test_missing_policy_fail_open():
    r = mod.evaluate("codex", "edit", policy=None,
                     task_id="")  # will try to load real file
    # real file exists, so this actually loads it; assert it does not crash
    if "decision" not in r:
        _fail(f"evaluate with real policy should return a decision: {r}")
    print("PASS  real policy load returns a decision (no crash)")


if __name__ == "__main__":
    test_safe_mode_allowed()
    test_privileged_allowed_by_default()
    test_invalid_mode_blocked()
    test_kill_switch()
    test_privileged_requires_auth_when_hardened()
    test_unknown_agent_fail_open()
    test_missing_policy_fail_open()
    print("\n7/7 agent-action-policy tests passed")
