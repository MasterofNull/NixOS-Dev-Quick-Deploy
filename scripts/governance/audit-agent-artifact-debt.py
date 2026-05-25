#!/usr/bin/env python3
"""Audit agent artifact stores that can accumulate stale context.

The script is read-only by default. It reports transient agent outputs, cache
directories, old scratch/session files, and active-looking nested workspaces
that should be summarized, archived, or pruned.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]

TRANSIENT_ROOTS = [
    Path(".agents/delegation/outputs"),
    Path(".agents/sessions"),
    Path(".agents/scratchpad"),
    Path(".agent/comms"),
]

AUTHORITY_DRIFT_ROOTS = [
    Path(".agent/workflows"),
    Path(".agents/planning"),
    Path(".agents/summary"),
]

CACHE_DIR_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".cache",
}

NESTED_AGENT_DIR_NAMES = {
    ".agent",
    ".agents",
    ".claude",
}

DEFAULT_OLD_DAYS = 14
DEFAULT_LARGE_BYTES = 1_000_000
DEFAULT_PULSE_BYTES = 256 * 1024


@dataclass(frozen=True)
class FileFinding:
    path: Path
    size: int
    age_days: float
    reason: str

    def as_dict(self) -> dict[str, object]:
        return {
            "path": self.path.as_posix(),
            "size_bytes": self.size,
            "age_days": round(self.age_days, 1),
            "reason": self.reason,
        }


def repo_path(path: Path) -> Path:
    return ROOT / path


def rel(path: Path) -> Path:
    try:
        return path.relative_to(ROOT)
    except ValueError:
        return path


def file_age_days(path: Path, now: float) -> float:
    return max(0.0, (now - path.stat().st_mtime) / 86400.0)


def iter_files(roots: Iterable[Path]) -> Iterable[Path]:
    for root in roots:
        full = repo_path(root)
        if not full.exists():
            continue
        if full.is_file():
            yield full
            continue
        for path in full.rglob("*"):
            if path.is_file():
                yield path


def directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def count_files(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return 1
    return sum(1 for p in path.rglob("*") if p.is_file())


def git_tracked(path: Path) -> bool:
    try:
        subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "--error-unmatch", "--", path.as_posix()],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def find_cache_dirs() -> list[Path]:
    ignored_names = {".git", "node_modules", ".direnv", ".devenv"}
    findings: list[Path] = []
    for dirpath, dirnames, _filenames in os.walk(ROOT):
        current = Path(dirpath)
        dirnames[:] = [
            name
            for name in dirnames
            if name not in ignored_names and name not in CACHE_DIR_NAMES
        ]
        for name in set(os.listdir(current)).intersection(CACHE_DIR_NAMES):
            cache_path = current / name
            if cache_path.is_dir():
                findings.append(rel(cache_path))
    return sorted(findings)


def find_nested_agent_dirs() -> list[Path]:
    roots = [repo_path(Path(".agent/workflows")), repo_path(Path("archive"))]
    findings: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_dir() and path.name in NESTED_AGENT_DIR_NAMES:
                findings.append(rel(path))
    return sorted(findings)


def classify_files(
    paths: Iterable[Path],
    now: float,
    old_days: int,
    large_bytes: int,
) -> list[FileFinding]:
    findings: list[FileFinding] = []
    for path in paths:
        stat = path.stat()
        age = file_age_days(path, now)
        reasons: list[str] = []
        if stat.st_size >= large_bytes:
            reasons.append("large")
        if age >= old_days:
            reasons.append("old")
        if not git_tracked(rel(path)):
            reasons.append("untracked")
        if reasons:
            findings.append(
                FileFinding(
                    path=rel(path),
                    size=stat.st_size,
                    age_days=age,
                    reason=",".join(reasons),
                )
            )
    return sorted(findings, key=lambda item: item.size, reverse=True)


def format_size(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MiB"
    if size >= 1024:
        return f"{size / 1024:.1f} KiB"
    return f"{size} B"


def build_report(args: argparse.Namespace) -> tuple[dict[str, object], bool]:
    now = time.time()
    transient_summary = []
    for root in TRANSIENT_ROOTS:
        full = repo_path(root)
        transient_summary.append(
            {
                "path": root.as_posix(),
                "exists": full.exists(),
                "files": count_files(full),
                "size_bytes": directory_size(full),
            }
        )

    drift_summary = []
    for root in AUTHORITY_DRIFT_ROOTS:
        full = repo_path(root)
        drift_summary.append(
            {
                "path": root.as_posix(),
                "exists": full.exists(),
                "files": count_files(full),
                "size_bytes": directory_size(full),
            }
        )

    transient_findings = classify_files(
        iter_files(TRANSIENT_ROOTS),
        now=now,
        old_days=args.old_days,
        large_bytes=args.large_bytes,
    )
    drift_findings = classify_files(
        iter_files(AUTHORITY_DRIFT_ROOTS),
        now=now,
        old_days=args.old_days,
        large_bytes=args.large_bytes,
    )

    pulse = repo_path(Path(".agent/collaboration/PULSE.log"))
    pulse_size = pulse.stat().st_size if pulse.exists() else 0
    pulse_warn = pulse_size >= args.pulse_bytes

    cache_dirs = find_cache_dirs()
    nested_agent_dirs = find_nested_agent_dirs()

    warning_count = (
        len(transient_findings)
        + len(drift_findings)
        + len(cache_dirs)
        + len(nested_agent_dirs)
        + (1 if pulse_warn else 0)
    )

    report: dict[str, object] = {
        "status": "WARN" if warning_count else "PASS",
        "warning_count": warning_count,
        "thresholds": {
            "old_days": args.old_days,
            "large_bytes": args.large_bytes,
            "pulse_bytes": args.pulse_bytes,
        },
        "transient_roots": transient_summary,
        "authority_drift_roots": drift_summary,
        "transient_findings": [item.as_dict() for item in transient_findings[: args.limit]],
        "authority_drift_findings": [item.as_dict() for item in drift_findings[: args.limit]],
        "cache_dirs": [p.as_posix() for p in cache_dirs[: args.limit]],
        "nested_agent_dirs": [p.as_posix() for p in nested_agent_dirs[: args.limit]],
        "pulse_log": {
            "path": ".agent/collaboration/PULSE.log",
            "exists": pulse.exists(),
            "size_bytes": pulse_size,
            "warn": pulse_warn,
        },
        "policy": "docs/operations/agent-artifact-gc-policy.md",
    }
    return report, warning_count > 0


def print_human(report: dict[str, object]) -> None:
    print(f"[agent-artifact-gc] {report['status']}: {report['warning_count']} cleanup signals")
    print(f"[agent-artifact-gc] Policy: {report['policy']}")

    print("\nTransient stores:")
    for item in report["transient_roots"]:  # type: ignore[index]
        print(
            "  - {path}: {files} files, {size}".format(
                path=item["path"],
                files=item["files"],
                size=format_size(int(item["size_bytes"])),
            )
        )

    print("\nAuthority-drift stores:")
    for item in report["authority_drift_roots"]:  # type: ignore[index]
        print(
            "  - {path}: {files} files, {size}".format(
                path=item["path"],
                files=item["files"],
                size=format_size(int(item["size_bytes"])),
            )
        )

    pulse = report["pulse_log"]  # type: ignore[assignment]
    if pulse["exists"]:  # type: ignore[index]
        marker = "WARN" if pulse["warn"] else "OK"  # type: ignore[index]
        print(
            f"\nPulse log: {marker} {pulse['path']} is "
            f"{format_size(int(pulse['size_bytes']))}"
        )

    for title, key in (
        ("Transient findings", "transient_findings"),
        ("Authority-drift findings", "authority_drift_findings"),
        ("Cache directories", "cache_dirs"),
        ("Nested agent directories", "nested_agent_dirs"),
    ):
        values = report[key]  # type: ignore[index]
        if not values:
            continue
        print(f"\n{title}:")
        for item in values:
            if isinstance(item, dict):
                print(
                    "  - {path} ({size}; {reason}; {age} days old)".format(
                        path=item["path"],
                        size=format_size(int(item["size_bytes"])),
                        reason=item["reason"],
                        age=item["age_days"],
                    )
                )
            else:
                print(f"  - {item}")

    print("\nNo files were deleted. Promote useful lessons before pruning raw artifacts.")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON report")
    parser.add_argument("--strict", action="store_true", help="exit nonzero on warnings")
    parser.add_argument("--old-days", type=int, default=DEFAULT_OLD_DAYS)
    parser.add_argument("--large-bytes", type=int, default=DEFAULT_LARGE_BYTES)
    parser.add_argument("--pulse-bytes", type=int, default=DEFAULT_PULSE_BYTES)
    parser.add_argument("--limit", type=int, default=25)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    report, has_warnings = build_report(args)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_human(report)
    return 1 if args.strict and has_warnings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
