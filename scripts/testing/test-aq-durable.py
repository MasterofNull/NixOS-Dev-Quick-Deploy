#!/usr/bin/env python3
"""Comprehensive unit test suite for Durable Agent Runtime & Effect Sandwich (DP-2)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ai" / "lib"))

from durable_runtime import (
    ConcurrencyConflictError,
    DurableEffectStore,
    EffectSandwichMiddleware,
    IntentState,
    OutcomeUnknownError,
    ToolClass,
    classify_tool,
    compute_idempotency_key,
)


def assert_true(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def main() -> int:
    passed = 0
    total = 7

    print("=== Testing Durable Agent Runtime & Effect Sandwich (DP-2) ===")

    with tempfile.TemporaryDirectory(prefix="test-aq-durable-") as tmp:
        tmp_dir = Path(tmp)
        ledger_file = tmp_dir / "ledger.json"

        # ── 1. Tool Classification ──────────────────────────────────────────
        try:
            assert_true(classify_tool("cat") == ToolClass.CLASS_1_READ_ONLY, "cat should be Class 1")
            assert_true(classify_tool("read_file") == ToolClass.CLASS_1_READ_ONLY, "read_file should be Class 1")
            assert_true(classify_tool("agrep") == ToolClass.CLASS_1_READ_ONLY, "agrep should be Class 1")
            assert_true(classify_tool("write_to_file") == ToolClass.CLASS_2_IDEMPOTENT_WRITE, "write_to_file should be Class 2")
            assert_true(classify_tool("replace_file_content") == ToolClass.CLASS_2_IDEMPOTENT_WRITE, "replace should be Class 2")
            assert_true(classify_tool("git_push") == ToolClass.CLASS_3_EXTERNAL_MUTATION, "git_push should be Class 3")
            assert_true(classify_tool("deploy") == ToolClass.CLASS_3_EXTERNAL_MUTATION, "deploy should be Class 3")
            print("  PASS  DP-2 [1/7]: Tool classification assigns Class 1, 2, and 3 correctly")
            passed += 1
        except Exception as e:
            print(f"  FAIL  DP-2 [1/7]: Tool classification: {e}")

        # ── 2. Effect Sandwich Happy Path ────────────────────────────────────
        try:
            store = DurableEffectStore(ledger_file)
            middleware = EffectSandwichMiddleware(store)

            calls = []
            def sample_mutation(args):
                calls.append(args)
                return {"status": "ok", "applied": args["value"]}

            intent, res = middleware.execute(
                run_id="run-1",
                step_id=1,
                tool_name="sample_write",
                args={"key": "test", "value": 42},
                execution_fn=sample_mutation,
            )

            assert_true(intent.state == IntentState.COMMITTED.value, "State should be COMMITTED")
            assert_true(intent.version == 3, f"Expected version 3 after 2 transitions, got {intent.version}")
            assert_true(res == {"status": "ok", "applied": 42}, "Result should match mutation output")
            assert_true(len(calls) == 1, "Mutation function should be called once")
            print("  PASS  DP-2 [2/7]: Effect sandwich happy path (PREPARED -> EXECUTING -> COMMITTED)")
            passed += 1
        except Exception as e:
            print(f"  FAIL  DP-2 [2/7]: Effect sandwich happy path: {e}")

        # ── 3. Idempotent Deduplication & Replay Safety ─────────────────────
        try:
            # Execute identical run_id, step_id, tool_name, and args
            replay_intent, replay_res = middleware.execute(
                run_id="run-1",
                step_id=1,
                tool_name="sample_write",
                args={"key": "test", "value": 42},
                execution_fn=sample_mutation,
            )

            assert_true(replay_intent.intent_id == intent.intent_id, "Should return existing intent")
            assert_true(replay_intent.state == IntentState.COMMITTED.value, "Replay state should remain COMMITTED")
            assert_true(replay_res == {"status": "ok", "applied": 42}, "Replay result should match cached receipt")
            assert_true(len(calls) == 1, "Mutation function must NOT be called again on replay")
            print("  PASS  DP-2 [3/7]: Idempotency deduplication returns cached receipt without re-execution")
            passed += 1
        except Exception as e:
            print(f"  FAIL  DP-2 [3/7]: Idempotency deduplication: {e}")

        # ── 4. Known Domain Failure Handling ─────────────────────────────────
        try:
            def failing_tool(args):
                raise ValueError("Invalid target parameter")

            failed_caught = False
            try:
                middleware.execute(
                    run_id="run-1",
                    step_id=2,
                    tool_name="failing_tool",
                    args={"target": "invalid"},
                    execution_fn=failing_tool,
                )
            except ValueError:
                failed_caught = True

            assert_true(failed_caught, "Expected ValueError to be raised")
            records = store.list_intents(run_id="run-1", state=IntentState.FAILED_KNOWN)
            assert_true(len(records) == 1, "Should record 1 FAILED_KNOWN intent")
            assert_true(records[0].error == "Invalid target parameter", "Error message recorded correctly")
            print("  PASS  DP-2 [4/7]: Known domain failures transition cleanly to FAILED_KNOWN")
            passed += 1
        except Exception as e:
            print(f"  FAIL  DP-2 [4/7]: Known failure handling: {e}")

        # ── 5. Crash Simulation & Outcome Reconciliation ─────────────────────
        try:
            # Case A: Mutation actually landed before crash
            mutation_landed = False
            def crashing_mutation_a(args):
                nonlocal mutation_landed
                mutation_landed = True
                raise ConnectionResetError("Process crashed mid-network-call")

            def inspector_a(args):
                # Verifies target state
                return mutation_landed, {"verified": True, "landed_at": "upstream"}

            rec_intent, rec_res = middleware.execute(
                run_id="run-crash",
                step_id=1,
                tool_name="git_push",
                args={"remote": "origin", "branch": "feat/x"},
                execution_fn=crashing_mutation_a,
                target_inspector_fn=inspector_a,
            )

            assert_true(rec_intent.state == IntentState.RECONCILED_COMMITTED.value, "Should be RECONCILED_COMMITTED")
            assert_true(rec_res == {"verified": True, "landed_at": "upstream"}, "Reconciled result returned")

            # Case B: Mutation did NOT land before crash
            def crashing_mutation_b(args):
                raise TimeoutError("Deadlock before write")

            def inspector_b(args):
                return False, None

            crashed_b = False
            try:
                middleware.execute(
                    run_id="run-crash",
                    step_id=2,
                    tool_name="git_push",
                    args={"remote": "origin", "branch": "feat/y"},
                    execution_fn=crashing_mutation_b,
                    target_inspector_fn=inspector_b,
                )
            except OutcomeUnknownError:
                crashed_b = True

            assert_true(crashed_b, "Should raise OutcomeUnknownError when mutation did not land")
            intent_b = store.list_intents(run_id="run-crash", state=IntentState.RECONCILED_FAILED)[0]
            assert_true(intent_b.state == IntentState.RECONCILED_FAILED.value, "Should be RECONCILED_FAILED")
            print("  PASS  DP-2 [5/7]: Crash & OUTCOME_UNKNOWN reconciliation handles landed vs unapplied mutations")
            passed += 1
        except Exception as e:
            print(f"  FAIL  DP-2 [5/7]: Crash and outcome reconciliation: {e}")

        # ── 6. Monotonic CAS Concurrency Conflict Detection ─────────────────
        try:
            intent_cas = store.prepare_intent("run-cas", 1, "test_tool", {"v": 1})
            # Transition with wrong version
            conflict_caught = False
            try:
                store.transition(intent_cas.intent_id, IntentState.EXECUTING, expected_version=999)
            except ConcurrencyConflictError:
                conflict_caught = True

            assert_true(conflict_caught, "Expected ConcurrencyConflictError on version mismatch")
            print("  PASS  DP-2 [6/7]: Monotonic CAS prevents lost updates and concurrent mutation races")
            passed += 1
        except Exception as e:
            print(f"  FAIL  DP-2 [6/7]: CAS concurrency conflict: {e}")

        # ── 7. CLI Utility (aq-durable) Integration ──────────────────────────
        try:
            cli = ROOT / "scripts" / "ai" / "aq-durable"
            # Status command
            proc_status = subprocess.run(
                [sys.executable, str(cli), "--ledger", str(ledger_file), "status", "--json"],
                capture_output=True, text=True, check=True
            )
            data = json.loads(proc_status.stdout)
            assert_true(data["count"] >= 4, "CLI status should return recorded intents")

            # Verify command
            proc_verify = subprocess.run(
                [sys.executable, str(cli), "--ledger", str(ledger_file), "verify"],
                capture_output=True, text=True, check=True
            )
            assert_true("PASS: Durable ledger integrity valid" in proc_verify.stdout, "Verify should pass")

            # Classify command
            proc_cls = subprocess.run(
                [sys.executable, str(cli), "classify", "read_file", "--json"],
                capture_output=True, text=True, check=True
            )
            cls_data = json.loads(proc_cls.stdout)
            assert_true(cls_data["tool_class"] == "read_only", "CLI classify should return read_only")

            print("  PASS  DP-2 [7/7]: CLI utility aq-durable (status, verify, classify) fully functional")
            passed += 1
        except Exception as e:
            print(f"  FAIL  DP-2 [7/7]: CLI utility integration: {e}")

    print(f"\n{passed}/{total} fixtures passed.")
    if passed == total:
        print("ALL 7 FIXTURES PASS")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
