#!/usr/bin/env python3
"""Regression tests for the 2026-11-06 sweep findings (gates and lanes). Each case fails on the pre-fix code.

  1. every file in tier0.d is picked up by a glob the tier0 runner actually loops over
  2. collect_changed_files: no origin/main widens the scan instead of returning "nothing changed"
  3. pre-merge-commit refuses when its guard script is absent; opt-in pre-push parity refuses when its runners are absent
  4. check-workflow-script-refs fails on a dangling path and passes on a glob mention
  5. the retired Antigravity lane holds no eligibility grant and no egress allowlist
  6. the Codex MCP projection carries semgrep
"""
import fnmatch
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/governance/lib"))
from clean_git_env import clean_git_env  # noqa: E402

TIER0 = REPO / "scripts/governance/tier0-validation-gate.sh"
failures = []


def check(name, cond, detail=""):
    print(("PASS: " if cond else "FAIL: ") + name + ("" if cond else f" -- {detail}"))
    if not cond:
        failures.append(name)


def sandbox_env(home: Path) -> dict:
    return {**clean_git_env(), "HOME": str(home), "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}


def run(args, cwd, env, timeout=60):
    return subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True, timeout=timeout,
                          stdin=subprocess.DEVNULL)


def make_repo(tmp: Path, env) -> Path:
    r = tmp / "repo"
    r.mkdir()
    run(["git", "init", "-q", "-b", "main"], r, env)
    (r / "ok.py").write_text("x = 1\n")
    (r / "notes.md").write_text("doc\n")
    run(["git", "add", "-A"], r, env)
    run(["git", "commit", "-q", "--no-verify", "-m", "base"], r, env)
    return r


def tier0_fn(name: str) -> str:
    m = re.search(rf"^{name}\(\) \{{\n.*?^\}}\n", TIER0.read_text(), flags=re.S | re.M)
    assert m, f"function {name} not found in tier0"
    return m.group(0)


# 1 ---------------------------------------------------------------------------------------------------------
text = TIER0.read_text()
globs = re.findall(r"\"\$\{?TIER0D\}?\"/(\S+?)[;\s]", text)
files = sorted(p.name for p in (REPO / "scripts/governance/tier0.d").iterdir() if p.is_file() and p.name != "README.md")
unrun = [f for f in files if not any(fnmatch.fnmatch(f, g) for g in globs)]
check("tier0.d: every gate file matches a glob the runner loops over", not unrun, f"never run: {unrun}")
check("tier0.d: python gates are run with python3, not bash", re.search(r'\*\.py\b.*|ext_runner=python3', text) is not None
      and "ext_runner=python3" in text)

# 2 ---------------------------------------------------------------------------------------------------------
with tempfile.TemporaryDirectory(prefix="gate-lane-") as d:
    tmp = Path(d)
    (tmp / "home").mkdir()
    env = sandbox_env(tmp / "home")
    repo = make_repo(tmp, env)
    (repo / "bad.py").write_text("def (:\n")
    run(["git", "add", "-A"], repo, env)
    run(["git", "commit", "-q", "--no-verify", "-m", "bad"], repo, env)

    def collect(mode: str) -> subprocess.CompletedProcess:
        return run(["bash", "-c", f"set -u; MODE={mode}; {tier0_fn('collect_changed_files')} collect_changed_files"], repo, env)

    r = collect("--pre-deploy")
    check("collect_changed_files: --pre-deploy with no origin/main still lists the bad file",
          "bad.py" in r.stdout.split(), f"rc={r.returncode} out={r.stdout!r}")

    # the real python gate, with the real collector, on the same input: must FAIL, not "No Python changes detected"
    gate = (f"set -u; MODE=--pre-deploy; log(){{ :; }}; pass(){{ echo PASS \"$*\"; }}; fail(){{ echo FAIL \"$*\"; }}; "
            f"{tier0_fn('collect_changed_files')} {tier0_fn('gate_python_syntax')} gate_python_syntax || true")
    g = run(["bash", "-c", gate], repo, env)
    check("gate_python_syntax: bad file with no origin/main is a FAIL", g.stdout.startswith("FAIL"), g.stdout)

    # with a resolvable base, only the changed files are listed (behaviour that must not change)
    run(["git", "update-ref", "refs/remotes/origin/main", "HEAD~1"], repo, env)
    r = collect("--pre-deploy")
    check("collect_changed_files: with origin/main only the diff is listed", r.stdout.split() == ["bad.py"], r.stdout)
    run(["git", "update-ref", "refs/remotes/origin/main", "HEAD"], repo, env)
    r = collect("--pre-deploy")
    check("collect_changed_files: nothing ahead of origin/main is an empty list", r.returncode == 0 and not r.stdout.strip(),
          r.stdout)

    # pre-commit: staged files only, empty when nothing is staged
    (repo / "staged.py").write_text("y = 2\n")
    run(["git", "add", "staged.py"], repo, env)
    r = collect("--pre-commit")
    check("collect_changed_files: --pre-commit lists only staged files", r.stdout.split() == ["staged.py"], r.stdout)
    run(["git", "reset", "-q"], repo, env)
    r = collect("--pre-commit")
    check("collect_changed_files: --pre-commit with nothing staged is empty (doc-only unchanged)",
          not r.stdout.strip(), r.stdout)

# 3 ---------------------------------------------------------------------------------------------------------
with tempfile.TemporaryDirectory(prefix="gate-lane-") as d:
    tmp = Path(d)
    (tmp / "home").mkdir()
    env = sandbox_env(tmp / "home")
    repo = make_repo(tmp, env)
    r = run(["bash", str(REPO / ".githooks/pre-merge-commit")], repo, env)
    check("pre-merge-commit: missing guard script refuses the merge", r.returncode != 0 and "missing" in r.stderr,
          f"rc={r.returncode} err={r.stderr!r}")

    src = re.search(r"^run_ci_parity_opt_in\(\) \{\n.*?^\}\n", (REPO / ".githooks/pre-push").read_text(), flags=re.S | re.M)
    assert src, "run_ci_parity_opt_in not found in pre-push"
    e2 = {**env, "PRE_PUSH_CI_PARITY": "1"}
    r = run(["bash", "-c", f"{src.group(0)} run_ci_parity_opt_in HEAD"], repo, e2)
    check("pre-push: requested CI parity with its runners absent fails", r.returncode != 0, f"rc={r.returncode} {r.stderr!r}")
    r = run(["bash", "-c", f"{src.group(0)} run_ci_parity_opt_in HEAD"], repo, {**env, "PRE_PUSH_CI_PARITY": "0"})
    check("pre-push: parity stays opt-in (off means no-op)", r.returncode == 0, r.stderr)

# 4 ---------------------------------------------------------------------------------------------------------
with tempfile.TemporaryDirectory(prefix="gate-lane-") as d:
    tmp = Path(d)
    refs = REPO / "scripts/governance/check-workflow-script-refs.sh"
    good = tmp / "glob.yml"
    good.write_text("jobs:\n  a:\n    name: Manifest test groups (every scripts/testing/test-*)\n")
    bad = tmp / "dangling.yml"
    bad.write_text("jobs:\n  a:\n    steps:\n      - run: bash scripts/does-not-exist-zz.sh\n")
    env = sandbox_env(tmp)
    r = run(["bash", str(refs), str(good)], REPO, env)
    check("workflow-script-refs: a glob mention is not a dangling path", r.returncode == 0, r.stdout + r.stderr)
    r = run(["bash", str(refs), str(bad)], REPO, env)
    check("workflow-script-refs: a dangling path fails", r.returncode == 1, r.stdout + r.stderr)

# 5 ---------------------------------------------------------------------------------------------------------
lane = REPO / "scripts/ai/aq-lane-eligibility"
for role in ("research", "reviewer"):
    r = run([sys.executable, str(lane), "check", "antigravity", role, "--json"], REPO, os.environ.copy())
    status = json.loads(r.stdout)["status"] if r.stdout.strip().startswith("{") else r.stdout
    check(f"lane registry: retired antigravity holds no {role} grant", status != "eligible", r.stdout)
r = run([sys.executable, str(lane), "check", "antigravity", "implementer", "--json"], REPO, os.environ.copy())
check("lane registry: antigravity implementer hard block is kept", '"hard-ineligible"' in r.stdout, r.stdout)
for role in ("research", "reviewer"):
    r = run([sys.executable, str(lane), "check", "gemini", role, "--json"], REPO, os.environ.copy())
    check(f"lane registry: gemini {role} grant unaffected", '"status": "eligible"' in r.stdout, r.stdout)

sys.path.insert(0, str(REPO / "scripts/ai/lib"))
import remote_lane_egress as rle  # noqa: E402

cls = [v for k, v in vars(rle).items() if isinstance(v, type) and hasattr(v, "evaluate")]
eng = cls[0](REPO / "config/remote-lane-egress.json") if cls else None
if eng is None:
    check("egress: engine class found", False, "no class with evaluate()")
else:
    for lane_id in ("antigravity", "agy"):
        v = eng.evaluate({"lane": lane_id, "dest_host": "cloudaicompanion.googleapis.com", "dest_port": 443})
        check(f"egress: retired {lane_id} lane is held, not allowlisted", v["action"] == "hold", str(v))
    v = eng.evaluate({"lane": "gemini", "dest_host": "cloudcode-pa.googleapis.com", "dest_port": 443})
    check("egress: live gemini lane still allowlisted", v["reason_code"] == "RULE_ALLOWLISTED", str(v))

# 6 ---------------------------------------------------------------------------------------------------------
base = (REPO / "nix/home/base.nix").read_text()
check("codex MCP projection declares semgrep", '.mcp_servers.semgrep = {' in base)

# 7: wired checks must exist in the manifest and be run by the workflow ----------------------------------------
manifest = json.loads((REPO / "config/ci-checks.json").read_text())
ids = {c["id"] for c in manifest["checks"]}
wf = (REPO / ".github/workflows/test.yml").read_text()
for cid in ("workflow-script-refs", "doc-lifecycle-hygiene", "doc-frontmatter", "agent-context-tooling",
            "context-bootstrap", "aq-integrity-logical-baseline", "gate-lane-findings-tests"):
    check(f"manifest: {cid} is a check and a workflow runs it", cid in ids and cid in wf, f"in manifest={cid in ids} in workflow={cid in wf}")

print()
if failures:
    print(f"FAILED {len(failures)}: {failures}")
    sys.exit(1)
print("all gate/lane finding checks passed")
