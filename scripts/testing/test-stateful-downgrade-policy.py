#!/usr/bin/env python3
"""Static regression check for stateful service downgrade protection."""

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_SCRIPT = REPO_ROOT / "nixos-quick-deploy.sh"


REQUIRED_SNIPPETS = [
    'STATEFUL_DOWNGRADE_POLICY="${STATEFUL_DOWNGRADE_POLICY:-strict}" # strict|warn',
    "version_lt() {",
    "current_redis_version() {",
    "target_redis_version() {",
    "guard_stateful_service_downgrades() {",
    'case "${STATEFUL_DOWNGRADE_POLICY}" in',
    "guard_stateful_service_downgrades",
]


def main() -> int:
    text = DEPLOY_SCRIPT.read_text(encoding="utf-8")
    missing = [snippet for snippet in REQUIRED_SNIPPETS if snippet not in text]
    if missing:
        print("Stateful downgrade policy regression detected:", file=sys.stderr)
        for snippet in missing:
            print(f"  - {snippet}", file=sys.stderr)
        return 1

    print("PASS: stateful service downgrade protection is wired into deployment")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
