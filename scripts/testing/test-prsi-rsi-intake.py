#!/usr/bin/env python3
"""Focused offline coverage for bounded RSI incident intake in PRSI."""

from __future__ import annotations

import importlib.util
import json
import tempfile
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]

# The live dispatcher performs Git preflight/worktree operations. Keep its
# systemd runtime PATH contract explicit so hardening cannot disable RSI.
service_config = (ROOT / "nix/modules/roles/ai-stack.nix").read_text(encoding="utf-8")
dispatch_service = service_config.split("systemd.services.ai-prsi-rsi-dispatch = {", 1)[1].split("\n      };", 1)[0]
# delegate-to-local needs bash/python3/util-linux/curl on the unit PATH (exit 127 on 2026-09-30).
# python3 must come from the system cliPython (httpx etc.), not bare pkgs.python3.
for dep in ("pkgs.git", "pkgs.bash", "pkgs.util-linux", "pkgs.curl", '"/run/current-system/sw"'):
    assert dep in dispatch_service.split("path = [", 1)[1].split("];", 1)[0], dep
assert "pkgs.python3" not in dispatch_service.split("path = [", 1)[1].split("];", 1)[0]
# Live repair appends to the collaboration runtime and RSI registers (EROFS 2026-09-30).
for rw in ("/.agent/collaboration\"", "/.agent/memory/issues-backlog.md\"", "/.agent/WORKAROUND-REGISTER.md\""):
    assert rw in dispatch_service, rw
# Repair budget must fit local agent-mode pacing and a worktree checkout.
assert "--timeout-seconds=2400" in dispatch_service and 'TimeoutSec = "2460"' in dispatch_service
assert 'MemoryMax = "1G"' in dispatch_service
print("PASS: RSI dispatcher systemd PATH provides Git")


def load_prsi():
    path = ROOT / "scripts" / "automation" / "prsi-orchestrator.py"
    spec = importlib.util.spec_from_file_location("prsi_orchestrator_rsi_intake", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


with tempfile.TemporaryDirectory() as tmp:
    tmp_path = Path(tmp)
    incidents_path = tmp_path / "rsi-incidents.json"
    queue_path = tmp_path / "action-queue.json"
    state_path = tmp_path / "runtime-state.json"
    log_path = tmp_path / "prsi-actions.jsonl"
    raw_error = "UNTRUSTED-ERROR " + ("x" * 20_000)
    incidents_path.write_text(json.dumps({
        "version": 1,
        "incidents": {
            "fingerprint-open": {
                "id": "rsi-incident-42",
                "producer": "untrusted-producer",
                "path": "scripts/testing/test-prsi-rsi-intake.py",
                "authority": "untrusted-authority",
                "error": raw_error,
                "root_fix": "also untrusted",
                "status": "open",
                "count": 1,
                "first_seen": "2026-01-01T00:00:00Z",
                "last_seen": "2026-01-01T00:00:00Z",
                "agent": "agent",
                "subject": "subject",
                "severity": "high",
            },
            "fingerprint-resolved": {
                "id": "rsi-resolved-7",
                "status": "resolved",
                "severity": "critical",
            },
            "fingerprint-invalid": {
                "id": "bad id with spaces",
                "status": "open",
                "severity": "critical",
            },
        },
    }), encoding="utf-8")

    prsi = load_prsi()
    prsi._RSI_INCIDENTS = incidents_path
    prsi.QUEUE_PATH = queue_path
    prsi.PRSI_STATE_PATH = state_path
    prsi.ACTIONS_LOG_PATH = log_path
    prsi._fetch_report = lambda since: {}
    prsi._fetch_delegation_feedback_actions = lambda since: []
    prsi._fetch_workflow_deviation_actions = lambda: []

    candidates = prsi._fetch_rsi_incident_actions()
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["incident_id"] == "rsi-incident-42"
    assert candidate["root_issue_key"] == "rsi-incident:rsi-incident-42"
    assert candidate["shadow_only"] is True and candidate["safe"] is False
    assert raw_error not in json.dumps(candidate)
    assert len(json.dumps(candidate)) < 1_000
    print("PASS: open incidents become bounded inert candidates")

    assert prsi.cmd_sync(Namespace(since="1d")) == 0
    queued = json.loads(queue_path.read_text(encoding="utf-8"))["actions"]
    assert len(queued) == 1
    row = queued[0]
    stable_id = row["id"]
    assert row["status"] == "shadow_queued"
    assert row["risk"] == "high"
    assert raw_error not in queue_path.read_text(encoding="utf-8")

    store = json.loads(incidents_path.read_text(encoding="utf-8"))
    store["incidents"]["fingerprint-open"]["count"] = 2
    incidents_path.write_text(json.dumps(store), encoding="utf-8")
    assert prsi.cmd_sync(Namespace(since="1d")) == 0
    deduped = json.loads(queue_path.read_text(encoding="utf-8"))["actions"]
    assert len(deduped) == 1 and deduped[0]["id"] == stable_id
    assert deduped[0]["seen_count"] == 2
    assert deduped[0]["raw_action"]["incident_count"] == 2
    print("PASS: repeated incident ids update one stable queue candidate")

    # A failure event must remain ingestible when report/model services fail.
    # Exercise the real dispatch entrypoint, including idempotent queue merge.
    prior_meta = {"since": "7d", "degradation": {"degraded": True, "reasons": ["existing-signal"]}}
    queue_path.write_text(json.dumps({"actions": deduped, "meta": prior_meta}), encoding="utf-8")
    prsi._RSI_DISPATCH_LOCK = tmp_path / "rsi-dispatch.lock"
    dispatch_args = Namespace(since="1d", execute=False, max_attempts=3)
    with patch.object(prsi, "_fetch_structured_actions", side_effect=AssertionError("report pipeline invoked")):
        assert prsi.cmd_rsi_dispatch(dispatch_args) == 0
        assert prsi.cmd_rsi_dispatch(dispatch_args) == 0
    snapshot = json.loads(queue_path.read_text(encoding="utf-8"))
    assert snapshot["meta"] == prior_meta
    assert len(snapshot["actions"]) == 1
    assert snapshot["actions"][0]["id"] == stable_id
    assert snapshot["actions"][0]["status"] == "rsi_pending"
    events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert events[-1]["scope"] == "rsi_incidents"
    print("PASS: RSI dispatch bypasses report/model pipeline and preserves degradation evidence")

    try:
        prsi._set_approval(stable_id, "approve", "test-owner", "must remain inert")
    except PermissionError as exc:
        assert str(exc) == "shadow-only-action-cannot-be-approved"
    else:
        raise AssertionError("RSI candidate must not be approved")

    deduped[0]["status"] = "approved"  # Corrupt/pre-existing state defense.
    queue_path.write_text(json.dumps({"actions": deduped, "meta": {}}), encoding="utf-8")
    called = {"value": False}

    def forbidden_subprocess(*args, **kwargs):
        called["value"] = True
        raise AssertionError("RSI candidate reached aq-optimizer")

    prsi.subprocess.run = forbidden_subprocess
    assert prsi.cmd_execute(Namespace(limit=5, dry_run=False)) == 0
    after = json.loads(queue_path.read_text(encoding="utf-8"))["actions"][0]
    assert called["value"] is False
    assert after["status"] == "shadow_queued"
    assert after["execution"]["result"] == "blocked_shadow_only"
    print("PASS: RSI candidates cannot reach optimizer execution")

# A zero exit status, generic diagnostic words, malformed ids, or stderr-only
# receipts are not handoff proof. Only the delegate's exact stdout line counts.
success_receipt = "[delegate-to-local] Task local-20260928-123456-abcdef completed.\n"
for stdout, stderr, code, expected in [
    ("result: maybe completed", "worktree created", 0, "rsi_failed"),
    ("Task rsi-42 completed.\n", "", 0, "rsi_failed"),
    ("", success_receipt, 0, "rsi_failed"),
    (success_receipt, "warning: diagnostic only", 0, "rsi_awaiting_validation"),
    (success_receipt, "failed", 1, "rsi_failed"),
]:
    proc = type("Proc", (), {"returncode": code, "communicate": lambda self, timeout=None: (stdout, stderr)})()
    with patch.object(prsi.subprocess, "Popen", return_value=proc):
        result, _receipt = prsi._run_rsi_delegate(row, 30, False)
    assert result == expected, (result, expected)
print("PASS: RSI dispatch requires an exact successful delegate receipt")

print("PASS: PRSI RSI incident intake")
