"""Pure, bounded ownership for deterministic QA probe subprocesses.

This module deliberately knows nothing about provider executables or repository policy.  It owns
one already-authorized argv invocation and returns a closed, output-bounded evidence record.  The
module is Linux-only because descriptor-bound identity and subreaper semantics are contractual.
"""

from __future__ import annotations

import ctypes
import errno
import fcntl
import hashlib
import json
import os
import re
import signal
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


SCHEMA_VERSION = "qa.provider-probe-result.v1"
FAILURE_CLASSES = frozenset(
    {
        "none",
        "executable_missing",
        "spawn_failed",
        "exit_nonzero",
        "provider_reported_failure",
        "machine_output_missing",
        "machine_output_invalid",
        "deadline_exceeded",
        "output_limit_exceeded",
        "cleanup_failed",
        "interrupted",
        "probe_busy",
        "contract_invalid",
    }
)
LIFECYCLE_STATES = frozenset({"starting", "running", "terminating", "reaping", "terminal"})
PROVIDERS = frozenset({"codex", "qwen", "claude", "pi"})
PROFILES = frozenset({"codex_help", "qwen_help", "claude_help", "pi_help"})
PROFILE_BINDINGS = {
    "codex": ("codex_help", "codex", ("codex", "--help")),
    "qwen": ("qwen_help", "qwen", ("qwen", "--help")),
    "claude": ("claude_help", "claude", ("claude", "--help")),
    "pi": ("pi_help", "pi", ("pi", "--help")),
}
EXACT_BUDGETS = {
    "provider_deadline_seconds": 45,
    "sigterm_grace_seconds": 2,
    "sigkill_reap_seconds": 1,
    "aggregate_deadline_seconds": 200,
    "attempts_per_provider": 1,
    "stderr_retention_bytes": 4096,
    "stdout_retention_bytes": 65536,
}
MACHINE_REASON_CODES = frozenset({"ok", "unhealthy", "auth_required", "rate_limited", "unknown"})
DISPOSITIONS = frozenset({"default_terminating", "ignored", "custom"})
TERMINATION_ACTIONS = frozenset({"sigcont", "sigterm", "sigkill", "quiescence", "reap"})
ACTION_OUTCOMES = frozenset({"sent", "not_needed", "esrch_verified", "complete", "failed"})

_PR_GET_CHILD_SUBREAPER = 37
_PR_SET_CHILD_SUBREAPER = 36
_LIBC = ctypes.CDLL(None, use_errno=True)
_AUTH_BEARER_RE = re.compile(r"(?i)\bauthorization\s*:\s*bearer\s+[^\s,;]+")
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[^\s,;]+")
_SECRET_RE = re.compile(
    r"(?i)\b(api[-_]?key|authorization|bearer|password|passwd|secret|token)\b\s*[:=]\s*([^\s,;]+)"
)
_PATH_RE = re.compile(r"(?<![A-Za-z0-9_.-])/(?:[^\s/:]+/)+[^\s:]*")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_INVOCATION_LOCK = threading.Lock()


class LifecycleContractError(RuntimeError):
    """Raised only for programmer misuse before a process can be owned."""


@dataclass(frozen=True)
class _ProcIdentity:
    pid: int
    pgid: int
    sid: int
    start_time: int
    pidfd: int


@dataclass
class _Capture:
    limit: int
    data: bytearray = field(default_factory=bytearray)
    truncated: bool = False

    def add(self, chunk: bytes) -> None:
        remaining = max(0, self.limit - len(self.data))
        if remaining:
            self.data.extend(chunk[:remaining])
        if len(chunk) > remaining:
            self.truncated = True


@dataclass
class _SignalController:
    prior_handlers: dict[int, Any]
    prior_mask: set[signal.Signals]
    read_fd: int
    write_fd: int
    first_signal: int | None = None
    first_signal_at: float | None = None
    coalesced: int = 0

    def close(self) -> None:
        for descriptor in (self.read_fd, self.write_fd):
            try:
                os.close(descriptor)
            except OSError:
                pass


def _now_ms(start: float) -> int:
    return max(0, int((time.monotonic() - start) * 1000))


def _classify_disposition(value: Any) -> str:
    if value == signal.SIG_DFL:
        return "default_terminating"
    if value == signal.SIG_IGN:
        return "ignored"
    return "custom"


def _prctl(option: int, value: int = 0) -> int:
    output = ctypes.c_int()
    argument = ctypes.byref(output) if option == _PR_GET_CHILD_SUBREAPER else ctypes.c_ulong(value)
    result = _LIBC.prctl(ctypes.c_int(option), argument, 0, 0, 0)
    if result != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    return output.value if option == _PR_GET_CHILD_SUBREAPER else 0


def _preflight() -> None:
    required = (
        hasattr(os, "pidfd_open"),
        hasattr(os, "waitid"),
        hasattr(os, "WNOWAIT"),
        Path("/proc/self/stat").is_file(),
    )
    if not all(required):
        raise LifecycleContractError("required Linux lifecycle primitives are unavailable")
    previous = _prctl(_PR_GET_CHILD_SUBREAPER)
    _prctl(_PR_SET_CHILD_SUBREAPER, previous)


def _proc_stat(pid: int) -> tuple[str, int, int, int, int] | None:
    """Return state, ppid, pgrp, session and start-time without trusting comm spacing."""
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
    except (FileNotFoundError, PermissionError, ProcessLookupError, OSError):
        return None
    close = raw.rfind(")")
    if close < 0:
        return None
    fields = raw[close + 2 :].split()
    if len(fields) < 20:
        return None
    try:
        return fields[0], int(fields[1]), int(fields[2]), int(fields[3]), int(fields[19])
    except ValueError:
        return None


def _identity_valid(identity: _ProcIdentity) -> bool:
    stat = _proc_stat(identity.pid)
    if stat is None:
        return False
    _state, _ppid, pgid, sid, start_time = stat
    if (pgid, sid, start_time) != (identity.pgid, identity.sid, identity.start_time):
        return False
    try:
        # The pidfd is the durable identity binding; WNOWAIT is intentionally performed against
        # the still-bound child PID because several supported Python/libc combinations expose
        # pidfd_open before accepting P_PIDFD in waitid.
        os.waitid(os.P_PID, identity.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
    except ChildProcessError:
        return False
    except OSError as exc:
        return exc.errno not in {errno.EBADF, errno.EINVAL}
    return True


def _group_members(identity: _ProcIdentity) -> list[int]:
    members: list[int] = []
    try:
        entries = os.scandir("/proc")
    except OSError:
        return [identity.pid]  # fail closed: never claim quiescence on unreadable /proc
    with entries:
        for entry in entries:
            if not entry.name.isdigit():
                continue
            pid = int(entry.name)
            stat = _proc_stat(pid)
            if stat is None:
                continue
            state, _ppid, pgid, sid, _start = stat
            if pid != identity.pid and state != "Z" and pgid == identity.pgid and sid == identity.sid:
                # Bind the observed member while classifying it.  Group signalling still depends
                # exclusively on the unreaped, descriptor-bound leader anchor.
                try:
                    member_pidfd = os.pidfd_open(pid, 0)
                except OSError:
                    member_pidfd = -1
                if member_pidfd >= 0:
                    os.close(member_pidfd)
                members.append(pid)
    return members


def _descendants_of(root_pid: int) -> set[int]:
    """Enumerate live descendants by PPID, including children that changed session."""
    parent_map: dict[int, int] = {}
    try:
        entries = os.scandir("/proc")
    except OSError:
        return set()
    with entries:
        for entry in entries:
            if entry.name.isdigit():
                pid = int(entry.name)
                stat = _proc_stat(pid)
                if stat and stat[0] != "Z":
                    parent_map[pid] = stat[1]
    descendants: set[int] = set()
    frontier = {root_pid}
    while frontier:
        discovered = {pid for pid, ppid in parent_map.items() if ppid in frontier and pid not in descendants}
        if not discovered:
            break
        descendants.update(discovered)
        frontier = discovered
    return descendants


def _two_pass_quiescent(identity: _ProcIdentity, *, interval: float = 0.01) -> bool:
    if _group_members(identity):
        return False
    time.sleep(interval)
    return not _group_members(identity)


def _send_group(identity: _ProcIdentity, sig: int) -> str:
    if not _identity_valid(identity):
        return "failed"
    try:
        os.killpg(identity.pgid, sig)
        return "sent"
    except ProcessLookupError:
        exited, _status = _leader_exit(identity)
        return "esrch_verified" if exited and _two_pass_quiescent(identity) else "failed"
    except OSError:
        return "failed"


def _leader_exit(identity: _ProcIdentity) -> tuple[bool, int | None]:
    try:
        info = os.waitid(os.P_PID, identity.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
    except (ChildProcessError, OSError):
        return False, None
    if info is None or info.si_pid == 0:
        return False, None
    if info.si_code == os.CLD_EXITED:
        return True, int(info.si_status)
    return True, -int(info.si_status)


def _reap_pid(pid: int, *, deadline: float) -> bool:
    while time.monotonic() < deadline:
        try:
            waited, _status = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            return True
        if waited == pid:
            return True
        time.sleep(0.01)
    return False


def _exceptional_teardown(
    identity: _ProcIdentity,
    process: subprocess.Popen[bytes] | None,
    baseline_children: set[int],
    actions: list[dict[str, Any]],
    started: float,
) -> bool:
    """Best-effort descriptor-bound teardown used when the primary controller faults.

    This routine never trusts a bare PID/PGID.  Each group action revalidates the unreaped leader
    identity; failures are accumulated while later teardown steps continue.
    """
    successful = True

    def record(name: str, outcome: str) -> None:
        actions.append({"action": name, "outcome": outcome, "at_ms": _now_ms(started)})

    for name, child_signal in (
        ("sigcont", signal.SIGCONT),
        ("sigterm", signal.SIGTERM),
    ):
        try:
            outcome = _send_group(identity, child_signal)
        except Exception:
            outcome = "failed"
        record(name, outcome)
        successful = successful and outcome != "failed"

    term_end = time.monotonic() + 2.0
    while time.monotonic() < term_end:
        try:
            leader_done, _status = _leader_exit(identity)
            quiet = _two_pass_quiescent(identity)
        except Exception:
            leader_done, quiet = False, False
            successful = False
        if leader_done and quiet:
            break
        time.sleep(0.01)

    try:
        leader_done, _status = _leader_exit(identity)
        members_remain = bool(_group_members(identity))
    except Exception:
        leader_done, members_remain = False, True
        successful = False
    if not leader_done or members_remain:
        try:
            kill_outcome = _send_group(identity, signal.SIGKILL)
        except Exception:
            kill_outcome = "failed"
        record("sigkill", kill_outcome)
        successful = successful and kill_outcome != "failed"
    else:
        record("sigkill", "not_needed")

    reap_end = time.monotonic() + 1.0
    quiet = False
    while time.monotonic() < reap_end:
        try:
            quiet = _two_pass_quiescent(identity)
        except Exception:
            quiet = False
            successful = False
        if quiet:
            break
        time.sleep(0.01)
    record("quiescence", "complete" if quiet else "failed")
    successful = successful and quiet

    try:
        adopted = _children_of(os.getpid()) - baseline_children - {identity.pid}
        for child_pid in adopted:
            stat = _proc_stat(child_pid)
            if stat and stat[0] == "Z":
                successful = _reap_pid(child_pid, deadline=time.monotonic() + 0.2) and successful
    except Exception:
        successful = False

    try:
        leader_reaped = _reap_pid(identity.pid, deadline=time.monotonic() + 1.0)
    except Exception:
        leader_reaped = False
    record("reap", "complete" if leader_reaped else "failed")
    successful = successful and leader_reaped
    if process is not None and leader_reaped:
        process.returncode = -signal.SIGKILL
    try:
        os.close(identity.pidfd)
    except OSError:
        successful = False
    return successful


def _children_of(parent_pid: int) -> set[int]:
    children: set[int] = set()
    try:
        entries = os.scandir("/proc")
    except OSError:
        return children
    with entries:
        for entry in entries:
            if entry.name.isdigit():
                stat = _proc_stat(int(entry.name))
                if stat and stat[1] == parent_pid:
                    children.add(int(entry.name))
    return children


def _install_signal_controller() -> _SignalController:
    if threading.current_thread() is not threading.main_thread():
        raise LifecycleContractError("outer signal ownership requires the main thread")
    watched = {signal.SIGTERM, signal.SIGINT}
    prior_mask = signal.pthread_sigmask(signal.SIG_BLOCK, watched)
    prior_handlers = {sig: signal.getsignal(sig) for sig in watched}
    read_fd, write_fd = os.pipe2(os.O_NONBLOCK | os.O_CLOEXEC)
    controller = _SignalController(prior_handlers, set(prior_mask), read_fd, write_fd)

    def handler(signum: int, _frame: Any) -> None:
        if controller.first_signal is None:
            controller.first_signal = signum
            controller.first_signal_at = time.monotonic()
            try:
                os.write(controller.write_fd, b"!")
            except OSError:
                pass
        else:
            controller.coalesced += 1

    try:
        for sig in watched:
            signal.signal(sig, handler)
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, prior_mask)
    return controller


def _restore_and_redeliver(controller: _SignalController) -> tuple[str | None, bool]:
    watched = {signal.SIGTERM, signal.SIGINT}
    signal.pthread_sigmask(signal.SIG_BLOCK, watched)
    try:
        signum = controller.first_signal
        disposition = _classify_disposition(controller.prior_handlers[signum]) if signum else None
        for sig, handler in controller.prior_handlers.items():
            signal.signal(sig, handler)
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, controller.prior_mask)
        controller.close()
    if signum:
        os.kill(os.getpid(), signum)
        return disposition, True
    return None, False


def _drain(pipe: Any, capture: _Capture) -> None:
    try:
        while True:
            chunk = pipe.read(65536)
            if not chunk:
                return
            capture.add(chunk)
    finally:
        pipe.close()


def sanitize_stderr(raw: bytes, limit: int = 4096) -> tuple[str, bool]:
    decoded = raw.decode("utf-8", errors="replace")
    decoded = _CONTROL_RE.sub("", decoded)
    decoded = _AUTH_BEARER_RE.sub("Authorization: Bearer [REDACTED]", decoded)
    decoded = _BEARER_RE.sub("Bearer [REDACTED]", decoded)
    decoded = _SECRET_RE.sub(lambda match: f"{match.group(1)}=[REDACTED]", decoded)
    decoded = _PATH_RE.sub("<PATH>", decoded)
    encoded = decoded.encode("utf-8")
    truncated = len(encoded) > limit
    bounded = encoded[:limit]
    while bounded:
        try:
            return bounded.decode("utf-8"), truncated
        except UnicodeDecodeError:
            bounded = bounded[:-1]
    return "", truncated


def normalize_probe_output(
    *,
    mode: str,
    stdout: bytes,
    exit_code: int | None,
    lifecycle_failure: str = "none",
    stdout_truncated: bool = False,
    stderr_truncated: bool = False,
) -> tuple[str, str]:
    if lifecycle_failure not in FAILURE_CLASSES:
        return "fail", "contract_invalid"
    if lifecycle_failure != "none":
        return "fail", lifecycle_failure
    if stdout_truncated or stderr_truncated:
        return "fail", "output_limit_exceeded"
    if mode == "exit_only":
        return ("pass", "none") if exit_code == 0 else ("fail", "exit_nonzero")
    if mode != "machine_json_v1":
        return "fail", "contract_invalid"
    if not stdout.strip():
        return "fail", "machine_output_missing"
    try:
        text = stdout.decode("utf-8")
        decoder = json.JSONDecoder()
        payload, end = decoder.raw_decode(text)
        if text[end:].strip() or not isinstance(payload, dict):
            raise ValueError("multiple or trailing values")
        if set(payload) != {"schema_version", "status", "reason_code"}:
            raise ValueError("open machine object")
        if payload["schema_version"] != "qa.provider-probe-machine.v1":
            raise ValueError("unknown machine version")
        if payload["status"] not in {"pass", "fail"}:
            raise ValueError("unknown machine status")
        if payload["reason_code"] not in MACHINE_REASON_CODES:
            raise ValueError("unknown machine reason")
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return "fail", "machine_output_invalid"
    if payload["status"] == "fail":
        return "fail", "provider_reported_failure"
    if exit_code != 0:
        return "fail", "exit_nonzero"
    return "pass", "none"


def _evidence_digest(record: Mapping[str, Any]) -> str:
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def _result(
    *,
    invocation_id: str,
    provider_id: str,
    profile_id: str,
    started: float,
    deadline_s: float,
    exit_code: int | None,
    result: str,
    failure_class: str,
    actions: list[dict[str, Any]],
    stdout_truncated: bool,
    stderr_truncated: bool,
    stderr_summary: str,
    disposition_class: str | None,
    redelivered: bool,
    coalesced_signals: int,
) -> dict[str, Any]:
    ended = time.monotonic()
    base: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "invocation_id": invocation_id,
        "provider_id": provider_id,
        "profile_id": profile_id,
        "lifecycle_state": "terminal",
        "started_monotonic_ms": int(started * 1000),
        "ended_monotonic_ms": int(ended * 1000),
        "duration_ms": max(0, int((ended - started) * 1000)),
        "deadline_ms": int(deadline_s * 1000),
        "exit_code": exit_code,
        "result": result,
        "failure_class": failure_class,
        "termination_actions": actions,
        "stdout_truncated": stdout_truncated,
        "stderr_truncated": stderr_truncated,
        "stderr_summary": stderr_summary,
        "disposition": {
            "class": disposition_class,
            "redelivered": redelivered,
            "coalesced_signals": coalesced_signals,
        },
    }
    base["evidence_digest"] = _evidence_digest(base)
    return base


def _terminal_without_spawn(
    invocation_id: str,
    provider_id: str,
    profile_id: str,
    deadline_s: float,
    failure: str,
    started: float,
) -> dict[str, Any]:
    return _result(
        invocation_id=invocation_id,
        provider_id=provider_id,
        profile_id=profile_id,
        started=started,
        deadline_s=deadline_s,
        exit_code=None,
        result="fail",
        failure_class=failure,
        actions=[],
        stdout_truncated=False,
        stderr_truncated=False,
        stderr_summary="",
        disposition_class=None,
        redelivered=False,
        coalesced_signals=0,
    )


def validate_policy(policy: Mapping[str, Any]) -> bool:
    """Validate the immutable v1 policy without resolving or executing any executable."""
    if set(policy) != {"schema_version", "budgets", "profiles"}:
        return False
    if policy.get("schema_version") != "qa.provider-probe-policy.v1":
        return False
    if policy.get("budgets") != EXACT_BUDGETS:
        return False
    profiles = policy.get("profiles")
    if not isinstance(profiles, list) or len(profiles) != 4:
        return False
    expected: list[dict[str, Any]] = []
    for provider in ("codex", "qwen", "claude", "pi"):
        profile_id, executable, argv = PROFILE_BINDINGS[provider]
        expected.append(
            {
                "provider_id": provider,
                "profile_id": profile_id,
                "mode": "exit_only",
                "executable": executable,
                "argv": list(argv),
            }
        )
    return profiles == expected


def _deadline_reached(now: float, deadline: float) -> bool:
    """Small seam used only by deterministic offline tests; policy values remain exact."""
    return now >= deadline


def run_owned_process(
    argv: Sequence[str],
    *,
    provider_id: str,
    profile_id: str,
    policy: Mapping[str, Any],
    invocation_id: str | None = None,
    cwd: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
    deadline_s: float = 45.0,
    term_grace_s: float = 2.0,
    kill_reap_s: float = 1.0,
    stdout_limit_bytes: int = 65536,
    stderr_limit_bytes: int = 4096,
    mode: str = "exit_only",
    publication: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Run one local fixture command with descriptor-bound process-session ownership.

    Provider/profile identifiers are evidence labels only; this helper never resolves policy or
    provider executables.  Callers must pass an explicit argv sequence and immutable environment.
    """
    started = time.monotonic()
    invocation_id = invocation_id or str(uuid.uuid4())
    if (
        not argv
        or isinstance(argv, (str, bytes))
        or provider_id not in PROVIDERS
        or profile_id not in PROFILES
        or PROFILE_BINDINGS.get(provider_id, (None,))[0] != profile_id
        or not validate_policy(policy)
        or mode not in {"exit_only", "machine_json_v1"}
        or deadline_s != 45.0
        or term_grace_s != 2.0
        or kill_reap_s != 1.0
        or stdout_limit_bytes != 65536
        or stderr_limit_bytes != 4096
    ):
        return _terminal_without_spawn(
            invocation_id, provider_id, profile_id, 45.0, "contract_invalid", started
        )
    if not _INVOCATION_LOCK.acquire(blocking=False):
        return _terminal_without_spawn(
            invocation_id, provider_id, profile_id, deadline_s, "probe_busy", started
        )
    lock_held = True

    previous_subreaper: int | None = None
    controller: _SignalController | None = None
    process: subprocess.Popen[bytes] | None = None
    identity: _ProcIdentity | None = None
    stdout_capture = _Capture(stdout_limit_bytes)
    stderr_capture = _Capture(stderr_limit_bytes)
    readers: list[threading.Thread] = []
    actions: list[dict[str, Any]] = []
    exit_code: int | None = None
    failure = "none"
    residual_seen = False
    escaped_seen = False
    baseline_children = _children_of(os.getpid())

    def action(name: str, outcome: str) -> None:
        actions.append({"action": name, "outcome": outcome, "at_ms": _now_ms(started)})

    try:
        try:
            _preflight()
            previous_subreaper = _prctl(_PR_GET_CHILD_SUBREAPER)
            _prctl(_PR_SET_CHILD_SUBREAPER, 1)
            controller = _install_signal_controller()
        except (LifecycleContractError, OSError, ValueError):
            return _terminal_without_spawn(
                invocation_id, provider_id, profile_id, deadline_s, "contract_invalid", started
            )

        try:
            process = subprocess.Popen(
                list(argv),
                cwd=cwd,
                env=dict(env) if env is not None else {},
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
                shell=False,
                close_fds=True,
            )
        except FileNotFoundError:
            failure = "executable_missing"
        except OSError:
            failure = "spawn_failed"
        if process is None:
            if previous_subreaper is not None:
                _prctl(_PR_SET_CHILD_SUBREAPER, previous_subreaper)
                previous_subreaper = None
            _INVOCATION_LOCK.release()
            lock_held = False
            redelivery_controller = controller
            controller = None
            disposition, redelivered = _restore_and_redeliver(redelivery_controller)
            return _result(
                invocation_id=invocation_id,
                provider_id=provider_id,
                profile_id=profile_id,
                started=started,
                deadline_s=deadline_s,
                exit_code=None,
                result="fail",
                failure_class=failure,
                actions=actions,
                stdout_truncated=False,
                stderr_truncated=False,
                stderr_summary="",
                disposition_class=disposition,
                redelivered=redelivered,
                coalesced_signals=controller.coalesced if controller else 0,
            )

        stat = _proc_stat(process.pid)
        try:
            pidfd = os.pidfd_open(process.pid, 0)
        except OSError:
            try:
                process.terminate()
                process.wait(timeout=max(0.1, kill_reap_s))
            except (OSError, subprocess.SubprocessError):
                try:
                    process.kill()
                    process.wait(timeout=max(0.1, kill_reap_s))
                except (OSError, subprocess.SubprocessError):
                    pass
            failure = "contract_invalid"
            stat = None
        if stat is None:
            if process.returncode is None:
                try:
                    process.terminate()
                    process.wait(timeout=max(0.1, kill_reap_s))
                except (OSError, subprocess.SubprocessError):
                    pass
            failure = "contract_invalid"
        else:
            _state, _ppid, pgid, sid, start_time = stat
            identity = _ProcIdentity(process.pid, pgid, sid, start_time, pidfd)

        if identity is not None:
            assert process.stdout is not None and process.stderr is not None
            readers = [
                threading.Thread(target=_drain, args=(process.stdout, stdout_capture), daemon=True),
                threading.Thread(target=_drain, args=(process.stderr, stderr_capture), daemon=True),
            ]
            for reader in readers:
                reader.start()

            deadline = started + deadline_s
            while True:
                exited, observed = _leader_exit(identity)
                if exited:
                    exit_code = observed
                    residual_seen = bool(_group_members(identity))
                    descendants = _descendants_of(identity.pid)
                    adopted = _children_of(os.getpid()) - baseline_children - {identity.pid}
                    escaped_seen = any(
                        (stat := _proc_stat(pid)) is not None
                        and (stat[2], stat[3]) != (identity.pgid, identity.sid)
                        for pid in descendants | adopted
                    )
                    if escaped_seen:
                        failure = "cleanup_failed"
                    break
                if _proc_stat(identity.pid) is None:
                    # Another waiter consumed our direct child.  The pidfd can no longer anchor a
                    # group decision, so fail closed without a numeric signal.
                    failure = "contract_invalid"
                    break
                if controller.first_signal is not None:
                    failure = "interrupted"
                    break
                if _deadline_reached(time.monotonic(), deadline):
                    failure = "deadline_exceeded"
                    break
                time.sleep(0.01)

            needs_cleanup = failure in {"deadline_exceeded", "interrupted"} or residual_seen
            if needs_cleanup:
                cleanup_started = time.monotonic()
                action("sigcont", _send_group(identity, signal.SIGCONT))
                action("sigterm", _send_group(identity, signal.SIGTERM))
                grace_end = min(cleanup_started + term_grace_s, cleanup_started + 2.0)
                while time.monotonic() < grace_end:
                    leader_done, _leader_status = _leader_exit(identity)
                    if leader_done and _two_pass_quiescent(identity):
                        break
                    time.sleep(0.01)
                if _group_members(identity) or not _leader_exit(identity)[0]:
                    action("sigkill", _send_group(identity, signal.SIGKILL))
                else:
                    action("sigkill", "not_needed")
                reap_end = time.monotonic() + min(kill_reap_s, 1.0)
                while time.monotonic() < reap_end and not _two_pass_quiescent(identity):
                    time.sleep(0.01)
                quiet = _two_pass_quiescent(identity)
                action("quiescence", "complete" if quiet else "failed")
                if residual_seen:
                    failure = "cleanup_failed"
                elif not quiet:
                    failure = "cleanup_failed"

            for reader in readers:
                reader.join(timeout=1.0)

            owned_now = _children_of(os.getpid()) - baseline_children - {identity.pid}
            escaped_live = False
            for child_pid in owned_now:
                stat_now = _proc_stat(child_pid)
                if stat_now and stat_now[0] != "Z":
                    escaped_live = True
                elif stat_now:
                    _reap_pid(child_pid, deadline=time.monotonic() + 0.2)
            if escaped_live:
                failure = "cleanup_failed"

            quiet = _two_pass_quiescent(identity)
            if not quiet:
                failure = "cleanup_failed"
            if not any(entry["action"] == "quiescence" for entry in actions):
                action("quiescence", "complete" if quiet else "failed")
            reaped = _reap_pid(identity.pid, deadline=time.monotonic() + 1.0)
            action("reap", "complete" if reaped else "failed")
            if reaped:
                # Popen did not perform the wait (WNOWAIT is contractual), so record the already
                # observed status to prevent its destructor from attempting a second wait.
                process.returncode = exit_code if exit_code is not None else -signal.SIGKILL
            os.close(identity.pidfd)
            identity = None
            if actions[-1]["outcome"] != "complete":
                failure = "cleanup_failed"

        sanitized, sanitize_truncated = sanitize_stderr(bytes(stderr_capture.data), stderr_limit_bytes)
        stderr_capture.truncated = stderr_capture.truncated or sanitize_truncated
        result, normalized_failure = normalize_probe_output(
            mode=mode,
            stdout=bytes(stdout_capture.data),
            exit_code=exit_code,
            lifecycle_failure=failure,
            stdout_truncated=stdout_capture.truncated,
            stderr_truncated=stderr_capture.truncated,
        )
        disposition_class = None
        redelivered = False
        coalesced = controller.coalesced
        provisional = _result(
            invocation_id=invocation_id,
            provider_id=provider_id,
            profile_id=profile_id,
            started=started,
            deadline_s=deadline_s,
            exit_code=exit_code,
            result=result,
            failure_class=normalized_failure,
            actions=actions,
            stdout_truncated=stdout_capture.truncated,
            stderr_truncated=stderr_capture.truncated,
            stderr_summary=sanitized,
            disposition_class=None,
            redelivered=False,
            coalesced_signals=coalesced,
        )
        if controller.first_signal is not None and publication is not None:
            signal_started = controller.first_signal_at or time.monotonic()
            # Reserve a small deterministic margin for handler/mask restoration and the one kill.
            remaining = max(0.0, signal_started + 4.9 - time.monotonic())
            worker = threading.Thread(target=publication, args=(dict(provisional),), daemon=True)
            worker.start()
            worker.join(timeout=remaining)
        if previous_subreaper is not None:
            _prctl(_PR_SET_CHILD_SUBREAPER, previous_subreaper)
            previous_subreaper = None
        _INVOCATION_LOCK.release()
        lock_held = False
        redelivery_controller = controller
        controller = None
        disposition_class, redelivered = _restore_and_redeliver(redelivery_controller)
        return _result(
            invocation_id=invocation_id,
            provider_id=provider_id,
            profile_id=profile_id,
            started=started,
            deadline_s=deadline_s,
            exit_code=exit_code,
            result=result,
            failure_class=normalized_failure,
            actions=actions,
            stdout_truncated=stdout_capture.truncated,
            stderr_truncated=stderr_capture.truncated,
            stderr_summary=sanitized,
            disposition_class=disposition_class,
            redelivered=redelivered,
            coalesced_signals=coalesced,
        )
    except Exception:
        # An exception raised by an already-restored custom disposition is outside lifecycle
        # ownership and must propagate; its controller was consumed before invocation.
        if controller is None and identity is None and not lock_held:
            raise
        failure = "cleanup_failed"
        if identity is not None:
            _exceptional_teardown(identity, process, baseline_children, actions, started)
            identity = None
        for reader in readers:
            reader.join(timeout=0.5)
        if process is not None:
            for pipe in (process.stdout, process.stderr):
                if pipe is not None and not pipe.closed:
                    try:
                        pipe.close()
                    except OSError:
                        pass
        sanitized, sanitize_truncated = sanitize_stderr(
            bytes(stderr_capture.data), stderr_limit_bytes
        )
        stderr_capture.truncated = stderr_capture.truncated or sanitize_truncated
        disposition_class = None
        redelivered = False
        coalesced = controller.coalesced if controller is not None else 0
        if previous_subreaper is not None:
            try:
                _prctl(_PR_SET_CHILD_SUBREAPER, previous_subreaper)
            finally:
                previous_subreaper = None
        if lock_held:
            _INVOCATION_LOCK.release()
            lock_held = False
        if controller is not None:
            redelivery_controller = controller
            controller = None
            disposition_class, redelivered = _restore_and_redeliver(redelivery_controller)
        return _result(
            invocation_id=invocation_id,
            provider_id=provider_id,
            profile_id=profile_id,
            started=started,
            deadline_s=deadline_s,
            exit_code=exit_code,
            result="fail",
            failure_class=failure,
            actions=actions[-8:],
            stdout_truncated=stdout_capture.truncated,
            stderr_truncated=stderr_capture.truncated,
            stderr_summary=sanitized,
            disposition_class=disposition_class,
            redelivered=redelivered,
            coalesced_signals=coalesced,
        )
    finally:
        if identity is not None:
            try:
                _exceptional_teardown(identity, process, baseline_children, actions, started)
            except Exception:
                try:
                    os.close(identity.pidfd)
                except OSError:
                    pass
            identity = None
        if previous_subreaper is not None:
            try:
                _prctl(_PR_SET_CHILD_SUBREAPER, previous_subreaper)
            except OSError:
                pass
            previous_subreaper = None
        if lock_held:
            _INVOCATION_LOCK.release()
            lock_held = False
        if controller is not None:
            redelivery_controller = controller
            controller = None
            _restore_and_redeliver(redelivery_controller)


__all__ = [
    "FAILURE_CLASSES",
    "LifecycleContractError",
    "normalize_probe_output",
    "run_owned_process",
    "sanitize_stderr",
    "validate_policy",
]
