#!/usr/bin/env python3
"""Hermetic failure matrix for delegated worktree isolation."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "scripts/ai/lib/worktree-isolation.sh"
CODEX = ROOT / "scripts/ai/delegate-to-codex"
LOCAL = ROOT / "scripts/ai/delegate-to-local"
GIT = shutil.which("git")
assert GIT, "git is required for this fixture"


def run(args, *, env=None, check=True):
    result = subprocess.run(args, env=env, text=True, capture_output=True)
    if check and result.returncode:
        raise AssertionError(f"command failed ({result.returncode}): {args}\n{result.stderr}")
    return result


def bash(script, *, env=None, check=True):
    return run(["bash", "-c", script], env=env, check=check)


def git(repo, *args, check=True):
    return run([GIT, "-C", str(repo), *args], check=check)


for path in (HELPER, CODEX, LOCAL):
    run(["bash", "-n", str(path)])

# Explicit shared editing remains denied without launching a provider.
assert run([str(CODEX), "--shared", "--mode", "edit", "--prompt", "fixture"], check=False).returncode
assert run([str(LOCAL), "--shared", "--mode", "agent", "--prompt", "fixture", "--no-consult"], check=False).returncode

with tempfile.TemporaryDirectory(prefix="worktree-isolation-") as temp:
    repo = Path(temp) / "repo"
    git(Path(temp), "init", "-q", str(repo))
    git(repo, "config", "user.email", "fixture@example.invalid")
    git(repo, "config", "user.name", "fixture")
    (repo / "base.txt").write_text("base\n")
    git(repo, "add", "base.txt")
    git(repo, "commit", "-qm", "base")
    shared_head = git(repo, "rev-parse", "HEAD").stdout.strip()

    blocked_path = repo / ".agents/delegation/worktrees/task-blocked"
    blocked_path.mkdir(parents=True)
    assert bash(f'source "{HELPER}"; wt_create "{repo}" task-blocked', check=False).returncode
    assert bash(f'source "{HELPER}"; wt_create "{repo}" ../escape', check=False).returncode

    wt = Path(bash(f'source "{HELPER}"; wt_create "{repo}" task-safe').stdout.strip())
    assert wt.is_dir()
    assert git(repo, "rev-parse", "refs/delegate-base/task-safe").stdout.strip() == shared_head

    # The saved dispatch base cannot move when the shared checkout moves.
    (repo / "shared-after-dispatch.txt").write_text("later\n")
    git(repo, "add", "shared-after-dispatch.txt")
    git(repo, "commit", "-qm", "shared moves")
    assert git(repo, "rev-parse", "refs/delegate-base/task-safe").stdout.strip() == shared_head
    assert git(repo, "diff", "--cached", "--quiet", check=False).returncode == 0

    other = Path(bash(f'source "{HELPER}"; wt_create "{repo}" task-other').stdout.strip())
    assert bash(f'source "{HELPER}"; wt_validate "{repo}" "{repo}" task-safe', check=False).returncode
    assert bash(f'source "{HELPER}"; wt_validate "{repo}" "{other}" task-safe', check=False).returncode
    git(wt, "checkout", "-qb", "wrong-branch")
    assert bash(f'source "{HELPER}"; wt_validate "{repo}" "{wt}" task-safe', check=False).returncode
    git(wt, "checkout", "-q", "delegate/task-safe")
    escape = repo / ".agents/delegation/worktrees/task-safe-escape"
    escape.symlink_to(repo, target_is_directory=True)
    assert bash(f'source "{HELPER}"; wt_validate "{repo}" "{escape}" task-safe', check=False).returncode

    # Committed plus current binary/new/deleted changes all export from dispatch base.
    (wt / "committed.txt").write_text("committed\n")
    git(wt, "add", "committed.txt")
    git(wt, "commit", "-qm", "agent committed")
    (wt / "base.txt").unlink()
    (wt / "uncommitted.bin").write_bytes(b"\x00binary\xff\x01")
    (wt / "new.txt").write_text("new\n")
    outputs = repo / "outputs"
    bash(f'source "{HELPER}"; wt_handback "{repo}" "{wt}" task-safe "{outputs}"')
    patch = (outputs / "task-safe.patch").read_text()
    for marker in ("base.txt", "committed.txt", "new.txt", "uncommitted.bin", "GIT binary patch"):
        assert marker in patch, marker
    assert git(repo, "diff", "--cached", "--quiet", check=False).returncode == 0
    assert wt.is_dir(), "successful handback must retain the worktree"

    clean = Path(bash(f'source "{HELPER}"; wt_create "{repo}" task-clean').stdout.strip())
    clean_outputs = repo / "clean-outputs"
    for _ in range(2):
        bash(f'source "{HELPER}"; wt_handback "{repo}" "{clean}" task-clean "{clean_outputs}"')
        assert (clean_outputs / "task-clean.patch").exists()
    assert git(repo, "diff", "--cached", "--quiet", check=False).returncode == 0

    export_wt = Path(bash(f'source "{HELPER}"; wt_create "{repo}" task-export').stdout.strip())
    (export_wt / "export.txt").write_text("retain\n")
    bad_outputs = repo / "not-a-directory"
    bad_outputs.write_text("block mkdir\n")
    assert bash(f'source "{HELPER}"; wt_handback "{repo}" "{export_wt}" task-export "{bad_outputs}"', check=False).returncode
    assert (export_wt / "export.txt").exists() and export_wt.is_dir()

    stage_wt = Path(bash(f'source "{HELPER}"; wt_create "{repo}" task-stage').stdout.strip())
    (stage_wt / "stage.txt").write_text("retain\n")
    shim = Path(temp) / "shim"
    shim.mkdir()
    (shim / "git").write_text('#!/bin/sh\nfor arg in "$@"; do [ "$arg" = add ] && exit 77; done\nexec "$REAL_GIT" "$@"\n')
    (shim / "git").chmod(0o755)
    shim_env = {**os.environ, "PATH": f"{shim}:{os.environ['PATH']}", "REAL_GIT": GIT}
    assert bash(f'source "{HELPER}"; wt_handback "{repo}" "{stage_wt}" task-stage "{repo}/stage-outputs"', env=shim_env, check=False).returncode
    assert (stage_wt / "stage.txt").exists() and stage_wt.is_dir()

    commit_wt = Path(bash(f'source "{HELPER}"; wt_create "{repo}" task-commit').stdout.strip())
    (commit_wt / "commit.txt").write_text("retain\n")
    hook = repo / ".git/hooks/pre-commit"
    hook.write_text("#!/bin/sh\nexit 44\n")
    hook.chmod(0o755)
    assert bash(f'source "{HELPER}"; wt_handback "{repo}" "{commit_wt}" task-commit "{repo}/commit-outputs"', check=False).returncode
    assert git(commit_wt, "diff", "--cached", "--name-only").stdout.strip() == "commit.txt"
    assert commit_wt.is_dir()

# Internal (background) handback entry points return helper failure to their caller.
for wrapper in (CODEX, LOCAL):
    assert run([str(wrapper), "--internal-worktree-handback", "task-safe", "/no/such/worktree", "delegate/task-safe"], check=False).returncode


def caller_fixture(wrapper: Path, *, local: bool, background: bool) -> None:
    """Execute a wrapper path with a successful child and a failing commit hook."""
    with tempfile.TemporaryDirectory(prefix="worktree-caller-") as temp:
        repo = Path(temp) / "repo"
        shutil.copytree(ROOT / "scripts/ai", repo / "scripts/ai")
        git(Path(temp), "init", "-q", str(repo))
        git(repo, "config", "user.email", "fixture@example.invalid")
        git(repo, "config", "user.name", "fixture")
        (repo / "base.txt").write_text("base\n")
        git(repo, "add", ".")
        git(repo, "commit", "-qm", "base")
        hook = repo / ".git/hooks/pre-commit"
        hook.write_text("#!/bin/sh\nexit 44\n")
        hook.chmod(0o755)

        stub_bin = Path(temp) / "bin"
        stub_bin.mkdir()
        capture = Path(temp) / "curl.log"
        (stub_bin / "curl").write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$CURL_CAPTURE"\nexit 0\n')
        (stub_bin / "curl").chmod(0o755)
        if local:
            (stub_bin / "python3").write_text(
                '#!/bin/sh\n'
                'case "$1" in\n'
                '  */dispatch.py)\n'
                '    shift; task=""; output=""; delegation=""\n'
                '    while [ "$#" -gt 0 ]; do\n'
                '      case "$1" in --task-id) task="$2"; shift 2 ;; --output) output="$2"; shift 2 ;; --delegation-dir) delegation="$2"; shift 2 ;; *) shift ;; esac\n'
                '    done\n'
                '    printf "child change\\n" > child.txt; mkdir -p "$(dirname "$output")"; printf "child success\\n" > "$output"\n'
                '    printf \'{"id":"%s","agent":"local-direct","status":"done","output_file":"%s"}\\n\' "$task" "$output" >> "$delegation/registry.jsonl"; exit 0 ;;\n'
                'esac\n'
                'exec "$REAL_PYTHON" "$@"\n'
            )
            (stub_bin / "python3").chmod(0o755)
        else:
            codex_stub = Path(temp) / "codex"
            codex_stub.write_text('#!/bin/sh\nprintf "child change\\n" > child.txt\nexit 0\n')
            codex_stub.chmod(0o755)

        env = {**os.environ, "PATH": f"{stub_bin}:{os.environ['PATH']}", "CURL_CAPTURE": str(capture),
               "REAL_PYTHON": shutil.which("python3") or "python3"}
        args = [str(repo / "scripts/ai" / wrapper.name), "--mode", "agent" if local else "safe",
                "--prompt", "fixture child"]
        if local:
            args.append("--no-consult")
        else:
            env["CODEX_BIN"] = str(codex_stub)
        if not background:
            args.append("--wait")
        result = run(args, env=env, check=False)
        if not background:
            assert result.returncode, result.stdout + result.stderr

        registry = repo / ".agents/delegation/registry.jsonl"
        for _ in range(100):
            if (registry.exists() and '"terminal_reason": "worktree_handback_failed"' in registry.read_text()
                    and capture.exists() and "worktree_handback_failed" in capture.read_text()
                    and "error_resolution" in capture.read_text()):
                break
            import time
            time.sleep(0.05)
        records = registry.read_text()
        assert '"status": "failed"' in records
        assert '"terminal_reason": "worktree_handback_failed"' in records
        assert "worktree_handback_failed" in capture.read_text()
        assert "error_resolution" in capture.read_text()
        if not background:
            assert any((repo / ".agents/sessions").glob("*.json")), "foreground must save its session"


for wrapper, local in ((CODEX, False), (LOCAL, True)):
    caller_fixture(wrapper, local=local, background=False)
    caller_fixture(wrapper, local=local, background=True)

print("PASS: worktree isolation fail-closed contracts")
