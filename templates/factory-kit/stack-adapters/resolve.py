#!/usr/bin/env python3
"""Inspect root metadata and emit safe, declarative stack gate commands."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tomllib
from pathlib import Path

STACKS = {
    "python": "pyproject.toml", "node": "package.json", "rust": "Cargo.toml",
    "go": "go.mod", "nix": "flake.nix",
}
CHECKS = ("build", "test", "lint", "secret_scan")
PROFILE_DIR = Path(__file__).with_name("profiles")


def unavailable(reason: str) -> dict[str, object]:
    return {"state": "UNCONFIGURED", "command": None, "reason": reason}


def command(value: str, tool: str) -> dict[str, object]:
    if shutil.which(tool) is None:
        return unavailable(f"required tool unavailable: {tool}")
    return {"state": "READY", "command": value, "tool": tool}


def module_command(value: str, module: str) -> dict[str, object]:
    """Keep module-backed commands unconfigured without importing target code."""
    if shutil.which("python") is None:
        return unavailable("required tool unavailable: python")
    return {
        "state": "UNCONFIGURED", "command": value, "requires": ["python", module],
        "reason": "runtime module availability is not verified by metadata-only detection",
    }


def load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def load_toml(path: Path) -> dict[str, object]:
    try:
        value = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def resolve(root: Path, override: str | None = None) -> dict[str, object]:
    found = [stack for stack, marker in STACKS.items() if (root / marker).is_file()]
    if override:
        if override not in (*STACKS, "generic"):
            raise ValueError(f"unsupported stack override: {override}")
        found = [override]
    if not found:
        found = ["generic"]
    profiles = {stack: profile(root, stack) for stack in found}
    return {"root": str(root), "stacks": found, "profiles": profiles}


def profile(root: Path, stack: str) -> dict[str, object]:
    checks = {name: unavailable(f"no safe conventional {name} command declared") for name in CHECKS}
    checks["secret_scan"] = command("gitleaks detect --no-git --redact", "gitleaks")
    marker = STACKS.get(stack)
    if marker and not (root / marker).is_file():
        reason = f"required stack marker absent: {marker}"
        for name in ("build", "test", "lint"):
            checks[name] = unavailable(reason)
        return {"stack": stack, "marker_present": False, "checks": checks}
    if stack == "python":
        data = load_toml(root / "pyproject.toml")
        tools = data.get("tool", {}) if isinstance(data.get("tool"), dict) else {}
        if "pytest" in tools:
            checks["test"] = module_command("python -m pytest", "pytest")
        if "ruff" in tools:
            checks["lint"] = module_command("python -m ruff check .", "ruff")
        if isinstance(data.get("build-system"), dict):
            checks["build"] = module_command("python -m build", "build")
    elif stack == "node":
        scripts = load_json(root / "package.json").get("scripts", {})
        if isinstance(scripts, dict):
            for name in ("build", "test", "lint"):
                if isinstance(scripts.get(name), str) and scripts[name].strip():
                    checks[name] = command(f"npm run {name}", "npm")
    else:
        declared = load_json(PROFILE_DIR / f"{stack}.json").get("commands", {})
        if isinstance(declared, dict):
            for name, spec in declared.items():
                if isinstance(spec, dict) and isinstance(spec.get("command"), str) and isinstance(spec.get("tool"), str):
                    checks[name] = command(spec["command"], spec["tool"])
    return {"stack": stack, "marker_present": marker is not None, "checks": checks}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", type=Path)
    parser.add_argument("--override", choices=(*STACKS, "generic"))
    args = parser.parse_args()
    root = args.repository.resolve()
    if not root.is_dir():
        parser.error(f"not a directory: {root}")
    print(json.dumps(resolve(root, args.override), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
