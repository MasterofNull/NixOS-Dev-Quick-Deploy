#!/usr/bin/env python3
"""Bounded aggregate owner for the four fixed flagship CLI probes."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import shutil
import stat
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "scripts/testing/harness_qa/core/process_lifecycle.py"
_SPEC = importlib.util.spec_from_file_location("qa_probe_lifecycle", CORE)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError("lifecycle owner unavailable")
_LIFECYCLE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _LIFECYCLE
_SPEC.loader.exec_module(_LIFECYCLE)

LOCK_NAME = "provider-probe.lock"
HEARTBEAT_NAME = "provider-probe-active.json"
ORDER = ("codex", "qwen", "claude", "pi")
PROFILE_BY_PROVIDER = {
    "codex": "codex_help",
    "qwen": "qwen_help",
    "claude": "claude_help",
    "pi": "pi_help",
}
STATE_RANK = {"starting": 1, "running": 2, "terminating": 3, "reaping": 4, "terminal": 5}
_TERMINATION_ACTIONS = frozenset({"sigcont", "sigterm", "sigkill", "quiescence", "reap"})
_ACTION_OUTCOMES = frozenset({"sent", "not_needed", "esrch_verified", "complete", "failed"})
_DISPOSITION_CLASSES = frozenset({"default_terminating", "ignored", "custom"})
# R-A1: bounded wait budget for the join inside the C1 publication callback. The C1B
# terminal lifecycle event is already on the observer pipe before the barrier ever calls
# this callback (process_lifecycle.py emits it synchronously just before invoking
# ``publication``), so this is a safety margin against a stuck reader/ticker, not the
# correctness mechanism -- comfortably inside C1C's ~4.9s barrier budget.
_CALLBACK_JOIN_BUDGET_S = 4.0


def _canonical(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _digest(record: Mapping[str, Any]) -> str:
    raw = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _no_spawn(invocation_id: str, profile: Mapping[str, Any], failure: str, now: float) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema_version": "qa.provider-probe-result.v1",
        "invocation_id": invocation_id,
        "provider_id": profile["provider_id"],
        "profile_id": profile["profile_id"],
        "lifecycle_state": "terminal",
        "started_monotonic_ms": int(now * 1000),
        "ended_monotonic_ms": int(now * 1000),
        "duration_ms": 0,
        "deadline_ms": 45000,
        "exit_code": None,
        "result": "fail",
        "failure_class": failure,
        "termination_actions": [],
        "stdout_truncated": False,
        "stderr_truncated": False,
        "stderr_summary": "",
        "disposition": {"class": None, "redelivered": False, "coalesced_signals": 0},
    }
    base["evidence_digest"] = _digest(base)
    return base


def _valid_uuid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return False
    return True


def _valid_terminal_result(
    record: Any,
    *,
    invocation_id: str,
    provider_id: str,
    profile_id: str,
) -> bool:
    """4.2: closed terminal validation of the C1 result delivered over the publication barrier.

    Rejects missing/extra fields, non-UUID invocation, wrong provider/profile, wrong
    lifecycle state, invalid timing/bounds, unknown result/failure/action/disposition
    values, inconsistent pass/failure relation, or a malformed digest. Never raises.
    """
    if not isinstance(record, dict):
        return False
    required = {
        "schema_version", "invocation_id", "provider_id", "profile_id", "lifecycle_state",
        "started_monotonic_ms", "ended_monotonic_ms", "duration_ms", "deadline_ms",
        "exit_code", "result", "failure_class", "termination_actions",
        "stdout_truncated", "stderr_truncated", "stderr_summary", "disposition",
        "evidence_digest",
    }
    if set(record) != required:
        return False
    if record["schema_version"] != "qa.provider-probe-result.v1":
        return False
    if record["invocation_id"] != invocation_id or not _valid_uuid(invocation_id):
        return False
    if record["provider_id"] != provider_id or record["profile_id"] != profile_id:
        return False
    if record["lifecycle_state"] != "terminal":
        return False
    started, ended = record["started_monotonic_ms"], record["ended_monotonic_ms"]
    if not isinstance(started, int) or isinstance(started, bool) or started < 0:
        return False
    if not isinstance(ended, int) or isinstance(ended, bool) or ended < 0:
        return False
    duration = record["duration_ms"]
    if not isinstance(duration, int) or isinstance(duration, bool) or not 0 <= duration <= 300000:
        return False
    if record["deadline_ms"] != 45000:
        return False
    exit_code = record["exit_code"]
    if exit_code is not None and (
        not isinstance(exit_code, int) or isinstance(exit_code, bool) or not -255 <= exit_code <= 255
    ):
        return False
    result = record["result"]
    failure_class = record["failure_class"]
    if result not in ("pass", "fail") or failure_class not in _LIFECYCLE.FAILURE_CLASSES:
        return False
    if (result == "pass") != (failure_class == "none"):
        return False
    actions = record["termination_actions"]
    if not isinstance(actions, list) or len(actions) > 8:
        return False
    for entry in actions:
        if not isinstance(entry, dict) or set(entry) != {"action", "outcome", "at_ms"}:
            return False
        if entry["action"] not in _TERMINATION_ACTIONS or entry["outcome"] not in _ACTION_OUTCOMES:
            return False
        at_ms = entry["at_ms"]
        if not isinstance(at_ms, int) or isinstance(at_ms, bool) or not 0 <= at_ms <= 50000:
            return False
    if not isinstance(record["stdout_truncated"], bool) or not isinstance(record["stderr_truncated"], bool):
        return False
    stderr_summary = record["stderr_summary"]
    if not isinstance(stderr_summary, str) or len(stderr_summary) > 4096:
        return False
    disposition = record["disposition"]
    if not isinstance(disposition, dict) or set(disposition) != {"class", "redelivered", "coalesced_signals"}:
        return False
    disposition_class = disposition["class"]
    redelivered = disposition["redelivered"]
    coalesced = disposition["coalesced_signals"]
    if disposition_class is not None and disposition_class not in _DISPOSITION_CLASSES:
        return False
    if not isinstance(redelivered, bool):
        return False
    if not isinstance(coalesced, int) or isinstance(coalesced, bool) or not 0 <= coalesced <= 1000000:
        return False
    if disposition_class is None and redelivered:
        return False
    if redelivered and not isinstance(disposition_class, str):
        return False
    digest = record["evidence_digest"]
    if not isinstance(digest, str) or len(digest) != 71 or not digest.startswith("sha256:"):
        return False
    if any(ch not in "0123456789abcdef" for ch in digest[7:]):
        return False
    return True


class AggregateLock:
    """Persistent stable-inode admission lock rooted at one validated directory fd."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.dir_fd = -1
        self.fd = -1

    def acquire(self) -> bool:
        self.dir_fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        directory = os.fstat(self.dir_fd)
        if not stat.S_ISDIR(directory.st_mode) or directory.st_uid != os.geteuid() or directory.st_mode & 0o022:
            raise RuntimeError("unsafe aggregate directory")
        # 4.4: only a newly created inode may be normalized to 0600. A pre-existing inode
        # is validated as-is and rejected without ever mutating its bytes, mode, owner,
        # link count, or identity.
        created = False
        try:
            self.fd = os.open(
                LOCK_NAME,
                os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
                0o600,
                dir_fd=self.dir_fd,
            )
            created = True
        except FileExistsError:
            self.fd = os.open(
                LOCK_NAME,
                os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=self.dir_fd,
            )
        before = os.fstat(self.fd)
        if created and before.st_mode & 0o777 != 0o600:
            raise RuntimeError("newly created aggregate lock is not mode 0600")
        self._validate(before, os.stat(LOCK_NAME, dir_fd=self.dir_fd, follow_symlinks=False))
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        after = os.fstat(self.fd)
        self._validate(after, os.stat(LOCK_NAME, dir_fd=self.dir_fd, follow_symlinks=False))
        if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
            raise RuntimeError("aggregate lock inode changed")
        return True

    @staticmethod
    def _validate(handle: os.stat_result, named: os.stat_result) -> None:
        if not stat.S_ISREG(handle.st_mode) or handle.st_nlink != 1 or handle.st_uid != os.geteuid():
            raise RuntimeError("unsafe aggregate lock")
        if handle.st_mode & 0o022 or (handle.st_dev, handle.st_ino) != (named.st_dev, named.st_ino):
            raise RuntimeError("unsafe aggregate lock identity")

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1
        if self.dir_fd >= 0:
            os.close(self.dir_fd)
            self.dir_fd = -1


def _heartbeat(
    dir_fd: int,
    invocation_id: str,
    provider: str,
    state: str,
    elapsed_ms: int,
    failure: str | None,
) -> None:
    record = {
        "schema_version": "qa.provider-probe-active.v1",
        "qa_invocation_id": invocation_id,
        "provider_id": provider,
        "lifecycle_state": state,
        "elapsed_ms": min(300000, max(0, elapsed_ms)),
        "heartbeat_utc": datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z"),
        "deadline_ms": 45000,
        "last_terminal_failure_class": failure if state == "terminal" else None,
    }
    raw = _canonical(record)
    try:
        old = os.stat(HEARTBEAT_NAME, dir_fd=dir_fd, follow_symlinks=False)
        if not stat.S_ISREG(old.st_mode) or old.st_nlink != 1 or old.st_uid != os.geteuid() or old.st_mode & 0o022:
            raise RuntimeError("unsafe heartbeat target")
    except FileNotFoundError:
        pass
    temp = f".{HEARTBEAT_NAME}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    fd = os.open(
        temp,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
        0o600,
        dir_fd=dir_fd,
    )
    try:
        view = memoryview(raw)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise RuntimeError("short heartbeat write")
            view = view[written:]
        os.fsync(fd)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.geteuid():
            raise RuntimeError("unsafe heartbeat temporary")
        os.rename(temp, HEARTBEAT_NAME, src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
        os.fsync(dir_fd)
    finally:
        os.close(fd)
        try:
            os.unlink(temp, dir_fd=dir_fd)
        except FileNotFoundError:
            pass


class ObserverConsumer:
    """The sole C1B lifecycle-event reader, C1 result collector, and (via
    ``submit_result``) the aggregate process's synchronous join driver on the C1 bounded
    publication callback path (R-A1).

    ``committed``/``cancelled`` make the join decision idempotent: once either is set, a
    later call to ``_finalize_join`` for this same provider iteration is a no-op that
    returns the existing decision without re-joining, re-validating, or re-writing
    anything. This is what makes the ordinary post-``run_owned_process``-return call safe
    regardless of whether the callback path already decided.
    """

    def __init__(
        self,
        read_fd: int,
        dir_fd: int,
        invocation_id: str,
        provider: str,
        profile_id: str,
        started: float,
        enabled: bool,
    ) -> None:
        self.read_fd = read_fd
        self.dir_fd = dir_fd
        self.invocation_id = invocation_id
        self.provider = provider
        self.profile_id = profile_id
        self.started = started
        self.enabled = enabled
        self.events: list[tuple[int, str]] = []
        self.invalid = False
        self.result: Mapping[str, Any] | None = None
        self.result_key: tuple[str, str, str, str, str] | None = None
        self.result_ready = threading.Event()
        self.write_lock = threading.Lock()
        self.latest_state: str | None = None
        self.done = threading.Event()
        self.committed = False
        self.cancelled = False
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.ticker = threading.Thread(target=self._tick, daemon=True)

    def start(self) -> None:
        self.thread.start()
        self.ticker.start()

    def _tick(self) -> None:
        while not self.done.wait(0.9):
            state = self.latest_state
            if self.enabled and state in {"starting", "running", "terminating", "reaping"}:
                try:
                    with self.write_lock:
                        _heartbeat(
                            self.dir_fd, self.invocation_id, self.provider, state,
                            int((time.monotonic() - self.started) * 1000), None,
                        )
                except RuntimeError:
                    self.invalid = True

    def _read(self) -> None:
        buffer = b""
        try:
            while True:
                try:
                    chunk = os.read(self.read_fd, 512)
                except BlockingIOError:
                    time.sleep(0.005)
                    continue
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    parts = line.decode("ascii").split("|")
                    if len(parts) != 4 or parts[0] != "qa.provider-probe-state.v1":
                        raise ValueError("invalid observer record")
                    sequence, state = int(parts[1]), parts[2]
                    if sequence != len(self.events) + 1 or state not in STATE_RANK:
                        raise ValueError("invalid observer sequence")
                    if self.events and STATE_RANK[state] <= STATE_RANK[self.events[-1][1]]:
                        raise ValueError("backward observer state")
                    self.events.append((sequence, state))
                    self.latest_state = state
                    if self.enabled and state != "terminal":
                        with self.write_lock:
                            _heartbeat(
                                self.dir_fd, self.invocation_id, self.provider, state,
                                int((time.monotonic() - self.started) * 1000), None,
                            )
                if self.latest_state == "terminal":
                    break
        except (OSError, UnicodeError, ValueError, RuntimeError):
            self.invalid = True
        finally:
            os.close(self.read_fd)
            self.done.set()

    def submit_result(self, result: Mapping[str, Any]) -> None:
        """Invoked synchronously by the C1C publication barrier -- never a daemon thread.

        R-A1 / AM2 4.1: drives the join to COMMITTED or synchronously CANCELLED before
        returning, so a default-disposition redelivery can never kill the process ahead of
        the terminal write, and custom/ignored dispositions never observe a write landing
        after handler return. An identical duplicate is idempotent; a conflicting duplicate
        cancels without writing.
        """
        key = (
            str(result.get("invocation_id")), str(result.get("provider_id")),
            str(result.get("profile_id")), str(result.get("result")),
            str(result.get("failure_class")),
        )
        expected = (self.invocation_id, self.provider)
        valid = key[:2] == expected and result.get("lifecycle_state") == "terminal"
        if valid and self.result_key is not None and self.result_key != key:
            valid = False  # conflicting duplicate
        if not valid:
            self.invalid = True
            _finalize_join(
                self, None,
                invocation_id=self.invocation_id, provider_id=self.provider,
                profile_id=self.profile_id, reader_wait_timeout=_CALLBACK_JOIN_BUDGET_S,
            )
            return
        if self.result_key is None:
            self.result_key = key
            self.result = dict(result)
        self.result_ready.set()
        _finalize_join(
            self, self.result,
            invocation_id=self.invocation_id, provider_id=self.provider,
            profile_id=self.profile_id, reader_wait_timeout=_CALLBACK_JOIN_BUDGET_S,
        )


def _drain_publication_pipe(read_fd: int) -> str | None:
    """Deterministically drain the accepted C1C publication-barrier channel.

    The barrier writer side is always closed (by C1C itself, or by this caller closing its
    own ``publication_fd``) before this is called, so ``os.read`` reaching EOF is guaranteed
    and this never blocks on an arbitrary timeout.
    """
    buffer = b""
    while True:
        try:
            chunk = os.read(read_fd, 512)
        except (BlockingIOError, OSError):
            break
        if not chunk:
            break
        buffer += chunk
    last_sequence = 0
    terminal = False
    last_state: str | None = None
    for line in buffer.split(b"\n"):
        if not line:
            continue
        parsed = _LIFECYCLE.accept_publication_record(line + b"\n", last_sequence=last_sequence, terminal=terminal)
        if parsed is None:
            continue
        sequence, state, _value_ms = parsed
        last_sequence = sequence
        last_state = state
        if sequence == 2:
            terminal = True
    return last_state


def _finalize_join(
    consumer: ObserverConsumer,
    result: Mapping[str, Any] | None,
    *,
    invocation_id: str,
    provider_id: str,
    profile_id: str,
    reader_wait_timeout: float | None,
) -> bool:
    """The one closed join owned by the aggregate process (AM2 4.1, R-A1).

    Reachable from either the C1 bounded publication callback (mid-run signal path:
    ``reader_wait_timeout`` bounded, called from ``ObserverConsumer.submit_result`` before
    it returns control to the C1C barrier) or the ordinary post-``run_owned_process``-return
    path (``reader_wait_timeout=None``: unbounded-but-guaranteed, since both write ends are
    already closed by the caller before this runs, so EOF is deterministic). Idempotent: a
    second call for the same provider iteration is a no-op that returns the already-decided
    outcome. Commits -- writes the single terminal heartbeat, canonical mode only -- or
    cancels -- writes nothing (R-A2) -- before returning.
    """
    if consumer.committed:
        return True
    if consumer.cancelled:
        return False
    if reader_wait_timeout is None:
        consumer.thread.join()
        consumer.done.wait()
        reader_done = True
    else:
        reader_done = consumer.done.wait(reader_wait_timeout)
        if reader_done:
            consumer.thread.join(timeout=reader_wait_timeout)
    if reader_done:
        consumer.ticker.join(timeout=reader_wait_timeout)
    committed = (
        reader_done
        and result is not None
        and not consumer.invalid
        and bool(consumer.events)
        and consumer.events[-1][1] == "terminal"
        and _valid_terminal_result(
            result,
            invocation_id=invocation_id,
            provider_id=provider_id,
            profile_id=profile_id,
        )
    )
    if committed and consumer.enabled:
        try:
            _heartbeat(
                consumer.dir_fd, invocation_id, provider_id, "terminal",
                int((time.monotonic() - consumer.started) * 1000),
                str(result["failure_class"]),  # type: ignore[index]
            )
        except RuntimeError:
            pass
    consumer.committed = committed
    consumer.cancelled = not committed
    return committed


def _load_policy(repo_root: Path) -> dict[str, Any]:
    policy = json.loads((repo_root / "config/qa-provider-probe-policy.json").read_text(encoding="utf-8"))
    if not _LIFECYCLE.validate_policy(policy):
        raise RuntimeError("provider policy invalid")
    return policy


def run_provider_probe(
    *,
    repo_root: Path = ROOT,
    qa_invocation_id: str | None = None,
    executable_path: str | None = None,
    primary_home: str | None = None,
    canonical: bool = False,
    resolver: Callable[[str, str | None], str | None] | None = None,
) -> list[dict[str, Any]]:
    """Run exactly four policy profiles sequentially; tests may inject only ``resolver``."""
    # 4.3: reserved canonical identity fails closed before lock admission, provider
    # resolution, process ownership, heartbeat, or evidence work. Only standalone
    # compatibility mode (canonical=False) may mint a non-authoritative UUID.
    if canonical:
        if not _valid_uuid(qa_invocation_id):
            raise RuntimeError("canonical probe requires a valid reserved qa_invocation_id")
        invocation_id = qa_invocation_id
    else:
        invocation_id = qa_invocation_id or str(uuid.uuid4())
        uuid.UUID(invocation_id)
    policy = _load_policy(repo_root)
    lock = AggregateLock(repo_root / ".agent/qa")
    aggregate_started = time.monotonic()
    try:
        if not lock.acquire():
            return [_no_spawn(invocation_id, profile, "probe_busy", aggregate_started) for profile in policy["profiles"]]
        results: list[dict[str, Any]] = []
        for index, profile in enumerate(policy["profiles"]):
            if time.monotonic() - aggregate_started >= 200:
                results.extend(_no_spawn(invocation_id, item, "interrupted", time.monotonic()) for item in policy["profiles"][index:])
                break
            resolver_fn = resolver or (lambda name, path: shutil.which(name, path=path))
            executable = resolver_fn(profile["executable"], executable_path)
            argv = [executable, "--help"] if executable else list(profile["argv"])
            read_fd, write_fd = os.pipe2(os.O_NONBLOCK | os.O_CLOEXEC)
            pub_read_fd, pub_write_fd = os.pipe2(os.O_NONBLOCK | os.O_CLOEXEC)
            consumer = ObserverConsumer(
                read_fd,
                lock.dir_fd,
                invocation_id,
                profile["provider_id"],
                profile["profile_id"],
                time.monotonic(),
                canonical,
            )
            consumer.start()
            env = {
                "PATH": executable_path or os.defpath,
                "HOME": primary_home or str(Path.home()),
                "LANG": "C.UTF-8",
            }
            try:
                result = _LIFECYCLE.run_owned_process(
                    argv,
                    provider_id=profile["provider_id"],
                    profile_id=profile["profile_id"],
                    policy=policy,
                    invocation_id=invocation_id,
                    env=env,
                    # 4.1: exclusively the accepted C1C synchronous publication barrier.
                    # The legacy daemon publication callback (no publication_fd) is never
                    # used on this path.
                    publication=consumer.submit_result,
                    observer_fd=write_fd,
                    publication_fd=pub_write_fd,
                )
            except _LIFECYCLE._PublicationContractViolation:
                # The barrier already neutralized shared restoration state and fail-stopped
                # before any redelivery/handler return/ordinary continuation. Close what we
                # own, join deterministically, and permanently stop the aggregate: the
                # underlying process-owner lock never releases after this exception.
                os.close(write_fd)
                os.close(pub_write_fd)
                consumer.thread.join()
                consumer.done.wait()
                consumer.ticker.join()
                _drain_publication_pipe(pub_read_fd)
                os.close(pub_read_fd)
                if canonical:
                    try:
                        _heartbeat(
                            lock.dir_fd, invocation_id, profile["provider_id"], "terminal",
                            int((time.monotonic() - aggregate_started) * 1000), "contract_invalid",
                        )
                    except RuntimeError:
                        pass
                results.extend(
                    _no_spawn(invocation_id, item, "contract_invalid", time.monotonic())
                    for item in policy["profiles"][index:]
                )
                break
            os.close(write_fd)
            os.close(pub_write_fd)
            # R-A1: idempotent no-op when the C1 bounded publication callback (signal path)
            # already drove this to COMMITTED or CANCELLED inside submit_result; otherwise
            # (the far more common no-signal path) this is where the join first commits,
            # with a guaranteed (non-arbitrary-timeout) reader/ticker join since both write
            # ends are already closed. R-A2: no heartbeat is written on a cancelled join --
            # commit-gating lives entirely inside ``_finalize_join``.
            _finalize_join(
                consumer, result,
                invocation_id=invocation_id,
                provider_id=profile["provider_id"],
                profile_id=profile["profile_id"],
                reader_wait_timeout=None,
            )
            _drain_publication_pipe(pub_read_fd)
            os.close(pub_read_fd)
            results.append(result)
            if result["failure_class"] == "interrupted":
                results.extend(_no_spawn(invocation_id, item, "interrupted", time.monotonic()) for item in policy["profiles"][index + 1 :])
                break
        if len(results) != 4:
            raise RuntimeError("aggregate evidence shape invalid")
        return results
    finally:
        lock.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--machine", action="store_true")
    parser.parse_args(argv)
    results = run_provider_probe(
        executable_path=os.environ.get("PATH", os.defpath),
        primary_home=os.environ.get("HOME", str(Path.home())),
        canonical=False,
    )
    print(json.dumps({"schema_version": "qa.provider-probe-aggregate.v1", "results": results}, sort_keys=True))
    return 0 if all(item["result"] == "pass" for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
