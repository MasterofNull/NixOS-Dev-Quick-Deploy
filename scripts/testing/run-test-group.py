#!/usr/bin/env python3
"""Run the `tests` list of one config/ci-checks.json check (usage: run-test-group.py <check-id>).

Each test gets a 120 s timeout, repo-locating GIT_* stripped, stdin closed and a private
AQ_DELEGATION_DIR and no ambient PYTHONPATH so no test touches the shared delegation ledger. Fails if any test fails.
"""
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


def run_one(test: str):
    interp = "python3" if test.endswith(".py") else "bash"
    with tempfile.TemporaryDirectory(prefix="aq-test-group-") as d:
        # PYTHONPATH is dropped: operator shells point it at the MAIN checkout, which shadows this tree's modules.
        # CI_CHECKS_* is dropped: ci-merge-parity exports CI_CHECKS_CHANGED_FILES for its own runner, and tests
        # of that runner must not inherit it.
        env = {**{k: v for k, v in clean_git_env().items() if k != "PYTHONPATH" and not k.startswith("CI_CHECKS_")},
               "TMPDIR": d, "AQ_DELEGATION_DIR": f"{d}/delegation"}
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
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(run_one, entry["tests"]))
    bad = [r for r in results if r[1] != 0]
    for test, rc, tail in bad:
        print(f"FAIL {test} rc={rc}\n{tail}\n", file=sys.stderr)
    print(f"run-test-group {argv[0]}: {len(results) - len(bad)}/{len(results)} passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
