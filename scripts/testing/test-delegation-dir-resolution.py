#!/usr/bin/env python3
"""A delegate script run from a git worktree must use the MAIN repo's delegation dir."""
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        main_repo = Path(td) / "main"
        (main_repo / "scripts").mkdir(parents=True)
        shutil.copytree(REPO_ROOT / "scripts" / "ai", main_repo / "scripts" / "ai")
        git(main_repo, "init", "-q")
        git(main_repo, "add", "-A")
        git(main_repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")
        wt = Path(td) / "wt"
        git(main_repo, "worktree", "add", "-q", "-b", "wt-branch", str(wt))

        outputs = main_repo / ".agents" / "delegation" / "outputs"
        outputs.mkdir(parents=True)
        today = datetime.now().strftime("%Y%m%d")
        (outputs / f"codex-{today}-aaa111.log").write_text("tokens used\n12,345\n")

        env = {k: v for k, v in os.environ.items()
               if k not in ("AQ_DELEGATION_DIR", "DELEGATE_OUTPUTS_DIR")}
        r = subprocess.run(
            ["bash", str(wt / "scripts" / "ai" / "delegate-to-codex"), "--budget-check-only"],
            capture_output=True, text=True, env=env, cwd=wt)
        out = r.stdout + r.stderr
        if "12345" not in out.replace(",", ""):
            print(f"FAIL: worktree run did not count main-repo logs (rc={r.returncode}):\n{out}")
            return 1
        if (wt / ".agents" / "delegation" / "outputs").exists():
            print("FAIL: worktree-local delegation outputs dir was created")
            return 1
        print("PASS: worktree --budget-check-only counts main repo outputs (12345 tokens)")

        # Missing lib: fallback must warn on stderr naming the path used.
        nolib = Path(td) / "nolib"
        (nolib / "scripts").mkdir(parents=True)
        shutil.copytree(REPO_ROOT / "scripts" / "ai", nolib / "scripts" / "ai")
        (nolib / "scripts" / "ai" / "lib" / "delegation-dir.sh").unlink()
        r = subprocess.run(
            ["bash", str(nolib / "scripts" / "ai" / "delegate-to-codex"), "--budget-check-only"],
            capture_output=True, text=True, env=env, cwd=nolib)
        if "delegation-dir.sh not sourceable" not in r.stderr:
            print(f"FAIL: no fallback warning when lib missing:\n{r.stderr}")
            return 1
        print("PASS: missing delegation-dir.sh emits fallback warning")

        # aq-review-receipt main root must match delegation_dir.py from a worktree.
        sys.path.insert(0, str(REPO_ROOT / "scripts" / "ai" / "lib"))
        from delegation_dir import resolve_main_root
        expected = resolve_main_root(wt / "scripts" / "ai")
        if expected.resolve() != main_repo.resolve():
            print(f"FAIL: resolve_main_root={expected} != {main_repo}")
            return 1
        probe = (
            "import importlib.machinery,importlib.util,sys;"
            "l=importlib.machinery.SourceFileLoader('r',sys.argv[1]);"
            "m=importlib.util.module_from_spec(importlib.util.spec_from_loader('r',l));"
            "l.exec_module(m);print(m.MAIN_ROOT)"
        )
        r = subprocess.run([sys.executable, "-c", probe, str(wt / "scripts" / "ai" / "aq-review-receipt")],
                           capture_output=True, text=True, env=env, cwd=wt)
        if r.stdout.strip() != str(expected):
            print(f"FAIL: aq-review-receipt MAIN_ROOT {r.stdout.strip()!r} != {str(expected)!r}\n{r.stderr}")
            return 1
        print("PASS: aq-review-receipt MAIN_ROOT matches delegation_dir.py from worktree")
        return 0


if __name__ == "__main__":
    sys.exit(main())
