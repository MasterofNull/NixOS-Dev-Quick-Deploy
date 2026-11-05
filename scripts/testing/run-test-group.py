#!/usr/bin/env python3
"""Run the `tests` list of one config/ci-checks.json check (usage: run-test-group.py <check-id>).

State paths (RSI ledger/backlog, on-call, triage) are pointed at the per-test temp dir, and the group fails,
naming the files, if `git status` (paths + content hashes) differs after the run (P0.6: tests cannot mutate live state).

Each test gets a 120 s timeout, repo-locating GIT_* stripped, stdin closed and a private
AQ_DELEGATION_DIR and no ambient PYTHONPATH so no test touches the shared delegation ledger. Fails if any test fails.
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/governance/lib"))
from clean_git_env import clean_git_env  # noqa: E402

TIMEOUT = 120


def tree_state() -> dict:
    """{porcelain line: content hash} so a re-edit of an already-dirty file is also seen."""
    out = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain", "--untracked-files=all"],
                         capture_output=True, text=True, env=clean_git_env()).stdout.splitlines()
    state = {}
    for line in out:
        f = REPO / line[3:].split(" -> ")[-1]
        state[line] = hashlib.sha256(f.read_bytes()).hexdigest() if f.is_file() else ""
    return state


def run_one(test: str):
    interp = "python3" if test.endswith(".py") else "bash"
    with tempfile.TemporaryDirectory(prefix="aq-test-group-") as d:
        # PYTHONPATH is dropped: operator shells point it at the MAIN checkout, which shadows this tree's modules.
        # CI_CHECKS_* is dropped: ci-merge-parity exports CI_CHECKS_CHANGED_FILES for its own runner, and tests
        # of that runner must not inherit it.
        env = {**{k: v for k, v in clean_git_env().items() if k != "PYTHONPATH" and not k.startswith("CI_CHECKS_")},
               "TMPDIR": d, "AQ_DELEGATION_DIR": f"{d}/delegation",
               "RSI_RUNTIME_DIR": f"{d}/rsi", "RSI_BACKLOG_FILE": f"{d}/issues-backlog.md",
               "PRSI_INCIDENTS_FILE": f"{d}/rsi/rsi-incidents.json",
               "AQ_ONCALL_STATE_DIR": f"{d}/oncall", "AQ_TRIAGE_STATE_DIR": f"{d}/triage",
               "PULSE_LOG_PATH": f"{d}/PULSE.log", "RESUME_JSON_PATH": f"{d}/RESUME.json"}
        try:
            r = subprocess.run([interp, test], cwd=REPO, env=env, stdin=subprocess.DEVNULL,
                               capture_output=True, text=True, timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            return test, 124, f"timeout after {TIMEOUT}s"
    tail = "\n".join((r.stdout + r.stderr).strip().splitlines()[-8:])
    return test, r.returncode, tail


def main(argv) -> int:
    if len(argv) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    manifest = json.load(open(os.environ.get("CI_CHECKS_MANIFEST", REPO / "config/ci-checks.json")))
    entry = next((c for c in manifest["checks"] if c["id"] == argv[0]), None)
    if entry is None or not entry.get("tests"):
        print(f"FAIL: no check '{argv[0]}' with a tests list", file=sys.stderr)
        return 2
    before = tree_state()
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(run_one, entry["tests"]))
    after = tree_state()
    mutated = sorted({k[3:] for k in before.keys() ^ after.keys()} |
                     {k[3:] for k in before.keys() & after.keys() if before[k] != after[k]})
    if mutated:
        print(f"FAIL {argv[0]}: tests mutated the checkout (state must go to temp dirs): {', '.join(mutated)}",
              file=sys.stderr)
    bad = [r for r in results if r[1] != 0]
    for test, rc, tail in bad:
        print(f"FAIL {test} rc={rc}\n{tail}\n", file=sys.stderr)
    print(f"run-test-group {argv[0]}: {len(results) - len(bad)}/{len(results)} passed")
    return 1 if bad or mutated else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
