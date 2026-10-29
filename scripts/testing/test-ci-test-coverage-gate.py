#!/usr/bin/env python3
"""tier0.d/check-ci-test-coverage.sh must fail on an undeclared scripts/testing test and pass once declared or exempted."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GATE = REPO / "scripts/governance/tier0.d/check-ci-test-coverage.sh"
ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def run(root: Path, manifest: dict):
    mf = root / "config" / "ci-checks.json"
    mf.parent.mkdir(parents=True, exist_ok=True)
    mf.write_text(json.dumps(manifest))
    p = subprocess.run(["bash", str(GATE)], capture_output=True, text=True,
                       env={**ENV, "CI_TEST_ROOT": str(root), "CI_MANIFEST_FILE": str(mf)})
    return p.returncode, p.stderr + p.stdout


def check(cmd):
    return {"id": "x", "cmd": cmd, "paths": [], "needs": [], "ci_workflow": ".github/workflows/test.yml#syntax"}


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "scripts/testing").mkdir(parents=True)
        (root / "scripts/testing/test-a.py").write_text("")
        (root / "scripts/testing/test-b.sh").write_text("")
        base = {"checks": [], "test_exempt": []}
        rc, out = run(root, base)
        assert rc == 1 and "test-a.py" in out and "test-b.sh" in out, (rc, out)
        rc, out = run(root, {"checks": [check("scripts/testing/test-a.py"), check("bash scripts/testing/test-b.sh")]})
        assert rc == 0, (rc, out)
        rc, out = run(root, {"checks": [check("scripts/testing/test-a.py")],
                             "test_exempt": [{"script": "scripts/testing/test-b.sh", "reason": "host-only"}]})
        assert rc == 0, (rc, out)
        rc, out = run(root, {"checks": [check("scripts/testing/test-a.py")],
                             "test_exempt": [{"script": "scripts/testing/test-b.sh", "reason": ""}]})
        assert rc == 1 and "no reason" in out, (rc, out)
        rc, out = run(root, {"checks": [check("scripts/testing/test-a.py"), check("scripts/testing/test-b.sh")],
                             "test_exempt": [{"script": "scripts/testing/test-gone.py", "reason": "r"}]})
        assert rc == 1 and "stale" in out, (rc, out)
        rc, out = run(root, {"checks": [check("scripts/testing/test-a.py"), check("scripts/testing/test-b.sh")],
                             "test_exempt": [{"script": "scripts/testing/test-a.py", "reason": "r"}]})
        assert rc == 1 and "also a checks cmd" in out, (rc, out)
        grp = {**check("scripts/testing/run-test-group.py x"), "tests": ["scripts/testing/test-a.py", "scripts/testing/test-b.sh"]}
        rc, out = run(root, {"checks": [grp]})
        assert rc == 0, (rc, out)
    print("PASS: gate fails on undeclared/stale/reasonless, passes on declared or exempted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
