#!/usr/bin/env python3
"""Project editorial tracker items from bounded, read-only git evidence."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    override = os.environ.get("FACTORY_REPO_ROOT")
    if override:
        return Path(override).resolve()
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], check=True, capture_output=True, text=True
    )
    return Path(result.stdout.strip())


def git_log(root: Path) -> tuple[str, str]:
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
    try:
        shallow = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(root), "rev-parse", "--is-shallow-repository"],
            capture_output=True, text=True, timeout=10, env=env,
        )
        history = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(root), "log", "--oneline", "-n", "5000"],
            capture_output=True, text=True, timeout=30, env=env,
        )
    except (OSError, subprocess.SubprocessError):
        return "", "unavailable"
    if shallow.returncode or history.returncode:
        return "", "unavailable"
    return history.stdout, "shallow_incomplete" if shallow.stdout.strip() == "true" else "complete"


def validate(manifest: object) -> list[str]:
    if not isinstance(manifest, dict):
        return ["tracker root must be an object"]
    errors: list[str] = []
    plan = manifest.get("plan")
    if not isinstance(plan, dict):
        errors.append("plan must be an object")
    else:
        for field in ("id", "title", "goal"):
            if not isinstance(plan.get(field), str) or not plan[field]:
                errors.append(f"plan.{field} must be a non-empty string")
    items = manifest.get("items")
    if not isinstance(items, list) or not items:
        return errors + ["items must be a non-empty array"]
    ids: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            errors.append("every item must be an object")
            continue
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id:
            errors.append("item missing id")
        elif item_id in ids:
            errors.append(f"duplicate item id {item_id}")
        else:
            ids.add(item_id)
        for field in ("goal", "validation_goal"):
            if not isinstance(item.get(field), str) or not item[field]:
                errors.append(f"item {item_id} {field} must be a non-empty string")
        if "status" in item:
            errors.append(f"item {item_id} must not hand-type status")
        deps = item.get("deps")
        if not isinstance(deps, list) or not all(isinstance(dep, str) and dep for dep in deps):
            errors.append(f"item {item_id} deps must be an array of non-empty strings")
        detection = item.get("detection")
        if not isinstance(detection, dict):
            errors.append(f"item {item_id} detection must be an object")
        elif "commit_match" in detection and (
            not isinstance(detection["commit_match"], list)
            or not all(isinstance(token, str) and token for token in detection["commit_match"])
        ):
            errors.append(f"item {item_id} detection.commit_match must be an array of non-empty strings")
        pct_hint = item.get("pct_hint", 60)
        if isinstance(pct_hint, bool) or not isinstance(pct_hint, (int, float)) or not 0 <= pct_hint <= 100:
            errors.append(f"item {item_id} pct_hint must be a number from 0 to 100")
        acceptance = item.get("acceptance")
        if acceptance is not None and (
            not isinstance(acceptance, dict) or not isinstance(acceptance.get("status"), str)
        ):
            errors.append(f"item {item_id} acceptance.status must be a string when acceptance is provided")
    for item in items:
        if not isinstance(item, dict):
            continue
        for dependency in item.get("deps", []):
            if dependency not in ids:
                errors.append(f"item {item.get('id')} dependency {dependency!r} is unknown")
    return errors


def project(manifest: dict, history: str, source_health: str) -> dict:
    rows = []
    for item in manifest["items"]:
        matches = (item.get("detection") or {}).get("commit_match", [])
        accepted = (item.get("acceptance") or {}).get("status") == "accepted"
        evidence_matches = bool(matches) and any(token in history for token in matches)
        if source_health != "complete" and matches:
            status, percent = "UNKNOWN", None
        elif evidence_matches and accepted:
            status, percent = "SHIPPED", 100
        elif evidence_matches:
            status, percent = "IN-PROGRESS", min(99, int(item.get("pct_hint", 60)))
        else:
            status, percent = "DESIGNED", 10
        rows.append({"id": item["id"], "name": item.get("name", item["id"]), "status": status, "pct": percent})
    known = [row["pct"] for row in rows if row["pct"] is not None]
    return {
        "plan": manifest["plan"], "items": rows,
        "rollup_pct": round(sum(known) / len(known)) if known else None,
        "source_health": source_health,
        "rollup_authoritative": source_health == "complete",
    }


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: pm-tracker <plan-dir> [--check|--json]", file=sys.stderr)
        return 2
    plan_dir = Path(sys.argv[1])
    root = repo_root()
    if not plan_dir.is_absolute():
        plan_dir = root / plan_dir
    try:
        manifest = json.loads((plan_dir / "tracker.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    errors = validate(manifest)
    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1
    history, health = git_log(root)
    result = project(manifest, history, health)
    if "--check" in sys.argv[2:]:
        print(f"PASS: {plan_dir.name}/tracker.json valid and projects")
    else:
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
