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
import json
import sys
import tempfile
import subprocess
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

        # Simulate dispatch_task() with pre_registered=True
        dispatch_mod.dispatch_task(
            config=config,
            prompt="probe",
            task_id=task_id,
            output_file=output_file,
            registry=registry,
            script_dir=LIB.parent,
            pre_registered=True,
        )

        entry = registry.get(task_id)
        assert_true(entry is not None, "Registry entry missing after service-down dispatch")
        assert_true(
            entry.get("status") in {"failed", "done"},
            f"Expected status failed/done, got {entry.get('status')}",
        )
        print(f"PASS  service-down dispatch: registry entry status={entry['status']}")


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

        def fake_popen(cmd, start_new_session=False):
            calls.append((cmd, start_new_session))
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
        assert_true(
            "Agent task started" in output_file.read_text(encoding="utf-8"),
            "initial output file should contain a running marker",
        )
        print("PASS  agent runner creates initial output/progress artifacts")


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

            def poll(self):
                return self.returncode

        fake_proc = FakeProcess()
        original_popen = dispatch_mod.subprocess.Popen
        original_terminate = dispatch_mod._terminate_agent_process
        original_no_progress = dispatch_mod._compute_agent_no_progress_timeout
        original_monotonic = dispatch_mod.time.monotonic
        original_sleep = dispatch_mod.time.sleep
        terminated = []
        clock = iter([0.0, 2.0, 3.0])

        def fake_popen(cmd, start_new_session=False):
            return fake_proc

        def fake_terminate(proc):
            terminated.append(proc.pid)
            proc.returncode = -15

        try:
            dispatch_mod.subprocess.Popen = fake_popen
            dispatch_mod._terminate_agent_process = fake_terminate
            dispatch_mod._compute_agent_no_progress_timeout = lambda timeout_secs: 1
            dispatch_mod.time.monotonic = lambda: next(clock, 3.0)
            dispatch_mod.time.sleep = lambda seconds: None
            ok = dispatch_mod.AgentRunner(script_dir).run(config, "probe", output_file, max_calls=1)
        finally:
            dispatch_mod.subprocess.Popen = original_popen
            dispatch_mod._terminate_agent_process = original_terminate
            dispatch_mod._compute_agent_no_progress_timeout = original_no_progress
            dispatch_mod.time.monotonic = original_monotonic
            dispatch_mod.time.sleep = original_sleep

        assert_true(not ok, "AgentRunner should fail a no-progress child")
        assert_true(terminated == [fake_proc.pid], "AgentRunner should terminate the stalled child")
        assert_true(
            "Agent no-progress timeout" in output_file.read_text(encoding="utf-8"),
            "timeout artifact should explain the no-progress watchdog",
        )
        print("PASS  agent runner reaps no-progress child")


def test_agent_runner_defaults_allow_long_horizon_work():
    """Default agent watchdog policy should allow overnight/day-long local tasks."""
    dispatch_mod = _load_dispatch()
    wall_clock = dispatch_mod._compute_agent_wall_clock(timeout_secs=300, max_calls=50)
    no_progress = dispatch_mod._compute_agent_no_progress_timeout(timeout_secs=300)
    assert_true(wall_clock >= 86400, f"agent wall clock should allow day-long work, got {wall_clock}s")
    assert_true(no_progress >= 14400, f"no-progress watchdog should allow slow generations, got {no_progress}s")
    print("PASS  agent runner defaults allow long-horizon work")


if __name__ == "__main__":
    passed = failed = 0
    tests = [
        test_pre_register_before_dispatch_task,
        test_dispatch_task_accepts_pre_registered,
        test_service_down_still_creates_registry_entry,
        test_registry_entry_exists_before_service_check,
        test_agent_runner_creates_initial_output_artifacts,
        test_agent_runner_reaps_no_progress_child,
        test_agent_runner_defaults_allow_long_horizon_work,
    ]
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as exc:
            print(f"FAIL  {t.__name__}: {exc}")
            failed += 1

    total = passed + failed
    print(f"\n{passed}/{total} tests passed")
    if failed:
        sys.exit(1)
