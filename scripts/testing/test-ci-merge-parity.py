#!/usr/bin/env python3
"""Tests for ci-merge-parity.sh and ci-clean-env.sh using throwaway git repo fixtures."""
import json, os, shutil, subprocess, tempfile, unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GOV = REPO / "scripts/governance"
ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"}


def sh(cmd, cwd, **kw):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env={**ENV, **kw.pop("env", {})}, **kw)


def git(cwd, *a):
    r = sh(["git", *a], cwd)
    assert r.returncode == 0, r.stderr
    return r.stdout


def make_repo(tmp):
    """Fixture repo with origin/main; manifest check fails iff file `poison` exists."""
    d = Path(tmp) / "repo"
    (d / "scripts/governance/tier0.d").mkdir(parents=True)
    (d / "config").mkdir()
    (d / ".github/workflows").mkdir(parents=True)
    for n in ("run-ci-checks.sh", "ci-merge-parity.sh", "ci-clean-env.sh"):
        shutil.copy(GOV / n, d / "scripts/governance" / n)
    (d / "scripts/chk.sh").write_text('#!/usr/bin/env bash\n[[ ! -e poison ]] || { echo "poison present"; exit 1; }\n')
    (d / "config/ci-checks.json").write_text(json.dumps({"version": 1, "checks": [
        {"id": "chk", "cmd": "scripts/chk.sh", "paths": [], "needs": [], "ci_workflow": ".github/workflows/w.yml"}], "ci_exempt": []}))
    (d / ".github/workflows/w.yml").write_text("name: w\n")
    git(d, "init", "-q", "-b", "main")
    git(d, "add", "-A"); git(d, "commit", "-qm", "base")
    git(d, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(d, "checkout", "-q", "-b", "feat")
    return d


class MergeParity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ci-parity-test-")
        self.repo = make_repo(self.tmp)

    def tearDown(self):
        shutil.move(self.tmp, self.tmp + ".done")  # archive, never rm

    def parity(self, *a, env=None):
        return sh(["bash", "scripts/governance/ci-merge-parity.sh", *a], self.repo, env={"TMPDIR": self.tmp, **(env or {})})

    def advance_main(self, fname, content):
        git(self.repo, "checkout", "-q", "main")
        Path(self.repo / fname).parent.mkdir(parents=True, exist_ok=True)
        (self.repo / fname).write_text(content)
        git(self.repo, "add", "-A"); git(self.repo, "commit", "-qm", "main moves")
        git(self.repo, "update-ref", "refs/remotes/origin/main", "HEAD")
        git(self.repo, "checkout", "-q", "feat")

    def test_branch_ok_but_fails_after_merging_main(self):
        (self.repo / "feature.txt").write_text("x"); git(self.repo, "add", "-A"); git(self.repo, "commit", "-qm", "f")
        ok = sh(["./scripts/governance/run-ci-checks.sh", "--all"], self.repo)
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)  # branch alone passes
        self.advance_main("poison", "1")
        r = self.parity("--all")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("[FAIL] chk", r.stdout)
        self.assertEqual(git(self.repo, "worktree", "list").count("\n"), 1)  # temp worktree removed

    def test_clean_merge_passes(self):
        (self.repo / "feature.txt").write_text("x"); git(self.repo, "add", "-A"); git(self.repo, "commit", "-qm", "f")
        self.advance_main("other.txt", "1")
        r = self.parity("--all")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_conflict_fails_with_clear_message(self):
        (self.repo / "same.txt").write_text("branch"); git(self.repo, "add", "-A"); git(self.repo, "commit", "-qm", "f")
        self.advance_main("same.txt", "main")
        r = self.parity("--all")
        self.assertEqual(r.returncode, 1)
        self.assertIn("conflicts", r.stderr)
        self.assertIn("Update the branch", r.stderr)

    def test_skip_env_warns_not_silent(self):
        r = self.parity("--all", env={"CI_MERGE_PARITY_SKIP": "1"})
        self.assertEqual(r.returncode, 0)
        self.assertIn("WARN", r.stderr)

    def test_fetch_failure_warns_and_reports_base(self):
        r = self.parity("--all")
        self.assertIn("WARN: cannot fetch base", r.stderr)
        self.assertIn("BASE=origin/main", r.stdout)
        self.assertIn("uncommitted changes NOT included", r.stdout)

    def test_selection_uses_pr_diff_not_main_delta(self):
        m = json.loads((self.repo / "config/ci-checks.json").read_text())
        m["checks"].append({"id": "scoped", "cmd": "scripts/chk.sh", "paths": ["docs/**"], "needs": [], "ci_workflow": ".github/workflows/w.yml"})
        (self.repo / "config/ci-checks.json").write_text(json.dumps(m))
        git(self.repo, "add", "-A"); git(self.repo, "commit", "-qm", "m")
        git(self.repo, "update-ref", "refs/remotes/origin/main", "HEAD")
        (self.repo / "feature.txt").write_text("x"); git(self.repo, "add", "-A"); git(self.repo, "commit", "-qm", "f")
        self.advance_main("docs/m.md", "1")  # main-only docs change
        r = self.parity()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("] chk:", r.stdout)
        self.assertNotIn("] scoped:", r.stdout)


class CleanEnv(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ci-clean-test-")
        self.repo = make_repo(self.tmp)
        (self.repo / "scripts/chk.sh").write_text('#!/usr/bin/env bash\npython3 -c "import yaml" || { echo "missing yaml"; exit 1; }\n')

    def tearDown(self):
        shutil.move(self.tmp, self.tmp + ".done")

    def run_clean(self, reqs_text, extra_env=None):
        reqs = Path(self.tmp) / "reqs.txt"
        reqs.write_text(reqs_text)
        return sh(["bash", "scripts/governance/ci-clean-env.sh", "--all"], self.repo,
                  env={"CI_CLEAN_ENV_REQS": str(reqs), "TMPDIR": self.tmp, **(extra_env or {})})

    def test_missing_requirement_fails_check_not_passes(self):
        r = self.run_clean("# none\n")
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("[FAIL] chk", r.stdout)
        self.assertEqual([p for p in Path(self.tmp).glob("ci-clean-env-*")], [])  # venv cleaned up

    def test_unavailable_requirement_aborts_explicitly(self):
        r = self.run_clean("definitely-not-a-real-pkg-xyz\n", {"PIP_NO_INDEX": "1"})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("NOT running checks", r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
