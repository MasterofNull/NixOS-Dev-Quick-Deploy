#!/usr/bin/env python3
"""Safe, greenfield-only installer for the portable factory gate bundle.

This program deliberately reads only repository metadata while resolving stack
checks.  It never runs target commands; execution proof belongs to the caller's
isolated fixture test.  Existing projects and hook configurations are refused
for the confirm-gated brownfield slice.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
RECEIPT = Path(".factory/gate-install.json")
BUNDLE_DESTINATION = Path(".factory/gate-bundle")
STARTER_TRACKER = Path(".agents/plans/factory-gate/tracker.json")
HOOKS_PATH = ".githooks"
PLACEHOLDER = re.compile(r"\{\{([A-Z0-9_]+)\}\}")


def emit(value: dict[str, Any]) -> int:
    print(json.dumps(value, sort_keys=True))
    return 0


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args], text=True, capture_output=True, check=False,
        # Do not inherit a caller's repository-routing variables.  Git itself
        # exports these to hooks, and accepting them here could inspect a
        # different repository during a supposedly metadata-only operation.
        env={key: os.environ[key] for key in ("PATH", "HOME", "XDG_CONFIG_HOME") if key in os.environ},
    )


def git_value(root: Path, *args: str) -> str | None:
    result = git(root, *args)
    return result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else None


def git_metadata_conflict(target: Path) -> str | None:
    """Reject redirected metadata and active default hooks before changing config."""
    metadata = target / ".git"
    if not metadata.exists() and not metadata.is_symlink():
        return None
    if metadata.is_symlink() or not metadata.is_dir():
        return ".git must be a local directory (gitdir redirects are not greenfield-safe)"
    config = metadata / "config"
    if config.is_symlink() or (config.exists() and not config.is_file()):
        return ".git/config is redirected; refuse writes outside the target"
    if (metadata / "commondir").exists() or (metadata / "commondir").is_symlink():
        return ".git/commondir shared metadata is not greenfield-safe"
    hooks = metadata / "hooks"
    if hooks.is_symlink():
        return ".git/hooks is redirected; preserve it for FT-4 composition"
    if hooks.exists() and not hooks.is_dir():
        return ".git/hooks is not a local directory; preserve it for FT-4 composition"
    if hooks.is_dir():
        for hook in sorted(hooks.iterdir()):
            if hook.name.endswith(".sample"):
                continue
            if hook.is_symlink() or (hook.is_file() and os.access(hook, os.X_OK)):
                return f"active default hook preserved: .git/hooks/{hook.name}"
    return None


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def resolver(bundle_root: Path, target: Path, stack: str | None) -> dict[str, Any]:
    command = [sys.executable, str(bundle_root / "stack-adapters/resolve.py"), str(target)]
    if stack and stack not in {"", "TBD"}:
        command.extend(["--override", stack.lower()])
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(f"stack detector failed: {result.stderr.strip() or result.stdout.strip()}")
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise RuntimeError("stack detector did not return a JSON object")
    return value


def command_values(detected: dict[str, Any]) -> tuple[dict[str, str], list[str]]:
    commands: dict[str, str] = {}
    blocked: list[str] = []
    for name in ("build", "test", "lint", "secret_scan"):
        ready: list[str] = []
        reasons: list[str] = []
        for stack, profile in (detected.get("profiles") or {}).items():
            check = profile.get("checks", {}).get(name, {}) if isinstance(profile, dict) else {}
            if check.get("state") == "READY" and isinstance(check.get("command"), str):
                ready.append(check["command"])
            elif isinstance(check.get("reason"), str):
                reasons.append(f"{stack}: {check['reason']}")
        if ready and not reasons:
            # Profiles are trusted bundle data.  Retain every detected ready
            # command instead of choosing the first stack in a polyglot repo.
            # A mixed ready/unconfigured set must keep the template blocked:
            # running only the ready subset would falsely pass a requirement.
            commands[name] = " && ".join(dict.fromkeys(ready))
        if reasons:
            blocked.append(f"{name}: {'; '.join(reasons)}")
        elif not ready:
            blocked.append(f"{name}: no safe command declared")
    # The universal live/freshness checks have no metadata-only conventional command.
    blocked.extend(["live_service: no safe conventional command declared", "freshness: no safe conventional command declared"])
    return commands, blocked


def render_values(project_name: str, commands: dict[str, str]) -> dict[str, str]:
    return {
        "ARCHIVE_POLICY": ".agent/archive/ (preserve evidence; do not delete)",
        "BUILD_CMD": commands.get("build", "{{BUILD_CMD}}"),
        "CLAUDE_ROLE": "implementer/reviewer as assigned",
        "CODEX_ROLE": "implementer/reviewer as assigned",
        "FRESHNESS_CHECK_CMD": "{{FRESHNESS_CHECK_CMD}}",
        "GATE_RUNNER_PATH": "scripts/governance/gate-runner",
        "GEMINI_ROLE": "implementer/reviewer as assigned",
        "HOOKS_PATH": HOOKS_PATH,
        "ISSUES_PATH": ".agent/memory/issues-backlog.md",
        "LANE_PARITY_CHECK": "reserved for FT-7",
        "LINT_CMD": commands.get("lint", "{{LINT_CMD}}"),
        "LIVE_SERVICE_CHECK_CMD": "{{LIVE_SERVICE_CHECK_CMD}}",
        "LOCAL_AGENT_ROLE": "bounded implementer as assigned",
        "LOCAL_CAPABILITY_CONSTRAINTS": "follow the target capability policy",
        "PLAN_ROOT": ".agents/plans",
        "PM_TRACKER_PATH": "scripts/pm-tracker",
        "PROJECT_METADATA_FILE": str(RECEIPT),
        "PROJECT_NAME": project_name,
        "PROTECTED_BRANCHES": "main master trunk",
        "PULSE_PATH": ".agent/collaboration/PULSE.log",
        "REPOSITORY_LAYOUT": "src/ and tests/ (adjust only by authorized target configuration)",
        "RESUME_PATH": ".agent/collaboration/RESUME.json",
        "RISK_TIER_POLICY": "reserved for FT-6",
        "SECRET_SCAN_CMD": commands.get("secret_scan", "{{SECRET_SCAN_CMD}}"),
        "SHARED_RULES": ".agent/SHARED-RULES.md",
        "SOURCE_DIR": "src",
        "SOURCE_REPOSITORY": "factory-gate-bundle",
        "TEST_CMD": commands.get("test", "{{TEST_CMD}}"),
        "TEST_DIR": "tests",
        "WORKFLOW_CANON_PATH": ".agent/WORKFLOW-CANON.md",
    }


def rendered(source: Path, values: dict[str, str]) -> bytes:
    data = source.read_text(encoding="utf-8")
    return PLACEHOLDER.sub(lambda match: values.get(match.group(1), match.group(0)), data).encode()


def manifest_entries(bundle_root: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    manifest = load_json(bundle_root / "MANIFEST.json")
    files = manifest.get("files")
    if not isinstance(files, list):
        raise RuntimeError("bundle manifest has no files list")
    entries = [entry for entry in files if isinstance(entry, dict) and entry.get("bundle_path") != "."]
    if not entries:
        raise RuntimeError("bundle manifest has no renderable entries")
    checked: list[dict[str, str]] = []
    for entry in entries:
        source_rel, destination = str(entry.get("bundle_path", "")), str(entry.get("install_target", ""))
        source_raw = bundle_root / source_rel
        source = source_raw.resolve()
        target = Path(destination)
        if (not source_rel or source_rel == "." or source_raw.is_symlink() or not source.is_file()
                or bundle_root not in source.parents or target.is_absolute() or not destination
                or any(part in ("", "..") for part in target.parts)):
            raise RuntimeError(f"unsafe manifest entry: {source_rel!r} -> {destination!r}")
        checked.append({"bundle_path": source_rel, "install_target": destination})
    return manifest, checked


def collision_report(target: Path, bundle_root: Path) -> list[str]:
    _, entries = manifest_entries(bundle_root)
    destinations = [BUNDLE_DESTINATION, RECEIPT, STARTER_TRACKER]
    for entry in entries:
        destination = Path(str(entry.get("install_target", "")))
        if destination.is_absolute() or ".." in destination.parts:
            raise RuntimeError(f"unsafe manifest destination: {destination}")
        destinations.append(destination)
    conflicts: set[str] = set()
    for path in destinations:
        candidate = target / path
        if candidate.exists() or candidate.is_symlink():
            conflicts.add(str(path))
        # Existing directories may be scaffold parents (for example .agent),
        # but a file or symlink ancestor would redirect a later write.
        parent = candidate.parent
        while parent != target:
            if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
                conflicts.add(str(parent.relative_to(target)))
            parent = parent.parent
    return sorted(conflicts)


def preview(target: Path, bundle_root: Path, stack: str | None, project_name: str) -> dict[str, Any]:
    detected = resolver(bundle_root, target, stack)
    commands, blocked = command_values(detected)
    metadata_conflict = git_metadata_conflict(target)
    configured = (git_value(target, "config", "--get", "core.hooksPath")
                  if (target / ".git").is_dir() and not metadata_conflict else None)
    collisions = collision_report(target, bundle_root)
    hooks_conflict = configured not in (None, "", HOOKS_PATH)
    safe = not collisions and not hooks_conflict and not metadata_conflict
    return {
        "schema_version": SCHEMA_VERSION,
        "target": str(target),
        "project_name": project_name,
        "operation": "preview",
        "safe_to_install": safe,
        "collisions": collisions,
        "hooks": {"configured_path": configured, "expected_path": HOOKS_PATH,
                  "state": "CONFLICT" if hooks_conflict or metadata_conflict else "UNCONFIGURED",
                  "conflict": metadata_conflict},
        "detector": detected,
        "checks": {"commands": commands, "state": "CONFIGURATION_BLOCKED" if blocked else "READY",
                   "required_unconfigured": blocked},
    }


def copy_bundle(bundle_root: Path, target: Path) -> None:
    shutil.copytree(bundle_root, target / BUNDLE_DESTINATION, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def install(target: Path, bundle_root: Path, stack: str | None, project_name: str) -> dict[str, Any]:
    report = preview(target, bundle_root, stack, project_name)
    if not report["safe_to_install"]:
        report.update({"operation": "install", "installation": {"state": "REFUSED"}})
        return report
    if not (target / ".git").is_dir() or (target / ".git").is_symlink():
        report.update({"operation": "install", "installation": {"state": "REFUSED", "reason": "target is not a git repository"}})
        return report
    manifest, entries = manifest_entries(bundle_root)
    values = render_values(project_name, report["checks"]["commands"])
    copy_bundle(bundle_root, target)
    for entry in entries:
        source = bundle_root / str(entry["bundle_path"])
        relative_destination = Path(str(entry["install_target"]))
        destination = target / relative_destination
        # The complete source bundle is deliberately retained byte-for-byte as
        # a standalone recovery/reference artifact.  Do not re-render its
        # manifest, self-test, or adapter sources through their duplicate
        # manifest destinations.
        if relative_destination.is_relative_to(BUNDLE_DESTINATION):
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(rendered(source, values))
        source_mode = source.stat().st_mode
        if source_mode & stat.S_IXUSR:
            destination.chmod(destination.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    starter = target / STARTER_TRACKER
    starter.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(bundle_root / "pm-tracker/sample/tracker.json", starter)
    configured = git(target, "config", "--local", "core.hooksPath", HOOKS_PATH)
    if configured.returncode:
        raise RuntimeError(f"could not configure core.hooksPath: {configured.stderr.strip()}")
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "bundle_version": manifest.get("bundle_version"),
        "target": str(target),
        "detector": report["detector"],
        "checks": report["checks"],
        "hooks": {"configured_path": HOOKS_PATH, "expected_path": HOOKS_PATH,
                  "state": "ACTIVE", "executable": {
                      "pre_commit": os.access(target / HOOKS_PATH / "pre-commit", os.X_OK),
                      "commit_msg": os.access(target / HOOKS_PATH / "commit-msg", os.X_OK)}},
        "tracker": {"state": "DISCOVERED", "paths": [str(STARTER_TRACKER)]},
        "proof": {"state": "HOOK_PATH_VERIFIED", "detail": "Configured target hook path and executable hook files; execution proof is isolated fixture coverage."},
        "activation": "ACTIVATION_BLOCKED" if report["checks"]["required_unconfigured"] else "READY",
    }
    receipt_path = target / RECEIPT
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt["installation"] = {"state": "INSTALLED", "receipt_path": str(RECEIPT), "manifest_path": str(BUNDLE_DESTINATION / "MANIFEST.json")}
    return receipt


def status(target: Path, bundle_root: Path, stack: str | None, project_name: str) -> dict[str, Any]:
    receipt = load_json(target / RECEIPT)
    configured = git_value(target, "config", "--get", "core.hooksPath") if (target / ".git").exists() else None
    hooks_dir = target / (configured or HOOKS_PATH)
    executable = {name: (hooks_dir / name).is_file() and os.access(hooks_dir / name, os.X_OK)
                  for name in ("pre-commit", "commit-msg")}
    tracker_paths = [str(path.relative_to(target)) for path in target.glob(".agents/plans/**/tracker.json")]
    state = "ACTIVE" if configured == HOOKS_PATH and all(executable.values()) else "UNCONFIGURED"
    return {
        "schema_version": SCHEMA_VERSION, "target": str(target), "operation": "status",
        "installation": {"state": "INSTALLED" if receipt else "ABSENT", "receipt_path": str(RECEIPT)},
        "bundle_version": receipt.get("bundle_version"),
        "hooks": {"state": state, "configured_path": configured, "expected_path": HOOKS_PATH, "executable": executable},
        "checks": receipt.get("checks", {"state": "UNKNOWN", "required_unconfigured": ["no install receipt"]}),
        "tracker": {"state": "DISCOVERED" if tracker_paths else "NONE", "paths": tracker_paths},
        "proof": receipt.get("proof", {"state": "NOT_RUN"}),
        "activation": receipt.get("activation", "ACTIVATION_BLOCKED"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("preview", "install", "status"))
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--bundle-root", type=Path, required=True)
    parser.add_argument("--stack")
    parser.add_argument("--project-name", required=True)
    args = parser.parse_args()
    target, bundle_root = args.target.resolve(), args.bundle_root.resolve()
    try:
        if args.operation == "preview":
            result = preview(target, bundle_root, args.stack, args.project_name)
            emit(result)
            return 0 if result["safe_to_install"] else 1
        if args.operation == "install":
            result = install(target, bundle_root, args.stack, args.project_name)
            return emit(result) if result.get("installation", {}).get("state") == "INSTALLED" else 1
        return emit(status(target, bundle_root, args.stack, args.project_name))
    except (OSError, RuntimeError, ValueError) as error:
        return emit({"schema_version": SCHEMA_VERSION, "operation": args.operation, "state": "ERROR", "error": str(error)}) or 1


if __name__ == "__main__":
    raise SystemExit(main())
