#!/usr/bin/env python3
"""Verify that top-level requirements remain covered by a hash-bearing lockfile."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


REQ_NAME_PATTERN = re.compile(r"^\s*([A-Za-z0-9_.-]+)(?:\[([^\]]+)\])?")
LOCK_NAME_PATTERN = re.compile(r"^\s*([A-Za-z0-9_.-]+)(?:\[([^\]]+)\])?==([^\s\\]+)")

EXTRAS_LOCK_ALIASES: dict[tuple[str, frozenset[str]], tuple[str, ...]] = {
    ("psycopg", frozenset({"binary"})): ("psycopg-binary",),
    ("psycopg", frozenset({"binary", "pool"})): ("psycopg-binary", "psycopg-pool"),
    ("redis", frozenset({"hiredis"})): ("redis", "hiredis"),
    ("uvicorn", frozenset({"standard"})): ("uvicorn",),
}


def _normalize(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def _strip_inline_comment(line: str) -> str:
    return line.split("#", 1)[0].strip()


def _requirement_candidates(name: str, extras: tuple[str, ...]) -> tuple[str, ...]:
    normalized_name = _normalize(name)
    normalized_extras = frozenset(_normalize(extra) for extra in extras if extra.strip())
    if not normalized_extras:
        return (normalized_name,)
    alias = EXTRAS_LOCK_ALIASES.get((normalized_name, normalized_extras))
    if alias:
        return alias
    return (normalized_name,)


def _parse_requirement(raw: str) -> tuple[tuple[str, ...], str] | None:
    line = _strip_inline_comment(raw)
    if not line or line.startswith("#") or line.startswith("-"):
        return None
    match = REQ_NAME_PATTERN.match(line)
    if not match:
        return None
    extras = tuple(
        _normalize(extra)
        for extra in (match.group(2) or "").split(",")
        if extra.strip()
    )
    return _requirement_candidates(match.group(1), extras), raw.strip()


def _load_top_level_requirements(path: Path) -> list[tuple[tuple[str, ...], str]]:
    requirements: list[tuple[tuple[str, ...], str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_requirement(raw)
        if parsed is not None:
            requirements.append(parsed)
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
        match = LOCK_NAME_PATTERN.match(line)
        if not match:
            continue
        locked[_normalize(match.group(1))] = match.group(3)
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

    for candidates, source_line in top_level:
        if not any(locked.get(candidate) is not None for candidate in candidates):
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
