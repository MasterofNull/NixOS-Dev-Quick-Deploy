#!/usr/bin/env python3
"""Validate the AI capability implementation backlog stays actionable and gated."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKLOG = ROOT / "config" / "ai-capability-implementation-backlog.json"
SCHEMA = ROOT / "config" / "schemas" / "ai-capability-implementation-backlog.schema.json"

REQUIRED_FIELDS = {
    "id",
    "domain",
    "priority",
    "status",
    "candidate_urls",
    "local_equivalents",
    "gap_type",
    "runtime_authority",
    "data_access_class",
    "suggested_first_slice",
    "security_gates",
    "observability_required",
    "validation",
    "dashboard_parity",
    "owner",
}
ALLOWED_PRIORITIES = {"critical", "high", "medium", "low"}
ALLOWED_STATUSES = {"backlog", "ready-for-prd", "defer", "blocked"}
ALLOWED_GAPS = {"missing", "weaker", "blocked", "duplicate", "mature-alternative"}


def load(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    errors: list[str] = []
    payload = load(BACKLOG)
    load(SCHEMA)

    policy = payload.get("policy", {})
    if policy.get("default_status") != "backlog":
        errors.append("policy.default_status must remain backlog")
    if policy.get("activation_gate") != "capability-intake":
        errors.append("policy.activation_gate must be capability-intake")

    items = payload.get("items")
    if not isinstance(items, list) or not items:
        errors.append("items must be a non-empty list")
        items = []

    seen: set[str] = set()
    ready_or_critical = 0
    for index, item in enumerate(items):
        prefix = f"items[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue

        missing = sorted(REQUIRED_FIELDS - set(item))
        if missing:
            errors.append(f"{prefix} missing fields: {', '.join(missing)}")
            continue

        item_id = str(item["id"])
        if item_id in seen:
            errors.append(f"duplicate backlog id: {item_id}")
        seen.add(item_id)

        if item["priority"] not in ALLOWED_PRIORITIES:
            errors.append(f"{item_id}.priority is not allowed")
        if item["status"] not in ALLOWED_STATUSES:
            errors.append(f"{item_id}.status is not allowed")
        if item["gap_type"] not in ALLOWED_GAPS:
            errors.append(f"{item_id}.gap_type is not allowed")
        if item["priority"] == "critical" or item["status"] == "ready-for-prd":
            ready_or_critical += 1

        for field in (
            "candidate_urls",
            "local_equivalents",
            "runtime_authority",
            "security_gates",
            "observability_required",
            "validation",
        ):
            if not isinstance(item.get(field), list) or not item[field]:
                errors.append(f"{item_id}.{field} must be a non-empty list")

        if not any(str(url).startswith("https://github.com/") for url in item.get("candidate_urls", [])):
            errors.append(f"{item_id}.candidate_urls must include at least one GitHub URL")
        if not any("capability-intake" in gate for gate in item.get("security_gates", [])):
            errors.append(f"{item_id}.security_gates must include capability-intake")
        if not item.get("suggested_first_slice", "").strip():
            errors.append(f"{item_id}.suggested_first_slice is required")
        parity = item.get("dashboard_parity", "").lower()
        if not any(surface in parity for surface in ("dashboard", "aq-report", "panel")):
            errors.append(f"{item_id}.dashboard_parity must mention dashboard, aq-report, or panel visibility")

    if len(items) < 10:
        errors.append("backlog must record at least ten capability domains")
    if ready_or_critical < 5:
        errors.append("backlog must include at least five critical or ready-for-prd items")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"PASS: {len(items)} AI capability backlog items valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
