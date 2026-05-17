#!/usr/bin/env python3
"""Static regression check for blocking post-flight health policy."""

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_SCRIPT = REPO_ROOT / "nixos-quick-deploy.sh"


REQUIRED_SNIPPETS = [
    'POST_FLIGHT_HEALTH_POLICY="${POST_FLIGHT_HEALTH_POLICY:-strict}" # strict|warn',
    "run_required_postflight_check() {",
    'case "${POST_FLIGHT_HEALTH_POLICY}" in',
    'Expected: strict|warn.',
    'run_required_postflight_check \\\n      "Running post-deploy health check"',
    'run_required_postflight_check \\\n      "Running AI stack MCP health check"',
]


def main() -> int:
    text = DEPLOY_SCRIPT.read_text(encoding="utf-8")
    missing = [snippet for snippet in REQUIRED_SNIPPETS if snippet not in text]
    if missing:
        print("Post-flight health policy regression detected:", file=sys.stderr)
        for snippet in missing:
            print(f"  - {snippet}", file=sys.stderr)
        return 1

    print("PASS: post-flight health checks are strict by default")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
