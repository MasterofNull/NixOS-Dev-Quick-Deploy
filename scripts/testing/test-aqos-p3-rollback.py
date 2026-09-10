#!/usr/bin/env python3
"""Offline acceptance tests for the AQ-OS P3 rollback safety net."""

from __future__ import annotations

import dataclasses
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "scripts" / "ai" / "lib"
sys.path.insert(0, str(LIB_DIR))

import approval_executor as AE  # noqa: E402
import approval_request as AR  # noqa: E402
import aqos_rollback as rollback  # noqa: E402


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class Store:
    def __init__(self, record: dict) -> None:
        self.record = record

    def load(self, request_id: str):
        return self.record if self.record["request_id"] == request_id else None

    def save(self, record: dict) -> None:
        self.record = record


def request_for(plan: rollback.RollbackPlan, request_id: str, *, current: int) -> dict:
    return AR.create_request(
        request_id=request_id,
        created_by="test-aqos-p3-rollback",
        runbook=rollback.RUNBOOK_NAME,
        params=rollback.request_params(plan, current_generation=current),
        grant_subject="system-recovery",
    )


def test_capture_generation_from_mocked_profile_link() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        profile = Path(tmp) / "system"
        os.symlink("/nix/var/nix/profiles/system-47-link", profile)
        check(rollback.capture_generation(profile) == 47, "generation must come from the profile link")


def test_plans_are_typed_plain_language_without_hashes() -> None:
    back = rollback.plan_rollback(48, 47)
    forward = rollback.plan_roll_forward({"schema": "aqos.install-plan-lock.v1"})
    check(back.direction is rollback.RollbackDirection.BACK, "rollback plan must be typed as back")
    check(forward.direction is rollback.RollbackDirection.FORWARD, "roll-forward plan must be typed")
    for plan in (back, forward):
        check(bool(plan.description), "plans need a plain-language description")
        check("sha256" not in plan.description.lower(), "plain language must not expose hash jargon")
        check(re.search(r"\b[0-9a-fA-F]{64}\b", plan.description) is None, "no digest may be shown")


def test_runbook_registered_and_pending_is_inert() -> None:
    check(rollback.RUNBOOK_NAME in AR.RUNBOOK_REGISTRY, "aqos-rollback must be registered")
    plan = rollback.plan_rollback(48, 47)
    record = request_for(plan, "p3-rollback-pending-0001", current=48)
    store = Store(record)
    effect = mock.Mock()
    original = AR.RUNBOOK_REGISTRY[rollback.RUNBOOK_NAME]
    AR.RUNBOOK_REGISTRY[rollback.RUNBOOK_NAME] = dataclasses.replace(original, effect=effect)
    try:
        outcome = AE.execute_request(record["request_id"], load_record=store.load, save_record=store.save)
    finally:
        AR.RUNBOOK_REGISTRY[rollback.RUNBOOK_NAME] = original
    check(outcome.reason == AE.REASON_NOT_APPROVED, "pending request must be rejected")
    effect.assert_not_called()


def test_approved_rollback_resolves_only_to_inert_native_effect() -> None:
    plan = rollback.plan_rollback(48, 47)
    record = request_for(plan, "p3-rollback-approved-0001", current=48)
    approved, _ = AR.transition(record, AR.STATUS_APPROVED, actor="owner-webauthn")
    store = Store(approved)
    with mock.patch.object(subprocess, "run") as system_call:
        outcome = AE.execute_request(record["request_id"], load_record=store.load, save_record=store.save)
    check(outcome.ok, f"approved rollback effect should resolve: {outcome.reason}")
    result = next(event["result"] for event in outcome.events if event["event"] == "effect_executed")
    check(result["executor"]["argv"] == ["nixos-rebuild", "switch", "--rollback"],
          "rollback must use the native NixOS generation command")
    check(result["executor"]["executable"] is False, "P0 effect must stay inert")
    system_call.assert_not_called()


def test_approved_roll_forward_reprojects_known_good_lock_inertly() -> None:
    lock = {"schema": "aqos.install-plan-lock.v1", "selection": {"golden_profile": "profile.base"}}
    plan = rollback.plan_roll_forward(lock)
    record = request_for(plan, "p3-forward-approved-0001", current=48)
    approved, _ = AR.transition(record, AR.STATUS_APPROVED, actor="owner-webauthn")
    store = Store(approved)
    inert_projection = {"executor": {"executable": False, "argv": ["build-only"]}}
    with (
        mock.patch.object(rollback, "_load_projection_inputs", return_value=({}, b"{}")),
        mock.patch.object(rollback.resolver, "compile_projection", return_value=inert_projection) as compile_call,
        mock.patch.object(subprocess, "run") as system_call,
    ):
        outcome = AE.execute_request(record["request_id"], load_record=store.load, save_record=store.save)
    check(outcome.ok, f"approved roll-forward effect should resolve: {outcome.reason}")
    compile_call.assert_called_once_with(lock, {}, b"{}")
    result = next(event["result"] for event in outcome.events if event["event"] == "effect_executed")
    check(result["projection"]["executor"]["executable"] is False, "roll-forward must stay inert")
    system_call.assert_not_called()


def test_denied_and_expired_requests_apply_nothing() -> None:
    plan = rollback.plan_rollback(48, 47)
    original = AR.RUNBOOK_REGISTRY[rollback.RUNBOOK_NAME]
    effect = mock.Mock()
    AR.RUNBOOK_REGISTRY[rollback.RUNBOOK_NAME] = dataclasses.replace(original, effect=effect)
    try:
        for status, request_id in (
            (AR.STATUS_DENIED, "p3-rollback-denied-0001"),
            (AR.STATUS_EXPIRED, "p3-rollback-expired-0001"),
        ):
            record = request_for(plan, request_id, current=48)
            terminal, _ = AR.transition(record, status, actor="test")
            store = Store(terminal)
            outcome = AE.execute_request(request_id, load_record=store.load, save_record=store.save)
            check(outcome.reason == AE.REASON_NOT_APPROVED, f"{status} request must not execute")
    finally:
        AR.RUNBOOK_REGISTRY[rollback.RUNBOOK_NAME] = original
    effect.assert_not_called()


def test_observability_state_reports_generation_and_availability() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        state_path = Path(tmp) / "aqos-rollback.json"
        rollback.write_rollback_state(48, 47, state_path)
        state = json.loads(state_path.read_text(encoding="utf-8"))
    check(state["current_generation"] == 48, "state must expose current generation")
    check(state["captured_generation"] == 47, "state must expose captured generation")
    check(state["rollback_available"] is True, "newer current generation makes rollback available")


def main() -> int:
    tests = sorted((name, value) for name, value in globals().items() if name.startswith("test_") and callable(value))
    failures: list[str] = []
    for name, test in tests:
        try:
            test()
            print(f"PASS {name}")
        except Exception as exc:  # noqa: BLE001 - standalone test runner reports all failures
            failures.append(f"{name}: {exc}")
            print(f"FAIL {name}: {exc}")
    if failures:
        print(f"\n{len(failures)} failure(s)", file=sys.stderr)
        return 1
    print(f"\nPASS: {len(tests)} p3-rollback tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
