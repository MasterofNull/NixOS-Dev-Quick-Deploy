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


def run(root: Path, manifest: dict, invoked_skip=None, wf_text=None):
    mf = root / "config" / "ci-checks.json"
    mf.parent.mkdir(parents=True, exist_ok=True)
    mf.write_text(json.dumps(manifest))
    wf = root / "wf"
    wf.mkdir(exist_ok=True)
    if wf_text is None:
        wf_text = "".join(f"run: ./scripts/governance/run-ci-checks.sh --all --only {c['id']}\n"
                          for c in manifest["checks"] if c["id"] not in (invoked_skip or ()))
    (wf / "t.yml").write_text(wf_text)
    p = subprocess.run(["bash", str(GATE)], capture_output=True, text=True,
                       env={**ENV, "CI_TEST_ROOT": str(root), "CI_MANIFEST_FILE": str(mf), "CI_WORKFLOW_DIR": str(wf)})
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
                             "test_exempt": [{"script": "scripts/testing/test-b.sh", "reason": "host-only", "class": "live-service"}]})
        assert rc == 0, (rc, out)
        rc, out = run(root, {"checks": [check("scripts/testing/test-a.py")],
                             "test_exempt": [{"script": "scripts/testing/test-b.sh", "reason": "", "class": "live-service"}]})
        assert rc == 1 and "no reason" in out, (rc, out)
        rc, out = run(root, {"checks": [check("scripts/testing/test-a.py"), check("scripts/testing/test-b.sh")],
                             "test_exempt": [{"script": "scripts/testing/test-gone.py", "reason": "r", "class": "slow"}]})
        assert rc == 1 and "stale" in out, (rc, out)
        rc, out = run(root, {"checks": [check("scripts/testing/test-a.py"), check("scripts/testing/test-b.sh")],
                             "test_exempt": [{"script": "scripts/testing/test-a.py", "reason": "r", "class": "slow"}]})
        assert rc == 1 and "also a checks cmd" in out, (rc, out)
        grp = {**check("scripts/testing/run-test-group.py x"), "tests": ["scripts/testing/test-a.py", "scripts/testing/test-b.sh"]}
        rc, out = run(root, {"checks": [grp]})
        assert rc == 0, (rc, out)
        rc, out = run(root, {"checks": [check("scripts/testing/test-a.py")],
                             "test_exempt": [{"script": "scripts/testing/test-b.sh", "reason": "host-only"}]})
        assert rc == 1 and "class" in out, (rc, out)
        rc, out = run(root, {"checks": [check("scripts/testing/test-a.py")],
                             "test_exempt": [{"script": "scripts/testing/test-b.sh", "reason": "r", "class": "whatever"}]})
        assert rc == 1 and "class" in out, (rc, out)
        rc, out = run(root, {"checks": [check("scripts/testing/test-a.py"), check("scripts/testing/test-b.sh")]}, invoked_skip={"x"})
        assert rc == 1 and "no workflow invokes" in out, (rc, out)
        # the id only in a YAML comment: not an invocation
        rc, out = run(root, {"checks": [check("scripts/testing/test-a.py")]},
                      wf_text="# run: ./scripts/governance/run-ci-checks.sh --all --only x\nrun: echo ok\n")
        assert rc == 1 and "no workflow invokes" in out, (rc, out)
        # the id only in a name: or an echo string: not an invocation
        rc, out = run(root, {"checks": [check("scripts/testing/test-a.py")]},
                      wf_text="name: run-ci-checks.sh --only x\nrun: |\n  echo \"./scripts/governance/run-ci-checks.sh --only x\"\n")
        assert rc == 1 and "no workflow invokes" in out, (rc, out)
    # a red declared test must fail the runner; a green one must pass it
    with tempfile.TemporaryDirectory() as d:
        red, green = Path(d) / "test-red.py", Path(d) / "test-green.py"
        red.write_text("import sys; sys.exit(1)\n")
        green.write_text("")
        for tests, want in (([str(green)], 0), ([str(green), str(red)], 1)):
            mf = Path(d) / "m.json"
            mf.write_text(json.dumps({"checks": [{"id": "g", "cmd": "x", "tests": tests}]}))
            p = subprocess.run([sys.executable, str(REPO / "scripts/testing/run-test-group.py"), "g"],
                               capture_output=True, text=True, env={**ENV, "CI_CHECKS_MANIFEST": str(mf)})
            assert p.returncode == want, (tests, p.returncode, p.stderr)
    print("PASS: gate fails on undeclared/stale/reasonless, passes on declared or exempted; red test fails runner")
    return 0


if __name__ == "__main__":
    sys.exit(main())
