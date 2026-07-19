#!/usr/bin/env python3
"""Offline adversarial acceptance for the QPPR-C1B observer descriptor."""

from __future__ import annotations

import errno
import fcntl
import importlib.util
import json
import os
import signal
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from typing import Callable


if len(sys.argv) == 3 and sys.argv[1] == "--fixture":
    mode = sys.argv[2]
    if mode == "exit_zero":
        raise SystemExit(0)
    if mode == "sleep":
        time.sleep(30)
        raise SystemExit(0)
    if mode == "leader_zero_child":
        if os.fork() == 0:
            time.sleep(30)
            os._exit(0)
        raise SystemExit(0)
    if mode == "fd_isolation":
        leaked = []
        for entry in Path("/proc/self/fd").iterdir():
            descriptor = int(entry.name)
            if descriptor > 2:
                try:
                    target = os.readlink(entry)
                except OSError:
                    continue
                if target.startswith("pipe:"):
                    leaked.append(descriptor)
        raise SystemExit(80 if leaked else 0)
    raise SystemExit(64)


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts/testing/harness_qa/core/process_lifecycle.py"
POLICY_PATH = ROOT / "config/qa-provider-probe-policy.json"
SPEC = importlib.util.spec_from_file_location("qa_process_lifecycle_c1b", MODULE_PATH)
assert SPEC and SPEC.loader
LIFECYCLE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = LIFECYCLE
SPEC.loader.exec_module(LIFECYCLE)
POLICY = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
PREFIX = "qa.provider-probe-state.v1"


def _fixture(mode: str) -> list[str]:
    return [sys.executable, str(Path(__file__).resolve()), "--fixture", mode]


def _invoke(mode: str, *, observer_fd: int | None = None, force_deadline: bool = False):
    original = LIFECYCLE._deadline_reached
    if force_deadline:
        forced_at = time.monotonic() + 0.12
        LIFECYCLE._deadline_reached = lambda now, _deadline: now >= forced_at
    try:
        return LIFECYCLE.run_owned_process(
            _fixture(mode),
            provider_id="codex",
            profile_id="codex_help",
            invocation_id="00000000-0000-4000-8000-00000000000b",
            policy=POLICY,
            env={},
            observer_fd=observer_fd,
        )
    finally:
        LIFECYCLE._deadline_reached = original


def _pipe() -> tuple[int, int]:
    return os.pipe2(os.O_NONBLOCK | os.O_CLOEXEC)


def _read_all(descriptor: int) -> bytes:
    chunks: list[bytes] = []
    while True:
        try:
            chunk = os.read(descriptor, 65536)
        except BlockingIOError:
            break
        if not chunk:
            break
        chunks.append(chunk)
    return b"".join(chunks)


def _run_observed(mode: str, *, force_deadline: bool = False):
    read_fd, write_fd = _pipe()
    try:
        result = _invoke(mode, observer_fd=write_fd, force_deadline=force_deadline)
        os.close(write_fd)
        write_fd = -1
        raw = _read_all(read_fd)
    finally:
        for descriptor in (read_fd, write_fd):
            if descriptor >= 0:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
    events = []
    for line in raw.decode("ascii").splitlines():
        version, sequence, state, elapsed = line.split("|")
        events.append((version, int(sequence), state, int(elapsed), line))
    return result, events


class ObserverSequenceTests(unittest.TestCase):
    def assert_sequence(self, events, expected: list[str]) -> None:
        self.assertEqual([entry[2] for entry in events], expected)
        self.assertEqual([entry[1] for entry in events], list(range(1, len(events) + 1)))
        elapsed = [entry[3] for entry in events]
        self.assertEqual(elapsed, sorted(elapsed))
        for version, _sequence, _state, milliseconds, line in events:
            self.assertEqual(version, PREFIX)
            self.assertLessEqual(len((line + "\n").encode("ascii")), 96)
            self.assertLessEqual(milliseconds, 300000)
            payload = "|".join(line.split("|")[1:]).lower()
            for prohibited in (
                "provider", "pid", "argv", "prompt", "credential", "error", "result"
            ):
                self.assertNotIn(prohibited, payload)

    def test_exact_clean_spawn_failure_timeout_and_residual_sequences(self) -> None:
        clean, clean_events = _run_observed("exit_zero")
        self.assertEqual(clean["failure_class"], "none")
        self.assert_sequence(clean_events, ["starting", "running", "reaping", "terminal"])

        read_fd, write_fd = _pipe()
        try:
            missing = LIFECYCLE.run_owned_process(
                ["/definitely/absent/qppr-c1b"],
                provider_id="codex",
                profile_id="codex_help",
                policy=POLICY,
                env={},
                observer_fd=write_fd,
            )
            os.close(write_fd)
            write_fd = -1
            missing_raw = _read_all(read_fd)
        finally:
            for descriptor in (read_fd, write_fd):
                if descriptor >= 0:
                    try:
                        os.close(descriptor)
                    except OSError:
                        pass
        missing_states = [line.split("|")[2] for line in missing_raw.decode().splitlines()]
        self.assertEqual(missing["failure_class"], "executable_missing")
        self.assertEqual(missing_states, ["starting", "reaping", "terminal"])

        timeout, timeout_events = _run_observed("sleep", force_deadline=True)
        self.assertEqual(timeout["failure_class"], "deadline_exceeded")
        self.assert_sequence(
            timeout_events, ["starting", "running", "terminating", "reaping", "terminal"]
        )

        residual, residual_events = _run_observed("leader_zero_child")
        self.assertEqual(residual["failure_class"], "cleanup_failed")
        self.assert_sequence(
            residual_events, ["starting", "running", "terminating", "reaping", "terminal"]
        )

    def test_interruption_and_exceptional_teardown_sequences(self) -> None:
        prior = signal.getsignal(signal.SIGINT)
        delivered = {"count": 0}

        def returning_handler(_signum: int, _frame: object) -> None:
            delivered["count"] += 1

        signal.signal(signal.SIGINT, returning_handler)
        read_fd, write_fd = _pipe()
        sender = threading.Thread(
            target=lambda: (time.sleep(0.15), os.kill(os.getpid(), signal.SIGINT)), daemon=True
        )
        publication_observed = {"terminal": False}
        publication_raw = bytearray()

        def publication(_record) -> None:
            publication_raw.extend(_read_all(read_fd))
            publication_observed["terminal"] = b"|terminal|" in publication_raw

        try:
            sender.start()
            interrupted = LIFECYCLE.run_owned_process(
                _fixture("sleep"),
                provider_id="codex",
                profile_id="codex_help",
                invocation_id="00000000-0000-4000-8000-00000000000b",
                policy=POLICY,
                env={},
                observer_fd=write_fd,
                publication=publication,
            )
            sender.join(timeout=1.0)
            os.close(write_fd)
            write_fd = -1
            publication_raw.extend(_read_all(read_fd))
            states = [line.split("|")[2] for line in publication_raw.decode().splitlines()]
        finally:
            signal.signal(signal.SIGINT, prior)
            for descriptor in (read_fd, write_fd):
                if descriptor >= 0:
                    try:
                        os.close(descriptor)
                    except OSError:
                        pass
        self.assertEqual(interrupted["failure_class"], "interrupted")
        self.assertEqual(delivered["count"], 1)
        self.assertTrue(publication_observed["terminal"])
        self.assertEqual(states, ["starting", "running", "terminating", "reaping", "terminal"])

        original_send = LIFECYCLE._send_group
        faulted = {"value": False}

        def fail_once(identity, child_signal: int) -> str:
            if child_signal == signal.SIGCONT and not faulted["value"]:
                faulted["value"] = True
                raise RuntimeError("injected teardown transition")
            return original_send(identity, child_signal)

        LIFECYCLE._send_group = fail_once
        try:
            exceptional, exceptional_events = _run_observed("sleep", force_deadline=True)
        finally:
            LIFECYCLE._send_group = original_send
        self.assertEqual(exceptional["failure_class"], "cleanup_failed")
        self.assert_sequence(
            exceptional_events,
            ["starting", "running", "terminating", "reaping", "terminal"],
        )

    def test_post_reaping_exception_cannot_reverse_lifecycle_order(self) -> None:
        read_fd, write_fd = _pipe()
        original_reap = LIFECYCLE._reap_pid
        original_fcntl = LIFECYCLE.fcntl.fcntl
        observed = bytearray()
        duplicate_fds: list[int] = []
        injected = {"value": False}
        baseline_children = LIFECYCLE._children_of(os.getpid())

        def observed_fcntl(fd: int, command: int, *args):
            result = original_fcntl(fd, command, *args)
            if command == fcntl.F_DUPFD_CLOEXEC:
                duplicate_fds.append(result)
            return result

        def fail_first_reap_after_reaping(pid: int, *, deadline: float) -> bool:
            observed.extend(_read_all(read_fd))
            states = [line.split("|")[2] for line in observed.decode().splitlines()]
            if "reaping" in states and not injected["value"]:
                injected["value"] = True
                raise RuntimeError("injected post-reaping failure")
            return original_reap(pid, deadline=deadline)

        LIFECYCLE.fcntl.fcntl = observed_fcntl
        LIFECYCLE._reap_pid = fail_first_reap_after_reaping
        try:
            result = _invoke("exit_zero", observer_fd=write_fd)
            os.close(write_fd)
            write_fd = -1
            observed.extend(_read_all(read_fd))
        finally:
            LIFECYCLE._reap_pid = original_reap
            LIFECYCLE.fcntl.fcntl = original_fcntl
            for descriptor in (read_fd, write_fd):
                if descriptor >= 0:
                    try:
                        os.close(descriptor)
                    except OSError:
                        pass

        events = []
        for line in observed.decode("ascii").splitlines():
            version, sequence, state, elapsed = line.split("|")
            events.append((version, int(sequence), state, int(elapsed), line))
        self.assertTrue(injected["value"])
        self.assertEqual(result["failure_class"], "cleanup_failed")
        self.assert_sequence(events, ["starting", "running", "reaping", "terminal"])
        self.assertEqual(sum(event[2] == "terminal" for event in events), 1)
        self.assertNotIn("terminating", [event[2] for event in events])
        self.assertIn("sigcont", [action["action"] for action in result["termination_actions"]])
        self.assertIn("reap", [action["action"] for action in result["termination_actions"]])
        self.assertEqual(LIFECYCLE._children_of(os.getpid()) - baseline_children, set())
        self.assertEqual(len(duplicate_fds), 1)
        with self.assertRaises(OSError):
            os.fstat(duplicate_fds[0])

    def test_transition_order_is_bound_to_cleanup_reap_normalization_and_publication(self) -> None:
        read_fd, write_fd = _pipe()
        original_send = LIFECYCLE._send_group
        original_reap = LIFECYCLE._reap_pid
        original_normalize = LIFECYCLE.normalize_probe_output
        original_write = LIFECYCLE.os.write
        observations: dict[str, bool] = {}

        def states_now() -> list[str]:
            return [line.split("|")[2] for line in _read_all(read_fd).decode().splitlines()]

        def observed_send(identity, child_signal: int) -> str:
            if child_signal == signal.SIGCONT:
                observations["terminating_before_sigcont"] = "terminating" in states_now()
            return original_send(identity, child_signal)

        def observed_reap(pid: int, *, deadline: float) -> bool:
            observations["reaping_before_reap"] = "reaping" in states_now()
            return original_reap(pid, deadline=deadline)

        def observed_normalize(**kwargs):
            output = original_normalize(**kwargs)
            observations["normalized"] = True
            return output

        def observed_write(fd: int, payload: bytes) -> int:
            if b"|terminal|" in payload:
                observations["terminal_after_normalization"] = observations.get(
                    "normalized", False
                )
            return original_write(fd, payload)

        def publication(_record) -> None:
            observations["terminal_before_publication"] = "terminal" in states_now()

        LIFECYCLE._send_group = observed_send
        LIFECYCLE._reap_pid = observed_reap
        LIFECYCLE.normalize_probe_output = observed_normalize
        LIFECYCLE.os.write = observed_write
        try:
            forced_at = time.monotonic() + 0.12
            original_deadline = LIFECYCLE._deadline_reached
            LIFECYCLE._deadline_reached = lambda now, _deadline: now >= forced_at
            try:
                result = LIFECYCLE.run_owned_process(
                    _fixture("sleep"),
                    provider_id="codex",
                    profile_id="codex_help",
                    policy=POLICY,
                    env={},
                    observer_fd=write_fd,
                    publication=publication,
                )
            finally:
                LIFECYCLE._deadline_reached = original_deadline
        finally:
            LIFECYCLE._send_group = original_send
            LIFECYCLE._reap_pid = original_reap
            LIFECYCLE.normalize_probe_output = original_normalize
            LIFECYCLE.os.write = original_write
            os.close(write_fd)
            os.close(read_fd)
        self.assertEqual(result["failure_class"], "deadline_exceeded")
        self.assertTrue(observations["terminating_before_sigcont"])
        self.assertTrue(observations["reaping_before_reap"])
        self.assertTrue(observations["normalized"])
        self.assertTrue(observations["terminal_after_normalization"])


class ObserverDescriptorTests(unittest.TestCase):
    def _assert_invalid(self, descriptor: int) -> None:
        flags_before = None
        try:
            flags_before = fcntl.fcntl(descriptor, fcntl.F_GETFL)
        except (OSError, ValueError):
            pass
        result = _invoke("exit_zero", observer_fd=descriptor)
        self.assertEqual(result["failure_class"], "contract_invalid")
        if flags_before is not None:
            self.assertEqual(fcntl.fcntl(descriptor, fcntl.F_GETFL), flags_before)

    def test_invalid_descriptors_fail_closed_without_mutating_caller(self) -> None:
        read_fd, write_fd = _pipe()
        try:
            self._assert_invalid(read_fd)
            blocking_read, blocking_write = os.pipe2(os.O_CLOEXEC)
            try:
                self._assert_invalid(blocking_write)
            finally:
                os.close(blocking_read)
                os.close(blocking_write)
            flags = fcntl.fcntl(write_fd, fcntl.F_GETFD)
            fcntl.fcntl(write_fd, fcntl.F_SETFD, flags & ~fcntl.FD_CLOEXEC)
            self._assert_invalid(write_fd)
            self.assertFalse(fcntl.fcntl(write_fd, fcntl.F_GETFD) & fcntl.FD_CLOEXEC)
        finally:
            os.close(read_fd)
            os.close(write_fd)

        with tempfile.TemporaryFile() as regular:
            self._assert_invalid(regular.fileno())
        closed_read, closed_write = _pipe()
        os.close(closed_write)
        try:
            self._assert_invalid(closed_write)
            self._assert_invalid(-1)
        finally:
            os.close(closed_read)

    def test_cloexec_duplicate_close_fds_and_duplicate_cleanup(self) -> None:
        captured: list[int] = []
        original_fcntl = LIFECYCLE.fcntl.fcntl

        def observed_fcntl(fd: int, command: int, *args):
            result = original_fcntl(fd, command, *args)
            if command == fcntl.F_DUPFD_CLOEXEC:
                captured.append(result)
                self.assertTrue(original_fcntl(result, fcntl.F_GETFD) & fcntl.FD_CLOEXEC)
            return result

        read_fd, write_fd = _pipe()
        LIFECYCLE.fcntl.fcntl = observed_fcntl
        try:
            result = _invoke("fd_isolation", observer_fd=write_fd)
        finally:
            LIFECYCLE.fcntl.fcntl = original_fcntl
            os.close(write_fd)
            _read_all(read_fd)
            os.close(read_fd)
        self.assertEqual(result["failure_class"], "none")
        self.assertEqual(len(captured), 1)
        with self.assertRaises(OSError):
            os.fstat(captured[0])

    def test_observer_failures_and_backpressure_never_change_lifecycle_result(self) -> None:
        read_fd, write_fd = _pipe()
        try:
            os.close(read_fd)
            read_fd = -1
            started = time.monotonic()
            self.assertEqual(
                _invoke("sleep", observer_fd=write_fd, force_deadline=True)["failure_class"],
                "deadline_exceeded",
            )
            self.assertLess(time.monotonic() - started, 4.0)
        finally:
            for descriptor in (read_fd, write_fd):
                if descriptor >= 0:
                    try:
                        os.close(descriptor)
                    except OSError:
                        pass

        read_fd, write_fd = _pipe()
        try:
            while True:
                os.write(write_fd, b"x" * 4096)
        except BlockingIOError:
            pass
        try:
            started = time.monotonic()
            self.assertEqual(
                _invoke("sleep", observer_fd=write_fd, force_deadline=True)["failure_class"],
                "deadline_exceeded",
            )
            self.assertLess(time.monotonic() - started, 4.0)
        finally:
            os.close(write_fd)
            os.close(read_fd)

        for injected in (
            OSError(errno.EPIPE, "injected"),
            BlockingIOError(errno.EAGAIN, "injected"),
            OSError(errno.EBADF, "injected"),
            "short",
        ):
            read_fd, write_fd = _pipe()
            original_write = LIFECYCLE.os.write
            calls = {"events": 0}

            def failing_write(fd: int, payload: bytes) -> int:
                if payload.startswith(PREFIX.encode()):
                    calls["events"] += 1
                    if injected == "short":
                        return max(0, len(payload) - 1)
                    raise injected
                return original_write(fd, payload)

            LIFECYCLE.os.write = failing_write
            try:
                result = _invoke("exit_zero", observer_fd=write_fd)
            finally:
                LIFECYCLE.os.write = original_write
                os.close(write_fd)
                os.close(read_fd)
            self.assertEqual(result["failure_class"], "none")
            self.assertEqual(calls["events"], 1)

    def test_default_behavior_unchanged_and_observer_adds_no_thread_or_retry(self) -> None:
        baseline = _invoke("exit_zero")
        self.assertEqual(baseline["failure_class"], "none")
        original_thread = LIFECYCLE.threading.Thread
        targets: list[Callable[..., object] | None] = []

        def observed_thread(*args, **kwargs):
            targets.append(kwargs.get("target") if "target" in kwargs else args[0] if args else None)
            return original_thread(*args, **kwargs)

        read_fd, write_fd = _pipe()
        LIFECYCLE.threading.Thread = observed_thread
        try:
            observed = _invoke("exit_zero", observer_fd=write_fd)
        finally:
            LIFECYCLE.threading.Thread = original_thread
            os.close(write_fd)
            lines = _read_all(read_fd).splitlines()
            os.close(read_fd)
        self.assertEqual(observed["failure_class"], "none")
        self.assertEqual(len(lines), 4)
        self.assertTrue(targets)
        self.assertTrue(all(target is LIFECYCLE._drain for target in targets))


if __name__ == "__main__":
    unittest.main(verbosity=2)
