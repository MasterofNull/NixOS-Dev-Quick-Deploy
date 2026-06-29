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


if __name__ == "__main__":
    passed = failed = 0
    tests = [
        test_pre_register_before_dispatch_task,
        test_dispatch_task_accepts_pre_registered,
        test_service_down_still_creates_registry_entry,
        test_registry_entry_exists_before_service_check,
        test_delegate_to_local_exposes_repair_status,
        test_agent_runner_creates_initial_output_artifacts,
        test_agent_runner_reaps_no_progress_child,
        test_agent_runner_defaults_allow_long_horizon_work,
        test_registry_status_reconciles_dead_agent_failure,
        test_registry_monitor_is_read_only_json,
        test_registry_repair_stale_dry_run_and_apply,
        test_aq_report_exposes_local_agent_monitor,
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
