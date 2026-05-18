#!/usr/bin/env python3
"""Seed capability-domain AIDB namespaces from canonical local sources."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO_ROOT / "config" / "domain-knowledge-seeds.json"
INGEST_SCRIPT = REPO_ROOT / "scripts" / "data" / "ingest-project-knowledge.py"


def _load_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    domains = data.get("domains")
    if not isinstance(domains, list) or not domains:
        raise ValueError("manifest must contain a non-empty 'domains' list")

    seen_projects: set[str] = set()
    for item in domains:
        if not isinstance(item, dict):
            raise ValueError("each domain entry must be an object")
        domain = item.get("domain")
        project = item.get("project")
        paths = item.get("paths")
        if not isinstance(domain, str) or not domain:
            raise ValueError("domain entry missing non-empty 'domain'")
        if not isinstance(project, str) or not project:
            raise ValueError(f"{domain}: missing non-empty 'project'")
        if project in seen_projects:
            raise ValueError(f"duplicate project namespace: {project}")
        if not isinstance(paths, list) or not paths or not all(isinstance(p, str) and p for p in paths):
            raise ValueError(f"{domain}: 'paths' must be a non-empty string list")
        seen_projects.add(project)
    return data


def _missing_paths(paths: list[str]) -> list[str]:
    return [path for path in paths if not (REPO_ROOT / path).exists()]


def _run_seed(
    *,
    domain: str,
    project: str,
    paths: list[str],
    dry_run: bool,
    delay: float,
) -> int:
    cmd = [
        sys.executable,
        str(INGEST_SCRIPT),
        "--project",
        project,
        "--delay",
        str(delay),
        "--paths",
        *paths,
    ]
    if dry_run:
        cmd.insert(2, "--dry-run")

    print(f"[domain-seed] {domain} -> {project}")
    return subprocess.run(cmd, cwd=REPO_ROOT, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed canonical domain AIDB namespaces")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help=f"Seed manifest path (default: {DEFAULT_MANIFEST.relative_to(REPO_ROOT)})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate sources and count candidate chunks without posting to AIDB",
    )
    parser.add_argument(
        "--domain",
        action="append",
        default=[],
        help="Seed only the named domain. Repeat to select multiple domains.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Seconds between POST /documents calls per namespace",
    )
    args = parser.parse_args()

    manifest_path = args.manifest if args.manifest.is_absolute() else REPO_ROOT / args.manifest
    try:
        manifest = _load_manifest(manifest_path)
    except Exception as exc:
        print(f"[domain-seed] invalid manifest: {exc}", file=sys.stderr)
        return 2

    selected_domains = set(args.domain)
    known_domains = {item["domain"] for item in manifest["domains"]}
    unknown_domains = selected_domains - known_domains
    if unknown_domains:
        print(
            f"[domain-seed] unknown domain(s): {', '.join(sorted(unknown_domains))}",
            file=sys.stderr,
        )
        return 2

    statuses: list[tuple[str, str, int]] = []
    for item in manifest["domains"]:
        domain = item["domain"]
        if selected_domains and domain not in selected_domains:
            continue
        project = item["project"]
        paths = item["paths"]
        missing = _missing_paths(paths)
        if missing:
            print(
                f"[domain-seed] {domain}: missing seed paths: {', '.join(missing)}",
                file=sys.stderr,
            )
            statuses.append((domain, project, 2))
            continue

        status = _run_seed(
            domain=domain,
            project=project,
            paths=paths,
            dry_run=args.dry_run,
            delay=args.delay,
        )
        statuses.append((domain, project, status))

    print("\n[domain-seed] summary")
    for domain, project, status in statuses:
        print(f"  {domain:22s} {project:30s} exit={status}")

    return 0 if statuses and all(status == 0 for _, _, status in statuses) else 1


if __name__ == "__main__":
    raise SystemExit(main())
