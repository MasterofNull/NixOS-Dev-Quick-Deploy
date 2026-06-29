#!/usr/bin/env python3
"""Validate suggested external AI repo candidates stay security-gated."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "config" / "suggested-ai-repo-candidates.json"
SCHEMA = ROOT / "config" / "schemas" / "suggested-ai-repo-candidates.schema.json"

REQUIRED_FIELDS = {
    "id",
    "name",
    "source_url",
    "category",
    "priority",
    "state",
    "maturity_signal",
    "why_research",
    "local_gap_targets",
    "parity_checks",
    "security_gates",
    "intake_action",
    "delegation_targets",
}
ALLOWED_STATES = {"research-only", "proposed", "defer", "reject"}
ALLOWED_CATEGORIES = {
    "agent-framework",
    "coding-agent",
    "mcp-infrastructure",
    "browser-automation",
    "memory-rag",
    "benchmark",
}


def load(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    errors: list[str] = []
    payload = load(CATALOG)
    load(SCHEMA)

    policy = payload.get("policy", {})
    if policy.get("default_state") != "research-only":
        errors.append("policy.default_state must remain research-only")
    if policy.get("required_gate") != "capability-intake":
        errors.append("policy.required_gate must be capability-intake")

    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        errors.append("candidates must be a non-empty list")
        candidates = []

    seen: set[str] = set()
    high_count = 0
    for index, candidate in enumerate(candidates):
        prefix = f"candidates[{index}]"
        if not isinstance(candidate, dict):
            errors.append(f"{prefix} must be an object")
            continue

        missing = sorted(REQUIRED_FIELDS - set(candidate))
        if missing:
            errors.append(f"{prefix} missing fields: {', '.join(missing)}")
            continue

        candidate_id = str(candidate["id"])
        if candidate_id in seen:
            errors.append(f"duplicate candidate id: {candidate_id}")
        seen.add(candidate_id)

        if not candidate["source_url"].startswith("https://github.com/"):
            errors.append(f"{candidate_id}.source_url must be a GitHub HTTPS URL")
        if candidate["category"] not in ALLOWED_CATEGORIES:
            errors.append(f"{candidate_id}.category is not allowed")
        if candidate["state"] not in ALLOWED_STATES:
            errors.append(f"{candidate_id}.state is not allowed")
        if candidate["state"] == "enabled":
            errors.append(f"{candidate_id} must not be enabled from this catalog")
        if candidate["priority"] == "high":
            high_count += 1

        for field in ("local_gap_targets", "parity_checks", "security_gates", "delegation_targets"):
            if not isinstance(candidate.get(field), list) or not candidate[field]:
                errors.append(f"{candidate_id}.{field} must be a non-empty list")

        if "local-agent" not in candidate.get("delegation_targets", []):
            errors.append(f"{candidate_id}.delegation_targets must include local-agent")
        if not any("capability-intake" in gate for gate in candidate.get("security_gates", [])):
            errors.append(f"{candidate_id}.security_gates must include capability-intake")

    if high_count < 5:
        errors.append("catalog should include at least five high-priority candidates")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"PASS: {len(candidates)} suggested AI repo candidates valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
