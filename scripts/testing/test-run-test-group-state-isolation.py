#!/usr/bin/env python3
"""run-test-group.py fails (naming the files) when a test mutates the checkout, and passes a clean one."""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SRC = Path(__file__).resolve().parents[2]


def run_group(tests: dict[str, str]):
    with tempfile.TemporaryDirectory(prefix="aq-rtg-iso-") as d:
        repo = Path(d)
        for rel in ("scripts/testing/run-test-group.py", "scripts/governance/lib/clean_git_env.py"):
            (repo / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(SRC / rel, repo / rel)
        (repo / "config").mkdir()
        for name, body in tests.items():
            (repo / name).write_text(body)
        (repo / "config/ci-checks.json").write_text(json.dumps({"checks": [{"id": "g", "tests": list(tests)}]}))
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "b"], cwd=repo, check=True)
        r = subprocess.run([sys.executable, str(repo / "scripts/testing/run-test-group.py"), "g"],
                           cwd=repo, capture_output=True, text=True)
        return r


MUTATE = "open('.agent-state.txt', 'w').write('x')\n"
CLEAN = "import os, pathlib\npathlib.Path(os.environ['RSI_RUNTIME_DIR']).mkdir(parents=True)\n"

bad = run_group({"t_mutate.py": MUTATE})
assert bad.returncode == 1, bad
assert ".agent-state.txt" in bad.stderr, bad.stderr

good = run_group({"t_clean.py": CLEAN})
assert good.returncode == 0, good.stderr
print("PASS test-run-test-group-state-isolation")
