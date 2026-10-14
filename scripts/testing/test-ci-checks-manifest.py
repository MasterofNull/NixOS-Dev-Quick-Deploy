#!/usr/bin/env python3
"""Tests for config/ci-checks.json, run-ci-checks.sh selection, and the tier0.d coverage check."""
import json, os, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "config/ci-checks.json"
RUNNER = ROOT / "scripts/governance/run-ci-checks.sh"
COVER = ROOT / "scripts/governance/tier0.d/check-ci-manifest-coverage.sh"

def run(cmd, **env):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, env={**os.environ, **env})

def test_schema():
    m = json.loads(MANIFEST.read_text())
    ids = [c["id"] for c in m["checks"]]
    assert len(ids) == len(set(ids)), "duplicate ids"
    for c in m["checks"]:
        for k in ("id", "cmd", "paths", "needs", "ci_workflow"):
            assert k in c, f"{c.get('id')} missing {k}"
        assert (ROOT / c["cmd"].split()[0]).is_file(), f"{c['id']} script missing"
        assert isinstance(c["paths"], list) and isinstance(c["needs"], list)
        wf = c["ci_workflow"].split("#")[0]
        assert (ROOT / wf).is_file(), f"{c['id']} workflow missing"
    for e in m["ci_exempt"]:
        assert e.get("script") and e.get("reason")

def selected(files):
    r = run([str(RUNNER), "--list", "--changed"], CI_CHECKS_CHANGED_FILES="\n".join(files))
    assert r.returncode == 0, r.stderr
    return set(r.stdout.split())

def test_changed_selection():
    always = {c["id"] for c in json.loads(MANIFEST.read_text())["checks"] if not c["paths"]}
    assert selected(["README.md"]) == always
    s = selected(["templates/foo/bar.tmpl"])
    assert "template-placeholders" in s and "skill-template" not in s
    s = selected([".agent/skills/x/SKILL.md"])
    assert {"skill-source-of-truth", "skill-template", "skill-external-deps"} <= s
    assert "validate-echo-colors" in selected(["scripts/a/b.sh"])
    assert "validate-echo-colors" not in selected(["docs/a.md"])

def test_only_unknown_fails():
    assert run([str(RUNNER), "--all", "--only", "nope"]).returncode == 2

def test_missing_tool_warns_and_fail_exits_nonzero():
    with tempfile.TemporaryDirectory() as d:
        mf = Path(d) / "m.json"
        mf.write_text(json.dumps({"checks": [
            {"id": "a", "cmd": "scripts/governance/check-world-writable.sh", "paths": [], "needs": ["no-such-tool-xyz"], "ci_workflow": "x"},
            {"id": "b", "cmd": "scripts/does-not-exist.sh", "paths": [], "needs": [], "ci_workflow": "x"}]}))
        r = run([str(RUNNER), "--all"], CI_CHECKS_MANIFEST=str(mf))
        assert "[WARN] a" in r.stdout and "[FAIL] b" in r.stdout and r.returncode == 1, r.stdout

def _mf(d, tool):
    mf = Path(d) / "m.json"
    mf.write_text(json.dumps({"checks": [{"id": "a", "cmd": "scripts/governance/check-world-writable.sh", "paths": ["x/**"], "needs": [tool], "ci_workflow": "x"}]}))
    return str(mf)

def test_ci_true_missing_tool_fails():
    with tempfile.TemporaryDirectory() as d:
        r = run([str(RUNNER), "--all"], CI_CHECKS_MANIFEST=_mf(d, "no-such-tool-xyz"), CI="true")
        assert r.returncode == 1 and "[FAIL] a" in r.stdout, r.stdout

def test_diff_failure_runs_all():
    with tempfile.TemporaryDirectory() as d:
        r = run([str(RUNNER), "--changed", "--base", "no-such-ref-xyz"], CI_CHECKS_MANIFEST=_mf(d, "find"))
        assert "running ALL" in r.stderr and "[PASS] a" in r.stdout, (r.stdout, r.stderr)

def test_coverage_missing_paths():
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "config").mkdir()
        mf = Path(d) / "config/ci-checks.json"
        mf.write_text(json.dumps({"checks": [], "ci_exempt": [{"script": "scripts/gone.sh", "reason": "r"}]}))
        wf = Path(d) / "wf"; wf.mkdir()
        r = run([str(COVER)], CI_MANIFEST_FILE=str(mf), CI_WORKFLOW_DIR=str(wf))
        assert r.returncode == 1 and "gone.sh" in r.stderr

def test_coverage():
    assert run([str(COVER)]).returncode == 0
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "x.yml").write_text("jobs:\n  j:\n    steps:\n      - run: ./scripts/testing/brand-new-gate.sh\n")
        r = run([str(COVER)], CI_WORKFLOW_DIR=d)
        assert r.returncode == 1 and "brand-new-gate.sh" in r.stderr

if __name__ == "__main__":
    fails = 0
    for n, f in sorted(globals().items()):
        if n.startswith("test_"):
            try: f(); print(f"PASS {n}")
            except Exception as e: fails += 1; print(f"FAIL {n}: {e}")
    sys.exit(1 if fails else 0)
