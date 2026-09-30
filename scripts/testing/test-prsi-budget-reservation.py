#!/usr/bin/env python3
"""Offline regressions for shared, pre-dispatch PRSI budget reservations."""
import importlib.util
import multiprocessing
import tempfile
from argparse import Namespace
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("prsi", ROOT / "scripts/automation/prsi-orchestrator.py")
prsi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prsi)
POLICY = {"enabled": True, "budget": {"remote_token_cap_daily": 100}, "counterfactual": {"sample_rate": 0}}


def row():
    return {"id": "test", "status": "approved", "estimated_token_cost": 60,
            "raw_action": {"type": "test"}}


def reserve(start, results):
    start.wait()
    selected, _, _, _ = prsi._reserve_actions_for_execution([row()], POLICY, 1)
    results.put(len(selected))


def main():
    with tempfile.TemporaryDirectory() as tmp:
        prsi.PRSI_STATE_PATH = Path(tmp) / "state.json"
        # Preview must not persist usage, including counterfactual state.
        assert len(prsi._reserve_actions_for_execution([row()], POLICY, 1, dry_run=True)[0]) == 1
        assert not prsi.PRSI_STATE_PATH.exists()
        ctx = multiprocessing.get_context("fork")
        start, results = ctx.Event(), ctx.Queue()
        workers = [ctx.Process(target=reserve, args=(start, results)) for _ in range(4)]
        for worker in workers:
            worker.start()
        start.set()
        for worker in workers:
            worker.join(10)
            assert worker.exitcode == 0
        assert sum(results.get(timeout=2) for _ in workers) == 1
        assert prsi._load_state()["remote_tokens_used"] == 60

        # A successful optimizer process that reports no applied action must
        # leave the PRSI row retryable while keeping its attempted-call budget.
        prsi._save_state({"date": prsi._today_utc(), "remote_tokens_used": 0})
        noop = CompletedProcess([], 0, '{"ok":true,"applied":[]}', "")
        queue = {"actions": [row()]}
        events = []

        def save_state(state):
            import json
            prsi.PRSI_STATE_PATH.write_text(json.dumps(state))

        with patch.object(prsi, "_load_policy", return_value=POLICY), \
             patch.object(prsi, "_load_queue", return_value=queue), \
             patch.object(prsi, "_save_queue"), patch.object(prsi, "_log_event", side_effect=events.append), \
             patch.object(prsi, "_write_json"), patch.object(prsi.subprocess, "run", return_value=noop), \
             patch.object(prsi, "_save_state", side_effect=save_state):
            assert prsi.cmd_execute(Namespace(limit=1, dry_run=False)) == 0
        assert queue["actions"][0]["status"] == "approved"
        assert queue["actions"][0]["execution"]["result"] == "optimizer_noop"
        assert events[-1]["applied_count"] == 0
        assert prsi._load_state()["remote_tokens_used"] == 60

        # Both failure exits must retain the reservation before subprocess work.
        for failure in (CompletedProcess([], 1, "", "failed"), TimeoutExpired("optimizer", 300)):
            prsi._save_state({"date": prsi._today_utc(), "remote_tokens_used": 0})

            def run(*args, **kwargs):
                assert prsi._load_state()["remote_tokens_used"] == 60
                if isinstance(failure, Exception):
                    raise failure
                return failure

            with patch.object(prsi, "_load_policy", return_value=POLICY), \
                 patch.object(prsi, "_load_queue", return_value={"actions": [row()]}), \
                 patch.object(prsi, "_log_event"), patch.object(prsi, "_write_json"), \
                 patch.object(prsi.subprocess, "run", side_effect=run):
                # Keep real state writes while suppressing the unrelated actions payload.
                def save(state):
                    import json
                    prsi.PRSI_STATE_PATH.write_text(json.dumps(state))
                with patch.object(prsi, "_save_state", side_effect=save):
                    try:
                        prsi.cmd_execute(Namespace(limit=1, dry_run=False))
                    except (RuntimeError, TimeoutExpired):
                        pass
                    else:
                        raise AssertionError("failure was swallowed")
            assert prsi._load_state()["remote_tokens_used"] == 60
            assert not prsi._reserve_actions_for_execution([row()], POLICY, 1)[0]
    print("PASS: concurrent reservations, dry run, failure and timeout budgets")


if __name__ == "__main__":
    main()
