#!/usr/bin/env bash
# Run path-aware CI-sensitive checks for changed files.
# Checks are defined in config/validation-check-registry.json — edit that file to add new checks.
# Usage: ./scripts/governance/run-focused-ci-checks.sh [--pre-commit|--pre-deploy]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

export REGISTRY="${REPO_ROOT}/config/validation-check-registry.json"
export MODE="${1:---pre-commit}"

collect_changed_files() {
  if [[ "${MODE}" == "--pre-commit" ]]; then
    git diff --cached --name-only --diff-filter=ACM 2>/dev/null || true
    return 0
  fi

  {
    git diff --name-only --diff-filter=ACM origin/main...HEAD 2>/dev/null || true
    git diff --name-only --diff-filter=ACM 2>/dev/null || true
  } | awk 'NF && !seen[$0]++'
}


if [[ ! -f "${REGISTRY}" ]]; then
  echo "[focused-ci] WARN: registry not found at ${REGISTRY} — no path-gated checks run"
  exit 0
fi

# Read registry and dispatch checks
python3 - <<'PYEOF'
import json, os, subprocess, sys, shlex

registry_path = os.environ.get("REGISTRY", "config/validation-check-registry.json")
mode = os.environ.get("MODE", "--pre-commit")

with open(registry_path) as f:
    registry = json.load(f)

import subprocess as sp

def collect_changed_files(mode):
    if mode == "--pre-commit":
        r = sp.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
                   capture_output=True, text=True)
        return set(r.stdout.splitlines())
    else:
        r1 = sp.run(["git", "diff", "--name-only", "--diff-filter=ACM", "origin/main...HEAD"],
                    capture_output=True, text=True)
        r2 = sp.run(["git", "diff", "--name-only", "--diff-filter=ACM"],
                    capture_output=True, text=True)
        return set(r1.stdout.splitlines()) | set(r2.stdout.splitlines())

staged = collect_changed_files(mode)
ran_any = False
any_failed = False

for check in registry.get("checks", []):
    if not check.get("enabled", True):
        continue

    check_id = check["id"]
    desc = check["description"]
    triggers = check.get("trigger_paths", [])
    cmd = check["command"]
    timeout = check.get("timeout_seconds", 0) or None
    require_tool = check.get("require_tool")

    # Check tool availability
    if require_tool:
        import shutil
        if not shutil.which(require_tool):
            print(f"[focused-ci] SKIP ({check_id}): '{require_tool}' not in PATH")
            continue

    # Check if any trigger path is staged
    if not any(t in staged for t in triggers):
        continue

    ran_any = True
    print(f"[focused-ci] RUN: {desc}")
    try:
        result = sp.run(cmd, timeout=timeout)
        if result.returncode == 0:
            print(f"[focused-ci] PASS: {desc}")
        else:
            print(f"[focused-ci] FAIL: {desc}", file=sys.stderr)
            any_failed = True
    except sp.TimeoutExpired:
        print(f"[focused-ci] FAIL: {desc} (timed out after {timeout}s)", file=sys.stderr)
        any_failed = True
    except FileNotFoundError as e:
        print(f"[focused-ci] FAIL: {desc} — command not found: {e}", file=sys.stderr)
        any_failed = True

if not ran_any:
    print("[focused-ci] SKIP: no CI-sensitive changed paths detected")

sys.exit(1 if any_failed else 0)
PYEOF
