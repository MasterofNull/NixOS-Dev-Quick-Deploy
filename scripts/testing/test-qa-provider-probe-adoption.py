#!/usr/bin/env python3
"""Offline acceptance tests for QPPR-A1 adoption."""
from __future__ import annotations

import importlib.util
import io
import json
import multiprocessing
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
from contextlib import redirect_stdout
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts/testing/qa-provider-probe.py"
SPEC = importlib.util.spec_from_file_location("qa_provider_probe_test", RUNNER)
assert SPEC and SPEC.loader
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def _hold_lock(directory: str, ready: multiprocessing.Queue) -> None:
    lock = probe.AggregateLock(Path(directory))
    ready.put((lock.acquire(), os.fstat(lock.fd).st_ino))
    while True:
        import time
        time.sleep(1)


class AdoptionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        (root / "config").mkdir()
        (root / ".agent/qa").mkdir(parents=True)
        (root / "bin").mkdir()
        (root / "config/qa-provider-probe-policy.json").write_bytes(
            (ROOT / "config/qa-provider-probe-policy.json").read_bytes()
        )
        self.root, self.bin = root, root / "bin"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def executable(self, name: str, body: str = "exit 0") -> None:
        path = self.bin / name
        path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
        path.chmod(0o700)

    def run_probe(self, canonical: bool = False) -> list[dict]:
        return probe.run_provider_probe(
            repo_root=self.root,
            qa_invocation_id=str(uuid.uuid4()),
            executable_path=str(self.bin),
            canonical=canonical,
        )

    def test_clean_exact_four_policy_order(self) -> None:
        for name in probe.ORDER:
            self.executable(name)
        got = self.run_probe()
        self.assertEqual([item["provider_id"] for item in got], list(probe.ORDER))
        self.assertTrue(all(item["result"] == "pass" for item in got))
        schema = json.loads((ROOT / "config/qa-provider-probe-contract.schema.json").read_text())
        validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
        for item in got:
            validator.validate(item)

    def test_nonzero_and_missing_are_typed(self) -> None:
        for name in probe.ORDER:
            self.executable(name)
        self.executable("qwen", "exit 7")
        (self.bin / "pi").unlink()
        got = self.run_probe()
        self.assertEqual(got[1]["failure_class"], "exit_nonzero")
        self.assertEqual(got[3]["failure_class"], "executable_missing")

    def test_closed_check_result_serialization(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "result_for_adoption", ROOT / "scripts/testing/harness_qa/core/result.py"
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        for name in probe.ORDER:
            self.executable(name)
        details = self.run_probe()
        result = module.passed(7, "0.6.1", "probe")
        result.details = details
        self.assertEqual(result.to_dict()["details"], details)
        self.assertEqual(len(details), 4)

    def test_json_reporter_and_immutable_store_preserve_details(self) -> None:
        for name in probe.ORDER:
            self.executable(name)
        details = self.run_probe()
        sys.path.insert(0, str(ROOT / "scripts/testing"))
        sys.path.insert(0, str(ROOT / "scripts/ai/lib"))
        from harness_qa.core.result import ResultSet, passed
        from harness_qa.reporters.json_out import JsonReporter
        from qa_evidence_store import QAEvidenceStore

        result = passed(7, "0.6.1", "probe")
        result.details = details
        result_set = ResultSet(phase="0", results=[result])
        output = io.StringIO()
        with redirect_stdout(output):
            JsonReporter().render(result_set)
        rendered = json.loads(output.getvalue())
        self.assertEqual(rendered["tests"][0]["details"], details)

        store = QAEvidenceStore.for_isolated_test(self.root / "evidence", mountinfo_text="")
        invocation = store.reserve_invocation(str(uuid.uuid4()))
        store.publish(invocation, {"phase": "0", "tests": [result.to_dict()]})
        persisted = store.read_latest().payload
        self.assertEqual(persisted["results"]["tests"][0]["details"], details)

    def test_busy_is_no_spawn_and_preserves_inode(self) -> None:
        lock = probe.AggregateLock(self.root / ".agent/qa")
        self.assertTrue(lock.acquire())
        inode = os.fstat(lock.fd).st_ino
        try:
            got = self.run_probe(canonical=True)
            self.assertEqual([item["failure_class"] for item in got], ["probe_busy"] * 4)
            self.assertFalse((self.root / ".agent/qa/provider-probe-active.json").exists())
        finally:
            lock.close()
        self.assertEqual((self.root / ".agent/qa/provider-probe.lock").stat().st_ino, inode)

    def test_cross_process_owner_crash_releases_same_inode(self) -> None:
        queue: multiprocessing.Queue = multiprocessing.Queue()
        owner = multiprocessing.Process(target=_hold_lock, args=(str(self.root / ".agent/qa"), queue))
        owner.start()
        acquired, inode = queue.get(timeout=2)
        self.assertTrue(acquired)
        try:
            got = self.run_probe(canonical=True)
            self.assertEqual([item["failure_class"] for item in got], ["probe_busy"] * 4)
        finally:
            owner.terminate()
            owner.join(timeout=2)
        replacement = probe.AggregateLock(self.root / ".agent/qa")
        try:
            self.assertTrue(replacement.acquire())
            self.assertEqual(os.fstat(replacement.fd).st_ino, inode)
        finally:
            replacement.close()

    def test_symlink_lock_fails_closed(self) -> None:
        (self.root / ".agent/qa/provider-probe.lock").symlink_to(self.root / "outside")
        with self.assertRaises(OSError):
            self.run_probe()

    def test_canonical_heartbeat_is_closed_and_terminal(self) -> None:
        for name in probe.ORDER:
            self.executable(name)
        got = self.run_probe(canonical=True)
        heartbeat = json.loads((self.root / ".agent/qa/provider-probe-active.json").read_text())
        self.assertEqual(heartbeat["lifecycle_state"], "terminal")
        self.assertEqual(heartbeat["provider_id"], "pi")
        self.assertEqual(heartbeat["last_terminal_failure_class"], got[-1]["failure_class"])
        self.assertEqual(
            set(heartbeat),
            {
                "schema_version", "qa_invocation_id", "provider_id", "lifecycle_state",
                "elapsed_ms", "heartbeat_utc", "deadline_ms", "last_terminal_failure_class",
            },
        )

    def test_standalone_writes_no_heartbeat(self) -> None:
        for name in probe.ORDER:
            self.executable(name)
        self.run_probe(canonical=False)
        self.assertFalse((self.root / ".agent/qa/provider-probe-active.json").exists())

    def test_heartbeat_symlink_fails_closed(self) -> None:
        for name in probe.ORDER:
            self.executable(name)
        (self.root / ".agent/qa/provider-probe-active.json").symlink_to(self.root / "outside")
        self.run_probe(canonical=True)
        self.assertTrue((self.root / ".agent/qa/provider-probe-active.json").is_symlink())

    def test_shell_has_one_owner_no_timeout(self) -> None:
        text = (ROOT / "scripts/testing/smoke-flagship-cli-surfaces.sh").read_text()
        self.assertIn("exec python3", text)
        self.assertNotIn("timeout --foreground", text)
        self.assertNotIn("eval ", text)

    def test_phase0_direct_adoption_and_dashboard_skip(self) -> None:
        phase = (ROOT / "scripts/testing/harness_qa/phases/phase0.py").read_text()
        self.assertIn("module.run_provider_probe(", phase)
        self.assertIn('"0.6.1"', phase)
        self.assertIn('_dashboard_host_only_skip(7, "0.6.1"', phase)
        self.assertNotIn('cmd_ok("bash", str(script), env=env)', phase)
        main = (ROOT / "scripts/testing/harness_qa/main.py").read_text()
        self.assertIn("tests.append(r.to_dict())", main)
        self.assertLess(main.index("reserve_invocation(str(uuid.uuid4()))"), main.index("ctx = RunContext("))

    # -- AM2/AM3 correction coverage -----------------------------------------------------

    def test_canonical_missing_invocation_is_zero_action(self) -> None:
        """4.3 / AM2 §5 item 4: canonical missing/invalid invocation performs zero
        lock/provider/spawn/write actions."""
        for name in probe.ORDER:
            self.executable(name)
        with self.assertRaises(RuntimeError):
            probe.run_provider_probe(
                repo_root=self.root, qa_invocation_id=None,
                executable_path=str(self.bin), canonical=True,
            )
        with self.assertRaises(RuntimeError):
            probe.run_provider_probe(
                repo_root=self.root, qa_invocation_id="not-a-uuid",
                executable_path=str(self.bin), canonical=True,
            )
        self.assertFalse((self.root / ".agent/qa/provider-probe.lock").exists())
        self.assertFalse((self.root / ".agent/qa/provider-probe-active.json").exists())

    def test_preexisting_unsafe_lock_rejected_without_mutation(self) -> None:
        """4.4 / AM2 §5 item 5: a pre-existing effective-user-owned 0666 lock is rejected
        and retains its exact original mode, inode, and bytes."""
        lock_path = self.root / ".agent/qa/provider-probe.lock"
        lock_path.write_bytes(b"pre-existing-bytes")
        lock_path.chmod(0o666)
        before_stat = lock_path.stat()
        for name in probe.ORDER:
            self.executable(name)
        with self.assertRaises(RuntimeError):
            self.run_probe()
        after_stat = lock_path.stat()
        self.assertEqual(after_stat.st_mode, before_stat.st_mode)
        self.assertEqual(after_stat.st_ino, before_stat.st_ino)
        self.assertEqual(lock_path.read_bytes(), b"pre-existing-bytes")

    def test_newly_created_lock_is_mode_0600(self) -> None:
        for name in probe.ORDER:
            self.executable(name)
        got = self.run_probe()
        self.assertTrue(all(item["result"] == "pass" for item in got))
        mode = (self.root / ".agent/qa/provider-probe.lock").stat().st_mode & 0o777
        self.assertEqual(mode, 0o600)

    def test_closed_details_serializer_rejects_malformed_variants(self) -> None:
        """4.5 / AM2 §5 item 6: the serializer accepts exactly four valid records and
        rejects extra, missing, reordered, duplicate, malformed, sensitive,
        cross-invocation, cross-provider, and cross-profile details."""
        spec = importlib.util.spec_from_file_location(
            "result_for_malformed_details", ROOT / "scripts/testing/harness_qa/core/result.py"
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        for name in probe.ORDER:
            self.executable(name)
        details = self.run_probe()
        self.assertEqual(len(details), 4)

        def expect_reject(mutated: object) -> None:
            result = module.passed(7, "0.6.1", "probe")
            result.details = mutated
            with self.assertRaises(ValueError):
                result.to_dict()

        # None remains valid.
        result = module.passed(7, "0.6.1", "probe")
        result.details = None
        self.assertNotIn("details", result.to_dict())

        # extra record
        expect_reject(details + [details[0]])
        # missing record
        expect_reject(details[:3])
        # reordered (not codex,qwen,claude,pi)
        expect_reject([details[1], details[0], details[2], details[3]])
        # duplicate record in place of a distinct one
        expect_reject([details[0], details[0], details[2], details[3]])
        # malformed field (unknown failure_class)
        malformed = json.loads(json.dumps(details))
        malformed[0]["failure_class"] = "not_a_real_class"
        expect_reject(malformed)
        # sensitive/unknown field injected
        sensitive = json.loads(json.dumps(details))
        sensitive[0]["argv"] = ["codex", "--help"]
        expect_reject(sensitive)
        # cross-invocation (one record from a different invocation id)
        cross_invocation = json.loads(json.dumps(details))
        cross_invocation[0]["invocation_id"] = str(uuid.uuid4())
        expect_reject(cross_invocation)
        # cross-provider (provider swapped without swapping profile)
        cross_provider = json.loads(json.dumps(details))
        cross_provider[0]["provider_id"] = "qwen"
        expect_reject(cross_provider)
        # cross-profile (profile swapped without swapping provider)
        cross_profile = json.loads(json.dumps(details))
        cross_profile[0]["profile_id"] = "qwen_help"
        expect_reject(cross_profile)
        # arbitrary dictionary
        expect_reject([{"not": "a record"}] * 4)

    def test_publication_barrier_exclusively_used(self) -> None:
        """4.1: run_owned_process must always be invoked with publication_fd set, never
        the legacy daemon-callback (no publication_fd) path."""
        source = (ROOT / "scripts/testing/qa-provider-probe.py").read_text()
        import re as _re

        calls = _re.findall(r"run_owned_process\(.*?\n            \)", source, _re.DOTALL)
        self.assertTrue(calls, "expected at least one run_owned_process call site")
        for call in calls:
            self.assertIn("publication_fd=pub_write_fd", call)
        self.assertNotIn("threading.Thread(target=publication", source)


class RoadmapVerifierFixtureTests(unittest.TestCase):
    """Roadmap-verifier-recovery §4: deterministic fixture proof that the corrected
    verifier passes the canonical form and fails when the exec is removed, the Phase-0
    direct call is removed, or the legacy provider loop is reintroduced. No real provider,
    network, or Phase-0 live execution occurs; this only replays the verifier's own static
    regex checks (extracted from the verifier script itself) against fixture text."""

    VERIFIER = ROOT / "scripts/testing/verify-flake-first-roadmap-completion.sh"
    SMOKE = ROOT / "scripts/testing/smoke-flagship-cli-surfaces.sh"
    PHASE0 = ROOT / "scripts/testing/harness_qa/phases/phase0.py"

    @staticmethod
    def _extract_flagship_checks(verifier_text: str) -> list[tuple[str, str, str, bool]]:
        """Returns (path, pattern, label, must_be_absent) for every flagship-CLI-smoke or
        Phase-0-flagship-adoption check in the verifier."""
        import re

        checks: list[tuple[str, str, str, bool]] = []
        for match in re.finditer(
            r'check_(pattern|absent_pattern)\s+"([^"]+)"\s+\'([^\']*)\'\s+\'([^\']*)\'',
            verifier_text,
        ):
            kind, path, pattern, label = match.groups()
            if "smoke-flagship-cli-surfaces.sh" in path or (
                "phase0.py" in path
                and ("flagship" in label.lower() or "run_provider_probe" in pattern)
            ):
                checks.append((path, pattern, label, kind == "absent_pattern"))
        return checks

    def _evaluate(
        self, checks: list[tuple[str, str, str, bool]], smoke: str, phase0: str
    ) -> bool:
        import re as _re

        for path, pattern, _label, must_be_absent in checks:
            if path.endswith("smoke-flagship-cli-surfaces.sh"):
                text = smoke
            elif path.endswith("phase0.py"):
                text = phase0
            else:
                raise AssertionError(f"unexpected checked path: {path}")
            matched = bool(_re.search(pattern, text))
            check_passed = (not matched) if must_be_absent else matched
            if not check_passed:
                return False
        return True

    def test_verifier_flagship_checks_pass_canonical_and_fail_on_regression(self) -> None:
        verifier_text = self.VERIFIER.read_text()
        checks = self._extract_flagship_checks(verifier_text)
        self.assertTrue(checks, "expected at least one flagship-CLI verifier check")
        smoke_text = self.SMOKE.read_text()
        phase0_text = self.PHASE0.read_text()

        # Canonical form: every extracted check passes.
        self.assertTrue(self._evaluate(checks, smoke_text, phase0_text))

        # Exec removed -> must fail.
        no_exec = smoke_text.replace('exec python3 "${runner}" --machine', "true")
        self.assertFalse(self._evaluate(checks, no_exec, phase0_text))

        # Phase-0 direct call removed -> must fail.
        no_phase0_call = phase0_text.replace("module.run_provider_probe(", "module.unused_call(")
        self.assertFalse(self._evaluate(checks, smoke_text, no_phase0_call))

        # Legacy loop reintroduced -> must fail (negative assertion catches it).
        legacy_reintroduced = smoke_text + "\ncommands=(cn codex qwen gemini claude pi)\n"
        self.assertFalse(self._evaluate(checks, legacy_reintroduced, phase0_text))


def _closed_record(
    invocation_id: str, provider_id: str, profile_id: str, result: str, failure_class: str
) -> dict:
    base = probe._no_spawn(
        invocation_id, {"provider_id": provider_id, "profile_id": profile_id}, failure_class, 0.0
    )
    base["result"] = result
    return base


class SignalPathAdversarialTests(unittest.TestCase):
    """R-A3 / AM2 §5 items 1-3: default/custom/ignored disposition signal-path proofs, plus
    conflicting-duplicate, identical-duplicate, and write-spy proofs. Deterministic via
    explicit event ordering or subprocess-observed state, never a sleep-only assertion as
    the proof itself -- a short sleep is used only to let the slow fixture subprocess
    actually be mid-execution before the real signal fires, matching the established C1C
    subprocess-fixture pattern in test-qa-provider-probe-lifecycle.py."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        (root / "config").mkdir()
        (root / ".agent/qa").mkdir(parents=True)
        (root / "bin").mkdir()
        (root / "config/qa-provider-probe-policy.json").write_bytes(
            (ROOT / "config/qa-provider-probe-policy.json").read_bytes()
        )
        self.root, self.bin = root, root / "bin"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write_scripts(self, slow_provider: str, slow_seconds: float = 6.0) -> None:
        """The slow provider touches a marker file immediately on start, before sleeping.
        The signal sender polls for that marker (see ``_signal_fixture_main``) instead of
        guessing a fixed absolute delay -- this is a genuine event barrier against actual
        process state, not a timing assumption, so it stays deterministic regardless of
        interpreter/module-load startup overhead in any given environment.

        ``run_provider_probe`` deliberately scopes the child's PATH to the fixture bin
        directory only (mirroring production's provider-resolution sandboxing), so the slow
        script cannot rely on external ``touch``/``sleep`` binaries being resolvable -- and
        must not fall back to the real system PATH either, since this repo's real system PATH
        genuinely has ``codex``/``claude``/``qwen``/``pi`` CLIs installed, and broadening PATH
        risks resolving to a real agent binary instead of this fixture. The marker-touch and
        sleep are therefore done in pure Python, invoked via ``sys.executable``'s absolute
        path (no PATH lookup at all), with zero external-binary dependency.
        """
        marker = self.root / "slow-provider-started.marker"
        helper = self.root / "_slow_provider_helper.py"
        helper.write_text(
            "import pathlib, sys, time\n"
            "pathlib.Path(sys.argv[1]).touch()\n"
            "time.sleep(float(sys.argv[2]))\n",
            encoding="utf-8",
        )
        for name in probe.ORDER:
            if name == slow_provider:
                # Plain absolute paths and a number as argv -- no shell-quoting surface at
                # all, unlike embedding a -c script inline.
                body = f"exec {sys.executable} {helper} {marker} {slow_seconds}"
            else:
                body = "exit 0"
            path = self.bin / name
            path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
            path.chmod(0o700)

    def _run_child(self, mode: str, timeout: float = 20.0) -> "subprocess.CompletedProcess[str]":
        return subprocess.run(
            [
                sys.executable, str(Path(__file__).resolve()),
                "--signal-fixture", mode, str(self.root), str(self.bin),
            ],
            capture_output=True, text=True, timeout=timeout,
        )

    def test_default_disposition_kill_writes_exactly_one_terminal_heartbeat(self) -> None:
        """Item 1/2: default-disposition kill still yields exactly one valid terminal
        write. The regressed candidate produced zero writes here (the process died inside
        the deferred-commit window) while the barrier channel had already recorded a false
        'completed'. A signal-interrupted provider legitimately reports a non-'none'
        failure class (its work was cut short, not completed) -- what this test proves is
        that the write happened at all, with a valid classification, despite the kill."""
        self._write_scripts("qwen")
        completed = self._run_child("default")
        self.assertNotEqual(completed.returncode, 0, completed.stderr)
        heartbeat_path = self.root / ".agent/qa/provider-probe-active.json"
        self.assertTrue(heartbeat_path.exists(), completed.stderr)
        heartbeat = json.loads(heartbeat_path.read_text())
        self.assertEqual(heartbeat["provider_id"], "qwen")
        self.assertEqual(heartbeat["lifecycle_state"], "terminal")
        self.assertIn(heartbeat["last_terminal_failure_class"], probe._LIFECYCLE.FAILURE_CLASSES)

    def test_custom_disposition_terminal_write_precedes_redelivered_handler(self) -> None:
        """Item 2: the terminal write completes before handler return / redelivery. Proof:
        the redelivered custom handler only ever runs after C1C's restore-and-redeliver,
        which (per R-A1) only runs after the join already committed; the handler reads back
        its own already-committed state instead of the test inferring order from timing."""
        self._write_scripts("qwen")
        completed = self._run_child("custom")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout.strip())
        self.assertEqual(tuple(payload["handler_observed"]), ("qwen", "terminal"))

    def test_ignored_disposition_terminal_write_precedes_ordinary_continuation(self) -> None:
        """Item 2, ignored-disposition variant. SIG_IGN offers no Python-level handler hook,
        so this uses the last-in-policy-order provider ('pi'): the shared heartbeat file's
        final state, read only after the whole aggregate call returns, is then
        unambiguously this provider's own write and cannot have been overwritten by a
        later provider."""
        self._write_scripts("pi")
        completed = self._run_child("ignored")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout.strip())
        final = payload["final_heartbeat"]
        self.assertIsNotNone(final, completed.stderr)
        self.assertEqual(final["provider_id"], "pi")
        self.assertEqual(final["lifecycle_state"], "terminal")

    def test_conflicting_duplicate_submission_cancels_without_overwrite(self) -> None:
        """Item 1/3: a conflicting duplicate does not overwrite the already-committed
        terminal write."""
        dir_fd = os.open(str(self.root / ".agent/qa"), os.O_RDONLY | os.O_DIRECTORY)
        try:
            invocation_id = str(uuid.uuid4())
            read_fd, write_fd = os.pipe2(os.O_NONBLOCK | os.O_CLOEXEC)
            consumer = probe.ObserverConsumer(
                read_fd, dir_fd, invocation_id, "codex", "codex_help", time.monotonic(), True,
            )
            consumer.start()
            os.write(write_fd, b"qa.provider-probe-state.v1|1|starting|0\n")
            os.write(write_fd, b"qa.provider-probe-state.v1|2|running|0\n")
            os.write(write_fd, b"qa.provider-probe-state.v1|3|terminal|0\n")
            os.close(write_fd)
            record = _closed_record(invocation_id, "codex", "codex_help", "pass", "none")
            consumer.submit_result(record)
            self.assertTrue(consumer.committed)
            conflicting = _closed_record(invocation_id, "codex", "codex_help", "fail", "exit_nonzero")
            consumer.submit_result(conflicting)
            heartbeat = json.loads((self.root / ".agent/qa/provider-probe-active.json").read_text())
            self.assertEqual(heartbeat["last_terminal_failure_class"], "none")
        finally:
            os.close(dir_fd)

    def test_identical_duplicate_submission_is_idempotent(self) -> None:
        """Item 1: an identical duplicate submission is idempotent (stays committed, does
        not flip to cancelled)."""
        dir_fd = os.open(str(self.root / ".agent/qa"), os.O_RDONLY | os.O_DIRECTORY)
        try:
            invocation_id = str(uuid.uuid4())
            read_fd, write_fd = os.pipe2(os.O_NONBLOCK | os.O_CLOEXEC)
            consumer = probe.ObserverConsumer(
                read_fd, dir_fd, invocation_id, "codex", "codex_help", time.monotonic(), True,
            )
            consumer.start()
            os.write(write_fd, b"qa.provider-probe-state.v1|1|starting|0\n")
            os.write(write_fd, b"qa.provider-probe-state.v1|2|running|0\n")
            os.write(write_fd, b"qa.provider-probe-state.v1|3|terminal|0\n")
            os.close(write_fd)
            record = _closed_record(invocation_id, "codex", "codex_help", "pass", "none")
            consumer.submit_result(record)
            self.assertTrue(consumer.committed)
            consumer.submit_result(dict(record))
            self.assertTrue(consumer.committed)
            self.assertFalse(consumer.cancelled)
        finally:
            os.close(dir_fd)

    def test_invalid_observer_stream_cancels_with_zero_heartbeat_writes(self) -> None:
        """Item 3: a backward/invalid C1B observer sequence cancels the join and emits no
        terminal projection -- proven by a write-spy on ``_heartbeat`` observing zero calls
        with ``state == "terminal"``. A best-effort *interim* heartbeat for the one valid
        record that preceded the corruption is legitimate, pre-existing observability
        behavior (unrelated to the join/commit decision) and is not itself a violation; only
        a terminal-state write would be."""
        dir_fd = os.open(str(self.root / ".agent/qa"), os.O_RDONLY | os.O_DIRECTORY)
        try:
            invocation_id = str(uuid.uuid4())
            read_fd, write_fd = os.pipe2(os.O_NONBLOCK | os.O_CLOEXEC)
            consumer = probe.ObserverConsumer(
                read_fd, dir_fd, invocation_id, "codex", "codex_help", time.monotonic(), True,
            )
            consumer.start()
            # Backward/duplicate sequence (1 then 1 again): ObserverConsumer._read raises
            # and marks the consumer invalid after processing the first valid record;
            # "terminal" is never reached.
            os.write(write_fd, b"qa.provider-probe-state.v1|1|starting|0\n")
            os.write(write_fd, b"qa.provider-probe-state.v1|1|starting|0\n")
            os.close(write_fd)
            record = _closed_record(invocation_id, "codex", "codex_help", "pass", "none")
            terminal_write_calls: list[tuple[object, ...]] = []
            original_heartbeat = probe._heartbeat

            def _spy(*args: object, **kwargs: object) -> None:
                state = args[3] if len(args) > 3 else kwargs.get("state")
                if state == "terminal":
                    terminal_write_calls.append(args)
                original_heartbeat(*args, **kwargs)  # type: ignore[misc]

            probe._heartbeat = _spy
            try:
                consumer.submit_result(record)
            finally:
                probe._heartbeat = original_heartbeat
            self.assertTrue(consumer.cancelled)
            self.assertFalse(consumer.committed)
            self.assertEqual(terminal_write_calls, [])
            heartbeat_path = self.root / ".agent/qa/provider-probe-active.json"
            if heartbeat_path.exists():
                self.assertNotEqual(json.loads(heartbeat_path.read_text())["lifecycle_state"], "terminal")
        finally:
            os.close(dir_fd)


def _signal_fixture_main(argv: list[str]) -> int:
    """Child-process entry point for the R-A3 default/custom/ignored disposition proofs.

    Invoked as: test-qa-provider-probe-adoption.py --signal-fixture MODE ROOT BIN. Installs
    a background sender that delivers a real SIGTERM to this process once the slow fixture
    provider's own marker file proves it has actually started (an event barrier against real
    process state, not a fixed-delay guess -- robust regardless of interpreter/module-load
    startup overhead), while the main thread runs a real ``run_provider_probe`` against that
    slow (sleeping) fixture executable, so the signal reliably lands mid-run -- mirroring the
    subprocess-isolated, real-signal pattern already established in
    test-qa-provider-probe-lifecycle.py's ``PublicationBarrierSubprocessTests``.
    """
    mode, root, bin_dir = argv[0], argv[1], argv[2]
    heartbeat_path = Path(root) / ".agent/qa/provider-probe-active.json"
    handler_observed: dict[str, object] = {}

    if mode == "custom":
        def _custom_handler(signum: int, frame: object) -> None:
            # Fires only as part of the *redelivered* signal, after C1C's
            # _restore_and_redeliver has run -- which, per R-A1, only runs after the join
            # has already been driven to COMMITTED or CANCELLED (and, on commit, after the
            # terminal heartbeat has already been written). Reading state here is a
            # deterministic ordering proof, not a timing inference.
            if heartbeat_path.exists():
                try:
                    hb = json.loads(heartbeat_path.read_text())
                    handler_observed["seen"] = [hb.get("provider_id"), hb.get("lifecycle_state")]
                except (OSError, ValueError):
                    handler_observed["seen"] = "unreadable"
            else:
                handler_observed["seen"] = "missing"
        signal.signal(signal.SIGTERM, _custom_handler)
    elif mode == "ignored":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    # "default": leave SIG_DFL -- the process dies on redelivery.

    def _sender() -> None:
        marker = Path(root) / "slow-provider-started.marker"
        deadline = time.monotonic() + 15.0
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        # Small fixed buffer so the aggregate's own poll loop has registered the "running"
        # lifecycle state before the signal lands; the gating condition proven above is the
        # marker (real process state), not this buffer.
        time.sleep(0.1)
        os.kill(os.getpid(), signal.SIGTERM)

    threading.Thread(target=_sender, daemon=True).start()

    probe.run_provider_probe(
        repo_root=Path(root),
        qa_invocation_id=str(uuid.uuid4()),
        executable_path=bin_dir,
        canonical=True,
    )
    # Reached only for custom/ignored dispositions; "default" never returns here.
    if mode == "custom":
        print(json.dumps({"handler_observed": handler_observed.get("seen")}), flush=True)
    else:
        final = None
        if heartbeat_path.exists():
            try:
                final = json.loads(heartbeat_path.read_text())
            except (OSError, ValueError):
                final = None
        print(json.dumps({"final_heartbeat": final}), flush=True)
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--signal-fixture":
        raise SystemExit(_signal_fixture_main(sys.argv[2:]))
    unittest.main()
