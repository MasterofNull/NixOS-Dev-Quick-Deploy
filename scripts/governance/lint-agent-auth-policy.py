#!/usr/bin/env python3
"""Lint config/agent-auth-policy.json (agent-auth DESIGN 8.1 AUTH-S2).

Fails when: the policy is structurally invalid (undeclared scopes, scope without
guidance, class granting an undeclared scope, self_service profile not a strict
subset of owner-agent) or when an existing loopback-agent prefix / public path
would classify as the catch-all admin scope for every method (a family with no
scope). Static add_get/add_post routes that fall to admin are listed
informationally: unmatched-to-admin is the designed default.
"""
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HC = REPO / "ai-stack" / "mcp-servers" / "hybrid-coordinator"
sys.path[:0] = [str(HC), str(HC.parent)]
os.environ.setdefault("AI_STRICT_ENV", "false")  # lint only reads constants; skip service env checks
os.environ.setdefault("AQ_AGENT_AUTH_POLICY", str(REPO / "config" / "agent-auth-policy.json"))

from middleware.auth import LOOPBACK_AGENT_PREFIXES, PUBLIC_PATHS  # noqa: E402
from middleware.authz import Policy, PolicyError, load_policy  # noqa: E402

ROUTE_RE = re.compile(r"""add_(?:get|post|put|delete|patch)\(\s*["'](/[^"']*)["']""")


def main() -> int:
    try:
        policy = load_policy()
    except (PolicyError, OSError, ValueError, KeyError) as exc:
        print(f"[lint-agent-auth-policy] FAIL: {exc}", file=sys.stderr)
        return 1
    failures = []
    for path in sorted(PUBLIC_PATHS):
        if policy.match("GET", path)[0] != policy.public_scope:
            failures.append(f"public path {path} is not scope '{policy.public_scope}'")
    for prefix in LOOPBACK_AGENT_PREFIXES:
        scopes = {policy.match(m, prefix)[0] for m in ("GET", "POST")}
        if scopes <= {policy.default_scope}:
            failures.append(f"loopback prefix {prefix} resolves to '{policy.default_scope}' for GET and POST")
    unscoped = set()
    for py in HC.rglob("*.py"):
        if "tests" in py.parts:
            continue
        for route in ROUTE_RE.findall(py.read_text(errors="ignore")):
            if policy.match("GET", route)[0] == policy.default_scope and \
                    policy.match("POST", route)[0] == policy.default_scope:
                unscoped.add(route)
    for f in failures:
        print(f"[lint-agent-auth-policy] FAIL: {f}", file=sys.stderr)
    if failures:
        return 1
    print(f"[lint-agent-auth-policy] PASS: {len(policy.scopes)} scopes, "
          f"{len(LOOPBACK_AGENT_PREFIXES)} loopback prefixes covered, "
          f"{len(unscoped)} static routes default to '{policy.default_scope}' (informational)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
