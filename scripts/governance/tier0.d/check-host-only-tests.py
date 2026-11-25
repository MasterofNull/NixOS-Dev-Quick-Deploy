#!/usr/bin/env python3
"""tier0.d: run the tests config/ci-checks.json exempts from CI as host-only.

Selects test_exempt entries with class "sandbox-env" (the host-only class CI cannot run) and runs
them on the host so they cannot rot unseen (backlog HOST-ONLY-TESTS-ROT-UNSEEN).
--pre-commit runs only entries whose script is staged, whose optional `paths` globs match a staged
file, or whose module under test (test-<stem>.* -> <stem>.*) is staged. Other modes run all.
A missing host tool (exit 77, or FileNotFoundError / "command not found" / "<tool> not found") is SKIP.
Env overrides: HOST_ONLY_MANIFEST_FILE, HOST_ONLY_ROOT, HOST_ONLY_STAGED, HOST_ONLY_TIMEOUT, HOST_ONLY_BUDGET.
"""
import fnmatch
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

TAG = "[tier0.d/check-host-only-tests]"
REPO = Path(__file__).resolve().parents[3]
ROOT = Path(os.environ.get("HOST_ONLY_ROOT", REPO))
MANIFEST = Path(os.environ.get("HOST_ONLY_MANIFEST_FILE", ROOT / "config/ci-checks.json"))
TIMEOUT = int(os.environ.get("HOST_ONLY_TIMEOUT", "120"))
BUDGET = int(os.environ.get("HOST_ONLY_BUDGET", "600"))
MISSING_TOOL = re.compile(
    r"FileNotFoundError: .*?'([^']+)'|(\S+): command not found|(\S+) not found on PATH")


def staged_files():
    if os.environ.get("HOST_ONLY_STAGED") is not None:
        return [f for f in os.environ["HOST_ONLY_STAGED"].split(",") if f]
    p = subprocess.run(["git", "-C", str(ROOT), "diff", "--cached", "--name-only"],
                       capture_output=True, text=True)
    return [f for f in p.stdout.splitlines() if f]


def triggered(entry, files):
    script = entry["script"]
    stem = re.sub(r"^test-", "", Path(script).stem)
    for f in files:
        if f == script or any(fnmatch.fnmatch(f, g) for g in entry.get("paths", [])):
            return True
        if Path(f).stem == stem:
            return True
    return False


def runner(script):
    return ["bash", script] if script.endswith(".sh") else [sys.executable, script]


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--pre-commit"
    if mode == "--ci":
        print(f"{TAG} SKIP: host-only tests do not run under --ci")
        return 0
    entries = [e for e in json.loads(MANIFEST.read_text()).get("test_exempt", [])
               if e.get("class") == "sandbox-env"]
    if mode == "--pre-commit":
        files = staged_files()
        selected = [e for e in entries if triggered(e, files)]
    else:
        selected = entries
    if not selected:
        print(f"{TAG} PASS: no host-only test selected for this change")
        return 0
    failed = False
    start = time.monotonic()
    for e in selected:
        script = e["script"]
        if time.monotonic() - start > BUDGET:
            print(f"{TAG} SKIP: {script} (total budget {BUDGET}s exhausted)")
            continue
        try:
            p = subprocess.run(runner(script), cwd=ROOT, capture_output=True, text=True,
                               timeout=TIMEOUT, stdin=subprocess.DEVNULL)
            rc, out = p.returncode, (p.stdout or "") + (p.stderr or "")
        except subprocess.TimeoutExpired:
            print(f"{TAG} FAIL: {script} timed out after {TIMEOUT}s")
            failed = True
            continue
        if rc == 0:
            print(f"{TAG} PASS: {script}")
            continue
        m = MISSING_TOOL.search(out)
        if rc == 77 or m:
            tool = next((g for g in m.groups() if g), "unknown") if m else "unspecified"
            print(f"{TAG} SKIP: {script} (missing host prerequisite: {tool})")
            continue
        tail = "\n".join(out.strip().splitlines()[-15:])
        print(f"{TAG} FAIL: {script} (rc={rc})\n{tail}")
        failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
