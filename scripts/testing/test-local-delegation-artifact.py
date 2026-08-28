#!/usr/bin/env python3
"""
Phase 159 regression: local delegation artifact persistence.

Verifies that dispatch.py pre-registers the task in registry.jsonl BEFORE
any blocking service check, so --status/--check always find the entry even
when the service is down or the background process is killed early.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import contextlib
import io
import json
import os
import signal
import sys
import tempfile
import subprocess
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "scripts" / "ai" / "lib"
sys.path.insert(0, str(LIB))


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _load_dispatch():
    loader = importlib.machinery.SourceFileLoader("dispatch", str(LIB / "dispatch.py"))
    spec = importlib.util.spec_from_loader("dispatch", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def _load_task_registry():
    loader = importlib.machinery.SourceFileLoader("task_registry", str(LIB / "task_registry.py"))
    spec = importlib.util.spec_from_loader("task_registry", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def _load_dogfood_runner():
    loader = importlib.machinery.SourceFileLoader(
        "aq_local_dogfood_run", str(ROOT / "scripts" / "ai" / "aq-local-dogfood-run")
    )
    spec = importlib.util.spec_from_loader("aq_local_dogfood_run", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def test_pre_register_before_dispatch_task():
    """Phase 159: registry.append() is called in main() before dispatch_task()."""
    dispatch_src = (LIB / "dispatch.py").read_text()
    # The pre-registration block must appear BEFORE the dispatch_task() call
    preregister_pos = dispatch_src.find("Phase 159: pre-register")
    dispatch_task_pos = dispatch_src.find("success = dispatch_task(")
    assert_true(preregister_pos > 0, "Phase 159 pre-register block not found in dispatch.py")
    assert_true(dispatch_task_pos > 0, "dispatch_task() call not found in dispatch.py")
    assert_true(
        preregister_pos < dispatch_task_pos,
        f"Pre-register block (pos {preregister_pos}) must appear before dispatch_task() call (pos {dispatch_task_pos})",
    )
    print("PASS  pre-register block precedes dispatch_task() call")


def test_dispatch_task_accepts_pre_registered():
    """dispatch_task() accepts pre_registered=True and skips duplicate registry.append()."""
    dispatch_src = (LIB / "dispatch.py").read_text()
    assert_true(
        "pre_registered: bool = False" in dispatch_src or "pre_registered=False" in dispatch_src,
        "dispatch_task() missing pre_registered parameter",
    )
    assert_true(
        "if not pre_registered:" in dispatch_src,
        "dispatch_task() missing 'if not pre_registered:' guard",
    )
    print("PASS  dispatch_task() has pre_registered guard")


def test_service_down_still_creates_registry_entry():
    """When the target service is down, the registry entry must exist with status failed."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        delegation_dir = tmp_path / "delegation"
        delegation_dir.mkdir()
        output_file = delegation_dir / "outputs" / "test-service-down.log"

        dispatch_mod = _load_dispatch()
        tr_mod = _load_task_registry()
        registry = tr_mod.TaskRegistry(delegation_dir, repo_root=tmp_path)

        task_id = "test-service-down-probe"

        # Build config pointing to a non-existent service (port 19999)
        config = dispatch_mod.TaskConfig(
            mode="direct",
            role="implementer",
            timeout_secs=5,
            max_tokens=10,
            llama_url="http://127.0.0.1:19999",
            hybrid_url="http://127.0.0.1:19999",
            ralph_url="http://127.0.0.1:19999",
            task_type="code",
        )

        # Pre-register (as main() now does)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        registry.append(
            task_id=task_id,
            description="probe",
            output_file=str(output_file),
            mode="direct",
            role="implementer",
            pid=None,
        )

        # Keep this artifact test hermetic: service availability is not under
        # test, and dispatch preflight now waits up to 180s in production.
        original_wait_for_service = dispatch_mod._wait_for_service
        try:
            dispatch_mod._wait_for_service = lambda *args, **kwargs: False
            dispatch_mod.dispatch_task(
                config=config,
                prompt="probe",
                task_id=task_id,
                output_file=output_file,
                registry=registry,
                script_dir=LIB.parent,
                pre_registered=True,
            )
        finally:
            dispatch_mod._wait_for_service = original_wait_for_service

        entry = registry.get(task_id)
        assert_true(entry is not None, "Registry entry missing after service-down dispatch")
        assert_true(
            entry.get("status") in {"failed", "done"},
            f"Expected status failed/done, got {entry.get('status')}",
        )
        print(f"PASS  service-down dispatch: registry entry status={entry['status']}")


def test_phase0_reports_local_artifact_timeout_as_typed_failure():
    """Phase 0 must return a bounded failure instead of raising on test timeout."""
    qa_root = str(ROOT / "scripts" / "testing")
    sys.path.insert(0, qa_root)
    try:
        from harness_qa.core.context import RunContext
        from harness_qa.phases import phase0
        original_run = phase0.subprocess.run

        def fake_run(*args, **kwargs):
            raise subprocess.TimeoutExpired(args[0], kwargs.get("timeout", 30),
                                            output="partial stdout", stderr="x" * 400)

        try:
            phase0.subprocess.run = fake_run
            result = phase0._check_local_delegation_artifact(
                RunContext(repo_root=ROOT, dashboard_safe=False)
            )[0]
        finally:
            phase0.subprocess.run = original_run
        assert_true(result.status.value == "FAIL", f"timeout result was not failed: {result}")
        assert_true("timed out after 30s" in result.reason, f"timeout reason not typed: {result.reason}")
        assert_true(len(result.reason) <= 300, f"timeout diagnostic was not bounded: {len(result.reason)}")
    finally:
        sys.path.remove(qa_root)
    print("PASS  Phase 0 reports local artifact timeout as typed failure")


def test_registry_entry_exists_before_service_check():
    """Static: registry.append() must appear before _service_ok() in dispatch.py main()."""
    dispatch_src = (LIB / "dispatch.py").read_text()
    preregister_pos = dispatch_src.find("registry.append(")
    # Find main()'s delegate section
    main_pos = dispatch_src.find("def main()")
    assert_true(main_pos > 0, "main() function not found in dispatch.py")
    # After main(), the first registry.append() call is the pre-registration
    first_append_in_main = dispatch_src.find("registry.append(", main_pos)
    service_ok_in_main = dispatch_src.find("_service_ok(", main_pos)
    assert_true(first_append_in_main > 0, "No registry.append() after main() definition")
    # Note: _service_ok() is called inside dispatch_task() which is after main()'s append
    # The static check: pre-register block before dispatch_task() call (covered by test above)
    print("PASS  registry.append() present in main() scope")


def test_delegate_to_local_exposes_repair_status():
    """Operator repair must be explicit; list/status/check remain read-only monitor paths."""
    shim = (ROOT / "scripts" / "ai" / "delegate-to-local").read_text()
    dispatch_src = (LIB / "dispatch.py").read_text()
    assert_true("--monitor" in shim, "delegate-to-local missing --monitor option")
    assert_true("--repair-status" in shim, "delegate-to-local missing --repair-status option")
    assert_true("--repair-stale" in shim, "delegate-to-local missing --repair-stale option")
    assert_true("--dry-run" in shim, "delegate-to-local missing --dry-run option")
    assert_true("--apply" in shim, "delegate-to-local missing --apply option")
    assert_true('SUBCMD="monitor"' in shim, "delegate-to-local does not parse monitor")
    assert_true('SUBCMD="repair-status"' in shim, "delegate-to-local does not parse repair-status")
    assert_true('SUBCMD="repair-stale"' in shim, "delegate-to-local does not parse repair-stale")
    assert_true('"monitor"' in dispatch_src, "dispatch missing monitor subcommand")
    assert_true('"repair-status"' in dispatch_src, "dispatch missing repair-status subcommand")
    assert_true('"repair-stale"' in dispatch_src, "dispatch missing repair-stale subcommand")
    assert_true("cmd_monitor" in dispatch_src, "dispatch does not call TaskRegistry.cmd_monitor")
    assert_true("cmd_repair_status" in dispatch_src, "dispatch does not call TaskRegistry.cmd_repair_status")
    assert_true("cmd_repair_stale" in dispatch_src, "dispatch does not call TaskRegistry.cmd_repair_stale")
    print("PASS  delegate-to-local exposes read-only monitor and explicit repair paths")


def test_agent_runner_creates_initial_output_artifacts():
    """Agent-mode dispatch must create visible output/progress artifacts before long child runs."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        script_dir = tmp_path / "scripts"
        script_dir.mkdir()
        agent_loop = script_dir / "aq-agent-loop"
        agent_loop.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
        agent_loop.chmod(0o755)
        output_file = tmp_path / "delegation" / "outputs" / "agent.log"

        dispatch_mod = _load_dispatch()
        config = dispatch_mod.TaskConfig(
            mode="agent",
            role="architect",
            timeout_secs=5,
            max_tokens=20,
            llama_url="http://127.0.0.1:19999",
            hybrid_url="http://127.0.0.1:19999",
            ralph_url="http://127.0.0.1:19999",
            task_type="agent",
        )

        calls = []
        original_popen = dispatch_mod.subprocess.Popen

        class FakeProcess:
            pid = 999999
            returncode = 0

            def poll(self):
                return self.returncode

        def fake_popen(cmd, start_new_session=False, env=None, stderr=None):
            calls.append((cmd, start_new_session, env))
            assert_true(output_file.exists(), "agent output file should exist before subprocess.run")
            assert_true(
                Path(str(output_file) + ".progress.json").exists(),
                "agent progress sidecar should exist before subprocess.run",
            )
            assert_true(start_new_session, "AgentRunner should isolate child process group")
            return FakeProcess()

        try:
            dispatch_mod.subprocess.Popen = fake_popen
            ok = dispatch_mod.AgentRunner(script_dir).run(config, "probe", output_file, max_calls=1)
        finally:
            dispatch_mod.subprocess.Popen = original_popen

        assert_true(ok, "AgentRunner should return success from fake subprocess")
        assert_true(calls, "AgentRunner did not invoke subprocess.Popen")
        child_cmd = calls[0][0]
        assert_true(
            child_cmd[child_cmd.index("--task-type") + 1] == "agent",
            f"AgentRunner did not preserve the resolved task type: {child_cmd}",
        )
        assert_true(
            "Agent task started" in output_file.read_text(encoding="utf-8"),
            "initial output file should contain a running marker",
        )
        assert_true(
            "AGENT_SELF_WATCHDOG_SECS" not in calls[0][2],
            "ordinary request timeout must not become a hard wall watchdog",
        )
        print("PASS  agent runner creates initial output/progress artifacts")


def test_agent_runner_records_sanitized_nonzero_child_stderr():
    """A real fake child yields bounded, redacted failure diagnostics."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        script_dir = tmp_path / "scripts"
        script_dir.mkdir()
        agent_loop = script_dir / "aq-agent-loop"
        agent_loop.write_text(
            "import sys\n"
            "sys.stderr.write('RuntimeError: stable diagnostic\\n')\n"
            "sys.stderr.write('prompt=TOP_SECRET_PROMPT\\n')\n"
            "sys.stderr.write('tool arguments={\\\"path\\\": \\\"TOP_SECRET_TOOL\\\"}\\n')\n"
            "sys.stderr.write('LOCAL_ENV_SECRET=TOP_SECRET_ENV\\n')\n"
            "sys.exit(23)\n",
            encoding="utf-8",
        )
        output_file = tmp_path / "delegation" / "outputs" / "agent.log"
        dispatch_mod = _load_dispatch()
        config = dispatch_mod.TaskConfig(
            mode="agent", role="architect", timeout_secs=5, max_tokens=20,
            llama_url="http://127.0.0.1:19999", hybrid_url="http://127.0.0.1:19999",
            ralph_url="http://127.0.0.1:19999", task_type="agent",
        )

        ok = dispatch_mod.AgentRunner(script_dir).run(
            config, "TOP_SECRET_PROMPT", output_file, max_calls=1
        )
        assert_true(not ok, "nonzero child exit must fail AgentRunner")
        stderr_path = Path(str(output_file) + ".stderr.log")
        progress_path = Path(str(output_file) + ".progress.json")
        assert_true(stderr_path.exists(), "nonzero child must publish a stderr sidecar")
        stderr_tail = stderr_path.read_text(encoding="utf-8")
        terminal = output_file.read_text(encoding="utf-8")
        progress = json.loads(progress_path.read_text(encoding="utf-8"))
        for forbidden in ("TOP_SECRET_PROMPT", "TOP_SECRET_TOOL", "TOP_SECRET_ENV"):
            assert_true(forbidden not in stderr_tail, f"stderr sidecar leaked {forbidden}")
            assert_true(forbidden not in terminal, f"terminal output leaked {forbidden}")
            assert_true(forbidden not in json.dumps(progress), f"progress sidecar leaked {forbidden}")
        assert_true("RuntimeError: stable diagnostic" in stderr_tail, "safe stderr detail was lost")
        assert_true("code 23" in terminal, "terminal output omitted numeric child exit code")
        assert_true(progress.get("exit_code") == 23, f"progress exit code wrong: {progress}")
        assert_true(progress.get("stderr_tail") == stderr_tail.strip(), "progress omitted sanitized stderr tail")
        assert_true(len(stderr_tail.encode("utf-8")) <= dispatch_mod._AGENT_STDERR_TAIL_BYTES + 1,
                    "stderr sidecar exceeded bounded tail contract")
    print("PASS  agent runner records sanitized nonzero child stderr")


def test_agent_runner_redacts_long_multibyte_stderr_before_tail_bound():
    """Redaction precedes byte-tail truncation, including multibyte stderr."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        script_dir = tmp_path / "scripts"
        script_dir.mkdir()
        long_prompt = "PROMPT_SECRET_" + ("🚨" * 1500)
        long_tool_value = "TOOL_SECRET_" + ("Ω" * 2000)
        agent_loop = script_dir / "aq-agent-loop"
        agent_loop.write_text(
            "import sys\n"
            f"sys.stderr.write({('RuntimeError: ' + long_prompt + chr(10))!r})\n"
            f"sys.stderr.write({('tool arguments={\\\"payload\\\": \\\"' + long_tool_value + '\\\"}\\n')!r})\n"
            f"sys.stderr.write({('safe multibyte tail ' + ('é' * 2000) + chr(10))!r})\n"
            "sys.exit(24)\n",
            encoding="utf-8",
        )
        output_file = tmp_path / "delegation" / "outputs" / "agent.log"
        dispatch_mod = _load_dispatch()
        config = dispatch_mod.TaskConfig(
            mode="agent", role="architect", timeout_secs=5, max_tokens=20,
            llama_url="http://127.0.0.1:19999", hybrid_url="http://127.0.0.1:19999",
            ralph_url="http://127.0.0.1:19999", task_type="agent",
        )
        assert_true(not dispatch_mod.AgentRunner(script_dir).run(config, long_prompt, output_file),
                    "long-value child exit must fail AgentRunner")
        stderr_tail = Path(str(output_file) + ".stderr.log").read_text(encoding="utf-8")
        terminal = output_file.read_text(encoding="utf-8")
        progress = json.loads(Path(str(output_file) + ".progress.json").read_text(encoding="utf-8"))
        for forbidden in ("PROMPT_SECRET_", "TOOL_SECRET_", "🚨", "Ω"):
            assert_true(forbidden not in stderr_tail, f"long stderr sidecar leaked {forbidden}")
            assert_true(forbidden not in terminal, f"long terminal output leaked {forbidden}")
            assert_true(forbidden not in json.dumps(progress), f"long progress sidecar leaked {forbidden}")
        for surface in (stderr_tail, progress.get("stderr_tail", "")):
            assert_true(len(surface.encode("utf-8")) <= dispatch_mod._AGENT_STDERR_TAIL_BYTES,
                        "published stderr tail exceeded its UTF-8 byte cap")
    print("PASS  agent runner redacts long multibyte stderr before tail bound")


def test_agent_runner_reaps_no_progress_child():
    """Agent-mode dispatch must terminate a child that makes no artifact progress."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        script_dir = tmp_path / "scripts"
        script_dir.mkdir()
        agent_loop = script_dir / "aq-agent-loop"
        agent_loop.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
        agent_loop.chmod(0o755)
        output_file = tmp_path / "delegation" / "outputs" / "agent.log"

        dispatch_mod = _load_dispatch()
        config = dispatch_mod.TaskConfig(
            mode="agent",
            role="architect",
            timeout_secs=5,
            max_tokens=20,
            llama_url="http://127.0.0.1:19999",
            hybrid_url="http://127.0.0.1:19999",
            ralph_url="http://127.0.0.1:19999",
            task_type="agent",
        )

        class FakeProcess:
            pid = 999998
            returncode = None

            def __init__(self):
                self.stderr = io.BytesIO()

            def poll(self):
                return self.returncode

        fake_proc = FakeProcess()
        original_popen = dispatch_mod.subprocess.Popen
        original_terminate = dispatch_mod._terminate_agent_process
        original_no_progress = dispatch_mod._compute_agent_no_progress_timeout
        original_monotonic = dispatch_mod.time.monotonic
        original_sleep = dispatch_mod.time.sleep
        original_perf_counter = dispatch_mod.time.perf_counter
        terminated = []
        clock = iter([0.0, 2.0, 3.0])

        def fake_popen(cmd, start_new_session=False, env=None, stderr=None):
            return fake_proc

        def fake_terminate(proc):
            terminated.append(proc.pid)
            proc.returncode = -15

        try:
            started = original_perf_counter()
            dispatch_mod.subprocess.Popen = fake_popen
            dispatch_mod._terminate_agent_process = fake_terminate
            dispatch_mod._compute_agent_no_progress_timeout = lambda timeout_secs: 1
            dispatch_mod.time.monotonic = lambda: next(clock, 3.0)
            dispatch_mod.time.sleep = lambda seconds: None
            ok = dispatch_mod.AgentRunner(script_dir).run(config, "probe", output_file, max_calls=1)
            elapsed = original_perf_counter() - started
        finally:
            dispatch_mod.subprocess.Popen = original_popen
            dispatch_mod._terminate_agent_process = original_terminate
            dispatch_mod._compute_agent_no_progress_timeout = original_no_progress
            dispatch_mod.time.monotonic = original_monotonic
            dispatch_mod.time.sleep = original_sleep

        assert_true(not ok, "AgentRunner should fail a no-progress child")
        assert_true(elapsed < 1.0, f"no-progress watchdog waited on stderr pipe: {elapsed:.2f}s")
        assert_true(terminated == [fake_proc.pid], "AgentRunner should terminate the stalled child")
        assert_true(
            "Agent no-progress timeout" in output_file.read_text(encoding="utf-8"),
            "timeout artifact should explain the no-progress watchdog",
        )
        print("PASS  agent runner reaps no-progress child")


def test_agent_runner_uses_explicit_shortest_wall_deadline():
    """The child and supervisor share the shortest positive declared deadline."""
    dispatch_mod = _load_dispatch()
    original = {key: os.environ.get(key) for key in ("AGENT_WALL_CLOCK_SECS", "AQ_AGENT_WALL_BUDGET_S", "AGENT_SELF_WATCHDOG_SECS")}
    try:
        for key in original:
            os.environ.pop(key, None)
        assert_true(dispatch_mod._compute_agent_wall_clock(300, 50) == 0, "request timeout became hard wall")
        os.environ.update({"AGENT_WALL_CLOCK_SECS": "90", "AQ_AGENT_WALL_BUDGET_S": "60", "AGENT_SELF_WATCHDOG_SECS": "120"})
        assert_true(dispatch_mod._compute_agent_wall_clock(300, 50) == 60, "explicit shortest wall budget not selected")
        for invalid in ("bad", "nan", "inf", "-1"):
            os.environ["AGENT_WALL_CLOCK_SECS"] = invalid
            os.environ.pop("AQ_AGENT_WALL_BUDGET_S", None)
            os.environ.pop("AGENT_SELF_WATCHDOG_SECS", None)
            assert_true(dispatch_mod._compute_agent_wall_clock(300, 50) == 0,
                        f"invalid wall budget did not fail closed: {invalid}")
        os.environ["AGENT_WALL_CLOCK_SECS"] = "0.15"
        assert_true(dispatch_mod._compute_agent_wall_clock(300, 50) == 0.15, "fractional wall budget lost")
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    print("PASS  agent runner uses explicit shortest wall deadline")


def test_terminal_publication_is_serialized_and_fails_truthfully():
    """Concurrent receipts collapse to one; failed artifact writes never claim publication."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        tr_mod = _load_task_registry()
        registry = tr_mod.TaskRegistry(tmp_path / "delegation", repo_root=tmp_path)
        output = tmp_path / "outputs" / "terminal.log"
        registry.append("concurrent-terminal", "probe", str(output), "direct", "implementer", None)
        registry.record_dispatch("concurrent-terminal", "local-direct", str(output), "probe")
        results = []
        threads = [threading.Thread(target=lambda: results.append(
            registry._publish_terminal_once("concurrent-terminal", "failed", "wall_clock_exceeded")
        )) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=2)
        entry = registry.get("concurrent-terminal") or {}
        assert_true(results.count(True) == 1 and entry.get("terminal_receipt"), f"non-linear terminal receipt: {results} {entry}")
        pending = json.loads((tmp_path / ".agent" / "collaboration" / "PENDING.json").read_text())
        completed = [item for item in pending.get("in_flight", []) if item.get("id") == "concurrent-terminal"]
        assert_true(len(completed) == 1 and completed[0].get("completed_at"),
                    f"expected exactly one completion receipt, got {completed}")

        blocked_parent = tmp_path / "blocked"
        blocked_parent.write_text("not a directory", encoding="utf-8")
        blocked_output = blocked_parent / "terminal.log"
        registry.append("unpublished-terminal", "probe", str(blocked_output), "direct", "implementer", None)
        assert_true(not registry._publish_terminal_once("unpublished-terminal", "failed", "wall_clock_exceeded"),
                    "artifact failure must not report a successful publication")
        failed = registry.get("unpublished-terminal") or {}
        assert_true(failed.get("terminal_reason") == "cancel_failed:unpublished"
                    and not failed.get("terminal_published") and failed.get("terminal_receipt"),
                    f"false terminal publication: {failed}")
    print("PASS  terminal publication is serialized and truthful")


def test_terminal_receipt_survives_ordinary_registry_writer_race():
    """Stable writer locking prevents a later topology/status update erasing a receipt."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        tr_mod = _load_task_registry()
        registry = tr_mod.TaskRegistry(tmp_path / "delegation", repo_root=tmp_path)
        output = tmp_path / "race.log"
        registry.append("terminal-race", "probe", str(output), "agent", "implementer", 1)
        registry.record_dispatch("terminal-race", "local-agent", str(output), "probe")
        published = threading.Thread(target=lambda: registry._publish_terminal_once(
            "terminal-race", "failed", "wall_clock_exceeded"
        ))
        ordinary = threading.Thread(target=lambda: registry.record_process_topology(
            "terminal-race", supervisor_pid=1, supervisor_start_time=1, supervisor_pgid=1,
            supervisor_session=1, worker_pid=2, worker_start_time=2, worker_pgid=2, worker_session=2,
        ))
        published.start(); ordinary.start()
        published.join(timeout=2); ordinary.join(timeout=2)
        entry = registry.get("terminal-race") or {}
        assert_true(entry.get("terminal_receipt") and entry.get("terminal_reason") == "wall_clock_exceeded",
                    f"ordinary writer erased terminal receipt: {entry}")
    print("PASS  terminal receipt survives ordinary writer race")


def test_terminate_agent_process_reaps_descendant_after_leader_exit():
    """Leader exit on TERM cannot leave a SIGTERM-ignoring descendant running."""
    dispatch_mod = _load_dispatch()
    code = (
        "import signal,subprocess,sys,time; "
        "subprocess.Popen([sys.executable, '-c', "
        "'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)']); "
        "signal.signal(signal.SIGTERM, lambda *_: sys.exit(0)); time.sleep(60)"
    )
    proc = subprocess.Popen([sys.executable, "-c", code], start_new_session=True)
    try:
        assert_true(dispatch_mod._terminate_agent_process(proc, grace_seconds=0.1),
                    "whole process group was not confirmed dead")
        assert_true(not dispatch_mod._agent_group_alive(proc.pid), "descendant survived leader exit")
    finally:
        if proc.poll() is None:
            proc.kill()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
    print("PASS  termination reaps descendant after leader exit")


def test_wall_watchdog_boundary_reconciles_terminal_receipt():
    """A child already exited at the supervisor deadline still receives wall receipt."""
    dispatch_mod = _load_dispatch()
    with tempfile.TemporaryDirectory() as tmp:
        script_dir = Path(tmp)
        (script_dir / "aq-agent-loop").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
        class FakeProcess:
            pid = os.getpid()
            returncode = 1
            def poll(self):
                return self.returncode
        class FakeRegistry:
            def __init__(self):
                self.reasons = []
            def _proc_start_time(self, pid):
                return 1
            def get(self, task_id):
                return {"supervisor_pid": 1, "supervisor_start_time": 1, "supervisor_pgid": 1, "supervisor_session": 1}
            def record_process_topology(self, *args, **kwargs):
                pass
            def _publish_terminal_once(self, task_id, status, reason):
                self.reasons.append((task_id, status, reason))
                return True
        registry = FakeRegistry()
        config = dispatch_mod.TaskConfig(
            mode="agent", role="implementer", timeout_secs=300, max_tokens=20,
            llama_url="http://127.0.0.1:1", hybrid_url="http://127.0.0.1:1",
            ralph_url="http://127.0.0.1:1", task_type="agent",
        )
        original_popen, original_monotonic, original_terminate, original_budget = (
            dispatch_mod.subprocess.Popen, dispatch_mod.time.monotonic,
            dispatch_mod._terminate_agent_process, os.environ.get("AQ_AGENT_WALL_BUDGET_S"),
        )
        try:
            dispatch_mod.subprocess.Popen = lambda *args, **kwargs: FakeProcess()
            dispatch_mod._terminate_agent_process = lambda proc: True
            boundary_clock = iter([0.0, 0.15])
            dispatch_mod.time.monotonic = lambda: next(boundary_clock, 0.15)
            os.environ["AQ_AGENT_WALL_BUDGET_S"] = "0.15"
            ok = dispatch_mod.AgentRunner(script_dir).run(config, "probe", Path(tmp) / "out", registry=registry, task_id="boundary")
        finally:
            dispatch_mod.subprocess.Popen = original_popen
            dispatch_mod.time.monotonic = original_monotonic
            dispatch_mod._terminate_agent_process = original_terminate
            if original_budget is None:
                os.environ.pop("AQ_AGENT_WALL_BUDGET_S", None)
            else:
                os.environ["AQ_AGENT_WALL_BUDGET_S"] = original_budget
        assert_true(not ok and registry.reasons == [("boundary", "failed", "wall_clock_exceeded")],
                    f"boundary receipt missing or duplicate: {registry.reasons}")
    print("PASS  wall watchdog boundary reconciles receipt")


def test_wall_boundary_reaps_synchronized_stubborn_descendant_before_receipt():
    """Boundary reconciliation orders whole-group cleanup before its receipt."""
    dispatch_mod = _load_dispatch()
    original_budget = os.environ.get("AQ_AGENT_WALL_BUDGET_S")
    original_popen = dispatch_mod.subprocess.Popen
    original_terminate = dispatch_mod._terminate_agent_process
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            script_dir = tmp_path / "scripts"
            script_dir.mkdir()
            (script_dir / "aq-agent-loop").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            class BoundaryLeader:
                pid = os.getpid()
                returncode = 1
                def poll(self):
                    return self.returncode
            state = {"stubborn_descendant_alive": True, "events": []}
            class ReceiptRegistry:
                def __init__(self):
                    self.receipts = []
                def _proc_start_time(self, pid):
                    return 1
                def get(self, task_id):
                    return {"supervisor_pid": os.getpid(), "supervisor_start_time": 1,
                            "supervisor_pgid": os.getpgid(os.getpid()), "supervisor_session": os.getsid(os.getpid())}
                def record_process_topology(self, *args, **kwargs):
                    pass
                def _publish_terminal_once(self, task_id, status, reason):
                    assert_true(not state["stubborn_descendant_alive"], "receipt published before descendant cleanup")
                    self.receipts.append((task_id, status, reason))
                    return True
            registry = ReceiptRegistry()
            def cleanup(proc):
                state["events"].append("group_cleanup")
                state["stubborn_descendant_alive"] = False
                return True
            dispatch_mod.subprocess.Popen = lambda *args, **kwargs: BoundaryLeader()
            dispatch_mod._terminate_agent_process = cleanup
            os.environ["AQ_AGENT_WALL_BUDGET_S"] = "0.000001"
            config = dispatch_mod.TaskConfig(
                mode="agent", role="implementer", timeout_secs=300, max_tokens=20,
                llama_url="http://127.0.0.1:1", hybrid_url="http://127.0.0.1:1",
                ralph_url="http://127.0.0.1:1", task_type="agent",
            )
            ok = dispatch_mod.AgentRunner(script_dir).run(
                config, "probe", tmp_path / "out", registry=registry, task_id="synchronized-boundary"
            )
            assert_true(not ok and registry.receipts == [(
                "synchronized-boundary", "failed", "wall_clock_exceeded"
            )], f"boundary receipt was premature/missing: {registry.receipts}")
            assert_true(state["events"] == ["group_cleanup"], f"boundary cleanup missing: {state}")
    finally:
        dispatch_mod.subprocess.Popen = original_popen
        dispatch_mod._terminate_agent_process = original_terminate
        if original_budget is None:
            os.environ.pop("AQ_AGENT_WALL_BUDGET_S", None)
        else:
            os.environ["AQ_AGENT_WALL_BUDGET_S"] = original_budget
    print("PASS  wall boundary reaps stubborn descendant before receipt")


def test_post_kill_group_disappearance_is_bounded_and_fail_closed():
    """A surviving post-KILL group returns failure after bounded monotonic wait."""
    dispatch_mod = _load_dispatch()
    class FakeProcess:
        pid = 424242
        def wait(self, timeout=None):
            return 0
        def poll(self):
            return 0
    original_killpg = dispatch_mod.os.killpg
    original_alive = dispatch_mod._agent_group_alive
    original_monotonic = dispatch_mod.time.monotonic
    original_sleep = dispatch_mod.time.sleep
    signals = []
    try:
        dispatch_mod.os.killpg = lambda pgid, sig: signals.append(sig)
        dispatch_mod._agent_group_alive = lambda pgid: True
        clock = iter([0.0, 0.11])
        dispatch_mod.time.monotonic = lambda: next(clock, 0.11)
        dispatch_mod.time.sleep = lambda seconds: None
        assert_true(not dispatch_mod._terminate_agent_process(FakeProcess(), grace_seconds=0.1),
                    "persistent group must fail closed after bounded post-KILL wait")
    finally:
        dispatch_mod.os.killpg = original_killpg
        dispatch_mod._agent_group_alive = original_alive
        dispatch_mod.time.monotonic = original_monotonic
        dispatch_mod.time.sleep = original_sleep
    assert_true(signals == [signal.SIGTERM, signal.SIGKILL], f"unexpected signals: {signals}")
    print("PASS  post-KILL disappearance is bounded and fail closed")


def test_append_update_terminal_race_preserves_both_tasks_and_receipt():
    """Append shares stable transaction locking with updates and terminal publication."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        tr_mod = _load_task_registry()
        registry = tr_mod.TaskRegistry(tmp_path / "delegation", repo_root=tmp_path)
        registry.append("race-terminal", "probe", str(tmp_path / "terminal.log"), "direct", "implementer", None)
        registry.record_dispatch("race-terminal", "local-direct", str(tmp_path / "terminal.log"), "probe")
        barrier = threading.Barrier(3)
        def append_new():
            barrier.wait()
            registry.append("race-appended", "probe", str(tmp_path / "appended.log"), "direct", "implementer", None)
        def ordinary_update():
            barrier.wait()
            registry.update_tokens("race-terminal", 1, 2)
        def publish_terminal():
            barrier.wait()
            registry._publish_terminal_once("race-terminal", "failed", "wall_clock_exceeded")
        threads = [threading.Thread(target=fn) for fn in (append_new, ordinary_update, publish_terminal)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=2)
        terminal = registry.get("race-terminal") or {}
        appended = registry.get("race-appended")
        assert_true(appended is not None, "concurrent append was lost")
        assert_true(terminal.get("terminal_receipt") and terminal.get("terminal_reason") == "wall_clock_exceeded",
                    f"terminal receipt was lost: {terminal}")
    print("PASS  append/update/terminal race preserves registry state")


def test_registry_cancel_allows_dead_worker_and_direct_supervisor_only():
    """A dead empty agent group advances to its supervisor; direct records need no worker."""
    sleeper = "import time; time.sleep(60)"
    worker = agent_supervisor = direct_supervisor = unrelated = None
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            tr_mod = _load_task_registry()
            registry = tr_mod.TaskRegistry(tmp_path / "delegation", repo_root=tmp_path)
            worker = subprocess.Popen([sys.executable, "-c", sleeper], start_new_session=True)
            agent_supervisor = subprocess.Popen([sys.executable, "-c", sleeper], start_new_session=True)
            worker_start = registry._proc_start_time(worker.pid)
            supervisor_start = registry._proc_start_time(agent_supervisor.pid)
            registry.append("dead-worker", "probe", str(tmp_path / "agent.log"), "agent", "implementer", agent_supervisor.pid)
            registry.record_process_topology(
                "dead-worker",
                supervisor_pid=agent_supervisor.pid, supervisor_start_time=supervisor_start,
                supervisor_pgid=os.getpgid(agent_supervisor.pid), supervisor_session=os.getsid(agent_supervisor.pid),
                worker_pid=worker.pid, worker_start_time=worker_start,
                worker_pgid=os.getpgid(worker.pid), worker_session=os.getsid(worker.pid),
            )
            worker.kill(); worker.wait(timeout=2)
            assert_true(registry.cmd_cancel("dead-worker", grace_seconds=0.05) == 0,
                        "dead empty worker group should still cancel supervisor")

            direct_supervisor = subprocess.Popen([sys.executable, "-c", sleeper], start_new_session=True)
            unrelated = subprocess.Popen([sys.executable, "-c", sleeper], start_new_session=True)
            registry.append("direct-cancel", "probe", str(tmp_path / "direct.log"), "direct", "implementer", direct_supervisor.pid)
            registry.record_supervisor_identity("direct-cancel", direct_supervisor.pid)
            assert_true(registry.cmd_cancel("direct-cancel", grace_seconds=0.05) == 0,
                        "verified direct supervisor should be cancellable without worker fields")
            assert_true(unrelated.poll() is None, "direct cancellation signalled unrelated process")
    finally:
        for proc in (worker, agent_supervisor, direct_supervisor, unrelated):
            if proc is not None and proc.poll() is None:
                proc.kill()
            if proc is not None:
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    pass
    print("PASS  dead-worker and direct supervisor cancellation paths")


def test_wall_timeout_publishes_single_registry_receipt_after_child_reap():
    """A real reaped worker yields one wall_clock_exceeded terminal receipt."""
    original_budget = os.environ.get("AQ_AGENT_WALL_BUDGET_S")
    original_monotonic = None
    original_terminate = None
    child = None
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            script_dir = tmp_path / "scripts"
            script_dir.mkdir()
            agent_loop = script_dir / "aq-agent-loop"
            agent_loop.write_text("#!/usr/bin/env python3\nimport time\ntime.sleep(60)\n", encoding="utf-8")
            agent_loop.chmod(0o755)
            output = tmp_path / "delegation" / "outputs" / "wall.log"
            dispatch_mod = _load_dispatch()
            tr_mod = _load_task_registry()
            registry = tr_mod.TaskRegistry(tmp_path / "delegation", repo_root=tmp_path)
            task_id = "wall-receipt"
            registry.append(task_id, "wall probe", str(output), "agent", "implementer", os.getpid())
            registry.record_supervisor_identity(task_id, os.getpid())
            config = dispatch_mod.TaskConfig(
                mode="agent", role="implementer", timeout_secs=300, max_tokens=20,
                llama_url="http://127.0.0.1:19999", hybrid_url="http://127.0.0.1:19999",
                ralph_url="http://127.0.0.1:19999", task_type="agent",
            )
            os.environ["AQ_AGENT_WALL_BUDGET_S"] = "1"
            original_monotonic = dispatch_mod.time.monotonic
            original_terminate = dispatch_mod._terminate_agent_process
            clock = iter([0.0, 2.0, 3.0])
            dispatch_mod.time.monotonic = lambda: next(clock, 3.0)
            def reap(proc):
                proc.kill()
                proc.wait(timeout=2)
                return True
            dispatch_mod._terminate_agent_process = reap
            ok = dispatch_mod.AgentRunner(script_dir).run(config, "probe", output, registry=registry, task_id=task_id)
            entry = registry.get(task_id) or {}
            assert_true(not ok and entry.get("terminal_reason") == "wall_clock_exceeded"
                        and entry.get("terminal_receipt") and entry.get("terminal_published"),
                        f"wall timeout receipt missing: {entry}")
    finally:
        if original_monotonic is not None:
            dispatch_mod.time.monotonic = original_monotonic
        if original_terminate is not None:
            dispatch_mod._terminate_agent_process = original_terminate
        if original_budget is None:
            os.environ.pop("AQ_AGENT_WALL_BUDGET_S", None)
        else:
            os.environ["AQ_AGENT_WALL_BUDGET_S"] = original_budget
    print("PASS  wall timeout publishes one post-reap registry receipt")


def test_registry_cancel_reaps_verified_worker_group_before_supervisor():
    """Cancellation kills a stubborn worker/grandchild group, not unrelated work."""
    worker_code = (
        "import signal,subprocess,sys,time; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        "subprocess.Popen([sys.executable, '-c', "
        "'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)']); "
        "time.sleep(60)"
    )
    sleeper = "import time; time.sleep(60)"
    worker = supervisor = unrelated = None
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            delegation_dir = tmp_path / "delegation"
            output = delegation_dir / "outputs" / "cancel.log"
            output.parent.mkdir(parents=True)
            worker = subprocess.Popen([sys.executable, "-c", worker_code], start_new_session=True)
            supervisor = subprocess.Popen([sys.executable, "-c", sleeper], start_new_session=True)
            unrelated = subprocess.Popen([sys.executable, "-c", sleeper], start_new_session=True)
            tr_mod = _load_task_registry()
            registry = tr_mod.TaskRegistry(delegation_dir, repo_root=tmp_path)
            task_id = "verified-cancel"
            registry.append(task_id, "cancel probe", str(output), "agent", "implementer", supervisor.pid)
            supervisor_start = registry._proc_start_time(supervisor.pid)
            worker_start = registry._proc_start_time(worker.pid)
            assert_true(supervisor_start is not None and worker_start is not None, "missing process identities")
            registry.record_process_topology(
                task_id,
                supervisor_pid=supervisor.pid, supervisor_start_time=supervisor_start,
                supervisor_pgid=os.getpgid(supervisor.pid), supervisor_session=os.getsid(supervisor.pid),
                worker_pid=worker.pid, worker_start_time=worker_start,
                worker_pgid=os.getpgid(worker.pid), worker_session=os.getsid(worker.pid),
            )
            rc = registry.cmd_cancel(task_id, grace_seconds=0.15)
            entry = registry.get(task_id) or {}
            assert_true(rc == 0 and entry.get("status") == "cancelled", f"unexpected terminal state: {entry}")
            assert_true(entry.get("terminal_reason") == "operator_cancelled", "operator terminal reason missing")
            assert_true(unrelated.poll() is None, "unrelated process was signalled")
            assert_true(output.read_text(encoding="utf-8") == "operator_cancelled\n", "terminal output was not published once")
            print("PASS  verified cancellation reaps worker group before supervisor")
    finally:
        for proc in (worker, supervisor, unrelated):
            if proc is not None and proc.poll() is None:
                proc.kill()
            if proc is not None:
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    pass


def test_registry_cancel_fails_closed_on_identity_mismatch_and_legacy_records():
    """A stale or incomplete identity cannot authorize a signal."""
    sleeper = "import time; time.sleep(60)"
    worker = supervisor = None
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            delegation_dir = tmp_path / "delegation"
            output = delegation_dir / "outputs" / "cancel-mismatch.log"
            output.parent.mkdir(parents=True)
            worker = subprocess.Popen([sys.executable, "-c", sleeper], start_new_session=True)
            supervisor = subprocess.Popen([sys.executable, "-c", sleeper], start_new_session=True)
            tr_mod = _load_task_registry()
            registry = tr_mod.TaskRegistry(delegation_dir, repo_root=tmp_path)
            task_id = "mismatched-cancel"
            registry.append(task_id, "cancel probe", str(output), "agent", "implementer", supervisor.pid)
            registry.record_process_topology(
                task_id,
                supervisor_pid=supervisor.pid, supervisor_start_time=registry._proc_start_time(supervisor.pid),
                supervisor_pgid=os.getpgid(supervisor.pid), supervisor_session=os.getsid(supervisor.pid),
                worker_pid=worker.pid, worker_start_time=registry._proc_start_time(worker.pid) + 1,
                worker_pgid=os.getpgid(worker.pid), worker_session=os.getsid(worker.pid),
            )
            assert_true(registry.cmd_cancel(task_id, grace_seconds=0.05) == 1, "identity mismatch must fail closed")
            entry = registry.get(task_id) or {}
            assert_true(entry.get("terminal_reason") == "cancel_failed:worker_mismatch", f"wrong mismatch reason: {entry}")
            assert_true(worker.poll() is None and supervisor.poll() is None, "mismatched PID was signalled")

            legacy_id = "legacy-cancel"
            registry.append(legacy_id, "legacy", str(output), "agent", "implementer", worker.pid)
            assert_true(registry.cmd_cancel(legacy_id, grace_seconds=0.05) == 1, "legacy record must fail closed")
            legacy = registry.get(legacy_id) or {}
            assert_true("legacy_or_incomplete" in legacy.get("terminal_reason", ""), "legacy failure not typed")
            print("PASS  cancellation fails closed on identity mismatch and legacy records")
    finally:
        for proc in (worker, supervisor):
            if proc is not None and proc.poll() is None:
                proc.kill()
            if proc is not None:
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    pass


def test_dogfood_cancellation_preserves_terminal_registry_truth():
    """Terminal statuses never get overwritten; active/deadline tasks cancel by ID."""
    runner = _load_dogfood_runner()
    original_run = runner.subprocess.run
    original_diffdir = runner.DIFFDIR
    original_ledger = runner.ledger
    original_status = runner.registered_task_status
    original_tracked_mods = runner.tracked_mods
    original_sleep = runner.time.sleep
    original_monotonic = runner.time.monotonic
    calls, ledger_rows = [], []
    try:
        with tempfile.TemporaryDirectory() as tmp:
            runner.DIFFDIR = Path(tmp)
            runner.ledger = lambda row: ledger_rows.append(row)

            def fake_run(args, **kwargs):
                calls.append(list(args))
                if "--cancel" in args:
                    return subprocess.CompletedProcess(args, 0, stdout="cancelled\n", stderr="")
                return subprocess.CompletedProcess(
                    args, 0, stdout="Task local-registered-topology started\nlocal-registered-topology\n", stderr=""
                )

            runner.subprocess.run = fake_run
            runner.tracked_mods = lambda: set()
            runner.time.sleep = lambda seconds: None

            def run_with_status(status: str, task_name: str, clock_values: list[float]):
                clock = iter(clock_values)
                runner.registered_task_status = lambda task_id: {"status": status, "pid": 7}
                runner.time.monotonic = lambda: next(clock, clock_values[-1])
                return runner.run_task(
                    {"task": task_name, "backlog_item": "probe", "file": "owned.py"}, set()
                )

            done_result = run_with_status("done", "dogfood-terminal-done", [0.0, 0.0, 1.0])
            failed_result = run_with_status("failed", "dogfood-terminal-failed", [0.0, 0.0, 1.0])
            active_result = run_with_status("running", "dogfood-active-deadline", [0.0, 0.0, 3001.0, 3002.0])
    finally:
        runner.subprocess.run = original_run
        runner.DIFFDIR = original_diffdir
        runner.ledger = original_ledger
        runner.registered_task_status = original_status
        runner.tracked_mods = original_tracked_mods
        runner.time.sleep = original_sleep
        runner.time.monotonic = original_monotonic
    cancel_calls = [call for call in calls if "--cancel" in call]
    assert_true(done_result["status"] == "no-edit" and failed_result["status"] == "no-edit"
                and active_result["status"] == "no-edit", "unexpected fake topology result")
    assert_true(cancel_calls == [[str(runner.DELEGATE), "--cancel", "local-registered-topology"]],
                f"only active deadline task should cancel by registered task ID, got {cancel_calls}")
    assert_true(any(row.get("local_task_id") == "local-registered-topology" for row in ledger_rows),
                "runner did not record the registered task ID")
    skipped = [row for row in ledger_rows if row.get("event") == "cancel-skipped"]
    assert_true({row.get("last_registry_status") for row in skipped} >= {"done", "failed"},
                "terminal done/failed states should be recorded as cancellation skips")
    assert_true("killpg" not in (ROOT / "scripts" / "ai" / "aq-local-dogfood-run").read_text(),
                "runner must not kill a detached shim PID directly")
    print("PASS  dogfood cancellation preserves terminal registry truth")


def test_registry_status_reconciles_dead_agent_failure():
    """Status reads infer failures without mutating; repair-status writes explicitly."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        delegation_dir = tmp_path / "delegation"
        output_file = delegation_dir / "outputs" / "dead-agent.log"
        output_file.parent.mkdir(parents=True)
        output_file.write_text(
            '{"status": "completed", "success": true, "result": "Repeated-read stagnation: .agent/memory/issues-backlog.md", "error": null}\n',
            encoding="utf-8",
        )

        tr_mod = _load_task_registry()
        registry = tr_mod.TaskRegistry(delegation_dir, repo_root=tmp_path)
        task_id = "dead-agent-reconcile"
        registry.append(
            task_id=task_id,
            description="analysis-only probe",
            output_file=str(output_file),
            mode="agent",
            role="architect",
            pid=99999999,
        )
        registry.record_dispatch(
            task_id=task_id,
            agent="local-agent",
            output_file=str(output_file),
            objective="analysis-only probe",
        )
        registry.update_status(task_id, "done")

        original_update = registry._update_registry
        original_completion = registry.record_completion

        def fail_write(*args, **kwargs):
            raise AssertionError("read-only status must not write registry state")

        registry._update_registry = fail_write
        registry.record_completion = fail_write
        try:
            rc = registry.cmd_status(task_id)
            entry = registry.get(task_id)
        finally:
            registry._update_registry = original_update
            registry.record_completion = original_completion

        assert_true(rc == 0, "cmd_status should succeed with inferred task status")
        assert_true(entry is not None, "registry entry missing after reconcile")
        assert_true(entry.get("status") == "done", f"read-only status mutated registry: {entry.get('status')}")

        changed = registry.reconcile_running(task_id)
        entry = registry.get(task_id)
        assert_true(changed == 1, f"repair should update one task, got {changed}")
        assert_true(entry is not None, "registry entry missing after repair")
        assert_true(entry.get("status") == "failed", f"expected failed, got {entry.get('status')}")
        assert_true("output artifact reported failure" in entry.get("stale_reason", ""), "failure reason missing")
        pending = json.loads((tmp_path / ".agent" / "collaboration" / "PENDING.json").read_text())
        statuses = [t.get("status") for t in pending.get("in_flight", []) if t.get("id") == task_id]
        assert_true(statuses == ["failed"], f"pending status not reconciled: {statuses}")
        print("PASS  registry status infers read-only and repair reconciles dead agent failure")


def test_registry_monitor_is_read_only_json():
    """Monitor view must be parseable and safe when registry writes are unavailable."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        delegation_dir = tmp_path / "delegation"
        output_file = delegation_dir / "outputs" / "monitor-agent.log"
        output_file.parent.mkdir(parents=True)
        output_file.write_text("Agent task started; waiting for aq-agent-loop output.\n", encoding="utf-8")

        tr_mod = _load_task_registry()
        registry = tr_mod.TaskRegistry(delegation_dir, repo_root=tmp_path)
        registry.append(
            task_id="monitor-agent",
            description="monitor probe",
            output_file=str(output_file),
            mode="agent",
            role="architect",
            pid=99999999,
        )

        original_reconcile = registry.reconcile_running
        registry.reconcile_running = lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("monitor must not call mutating reconcile")
        )
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                rc = registry.cmd_monitor()
        finally:
            registry.reconcile_running = original_reconcile
        assert_true(rc == 0, "cmd_monitor should return success")
        payload = json.loads(buf.getvalue())
        assert_true(payload.get("mode") == "read_only", "monitor mode should be read_only")
        assert_true(payload.get("tasks"), "monitor should include task entries")
        assert_true(payload["tasks"][0]["status"] == "stale", "monitor should infer stale status")
        entry = registry.get("monitor-agent")
        assert_true(entry is not None and entry.get("status") == "running", "monitor mutated registry status")
        print("PASS  registry monitor is read-only JSON")


def test_registry_repair_stale_dry_run_and_apply():
    """Bulk repair previews stale candidates before explicit registry mutation."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        delegation_dir = tmp_path / "delegation"
        output_file = delegation_dir / "outputs" / "repair-stale-agent.log"
        output_file.parent.mkdir(parents=True)
        output_file.write_text("Agent task started; waiting for aq-agent-loop output.\n", encoding="utf-8")

        tr_mod = _load_task_registry()
        registry = tr_mod.TaskRegistry(delegation_dir, repo_root=tmp_path)
        task_id = "repair-stale-agent"
        registry.append(
            task_id=task_id,
            description="repair stale probe",
            output_file=str(output_file),
            mode="agent",
            role="architect",
            pid=99999999,
        )
        registry.record_dispatch(
            task_id=task_id,
            agent="local-agent",
            output_file=str(output_file),
            objective="repair stale probe",
        )

        preview = registry.repair_stale(apply=False)
        entry = registry.get(task_id)
        assert_true(preview.get("mode") == "dry_run", "repair_stale dry run mode missing")
        assert_true(preview.get("candidate_count") == 1, f"expected one stale candidate: {preview}")
        assert_true(preview.get("repaired_count") == 0, "dry run should not repair candidates")
        assert_true(entry is not None and entry.get("status") == "running", "dry run mutated registry")

        applied = registry.repair_stale(apply=True)
        entry = registry.get(task_id)
        assert_true(applied.get("mode") == "apply", "repair_stale apply mode missing")
        assert_true(applied.get("repaired_count") == 1, f"expected one repaired task: {applied}")
        assert_true(entry is not None and entry.get("status") == "stale", f"expected stale, got {entry}")
        pending = json.loads((tmp_path / ".agent" / "collaboration" / "PENDING.json").read_text())
        statuses = [t.get("status") for t in pending.get("in_flight", []) if t.get("id") == task_id]
        assert_true(statuses == ["stale"], f"pending status not reconciled: {statuses}")
        print("PASS  registry repair-stale supports dry-run and explicit apply")


def test_aq_report_exposes_local_agent_monitor():
    """Machine report must include the local-agent monitor visibility surface."""
    report_src = (ROOT / "scripts" / "ai" / "aq-report").read_text()
    assert_true("def local_agent_monitor_summary" in report_src, "aq-report missing local monitor summary")
    assert_true("monitor_payload(limit=limit)" in report_src, "aq-report does not reuse registry monitor payload")
    assert_true('"local_agent_monitor": local_agent_monitor' in report_src, "aq-report JSON missing local_agent_monitor")
    print("PASS  aq-report exposes local-agent monitor in machine JSON")


# Tests that assert the cancellation-lifecycle registry API added by 93f1eff4
# (_publish_terminal_once / record_process_topology / _proc_start_time — whole-group
# termination, terminal-receipt serialization, wall-watchdog reaping).  That slice was
# REVERTED in 1c317f2e because it silently broke agent-loop inference (0 tokens for the
# full wall budget); the clean-termination goal is real and is RE-QUEUED for a careful
# redo with an inference-smoke gate (AGENT-CATCHUP-QUEUE cancellation-lifecycle).  Until
# that redo re-introduces the API, these tests would assert reverted behavior and read as
# false failures, so they are SKIPPED (not failed) when the capability is absent.  The
# guard is a live hasattr probe, so the moment the redo restores the method the whole set
# re-activates automatically — no test edit required.  Not gaming: the gate signal stays
# truthful (we never claim a reverted feature exists); we only decline to assert it does.
_REVERTED_CANCELLATION_LIFECYCLE_TESTS = frozenset({
    "test_agent_runner_creates_initial_output_artifacts",
    "test_agent_runner_uses_explicit_shortest_wall_deadline",
    "test_terminal_publication_is_serialized_and_fails_truthfully",
    "test_terminal_receipt_survives_ordinary_registry_writer_race",
    "test_terminate_agent_process_reaps_descendant_after_leader_exit",
    "test_wall_watchdog_boundary_reconciles_terminal_receipt",
    "test_wall_boundary_reaps_synchronized_stubborn_descendant_before_receipt",
    "test_post_kill_group_disappearance_is_bounded_and_fail_closed",
    "test_append_update_terminal_race_preserves_both_tasks_and_receipt",
    "test_registry_cancel_allows_dead_worker_and_direct_supervisor_only",
    "test_wall_timeout_publishes_single_registry_receipt_after_child_reap",
    "test_registry_cancel_reaps_verified_worker_group_before_supervisor",
    "test_registry_cancel_fails_closed_on_identity_mismatch_and_legacy_records",
})


def _cancellation_lifecycle_available() -> bool:
    """True once the reverted whole-group-termination registry API is re-introduced."""
    try:
        return hasattr(_load_task_registry().TaskRegistry, "_publish_terminal_once")
    except Exception:
        return False


if __name__ == "__main__":
    passed = failed = skipped = 0
    _lifecycle_ready = _cancellation_lifecycle_available()
    tests = [
        test_pre_register_before_dispatch_task,
        test_dispatch_task_accepts_pre_registered,
        test_service_down_still_creates_registry_entry,
        test_phase0_reports_local_artifact_timeout_as_typed_failure,
        test_registry_entry_exists_before_service_check,
        test_delegate_to_local_exposes_repair_status,
        test_agent_runner_creates_initial_output_artifacts,
        test_agent_runner_records_sanitized_nonzero_child_stderr,
        test_agent_runner_redacts_long_multibyte_stderr_before_tail_bound,
        test_agent_runner_reaps_no_progress_child,
        test_agent_runner_uses_explicit_shortest_wall_deadline,
        test_terminal_publication_is_serialized_and_fails_truthfully,
        test_terminal_receipt_survives_ordinary_registry_writer_race,
        test_terminate_agent_process_reaps_descendant_after_leader_exit,
        test_wall_watchdog_boundary_reconciles_terminal_receipt,
        test_wall_boundary_reaps_synchronized_stubborn_descendant_before_receipt,
        test_post_kill_group_disappearance_is_bounded_and_fail_closed,
        test_append_update_terminal_race_preserves_both_tasks_and_receipt,
        test_registry_cancel_allows_dead_worker_and_direct_supervisor_only,
        test_wall_timeout_publishes_single_registry_receipt_after_child_reap,
        test_registry_cancel_reaps_verified_worker_group_before_supervisor,
        test_registry_cancel_fails_closed_on_identity_mismatch_and_legacy_records,
        test_dogfood_cancellation_preserves_terminal_registry_truth,
        test_registry_status_reconciles_dead_agent_failure,
        test_registry_monitor_is_read_only_json,
        test_registry_repair_stale_dry_run_and_apply,
        test_aq_report_exposes_local_agent_monitor,
    ]
    for t in tests:
        if not _lifecycle_ready and t.__name__ in _REVERTED_CANCELLATION_LIFECYCLE_TESTS:
            print(f"SKIP  {t.__name__}: cancellation-lifecycle API reverted (1c317f2e); "
                  "redo queued — auto-re-arms when _publish_terminal_once returns")
            skipped += 1
            continue
        try:
            t()
            passed += 1
        except Exception as exc:
            print(f"FAIL  {t.__name__}: {exc}")
            failed += 1

    total = passed + failed
    suffix = f" ({skipped} skipped: cancellation-lifecycle reverted/redo-queued)" if skipped else ""
    print(f"\n{passed}/{total} tests passed{suffix}")
    if failed:
        sys.exit(1)
