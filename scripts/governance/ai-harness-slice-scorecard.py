#!/usr/bin/env python3
# Validate the AI harness slice registry and emit a maturity scorecard.
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = REPO_ROOT / "config" / "ai-harness-slice-registry.json"
VALID_MATURITY = ("defined", "validated", "observable", "governed")
VALID_RISK = ("low", "medium", "high")
DIMENSIONS = (
    "contract",
    "owner_surface",
    "control_plane",
    "data_plane",
    "observability",
    "quality_gate",
    "discoverability",
    "governance",
)
PATH_KEYS = (
    "primary_paths",
    "config_paths",
    "policy_paths",
    "runtime_paths",
    "storage_paths",
    "test_paths",
    "docs",
)


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    return []


def path_exists(rel_path: str) -> bool:
    text = str(rel_path or "").strip()
    if not text:
        return False
    if text.startswith("runtime:"):
        return True
    if text.startswith("/") or text.startswith("journalctl ") or text.startswith("git revert "):
        return True
    if text.startswith("http://") or text.startswith("https://"):
        return True
    return (REPO_ROOT / text).exists()


def collect_declared_paths(section: Dict[str, Any]) -> Iterable[Tuple[str, str]]:
    for key in PATH_KEYS:
        for item in as_list(section.get(key)):
            yield key, str(item)


def validate_registry(data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    for key in ("version", "description", "score_dimensions", "maturity_levels", "slices"):
        if key not in data:
            errors.append(f"missing top-level key: {key}")

    slices = as_list(data.get("slices"))
    if not slices:
        errors.append("registry must declare at least one slice")
        return errors

    seen_ids: set[str] = set()
    for slice_data in slices:
        slice_id = str(slice_data.get("id", "")).strip()
        if not slice_id:
            errors.append("slice is missing id")
            continue
        if slice_id in seen_ids:
            errors.append(f"duplicate slice id: {slice_id}")
        seen_ids.add(slice_id)

        for key in ("name", "domain", "summary", "maturity_target"):
            if not str(slice_data.get(key, "")).strip():
                errors.append(f"{slice_id}: missing {key}")

        maturity_target = str(slice_data.get("maturity_target", "")).strip()
        if maturity_target and maturity_target not in VALID_MATURITY:
            errors.append(f"{slice_id}: invalid maturity_target {maturity_target!r}")

        governance = slice_data.get("governance") or {}
        risk_level = str(governance.get("risk_level", "")).strip()
        if risk_level and risk_level not in VALID_RISK:
            errors.append(f"{slice_id}: invalid risk_level {risk_level!r}")

        for section_name in DIMENSIONS:
            if section_name not in slice_data:
                errors.append(f"{slice_id}: missing section {section_name}")

        owner = slice_data.get("owner_surface") or {}
        if not as_list(owner.get("primary_paths")):
            errors.append(f"{slice_id}: owner_surface.primary_paths must not be empty")
        if not as_list(owner.get("entrypoints")):
            errors.append(f"{slice_id}: owner_surface.entrypoints must not be empty")

        contract = slice_data.get("contract") or {}
        for key in ("inputs", "outputs", "invariants", "failure_modes", "rollback_commands"):
            if not as_list(contract.get(key)):
                errors.append(f"{slice_id}: contract.{key} must not be empty")

        quality = slice_data.get("quality_gate") or {}
        if not as_list(quality.get("validation_commands")):
            errors.append(f"{slice_id}: quality_gate.validation_commands must not be empty")
        if not as_list(quality.get("acceptance_signals")):
            errors.append(f"{slice_id}: quality_gate.acceptance_signals must not be empty")

        discoverability = slice_data.get("discoverability") or {}
        if not as_list(discoverability.get("docs")):
            errors.append(f"{slice_id}: discoverability.docs must not be empty")

        for section_name in DIMENSIONS:
            section = slice_data.get(section_name) or {}
            if not isinstance(section, dict):
                errors.append(f"{slice_id}: section {section_name} must be an object")
                continue
            for path_key, rel_path in collect_declared_paths(section):
                if not path_exists(rel_path):
                    errors.append(f"{slice_id}: missing path for {section_name}.{path_key}: {rel_path}")

        for rel_path in as_list(owner.get("entrypoints")):
            if not path_exists(str(rel_path)):
                errors.append(f"{slice_id}: missing owner entrypoint: {rel_path}")

    return errors


def dimension_status(slice_data: Dict[str, Any], dimension: str) -> Dict[str, Any]:
    section = slice_data.get(dimension) or {}
    blockers: List[str] = []

    if dimension == "contract":
        required = ("inputs", "outputs", "invariants", "failure_modes", "rollback_commands")
        for key in required:
            if not as_list(section.get(key)):
                blockers.append(f"missing {dimension}.{key}")
    elif dimension == "owner_surface":
        if not as_list(section.get("primary_paths")):
            blockers.append("missing owner_surface.primary_paths")
        if not as_list(section.get("entrypoints")):
            blockers.append("missing owner_surface.entrypoints")
    elif dimension == "control_plane":
        if not (as_list(section.get("config_paths")) or as_list(section.get("policy_paths"))):
            blockers.append("missing control-plane config or policy paths")
    elif dimension == "data_plane":
        if not as_list(section.get("runtime_paths")):
            blockers.append("missing data_plane.runtime_paths")
        if not (
            as_list(section.get("api_endpoints"))
            or as_list(section.get("mcp_tools"))
            or as_list(section.get("storage_paths"))
            or as_list((slice_data.get("owner_surface") or {}).get("entrypoints"))
        ):
            blockers.append("missing api_endpoints, mcp_tools, storage_paths, or owner entrypoints")
    elif dimension == "observability":
        if not (as_list(section.get("health_checks")) or as_list(section.get("metrics_signals"))):
            blockers.append("missing health_checks or metrics_signals")
        if not (as_list(section.get("dashboards")) or as_list(section.get("alerts"))):
            blockers.append("missing dashboards or alerts")
    elif dimension == "quality_gate":
        if not as_list(section.get("validation_commands")):
            blockers.append("missing validation_commands")
        if not as_list(section.get("test_paths")):
            blockers.append("missing test_paths")
        if not as_list(section.get("acceptance_signals")):
            blockers.append("missing acceptance_signals")
    elif dimension == "discoverability":
        if not as_list(section.get("docs")):
            blockers.append("missing docs")
        if not (
            as_list(section.get("cli_entrypoints"))
            or as_list(section.get("dashboard_routes"))
        ):
            blockers.append("missing cli_entrypoints or dashboard_routes")
    elif dimension == "governance":
        if str(section.get("risk_level", "")).strip() not in VALID_RISK:
            blockers.append("missing or invalid risk_level")
        if not as_list(section.get("review_commands")):
            blockers.append("missing review_commands")

    for path_key, rel_path in collect_declared_paths(section):
        if not path_exists(rel_path):
            blockers.append(f"missing path {path_key}:{rel_path}")

    status = "pass" if not blockers else "fail"
    return {"status": status, "blockers": blockers}


def achieved_maturity(dimensions: Dict[str, Dict[str, Any]], levels: Dict[str, Any]) -> str:
    achieved = "defined"
    for level in VALID_MATURITY:
        required = as_list((levels.get(level) or {}).get("required_dimensions"))
        if required and all(dimensions.get(name, {}).get("status") == "pass" for name in required):
            achieved = level
        else:
            break
    return achieved


def build_scorecard(data: Dict[str, Any]) -> Dict[str, Any]:
    levels = data.get("maturity_levels") or {}
    scorecard: Dict[str, Any] = {
        "version": data.get("version"),
        "slice_count": len(as_list(data.get("slices"))),
        "slices": [],
        "summary": {},
    }

    achieved_counts = {level: 0 for level in VALID_MATURITY}
    target_counts = {level: 0 for level in VALID_MATURITY}

    for slice_data in as_list(data.get("slices")):
        statuses = {name: dimension_status(slice_data, name) for name in DIMENSIONS}
        passed = sum(1 for item in statuses.values() if item["status"] == "pass")
        total = len(DIMENSIONS)
        achieved = achieved_maturity(statuses, levels)
        target = str(slice_data.get("maturity_target", "defined")).strip()
        blockers = [
            f"{dimension}: {detail}"
            for dimension, info in statuses.items()
            for detail in info["blockers"]
        ]
        achieved_counts[achieved] += 1
        if target in target_counts:
            target_counts[target] += 1

        scorecard["slices"].append(
            {
                "id": slice_data["id"],
                "name": slice_data["name"],
                "domain": slice_data["domain"],
                "score": passed,
                "max_score": total,
                "percent": round((passed / total) * 100, 1),
                "target_maturity": target,
                "achieved_maturity": achieved,
                "dimensions": statuses,
                "blockers": blockers,
            }
        )

    scorecard["summary"] = {
        "achieved_maturity_counts": achieved_counts,
        "target_maturity_counts": target_counts,
        "fully_passing_slices": sum(1 for item in scorecard["slices"] if item["score"] == item["max_score"]),
    }
    return scorecard


def render_text(scorecard: Dict[str, Any], errors: List[str]) -> str:
    lines: List[str] = []
    lines.append("AI Harness Slice Scorecard")
    lines.append(f"Version: {scorecard.get('version', 'unknown')}")
    lines.append(f"Slices: {scorecard.get('slice_count', 0)}")
    if errors:
        lines.append("")
        lines.append("Validation Errors:")
        for error in errors:
            lines.append(f"- {error}")
    lines.append("")
    lines.append("Slice Summary:")
    for item in scorecard.get("slices", []):
        lines.append(
            f"- {item['id']}: {item['score']}/{item['max_score']} "
            f"({item['percent']}%) | achieved={item['achieved_maturity']} "
            f"| target={item['target_maturity']}"
        )
        if item["blockers"]:
            for blocker in item["blockers"][:4]:
                lines.append(f"  blocker: {blocker}")
    lines.append("")
    summary = scorecard.get("summary") or {}
    lines.append("Maturity Counts:")
    for level in VALID_MATURITY:
        lines.append(
            f"- {level}: achieved={summary.get('achieved_maturity_counts', {}).get(level, 0)} "
            f"| target={summary.get('target_maturity_counts', {}).get(level, 0)}"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the AI harness slice registry and emit a scorecard.")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero on registry validation errors.")
    args = parser.parse_args()

    registry = load_json(Path(args.registry))
    errors = validate_registry(registry)
    scorecard = build_scorecard(registry)

    if args.format == "json":
        print(json.dumps({"errors": errors, "scorecard": scorecard}, indent=2, sort_keys=True))
    else:
        print(render_text(scorecard, errors))

    if errors and args.strict:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
