#!/usr/bin/env python3
"""Regression coverage for scanning staged deletions without reviving their paths."""

from __future__ import annotations

import ctypes
import hashlib
import os
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCAN = ROOT / "scripts/governance/pre-archive-scan.sh"
HOOK = ROOT / "scripts/governance/pre-archive-scan-hook.sh"
IN_CREATE = 0x00000100
IN_MOVED_TO = 0x00000080
INOTIFY_EVENT = struct.Struct("iIII")


def fixture_env() -> dict[str, str]:
    """Prevent a parent Git invocation from leaking its repository state into a fixture."""
    return {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}


def watch_for_target_creation(parent: Path, target_name: str, command: list[str], repo: Path) -> subprocess.CompletedProcess[str]:
    """Run command while rejecting create/move events for target_name in parent."""
    libc = ctypes.CDLL(None, use_errno=True)
    fd = libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
    if fd == -1:
        raise OSError(ctypes.get_errno(), "inotify_init1")
    try:
        watch = libc.inotify_add_watch(fd, os.fsencode(parent), IN_CREATE | IN_MOVED_TO)
        if watch == -1:
            raise OSError(ctypes.get_errno(), f"inotify_add_watch({parent})")
        result = subprocess.run(command, cwd=repo, text=True, capture_output=True, env=fixture_env())
        events: list[tuple[int, str]] = []
        while True:
            try:
                data = os.read(fd, 4096)
            except BlockingIOError:
                break
            offset = 0
            while offset < len(data):
                _, mask, _, name_length = INOTIFY_EVENT.unpack_from(data, offset)
                offset += INOTIFY_EVENT.size
                name = data[offset:offset + name_length].rstrip(b"\0").decode()
                offset += name_length
                if name == target_name:
                    events.append((mask, name))
        assert not events, f"hook created deleted target according to inotify: {events}"
        return result
    finally:
        os.close(fd)


def run(repo: Path, *args: str, expect: int) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, cwd=repo, text=True, capture_output=True, env=fixture_env())
    if result.returncode != expect:
        raise AssertionError(
            f"{' '.join(args)} returned {result.returncode}, expected {expect}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def write_fixture(repo: Path, target: str, *, referenced: bool, preserve_archive: bool) -> Path:
    path = repo / target
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("completed task\n", encoding="utf-8")
    if referenced:
        (repo / "README.md").write_text(f"See {target}\n", encoding="utf-8")
    run(repo, "git", "add", ".", expect=0)
    run(repo, "git", "commit", "-m", "fixture", expect=0)
    if preserve_archive:
        archive = f"archive/{Path(target).name}"
        (repo / "archive").mkdir(exist_ok=True)
        run(repo, "git", "mv", "--", target, archive, expect=0)
        renamed = run(repo, "git", "diff", "--cached", "--name-status", expect=0)
        assert f"R100\t{target}\t{archive}" in renamed.stdout, "fixture must stage an R100 rename"
    else:
        run(repo, "git", "rm", "--", target, expect=0)
    return path


def assert_hook_does_not_materialize(repo: Path, target: str, *, referenced: bool, preserve_archive: bool) -> None:
    path = write_fixture(repo, target, referenced=referenced, preserve_archive=preserve_archive)
    assert not path.exists(), "fixture must begin with a missing staged target"
    path.parent.mkdir(parents=True, exist_ok=True)
    result = watch_for_target_creation(
        path.parent,
        path.name,
        ["bash", str(repo / "scripts/governance/pre-archive-scan-hook.sh")],
        repo,
    )
    expected = 1 if referenced else 0
    if result.returncode != expected:
        raise AssertionError(
            f"hook returned {result.returncode}, expected {expected}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    assert not path.exists(), "hook created the deleted target path"
    if referenced:
        assert "FAIL: inbound references" in result.stdout
    else:
        assert "PASS: no inbound references" in result.stdout


def run_fixture() -> None:
    with tempfile.TemporaryDirectory(prefix="pre-archive-no-replay-") as directory:
        repo = Path(directory)
        (repo / "scripts/governance").mkdir(parents=True)
        shutil.copy2(SCAN, repo / "scripts/governance/pre-archive-scan.sh")
        shutil.copy2(HOOK, repo / "scripts/governance/pre-archive-scan-hook.sh")
        run(repo, "git", "init", "-q", expect=0)
        run(repo, "git", "config", "user.email", "fixture@example.test", expect=0)
        run(repo, "git", "config", "user.name", "Fixture", expect=0)

        assert_hook_does_not_materialize(
            repo, "watched/referenced-task.md", referenced=True, preserve_archive=False
        )
        run(repo, "git", "reset", "--hard", "-q", "HEAD", expect=0)
        assert_hook_does_not_materialize(
            repo, "watched/unreferenced-task.md", referenced=False, preserve_archive=False
        )
        run(repo, "git", "reset", "--hard", "-q", "HEAD", expect=0)
        assert_hook_does_not_materialize(
            repo, "watched/referenced-rename.md", referenced=True, preserve_archive=True
        )
        run(repo, "git", "reset", "--hard", "-q", "HEAD", expect=0)
        assert_hook_does_not_materialize(
            repo, "watched/unreferenced-rename.md", referenced=False, preserve_archive=True
        )

        missing = run(repo, "bash", "scripts/governance/pre-archive-scan.sh", "watched/not-staged.md", expect=2)
        assert "target does not exist" in missing.stderr
        unverified = run(
            repo,
            "bash",
            "scripts/governance/pre-archive-scan.sh",
            "--staged-deletion",
            "watched/not-staged.md",
            expect=2,
        )
        assert "not staged for deletion" in unverified.stderr



def test_inherited_index_isolation() -> None:
    """A commit-hook GIT_INDEX_FILE must not become the fixture's Git index."""
    with tempfile.TemporaryDirectory(prefix="pre-archive-parent-index-") as directory:
        parent = Path(directory)
        run(parent, "git", "init", "-q", expect=0)
        run(parent, "git", "config", "user.email", "fixture@example.test", expect=0)
        run(parent, "git", "config", "user.name", "Fixture", expect=0)
        (parent / "parent.md").write_text("parent index sentinel\n", encoding="utf-8")
        run(parent, "git", "add", "parent.md", expect=0)
        run(parent, "git", "commit", "-m", "parent fixture", expect=0)
        inherited_index = parent / ".git/index"
        before = hashlib.sha256(inherited_index.read_bytes()).hexdigest()

        prior = os.environ.get("GIT_INDEX_FILE")
        os.environ["GIT_INDEX_FILE"] = str(inherited_index)
        try:
            run_fixture()
        finally:
            if prior is None:
                os.environ.pop("GIT_INDEX_FILE", None)
            else:
                os.environ["GIT_INDEX_FILE"] = prior

        after = hashlib.sha256(inherited_index.read_bytes()).hexdigest()
        assert after == before, "fixture changed inherited parent Git index"


def main() -> None:
    run_fixture()
    test_inherited_index_isolation()
    print("PASS: staged deletion scans never materialize deleted target paths or mutate inherited indexes")


if __name__ == "__main__":
    main()
