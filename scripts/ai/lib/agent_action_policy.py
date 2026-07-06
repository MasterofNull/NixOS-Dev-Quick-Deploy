#!/usr/bin/env python3
"""agent_action_policy — policy gate for external-agent delegation actions.

Enforced at the delegation boundary (delegate-to-codex / delegate-to-gemini) BEFORE an
external CLI is launched. The only action the harness controls at that boundary is the
execution MODE (the sandbox / approval posture): e.g. codex `edit`
(--dangerously-bypass-approvals-and-sandbox) or gemini `yolo` (auto-approve shell). This
module answers: is <agent> allowed to run in <mode>, and does that mode need authorization?

Decisions (config/agent-action-policy.json):
  - mode in agent.blocked_modes                 -> BLOCK (central kill-switch)
  - mode not in agent.allowed_modes (unless "*") -> BLOCK (invalid mode)
  - mode in agent.privileged_modes AND
      global.privileged_requires_authorization AND not authorized -> BLOCK (needs auth)
  - otherwise                                    -> ALLOW

Every decision is audited via a2a_guard.audit (shared .agent/collaboration/a2a-audit.log).
Fails OPEN (ALLOW) if the policy file is missing/broken and global.fail_open is true (the
default) — a config problem must not silently break all delegations — but the failure is
audited so it is visible.

CLI:  agent_action_policy.py <agent> <mode> [authorized]
        prints "ALLOW <reason>" (exit 0) or "BLOCK <reason>" (exit 3).
        authorized: "1"/"true" if the caller presented the authorization env.
"""
from __future__ import annotations

import json
import os
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path
from typing import Dict

_REPO = Path(__file__).resolve().parents[3]
_POLICY_PATH = os.environ.get(
    "AGENT_ACTION_POLICY", str(_REPO / "config" / "agent-action-policy.json")
)


def _audit(agent: str, mode: str, decision: str, reason: str, task_id: str = "") -> None:
    """Record the policy decision on the shared A2A audit trail (never raises)."""
    try:
        guard = SourceFileLoader(
            "a2a_guard", str(Path(__file__).with_name("a2a_guard.py"))
        ).load_module()
        guard.audit(
            direction="policy",
            from_agent="harness",
            to_agent=agent,
            summary=f"action-policy {decision}: mode={mode} — {reason}",
            secret_findings=None,
            task_id=task_id,
        )
    except Exception:
        pass


def load_policy(path: str | None = None) -> Dict:
    p = path or _POLICY_PATH
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def evaluate(agent: str, mode: str, authorized: bool = False,
             policy: Dict | None = None, task_id: str = "") -> Dict:
    """Return {ok, decision, reason, privileged}. decision in ALLOW|BLOCK."""
    try:
        pol = policy if policy is not None else load_policy()
    except Exception as exc:  # missing/broken policy
        # Consult fail_open only if we can; default to open (never hard-break delegation).
        reason = f"policy load failed ({exc}); fail-open ALLOW"
        _audit(agent, mode, "ALLOW", reason, task_id)
        return {"ok": True, "decision": "ALLOW", "reason": reason, "privileged": False}

    glob = pol.get("global", {})
    agents = pol.get("agents", {})
    acfg = agents.get(agent)
    if acfg is None:
        reason = f"agent '{agent}' not in policy; fail-open ALLOW"
        _audit(agent, mode, "ALLOW", reason, task_id)
        return {"ok": True, "decision": "ALLOW", "reason": reason, "privileged": False}

    allowed = acfg.get("allowed_modes", [])
    blocked = acfg.get("blocked_modes", [])
    privileged_modes = acfg.get("privileged_modes", [])
    is_privileged = mode in privileged_modes

    if mode in blocked:
        reason = f"mode '{mode}' is in {agent}.blocked_modes (kill-switch)"
        _audit(agent, mode, "BLOCK", reason, task_id)
        return {"ok": False, "decision": "BLOCK", "reason": reason, "privileged": is_privileged}

    if "*" not in allowed and mode not in allowed:
        reason = f"mode '{mode}' not in {agent}.allowed_modes {allowed}"
        _audit(agent, mode, "BLOCK", reason, task_id)
        return {"ok": False, "decision": "BLOCK", "reason": reason, "privileged": is_privileged}

    if is_privileged and glob.get("privileged_requires_authorization", False) and not authorized:
        env = glob.get("authorization_env", "A2A_ALLOW_PRIVILEGED")
        pr = acfg.get("privileged_reason", "privileged mode")
        reason = (f"privileged mode '{mode}' requires authorization ({env}=1). {pr}")
        _audit(agent, mode, "BLOCK", reason, task_id)
        return {"ok": False, "decision": "BLOCK", "reason": reason, "privileged": True}

    reason = (f"privileged mode '{mode}' authorized" if is_privileged
              else f"mode '{mode}' permitted")
    _audit(agent, mode, "ALLOW", reason, task_id)
    return {"ok": True, "decision": "ALLOW", "reason": reason, "privileged": is_privileged}


def _truthy(v: str) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "on")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: agent_action_policy.py <agent> <mode> [authorized]", file=sys.stderr)
        sys.exit(2)
    _agent, _mode = sys.argv[1], sys.argv[2]
    _authorized = _truthy(sys.argv[3]) if len(sys.argv) > 3 else False
    res = evaluate(_agent, _mode, authorized=_authorized, task_id=os.environ.get("AQ_TASK_ID", ""))
    print(f"{res['decision']} {res['reason']}")
    sys.exit(0 if res["ok"] else 3)
