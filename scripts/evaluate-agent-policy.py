#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict


def load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate(policy: Dict[str, Any], profile: str, task: str, tool: str) -> Dict[str, Any]:
    base = dict(policy.get("default", {}))
    prof = policy.get("profiles", {}).get(profile, {})

    out = {
        "profile": profile,
        "task": task,
        "tool": tool,
        "allow": bool(base.get("allow", True)),
        "reasoning_mode": prof.get("reasoning_mode", base.get("reasoning_mode", "hybrid")),
        "max_external_calls": int(prof.get("max_external_calls", base.get("max_external_calls", 1))),
        "max_retrieval_results": int(base.get("max_retrieval_results", 8)),
        "matched_overrides": [],
        "reasons": [],
    }

    allow_tools = set(prof.get("allow_tools", []))
    deny_tools = set(prof.get("deny_tools", []))
    if allow_tools and tool and tool not in allow_tools:
        out["allow"] = False
        out["reasons"].append(f"tool_not_in_allowlist:{tool}")
    if tool in deny_tools:
        out["allow"] = False
        out["reasons"].append(f"tool_denied:{tool}")

    tlow = task.lower()
    for rule in policy.get("task_overrides", []):
        needles = [n.lower() for n in rule.get("contains", [])]
        if needles and not any(n in tlow for n in needles):
            continue
        out["matched_overrides"].append(rule.get("contains", []))
        if "reasoning_mode" in rule:
            out["reasoning_mode"] = str(rule["reasoning_mode"])
        if "max_external_calls" in rule:
            out["max_external_calls"] = int(rule["max_external_calls"])
        if "max_retrieval_results" in rule:
            out["max_retrieval_results"] = int(rule["max_retrieval_results"])
        for denied in rule.get("deny_tools", []):
            if tool == denied:
                out["allow"] = False
                out["reasons"].append(f"override_denied_tool:{tool}")
        req = set(rule.get("require_tools", []))
        if req and tool and tool not in req:
            out["reasons"].append(f"override_prefers_tools:{','.join(sorted(req))}")

    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Evaluate profile/task/tool policy decisions")
    ap.add_argument("--policy", default="config/agent-routing-policy.json")
    ap.add_argument("--profile", required=True)
    ap.add_argument("--task", required=True)
    ap.add_argument("--tool", default="")
    args = ap.parse_args()

    policy = load(Path(args.policy))
    decision = evaluate(policy, args.profile, args.task, args.tool)
    print(json.dumps(decision, indent=2, sort_keys=True))
    return 0 if decision["allow"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
