#!/usr/bin/env python3
"""Read-only validation and deterministic resolution of the project payload manifest."""
from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

SCHEMA_VERSION = 1
OWNERS = frozenset({"project-init", "gate-bundle", "project-collaboration", "shared-engine"})
PROVIDERS = frozenset({"agentic-workflow-template", "gate-bundle", "fresh-seed", "shared-reference"})
RENDERERS = frozenset({"template", "reference", "seed"})
DISPOSITIONS = frozenset({"create", "preserve", "factory-refresh", "fresh-seed"})
LOCALITIES = frozenset({"project", "shared-reference"})
MODES = frozenset({"greenfield", "brownfield"})
_FORBIDDEN_SOURCE_PARTS = frozenset({"logs", "log", "history", "histories", "queues", "queue", "secrets", "secret", "credentials"})
_RUNTIME_HISTORY_NAMES = frozenset({"PULSE.log", "RESUME.json", "HANDOFF.md", "PENDING.json", "RECOVERY.md"})
CAPABILITY_INTERFACES = ("coordinator", "memory", "model", "tool", "skill", "telemetry", "secret")
_SENSITIVE_COMPONENT = re.compile(r"(?:^|[-_.])(?:secret(?:s)?|credential(?:s)?|private[-_.]?key|api[-_.]?key|token(?:s)?)(?:$|[-_.])", re.IGNORECASE)
_RUNTIME_COMPONENTS = frozenset({"log", "logs", "queue", "queues", "history", "histories"})
_SAFE_SECURITY_CHECK_SOURCE = PurePosixPath(
    "templates/factory-gate-bundle/checks.d/hard-20-secret-scan.sh"
)


class ManifestError(ValueError):
    """The manifest cannot safely describe a project payload."""


def _relative_path(value: Any, label: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise ManifestError(f"{label} must be a non-empty relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise ManifestError(f"{label} must not be absolute or traverse: {value!r}")
    return path


def _validate_source(source: Any, target: str) -> None:
    if not isinstance(source, dict) or source.get("provider") not in PROVIDERS:
        raise ManifestError(f"{target}: unknown or missing source provider")
    provider = source["provider"]
    if provider == "fresh-seed":
        if not isinstance(source.get("seed"), str) or "path" in source:
            raise ManifestError(f"{target}: fresh seed must name a seed and no source path")
        return
    path = _relative_path(source.get("path"), f"{target}: source path")
    parts = tuple(part.lower() for part in path.parts)
    filename = path.name.lower()
    runtime_seed_name = any(
        part == name.lower() or part.startswith(f"{name.lower()}.")
        for part in parts
        for name in _RUNTIME_HISTORY_NAMES
    )
    history_artifact = any(PurePosixPath(part).stem in _RUNTIME_COMPONENTS for part in parts)
    has_sensitive_component = any(_SENSITIVE_COMPONENT.search(part) for part in parts)
    if (any(part in _FORBIDDEN_SOURCE_PARTS for part in parts)
            or (has_sensitive_component and path != _SAFE_SECURITY_CHECK_SOURCE)):
        raise ManifestError(f"{target}: source path vendors forbidden secret/runtime content")
    if (runtime_seed_name or history_artifact or any(part in _RUNTIME_COMPONENTS for part in parts)
            or path.parts[:2] in ((".agent", "archive"), (".agents", "archive"))):
        raise ManifestError(f"{target}: source path vendors runtime history")


def _validate_entry(entry: Any, targets: set[str]) -> None:
    if not isinstance(entry, dict):
        raise ManifestError("inventory entry must be an object")
    target = str(_relative_path(entry.get("target"), "target"))
    if target in targets:
        raise ManifestError(f"duplicate target: {target}")
    targets.add(target)
    if entry.get("functional_owner") not in OWNERS:
        raise ManifestError(f"{target}: unknown functional owner")
    if entry.get("renderer") not in RENDERERS:
        raise ManifestError(f"{target}: unknown renderer")
    if entry.get("disposition") not in DISPOSITIONS:
        raise ManifestError(f"{target}: unknown disposition")
    if entry.get("locality") not in LOCALITIES:
        raise ManifestError(f"{target}: unknown locality")
    if not isinstance(entry.get("required"), bool):
        raise ManifestError(f"{target}: required must be boolean")
    _validate_source(entry.get("source"), target)
    if (entry["renderer"] == "seed") != (entry["source"]["provider"] == "fresh-seed"):
        raise ManifestError(f"{target}: seed renderer/provider mismatch")
    if (entry["disposition"] == "fresh-seed") != (entry["source"]["provider"] == "fresh-seed"):
        raise ManifestError(f"{target}: fresh-seed disposition/provider mismatch")
    if entry["locality"] == "shared-reference" and entry["source"]["provider"] != "shared-reference":
        raise ManifestError(f"{target}: shared reference must use shared-reference provider")
    connection = entry.get("connection")
    if target == ".factory/capability-manifest.json" and connection is None:
        raise ManifestError(f"{target}: capability record requires a typed connection")
    if connection is not None:
        if not isinstance(connection, dict) or connection.get("kind") != "shared-engine-capability-record":
            raise ManifestError(f"{target}: invalid capability connection record")
        if connection.get("states") != ["available", "unavailable", "unauthorized"]:
            raise ManifestError(f"{target}: capability states must be typed and complete")
        if connection.get("interfaces") != list(CAPABILITY_INTERFACES):
            raise ManifestError(f"{target}: capability interfaces must be typed and complete")


def load_manifest(path: str | Path) -> dict[str, Any]:
    """Load and validate a manifest without accessing an installation target."""
    manifest_path = Path(path)
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"cannot load manifest: {exc}") from exc
    if not isinstance(document, dict) or document.get("schema_version") != SCHEMA_VERSION:
        raise ManifestError("unsupported or missing schema_version")
    if not isinstance(document.get("payload_version"), str) or not document["payload_version"]:
        raise ManifestError("missing payload_version")
    inventory = document.get("inventory")
    if not isinstance(inventory, list) or not inventory:
        raise ManifestError("inventory must be a non-empty list")
    targets: set[str] = set()
    for entry in inventory:
        _validate_entry(entry, targets)
    return document


def resolve_inventory(path: str | Path, repository_root: str | Path, mode: str) -> tuple[dict[str, Any], ...]:
    """Return canonical, source-checked inventory for greenfield or brownfield preview.

    This function intentionally never inspects nor modifies a consumer project.
    """
    if mode not in MODES:
        raise ManifestError(f"unknown provisioning mode: {mode}")
    document = load_manifest(path)
    try:
        root = Path(repository_root).resolve(strict=True)
    except OSError as exc:
        raise ManifestError(f"repository root is not accessible: {repository_root}") from exc
    resolved: list[dict[str, Any]] = []
    for entry in document["inventory"]:
        source = entry["source"]
        if source["provider"] != "fresh-seed":
            source_raw = root / source["path"]
            try:
                source_path = source_raw.resolve(strict=True)
            except OSError as exc:
                raise ManifestError(f"{entry['target']}: active source does not exist: {source['path']}") from exc
            if source_path == root or root not in source_path.parents:
                raise ManifestError(f"{entry['target']}: active source escapes repository root")
            if not source_path.is_file() and not source_path.is_dir():
                raise ManifestError(f"{entry['target']}: active source has unsupported type")
        resolved.append(dict(entry))
    return tuple(sorted(resolved, key=lambda item: item["target"]))


def expected_inventory_parity(path: str | Path, repository_root: str | Path) -> tuple[dict[str, Any], ...]:
    """Require greenfield and brownfield previews to name identical functional targets."""
    greenfield = resolve_inventory(path, repository_root, "greenfield")
    brownfield = resolve_inventory(path, repository_root, "brownfield")
    if greenfield != brownfield:
        raise ManifestError("greenfield and brownfield required inventory differs")
    return greenfield
