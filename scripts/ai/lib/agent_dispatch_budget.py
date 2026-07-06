#!/usr/bin/env python3
"""agent_dispatch_budget — rate/budget limit for external-agent dispatches.

Enforced at the delegation boundary (delegate-to-codex / -gemini / -antigravity) BEFORE a
new dispatch is registered. Counts recent dispatches per agent (and across all external
agents) from the shared registry and refuses/warns when a rolling-window cap is exceeded —
bounding runaway agent loops (cost for paid lanes; outbound-message volume for all).

Source of truth: config/agent-dispatch-budget.json.
Registry: .agents/delegation/registry.jsonl — each line has {"agent", "created": ISO8601Z}.

Decision (per call, evaluated against dispatches ALREADY in the registry, i.e. excluding
the one about to be made):
  - global.enabled=false or bypass_env set    -> ALLOW (disabled/bypassed)
  - agent window count >= agent cap           -> over agent budget
  - global window count >= global cap         -> over global budget
  - enforcement=block on an over-budget result -> BLOCK (rc 3); enforcement=warn -> ALLOW+warn
Fails OPEN (ALLOW) if the policy/registry is missing or broken — a bookkeeping problem
must not silently halt all delegation — but the fail-open is audited.

CLI:  agent_dispatch_budget.py <agent> [registry_path]
        prints "ALLOW <reason>" (0) | "WARN <reason>" (0) | "BLOCK <reason>" (3).
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from importlib.machinery import SourceFileLoader
from pathlib import Path
from typing import Dict, List

_REPO = Path(__file__).resolve().parents[3]
_POLICY_PATH = os.environ.get(
    "AGENT_DISPATCH_BUDGET", str(_REPO / "config" / "agent-dispatch-budget.json")
)
_REGISTRY_PATH = str(_REPO / ".agents" / "delegation" / "registry.jsonl")


def _audit(agent: str, decision: str, reason: str) -> None:
    try:
        guard = SourceFileLoader(
            "a2a_guard", str(Path(__file__).with_name("a2a_guard.py"))
        ).load_module()
        guard.audit(direction="budget", from_agent="harness", to_agent=agent,
                    summary=f"dispatch-budget {decision}: {reason}", secret_findings=None)
    except Exception:
        pass


def load_policy(path: str | None = None) -> Dict:
    with open(path or _POLICY_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _parse_ts(s: str) -> float | None:
    try:
        s = s.strip().replace("Z", "+00:00")
        return datetime.fromisoformat(s).timestamp()
    except Exception:
        return None


def _recent_counts(registry_path: str, agents: List[str], now: float) -> Dict[str, list]:
    """Return {agent: [timestamps]} for configured agents present in the registry."""
    out: Dict[str, list] = {a: [] for a in agents}
    try:
        with open(registry_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                a = rec.get("agent")
                if a in out:
                    ts = _parse_ts(rec.get("created", ""))
                    if ts is not None:
                        out[a].append(ts)
    except OSError:
        return out
    return out


def check(agent: str, registry_path: str | None = None, policy: Dict | None = None,
          now: float | None = None) -> Dict:
    """Return {ok, decision, reason, agent_count, global_count}."""
    now = now if now is not None else datetime.now(timezone.utc).timestamp()
    try:
        pol = policy if policy is not None else load_policy()
    except Exception as exc:
        reason = f"budget policy load failed ({exc}); fail-open ALLOW"
        _audit(agent, "ALLOW", reason)
        return {"ok": True, "decision": "ALLOW", "reason": reason,
                "agent_count": 0, "global_count": 0}

    glob = pol.get("global", {})
    if not glob.get("enabled", True):
        return {"ok": True, "decision": "ALLOW", "reason": "budget disabled",
                "agent_count": 0, "global_count": 0}
    bypass_env = glob.get("bypass_env", "A2A_BUDGET_BYPASS")
    if os.environ.get(bypass_env, "").strip().lower() in ("1", "true", "yes", "on"):
        _audit(agent, "ALLOW", f"bypassed via {bypass_env}")
        return {"ok": True, "decision": "ALLOW", "reason": f"bypassed via {bypass_env}",
                "agent_count": 0, "global_count": 0}

    agents_cfg = pol.get("agents", {})
    reg = registry_path or _REGISTRY_PATH
    counts = _recent_counts(reg, list(agents_cfg.keys()), now)

    acfg = agents_cfg.get(agent, {})
    a_window = acfg.get("window_seconds", glob.get("window_seconds", 300))
    a_max = acfg.get("max_dispatches", glob.get("max_dispatches", 60))
    a_count = sum(1 for t in counts.get(agent, []) if now - t < a_window)

    g_window = glob.get("window_seconds", 300)
    g_max = glob.get("max_dispatches", 60)
    g_count = sum(1 for ts in counts.values() for t in ts if now - t < g_window)

    over = None
    if a_count >= a_max:
        over = f"agent '{agent}' at {a_count}/{a_max} dispatches in {a_window}s"
    elif g_count >= g_max:
        over = f"all external agents at {g_count}/{g_max} dispatches in {g_window}s"

    if over is None:
        reason = f"within budget (agent {a_count}/{a_max}, global {g_count}/{g_max})"
        return {"ok": True, "decision": "ALLOW", "reason": reason,
                "agent_count": a_count, "global_count": g_count}

    enforcement = glob.get("enforcement", "block")
    if enforcement == "warn":
        _audit(agent, "WARN", over)
        return {"ok": True, "decision": "WARN", "reason": over,
                "agent_count": a_count, "global_count": g_count}
    _audit(agent, "BLOCK", over)
    return {"ok": False, "decision": "BLOCK", "reason": over,
            "agent_count": a_count, "global_count": g_count}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: agent_dispatch_budget.py <agent> [registry_path]", file=sys.stderr)
        sys.exit(2)
    _agent = sys.argv[1]
    _reg = sys.argv[2] if len(sys.argv) > 2 else None
    res = check(_agent, registry_path=_reg)
    print(f"{res['decision']} {res['reason']}")
    sys.exit(0 if res["ok"] else 3)
