#!/usr/bin/env python3
"""Process-bound, cooperative Git integration guard.

The guard intentionally protects only participants using this wrapper/hook.  It
is an advisory same-user coordination boundary, not a security boundary against
someone who can change the repository or bypass Git hooks.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterator, Sequence


class IntegrationGuardError(RuntimeError):
    """A refused integration transaction; callers must preserve their index."""


_FULL_OID = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_LOCK_NAME = ".aq-integration-guard.lock"
_MAX_METADATA_BYTES = 8192


def _git(repo: Path, *args: str, input_bytes: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args], cwd=repo, env=os.environ.copy(), input=input_bytes,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )


def _git_text(repo: Path, *args: str) -> str:
    result = _git(repo, *args)
    if result.returncode:
        raise IntegrationGuardError(result.stderr.decode("utf-8", "replace").strip() or "git command failed")
    return result.stdout.decode("utf-8", "replace").strip()


def repository_root(repo: Path | str) -> Path:
    candidate = Path(repo).resolve()
    return Path(_git_text(candidate, "rev-parse", "--show-toplevel")).resolve()


def common_git_dir(repo: Path | str) -> Path:
    root = repository_root(repo)
    return Path(_git_text(root, "rev-parse", "--path-format=absolute", "--git-common-dir")).resolve()


def _lock_path(repo: Path | str) -> Path:
    return common_git_dir(repo) / _LOCK_NAME


def _proc_start_time(pid: int) -> str | None:
    try:
        # Field 22; the executable name can contain spaces/parentheses, so split
        # after the final ')' rather than trusting a whitespace split from field 1.
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
        return stat.rsplit(")", 1)[1].split()[19]
    except (OSError, IndexError):
        return None


def _pid_attribution(record: dict[str, Any]) -> str:
    owner = record.get("owner") if isinstance(record, dict) else None
    if not isinstance(owner, dict) or not isinstance(owner.get("pid"), int):
        return "metadata_missing"
    observed = _proc_start_time(owner["pid"])
    if observed is None:
        return "owner_pid_unobservable"
    if owner.get("process_start_time") != observed:
        return "owner_pid_reused"
    return "owner_pid_matches"


def _read_record(handle: Any) -> dict[str, Any]:
    try:
        handle.seek(0)
        raw = handle.read(_MAX_METADATA_BYTES + 1)
        if len(raw.encode("utf-8")) > _MAX_METADATA_BYTES:
            return {}
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else {}
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}


def _write_record(handle: Any, value: dict[str, Any]) -> None:
    handle.seek(0)
    handle.truncate()
    json.dump(value, handle, sort_keys=True, separators=(",", ":"))
    handle.write("\n")
    handle.flush()
    os.fsync(handle.fileno())


def _open_lock(repo: Path | str, *, create: bool) -> Any:
    path = _lock_path(repo)
    flags = (os.O_RDWR if create else os.O_RDONLY) | os.O_NONBLOCK | (os.O_CREAT if create else 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags, 0o600)
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            os.close(fd)
            raise IntegrationGuardError("integration guard lock is not a regular file")
        return os.fdopen(fd, "r+" if create else "r", encoding="utf-8")
    except OSError as exc:
        raise IntegrationGuardError(f"integration guard unavailable: {exc}") from exc


@contextmanager
def held_transaction_lock(repo: Path | str, record: dict[str, Any]) -> Iterator[None]:
    """Hold a stable common-dir inode for the entire integration transaction."""
    handle = _open_lock(repo, create=True)  # deliberately never unlinked
    try:
        acquired = False
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except BlockingIOError as exc:
            raise IntegrationGuardError("another aq-commit-agent transaction currently holds the common Git lock") from exc
        _write_record(handle, record)
        yield
    finally:
        try:
            # Preserve a truthful released record.  A crash leaves "held" data,
            # but the kernel releases flock; status then attributes it as stale.
            if acquired:
                _write_record(handle, {**record, "state": "idle", "released_at": int(time.time())})
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def status(repo: Path | str) -> dict[str, Any]:
    """Read-only status; never creates, removes, or takes ownership of the lock."""
    try:
        path = _lock_path(repo)
    except IntegrationGuardError as exc:
        return {"available": False, "state": "unavailable", "reason": str(exc)}
    if not path.exists():
        return {"available": False, "state": "unavailable", "reason": "integration guard lock has not been initialized"}
    try:
        with _open_lock(repo, create=False) as handle:
            record = _read_record(handle)
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
            except BlockingIOError:
                return {
                    "available": True, "state": "held", "attribution": _pid_attribution(record),
                    "owner": record.get("owner"), "branch": record.get("branch"),
                    "expected_head": record.get("expected_head"), "subject": record.get("subject"),
                }
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            stale = record.get("state") == "held"
            return {
                "available": True, "state": "idle",
                "attribution": _pid_attribution(record) if stale else ("lock_released" if record else "metadata_unavailable"),
                "owner": record.get("owner"), "branch": record.get("branch"),
                "expected_head": record.get("expected_head"), "subject": record.get("subject"),
            }
    except IntegrationGuardError as exc:
        return {"available": False, "state": "unavailable", "reason": str(exc)}


def _frozen_head_blob(repo: Path, head: str, path: str) -> bool:
    """True only when path is one exact blob entry, never a tree prefix."""
    result = _git(repo, "--literal-pathspecs", "ls-tree", "-z", head, "--", path)
    if result.returncode:
        return False
    entries = [entry for entry in result.stdout.split(b"\0") if entry]
    if len(entries) != 1 or b"\t" not in entries[0]:
        return False
    metadata, raw_name = entries[0].split(b"\t", 1)
    parts = metadata.split()
    return len(parts) == 3 and parts[1] == b"blob" and raw_name.decode("utf-8", "surrogateescape") == path


def validate_literal_paths(repo: Path | str, paths: Sequence[str], frozen_head: str | None = None) -> list[str]:
    root = repository_root(repo)
    head = frozen_head or current_head(root)
    if not paths:
        raise IntegrationGuardError("at least one repeated --path is required; directories are never bulk-staged")
    validated: list[str] = []
    seen: set[str] = set()
    for raw in paths:
        pure = PurePosixPath(raw)
        if not raw or raw.startswith("/") or "\\" in raw or raw == "." or any(part in ("", ".", "..", ".git") for part in pure.parts):
            raise IntegrationGuardError(f"unsafe literal repository path: {raw!r}")
        candidate = root / Path(*pure.parts)
        try:
            candidate.resolve().relative_to(root)
        except ValueError as exc:
            raise IntegrationGuardError(f"path escapes checkout: {raw!r}") from exc
        if candidate.is_dir():
            raise IntegrationGuardError(f"path must name one file, not a directory: {raw!r}")
        if not (candidate.is_file() or candidate.is_symlink()):
            if not _frozen_head_blob(root, head, raw):
                raise IntegrationGuardError(f"path must name an existing file or exact frozen-HEAD blob deletion: {raw!r}")
        if raw in seen:
            raise IntegrationGuardError(f"duplicate --path is not an explicit transaction: {raw!r}")
        seen.add(raw)
        validated.append(raw)
    return validated


def current_head(repo: Path | str) -> str:
    return _git_text(repository_root(repo), "rev-parse", "HEAD")


def current_branch(repo: Path | str) -> str:
    return _git_text(repository_root(repo), "symbolic-ref", "--quiet", "--short", "HEAD")


def staged_paths(repo: Path | str) -> set[str]:
    root = repository_root(repo)
    result = _git(root, "diff", "--cached", "--no-renames", "--name-only", "-z", "HEAD", "--")
    if result.returncode:
        raise IntegrationGuardError(result.stderr.decode("utf-8", "replace").strip() or "could not inspect staged paths")
    return {entry.decode("utf-8", "surrogateescape") for entry in result.stdout.split(b"\0") if entry}


def staged_binary_full_index_sha256(repo: Path | str) -> str:
    root = repository_root(repo)
    result = _git(root, "diff", "--cached", "--binary", "--full-index", "--no-ext-diff", "HEAD", "--")
    if result.returncode:
        raise IntegrationGuardError(result.stderr.decode("utf-8", "replace").strip() or "could not hash staged index")
    return hashlib.sha256(result.stdout).hexdigest()


def _published_binary_full_index_sha256(repo: Path | str, commit: str) -> str:
    root = repository_root(repo)
    result = _git(root, "diff", "--binary", "--full-index", "--no-ext-diff", f"{commit}^", commit, "--")
    if result.returncode:
        raise IntegrationGuardError(result.stderr.decode("utf-8", "replace").strip() or "could not hash published commit")
    return hashlib.sha256(result.stdout).hexdigest()


def _published_paths(repo: Path | str, commit: str) -> set[str]:
    root = repository_root(repo)
    result = _git(root, "diff-tree", "--no-commit-id", "--no-renames", "--name-only", "-z", "-r", f"{commit}^", commit, "--")
    if result.returncode:
        raise IntegrationGuardError(result.stderr.decode("utf-8", "replace").strip() or "could not inspect published paths")
    return {entry.decode("utf-8", "surrogateescape") for entry in result.stdout.split(b"\0") if entry}


def _is_owner_ancestor(owner: dict[str, Any]) -> bool:
    pid = owner.get("pid")
    start = owner.get("process_start_time")
    if not isinstance(pid, int) or not isinstance(start, str) or _proc_start_time(pid) != start:
        return False
    cursor = os.getpid()
    for _ in range(128):
        if cursor == pid:
            return True
        try:
            stat = Path(f"/proc/{cursor}/stat").read_text(encoding="utf-8")
            cursor = int(stat.rsplit(")", 1)[1].split()[1])
        except (OSError, IndexError, ValueError):
            return False
        if cursor <= 1:
            return False
    return False


def hook_allows_commit(repo: Path | str) -> tuple[bool, str]:
    """Permit only the active wrapper's Git-child commit while the lock is held."""
    observed = status(repo)
    if observed["state"] != "held":
        return True, "integration guard is idle or unavailable"
    path = _lock_path(repo)
    try:
        with _open_lock(repo, create=False) as handle:
            record = _read_record(handle)
    except (OSError, IntegrationGuardError):
        return False, "integration guard is held but its ownership metadata is unreadable"
    owner = record.get("owner") if isinstance(record.get("owner"), dict) else {}
    if not _is_owner_ancestor(owner):
        return False, "another aq-commit-agent transaction is active; foreign commit refused"
    try:
        paths = record.get("paths")
        if not isinstance(paths, list) or set(paths) != staged_paths(repo):
            return False, "active transaction staged paths changed"
        if record.get("expected_head") != current_head(repo) or record.get("branch") != current_branch(repo):
            return False, "active transaction branch or HEAD drifted"
        if record.get("expected_index_sha256") != staged_binary_full_index_sha256(repo):
            return False, "active transaction staged index drifted"
    except IntegrationGuardError as exc:
        return False, str(exc)
    return True, "active aq-commit-agent child commit allowed"


def _message_metadata(message_file: Path) -> tuple[str, str]:
    try:
        data = message_file.read_bytes()
    except OSError as exc:
        raise IntegrationGuardError(f"message file is unreadable: {message_file}") from exc
    subject = next((line.strip() for line in data.decode("utf-8", "strict").splitlines() if line.strip()), "")
    if not subject:
        raise IntegrationGuardError("message file must contain a non-empty commit subject")
    return subject, hashlib.sha256(data).hexdigest()


def run_transaction(
    repo: Path | str, *, paths: Sequence[str], expected_head: str,
    expected_index_sha256: str, message_file: Path | str,
    validator: Callable[[Path], None] | None = None,
) -> str:
    """Stage only declared paths, validate a frozen transaction, then commit.

    The optional callable is for disposable fixture tests only.  The production
    wrapper always supplies the canonical tier0 validator and exposes no flag.
    """
    root = repository_root(repo)
    if not _FULL_OID.fullmatch(expected_head):
        raise IntegrationGuardError("--expected-head must be the full 40- or 64-hex Git object ID")
    if not _SHA256.fullmatch(expected_index_sha256):
        raise IntegrationGuardError("--expected-index-sha256 must be exactly 64 lowercase hex characters")
    message_path = Path(message_file).resolve()
    subject, message_sha256 = _message_metadata(message_path)
    if current_head(root) != expected_head:
        raise IntegrationGuardError("expected HEAD does not match current HEAD")
    literal_paths = validate_literal_paths(root, paths, expected_head)
    branch = current_branch(root)
    preexisting = staged_paths(root)
    foreign = preexisting.difference(literal_paths)
    if foreign:
        raise IntegrationGuardError(f"foreign staged paths refused without mutation: {', '.join(sorted(foreign))}")

    record = {
        "state": "held", "owner": {"pid": os.getpid(), "process_start_time": _proc_start_time(os.getpid())},
        "branch": branch, "expected_head": expected_head, "expected_index_sha256": expected_index_sha256,
        "paths": literal_paths, "subject": subject, "message_sha256": message_sha256,
        "started_at": int(time.time()),
    }
    with held_transaction_lock(root, record):
        # Recheck after acquiring common-dir coordination: another worktree may
        # have altered refs or its index before this transaction got the lock.
        if current_head(root) != expected_head or current_branch(root) != branch:
            raise IntegrationGuardError("branch or HEAD drifted before staging")
        foreign = staged_paths(root).difference(literal_paths)
        if foreign:
            raise IntegrationGuardError(f"foreign staged paths refused without mutation: {', '.join(sorted(foreign))}")
        missing = [path for path in literal_paths if not ((root / path).is_file() or (root / path).is_symlink())]
        present = [path for path in literal_paths if path not in missing]
        if present:
            added = _git(root, "--literal-pathspecs", "add", "--", *present)
            if added.returncode:
                raise IntegrationGuardError(added.stderr.decode("utf-8", "replace").strip() or "explicit staging failed")
        if missing:
            # Git add rejects an absent pathspec even when its deletion is
            # pre-staged.  update-index removes only these exact validated
            # frozen-HEAD blob names; it has no recursive pathspec behavior.
            removed = _git(root, "update-index", "--remove", "--", *missing)
            if removed.returncode:
                raise IntegrationGuardError(removed.stderr.decode("utf-8", "replace").strip() or "explicit deletion staging failed")
        if staged_paths(root) != set(literal_paths):
            raise IntegrationGuardError("staged paths no longer exactly match the declared literal paths")
        if staged_binary_full_index_sha256(root) != expected_index_sha256:
            raise IntegrationGuardError("staged binary/full-index SHA256 does not match the frozen expected hash")
        if _message_metadata(message_path) != (subject, message_sha256):
            raise IntegrationGuardError("frozen commit subject or message changed before validation")
        if validator is not None:
            validator(root)
        if (current_head(root) != expected_head or current_branch(root) != branch or
                staged_binary_full_index_sha256(root) != expected_index_sha256 or
                _message_metadata(message_path) != (subject, message_sha256)):
            raise IntegrationGuardError("frozen branch, HEAD, staged index, or commit subject drifted during validation")
        commit = _git(root, "commit", "-F", str(message_path))
        if commit.returncode:
            raise IntegrationGuardError(commit.stderr.decode("utf-8", "replace").strip() or "git commit failed")
        published = _git_text(root, "rev-parse", "HEAD")
        published_subject = _git_text(root, "log", "-1", "--format=%s")
        valid = (
            _git_text(root, "rev-parse", f"{published}^") == expected_head and
            published_subject == subject and
            _published_paths(root, published) == set(literal_paths) and
            _published_binary_full_index_sha256(root, published) == expected_index_sha256
        )
        if not valid:
            # A commit already exists.  Never reset, rewrite, or hide it; surface
            # the exact published object for human recovery and review.
            raise IntegrationGuardError(f"commit {published} was created but post-commit frozen-subject/index verification failed; no rollback was attempted")
        return published


def _main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("hook", "status"))
    parser.add_argument("--repo", required=True)
    args = parser.parse_args(argv)
    if args.command == "hook":
        allowed, reason = hook_allows_commit(args.repo)
        if not allowed:
            print(f"pre-commit: {reason}", file=sys.stderr)
            return 1
        return 0
    print(json.dumps(status(args.repo), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
