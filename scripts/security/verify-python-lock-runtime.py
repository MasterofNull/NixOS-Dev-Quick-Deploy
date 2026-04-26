#!/usr/bin/env python3
"""Verify that top-level requirements remain covered by a hash-bearing lockfile."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


REQ_PATTERN = re.compile(r"^\s*([A-Za-z0-9_.-]+)(?:\[.*\])?")
LOCK_PATTERN = re.compile(r"^\s*([A-Za-z0-9_.-]+)==([^\s\\]+)")


def _normalize(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def _load_top_level_requirements(path: Path) -> dict[str, str]:
    requirements: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        match = REQ_PATTERN.match(line)
        if not match:
            continue
        requirements[_normalize(match.group(1))] = line
    return requirements


def _load_locked_versions(path: Path) -> tuple[dict[str, str], bool]:
    locked: dict[str, str] = {}
    saw_hash = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("--hash="):
            saw_hash = True
            continue
        match = LOCK_PATTERN.match(line)
        if not match:
            continue
        locked[_normalize(match.group(1))] = match.group(2)
    return locked, saw_hash


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--service", required=True)
    parser.add_argument("--requirements", required=True)
    parser.add_argument("--lock", required=True)
    args = parser.parse_args()

    req_path = Path(args.requirements)
    lock_path = Path(args.lock)

    if not req_path.exists() or not lock_path.exists():
        print(
            json.dumps(
                {
                    "event": "dependency_hash_mismatch",
                    "service": args.service,
                    "reason": "missing_requirements_or_lockfile",
                    "requirements": str(req_path),
                    "lockfile": str(lock_path),
                }
            ),
            file=sys.stderr,
        )
        return 1

    top_level = _load_top_level_requirements(req_path)
    locked, saw_hash = _load_locked_versions(lock_path)

    missing_from_lock: list[str] = []

    for name, source_line in sorted(top_level.items()):
        if locked.get(name) is None:
            missing_from_lock.append(source_line)

    if missing_from_lock or not saw_hash:
        print(
            json.dumps(
                {
                    "event": "dependency_hash_mismatch",
                    "service": args.service,
                    "requirements": str(req_path),
                    "lockfile": str(lock_path),
                    "missing_from_lock": missing_from_lock,
                    "hashes_present": saw_hash,
                }
            ),
            file=sys.stderr,
        )
        return 1

    print(
        json.dumps(
            {
                "event": "dependency_lock_verified",
                "service": args.service,
                "requirements": str(req_path),
                "lockfile": str(lock_path),
                "validated_packages": len(top_level),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
