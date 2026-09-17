#!/usr/bin/env python3
"""Disposable Git fixture coverage for CS-3's process-bound commit guard."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "scripts" / "ai" / "lib"
WRAPPER = ROOT / "scripts" / "ai" / "aq-commit-agent"
sys.path.insert(0, str(LIB))
import integration_guard as guard  # noqa: E402


def clean_env() -> dict[str, str]:
    """Fixtures never inherit a caller's Git directory or temporary index."""
    return {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}


def run(*args: str, cwd: Path, expected: int = 0, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, cwd=cwd, env=clean_env() if env is None else env, text=True, capture_output=True)
    if result.returncode != expected:
        raise AssertionError(f"{' '.join(args)} returned {result.returncode}, expected {expected}\n{result.stdout}\n{result.stderr}")
    return result


def write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def make_repo(base: Path) -> Path:
    repo = base / "repo"
    repo.mkdir()
    run("git", "init", "--initial-branch=main", cwd=repo)
    run("git", "config", "user.email", "fixture@example.test", cwd=repo)
    run("git", "config", "user.name", "Fixture", cwd=repo)
    fixture_hooks = repo / ".fixture-hooks"
    fixture_hooks.mkdir()
    run("git", "config", "core.hooksPath", ".fixture-hooks", cwd=repo)
    write(repo / "tracked.txt", "base\n")
    run("git", "add", "tracked.txt", cwd=repo)
    run("git", "commit", "-m", "test: base", cwd=repo)
    hooks = repo / ".githooks"
    hooks.mkdir()
    hook = hooks / "pre-commit"
    hook.write_text(
        "#!/usr/bin/env bash\n"
        f"exec {sys.executable!s} {LIB / 'integration_guard.py'!s} hook --repo \"$(git rev-parse --show-toplevel)\"\n",
        encoding="utf-8",
    )
    hook.chmod(0o755)
    run("git", "config", "core.hooksPath", ".githooks", cwd=repo)
    return repo


def expected_hash(repo: Path, paths: list[str]) -> str:
    run("git", "add", "--", *paths, cwd=repo)
    return guard.staged_binary_full_index_sha256(repo)


def message(repo: Path, subject: str = "test: guarded") -> Path:
    path = repo / "message.txt"
    write(path, subject + "\n\nfixture\n")
    return path


def noop(_: Path) -> None:
    return None


def assert_published_parity(repo: Path, commit: str, parent: str, paths: set[str], digest: str) -> None:
    assert run("git", "rev-parse", f"{commit}^", cwd=repo).stdout.strip() == parent
    assert guard._published_paths(repo, commit) == paths
    assert guard._published_binary_full_index_sha256(repo, commit) == digest


def hold_process(repo: Path) -> subprocess.Popen[str]:
    program = textwrap.dedent("""
        import os, pathlib, sys, time
        sys.path.insert(0, sys.argv[2])
        import integration_guard as g
        repo = pathlib.Path(sys.argv[1])
        record = {"state":"held", "owner":{"pid":os.getpid(), "process_start_time":g._proc_start_time(os.getpid())},
                  "branch":g.current_branch(repo), "expected_head":g.current_head(repo), "expected_index_sha256":"0" * 64,
                  "paths":[], "subject":"fixture"}
        with g.held_transaction_lock(repo, record):
            print("LOCKED", flush=True)
            time.sleep(20)
    """)
    proc = subprocess.Popen([sys.executable, "-c", program, str(repo), str(LIB)], cwd=repo, env=clean_env(), text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdout is not None and proc.stdout.readline().strip() == "LOCKED"
    return proc


def test_own_child_and_literal_contract(repo: Path) -> None:
    write(repo / "tracked.txt", "guarded\n")
    digest = expected_hash(repo, ["tracked.txt"])
    committed = guard.run_transaction(repo, paths=["tracked.txt"], expected_head=guard.current_head(repo),
                                      expected_index_sha256=digest, message_file=message(repo), validator=noop)
    assert committed == guard.current_head(repo)
    assert run("git", "log", "-1", "--format=%s", cwd=repo).stdout.strip() == "test: guarded"
    write(repo / "literal*pathspec.txt", "literal wildcard filename\n")
    literal_hash = expected_hash(repo, ["literal*pathspec.txt"])
    guard.run_transaction(repo, paths=["literal*pathspec.txt"], expected_head=guard.current_head(repo),
                          expected_index_sha256=literal_hash, message_file=message(repo, "test: literal filename"), validator=noop)
    legacy = run(sys.executable, str(WRAPPER), "legacy bulk message", cwd=repo, expected=2)
    assert "Legacy" in legacy.stderr or "usage:" in legacy.stderr
    for unsafe in (".", "../escape", ".git/config", "/absolute", ":(glob)*"):
        try:
            guard.validate_literal_paths(repo, [unsafe])
        except guard.IntegrationGuardError:
            pass
        else:
            raise AssertionError(f"unsafe path accepted: {unsafe}")
    write(repo / "untracked.txt", "must remain untracked\n")
    assert "untracked.txt" in run("git", "status", "--short", cwd=repo).stdout
    write(repo / "deleted-directory" / "entry.txt", "deleted directory fixture\n")
    run("git", "add", "deleted-directory/entry.txt", cwd=repo)
    run("git", "commit", "-m", "test: deleted directory base", cwd=repo)
    run("git", "rm", "-r", "deleted-directory", cwd=repo)
    # Restore only the index entry: the directory remains absent on disk while
    # a Git prefix lookup would still find its tracked descendant.
    run("git", "reset", "--", "deleted-directory/entry.txt", cwd=repo)
    try:
        guard.validate_literal_paths(repo, ["deleted-directory"])
    except guard.IntegrationGuardError:
        pass
    else:
        raise AssertionError("deleted directory prefix accepted")


def test_foreign_staging_rename_and_validator_preservation(repo: Path) -> None:
    write(repo / "tracked.txt", "target\n")
    write(repo / "foreign.txt", "foreign\n")
    run("git", "add", "foreign.txt", cwd=repo)
    before = run("git", "diff", "--cached", "--binary", "--full-index", "HEAD", "--", cwd=repo).stdout
    try:
        guard.run_transaction(repo, paths=["tracked.txt"], expected_head=guard.current_head(repo),
                              expected_index_sha256="0" * 64, message_file=message(repo), validator=noop)
    except guard.IntegrationGuardError as exc:
        assert "foreign staged" in str(exc)
    else:
        raise AssertionError("foreign staging accepted")
    assert before == run("git", "diff", "--cached", "--binary", "--full-index", "HEAD", "--", cwd=repo).stdout
    run("git", "reset", "--", "foreign.txt", cwd=repo)

    digest = expected_hash(repo, ["tracked.txt"])
    before = run("git", "diff", "--cached", "--binary", "--full-index", "HEAD", "--", cwd=repo).stdout
    try:
        guard.run_transaction(repo, paths=["tracked.txt"], expected_head=guard.current_head(repo),
                              expected_index_sha256=digest, message_file=message(repo),
                              validator=lambda _: (_ for _ in ()).throw(guard.IntegrationGuardError("fixture validator failure")))
    except guard.IntegrationGuardError as exc:
        assert "validator failure" in str(exc)
    else:
        raise AssertionError("validator failure committed")
    assert before == run("git", "diff", "--cached", "--binary", "--full-index", "HEAD", "--", cwd=repo).stdout
    run("git", "reset", "--", "tracked.txt", cwd=repo)

    run("git", "mv", "tracked.txt", "renamed.txt", cwd=repo)
    assert guard.staged_paths(repo) == {"tracked.txt", "renamed.txt"}
    try:
        guard.run_transaction(repo, paths=["renamed.txt"], expected_head=guard.current_head(repo),
                              expected_index_sha256=guard.staged_binary_full_index_sha256(repo), message_file=message(repo), validator=noop)
    except guard.IntegrationGuardError as exc:
        assert "foreign staged" in str(exc)
    else:
        raise AssertionError("rename source bypassed explicit path allowlist")
    run("git", "reset", "--", "tracked.txt", "renamed.txt", cwd=repo)


def test_owned_deletion_and_two_path_rename(repo: Path) -> None:
    write(repo / "owned-delete.txt", "delete me\n")
    run("git", "add", "owned-delete.txt", cwd=repo)
    run("git", "commit", "-m", "test: owned deletion base", cwd=repo)
    parent = guard.current_head(repo)
    (repo / "owned-delete.txt").unlink()
    deletion_hash = expected_hash(repo, ["owned-delete.txt"])
    deletion = guard.run_transaction(repo, paths=["owned-delete.txt"], expected_head=parent,
                                     expected_index_sha256=deletion_hash, message_file=message(repo, "test: owned deletion"), validator=noop)
    assert_published_parity(repo, deletion, parent, {"owned-delete.txt"}, deletion_hash)
    assert not (repo / "owned-delete.txt").exists()

    write(repo / "rename-from.txt", "rename me\n")
    run("git", "add", "rename-from.txt", cwd=repo)
    run("git", "commit", "-m", "test: owned rename base", cwd=repo)
    parent = guard.current_head(repo)
    run("git", "mv", "rename-from.txt", "rename-to.txt", cwd=repo)
    rename_hash = guard.staged_binary_full_index_sha256(repo)
    rename = guard.run_transaction(repo, paths=["rename-from.txt", "rename-to.txt"], expected_head=parent,
                                   expected_index_sha256=rename_hash, message_file=message(repo, "test: owned rename"), validator=noop)
    assert_published_parity(repo, rename, parent, {"rename-from.txt", "rename-to.txt"}, rename_hash)
    assert not (repo / "rename-from.txt").exists() and (repo / "rename-to.txt").is_file()


def test_index_drift_and_temporary_hook_index(repo: Path) -> None:
    write(repo / "tracked.txt", "before-drift\n")
    digest = expected_hash(repo, ["tracked.txt"])
    before = run("git", "diff", "--cached", "--binary", "--full-index", "HEAD", "--", cwd=repo).stdout

    def mutate_index(root: Path) -> None:
        write(root / "tracked.txt", "after-drift\n")
        run("git", "add", "tracked.txt", cwd=root)

    try:
        guard.run_transaction(repo, paths=["tracked.txt"], expected_head=guard.current_head(repo),
                              expected_index_sha256=digest, message_file=message(repo), validator=mutate_index)
    except guard.IntegrationGuardError as exc:
        assert "drifted" in str(exc)
    else:
        raise AssertionError("index drift committed")
    assert before != run("git", "diff", "--cached", "--binary", "--full-index", "HEAD", "--", cwd=repo).stdout
    run("git", "reset", "--", "tracked.txt", cwd=repo)

    write(repo / "tracked.txt", "branch-drift\n")
    branch_hash = expected_hash(repo, ["tracked.txt"])
    original_branch = guard.current_branch(repo)

    def move_branch(root: Path) -> None:
        run("git", "branch", "fixture-branch-drift", cwd=root)
        run("git", "symbolic-ref", "HEAD", "refs/heads/fixture-branch-drift", cwd=root)

    try:
        guard.run_transaction(repo, paths=["tracked.txt"], expected_head=guard.current_head(repo),
                              expected_index_sha256=branch_hash, message_file=message(repo), validator=move_branch)
    except guard.IntegrationGuardError as exc:
        assert "drifted" in str(exc)
    else:
        raise AssertionError("branch/HEAD drift committed")
    assert guard.current_branch(repo) == "fixture-branch-drift"
    run("git", "symbolic-ref", "HEAD", f"refs/heads/{original_branch}", cwd=repo)
    run("git", "reset", "--", "tracked.txt", cwd=repo)

    write(repo / "tracked.txt", "head-object-drift\n")
    head_hash = expected_hash(repo, ["tracked.txt"])
    frozen_head = guard.current_head(repo)
    created_head = ""

    def move_head_object(root: Path) -> None:
        nonlocal created_head
        created_head = run("git", "commit-tree", "HEAD^{tree}", "-p", "HEAD", "-m", "test: validator head drift", cwd=root).stdout.strip()
        run("git", "update-ref", "HEAD", created_head, cwd=root)

    try:
        guard.run_transaction(repo, paths=["tracked.txt"], expected_head=frozen_head,
                              expected_index_sha256=head_hash, message_file=message(repo), validator=move_head_object)
    except guard.IntegrationGuardError as exc:
        assert "drifted" in str(exc)
    else:
        raise AssertionError("actual HEAD object drift committed")
    assert created_head and guard.current_head(repo) == created_head and created_head != frozen_head
    assert (repo / "tracked.txt").read_text(encoding="utf-8") == "head-object-drift\n"
    assert run("git", "diff", "--cached", "--name-only", cwd=repo).stdout.strip() == "tracked.txt"
    run("git", "reset", "--", "tracked.txt", cwd=repo)

    # Git hooks receive GIT_INDEX_FILE for path-limited commits.  The guard must
    # inspect that active temporary index, not silently fall back to persistent.
    write(repo / "tracked.txt", "persistent\n")
    persistent_hash = expected_hash(repo, ["tracked.txt"])
    write(repo / "temporary.txt", "temporary\n")
    temp_index = repo / "temporary.index"
    temp_env = {**clean_env(), "GIT_INDEX_FILE": str(temp_index)}
    run("git", "read-tree", "HEAD", cwd=repo, env=temp_env)
    run("git", "add", "temporary.txt", cwd=repo, env=temp_env)
    record = {"state": "held", "owner": {"pid": os.getpid(), "process_start_time": guard._proc_start_time(os.getpid())},
              "branch": guard.current_branch(repo), "expected_head": guard.current_head(repo),
              "expected_index_sha256": persistent_hash, "paths": ["tracked.txt"], "subject": "fixture"}
    prior = os.environ.get("GIT_INDEX_FILE")
    os.environ["GIT_INDEX_FILE"] = str(temp_index)
    try:
        with guard.held_transaction_lock(repo, record):
            allowed, reason = guard.hook_allows_commit(repo)
            assert not allowed and ("paths changed" in reason or "index drifted" in reason)
    finally:
        if prior is None:
            os.environ.pop("GIT_INDEX_FILE", None)
        else:
            os.environ["GIT_INDEX_FILE"] = prior
    run("git", "reset", "--", "tracked.txt", cwd=repo)


def test_foreign_commit_linked_worktree_crash_and_safe_lock(repo: Path, base: Path) -> None:
    holder = hold_process(repo)
    try:
        write(repo / "foreign.txt", "foreign commit\n")
        run("git", "add", "foreign.txt", cwd=repo)
        refused = run("git", "commit", "-m", "test: foreign", cwd=repo, expected=1)
        assert "foreign commit refused" in refused.stderr
        run("git", "reset", "--", "foreign.txt", cwd=repo)
        linked = base / "linked"
        run("git", "worktree", "add", "-b", "fixture-linked", str(linked), cwd=repo)
        write(linked / "tracked.txt", "linked\n")
        digest = expected_hash(linked, ["tracked.txt"])
        try:
            guard.run_transaction(linked, paths=["tracked.txt"], expected_head=guard.current_head(linked),
                                  expected_index_sha256=digest, message_file=message(linked), validator=noop)
        except guard.IntegrationGuardError as exc:
            assert "currently holds" in str(exc)
        else:
            raise AssertionError("linked worktree bypassed common lock")
    finally:
        holder.terminate()
        holder.wait(timeout=5)

    program = textwrap.dedent("""
        import os, pathlib, sys
        sys.path.insert(0, sys.argv[2])
        import integration_guard as g
        repo = pathlib.Path(sys.argv[1])
        record = {"state":"held", "owner":{"pid":os.getpid(), "process_start_time":g._proc_start_time(os.getpid())}}
        with g.held_transaction_lock(repo, record): os._exit(0)
    """)
    assert subprocess.run([sys.executable, "-c", program, str(repo), str(LIB)], cwd=repo, env=clean_env()).returncode == 0
    released = guard.status(repo)
    assert released["state"] == "idle" and released["attribution"] == "owner_pid_unobservable"
    lock = guard.common_git_dir(repo) / ".aq-integration-guard.lock"
    lock.write_text(json.dumps({"state": "held", "owner": {"pid": os.getpid(), "process_start_time": "wrong"}}), encoding="utf-8")
    assert guard.status(repo)["attribution"] == "owner_pid_reused"


def test_no_ttl_fifo_and_dashboard_contract(repo: Path, base: Path) -> None:
    # An arbitrarily old timestamp is still held while the kernel flock exists;
    # status uses process ownership, never a TTL expiration policy.
    record = {"state": "held", "owner": {"pid": os.getpid(), "process_start_time": guard._proc_start_time(os.getpid())},
              "started_at": 1, "paths": [], "subject": "ancient fixture"}
    with guard.held_transaction_lock(repo, record):
        held = guard.status(repo)
        assert held["state"] == "held" and held["owner"]["pid"] == os.getpid()

    fifo_base = base / "fifo"
    fifo_base.mkdir()
    fifo_repo = make_repo(fifo_base)
    fifo_lock = guard.common_git_dir(fifo_repo) / ".aq-integration-guard.lock"
    os.mkfifo(fifo_lock)
    started = time.monotonic()
    assert guard.status(fifo_repo)["state"] == "unavailable"
    assert time.monotonic() - started < 1.0, "FIFO lock status probe blocked"
    route = (ROOT / "dashboard/backend/api/routes/aistack.py").read_text(encoding="utf-8")
    dashboard = (ROOT / "assets/dashboard.js").read_text(encoding="utf-8")
    assert "integration_guard" in route and "asyncio.to_thread(_integration_guard_status" in route
    assert "integration guard" in dashboard and "guardText" in dashboard


def main() -> None:
    # The guard deliberately honors Git's active index (notably pre-commit's
    # temporary index).  A disposable fixture must therefore discard every
    # inherited GIT_* value before it calls guard functions directly.
    inherited_index = os.environ.get("GIT_INDEX_FILE")
    sentinel = Path(inherited_index) if inherited_index else None
    sentinel_before = sentinel.read_bytes() if sentinel and sentinel.exists() else None
    for key in [key for key in os.environ if key.startswith("GIT_")]:
        os.environ.pop(key, None)
    with tempfile.TemporaryDirectory(prefix="aq-integration-guard-") as raw:
        base = Path(raw)
        repo = make_repo(base)
        test_own_child_and_literal_contract(repo)
        test_foreign_staging_rename_and_validator_preservation(repo)
        test_owned_deletion_and_two_path_rename(repo)
        test_index_drift_and_temporary_hook_index(repo)
        test_foreign_commit_linked_worktree_crash_and_safe_lock(repo, base)
        test_no_ttl_fifo_and_dashboard_contract(repo, base)
    if sentinel is not None and sentinel_before is not None:
        assert sentinel.read_bytes() == sentinel_before, "inherited temporary index was modified"
    print("PASS: integration guard process, index, worktree, crash, and dashboard contracts")


if __name__ == "__main__":
    # Exercise the whole fixture under a poisoned inherited Git index once;
    # the child strips it before every direct guard call and must leave it intact.
    if "GIT_INDEX_FILE" not in os.environ:
        with tempfile.TemporaryDirectory(prefix="aq-integration-index-sentinel-") as raw:
            sentinel = Path(raw) / "outside.index"
            sentinel.write_bytes(b"outside-index-sentinel")
            result = subprocess.run([sys.executable, str(Path(__file__).resolve())], cwd=ROOT,
                                    env={**clean_env(), "GIT_INDEX_FILE": str(sentinel)}, text=True, capture_output=True)
            if result.returncode or sentinel.read_bytes() != b"outside-index-sentinel":
                raise SystemExit(f"inherited-index isolation regression failed\n{result.stdout}\n{result.stderr}")
    main()
