#!/usr/bin/env python3
"""tier0.d: fail when a config/ci-checks.json "known-failing" test_exempt entry now passes.

A known-failing exemption is never rechecked by CI, so a test whose cause was fixed stays outside
CI (a passing test sat exempt after 974f2a608 fixed it). This gate runs those entries; one that
exits 0 is a stale exemption and FAILs. One that still fails PASSes (with its first output line).
Exit 77 or an entry `needs` tool missing from PATH is SKIP; a timeout counts as still failing.
Selection reuses check-host-only-tests.py (staged script, `paths` globs, module under test):
--pre-commit runs only triggered entries, other modes run all. Skipped under --ci or TIER0_CI=1.
Env overrides: HOST_ONLY_MANIFEST_FILE, HOST_ONLY_ROOT, HOST_ONLY_STAGED (shared with the host-only
gate), STALE_KF_TIMEOUT, STALE_KF_BUDGET.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

TAG = "[tier0.d/check-stale-known-failing]"
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("check_host_only_tests", HERE / "check-host-only-tests.py")
assert spec is not None and spec.loader is not None
host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)

TIMEOUT = int(os.environ.get("STALE_KF_TIMEOUT", "120"))
BUDGET = int(os.environ.get("STALE_KF_BUDGET", "600"))


def first_line(out):
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    return lines[0][:200] if lines else "no output"


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--pre-commit"
    if mode == "--ci" or os.environ.get("TIER0_CI") == "1":
        print(f"{TAG} SKIP: known-failing recheck does not run under --ci")
        return 0
    entries = [e for e in json.loads(host.MANIFEST.read_text()).get("test_exempt", [])
               if e.get("class") == "known-failing"]
    if mode == "--pre-commit":
        try:
            files = host.staged_files()
        except RuntimeError as exc:
            print(f"{TAG} FAIL: {exc}")
            return 1
        selected = [e for e in entries if host.triggered(e, files)]
    else:
        selected = entries
    if not selected:
        print(f"{TAG} PASS: no known-failing test selected for this change")
        return 0
    failed = False
    start = time.monotonic()
    for e in selected:
        script = e["script"]
        absent = [t for t in e.get("needs", []) if shutil.which(t) is None]
        if absent:
            print(f"{TAG} SKIP: {script} (missing host prerequisite: {', '.join(absent)})")
            continue
        if time.monotonic() - start > BUDGET:
            print(f"{TAG} SKIP: {script} (total budget {BUDGET}s exhausted)")
            continue
        try:
            p = subprocess.run(host.runner(script), cwd=host.ROOT, capture_output=True, text=True,
                               timeout=TIMEOUT, stdin=subprocess.DEVNULL, env=host.clean_git_env())
            rc, out = p.returncode, (p.stdout or "") + (p.stderr or "")
        except subprocess.TimeoutExpired:
            print(f"{TAG} PASS: {script} still fails (timed out after {TIMEOUT}s)")
            continue
        if rc == 0:
            print(f"{TAG} FAIL: known-failing exemption is stale: {script} passes — remove the "
                  "test_exempt entry and declare the check")
            failed = True
        elif rc == 77:
            print(f"{TAG} SKIP: {script} (missing host prerequisite: test exited 77)")
        else:
            print(f"{TAG} PASS: {script} still fails (rc={rc}): {first_line(out)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
