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
import hashlib
import shlex
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
RECEIPT = Path(".factory/gate-install.json")
EVIDENCE_RECEIPT = Path(".factory/gate-run-evidence.json")
BUNDLE_DESTINATION = Path(".factory/gate-bundle")
STARTER_TRACKER = Path(".agents/plans/factory-gate/tracker.json")
# These two checks have no metadata-only conventional command (see
# command_values below) and are WARN, not HARD, severity at --pre-commit in
# the installed gate-runner; they can never be auto-configured, so readiness
# must not treat them as commit-blocking the way build/test/lint/secret_scan are.
HARD_CHECK_PREFIXES = ("build:", "test:", "lint:", "secret_scan:")
COLLABORATION_STATE = {
    Path(".agent/collaboration/PULSE.log"): (
        b"[1970-01-01T00:00:00Z] [factory-gate] [initialize]: collaboration scaffold - ready\n"
    ),
    Path(".agent/collaboration/RESUME.json"): json.dumps({
        "schema_version": 1,
        "objective": "Factory gate scaffold initialized",
        "phase": "ORIENT",
        "remaining_work": ["Configure required checks", "Assign an authorized slice"],
        "changed_files": [],
        "resume_hint": "Review the install receipt before beginning work.",
    }, indent=2, sort_keys=True).encode() + b"\n",
    Path(".agent/memory/issues-backlog.md"): b"# Issues Backlog\n\nNo issues recorded at scaffold initialization.\n",
    Path(".agent/archive/.gitkeep"): b"",
}
HOOKS_PATH = ".githooks"
PLACEHOLDER = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
HOOK_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


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


def engine_capability(env_var: str) -> dict[str, str]:
    """Declare one shared-engine capability from the deploying ENV, never a live probe.

    Mirrors the FT-5 readiness lane model (hybrid_coordinator: CONFIGURED vs
    TRANSPORT_UNAVAILABLE): an endpoint is read from the environment the
    installer runs in; when absent, the capability is a typed "unavailable"
    declaration -- never a copied host-specific literal like 127.0.0.1:8003.
    curl_target is a separate non-empty field so a permission allow-pattern
    built from it can never collapse to an unbounded "curl *" wildcard.
    """
    endpoint = os.environ.get(env_var, "").strip()
    if endpoint:
        return {"state": "available", "endpoint": endpoint, "source": f"env:{env_var}", "curl_target": endpoint}
    sentinel = f"unavailable://{env_var.lower()}-not-configured"
    return {"state": "unavailable", "endpoint": "", "source": f"env:{env_var} (unset)", "curl_target": sentinel}


def render_values(project_name: str, commands: dict[str, str], layout_policy: str = "") -> dict[str, str]:
    hybrid = engine_capability("HYBRID_URL")
    aidb = engine_capability("AIDB_URL")
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
        "LAYOUT_POLICY": layout_policy,
        "REPOSITORY_LAYOUT": "the reviewed top-level policy in .factory/repo-structure.conf",
        "RESUME_PATH": ".agent/collaboration/RESUME.json",
        "RISK_TIER_POLICY": "reserved for FT-6",
        "SECRET_SCAN_CMD": commands.get("secret_scan", "{{SECRET_SCAN_CMD}}"),
        "SHARED_RULES": ".agent/SHARED-RULES.md",
        "SOURCE_DIR": "src",
        "SOURCE_REPOSITORY": "factory-gate-bundle",
        "TEST_CMD": commands.get("test", "{{TEST_CMD}}"),
        "TEST_DIR": "tests",
        "WORKFLOW_CANON_PATH": ".agent/WORKFLOW-CANON.md",
        "HYBRID_COORDINATOR_STATE": hybrid["state"],
        "HYBRID_COORDINATOR_ENDPOINT": hybrid["endpoint"],
        "HYBRID_COORDINATOR_SOURCE": hybrid["source"],
        "HYBRID_COORDINATOR_CURL_TARGET": hybrid["curl_target"],
        "HYBRID_COORDINATOR_HINTS_ENDPOINT": f"{hybrid['curl_target']}/hints",
        "HYBRID_COORDINATOR_HINTS_ENABLED": "true" if hybrid["state"] == "available" else "false",
        "AIDB_STATE": aidb["state"],
        "AIDB_ENDPOINT": aidb["endpoint"],
        "AIDB_SOURCE": aidb["source"],
        "AIDB_CURL_TARGET": aidb["curl_target"],
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


def planned_directories(paths: list[Path]) -> list[str]:
    directories: set[Path] = set()
    for path in paths:
        parent = path.parent
        while parent != Path("."):
            directories.add(parent)
            parent = parent.parent
    return sorted(str(path) for path in directories)


def layout_policy(target: Path, entries: list[dict[str, str]]) -> str:
    """Freeze legitimate current roots and every root the installer can create."""
    roots: set[str] = set()
    for path in target.iterdir():
        # Git metadata is validated by the caller and never reaches the policy.
        if path.name == ".git":
            continue
        if path.is_symlink() or "=" in path.name or "\n" in path.name or "\r" in path.name:
            raise RuntimeError(f"unsafe existing top-level path: {path.name!r}")
        roots.add(path.name)
    install_paths = [BUNDLE_DESTINATION, RECEIPT, STARTER_TRACKER, *COLLABORATION_STATE]
    install_paths.extend(Path(entry["install_target"]) for entry in entries)
    roots.update(path.parts[0] for path in install_paths if path.parts)
    return "".join(f"allowed_top={root}\n" for root in sorted(roots))


def rendered_outputs(bundle_root: Path, entries: list[dict[str, str]], values: dict[str, str]) -> dict[Path, bytes]:
    """Return every non-bundle file byte the installer may create."""
    outputs: dict[Path, bytes] = {}
    for entry in entries:
        destination = Path(entry["install_target"])
        if not destination.is_relative_to(BUNDLE_DESTINATION):
            outputs[destination] = rendered(bundle_root / entry["bundle_path"], values)
    outputs[STARTER_TRACKER] = (bundle_root / "pm-tracker/sample/tracker.json").read_bytes()
    outputs.update(COLLABORATION_STATE)
    return outputs


def bundle_write_paths(bundle_root: Path) -> list[Path]:
    """List the preserved source files that copy_bundle writes byte-for-byte."""
    return [BUNDLE_DESTINATION / path.relative_to(bundle_root) for path in sorted(bundle_root.rglob("*"))
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"]


def collision_report(target: Path, bundle_root: Path, extra_destinations: tuple[Path, ...] = ()) -> list[str]:
    _, entries = manifest_entries(bundle_root)
    destinations = [BUNDLE_DESTINATION, RECEIPT, STARTER_TRACKER]
    for entry in entries:
        destination = Path(str(entry.get("install_target", "")))
        if destination.is_absolute() or ".." in destination.parts:
            raise RuntimeError(f"unsafe manifest destination: {destination}")
        destinations.append(destination)
    destinations.extend(extra_destinations)
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
    _, entries = manifest_entries(bundle_root)
    values = render_values(project_name, commands, layout_policy(target, entries))
    outputs = rendered_outputs(bundle_root, entries, values)
    metadata_conflict = git_metadata_conflict(target)
    configured = (git_value(target, "config", "--get", "core.hooksPath")
                  if (target / ".git").is_dir() and not metadata_conflict else None)
    collisions = collision_report(target, bundle_root, tuple(outputs))
    hooks_conflict = configured not in (None, "", HOOKS_PATH)
    safe = not collisions and not hooks_conflict and not metadata_conflict
    rendered_plan = [{"path": str(path), "sha256": hashlib.sha256(data).hexdigest()}
                     for path, data in sorted(outputs.items())]
    bundle_paths = bundle_write_paths(bundle_root)
    directories = planned_directories([*bundle_paths, *outputs])
    fingerprint = {"bundle_sha256": bundle_digest(bundle_root), "target_content_sha256": target_content_digest(target),
                   "rendered_plan": rendered_plan, "directories": directories, "target": str(target), "stack": stack or ""}
    return {
        "schema_version": SCHEMA_VERSION,
        "target": str(target),
        "project_name": project_name,
        "operation": "preview",
        "safe_to_install": safe,
        "collisions": collisions,
        "preview_digest": hashlib.sha256(json.dumps(fingerprint, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "writes": sorted(str(path) for path in [*bundle_paths, *outputs]),
        "directories": directories,
        "rendered_plan": rendered_plan,
        "hooks": {"configured_path": configured, "expected_path": HOOKS_PATH,
                  "state": "CONFLICT" if hooks_conflict or metadata_conflict else "UNCONFIGURED",
                  "conflict": metadata_conflict},
        "detector": detected,
        "checks": {"commands": commands, "state": "CONFIGURATION_BLOCKED" if blocked else "READY",
                   "required_unconfigured": blocked},
    }


def copy_bundle(bundle_root: Path, target: Path) -> None:
    # dirs_exist_ok=True lets a compatible-upgrade retrofit re-copy the
    # retained bundle over its own prior copy; a genuinely foreign
    # .factory/gate-bundle is refused earlier, before this is ever called.
    shutil.copytree(bundle_root, target / BUNDLE_DESTINATION, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                     dirs_exist_ok=True)


def digest_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bundle_digest(bundle_root: Path) -> str:
    return framed_tree_digest(bundle_root, exclude_git=False)


def target_content_digest(target: Path) -> str:
    """Bind confirmation to ordinary target files without following links."""
    return framed_tree_digest(target, exclude_git=True)


def framed_tree_digest(root: Path, *, exclude_git: bool) -> str:
    """Hash typed, length-framed records; never concatenate raw file bytes."""
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if (exclude_git and ".git" in path.parts) or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        relative = str(path.relative_to(root))
        if path.is_symlink():
            record = {"path": relative, "type": "symlink", "target": os.readlink(path)}
        elif path.is_file():
            record = {"path": relative, "type": "file", "mode": stat.S_IMODE(path.stat().st_mode), "sha256": digest_bytes(path)}
        elif path.is_dir():
            record = {"path": relative, "type": "dir", "mode": stat.S_IMODE(path.stat().st_mode)}
        else:
            continue
        encoded = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
        digest.update(len(encoded).to_bytes(8, "big") + encoded)
    return digest.hexdigest()


def safe_write_path(target: Path, relative: Path, *, allow_existing: bool = False) -> str | None:
    """Reject exact/ancestor collisions before any archive or install write.

    allow_existing lets a compatible-upgrade retrofit re-apply over its own
    prior factory-managed files (already validated as ordinary files by the
    caller); it never tolerates a symlinked destination.
    """
    candidate = target / relative
    if candidate.is_symlink() or (candidate.exists() and not allow_existing):
        return f"existing write destination: {relative}"
    if allow_existing and candidate.exists() and not candidate.is_file():
        return f"unsupported existing destination: {relative}"
    parent = candidate.parent
    while parent != target:
        if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
            return f"unsafe destination ancestor: {parent.relative_to(target)}"
        parent = parent.parent
    return None


def retrofit_metadata_conflict(target: Path) -> str | None:
    """Brownfield supports only a local ordinary .git directory and hooks."""
    metadata = target / ".git"
    if metadata.is_symlink() or not metadata.is_dir():
        return "unsupported redirected or missing .git metadata"
    config, hooks = metadata / "config", metadata / "hooks"
    if config.is_symlink() or not config.is_file():
        return "unsupported redirected .git/config"
    if hooks.is_symlink() or not hooks.is_dir():
        return "unsupported redirected .git/hooks"
    if (metadata / "commondir").exists() or (metadata / "commondir").is_symlink():
        return "unsupported shared .git/commondir metadata"
    return None


def safe_hook_records(target: Path) -> tuple[list[dict[str, Any]], str | None]:
    records: list[dict[str, Any]] = []
    for hook in sorted((target / ".git/hooks").iterdir()):
        if hook.name.endswith(".sample") or not (hook.is_symlink() or (hook.is_file() and os.access(hook, os.X_OK))):
            continue
        if hook.is_symlink() or not HOOK_NAME.fullmatch(hook.name):
            return [], f"unsupported executable hook: {hook.name}"
        records.append({"name": hook.name, "mode": stat.S_IMODE(hook.stat().st_mode), "sha256": digest_bytes(hook)})
    return records, None


# Factory-owned tooling roots a compatible upgrade re-renders in place. This
# deliberately excludes every user/project file the manifest also installs
# (AGENTS.md, CLAUDE.md, .agent/*.md, collaboration-state seeds, the sample
# PM tracker) -- those stay preserved exactly as a first-time retrofit
# already preserves them, on both a first install and a later upgrade.
# capability-manifest.json IS included: it declares live env-derived
# shared-engine state (F1/F2), not user content, so an upgrade must
# re-declare the current HYBRID_URL/AIDB_URL availability rather than
# freezing whatever state happened to exist at first install.
FACTORY_MANAGED_PREFIXES = (
    Path("scripts/governance"),
    Path("scripts/pm-tracker"),
    Path(".factory/repo-structure.conf"),
    Path(".factory/pm-tracker"),
    Path(".factory/gate-retrofit-hooks"),
    Path(".factory/capability-manifest.json"),
    Path(HOOKS_PATH),
    BUNDLE_DESTINATION,
)


def _factory_managed(destination: Path) -> bool:
    return destination in FACTORY_MANAGED_PREFIXES or any(
        prefix in destination.parents for prefix in FACTORY_MANAGED_PREFIXES
    )


def _is_compatible_prior_install(target: Path) -> bool:
    """An already-onboarded repo (our own prior install/retrofit) is safe to re-apply.

    A foreign hooksPath is still refused by the caller; this only recognizes
    OUR OWN prior work as an upgrade target, never a stranger's identical
    hooksPath value.
    """
    receipt = load_json(target / RECEIPT)
    return bool(receipt) and receipt.get("hooks", {}).get("configured_path") == HOOKS_PATH


def retrofit_preview(target: Path, bundle_root: Path, stack: str | None, project_name: str) -> dict[str, Any]:
    conflict = retrofit_metadata_conflict(target)
    upgrade = False
    if not conflict:
        configured = git_value(target, "config", "--get", "core.hooksPath")
        if configured == HOOKS_PATH:
            upgrade = _is_compatible_prior_install(target)
            if not upgrade:
                conflict = f"unsupported existing core.hooksPath: {configured}"
        elif configured:
            conflict = f"unsupported existing core.hooksPath: {configured}"
    else:
        configured = None
    hooks, hook_conflict = safe_hook_records(target) if not conflict else ([], None)
    conflict = conflict or hook_conflict
    detected = resolver(bundle_root, target, stack)
    commands, blocked = command_values(detected)
    manifest, entries = manifest_entries(bundle_root)
    preserved: list[dict[str, Any]] = []
    writes: list[str] = [str(path) for path in bundle_write_paths(bundle_root)]
    rendered_plan: list[dict[str, str]] = []
    values = render_values(project_name, commands, layout_policy(target, entries))
    outputs = {path: content for path, content in rendered_outputs(bundle_root, entries, values).items()
               if path.parts[0] != HOOKS_PATH}
    routed = {record["name"] for record in hooks} | {"pre-commit", "commit-msg"}
    for name in ("pre-commit", "commit-msg"):
        outputs[Path(f".factory/gate-retrofit-hooks/{name}")] = rendered(bundle_root / "hooks" / name, values)
    outputs.update({Path(HOOKS_PATH) / name: router_script(target, name, name in {"pre-commit", "commit-msg"})
                    for name in sorted(routed)})
    for destination, content in outputs.items():
        candidate = target / destination
        managed = _factory_managed(destination)
        if candidate.exists() or candidate.is_symlink():
            if upgrade and managed:
                # A compatible prior install: refresh our own tooling output
                # in place instead of refusing or silently preserving it.
                if candidate.is_symlink() or not candidate.is_file():
                    conflict = conflict or f"unsupported existing destination: {destination}"
                else:
                    writes.append(str(destination))
                    rendered_plan.append({"path": str(destination), "sha256": hashlib.sha256(content).hexdigest()})
            elif managed:
                conflict = conflict or f"enforcement component collision: {destination}"
            elif candidate.is_symlink() or not candidate.is_file():
                conflict = conflict or f"unsupported existing destination: {destination}"
            else:
                preserved.append({"path": str(destination), "mode": stat.S_IMODE(candidate.stat().st_mode), "sha256": digest_bytes(candidate)})
        else:
            writes.append(str(destination))
            rendered_plan.append({"path": str(destination), "sha256": hashlib.sha256(content).hexdigest()})
    for path in (BUNDLE_DESTINATION, Path(".factory/gate-retrofit-hooks"), Path(".githooks")):
        candidate = target / path
        exists = candidate.exists() or candidate.is_symlink()
        if not exists:
            continue
        if not upgrade:
            conflict = conflict or f"existing factory destination requires a separate merge plan: {path}"
        elif candidate.is_symlink() or not candidate.is_dir():
            conflict = conflict or f"unsupported existing destination: {path}"
    # The receipt is written after hooks/configuration, so it must be refused
    # during preview as rigorously as every earlier destination. In
    # particular, do not follow a pre-existing .factory/gate-install.json
    # symlink outside the target. On a compatible upgrade the receipt is
    # ours and IS expected to already exist (it is how _is_compatible_
    # prior_install detected the upgrade candidate in the first place) --
    # allow_existing lets safe_write_path skip only the plain-exists
    # refusal, never the symlink/non-file refusal Codex's fix added.
    writes.append(str(RECEIPT))
    write_paths = [Path(path) for path in writes]
    directories = planned_directories(write_paths)
    for path in write_paths:
        issue = safe_write_path(target, path, allow_existing=upgrade and (_factory_managed(path) or path == RECEIPT))
        if issue:
            conflict = conflict or issue
    config = target / ".git/config"
    source_hash = bundle_digest(bundle_root)
    config_record = ({"mode": stat.S_IMODE(config.stat().st_mode), "sha256": digest_bytes(config)}
                     if config.is_file() and not config.is_symlink() else {"unavailable": True})
    fingerprint = {"bundle_sha256": source_hash, "config": config_record,
                   "hooks": hooks, "preserved": preserved, "writes": sorted(set(writes)), "directories": directories,
                   "configured_path": configured, "upgrade": upgrade,
                   "target_content_sha256": target_content_digest(target), "rendered_plan": rendered_plan,
                   "check_configuration": {"commands": commands, "required_unconfigured": blocked},
                   "target": str(target), "stack": stack or ""}
    digest = hashlib.sha256(json.dumps(fingerprint, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    backup = f".factory/gate-backups/{digest}/.git-config"
    backup_issue = safe_write_path(target, Path(backup))
    conflict = conflict or backup_issue
    return {"schema_version": SCHEMA_VERSION, "operation": "retrofit-preview", "target": str(target), "project_name": project_name,
            "safe_to_install": not conflict, "blocker": conflict, "preview_digest": digest, "source_bundle_sha256": source_hash,
            "writes": sorted(set(writes)), "directories": directories, "rendered_plan": rendered_plan, "upgrade": upgrade,
            "preserved": preserved, "hooks": {"configured_path": configured, "existing": hooks,
            "routing": ".git/hooks -> .githooks wrappers"}, "backup_paths": [backup], "detector": detected,
            "checks": {"commands": commands, "state": "CONFIGURATION_BLOCKED" if blocked else "READY", "required_unconfigured": blocked}}


def router_script(target: Path, name: str, factory: bool) -> bytes:
    root = shlex.quote(str(target))
    body = f"#!/usr/bin/env bash\nset -euo pipefail\nrepo_root={root}\n"
    body += f"original=\"${{repo_root}}/.git/hooks/{shlex.quote(name)}\"\nif [[ -x \"${{original}}\" ]]; then \"${{original}}\" \"$@\"; fi\n"
    if factory:
        body += "cd -- \"${repo_root}\"\n"
        body += f"exec \"${{repo_root}}/.factory/gate-retrofit-hooks/{name}\" \"$@\"\n"
    else:
        body = body.replace('if [[ -x "${original}" ]]; then "${original}" "$@"; fi\n', 'if [[ -x "${original}" ]]; then exec "${original}" "$@"; fi\nexit 0\n')
    return body.encode()


def retrofit_install(target: Path, bundle_root: Path, stack: str | None, project_name: str, confirmation: str | None) -> dict[str, Any]:
    report = retrofit_preview(target, bundle_root, stack, project_name)
    if not report["safe_to_install"]:
        report["installation"] = {"state": "REFUSED"}
        return report
    if not confirmation or confirmation != report["preview_digest"]:
        report["installation"] = {"state": "CONFIRMATION_REQUIRED", "expected_preview_digest": report["preview_digest"]}
        return report
    manifest, entries = manifest_entries(bundle_root)
    values = render_values(project_name, report["checks"]["commands"], layout_policy(target, entries))
    outputs = {path: content for path, content in rendered_outputs(bundle_root, entries, values).items()
               if path.parts[0] != HOOKS_PATH}
    routed = {record["name"] for record in report["hooks"]["existing"]} | {"pre-commit", "commit-msg"}
    for name in ("pre-commit", "commit-msg"):
        outputs[Path(f".factory/gate-retrofit-hooks/{name}")] = rendered(bundle_root / "hooks" / name, values)
    outputs.update({Path(HOOKS_PATH) / name: router_script(target, name, name in {"pre-commit", "commit-msg"})
                    for name in sorted(routed)})
    upgrade = bool(report.get("upgrade"))
    backup = target / report["backup_paths"][0]
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target / ".git/config", backup)
    copy_bundle(bundle_root, target)
    for relative, content in outputs.items():
        destination = target / relative
        refresh = upgrade and _factory_managed(relative)
        if (destination.exists() or destination.is_symlink()) and not refresh:
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        bundle_entry = next((entry for entry in entries if Path(entry["install_target"]) == relative), None)
        if bundle_entry and (bundle_root / bundle_entry["bundle_path"]).stat().st_mode & stat.S_IXUSR:
            destination.chmod(destination.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    for name in ("pre-commit", "commit-msg"):
        (target / ".factory/gate-retrofit-hooks" / name).chmod(0o755)
    for name in routed:
        (target / HOOKS_PATH / name).chmod(0o755)
    configured = git(target, "config", "--local", "core.hooksPath", HOOKS_PATH)
    if configured.returncode:
        raise RuntimeError(f"could not configure core.hooksPath: {configured.stderr.strip()}")
    receipt = {"schema_version": SCHEMA_VERSION, "bundle_version": manifest.get("bundle_version"), "target": str(target), "retrofit": True,
               "preview_digest": report["preview_digest"], "backup_paths": report["backup_paths"], "checks": report["checks"],
               "hooks": {"configured_path": HOOKS_PATH, "state": "ACTIVE", "composed": sorted(routed)}, "upgrade": upgrade,
               "proof": {"state": "HOOK_PATH_VERIFIED", "detail": "Existing hooks are routed before factory hooks; execution proof is fixture-only."},
               "activation": "ACTIVATION_BLOCKED" if report["checks"]["required_unconfigured"] else "READY"}
    (target / RECEIPT).parent.mkdir(parents=True, exist_ok=True)
    (target / RECEIPT).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt["installation"] = {"state": "INSTALLED", "receipt_path": str(RECEIPT)}
    return receipt


def install(target: Path, bundle_root: Path, stack: str | None, project_name: str) -> dict[str, Any]:
    report = preview(target, bundle_root, stack, project_name)
    if not report["safe_to_install"]:
        report.update({"operation": "install", "installation": {"state": "REFUSED"}})
        return report
    if not (target / ".git").is_dir() or (target / ".git").is_symlink():
        report.update({"operation": "install", "installation": {"state": "REFUSED", "reason": "target is not a git repository"}})
        return report
    manifest, entries = manifest_entries(bundle_root)
    values = render_values(project_name, report["checks"]["commands"], layout_policy(target, entries))
    outputs = rendered_outputs(bundle_root, entries, values)
    copy_bundle(bundle_root, target)
    for relative_destination, content in outputs.items():
        destination = target / relative_destination
        # The complete source bundle is deliberately retained byte-for-byte as
        # a standalone recovery/reference artifact.  Do not re-render its
        # manifest, self-test, or adapter sources through their duplicate
        # manifest destinations.
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        bundle_entry = next((entry for entry in entries if Path(entry["install_target"]) == relative_destination), None)
        if bundle_entry and (bundle_root / bundle_entry["bundle_path"]).stat().st_mode & stat.S_IXUSR:
            destination.chmod(destination.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
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


def render_agentic_settings(target: Path, template_root: Path, project_name: str) -> dict[str, Any]:
    """Render templates/agentic-workflow/.claude/settings.json.tmpl (F2 fix).

    This tree is a separate template set from the gate bundle (installed by
    scripts/ai/aqd's write_agent_command_specs, not manifest_entries()); it
    was previously `cp`'d byte-for-byte with no placeholder substitution at
    all, which is how the host-specific 127.0.0.1 URLs ended up hardcoded.
    Reuses render_values()/rendered() -- the same engine-capability
    declaration logic the gate bundle uses -- instead of a second resolver.
    """
    source = template_root / ".claude" / "settings.json.tmpl"
    destination = target / ".claude" / "settings.json"
    if not source.is_file():
        return {"schema_version": SCHEMA_VERSION, "operation": "render-agentic-settings",
                "state": "SKIPPED", "reason": "template not found", "source": str(source)}
    values = render_values(project_name, {})
    destination.parent.mkdir(parents=True, exist_ok=True)
    content = rendered(source, values)
    json.loads(content)  # fail closed on a template edit that breaks JSON, never write a broken file
    destination.write_bytes(content)
    return {"schema_version": SCHEMA_VERSION, "operation": "render-agentic-settings", "state": "RENDERED",
            "destination": str(destination),
            "capabilities": {"hybrid_coordinator": values["HYBRID_COORDINATOR_STATE"], "aidb": values["AIDB_STATE"]}}


def status(target: Path, bundle_root: Path, stack: str | None, project_name: str) -> dict[str, Any]:
    receipt = load_json(target / RECEIPT)
    configured = git_value(target, "config", "--get", "core.hooksPath") if (target / ".git").exists() else None
    hooks_dir = target / (configured or HOOKS_PATH)
    executable = {name: (hooks_dir / name).is_file() and os.access(hooks_dir / name, os.X_OK)
                  for name in ("pre-commit", "commit-msg")}
    tracker_paths = [str(path.relative_to(target)) for path in target.glob(".agents/plans/**/tracker.json")]
    state = "ACTIVE" if configured == HOOKS_PATH and all(executable.values()) else "UNCONFIGURED"
    # Checks configuration is re-derived from the CURRENT repo on every call,
    # never read back from the frozen install-time receipt: a package.json
    # that grows a test/lint script after install must be reported CONFIGURED
    # immediately, not stay UNCONFIGURED until the next install/retrofit.
    # Metadata-only, same as preview()/retrofit_preview() -- never executes
    # a target build/test/lint/secret_scan command.
    if receipt:
        try:
            detected = resolver(bundle_root, target, stack)
            commands, blocked = command_values(detected)
            checks = {"commands": commands, "state": "CONFIGURATION_BLOCKED" if blocked else "READY", "required_unconfigured": blocked}
        except RuntimeError as error:
            checks = receipt.get("checks") or {"state": "UNKNOWN", "required_unconfigured": [f"stack detector failed: {error}"]}
    else:
        checks = {"state": "UNKNOWN", "required_unconfigured": ["no install receipt"]}
    return {
        "schema_version": SCHEMA_VERSION, "target": str(target), "operation": "status",
        "installation": {"state": "INSTALLED" if receipt else "ABSENT", "receipt_path": str(RECEIPT)},
        "bundle_version": receipt.get("bundle_version"),
        "hooks": {"state": state, "configured_path": configured, "expected_path": HOOKS_PATH, "executable": executable},
        "checks": checks,
        "tracker": {"state": "DISCOVERED" if tracker_paths else "NONE", "paths": tracker_paths},
        "proof": receipt.get("proof", {"state": "NOT_RUN"}),
        "activation": receipt.get("activation", "ACTIVATION_BLOCKED"),
    }


def evidence_tree_digest(root: Path) -> str:
    """Digest binding readiness evidence to active check config + target source (FT-5 Case 1).

    Mirrors, field for field, the identical algorithm embedded in the
    installed gate-runner's own evidence-record/--preflight steps
    (templates/factory-gate-bundle/gate-runner) so a harness-side
    recomputation matches a target-recorded receipt exactly. Excludes
    .git/ and .factory/ (which holds this receipt, the install receipt,
    backups, and the retained bundle copy -- all of which would make the
    digest self-referential) except .factory/repo-structure.conf, the one
    check-configuration file that lives under .factory/.
    """
    keep = root / ".factory" / "repo-structure.conf"
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        relative = path.relative_to(root)
        parts = relative.parts
        if parts[0] == ".git":
            continue
        if parts[0] == ".factory" and path != keep:
            continue
        digest.update(f"{relative.as_posix()}\0{digest_bytes(path)}\n".encode())
    return digest.hexdigest()


def _execution_evidence_state(target: Path) -> tuple[str | None, dict[str, Any]]:
    """Case 1 anti-gaming: a receipt claim alone never proves fresh execution."""
    evidence_path = target / EVIDENCE_RECEIPT
    if evidence_path.is_symlink() or not evidence_path.is_file():
        return "MISSING_EXECUTION_EVIDENCE", {"present": False, "path": str(EVIDENCE_RECEIPT)}
    recorded = load_json(evidence_path)
    recorded_digest = recorded.get("evidence_digest") if isinstance(recorded, dict) else None
    if not isinstance(recorded_digest, str) or recorded.get("fail_count") != 0:
        return "MISSING_EXECUTION_EVIDENCE", {"present": True, "valid": False, "path": str(EVIDENCE_RECEIPT)}
    current_digest = evidence_tree_digest(target)
    if current_digest != recorded_digest:
        return "STALE_EXECUTION_EVIDENCE", {
            "present": True, "fresh": False, "recorded_digest": recorded_digest, "current_digest": current_digest,
            "generated_at": recorded.get("generated_at"), "mode": recorded.get("mode"),
        }
    return None, {
        "present": True, "fresh": True, "recorded_digest": recorded_digest,
        "generated_at": recorded.get("generated_at"), "mode": recorded.get("mode"),
        "pass_count": recorded.get("pass_count"), "warn_count": recorded.get("warn_count"),
    }


def _run_governance_check(target: Path, relative: str, timeout: int = 30) -> tuple[int, str]:
    """Execute an installed FACTORY governance tool, never a target-declared command.

    hard-10-repo-structure.sh and hard-80-pm-tracker.sh are fixed factory
    tooling wrappers (repo-structure-lint / pm-tracker projector) rendered to
    deterministic harness-relative paths at install time -- never a
    consumer-declared build/test/lint/secret_scan command -- so invoking them
    here is bounded structure/tracker validation, not "target script
    execution" in the sense the metadata-only preflight must refuse.
    """
    path = target / relative
    if not path.is_file() or not os.access(path, os.X_OK):
        return 1, f"{relative} missing or not executable"
    try:
        result = subprocess.run([str(path), "--pre-commit"], cwd=target, capture_output=True, text=True,
                                 timeout=timeout, check=False)
        output = (result.stdout + result.stderr).strip()
        return result.returncode, output[-400:]
    except (OSError, subprocess.TimeoutExpired) as error:
        return 1, str(error)[:200]


def readiness_preflight(target: Path, bundle_root: Path, stack: str | None, project_name: str) -> dict[str, Any]:
    """Metadata-only, non-executing readiness verdict (FT-5).

    Never runs target-declared build/test/lint/secret_scan commands, never
    installs tooling, and never executes documentation-notice prose. Reuses
    the existing installer status, gate runner receipts, structure lint and
    PM tracker check instead of a parallel policy engine.
    """
    report = status(target, bundle_root, stack, project_name)
    blockers: list[dict[str, str]] = []
    coverage: list[dict[str, Any]] = []

    def add(rule: str, check: str, evidence: Any, blocker: str | None, detail: str = "") -> None:
        coverage.append({"rule": rule, "check": check, "evidence": evidence, "blocker": blocker})
        if blocker:
            blockers.append({"code": blocker, "detail": detail or json.dumps(evidence, sort_keys=True)[:200]})

    installed = report["installation"]["state"] == "INSTALLED"
    add("installation", "factory_gate_install.status.installation", report["installation"],
        None if installed else "INSTALLATION_ABSENT",
        "no factory gate install receipt found" if not installed else "")

    hooks = report["hooks"]
    hooks_ok = hooks.get("state") == "ACTIVE" and all(hooks.get("executable", {}).values())
    add("hook_routing", "factory_gate_install.status.hooks", hooks,
        None if hooks_ok else "HOOKS_INVALID",
        f"hooks state={hooks.get('state')} configured_path={hooks.get('configured_path')!r}")

    checks = report["checks"]
    unconfigured = checks.get("required_unconfigured") or []
    hard_unconfigured = [item for item in unconfigured if item.startswith(HARD_CHECK_PREFIXES)]
    checks_ready = not hard_unconfigured
    add("required_checks_configured", "factory_gate_install.status.checks (hard-severity subset)",
        {"required_unconfigured": unconfigured, "hard_blocking": hard_unconfigured},
        None if checks_ready else "CHECKS_UNCONFIGURED", "; ".join(hard_unconfigured))

    # Activation is an aggregate gate: installed + hooks routed + hard checks
    # configured. The frozen install/retrofit receipt's own "activation"
    # field is exposed as evidence only -- it is computed once at install
    # time from the full (structurally WARN-inclusive) unconfigured list and
    # can never turn READY on its own; the aggregate below can.
    activation_ready = installed and hooks_ok and checks_ready
    add("activation", "aggregate: installation + hook_routing + required_checks_configured",
        {"receipt_activation": report.get("activation"), "installed": installed,
         "hooks_ok": hooks_ok, "checks_ready": checks_ready},
        None if activation_ready else "ACTIVATION_BLOCKED",
        f"receipt_activation={report.get('activation')!r}")

    evidence_blocker, evidence_detail = _execution_evidence_state(target)
    add("execution_evidence_freshness", "gate-run-evidence.json digest binding (FT-5 Case 1 anti-gaming)",
        evidence_detail, evidence_blocker)

    if installed:
        layout_rc, layout_detail = _run_governance_check(target, "scripts/governance/checks.d/hard-10-repo-structure.sh")
        add("repository_layout", "checks.d/hard-10-repo-structure.sh", {"exit_code": layout_rc, "detail": layout_detail},
            None if layout_rc == 0 else "LAYOUT_INVALID")

        tracker_rc, tracker_detail = _run_governance_check(target, "scripts/governance/checks.d/hard-80-pm-tracker.sh")
        add("pm_tracker", "checks.d/hard-80-pm-tracker.sh", {"exit_code": tracker_rc, "detail": tracker_detail},
            None if tracker_rc == 0 else "TRACKER_INVALID")
    else:
        add("repository_layout", "checks.d/hard-10-repo-structure.sh", {"skipped": "installation absent"}, None)
        add("pm_tracker", "checks.d/hard-80-pm-tracker.sh", {"skipped": "installation absent"}, None)

    # Absent/unconfigured inference lanes are informational only (FT-5 Case 4
    # / advisory Case 4): they are surfaced for visibility and never added to
    # blockers, so a missing lane can never make readiness_preflight nonzero.
    lanes = {
        "hybrid_coordinator": {
            "state": "CONFIGURED" if os.environ.get("HYBRID_URL") else "TRANSPORT_UNAVAILABLE",
            "detail": "informational only; absent/unconfigured lanes never block readiness",
        }
    }

    ready = not blockers
    return {
        "schema_version": SCHEMA_VERSION,
        "operation": "readiness-preflight",
        "target": str(target),
        "project_name": project_name,
        "ready": ready,
        "state": "READY" if ready else "BLOCKED",
        "blockers": blockers,
        "practice_coverage": coverage,
        "lanes": lanes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("preview", "install", "status", "retrofit-preview", "retrofit-install",
                                               "readiness-preflight", "render-agentic-settings"))
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--bundle-root", type=Path, required=True)
    parser.add_argument("--stack")
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--confirm-retrofit")
    args = parser.parse_args()
    target, bundle_root = args.target.resolve(), args.bundle_root.resolve()
    try:
        if args.operation == "preview":
            result = preview(target, bundle_root, args.stack, args.project_name)
            emit(result)
            return 0 if result["safe_to_install"] else 1
        if args.operation == "install":
            result = install(target, bundle_root, args.stack, args.project_name)
            emit(result)
            return 0 if result.get("installation", {}).get("state") == "INSTALLED" else 1
        if args.operation == "retrofit-preview":
            result = retrofit_preview(target, bundle_root, args.stack, args.project_name)
            emit(result)
            return 0 if result["safe_to_install"] else 1
        if args.operation == "retrofit-install":
            result = retrofit_install(target, bundle_root, args.stack, args.project_name, args.confirm_retrofit)
            emit(result)
            return 0 if result.get("installation", {}).get("state") == "INSTALLED" else 1
        if args.operation == "readiness-preflight":
            result = readiness_preflight(target, bundle_root, args.stack, args.project_name)
            emit(result)
            return 0 if result["ready"] else 1
        if args.operation == "render-agentic-settings":
            # bundle_root is reused as the agentic-workflow template root here
            # (a separate template tree from the gate bundle every other
            # operation resolves it against); see render_agentic_settings().
            result = render_agentic_settings(target, bundle_root, args.project_name)
            emit(result)
            return 0 if result["state"] in ("RENDERED", "SKIPPED") else 1
        return emit(status(target, bundle_root, args.stack, args.project_name))
    except (OSError, RuntimeError, ValueError) as error:
        return emit({"schema_version": SCHEMA_VERSION, "operation": args.operation, "state": "ERROR", "error": str(error)}) or 1


if __name__ == "__main__":
    raise SystemExit(main())
