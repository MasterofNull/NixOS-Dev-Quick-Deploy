#!/usr/bin/env python3
"""Regression checks for ai-stack-health-monitor."""

from __future__ import annotations

import contextlib
import io
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MONITOR = ROOT / "scripts" / "health" / "ai-stack-health-monitor.py"


def isolate_queue(aq, root: Path) -> None:
    """Point the queue module (shared with the monitor) at a temp dir; never touch live queue state."""
    aq._ATTENTION_DIR = root
    aq._QUEUE_FILE = root / "ATTENTION.json"
    aq._ARCHIVE_FILE = root / "ATTENTION_ARCHIVE.jsonl"
    aq._STATE_FILE = root / "notify-state.json"
    aq._MIRROR_PATH = root / "mirror.json"


def load_monitor() -> Any:
    spec = importlib.util.spec_from_file_location("ai_stack_health_monitor_under_test", MONITOR)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    import attention_queue as aq
    isolate_queue(aq, Path(tempfile.mkdtemp(prefix="health-monitor-queue-")))
    module.run_payload_audit = lambda: {"state": "ok", "findings": []}  # payload audit is covered by test-payload-audit-routine.py
    return module


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    monitor = load_monitor()

    failures = monitor.failed_checks({
        "tests": [
            {"id": "ok", "status": "PASS", "description": "healthy"},
            {"id": "bad", "status": "FAIL", "description": "broken"},
        ]
    })
    assert_true(len(failures) == 1 and failures[0]["id"] == "bad", "monitor should read current aq-qa tests schema")

    from attention_queue import AlertSpec

    accepted = []
    def validating_push(**spec):
        AlertSpec(**spec).validate()
        accepted.append(spec)

    original_push = monitor.push
    original_run_qa = monitor.run_aq_qa
    original_phases = monitor._PHASES
    original_write_status = monitor.write_status
    try:
        monitor.push = validating_push
        full_title = "x" * 243
        monitor.push_alert(source="test", severity="high", autonomy_boundary="human_gate",
                           title=full_title, detail="detail", proposed_action="inspect")
        assert_true(accepted[0]["title"] == "x" * 79 + "…", "243-character title should truncate")
        assert_true(full_title in accepted[0]["detail"], "full title should remain in detail")
        try:
            AlertSpec(source="test", severity="high", autonomy_boundary="human_gate",
                      title=full_title, detail="detail", proposed_action="inspect").validate()
        except ValueError:
            pass
        else:
            raise AssertionError("queue validation must remain strict")

        calls = []
        def reject_first(**spec):
            calls.append(spec)
            if len(calls) == 1:
                spec["severity"] = "invalid"
            return validating_push(**spec)

        monitor.push = reject_first
        monitor._PHASES = ["bad", "good"]
        monitor.run_aq_qa = lambda phase: {"error": full_title} if phase == "bad" else {
            "tests": [{"id": "bad", "status": "FAIL", "description": full_title}]}
        statuses = []
        monitor.write_status = statuses.append
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            assert_true(monitor.main() == 0, "invalid alert must not abort monitor")
        assert_true(len(calls) == 2 and len(accepted) == 2, "batch should queue the next valid alert")
        assert_true(all(len(item["title"]) <= 80 for item in calls), "both producers should bound titles")
        assert_true(full_title in accepted[-1]["detail"], "QA row detail should remain intact")
        assert_true("Skipping invalid alert" in stderr.getvalue(), "invalid alert should be logged")
        assert_true(statuses[0]["total_failures"] == 2, "status should record both failures")
    finally:
        monitor.push = original_push
        monitor.run_aq_qa = original_run_qa
        monitor._PHASES = original_phases
        monitor.write_status = original_write_status

    # Freshness-class failures (0.10.5) are maintenance: separate medium alert, never counted toward the
    # outage severity; a real failure with "expired" in its message must still be an outage.
    pushed = []
    monitor.push = lambda **spec: (AlertSpec(**spec).validate(), pushed.append(spec))
    monitor.write_status = lambda status: None
    monitor._PHASES = ["0"]
    def qa(tests):
        monitor.run_aq_qa = lambda phase: {"tests": tests}
        pushed.clear()
        with contextlib.redirect_stderr(io.StringIO()):
            monitor.main()
        return {item["dedup_key"]: item for item in pushed}
    try:
        stale = {"id": "0.10.5", "status": "FAIL", "description": "model catalog/profile freshness", "message": "model profile review is stale"}
        real = lambda n, msg="boom": {"id": f"0.9.{n}", "status": "FAIL", "description": f"real {n}", "message": msg}
        got = qa([stale, real(1), real(2)])
        assert_true(got["qa-phase-0"]["severity"] == "high", "freshness must not push 2 real failures to critical")
        assert_true(got["qa-phase-0-freshness"]["severity"] == "medium", "freshness alert must be medium maintenance")
        assert_true("0.10.5" not in got["qa-phase-0"]["detail"], "freshness failure must leave the outage alert")
        got = qa([stale])
        assert_true(list(got) == ["qa-phase-0-freshness"], "freshness-only run must raise only the maintenance alert")
        got = qa([real(1, "bump-expired"), real(2), real(3)])
        assert_true(got["qa-phase-0"]["severity"] == "critical" and "qa-phase-0-freshness" not in got,
                    "a real failure mentioning 'expired' must stay an outage")
    finally:
        monitor.push = original_push
        monitor.run_aq_qa = original_run_qa
        monitor._PHASES = original_phases
        monitor.write_status = original_write_status

    captured = {}

    def fake_run(cmd, *, env=None, capture_output=False, text=False, timeout=None):
        captured["cmd"] = cmd
        captured["env"] = dict(env or {})
        return subprocess.CompletedProcess(cmd, 0, stdout='{"tests":[]}', stderr="")

    original_run = monitor.subprocess.run
    try:
        monitor.subprocess.run = fake_run
        payload = monitor.run_aq_qa("0")
    finally:
        monitor.subprocess.run = original_run

    assert_true(payload["tests"] == [], "run_aq_qa should parse JSON output")
    assert_true(payload["_monitor_returncode"] == 0, "run_aq_qa should preserve subprocess return code")
    assert_true(captured["cmd"] == [sys.executable, str(monitor._HARNESS_RUNNER), "0", "--json"], "run_aq_qa should bypass shell launcher")
    for name in ("TMPDIR", "TEMP", "TMP"):
        assert_true(captured["env"].get(name) == str(monitor._TMPDIR), f"{name} should use repo-local writable tmp")
    assert_true(captured["env"].get("PATH", "").startswith(f"{monitor._PYTHON_BIN}:{monitor._SYSTEM_BIN}"), "run_aq_qa should prefer service Python before system tools")
    assert_true(captured["env"].get("PYTHONDONTWRITEBYTECODE") == "1", "run_aq_qa should not write pyc files into the read-only repo")
    assert_true(captured["env"].get("PYTHONPYCACHEPREFIX") == str(monitor._PYTHONPYCACHEPREFIX), "run_aq_qa should redirect pycache writes")
    assert_true(captured["env"].get("CARGO_TARGET_DIR") == str(monitor._CARGO_TARGET_DIR), "run_aq_qa should redirect cargo target writes")
    assert_true(monitor._TMPDIR.exists(), "run_aq_qa should create repo-local tmpdir")
    assert_true(monitor._PYTHONPYCACHEPREFIX.exists(), "run_aq_qa should create pycache dir")
    assert_true(monitor._CARGO_TARGET_DIR.exists(), "run_aq_qa should create cargo target dir")


    # --- machine recovery of the qa-phase-0 alert -------------------------------------------------------
    import attention_queue as aq

    def clean_result(n=3):
        return {"phase": "0", "_monitor_returncode": 0, "degraded_confidence": False, "passed": n, "failed": 0,
                "skipped": 0, "tests": [{"id": f"0.{i}", "status": "PASS"} for i in range(n)]}

    clean = monitor.is_complete_clean_phase0_result
    assert_true(clean(clean_result()), "a complete all-PASS phase-0 result must be clean")
    def mut(**kw):
        d = clean_result()
        d.update(kw)
        return d
    unclean = {
        "non-dict": [], "error": mut(error="x"), "phase": mut(phase="1"), "rc missing": {k: v for k, v in clean_result().items() if k != "_monitor_returncode"},
        "rc nonzero": mut(_monitor_returncode=1), "rc bool": mut(_monitor_returncode=False), "rc str": mut(_monitor_returncode="0"),
        "degraded": mut(degraded_confidence=True), "degraded missing": {k: v for k, v in clean_result().items() if k != "degraded_confidence"},
        "passed bool": mut(passed=True), "failed bool": mut(failed=False), "negative": mut(skipped=-1),
        "skipped": mut(skipped=1, passed=2, tests=clean_result(3)["tests"][:2] + [{"id": "s", "status": "SKIP"}]),
        "failed": mut(failed=1), "empty tests": mut(tests=[], passed=0), "count mismatch": mut(passed=2),
        "test status": mut(tests=[{"id": "0.0", "status": "pass"}] * 3), "test no id": mut(tests=[{"id": "", "status": "PASS"}] * 3),
        "test not obj": mut(tests=["PASS"] * 3), "tests not list": mut(tests="x"),
    }
    for name, data in unclean.items():
        assert_true(not clean(data), f"predicate must reject: {name}")

    # a JSON-supplied _monitor_returncode must not shadow the real subprocess result
    original_run = monitor.subprocess.run
    try:
        monitor.subprocess.run = lambda cmd, **kw: subprocess.CompletedProcess(
            cmd, 3, stdout=json.dumps(clean_result()), stderr="")
        shadowed = monitor.run_aq_qa("0")
        assert_true(shadowed["_monitor_returncode"] == 3 and not clean(shadowed),
                    "actual nonzero returncode must override a JSON-supplied 0")
        monitor.subprocess.run = lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout="[1]", stderr="")
        assert_true("error" in monitor.run_aq_qa("0"), "non-object JSON must be an error, not clean")
    finally:
        monitor.subprocess.run = original_run

    def fresh_queue():
        isolate_queue(aq, Path(tempfile.mkdtemp(prefix="health-monitor-queue-")))

    def push_p0(detail="d"):
        return aq.push(source="ai-stack-health-monitor", severity="high", autonomy_boundary="human_gate",
                       title="QA phase 0: 1 check failing", detail=detail, proposed_action="fix",
                       dedup_key="qa-phase-0", ttl_s=3600)

    def pending_ids():
        return [a["id"] for a in aq.get_pending()]

    def archive_rows():
        return [json.loads(l) for l in aq._ARCHIVE_FILE.read_text().splitlines()] if aq._ARCHIVE_FILE.exists() else []

    def run_main(probe):
        monitor.run_aq_qa = probe
        monitor.write_status = lambda status: None
        monitor._PHASES = ["0"]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            monitor.main()

    monitor.push = aq.push
    try:
        # queue fields: generation 1 on create, +1 on every identical dedup push
        fresh_queue()
        pid = push_p0()
        alert = aq.get_by_id(pid)
        assert_true(alert["dedup_key"] == "qa-phase-0" and alert["observation_generation"] == 1, "new alert persists raw key + generation 1")
        assert_true(push_p0() is None and aq.get_by_id(pid)["observation_generation"] == 2, "identical dedup push must bump the generation")
        push_p0("changed")
        assert_true(aq.get_by_id(pid)["observation_generation"] == 3, "changed dedup push must bump the generation")
        other = aq.push(source="ai-stack-health-monitor", severity="high", autonomy_boundary="human_gate", title="o",
                        detail="d", proposed_action="p", dedup_key="qa-phase-0-error", ttl_s=3600)
        assert_true("observation_generation" not in aq.get_by_id(other), "other keys get no generation")

        # clean run retires exactly once, with audit fields, and refreshes the mirror
        fresh_queue()
        pid = push_p0()
        order = []
        def clean_probe(phase):
            order.append("probe")
            return clean_result()
        real_snapshot = monitor.snapshot_recovery_candidate
        monitor.snapshot_recovery_candidate = lambda: (order.append("snapshot"), real_snapshot())[1]
        try:
            run_main(clean_probe)
        finally:
            monitor.snapshot_recovery_candidate = real_snapshot
        assert_true(order == ["snapshot", "probe"], "snapshot must precede the probe")
        assert_true(pending_ids() == [] and aq.get_by_id(pid) is None, "clean run must retire the pending alert")
        rows = archive_rows()
        assert_true(len(rows) == 1 and rows[0]["status"] == "recovered" and rows[0]["recovery_reason"] == "phase-0-clean"
                    and rows[0]["resolved_by"] == "ai-stack-health-monitor" and rows[0]["recovered_at"].endswith("Z")
                    and rows[0]["detail"] == "d" and rows[0]["id"] == pid, "archive record audit fields + preserved payload")
        assert_true(json.loads(aq._MIRROR_PATH.read_text())["pending_human_gate"] == 0, "retirement must update the mirror snapshot")
        run_main(clean_probe)
        assert_true(len(archive_rows()) == 1, "a second clean run must not re-archive")
        rec = aq.last_machine_recovery()
        assert_true(rec == {"source": "ai-stack-health-monitor", "dedup_key": "qa-phase-0",
                            "recovered_at": rows[0]["recovered_at"], "recovery_reason": "phase-0-clean"}, "last_machine_recovery projection")
        # fail -> clean -> fail creates a new pending alert with later evidence
        new_id = push_p0("later failure")
        assert_true(new_id != pid and aq.get_by_id(new_id)["detail"] == "later failure", "re-failure must alert anew")

        # concurrent failure observed while the probe runs wins
        fresh_queue()
        pid = push_p0()
        def racing_probe(phase):
            push_p0()  # identical dedup push: generation bump only
            return clean_result()
        run_main(racing_probe)
        assert_true(pending_ids() == [pid] and not archive_rows(), "a failure during the probe must keep the alert pending")

        # unclean / failing / error probes never retire
        for label, probe in {
            "skip": lambda p: mut(skipped=1, passed=2, tests=clean_result(3)["tests"][:2] + [{"id": "s", "status": "SKIP"}]),
            "nonzero": lambda p: mut(_monitor_returncode=1),
            "error": lambda p: {"error": "timeout", "phase": p, "checks": [], "summary": {"failed": 1}},
            "failing": lambda p: {"phase": "0", "tests": [{"id": "0.1", "status": "FAIL"}], "_monitor_returncode": 1},
        }.items():
            fresh_queue()
            pid = push_p0()
            run_main(probe)
            assert_true(aq.get_by_id(pid) is not None and not [r for r in archive_rows() if r.get("status") == "recovered"],
                        f"{label} probe must not retire the alert")

        # retire_recovered fences: wrong id/source/key/generation, manual resolution
        fresh_queue()
        pid = push_p0()
        snap = aq.snapshot_recovery_candidate()
        assert_true(snap["id"] == pid and snap["observation_generation"] == 1, "snapshot content")
        for bad in ({**snap, "observation_generation": 2}, {**snap, "id": "attn-x"}, {**snap, "source": "x"},
                    {**snap, "dedup_key": "qa-phase-0-error"}, {**snap, "observation_generation": True}, {}, None):
            assert_true(aq.retire_recovered(bad) is False and aq.get_by_id(pid) is not None, f"fenced retire {bad}")
        assert_true(aq.resolve(pid, "deferred", resolved_by="human"), "manual resolve")
        assert_true(aq.retire_recovered(snap) is False and archive_rows()[-1]["status"] == "deferred", "manual decision must win")

        # legacy migration: exactly one exact-identity row
        fresh_queue()
        pid = push_p0()
        data = json.loads(aq._QUEUE_FILE.read_text())
        for a in data["alerts"]:
            a.pop("dedup_key"); a.pop("observation_generation")
        aq._QUEUE_FILE.write_text(json.dumps(data))
        snap = aq.snapshot_recovery_candidate()
        stored = aq.get_by_id(pid)
        assert_true(snap and snap["observation_generation"] == 1 and stored["dedup_key"] == "qa-phase-0" and stored["observation_generation"] == 1,
                    "legacy row migrated to raw key + generation 1")
        for label, mutate in {
            "duplicate": lambda d: d["alerts"].append({**d["alerts"][0], "id": "attn-dup"}),
            "wrong identity": lambda d: d["alerts"][0].update(identity="0" * 16),
            "wrong boundary": lambda d: d["alerts"][0].update(autonomy_boundary="auto_ok"),
            "wrong source": lambda d: d["alerts"][0].update(source="other"),
            "wrong raw key": lambda d: d["alerts"][0].update(dedup_key="other"),
            "bad generation": lambda d: d["alerts"][0].update(observation_generation=0),
        }.items():
            fresh_queue()
            push_p0()
            d = json.loads(aq._QUEUE_FILE.read_text())
            d["alerts"][0].pop("dedup_key"); d["alerts"][0].pop("observation_generation")
            mutate(d)
            if label == "wrong raw key":
                d["alerts"][0]["dedup_key"] = "other"
            if label == "bad generation":
                d["alerts"][0]["dedup_key"] = "qa-phase-0"
            aq._QUEUE_FILE.write_text(json.dumps(d))
            assert_true(aq.snapshot_recovery_candidate() is None, f"migration must be a no-op: {label}")

        # bounded archive window and newest-by-timestamp selection
        fresh_queue()
        def rec_row(ts):
            return json.dumps({"status": "recovered", "source": "ai-stack-health-monitor", "dedup_key": "qa-phase-0",
                               "recovery_reason": "phase-0-clean", "recovered_at": ts, "detail": "secret"})
        aq._ARCHIVE_FILE.write_text("\n".join([rec_row("2026-01-02T00:00:00Z"), rec_row("2026-01-01T00:00:00Z"),
                                               "not json", rec_row("garbage")]) + "\n")
        assert_true(aq.last_machine_recovery()["recovered_at"] == "2026-01-02T00:00:00Z", "newest recovered_at wins, not archive order")
        aq._ARCHIVE_FILE.write_text(rec_row("2026-01-02T00:00:00Z") + "\n" + "\n".join(json.dumps({"status": "approved"}) for _ in range(200)) + "\n")
        assert_true(aq.last_machine_recovery() is None, "a recovery older than the 200-record window is null")
    finally:
        monitor.push = original_push
        monitor.run_aq_qa = original_run_qa
        monitor._PHASES = original_phases
        monitor.write_status = original_write_status

    original_status_path = monitor._STATUS_PATH
    try:
        monitor._STATUS_PATH = ROOT / ".agents" / "tmp" / "test-health-monitor-status.json"
        monitor.write_status({"source": "test", "total_failures": 0})
        status = json.loads(monitor._STATUS_PATH.read_text(encoding="utf-8"))
        assert_true(status["source"] == "test", "write_status should persist JSON status")
        assert_true(status["total_failures"] == 0, "write_status should preserve counters")
    finally:
        monitor._STATUS_PATH = original_status_path

    # aq-qa phase 0 takes its evidence lock in hybrid/telemetry; under
    # ProtectSystem=strict the unit must declare it writable (2026-10-02 EROFS).
    nix_src = (Path(__file__).resolve().parents[2] / "nix/modules/roles/ai-stack.nix").read_text(encoding="utf-8")
    unit = nix_src.split("systemd.services.ai-stack-health-monitor = {", 1)[1].split("systemd.timers.ai-stack-health-monitor", 1)[0]
    assert_true('"${cfg.mcpServers.dataDir}/hybrid/telemetry"' in unit,
                "health monitor unit must allow writes to the QA evidence lock dir")

    # Verify configurable harness timeout is properly configured.
    assert_true(hasattr(monitor, "_HARNESS_TIMEOUT_S"),
                "monitor should define _HARNESS_TIMEOUT_S constant")
    assert_true(monitor._HARNESS_TIMEOUT_S >= 430,
                f"default _HARNESS_TIMEOUT_S ({monitor._HARNESS_TIMEOUT_S}s) must be >= 430s (measured 2.5x phase 0 time)")
    assert_true("HARNESS_TIMEOUT_S=430" in unit or "HARNESS_TIMEOUT_S" in unit,
                "health monitor unit serviceConfig must set HARNESS_TIMEOUT_S env var")
    import re
    timeout_s = re.search(r'TimeoutStartSec\s*=\s*"(\d+)"', unit)
    assert_true(timeout_s and int(timeout_s.group(1)) >= 490,
                "health monitor unit must set TimeoutStartSec >= 490s (harness timeout + margin)")
    mem = re.search(r'MemoryMax\s*=\s*"(\d+)M"', unit)
    assert_true(mem and int(mem.group(1)) >= 768,
                "health monitor unit must set MemoryMax >= 768M (1.5x measured 504M peak RSS)")

    print("PASS: ai-stack-health-monitor handles aq-qa JSON schema, TMPDIR, status writes, evidence-lock path, and configurable timeout")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
