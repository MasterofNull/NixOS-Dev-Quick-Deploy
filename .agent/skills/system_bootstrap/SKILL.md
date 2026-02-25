---
name: system_bootstrap
description: Instructions and workflow for the system_bootstrap skill.
---

#!/usr/bin/env python3
"""
Run the canonical health check (and optional doc sync) so agents can verify the
stack before delegating work.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
HEALTH_SCRIPT = REPO_ROOT / "scripts" / "test_services.sh"
WORKFLOW_SCRIPT = REPO_ROOT / "scripts" / "test_real_world_workflows.sh"


def run(script: Path, label: str) -> int:
    if not script.is_file():
        print(f"{label} script missing: {script}", file=sys.stderr)
        return 1
    print(f"▶ {label}")
    return subprocess.run([str(script)], cwd=REPO_ROOT, check=False).returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bootstrap verifier for AI-Optimizer")
    parser.add_argument("--skip-health", action="store_true", help="Skip service health checks")
    parser.add_argument("--skip-workflows", action="store_true", help="Skip workflow tests")
    args = parser.parse_args(argv)

    if not args.skip_health and run(HEALTH_SCRIPT, "Service health") != 0:
        return 1

    if not args.skip_workflows and run(WORKFLOW_SCRIPT, "Workflow validation") != 0:
        return 1

    print("✅ system_bootstrap complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

## Maintenance
- Version: 1.0.0
- Keep this skill aligned with current repository workflows.
