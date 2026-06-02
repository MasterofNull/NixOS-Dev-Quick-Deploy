#!/usr/bin/env bash
# Run path-aware CI-sensitive checks for changed files.
# Checks are defined in config/validation-check-registry.json — edit that file to add new checks.
# Usage: ./scripts/governance/run-focused-ci-checks.sh [--pre-commit|--pre-deploy]
#
# Optional env vars:
#   FOCUSED_CI_JSON=<path>  Write structured check results to this JSON file (93.10)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

export REGISTRY="${REGISTRY:-${REPO_ROOT}/config/validation-check-registry.json}"
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
import json, os, subprocess, sys, shlex, time

registry_path = os.environ.get("REGISTRY", "config/validation-check-registry.json")
mode = os.environ.get("MODE", "--pre-commit")
json_out_path = os.environ.get("FOCUSED_CI_JSON", "").strip()

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

# JSON diagnostic accumulator (93.10)
check_results = []

def _tail(text: str, n: int = 20) -> str:
    lines = text.splitlines()
    return "\n".join(lines[-n:]) if lines else ""

for check in registry.get("checks", []):
    if not check.get("enabled", True):
        continue

    check_id = check["id"]
    desc = check["description"]
    triggers = check.get("trigger_paths", [])
    cmd = check["command"]
    timeout = check.get("timeout_seconds", 0) or None
    require_tool = check.get("require_tool")
    pass_staged = check.get("pass_staged_files", False)

    # Check tool availability
    if require_tool:
        import shutil
        if not shutil.which(require_tool):
            print(f"[focused-ci] SKIP ({check_id}): '{require_tool}' not in PATH")
            if json_out_path:
                check_results.append({
                    "check_id": check_id,
                    "description": desc,
                    "trigger_paths_matched": [],
                    "command": cmd,
                    "status": "skip",
                    "skip_reason": f"required tool '{require_tool}' not in PATH",
                    "duration_ms": None,
                    "exit_code": None,
                    "stdout_tail": "",
                    "stderr_tail": "",
                })
            continue

    def matches_trigger(path, trigger):
        trigger = trigger.rstrip("/")
        return path == trigger or path.startswith(trigger + "/")

    matched_paths = [
        path for path in staged for trigger in triggers
        if matches_trigger(path, trigger)
    ]
    # deduplicate matched paths, preserve order
    seen_paths = set()
    unique_matched = []
    for p in matched_paths:
        if p not in seen_paths:
            seen_paths.add(p)
            unique_matched.append(p)
    matched_paths = unique_matched

    if not matched_paths:
        continue

    ran_any = True

    # Build final command, appending staged files when registry requests it
    final_cmd = list(cmd)
    if pass_staged and matched_paths:
        final_cmd.extend(matched_paths)

    print(f"[focused-ci] RUN: {desc}")
    t0 = time.monotonic()
    result_status = "pass"
    exit_code = 0
    stdout_captured = ""
    stderr_captured = ""
    try:
        result = sp.run(final_cmd, timeout=timeout, capture_output=True, text=True)
        exit_code = result.returncode
        stdout_captured = result.stdout
        stderr_captured = result.stderr
        # Print through for human-readable output (backward compat)
        if stdout_captured:
            sys.stdout.write(stdout_captured)
        if stderr_captured:
            sys.stderr.write(stderr_captured)
        if exit_code == 0:
            print(f"[focused-ci] PASS: {desc}")
        else:
            print(f"[focused-ci] FAIL: {desc}", file=sys.stderr)
            any_failed = True
            result_status = "fail"
    except sp.TimeoutExpired as exc:
        elapsed = time.monotonic() - t0
        stdout_captured = (exc.stdout or b"").decode("utf-8", errors="replace")
        stderr_captured = (exc.stderr or b"").decode("utf-8", errors="replace")
        if stdout_captured:
            sys.stdout.write(stdout_captured)
        if stderr_captured:
            sys.stderr.write(stderr_captured)
        print(f"[focused-ci] FAIL: {desc} (timed out after {timeout}s)", file=sys.stderr)
        any_failed = True
        result_status = "timeout"
        exit_code = -1
    except FileNotFoundError as e:
        print(f"[focused-ci] FAIL: {desc} — command not found: {e}", file=sys.stderr)
        any_failed = True
        result_status = "fail"
        exit_code = -1
        stderr_captured = str(e)

    duration_ms = round((time.monotonic() - t0) * 1000, 1)

    if json_out_path:
        check_results.append({
            "check_id": check_id,
            "description": desc,
            "trigger_paths_matched": matched_paths,
            "command": final_cmd,
            "status": result_status,
            "skip_reason": None,
            "duration_ms": duration_ms,
            "exit_code": exit_code,
            "stdout_tail": _tail(stdout_captured),
            "stderr_tail": _tail(stderr_captured),
        })

if not ran_any:
    print("[focused-ci] SKIP: no CI-sensitive changed paths detected")

# Write JSON diagnostic output if requested (93.10 / 94.3).
# Always write when json_out_path is set — even on skip — so validation_health
# in aq-report reflects the latest gate result rather than staying no_data.
if json_out_path:
    import datetime
    doc = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "mode": mode,
        "overall_status": "fail" if any_failed else ("pass" if ran_any else "skip"),
        "checks_ran": sum(1 for r in check_results if r["status"] not in ("skip",)),
        "checks_passed": sum(1 for r in check_results if r["status"] == "pass"),
        "checks_failed": sum(1 for r in check_results if r["status"] in ("fail", "timeout")),
        "checks_skipped": sum(1 for r in check_results if r["status"] == "skip"),
        "checks": check_results,
    }
    try:
        import pathlib
        pathlib.Path(json_out_path).parent.mkdir(parents=True, exist_ok=True)
        with open(json_out_path, "w") as jf:
            json.dump(doc, jf, indent=2)
    except Exception as exc:
        print(f"[focused-ci] WARN: could not write JSON to {json_out_path}: {exc}", file=sys.stderr)

sys.exit(1 if any_failed else 0)
PYEOF
