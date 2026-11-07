#!/usr/bin/env python3
"""Gate placement: tier0 --pre-commit must be offline and bounded, and must still reject bad staged input.

Runs the real tier0-validation-gate.sh (this tree's version, including uncommitted changes) inside a
throwaway shared clone with fake curl/systemctl on PATH and every service URL pointed at a closed port.
  1. doc-only staged change: exit 0, QA phase 0 is an explicit SKIP naming its owners, no live probe ran.
  2. staged python syntax error: exit != 0 (syntax gate still local).
  3. staged seeded secret: exit != 0 (secret gate still local); skipped with a notice if gitleaks is absent.
  4. --pre-deploy / --maintenance / --ci keep QA phase 0 (HARD); static checks on the owners of moved checks.
Also checks the static ownership claims that make "moved" not mean "dropped".
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/governance/lib"))
from clean_git_env import clean_git_env  # noqa: E402

failures = []


def check(name, cond, detail=""):
    print(("PASS: " if cond else "FAIL: ") + name + ("" if cond else f" -- {detail}"))
    if not cond:
        failures.append(name)


def sh(args, cwd, env=None, timeout=600):
    return subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True, timeout=timeout,
                          stdin=subprocess.DEVNULL)


def build_clone(tmp: Path) -> Path:
    """Shared clone of HEAD plus this working tree's tracked diff and untracked files."""
    env = {**clean_git_env(), "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    clone = tmp / "clone"
    sh(["git", "clone", "-q", "--shared", "--no-checkout", str(REPO), str(clone)], tmp, env)
    sh(["git", "checkout", "-q", "--detach", "HEAD"], clone, env)
    head = sh(["git", "-C", str(REPO), "rev-parse", "HEAD"], tmp, env).stdout.strip()
    sh(["git", "checkout", "-q", "--detach", head], clone, env)
    # make origin/main resolvable for gates that diff against it
    sh(["git", "update-ref", "refs/remotes/origin/main", head], clone, env)
    diff = sh(["git", "-C", str(REPO), "diff", "HEAD", "--binary"], tmp, env).stdout
    if diff.strip():
        p = subprocess.run(["git", "apply", "--whitespace=nowarn", "-"], cwd=clone, input=diff, text=True,
                           env=env, capture_output=True)
        if p.returncode != 0:
            raise SystemExit(f"cannot overlay working tree diff: {p.stderr[:400]}")
    untracked = sh(["git", "-C", str(REPO), "ls-files", "-o", "--exclude-standard", "-z"], tmp, env).stdout
    for rel in filter(None, untracked.split("\0")):
        src = REPO / rel
        if src.is_file():
            dst = clone / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    # the throwaway clone must not look like a dirty tree to the gates: commit the overlay as the base
    sh(["git", "add", "-A"], clone, env)
    sh(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false",
        "commit", "-q", "--no-verify", "--allow-empty", "-m", "base"], clone, env)
    sh(["git", "update-ref", "refs/remotes/origin/main", "HEAD"], clone, env)
    return clone


def fake_bin(tmp: Path) -> tuple[Path, Path]:
    """curl/systemctl/ss stand-ins that log the call and fail, as when the stack is down."""
    b, log = tmp / "bin", tmp / "live-probes.log"
    b.mkdir()
    for tool in ("curl", "systemctl", "ss", "nc"):
        f = b / tool
        f.write_text(f"#!/usr/bin/env bash\necho \"{tool} $*\" >> '{log}'\nexit 7\n")
        f.chmod(0o755)
    return b, log


def tier0(clone: Path, tmp: Path, args, extra_env=None):
    b, log = fake_bin(tmp) if not (tmp / "bin").exists() else (tmp / "bin", tmp / "live-probes.log")
    env = {**clean_git_env(), "PATH": f"{b}:{os.environ['PATH']}", "TIER0_NO_CHECKOUT": "1",
           "HOME": str(tmp / "home"), "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
           "PYTHONDONTWRITEBYTECODE": "1", "AQ_QA_ADMISSION_DISABLE": "1"}
    for var in ("SWITCHBOARD_URL", "HYBRID_URL", "AIDB_URL", "LLAMA_URL", "DASHBOARD_URL", "QDRANT_URL",
                "REDIS_URL", "POSTGRES_URL"):
        env[var] = "http://127.0.0.1:9"  # discard port: nothing listens
    env.update(extra_env or {})
    (tmp / "home").mkdir(exist_ok=True)
    t0 = time.monotonic()
    p = sh(["bash", "scripts/governance/tier0-validation-gate.sh", *args], clone, env)
    return p.returncode, p.stdout + p.stderr, time.monotonic() - t0, log


def static_ownership_checks():
    gate = (REPO / "scripts/governance/tier0-validation-gate.sh").read_text()
    check("tier0 parses --ci and --maintenance", "--maintenance" in gate and "--ci)" in gate.replace("--ci)", "--ci)"))
    check("0.16.2 is a live-service-class id", re.search(r'LIVE_SERVICE_CLASS_IDS="[^"]*\b0\.16\.2\b', gate) is not None)
    hook = (REPO / ".githooks/pre-push").read_text()
    check("pre-push no longer runs CI suites by default",
          "PRE_PUSH_CI_PARITY" in hook and 'run_ci_parity_opt_in "${u_head}" || {' in hook)
    for needle in ("run_upstream_sync_check", "run_push_identity_check", "run_push_secret_scan",
                   "run_push_conflict_probe", "quick-deploy-lint.sh"):
        check(f"pre-push still owns: {needle}", needle in hook)
    wf = (REPO / ".github/workflows/test.yml").read_text()
    check("CI runs workflow-failure-masks (was only a pre-push --changed check)",
          "--only workflow-failure-masks" in wf)
    manifest = json.loads((REPO / "config/ci-checks.json").read_text())
    ids = {c["id"] for c in manifest["checks"]}
    check("this test is registered in config/ci-checks.json", "tier0-gate-placement-tests" in ids)
    check("CI runs this test", "--only tier0-gate-placement-tests" in wf)
    pm = (REPO / "scripts/governance/tier0.d/check-pm-tracker.sh").read_text()
    check("CI (tier0 --ci -> TIER0_CI=1) runs the full fail-closed owner-acceptance check",
          'export TIER0_CI="${CI_MODE}"' in gate and 'TIER0_CI:-0}" != "1"' in pm and "run_full_owner_acceptance" in pm)
    check("pre-push runs the full owner-acceptance check", "check-pm-tracker.sh --owner-acceptance" in hook)
    confine_wf = (REPO / ".github/workflows/confine-tests.yml").read_text()
    check("CI confine-tests.yml runs test-aq-confine.py", "test-aq-confine.py" in confine_wf)
    deploy = (REPO / "scripts/maintenance/aq-deploy-current").read_text()
    check("aq-deploy-current runs aq-qa 0 with AQ_CONFINE_REQUIRE_CONTEXT=1 after the switch",
          "AQ_CONFINE_REQUIRE_CONTEXT=1" in deploy and "aq-qa" in deploy)


def qa_unit_checks():
    """aq-qa --machine never prints nothing; 0.10.66 skips explicitly (never passes) where it cannot run."""
    import io
    from contextlib import redirect_stdout
    sys.path.insert(0, str(REPO / "scripts/testing"))
    from harness_qa.core.result import ResultSet, passed, failed
    from harness_qa.reporters.console import ConsoleReporter
    from harness_qa.phases import phase0
    for label, results, want in (("all-pass", [passed(1, "0.1", "a")], "1 passed"),
                                 ("one-fail", [passed(1, "0.1", "a"), failed(1, "0.2", "b", "why")], "1 failed")):
        buf = io.StringIO()
        with redirect_stdout(buf):
            ConsoleReporter().render(ResultSet(phase="0", results=results, duration_s=1), machine_mode=True)
        out = buf.getvalue()
        check(f"aq-qa --machine ({label}) prints a SUMMARY line", out.strip() != "" and "SUMMARY phase=0" in out and want in out, out)
    class Ctx:
        repo_root = REPO
    orig = phase0._confine_context_gap
    phase0._confine_context_gap = lambda: "systemd user manager unreachable from this process (test)"
    try:
        os.environ.pop("AQ_CONFINE_REQUIRE_CONTEXT", None)
        res = phase0._check_aq_confine_behavioral(Ctx())[0]
        check("0.10.66 in a context that cannot run it is an explicit SKIP with a reason",
              res.status.name == "SKIP" and "pre-deploy" in res.reason and "confine-tests.yml" in res.reason, repr(res))
        os.environ["AQ_CONFINE_REQUIRE_CONTEXT"] = "1"
        res = phase0._check_aq_confine_behavioral(Ctx())[0]
        check("0.10.66 under AQ_CONFINE_REQUIRE_CONTEXT=1 fails instead of skipping", res.status.name == "FAIL", repr(res))
    finally:
        phase0._confine_context_gap = orig
        os.environ.pop("AQ_CONFINE_REQUIRE_CONTEXT", None)


def owner_acceptance_cases():
    """The fetch-dependent owner-acceptance check lives at pre-push/CI/pre-deploy and still fails closed; the
    offline subset at --pre-commit catches a tampered allowlist without a network."""
    genv = {**clean_git_env(), "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}
    with tempfile.TemporaryDirectory(prefix="pm-owner-") as t:
        tmp = Path(t)
        origin, work = tmp / "origin.git", tmp / "work"
        sh(["git", "init", "-q", "--bare", "-b", "main", str(origin)], tmp, genv)
        sh(["git", "init", "-q", "-b", "main", str(work)], tmp, genv)
        for rel in ("scripts/ai/aq-pm-tracker", "scripts/ai/aq-refactor-status", "scripts/ai/lib", "config",
                    "scripts/governance/tier0.d/check-pm-tracker.sh", "scripts/governance/lib"):
            src, dst = REPO / rel, work / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__")) if src.is_dir() else shutil.copy2(src, dst)
        sh(["git", "add", "-A"], work, genv)
        sh(["git", "-c", "commit.gpgsign=false", "commit", "-q", "--no-verify", "-m", "base"], work, genv)
        sh(["git", "remote", "add", "origin", str(origin)], work, genv)
        sh(["git", "push", "-q", "origin", "main"], work, genv)
        gate = "scripts/governance/tier0.d/check-pm-tracker.sh"

        def run(*args):
            p = sh(["bash", gate, *args], work, genv, timeout=120)
            return p.returncode, p.stdout + p.stderr
        rc, out = run("--owner-acceptance")
        check("owner-acceptance (pre-push stage) passes on a clean tree", rc == 0, out[-400:])
        allow = work / "config/pm-tracker-unbacked-owner-acceptances.json"
        orig = allow.read_text()
        d = json.loads(orig)
        d["entries"].append({"plan": "seeded", "item": "bad", "acceptance_sha256": "0" * 64})
        allow.write_text(json.dumps(d))
        rc, out = run("--owner-acceptance")
        check("seeded bad allowlist entry is caught at the pre-push/CI stage", rc != 0 and "allowlist tuple" in out, out[-400:])
        rc, out = run("--pre-commit")
        check("seeded bad allowlist entry is also caught by the offline subset at --pre-commit",
              rc != 0 and "offline subset" in out, out[-400:])
        allow.write_text(orig)
        sh(["git", "remote", "set-url", "origin", str(tmp / "missing.git")], work, genv)
        rc, out = run("--owner-acceptance")
        check("owner-acceptance fails closed when origin cannot be fetched", rc != 0 and "cannot fetch origin/main" in out, out[-400:])
        rc, out = run("--pre-commit")
        check("--pre-commit does not need the network for owner-acceptance", "cannot fetch" not in out and "offline subset" not in out, out[-400:])


def monitor_cases():
    """The scheduled monitor must read an unreachable user manager as a FAILED result, not a skip."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("ai_stack_health_monitor", REPO / "scripts/health/ai-stack-health-monitor.py")
    mon = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mon)
    seen = {}

    class Done:
        returncode, stdout, stderr = 0, "{\"tests\": []}", ""

    def fake_run(argv, **kw):
        seen["env"] = kw.get("env", {})
        return Done()
    real_run = mon.subprocess.run
    mon.subprocess.run = fake_run
    try:
        mon.run_aq_qa("0")
    finally:
        mon.subprocess.run = real_run
    check("health monitor runs aq-qa with AQ_CONFINE_REQUIRE_CONTEXT=1", seen.get("env", {}).get("AQ_CONFINE_REQUIRE_CONTEXT") == "1", str(seen.get("env", {}).get("AQ_CONFINE_REQUIRE_CONTEXT")))
    sys.path.insert(0, str(REPO / "scripts/testing"))
    from harness_qa.phases import phase0
    class Ctx:
        repo_root = REPO
    orig = phase0._confine_context_gap
    phase0._confine_context_gap = lambda: "systemd user manager unreachable from this process (test)"
    old = os.environ.get("AQ_CONFINE_REQUIRE_CONTEXT")
    os.environ["AQ_CONFINE_REQUIRE_CONTEXT"] = seen["env"].get("AQ_CONFINE_REQUIRE_CONTEXT", "")
    try:
        res = phase0._check_aq_confine_behavioral(Ctx())[0]
    finally:
        phase0._confine_context_gap = orig
        if old is None:
            os.environ.pop("AQ_CONFINE_REQUIRE_CONTEXT", None)
        else:
            os.environ["AQ_CONFINE_REQUIRE_CONTEXT"] = old
    out = {"tests": [{"id": res.id, "status": res.status.name.lower(), "description": res.description}]}
    check("unreachable user manager under the monitor environment is a failed monitor result",
          [c["id"] for c in mon.failed_checks(out)] == ["0.10.66"], repr(out))


def pre_push_cases():
    """Every ref update on stdin is validated; a leading delete or clean ref must not hide a later bad publish."""
    genv = {**clean_git_env(), "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}
    zero = "0" * 40
    with tempfile.TemporaryDirectory(prefix="prepush-") as t:
        tmp = Path(t)
        origin, work = tmp / "origin.git", tmp / "work"
        sh(["git", "init", "-q", "--bare", "-b", "main", str(origin)], tmp, genv)
        sh(["git", "init", "-q", "-b", "main", str(work)], tmp, genv)
        for rel in (".githooks/pre-push", "scripts/ai/aq-pm-tracker", "scripts/ai/aq-refactor-status", "scripts/ai/lib", "config",
                    "scripts/governance/tier0.d/check-pm-tracker.sh", "scripts/governance/lib"):
            src, dst = REPO / rel, work / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__")) if src.is_dir() else shutil.copy2(src, dst)
        sh(["git", "add", "-A"], work, genv)
        sh(["git", "-c", "commit.gpgsign=false", "commit", "-q", "--no-verify", "-m", "base"], work, genv)
        sh(["git", "remote", "add", "origin", str(origin)], work, genv)
        sh(["git", "push", "-q", "origin", "main"], work, genv)
        sh(["git", "fetch", "-q", "origin"], work, genv)
        base = sh(["git", "rev-parse", "HEAD"], work, genv).stdout.strip()
        (work / "good.txt").write_text("good\n")
        sh(["git", "add", "-A"], work, genv)
        sh(["git", "-c", "commit.gpgsign=false", "commit", "-q", "--no-verify", "-m", "good"], work, genv)
        good = sh(["git", "rev-parse", "HEAD"], work, genv).stdout.strip()
        sh(["git", "checkout", "-q", "-b", "bad", base], work, genv)
        (work / "bad.txt").write_text("bad\n")
        sh(["git", "add", "-A"], work, genv)
        bad_env = {**genv, "GIT_AUTHOR_EMAIL": "x@localhost", "GIT_COMMITTER_EMAIL": "x@localhost"}
        sh(["git", "-c", "commit.gpgsign=false", "commit", "-q", "--no-verify", "-m", "bad"], work, bad_env)
        bad = sh(["git", "rev-parse", "HEAD"], work, genv).stdout.strip()

        def hook(lines, scan=False, nosync=False):
            env = {**genv, "SKIP_PRE_PUSH_LINT": "true"}
            if not scan:
                env["SKIP_SECRET_SCAN"] = "1"
            if nosync:
                env["SKIP_PRE_PUSH_SYNC_CHECK"] = "true"
            p = subprocess.run(["bash", ".githooks/pre-push", "origin", str(origin)], cwd=work, env=env, text=True,
                               input="".join(lines), capture_output=True, timeout=120)
            return p.returncode, p.stdout + p.stderr
        rc, out = hook([f"refs/heads/good {good} refs/heads/good {zero}\n"])
        check("pre-push accepts a clean publish", rc == 0, out[-400:])
        rc, out = hook([f"(delete) {zero} refs/heads/old {base}\n", f"refs/heads/bad {bad} refs/heads/bad {zero}\n"])
        check("pre-push rejects a bad publish that follows a delete", rc != 0 and "identity" in out, out[-400:])
        rc, out = hook([f"refs/heads/good {good} refs/heads/good {zero}\n", f"refs/heads/bad {bad} refs/heads/bad {zero}\n"])
        check("pre-push rejects a bad second ref after a clean first ref", rc != 0 and "identity" in out, out[-400:])
        rc, out = hook([f"(delete) {zero} refs/heads/old {base}\n"])
        check("pre-push accepts a delete-only push", rc == 0, out[-400:])

        # review-receipts: append-only branch with its own root history (S1 publishes plumbing commits here)
        rrefs = "refs/heads/review-receipts"
        rid = {**genv, "GIT_AUTHOR_NAME": "aq-review-receipt", "GIT_AUTHOR_EMAIL": "aq-review-receipt@noreply.invalid",
               "GIT_COMMITTER_NAME": "aq-review-receipt", "GIT_COMMITTER_EMAIL": "aq-review-receipt@noreply.invalid"}
        empty = sh(["git", "hash-object", "-t", "tree", "-w", "--stdin"], work, genv).stdout.strip() if False else \
            subprocess.run(["git", "mktree"], cwd=work, env=genv, input="", text=True, capture_output=True).stdout.strip()
        root = sh(["git", "commit-tree", empty, "-m", "receipt root"], work, rid).stdout.strip()
        # make the working branch BEHIND its upstream so a global sync check would block the push
        sh(["git", "checkout", "-q", "-b", "behind", base], work, genv)
        sh(["git", "branch", "-q", "--set-upstream-to=origin/main", "behind"], work, genv)
        other = tmp / "other"
        sh(["git", "clone", "-q", str(origin), str(other)], tmp, genv)
        (other / "adv.txt").write_text("adv\n")
        sh(["git", "add", "-A"], other, genv)
        sh(["git", "-c", "commit.gpgsign=false", "commit", "-q", "--no-verify", "-m", "adv"], other, genv)
        sh(["git", "push", "-q", "origin", "main"], other, genv)
        rc, out = hook([f"{rrefs} {root} {rrefs} {zero}\n"])
        check("pre-push accepts an unrelated-history root commit to review-receipts, even from a branch behind its upstream",
              rc == 0 and "conflicts" not in out and "behind" not in out, out[-500:])
        rc, out = hook([f"refs/heads/other {root} refs/heads/other {zero}\n"], nosync=True)
        check("the same unrelated-history commit to another branch only warns about the conflict",
              rc == 0 and "WARNING" in out and "conflicts with" in out, out[-500:])
        rc, out = hook([f"(delete) {zero} refs/heads/old {base}\n"])
        check("a delete-only push skips the sync check even from a branch behind its upstream",
              rc == 0 and "behind" not in out, out[-500:])
        rc, out = hook([])
        check("a manual run with no stdin still runs the sync check", rc != 0 and "behind" in out, out[-500:])
        rc, out = hook([f"{rrefs} {root} {rrefs} {zero}\n", f"refs/heads/bad {bad} refs/heads/bad {zero}\n"], nosync=True)
        check("a mixed push of review-receipts plus a bad branch fails", rc != 0 and "identity" in out, out[-500:])
        rc, out = hook([f"refs/heads/review-receipts-x {bad} refs/heads/review-receipts-x {zero}\n"], nosync=True)
        check("only the exact ref name is exempt (a lookalike ref gets the full checks)", rc != 0 and "identity" in out, out[-500:])
        if shutil.which("gitleaks"):
            fake_key = "AKIA" + "ABCDEFGHIJKLMNOP"
            sec_env = {**rid}
            (work / "r.txt").write_text(f"aws_access_key_id = {fake_key}\naws_secret_access_key = "
                                        f"{'wJalrXUtnFEMI/K7MDENG/bPxRfiCY' + 'EXAMPLEKEY'}\n")
            blob = sh(["git", "hash-object", "-w", "r.txt"], work, genv).stdout.strip()
            tree = subprocess.run(["git", "mktree"], cwd=work, env=genv, input=f"100644 blob {blob}\tr.txt\n", text=True,
                                  capture_output=True).stdout.strip()
            sec = sh(["git", "commit-tree", tree, "-m", "receipt with secret"], work, sec_env).stdout.strip()
            rc, out = hook([f"{rrefs} {sec} {rrefs} {zero}\n"], scan=True)
            check("a secret in a review-receipts commit is still caught", rc != 0 and "gitleaks" in out, out[-500:])
        else:
            print("SKIP-WARN: gitleaks not installed; review-receipts secret case not run")


def main() -> int:
    static_ownership_checks()
    monitor_cases()
    pre_push_cases()
    qa_unit_checks()
    owner_acceptance_cases()
    with tempfile.TemporaryDirectory(prefix="tier0-placement-") as t:
        tmp = Path(t)
        clone = build_clone(tmp)

        # 1. doc-only commit passes with the stack down
        (clone / "docs/harness-first/evidence").mkdir(parents=True, exist_ok=True)
        (clone / "docs/harness-first/evidence/2099-01-01-placement-probe.md").write_text("## Objective\nprobe\n")
        sh(["git", "add", "-A"], clone, clean_git_env())
        rc, out, secs, log = tier0(clone, tmp, ["--pre-commit"])
        check("doc-only staged commit passes tier0 --pre-commit with the live stack down", rc == 0, out[-1500:])
        check("QA phase 0 is an explicit SKIP naming its owners",
              re.search(r"SKIP: QA phase 0.*--pre-deploy.*--maintenance", out) is not None, out[-800:])
        check("harness regression suites are skipped for a doc-only change",
              "SKIP: Harness regression suites" in out, out[-800:])
        probes = log.read_text() if log.exists() else ""
        # aq-pm-tracker projects unit state with systemctl and tolerates it failing; that is projection input, not a gate.
        net = [ln for ln in probes.splitlines() if ln.split(" ", 1)[0] in ("curl", "ss", "nc")]
        check("no HTTP/port probe (curl/ss/nc) ran during a doc-only tier0 --pre-commit", not net, "\n".join(net[:5]))
        print(f"INFO: doc-only tier0 --pre-commit took {secs:.0f}s")
        for line in out.splitlines():
            m = re.search(r"timing: (\S+) (\d+)s", line)
            if m and int(m.group(2)) >= 5:
                print(f"INFO: slow gate {m.group(1)} {m.group(2)}s")

        # 1b. code under a doc directory is code: the suites run
        sh(["git", "reset", "-q"], clone, clean_git_env())
        seeded = clone / ".agent/skills/x/scripts/a.py"
        seeded.parent.mkdir(parents=True, exist_ok=True)
        seeded.write_text("print(1)\n")
        sh(["git", "add", ".agent/skills/x/scripts/a.py"], clone, clean_git_env())
        rc, out, secs, _ = tier0(clone, tmp, ["--pre-commit"], {"TIER0_SUITE_TIMEOUT_SECONDS": "1"})
        check("a staged script under .agent/ runs the harness regression suites",
              "SKIP: Harness regression suites" not in out and "Checking local-agent harness regression suites" in out, out[-800:])
        sh(["git", "rm", "-q", "-f", "--cached", ".agent/skills/x/scripts/a.py"], clone, clean_git_env())
        seeded.unlink()
        sh(["git", "add", "docs/harness-first/evidence/2099-01-01-placement-probe.md"], clone, clean_git_env())

        # 2. syntax error is still rejected locally
        bad_py = clone / "docs/harness-first/evidence/zz_placement_bad.py"
        bad_py.write_text("def broken(:\n    pass\n")
        sh(["git", "add", "-A"], clone, clean_git_env())
        rc, out, secs, _ = tier0(clone, tmp, ["--pre-commit"])
        check("staged python syntax error is rejected at --pre-commit", rc != 0 and "FAIL" in out, out[-800:])
        sh(["git", "rm", "-q", "-f", "--cached", "docs/harness-first/evidence/zz_placement_bad.py"], clone, clean_git_env())
        bad_py.unlink()

        # 3. seeded secret is still rejected locally (needs gitleaks, which the CI-parity gate shells out to)
        if shutil.which("gitleaks"):
            secret = clone / "docs/harness-first/evidence/2099-01-01-secret-probe.md"
            fake_key = "AKIA" + "ABCDEFGHIJKLMNOP"  # assembled so this file itself is not a finding
            secret.write_text(f"aws_access_key_id = {fake_key}\naws_secret_access_key = "
                              f"{'wJalrXUtnFEMI/K7MDENG/bPxRfiCY' + 'EXAMPLEKEY'}\n")
            sh(["git", "add", "-A"], clone, clean_git_env())
            rc, out, secs, _ = tier0(clone, tmp, ["--pre-commit"])
            check("staged seeded secret is rejected at --pre-commit", rc != 0, out[-800:])
        else:
            print("SKIP-WARN: gitleaks not installed; seeded-secret case not run (CI secrets-scan owns it)")

    print(f"SUMMARY: {len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
