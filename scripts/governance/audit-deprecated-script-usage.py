#!/usr/bin/env python3
"""Rank deprecated scripts by active repo references and classify keep vs archive."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"

DEPRECATION_PATTERNS = (
    "is deprecated.",
    "This script is deprecated.",
    "legacy component is deprecated.",
    "deprecated and disabled.",
)

EXCLUDED_PREFIXES = (
    "archive/",
    "docs/archive/",
    ".git/",
)

SELF_AUDIT_PATHS = {
    "docs/operations/deprecated-script-audit.md",
    "docs/operations/deprecated-script-audit.json",
}


@dataclass
class RefCounts:
    code: int = 0
    docs: int = 0
    tests: int = 0
    nix: int = 0
    other: int = 0
    archive: int = 0

    @property
    def active_total(self) -> int:
        return self.code + self.docs + self.tests + self.nix + self.other


@dataclass
class AuditRow:
    path: str
    active_references: int
    code_references: int
    docs_references: int
    test_references: int
    nix_references: int
    other_references: int
    archive_references: int
    recommendation: str
    rationale: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out", help="Write JSON results to this path.")
    parser.add_argument("--markdown-out", help="Write Markdown report to this path.")
    return parser.parse_args()


def tracked_files() -> list[Path]:
    proc = subprocess.run(
        ["git", "ls-files", "scripts"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [REPO_ROOT / line for line in proc.stdout.splitlines() if line]


def is_deprecated_script(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    head = "\n".join(text.splitlines()[:8])
    return any(marker in head for marker in DEPRECATION_PATTERNS)


def categorize_ref(ref_path: str) -> str:
    ref_path = ref_path.removeprefix("./")
    if ref_path.startswith(EXCLUDED_PREFIXES):
        return "archive"
    if ref_path.startswith("docs/"):
        return "docs"
    if ref_path.startswith("scripts/testing/"):
        return "tests"
    if ref_path.startswith("scripts/"):
        return "code"
    if ref_path.startswith("nix/") or ref_path == "nixos-quick-deploy.sh" or ref_path == "flake.nix":
        return "nix"
    return "other"


def reference_counts(target: str) -> RefCounts:
    proc = subprocess.run(
        ["rg", "-n", "-F", target, "--glob", "!archive/**", "--glob", "!docs/archive/**", "."],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    counts = RefCounts()
    for line in proc.stdout.splitlines():
        rel_path = line.split(":", 1)[0].removeprefix("./")
        if rel_path == target or rel_path in SELF_AUDIT_PATHS:
            continue
        category = categorize_ref(rel_path)
        if category == "code":
            counts.code += 1
        elif category == "docs":
            counts.docs += 1
        elif category == "tests":
            counts.tests += 1
        elif category == "nix":
            counts.nix += 1
        elif category == "archive":
            counts.archive += 1
        else:
            counts.other += 1

    archive_proc = subprocess.run(
        ["rg", "-n", "-F", target, "archive", "docs/archive"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    archive_refs = {
        line.split(":", 1)[0]
        for line in archive_proc.stdout.splitlines()
        if line and line.split(":", 1)[0].removeprefix("./") not in {target, *SELF_AUDIT_PATHS}
    }
    counts.archive += len(archive_refs)
    return counts


def recommendation(path: str, counts: RefCounts) -> tuple[str, str]:
    runtime_signal = counts.code + counts.tests + counts.nix
    doc_signal = counts.docs + counts.other
    if runtime_signal > 0:
        reasons = []
        if counts.code:
            reasons.append(f"{counts.code} code")
        if counts.tests:
            reasons.append(f"{counts.tests} test")
        if counts.nix:
            reasons.append(f"{counts.nix} nix/deploy")
        return "keep_as_shim", f"runtime references remain ({', '.join(reasons)})"
    if doc_signal >= 5:
        reasons = []
        if counts.docs:
            reasons.append(f"{counts.docs} doc")
        if counts.other:
            reasons.append(f"{counts.other} other")
        return "keep_as_shim", f"widely referenced in active docs/workflows ({', '.join(reasons)})"
    if counts.active_total > 0:
        return "archive_or_remove", "only low-signal references remain; remove after doc cleanup"
    return "archive_or_remove", "no active non-archive references found"


def build_rows() -> list[AuditRow]:
    rows: list[AuditRow] = []
    for path in tracked_files():
        if not is_deprecated_script(path):
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        counts = reference_counts(rel)
        rec, rationale = recommendation(rel, counts)
        rows.append(
            AuditRow(
                path=rel,
                active_references=counts.active_total,
                code_references=counts.code,
                docs_references=counts.docs,
                test_references=counts.tests,
                nix_references=counts.nix,
                other_references=counts.other,
                archive_references=counts.archive,
                recommendation=rec,
                rationale=rationale,
            )
        )
    rows.sort(
        key=lambda row: (
            -row.active_references,
            -row.code_references,
            -row.docs_references,
            row.path,
        )
    )
    return rows


def markdown_report(rows: list[AuditRow]) -> str:
    keep = [row for row in rows if row.recommendation == "keep_as_shim"]
    archive = [row for row in rows if row.recommendation == "archive_or_remove"]

    def table(items: list[AuditRow]) -> str:
        lines = [
            "| Script | Active refs | Code | Docs | Tests | Nix | Archive | Rationale |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
        for row in items:
            lines.append(
                f"| `{row.path}` | {row.active_references} | {row.code_references} | "
                f"{row.docs_references} | {row.test_references} | {row.nix_references} | "
                f"{row.archive_references} | {row.rationale} |"
            )
        if len(lines) == 2:
            lines.append("| _none_ | 0 | 0 | 0 | 0 | 0 | 0 | - |")
        return "\n".join(lines)

    top = rows[:10]
    lines = [
        "# Deprecated Script Audit",
        "Status: Active",
        "Owner: AI Stack Maintainers",
        f"Last Updated: {dt.date.today().isoformat()}",
        "",
        "Generated from active repo references under `scripts/`, `docs/`, `nix/`, and top-level deployment files.",
        "",
        "## Top Remaining Deprecated Scripts",
        "",
        table(top),
        "",
        "## Keep As Shim",
        "",
        table(keep),
        "",
        "## Archive Or Remove",
        "",
        table(archive),
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    rows = build_rows()
    payload = [asdict(row) for row in rows]
    if args.json_out:
        out = REPO_ROOT / args.json_out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if args.markdown_out:
        out = REPO_ROOT / args.markdown_out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(markdown_report(rows) + "\n", encoding="utf-8")
    if not args.json_out and not args.markdown_out:
        print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
