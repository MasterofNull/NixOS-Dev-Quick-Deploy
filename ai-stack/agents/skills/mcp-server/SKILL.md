#!/usr/bin/env python3
"""
# Skill: mcp-server

Wrapper around `scripts/deploy-aidb-mcp-server.sh` so agents can deploy,
inspect, or tail the MCP service deterministically.

Examples:

```bash
python .agent/skills/mcp-server/SKILL.md --action deploy
python .agent/skills/mcp-server/SKILL.md --action status
python .agent/skills/mcp-server/SKILL.md --action logs --tail 200 --follow
```
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def find_repo_root(start: Path) -> Path:
    for parent in [start, *start.parents]:
        if (parent / "nixos-quick-deploy.sh").is_file():
            return parent
        if (parent / "AGENTS.md").is_file() and (parent / "docs").is_dir():
            return parent
    return start.parents[2] if len(start.parents) > 2 else start


REPO_ROOT = find_repo_root(Path(__file__).resolve())
DEPLOY_SCRIPT = REPO_ROOT / "scripts" / "deploy-aidb-mcp-server.sh"


def run(cmd: list[str]) -> int:
    try:
        return subprocess.run(cmd, cwd=REPO_ROOT, check=False).returncode
    except FileNotFoundError as exc:
        print(f"Command not found: {exc}", file=sys.stderr)
        return 1


def deploy() -> int:
    if not DEPLOY_SCRIPT.is_file():
        print(f"Deploy script missing: {DEPLOY_SCRIPT}", file=sys.stderr)
        return 1
    return run([str(DEPLOY_SCRIPT)])


def status() -> int:
    return run(["systemctl", "--user", "status", "aidb-mcp-server"])


def logs(lines: int, follow: bool) -> int:
    cmd = [
        "journalctl",
        "--user",
        "-u",
        "aidb-mcp-server",
        "-n",
        str(lines),
    ]
    if follow:
        cmd.append("-f")
    return run(cmd)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Operate the AIDB MCP server")
    parser.add_argument("--action", choices=["deploy", "status", "logs"], default="status")
    parser.add_argument("--tail", type=int, default=100, help="Lines to tail when --action logs")
    parser.add_argument("--follow", action="store_true", help="Follow logs (only valid for --action logs)")
    args = parser.parse_args(argv)

    if args.action == "deploy":
        return deploy()
    if args.action == "status":
        return status()
    if args.action == "logs":
        return logs(args.tail, args.follow)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
