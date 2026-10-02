#!/usr/bin/env python3
"""Offline adversarial acceptance tests for the QPPR-C1 lifecycle contract."""

from __future__ import annotations

import copy
import fcntl
import importlib.util
import json
import os
import select
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

# Keep ordinary child fixtures independent of the comparatively heavy test/schema imports.  This
# also proves the lifecycle deadline measures the child, not test-harness import overhead.  "pub:"
# fixtures are excluded the same way "outer:" ones are -- they need the fully imported LIFECYCLE
# module below, not this fast path.
if (
    len(sys.argv) == 3
    and sys.argv[1] == "--fixture"
    and not sys.argv[2].startswith("outer:")
    and not sys.argv[2].startswith("pub:")
):
    _early_mode = sys.argv[2]
    if _early_mode == "exit_zero":
        raise SystemExit(0)
    if _early_mode == "exit_nonzero":
        raise SystemExit(23)
    if _early_mode == "sleep":
        time.sleep(30)
        raise SystemExit(0)
    if _early_mode == "ignore_term_sleep":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        time.sleep(30)
        raise SystemExit(0)
    if _early_mode == "self_stop":
        os.kill(os.getpid(), signal.SIGSTOP)
        time.sleep(30)
        raise SystemExit(0)
    if _early_mode == "fork_sleep":
        if os.fork() == 0:
            time.sleep(30)
            os._exit(0)
        time.sleep(30)
        raise SystemExit(0)
    if _early_mode == "leader_zero_child":
        if os.fork() == 0:
            time.sleep(30)
            os._exit(0)
        raise SystemExit(0)
    if _early_mode == "stderr_flood":
        _prefix = b"token=super-secret Authorization: Bearer bearer-secret Bearer standalone-secret /home/private/credential\x00\x01\n"
        os.write(2, _prefix + b"X" * 200000)
        raise SystemExit(0)
    if _early_mode == "escape_session":
        _ready_read, _ready_write = os.pipe()
        if os.fork() == 0:
            os.close(_ready_read)
            os.setsid()
            os.write(_ready_write, b"1")
            os.close(_ready_write)
            time.sleep(0.5)
            os._exit(0)
        os.close(_ready_write)
        os.read(_ready_read, 1)
        os.close(_ready_read)
        raise SystemExit(0)
    raise SystemExit(64)

import jsonschema


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts/testing/harness_qa/core/process_lifecycle.py"
SCHEMA_PATH = ROOT / "config/qa-provider-probe-contract.schema.json"
POLICY_PATH = ROOT / "config/qa-provider-probe-policy.json"
VECTORS_PATH = ROOT / "scripts/testing/fixtures/qa-provider-probe-vectors.json"

SPEC = importlib.util.spec_from_file_location("qa_process_lifecycle_c1", MODULE_PATH)
assert SPEC and SPEC.loader
LIFECYCLE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = LIFECYCLE
SPEC.loader.exec_module(LIFECYCLE)


def _fixture(mode: str) -> list[str]:
    return [sys.executable, str(Path(__file__).resolve()), "--fixture", mode]


def _policy() -> dict[str, object]:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def _pubsub_pipe() -> tuple[int, int]:
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


def _drain_publication(read_fd: int, *, timeout: float) -> list[bytes]:
    """Event-driven (select-based) read of newline-delimited records, bounded by ``timeout``.

    Never a bare sleep-then-check: each iteration blocks only until the descriptor is
    actually readable or the overall deadline expires.
    """
    deadline = time.monotonic() + timeout
    lines: list[bytes] = []
    buffer = bytearray()
    while time.monotonic() < deadline:
        remaining = max(0.0, deadline - time.monotonic())
        ready, _write_ready, _err_ready = select.select([read_fd], [], [], min(0.5, remaining))
        if not ready:
            continue
        try:
            chunk = os.read(read_fd, 4096)
        except BlockingIOError:
            continue
        if not chunk:
            break
        buffer.extend(chunk)
        while b"\n" in buffer:
            line, _sep, rest = buffer.partition(b"\n")
            lines.append(bytes(line) + b"\n")
            buffer[:] = rest
    return lines


def _read_stdout_line(child: "subprocess.Popen[bytes]", *, timeout: float) -> str | None:
    """Event-driven (select-based) read of one stdout line from a still-running child."""
    deadline = time.monotonic() + timeout
    buffer = bytearray()
    fd = child.stdout.fileno()  # type: ignore[union-attr]
    while time.monotonic() < deadline:
        remaining = max(0.0, deadline - time.monotonic())
        ready, _write_ready, _err_ready = select.select([fd], [], [], min(0.5, remaining))
        if not ready:
            continue
        chunk = os.read(fd, 4096)
        if not chunk:
            return None
        buffer.extend(chunk)
        if b"\n" in buffer:
            line, _sep, _rest = buffer.partition(b"\n")
            return line.decode()
    return None


def _run_fixture(mode: str, **kwargs: object) -> dict[str, object]:
    defaults: dict[str, object] = {
        "provider_id": "codex",
        "profile_id": "codex_help",
        "invocation_id": "00000000-0000-4000-8000-000000000001",
        "env": {},
        "policy": json.loads(POLICY_PATH.read_text(encoding="utf-8")),
    }
    force_deadline = bool(kwargs.pop("_force_deadline", False))
    defaults.update(kwargs)
    original_deadline = LIFECYCLE._deadline_reached
    if force_deadline:
        forced_at = time.monotonic() + 0.15
        LIFECYCLE._deadline_reached = lambda now, _deadline: now >= forced_at
    try:
        return LIFECYCLE.run_owned_process(_fixture(mode), **defaults)
    finally:
        LIFECYCLE._deadline_reached = original_deadline


def _validator_for(definition: str) -> jsonschema.Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    selected = {
        "$schema": schema["$schema"],
        "$id": schema["$id"] + "#test-" + definition,
        "$ref": f"#/$defs/{definition}",
        "$defs": schema["$defs"],
    }
    return jsonschema.Draft202012Validator(
        selected, format_checker=jsonschema.FormatChecker()
    )


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        cls.vectors = json.loads(VECTORS_PATH.read_text(encoding="utf-8"))

    def test_schema_is_draft_2020_12_and_all_objects_are_closed(self) -> None:
        self.assertEqual(
            self.schema["$schema"], "https://json-schema.org/draft/2020-12/schema"
        )
        jsonschema.Draft202012Validator.check_schema(self.schema)
        object_nodes: list[dict[str, object]] = []

        def visit(node: object) -> None:
            if isinstance(node, dict):
                if node.get("type") == "object":
                    object_nodes.append(node)
                for value in node.values():
                    visit(value)
            elif isinstance(node, list):
                for value in node:
                    visit(value)

        visit(self.schema)
        self.assertTrue(object_nodes)
        self.assertTrue(all(node.get("additionalProperties") is False for node in object_nodes))

    def test_policy_is_exact_closed_and_has_no_override_surface(self) -> None:
        _validator_for("policy").validate(self.policy)
        self.assertEqual(
            self.policy["budgets"],
            {
                "provider_deadline_seconds": 45,
                "sigterm_grace_seconds": 2,
                "sigkill_reap_seconds": 1,
                "aggregate_deadline_seconds": 200,
                "attempts_per_provider": 1,
                "stderr_retention_bytes": 4096,
                "stdout_retention_bytes": 65536,
            },
        )
        expected = [
            ("codex", "codex_help", "codex"),
            ("qwen", "qwen_help", "qwen"),
            ("claude", "claude_help", "claude"),
            ("pi", "pi_help", "pi"),
        ]
        actual = [
            (entry["provider_id"], entry["profile_id"], entry["executable"])
            for entry in self.policy["profiles"]
        ]
        self.assertEqual(actual, expected)
        for entry in self.policy["profiles"]:
            self.assertEqual(entry["mode"], "exit_only")
            self.assertEqual(entry["argv"], [entry["executable"], "--help"])
        encoded = json.dumps(self.policy).lower()
        for forbidden in ("retry", "fallback", "environment", "override"):
            self.assertNotIn(forbidden, encoded)

    def test_policy_and_vectors_reject_unknown_fields_versions_and_classes(self) -> None:
        policy_validator = _validator_for("policy")
        vector_validator = _validator_for("vector_set")
        vector_validator.validate(self.vectors)
        mutations = []
        bad = copy.deepcopy(self.policy)
        bad["unknown"] = True
        mutations.append((policy_validator, bad))
        bad = copy.deepcopy(self.policy)
        bad["schema_version"] = "qa.provider-probe-policy.v2"
        mutations.append((policy_validator, bad))
        bad = copy.deepcopy(self.policy)
        bad["profiles"][0]["provider_id"] = "other"
        mutations.append((policy_validator, bad))
        bad = copy.deepcopy(self.policy)
        bad["profiles"][0]["profile_id"] = "other_help"
        mutations.append((policy_validator, bad))
        bad = copy.deepcopy(self.policy)
        bad["profiles"] = [copy.deepcopy(self.policy["profiles"][0]) for _ in range(4)]
        mutations.append((policy_validator, bad))
        bad = copy.deepcopy(self.policy)
        bad["profiles"][0], bad["profiles"][1] = bad["profiles"][1], bad["profiles"][0]
        mutations.append((policy_validator, bad))
        bad = copy.deepcopy(self.policy)
        bad["profiles"] = bad["profiles"][:-1]
        mutations.append((policy_validator, bad))
        bad = copy.deepcopy(self.vectors)
        bad["normalization_vectors"][0]["expected_failure_class"] = "mystery"
        mutations.append((vector_validator, bad))
        bad = copy.deepcopy(self.vectors)
        bad["adversarial_vectors"][0]["invariants"].append("unknown_action")
        mutations.append((vector_validator, bad))
        for validator, candidate in mutations:
            with self.assertRaises(jsonschema.ValidationError):
                validator.validate(candidate)

    def test_runtime_rejects_raised_budget_and_swapped_profile_without_spawn(self) -> None:
        raised = copy.deepcopy(self.policy)
        raised["budgets"]["provider_deadline_seconds"] = 46
        swapped = copy.deepcopy(self.policy)
        swapped["profiles"][0]["profile_id"] = "qwen_help"
        for policy in (raised, swapped):
            result = LIFECYCLE.run_owned_process(
                _fixture("exit_zero"),
                provider_id="codex",
                profile_id="codex_help",
                policy=policy,
                env={},
            )
            self.assertEqual(result["failure_class"], "contract_invalid")
            self.assertEqual(result["termination_actions"], [])
        crossed = LIFECYCLE.run_owned_process(
            _fixture("exit_zero"),
            provider_id="codex",
            profile_id="qwen_help",
            policy=self.policy,
            env={},
        )
        self.assertEqual(crossed["failure_class"], "contract_invalid")

    def test_result_schema_rejects_prohibited_and_unknown_values(self) -> None:
        validator = _validator_for("result")
        record = _run_fixture("exit_zero")
        validator.validate(record)
        prohibited = (
            "prompt",
            "credentials",
            "home",
            "environment",
            "terminal",
            "path",
            "stdout",
            "stderr",
            "pid",
            "pgid",
            "sid",
            "argv",
        )
        for field in prohibited:
            bad = dict(record)
            bad[field] = "canary"
            with self.assertRaises(jsonschema.ValidationError, msg=field):
                validator.validate(bad)
        for field, value in (
            ("schema_version", "v2"),
            ("provider_id", "other"),
            ("profile_id", "other"),
            ("lifecycle_state", "unknown"),
            ("result", "unknown"),
            ("failure_class", "unknown"),
        ):
            bad = dict(record)
            bad[field] = value
            with self.assertRaises(jsonschema.ValidationError, msg=field):
                validator.validate(bad)
        bad = copy.deepcopy(record)
        bad["termination_actions"][0]["action"] = "unknown"
        with self.assertRaises(jsonschema.ValidationError):
            validator.validate(bad)
        bad = copy.deepcopy(record)
        bad["disposition"]["class"] = "unknown"
        with self.assertRaises(jsonschema.ValidationError):
            validator.validate(bad)

    def test_heartbeat_schema_accepts_exact_boundary_records(self) -> None:
        validator = _validator_for("heartbeat")
        idle = {
            "schema_version": "qa.provider-probe-active.v1",
            "qa_invocation_id": "00000000-0000-4000-8000-000000000001",
            "provider_id": None,
            "lifecycle_state": "idle",
            "elapsed_ms": 0,
            "heartbeat_utc": "2026-07-18T17:23:48Z",
            "deadline_ms": 45000,
            "last_terminal_failure_class": None,
        }
        terminal = {
            **idle,
            "provider_id": "pi",
            "lifecycle_state": "terminal",
            "elapsed_ms": 300000,
            "last_terminal_failure_class": "none",
        }
        validator.validate(idle)
        validator.validate(terminal)
        for state in ("starting", "running", "terminating", "reaping"):
            validator.validate(
                {
                    **idle,
                    "provider_id": "codex",
                    "lifecycle_state": state,
                    "elapsed_ms": 1,
                }
            )
        terminal["last_terminal_failure_class"] = "deadline_exceeded"
        validator.validate(terminal)
        jsonschema.Draft202012Validator(
            self.schema, format_checker=jsonschema.FormatChecker()
        ).validate(terminal)

    def test_heartbeat_schema_rejects_invalid_and_sensitive_records(self) -> None:
        validator = _validator_for("heartbeat")
        base = {
            "schema_version": "qa.provider-probe-active.v1",
            "qa_invocation_id": "00000000-0000-4000-8000-000000000001",
            "provider_id": "claude",
            "lifecycle_state": "running",
            "elapsed_ms": 1,
            "heartbeat_utc": "2026-07-18T17:23:48Z",
            "deadline_ms": 45000,
            "last_terminal_failure_class": None,
        }
        invalid_values = (
            ("schema_version", "qa.provider-probe-active.v2"),
            ("qa_invocation_id", "not-a-uuid"),
            ("provider_id", "other"),
            ("lifecycle_state", "unknown"),
            ("elapsed_ms", -1),
            ("elapsed_ms", 300001),
            ("heartbeat_utc", "not-a-time"),
            ("heartbeat_utc", "2026-07-18T17:23:48+01:00"),
            ("deadline_ms", 45001),
            ("last_terminal_failure_class", "unknown"),
        )
        for field, value in invalid_values:
            bad = dict(base)
            bad[field] = value
            with self.assertRaises(jsonschema.ValidationError, msg=(field, value)):
                validator.validate(bad)

        invalid_relationships = (
            {**base, "provider_id": None},
            {**base, "provider_id": "codex", "lifecycle_state": "idle"},
            {**base, "last_terminal_failure_class": "none"},
            {
                **base,
                "lifecycle_state": "terminal",
                "last_terminal_failure_class": None,
            },
        )
        for bad in invalid_relationships:
            with self.assertRaises(jsonschema.ValidationError, msg=bad):
                validator.validate(bad)

        for missing in base:
            bad = dict(base)
            del bad[missing]
            with self.assertRaises(jsonschema.ValidationError, msg=missing):
                validator.validate(bad)

        prohibited = (
            "pid",
            "pgid",
            "sid",
            "argv",
            "executable",
            "stdout",
            "stderr",
            "output",
            "path",
            "environment",
            "prompt",
            "credential",
            "model",
            "host_identifier",
            "acceptance_verdict",
        )
        for field in prohibited:
            bad = dict(base)
            bad[field] = "canary"
            with self.assertRaises(jsonschema.ValidationError, msg=field):
                validator.validate(bad)

    def test_golden_normalization_is_one_spawn_and_covers_every_failure(self) -> None:
        seen = set()
        for vector in self.vectors["normalization_vectors"]:
            result, failure = LIFECYCLE.normalize_probe_output(
                mode=vector["mode"],
                stdout=vector["stdout"].encode(),
                exit_code=vector["exit_code"],
                lifecycle_failure=vector["lifecycle_failure"],
                stdout_truncated=vector["stdout_truncated"],
                stderr_truncated=vector["stderr_truncated"],
            )
            self.assertEqual((result, failure), (vector["expected_result"], vector["expected_failure_class"]), vector["id"])
            self.assertEqual(vector["spawn_count"], 1)
            seen.add(vector["expected_failure_class"])
        self.assertEqual(seen, set(LIFECYCLE.FAILURE_CLASSES))

    def test_machine_json_boundaries_and_closed_reason_codes(self) -> None:
        exact = b'{"schema_version":"qa.provider-probe-machine.v1","status":"pass","reason_code":"ok"}'
        self.assertEqual(
            LIFECYCLE.normalize_probe_output(mode="machine_json_v1", stdout=exact, exit_code=0),
            ("pass", "none"),
        )
        for bad in (
            exact + b"\n{}",
            exact.replace(b'"ok"', b'"new_reason"'),
            exact.replace(b".v1", b".v2"),
            exact[:-1],
        ):
            self.assertEqual(
                LIFECYCLE.normalize_probe_output(mode="machine_json_v1", stdout=bad, exit_code=0),
                ("fail", "machine_output_invalid"),
            )


class LifecycleTests(unittest.TestCase):
    def test_clean_exit_and_nonzero_are_reaped_once(self) -> None:
        clean = _run_fixture("exit_zero")
        nonzero = _run_fixture("exit_nonzero")
        self.assertEqual((clean["result"], clean["failure_class"], clean["exit_code"]), ("pass", "none", 0))
        self.assertEqual((nonzero["result"], nonzero["failure_class"], nonzero["exit_code"]), ("fail", "exit_nonzero", 23))
        for record in (clean, nonzero):
            self.assertEqual(record["termination_actions"][-1]["action"], "reap")
            self.assertEqual(record["termination_actions"][-1]["outcome"], "complete")

    def test_missing_executable_spawn_failure_and_invalid_contract(self) -> None:
        missing = LIFECYCLE.run_owned_process(
            ["/definitely/absent/qppr-c1"],
            provider_id="codex",
            profile_id="codex_help",
            invocation_id="00000000-0000-4000-8000-000000000002",
            policy=json.loads(POLICY_PATH.read_text(encoding="utf-8")),
            env={},
        )
        self.assertEqual(missing["failure_class"], "executable_missing")
        with tempfile.TemporaryDirectory() as directory:
            denied = Path(directory) / "not-executable"
            denied.write_text("not executable", encoding="utf-8")
            denied.chmod(0o600)
            spawn_failed = LIFECYCLE.run_owned_process(
                [str(denied)],
                provider_id="codex",
                profile_id="codex_help",
                invocation_id="00000000-0000-4000-8000-000000000003",
                policy=json.loads(POLICY_PATH.read_text(encoding="utf-8")),
                env={},
            )
        self.assertEqual(spawn_failed["failure_class"], "spawn_failed")
        invalid = LIFECYCLE.run_owned_process(
            _fixture("exit_zero"),
            provider_id="unknown",
            profile_id="codex_help",
            invocation_id="00000000-0000-4000-8000-000000000004",
            policy=json.loads(POLICY_PATH.read_text(encoding="utf-8")),
        )
        self.assertEqual(invalid["failure_class"], "contract_invalid")

    def test_timeout_self_stop_and_fork_cleanup_order(self) -> None:
        for mode in ("sleep", "self_stop", "fork_sleep"):
            result = _run_fixture(mode, _force_deadline=True)
            self.assertEqual(result["failure_class"], "deadline_exceeded", mode)
            actions = [entry["action"] for entry in result["termination_actions"]]
            self.assertLess(actions.index("sigcont"), actions.index("sigterm"))
            self.assertLess(actions.index("sigterm"), actions.index("sigkill"))
            self.assertLess(actions.index("sigkill"), actions.index("quiescence"))
            self.assertLess(actions.index("quiescence"), actions.index("reap"))
            self.assertEqual(result["termination_actions"][-2]["outcome"], "complete")

    def test_esrch_is_not_quiescence_and_no_group_signal_follows_reap(self) -> None:
        original_killpg = LIFECYCLE.os.killpg
        original_reap = LIFECYCLE._reap_pid
        state = {"first": True, "reaped": False}

        def raced_killpg(pgid: int, sig: int) -> None:
            self.assertFalse(state["reaped"], "numeric group signal occurred after leader reap")
            if state["first"]:
                state["first"] = False
                raise ProcessLookupError()
            original_killpg(pgid, sig)

        def observed_reap(pid: int, *, deadline: float) -> bool:
            result = original_reap(pid, deadline=deadline)
            state["reaped"] = result
            return result

        LIFECYCLE.os.killpg = raced_killpg
        LIFECYCLE._reap_pid = observed_reap
        try:
            result = _run_fixture("sleep", _force_deadline=True)
        finally:
            LIFECYCLE.os.killpg = original_killpg
            LIFECYCLE._reap_pid = original_reap
        self.assertEqual(result["failure_class"], "deadline_exceeded")
        self.assertEqual(result["termination_actions"][0], {"action": "sigcont", "outcome": "failed", "at_ms": result["termination_actions"][0]["at_ms"]})
        self.assertTrue(state["reaped"])

    def test_subreaper_value_is_restored_on_success_and_timeout(self) -> None:
        before = LIFECYCLE._prctl(LIFECYCLE._PR_GET_CHILD_SUBREAPER)
        _run_fixture("exit_zero")
        self.assertEqual(LIFECYCLE._prctl(LIFECYCLE._PR_GET_CHILD_SUBREAPER), before)
        _run_fixture("sleep", _force_deadline=True)
        self.assertEqual(LIFECYCLE._prctl(LIFECYCLE._PR_GET_CHILD_SUBREAPER), before)

    def test_direct_child_already_reaped_fails_without_numeric_group_signal(self) -> None:
        original_pidfd_open = LIFECYCLE.os.pidfd_open
        original_killpg = LIFECYCLE.os.killpg
        reaper_done = threading.Event()

        def racing_pidfd_open(pid: int, flags: int = 0) -> int:
            descriptor = original_pidfd_open(pid, flags)

            def reap_direct_child() -> None:
                try:
                    os.waitpid(pid, 0)
                except ChildProcessError:
                    pass
                reaper_done.set()

            threading.Thread(target=reap_direct_child, daemon=True).start()
            return descriptor

        def forbidden_group_signal(_pgid: int, _sig: int) -> None:
            raise AssertionError("stale numeric group signal after external direct-child reap")

        LIFECYCLE.os.pidfd_open = racing_pidfd_open
        LIFECYCLE.os.killpg = forbidden_group_signal
        try:
            result = _run_fixture("exit_zero")
        finally:
            LIFECYCLE.os.pidfd_open = original_pidfd_open
            LIFECYCLE.os.killpg = original_killpg
        self.assertTrue(reaper_done.wait(1.0))
        self.assertEqual(result["failure_class"], "contract_invalid")

    def test_leader_exit_zero_with_live_child_is_cleanup_failed(self) -> None:
        result = _run_fixture("leader_zero_child")
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["failure_class"], "cleanup_failed")
        self.assertEqual(result["termination_actions"][-2]["action"], "quiescence")
        self.assertEqual(result["termination_actions"][-2]["outcome"], "complete")

    def test_stderr_flood_drains_redacts_controls_paths_and_caps(self) -> None:
        result = _run_fixture("stderr_flood")
        self.assertEqual(result["failure_class"], "output_limit_exceeded")
        self.assertTrue(result["stderr_truncated"])
        encoded = result["stderr_summary"].encode("utf-8")
        self.assertLessEqual(len(encoded), 4096)
        self.assertNotIn("super-secret", result["stderr_summary"])
        self.assertNotIn("bearer-secret", result["stderr_summary"].lower())
        self.assertNotIn("standalone-secret", result["stderr_summary"].lower())
        self.assertNotIn("/home/private/credential", result["stderr_summary"])
        self.assertNotIn("\x00", result["stderr_summary"])
        self.assertIn("[REDACTED]", result["stderr_summary"])
        self.assertIn("<PATH>", result["stderr_summary"])

    def test_probe_busy_is_nonblocking_and_owner_lock_is_unchanged(self) -> None:
        self.assertTrue(LIFECYCLE._INVOCATION_LOCK.acquire(blocking=False))
        try:
            started = time.monotonic()
            result = _run_fixture("exit_zero")
            self.assertLess(time.monotonic() - started, 0.25)
            self.assertEqual(result["failure_class"], "probe_busy")
            self.assertTrue(LIFECYCLE._INVOCATION_LOCK.locked())
        finally:
            LIFECYCLE._INVOCATION_LOCK.release()

    def test_new_session_escape_is_reported_without_group_targeting_escape(self) -> None:
        result = _run_fixture("escape_session")
        self.assertEqual(result["failure_class"], "cleanup_failed")
        actions = [entry["action"] for entry in result["termination_actions"]]
        self.assertEqual(actions[-1], "reap")
        time.sleep(0.7)
        while True:
            try:
                pid, _ = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                break
            if pid == 0:
                break

    def test_result_digest_is_deterministic_and_excludes_raw_streams(self) -> None:
        result = _run_fixture("exit_zero")
        digest = result.pop("evidence_digest")
        expected = "sha256:" + __import__("hashlib").sha256(
            json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        self.assertEqual(digest, expected)
        self.assertFalse(set(result) & {"stdout", "stderr", "argv", "pid", "pgid", "sid", "env"})


class OuterSignalTests(unittest.TestCase):
    def _outer(self, disposition: str, sig: int, second: bool = False) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            _fixture(f"outer:{disposition}:{sig}:{int(second)}"),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )

    def test_default_sigterm_and_sigint_terminate_by_restored_signal(self) -> None:
        for sig in (signal.SIGTERM, signal.SIGINT):
            started = time.monotonic()
            completed = self._outer("default", sig)
            self.assertEqual(completed.returncode, -sig)
            self.assertLess(time.monotonic() - started, 5.5)

    def test_returning_custom_handler_is_restored_and_redelivered_once(self) -> None:
        completed = self._outer("custom_return", signal.SIGTERM, second=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
        self.assertEqual(payload["handler_calls"], 1)
        self.assertEqual(payload["result"]["failure_class"], "interrupted")
        self.assertEqual(payload["result"]["disposition"]["class"], "custom")
        self.assertTrue(payload["result"]["disposition"]["redelivered"])
        self.assertGreaterEqual(payload["result"]["disposition"]["coalesced_signals"], 1)
        self.assertTrue(payload["handler_restored"])
        self.assertLess(payload["elapsed"], 5.0)

    def test_ignored_disposition_is_preserved_without_forced_exit(self) -> None:
        completed = self._outer("ignored", signal.SIGINT)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
        self.assertEqual(payload["result"]["failure_class"], "interrupted")
        self.assertEqual(payload["result"]["disposition"]["class"], "ignored")
        self.assertTrue(payload["handler_restored"])
        self.assertLess(payload["elapsed"], 5.0)

    def test_nonreturning_custom_handler_controls_post_redelivery_exit(self) -> None:
        completed = self._outer("custom_exit", signal.SIGTERM)
        self.assertEqual(completed.returncode, 71)
        observation = json.loads(completed.stdout.strip().splitlines()[-1])
        self.assertEqual(observation["handler_subreaper"], observation["prior_subreaper"])

    def test_terminating_redelivery_observes_restored_subreaper(self) -> None:
        completed = self._outer("custom_terminate_observe", signal.SIGTERM)
        self.assertEqual(completed.returncode, -signal.SIGTERM)
        observation = json.loads(completed.stdout.strip().splitlines()[-1])
        self.assertEqual(observation["handler_subreaper"], observation["prior_subreaper"])

    def test_raising_custom_handler_is_redelivered_exactly_once(self) -> None:
        completed = self._outer("custom_raise", signal.SIGTERM)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        observation = json.loads(completed.stdout.strip().splitlines()[-1])
        self.assertEqual(observation["handler_calls"], 1)
        self.assertEqual(observation["handler_subreaper"], observation["prior_subreaper"])
        self.assertTrue(observation["handler_restored"])
        self.assertTrue(observation["lock_restored"])

    def test_injected_cleanup_fault_still_tears_down_before_one_redelivery(self) -> None:
        completed = self._outer("custom_cleanup_fault", signal.SIGTERM)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        observation = json.loads(completed.stdout.strip().splitlines()[-1])
        self.assertEqual(observation["result"]["failure_class"], "cleanup_failed")
        self.assertEqual(observation["handler_calls"], 1)
        self.assertEqual(observation["handler_subreaper"], observation["prior_subreaper"])
        self.assertTrue(observation["handler_lock_released"])
        self.assertTrue(observation["pidfds_closed"])
        self.assertEqual(observation["owned_children_after"], [])
        self.assertEqual(observation["result"]["termination_actions"][-2]["outcome"], "complete")
        self.assertEqual(observation["result"]["termination_actions"][-1], {
            "action": "reap",
            "outcome": "complete",
            "at_ms": observation["result"]["termination_actions"][-1]["at_ms"],
        })

    def test_second_signal_during_each_cleanup_action_is_coalesced(self) -> None:
        for phase in ("sigterm", "sigkill", "reap"):
            completed = self._outer("custom_phase_" + phase, signal.SIGTERM)
            self.assertEqual(completed.returncode, 0, (phase, completed.stderr))
            payload = json.loads(completed.stdout.strip().splitlines()[-1])
            self.assertEqual(payload["handler_calls"], 1, phase)
            self.assertGreaterEqual(payload["result"]["disposition"]["coalesced_signals"], 1, phase)
            self.assertLess(payload["elapsed"], 5.0)

    def test_blocked_publication_cannot_delay_redelivery_past_slo(self) -> None:
        completed = self._outer("custom_return_pub", signal.SIGTERM)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
        self.assertLess(payload["signal_to_redelivery_elapsed"], 5.0)

    def test_legacy_publication_without_barrier_fd_still_uses_a_worker_thread(self) -> None:
        # R2/Proof 5: the legacy path (publication without publication_fd) is byte-frozen --
        # it must still spawn exactly the same daemon worker thread as before AM3.
        original_thread_cls = LIFECYCLE.threading.Thread
        constructed_targets: list[object] = []

        class _TrackedThread(original_thread_cls):  # type: ignore[misc,valid-type]
            def __init__(self, *args: object, **kwargs: object) -> None:
                constructed_targets.append(kwargs.get("target"))
                super().__init__(*args, **kwargs)

        def publication(_record: dict[str, object]) -> None:
            pass

        def sender() -> None:
            time.sleep(0.15)
            os.kill(os.getpid(), signal.SIGTERM)

        # A returning custom handler must be the prior disposition, or redelivery terminates
        # this test process via default SIG_DFL (see the in-process barrier tests).
        def returning_handler(_signum: int, _frame: object) -> None:
            pass

        prior = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGTERM, returning_handler)
        threading.Thread(target=sender, daemon=True).start()
        LIFECYCLE.threading.Thread = _TrackedThread
        try:
            result = LIFECYCLE.run_owned_process(
                _fixture("sleep"),
                provider_id="codex",
                profile_id="codex_help",
                policy=_policy(),
                invocation_id="00000000-0000-4000-8000-000000000010",
                env={},
                publication=publication,
            )
        finally:
            LIFECYCLE.threading.Thread = original_thread_cls
            signal.signal(signal.SIGTERM, prior)
        self.assertEqual(result["failure_class"], "interrupted")
        self.assertIn(publication, constructed_targets)


class PublicationBarrierInProcessTests(unittest.TestCase):
    """R1-R4 in-process proofs: the synchronous barrier does not need subprocess isolation
    for the on-time/completed and zero-budget/cancelled cases, since neither one blocks the
    calling thread beyond a bounded, short interval."""

    def test_on_time_publication_barrier_invokes_callback_and_emits_exact_sequence(self) -> None:
        read_fd, write_fd = _pubsub_pipe()
        prior = signal.getsignal(signal.SIGTERM)
        invoked = {"count": 0}

        def publication(_record: dict[str, object]) -> None:
            invoked["count"] += 1

        def sender() -> None:
            time.sleep(0.15)
            os.kill(os.getpid(), signal.SIGTERM)

        # A returning custom handler, installed before the call, becomes the "prior"
        # disposition that _restore_and_redeliver restores and then redelivers to -- without
        # this, redelivery would fall through to the default SIG_DFL disposition and
        # terminate this very test process instead of just returning.
        def returning_handler(_signum: int, _frame: object) -> None:
            pass

        signal.signal(signal.SIGTERM, returning_handler)
        threading.Thread(target=sender, daemon=True).start()
        try:
            result = LIFECYCLE.run_owned_process(
                _fixture("sleep"),
                provider_id="codex",
                profile_id="codex_help",
                policy=_policy(),
                invocation_id="00000000-0000-4000-8000-00000000000e",
                env={},
                publication=publication,
                publication_fd=write_fd,
            )
        finally:
            signal.signal(signal.SIGTERM, prior)
            os.close(write_fd)
        raw = _read_all(read_fd)
        os.close(read_fd)
        lines = raw.splitlines(keepends=True)
        self.assertEqual(len(lines), 2)
        first = LIFECYCLE.parse_publication_record(lines[0])
        second = LIFECYCLE.parse_publication_record(lines[1])
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertEqual((first[0], first[1]), (1, "running"))
        self.assertEqual((second[0], second[1]), (2, "completed"))
        self.assertEqual(invoked["count"], 1)
        self.assertEqual(result["failure_class"], "interrupted")
        self.assertEqual(
            LIFECYCLE.classify_publication_contract("completed", first[2], second[2], True),
            "completed",
        )

    def test_zero_budget_publication_barrier_emits_cancelled_without_invoking_callback(self) -> None:
        read_fd, write_fd = _pubsub_pipe()
        prior = signal.getsignal(signal.SIGTERM)
        invoked = {"count": 0}

        def publication(_record: dict[str, object]) -> None:
            invoked["count"] += 1

        def sender() -> None:
            time.sleep(0.15)
            os.kill(os.getpid(), signal.SIGTERM)

        # See test_on_time_publication_barrier_...: a returning custom handler must be the
        # prior disposition, or redelivery terminates this test process via default SIG_DFL.
        def returning_handler(_signum: int, _frame: object) -> None:
            pass

        signal.signal(signal.SIGTERM, returning_handler)

        # Deterministically exhaust the ~4.9s barrier budget by controlling the clock the
        # barrier reads (LIFECYCLE.time.monotonic), not by sleeping: once normalize_probe_output
        # (the last call before the barrier) has run, the module clock jumps far past
        # first_signal_at + 4.9s, so remaining budget is exactly zero regardless of how long
        # TERM grace/reaping took in real time.
        original_normalize = LIFECYCLE.normalize_probe_output
        original_time = LIFECYCLE.time
        skew = {"offset": 0.0}

        class _SkewedTime:
            def __getattr__(self, name: str) -> object:
                return getattr(original_time, name)

            def monotonic(self) -> float:
                return original_time.monotonic() + skew["offset"]

        def delayed_normalize(**kwargs: object) -> tuple[str, str]:
            skew["offset"] = 60.0
            return original_normalize(**kwargs)

        threading.Thread(target=sender, daemon=True).start()
        LIFECYCLE.normalize_probe_output = delayed_normalize
        LIFECYCLE.time = _SkewedTime()
        try:
            result = LIFECYCLE.run_owned_process(
                _fixture("ignore_term_sleep"),
                provider_id="codex",
                profile_id="codex_help",
                policy=_policy(),
                invocation_id="00000000-0000-4000-8000-00000000000f",
                env={},
                publication=publication,
                publication_fd=write_fd,
            )
        finally:
            LIFECYCLE.normalize_probe_output = original_normalize
            LIFECYCLE.time = original_time
            signal.signal(signal.SIGTERM, prior)
            os.close(write_fd)
        raw = _read_all(read_fd)
        os.close(read_fd)
        lines = raw.splitlines(keepends=True)
        self.assertEqual(len(lines), 2)
        first = LIFECYCLE.parse_publication_record(lines[0])
        second = LIFECYCLE.parse_publication_record(lines[1])
        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertEqual((first[0], first[1]), (1, "running"))
        self.assertEqual((second[0], second[1]), (2, "cancelled"))
        self.assertEqual(invoked["count"], 0)
        self.assertEqual(result["failure_class"], "interrupted")


class PublicationRecordAndClassifierTests(unittest.TestCase):
    """R6/R7/Proof 4: fail-closed record validation and the pure authoritative classifier."""

    def test_parse_publication_record_accepts_exact_wire_format(self) -> None:
        self.assertEqual(
            LIFECYCLE.parse_publication_record(b"qa.provider-publication.v1|1|running|1234\n"),
            (1, "running", 1234),
        )
        self.assertEqual(
            LIFECYCLE.parse_publication_record(b"qa.provider-publication.v1|2|completed|1235\n"),
            (2, "completed", 1235),
        )
        self.assertEqual(
            LIFECYCLE.parse_publication_record(b"qa.provider-publication.v1|2|cancelled|1235\n"),
            (2, "cancelled", 1235),
        )
        self.assertEqual(
            LIFECYCLE.parse_publication_record(
                b"qa.provider-publication.v1|2|contract_violation|1235\n"
            ),
            (2, "contract_violation", 1235),
        )

    def test_parse_publication_record_fails_closed_on_malformed_input(self) -> None:
        bad_records = (
            b"",
            b"\n",
            b"qa.provider-publication.v1|1|running|1234",
            b"qa.provider-publication.v2|1|running|1234\n",
            b"qa.provider-publication.v1|1|completed|1234\n",
            b"qa.provider-publication.v1|2|running|1234\n",
            b"qa.provider-publication.v1|3|running|1234\n",
            b"qa.provider-publication.v1|1|running|-1\n",
            b"qa.provider-publication.v1|1|running|12.5\n",
            b"qa.provider-publication.v1|1|running|\n",
            b"qa.provider-publication.v1|1|running|1234|extra\n",
            b"qa.provider-publication.v1|1|running\n",
            "qa.provider-publication.v1|1|running|1234\n".encode("utf-8") + b"\xff",
            b"qa.provider-publication.v1|1|running|" + b"9" * 20 + b"\n",
            b"x" * 200,
        )
        for record in bad_records:
            self.assertIsNone(LIFECYCLE.parse_publication_record(record), record)

    def test_accept_publication_record_rejects_duplicate_backward_and_post_terminal(self) -> None:
        running = b"qa.provider-publication.v1|1|running|1000\n"
        completed = b"qa.provider-publication.v1|2|completed|1001\n"

        self.assertEqual(
            LIFECYCLE.accept_publication_record(running, last_sequence=0, terminal=False),
            (1, "running", 1000),
        )
        self.assertIsNone(
            LIFECYCLE.accept_publication_record(running, last_sequence=1, terminal=False)
        )
        self.assertIsNone(
            LIFECYCLE.accept_publication_record(running, last_sequence=2, terminal=True)
        )
        self.assertEqual(
            LIFECYCLE.accept_publication_record(completed, last_sequence=1, terminal=False),
            (2, "completed", 1001),
        )
        self.assertIsNone(
            LIFECYCLE.accept_publication_record(completed, last_sequence=2, terminal=True)
        )
        violation = b"qa.provider-publication.v1|2|contract_violation|2000\n"
        self.assertIsNone(
            LIFECYCLE.accept_publication_record(violation, last_sequence=1, terminal=True)
        )

    def test_classify_publication_contract_matches_am2_rule_and_never_treats_missing_as_violated(
        self,
    ) -> None:
        self.assertEqual(
            LIFECYCLE.classify_publication_contract(None, 1000, 999999, False), "unavailable"
        )
        self.assertEqual(
            LIFECYCLE.classify_publication_contract(None, 1000, 500, False), "unavailable"
        )
        self.assertEqual(
            LIFECYCLE.classify_publication_contract("running", 1000, 999, False), "running"
        )
        self.assertEqual(
            LIFECYCLE.classify_publication_contract("running", 1000, 1000, False), "running"
        )
        self.assertEqual(
            LIFECYCLE.classify_publication_contract("running", 1000, 1001, False),
            "contract_violation",
        )
        self.assertEqual(
            LIFECYCLE.classify_publication_contract("running", 1000, 1001, True), "running"
        )
        for state in ("completed", "cancelled", "contract_violation"):
            self.assertEqual(
                LIFECYCLE.classify_publication_contract(state, 1000, 999999, False), state
            )
        self.assertEqual(
            LIFECYCLE.classify_publication_contract("bogus", 1000, 1, False), "unavailable"
        )

    def test_classifier_composed_with_stream_acceptance_cannot_be_downgraded_after_violation(
        self,
    ) -> None:
        running = b"qa.provider-publication.v1|1|running|1000\n"
        stray_completed = b"qa.provider-publication.v1|2|completed|1002\n"

        accepted = LIFECYCLE.accept_publication_record(running, last_sequence=0, terminal=False)
        self.assertIsNotNone(accepted)
        last_sequence, last_state, _value = accepted
        classification = LIFECYCLE.classify_publication_contract(last_state, 1000, 1001, False)
        self.assertEqual(classification, "contract_violation")

        # The consumer marks the stream terminal once it classifies a violation, matching how
        # the production observer's own terminal_attempted latch behaves.
        terminal = True
        last_state = "contract_violation"

        rejected = LIFECYCLE.accept_publication_record(
            stray_completed, last_sequence=last_sequence, terminal=terminal
        )
        self.assertIsNone(rejected)
        self.assertEqual(
            LIFECYCLE.classify_publication_contract(last_state, 1000, 1001, False),
            "contract_violation",
        )


class PublicationBarrierSubprocessTests(unittest.TestCase):
    """R5/R6/Proofs 2-3: subprocess-fixture, event-barrier proofs of structural fail-stop.

    Both scenarios run the synchronous barrier in an isolated child process because a
    never-returning (or slow-returning past the deadline) callback blocks the owner thread
    synchronously by design (R6) -- exercising that safely requires a process the parent can
    observe from outside and, for the never-return case, terminate and reap.
    """

    def _spawn(self, pub_mode: str, write_fd: int) -> "subprocess.Popen[bytes]":
        env = dict(os.environ)
        env["QPPR_PUBLICATION_FD"] = str(write_fd)
        return subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--fixture", f"pub:{pub_mode}"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            pass_fds=(write_fd,),
            env=env,
        )

    def test_never_returning_callback_blocks_owner_with_no_restoration_and_isolated_reap(
        self,
    ) -> None:
        read_fd, write_fd = _pubsub_pipe()
        child = self._spawn("never_return", write_fd)
        os.close(write_fd)
        try:
            records = _drain_publication(read_fd, timeout=5.0)
            self.assertEqual(len(records), 1, records)
            running = LIFECYCLE.parse_publication_record(records[0])
            self.assertIsNotNone(running)
            self.assertEqual((running[0], running[1]), (1, "running"))
            deadline_ms = running[2]
            # Injected classifier time one millisecond past the bound: the classifier is a
            # pure function, so there is no need to wait for real time to elapse.
            self.assertEqual(
                LIFECYCLE.classify_publication_contract(
                    "running", deadline_ms, deadline_ms + 1, False
                ),
                "contract_violation",
            )

            # The watcher-thread evidence line proves the owner thread is inside the
            # synchronous call with the invocation lock still held.
            evidence_line = _read_stdout_line(child, timeout=5.0)
            self.assertIsNotNone(evidence_line)
            evidence = json.loads(evidence_line)
            self.assertTrue(evidence["lock_held_in_callback"])

            # No further output ever arrives on either channel: no ordinary return, no
            # redelivery report, no follow-up probe report, no second publication record --
            # the owner is blocked synchronously inside the callback and structurally cannot
            # reach any of that code.
            self.assertIsNone(_read_stdout_line(child, timeout=1.5))
            self.assertEqual(_drain_publication(read_fd, timeout=0.5), [])
        finally:
            child.kill()
            child.wait(timeout=5.0)
            if child.stdout is not None:
                child.stdout.close()
            if child.stderr is not None:
                child.stderr.close()
            os.close(read_fd)

    def test_late_return_permanently_fail_stops_and_blocks_a_later_provider(self) -> None:
        read_fd, write_fd = _pubsub_pipe()
        child = self._spawn("late_return", write_fd)
        os.close(write_fd)
        try:
            stdout_data, stderr_data = child.communicate(timeout=15.0)
            self.assertEqual(child.returncode, 0, stderr_data)
            records = _drain_publication(read_fd, timeout=1.0)
            self.assertEqual(len(records), 2, records)
            running = LIFECYCLE.parse_publication_record(records[0])
            violation = LIFECYCLE.parse_publication_record(records[1])
            self.assertIsNotNone(running)
            self.assertIsNotNone(violation)
            self.assertEqual((running[0], running[1]), (1, "running"))
            self.assertEqual((violation[0], violation[1]), (2, "contract_violation"))
            self.assertEqual(
                LIFECYCLE.classify_publication_contract(
                    "contract_violation", running[2], violation[2], False
                ),
                "contract_violation",
            )
            payload = json.loads(stdout_data.decode())
            self.assertTrue(payload["lock_held_after_violation"])
            self.assertNotIn(True, payload["thread_constructions"])
            self.assertEqual(payload["follow_up_failure_class"], "probe_busy")
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5.0)
            os.close(read_fd)


def _fixture_publication_main(pub_mode: str) -> int:
    """Child-process entry point for the subprocess-isolated publication-barrier fixtures.

    Runs a real ``run_owned_process`` invocation with the synchronous opt-in barrier wired to
    the ``QPPR_PUBLICATION_FD`` descriptor inherited (via ``pass_fds``) from the parent test.
    """
    fd = int(os.environ["QPPR_PUBLICATION_FD"])
    # pass_fds necessarily clears FD_CLOEXEC to survive exec; the barrier contract requires it
    # set, so it is restored here -- exactly the shape of a caller handing off a prepared fd.
    fd_flags = fcntl.fcntl(fd, fcntl.F_GETFD)
    fcntl.fcntl(fd, fcntl.F_SETFD, fd_flags | fcntl.FD_CLOEXEC)
    status_flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    if not status_flags & os.O_NONBLOCK:
        fcntl.fcntl(fd, fcntl.F_SETFL, status_flags | os.O_NONBLOCK)

    constructed_targets: list[object] = []
    original_thread_cls = LIFECYCLE.threading.Thread

    class _TrackedThread(original_thread_cls):  # type: ignore[misc,valid-type]
        def __init__(self, *args: object, **kwargs: object) -> None:
            constructed_targets.append(kwargs.get("target"))
            super().__init__(*args, **kwargs)

    LIFECYCLE.threading.Thread = _TrackedThread

    def sender() -> None:
        time.sleep(0.3)
        os.kill(os.getpid(), signal.SIGTERM)

    threading.Thread(target=sender, daemon=True).start()

    entered = threading.Event()
    evidence: dict[str, object] = {}

    def publication(_record: dict[str, object]) -> None:
        evidence["lock_held_in_callback"] = LIFECYCLE._INVOCATION_LOCK.locked()
        entered.set()
        if pub_mode == "never_return":
            threading.Event().wait()
        else:
            threading.Event().wait(timeout=6.0)

    if pub_mode == "never_return":

        def watcher() -> None:
            if entered.wait(timeout=4.0):
                print(json.dumps(evidence, sort_keys=True), flush=True)

        threading.Thread(target=watcher, daemon=True).start()

    policy = _policy()
    try:
        LIFECYCLE.run_owned_process(
            _fixture("sleep"),
            provider_id="codex",
            profile_id="codex_help",
            policy=policy,
            invocation_id="00000000-0000-4000-8000-00000000000c",
            env={},
            publication=publication,
            publication_fd=fd,
        )
    except LIFECYCLE._PublicationContractViolation:
        follow_up = LIFECYCLE.run_owned_process(
            _fixture("exit_zero"),
            provider_id="codex",
            profile_id="codex_help",
            policy=policy,
            invocation_id="00000000-0000-4000-8000-00000000000d",
            env={},
        )
        print(
            json.dumps(
                {
                    "lock_held_after_violation": LIFECYCLE._INVOCATION_LOCK.locked(),
                    "thread_constructions": [
                        target is publication for target in constructed_targets
                    ],
                    "follow_up_failure_class": follow_up["failure_class"],
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return 0
    # An ordinary return is not exercised by either fixture mode; treat it as an unexpected
    # outcome so a regression cannot silently pass as a "late" or "never" proof.
    return 65


def _fixture_main(mode: str) -> int:
    if mode.startswith("pub:"):
        return _fixture_publication_main(mode[len("pub:") :])
    if mode == "exit_zero":
        return 0
    if mode == "exit_nonzero":
        return 23
    if mode == "sleep":
        time.sleep(30)
        return 0
    if mode == "ignore_term_sleep":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        time.sleep(30)
        return 0
    if mode == "self_stop":
        os.kill(os.getpid(), signal.SIGSTOP)
        time.sleep(30)
        return 0
    if mode == "fork_sleep":
        if os.fork() == 0:
            time.sleep(30)
            os._exit(0)
        time.sleep(30)
        return 0
    if mode == "leader_zero_child":
        if os.fork() == 0:
            time.sleep(30)
            os._exit(0)
        return 0
    if mode == "stderr_flood":
        prefix = b"token=super-secret Authorization: Bearer bearer-secret Bearer standalone-secret /home/private/credential\x00\x01\n"
        os.write(2, prefix + b"X" * 200000)
        return 0
    if mode == "escape_session":
        ready_read, ready_write = os.pipe()
        if os.fork() == 0:
            os.close(ready_read)
            os.setsid()
            os.write(ready_write, b"1")
            os.close(ready_write)
            time.sleep(0.5)
            os._exit(0)
        os.close(ready_write)
        os.read(ready_read, 1)
        os.close(ready_read)
        return 0
    if mode.startswith("outer:"):
        _, disposition, sig_text, second_text = mode.split(":")
        sig = int(sig_text)
        calls = {"count": 0}

        def custom(_signum: int, _frame: object) -> None:
            calls["count"] += 1

        def custom_exit(_signum: int, _frame: object) -> None:
            observation = {
                "handler_subreaper": LIFECYCLE._prctl(LIFECYCLE._PR_GET_CHILD_SUBREAPER),
                "prior_subreaper": prior_subreaper,
            }
            os.write(1, (json.dumps(observation) + "\n").encode())
            os._exit(71)

        def custom_terminate_observe(signum: int, _frame: object) -> None:
            observation = {
                "handler_subreaper": LIFECYCLE._prctl(LIFECYCLE._PR_GET_CHILD_SUBREAPER),
                "prior_subreaper": prior_subreaper,
            }
            os.write(1, (json.dumps(observation) + "\n").encode())
            signal.signal(signum, signal.SIG_DFL)
            os.kill(os.getpid(), signum)

        def custom_raise(_signum: int, _frame: object) -> None:
            calls["count"] += 1
            calls["subreaper"] = LIFECYCLE._prctl(LIFECYCLE._PR_GET_CHILD_SUBREAPER)
            raise RuntimeError("expected raising disposition")

        def custom_cleanup_fault(_signum: int, _frame: object) -> None:
            calls["count"] += 1
            calls["subreaper"] = LIFECYCLE._prctl(LIFECYCLE._PR_GET_CHILD_SUBREAPER)
            calls["lock_released"] = not LIFECYCLE._INVOCATION_LOCK.locked()

        prior_subreaper = LIFECYCLE._prctl(LIFECYCLE._PR_GET_CHILD_SUBREAPER)

        if disposition == "default":
            prior = signal.SIG_DFL
        elif disposition == "ignored":
            prior = signal.SIG_IGN
        elif disposition == "custom_exit":
            prior = custom_exit
        elif disposition == "custom_terminate_observe":
            prior = custom_terminate_observe
        elif disposition == "custom_raise":
            prior = custom_raise
        elif disposition == "custom_cleanup_fault":
            prior = custom_cleanup_fault
        else:
            prior = custom
        signal.signal(sig, prior)

        phase = disposition.removeprefix("custom_phase_") if disposition.startswith("custom_phase_") else None
        phase_fired = {"value": False}
        original_send_group = LIFECYCLE._send_group
        original_reap_pid = LIFECYCLE._reap_pid

        def phase_send_group(identity: object, child_signal: int) -> str:
            if (
                phase in {"sigterm", "sigkill"}
                and child_signal == getattr(signal, phase.upper())
                and not phase_fired["value"]
            ):
                phase_fired["value"] = True
                os.kill(os.getpid(), sig)
            return original_send_group(identity, child_signal)

        def phase_reap_pid(pid: int, *, deadline: float) -> bool:
            if phase == "reap" and not phase_fired["value"]:
                phase_fired["value"] = True
                os.kill(os.getpid(), sig)
            return original_reap_pid(pid, deadline=deadline)

        if phase:
            LIFECYCLE._send_group = phase_send_group
            LIFECYCLE._reap_pid = phase_reap_pid

        captured_pidfds: list[int] = []
        original_pidfd_open = LIFECYCLE.os.pidfd_open
        original_send_for_fault = LIFECYCLE._send_group
        faulted = {"value": False}

        def capture_pidfd(pid: int, flags: int = 0) -> int:
            descriptor = original_pidfd_open(pid, flags)
            captured_pidfds.append(descriptor)
            return descriptor

        def inject_cleanup_fault(identity: object, child_signal: int) -> str:
            if child_signal == signal.SIGTERM and not faulted["value"]:
                faulted["value"] = True
                raise RuntimeError("injected primary cleanup fault")
            return original_send_for_fault(identity, child_signal)

        if disposition == "custom_cleanup_fault":
            LIFECYCLE.os.pidfd_open = capture_pidfd
            LIFECYCLE._send_group = inject_cleanup_fault

        signal_sent_at = {"value": 0.0}

        def sender() -> None:
            # Give the local deterministic child time to install fixture-specific dispositions.
            time.sleep(0.4)
            signal_sent_at["value"] = time.monotonic()
            os.kill(os.getpid(), sig)
            if second_text == "1":
                time.sleep(0.03)
                os.kill(os.getpid(), sig)

        threading.Thread(target=sender, daemon=True).start()
        started = time.monotonic()
        try:
            result = LIFECYCLE.run_owned_process(
                _fixture("ignore_term_sleep" if phase else "sleep"),
                provider_id="codex",
                profile_id="codex_help",
                policy=json.loads(POLICY_PATH.read_text(encoding="utf-8")),
                invocation_id="00000000-0000-4000-8000-000000000009",
                env={},
                publication=(lambda _record: time.sleep(30)) if disposition == "custom_return_pub" else None,
            )
        except RuntimeError as exc:
            if disposition != "custom_raise" or str(exc) != "expected raising disposition":
                raise
            print(
                json.dumps(
                    {
                        "handler_calls": calls["count"],
                        "handler_subreaper": calls.get("subreaper"),
                        "prior_subreaper": prior_subreaper,
                        "handler_restored": signal.getsignal(sig) is prior,
                        "lock_restored": not LIFECYCLE._INVOCATION_LOCK.locked(),
                    },
                    sort_keys=True,
                )
            )
            return 0
        finally:
            if disposition == "custom_cleanup_fault":
                LIFECYCLE.os.pidfd_open = original_pidfd_open
                LIFECYCLE._send_group = original_send_for_fault
        elapsed = time.monotonic() - started
        pidfds_closed = True
        for descriptor in captured_pidfds:
            try:
                os.fstat(descriptor)
            except OSError:
                continue
            pidfds_closed = False
        payload = {
            "result": result,
            "handler_calls": calls["count"],
            "handler_restored": signal.getsignal(sig) is prior,
            "elapsed": elapsed,
            "signal_to_redelivery_elapsed": time.monotonic() - signal_sent_at["value"],
            "handler_subreaper": calls.get("subreaper"),
            "handler_lock_released": calls.get("lock_released"),
            "prior_subreaper": prior_subreaper,
            "pidfds_closed": pidfds_closed,
            "owned_children_after": sorted(LIFECYCLE._children_of(os.getpid())),
        }
        print(json.dumps(payload, sort_keys=True))
        return 0
    raise ValueError(f"unknown fixture mode: {mode}")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--fixture":
        raise SystemExit(_fixture_main(sys.argv[2]))
    unittest.main(verbosity=2)
