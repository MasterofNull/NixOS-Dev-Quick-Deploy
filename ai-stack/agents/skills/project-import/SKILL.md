---
name: project-import
description: Instructions and workflow for the project-import skill.
---

#!/usr/bin/env python3
"""
# Skill: project-import

Wrapper around `scripts/sync_docs_to_ai.sh` so agents can push docs into the
AIDB knowledge base without crafting the CLI manually.

Examples:

```bash
python .agent/skills/project-import/SKILL.md --project AI-Optimizer
python .agent/skills/project-import/SKILL.md --docs ../NixOS-Dev-Quick-Deploy/docs --project NixOS-Dev
```
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SYNC_SCRIPT = REPO_ROOT / "scripts" / "sync_docs_to_ai.sh"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync documentation into AIDB")
    parser.add_argument("--docs", type=Path, default=Path("docs"), help="Docs directory (default: %(default)s)")
    parser.add_argument("--project", default="AI-Optimizer", help="Project label used in AIDB")
    parser.add_argument("--base-url", default=os.environ.get("AIDB_BASE_URL", "http://localhost:8091"), help="AIDB base URL")
    parser.add_argument("--dry-run", action="store_true", help="Print the sync command without running it")
    args = parser.parse_args(argv)

    if not SYNC_SCRIPT.is_file():
        parser.error(f"Sync script missing: {SYNC_SCRIPT}")

    docs_dir = args.docs if args.docs.is_absolute() else REPO_ROOT / args.docs
    if not docs_dir.exists():
        parser.error(f"Docs directory not found: {docs_dir}")

    cmd = [str(SYNC_SCRIPT), "--docs", str(docs_dir), "--project", args.project]
    env = os.environ.copy()
    env["AIDB_BASE_URL"] = args.base_url

    print(f"⚙️  Running: {' '.join(cmd)}")
    if args.dry_run:
        print("Dry run enabled. No changes made.")
        return 0

    return subprocess.run(cmd, cwd=REPO_ROOT, env=env, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())

## Maintenance
- Version: 1.0.0
- Keep this skill aligned with current repository workflows.
