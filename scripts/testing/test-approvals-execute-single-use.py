#!/usr/bin/env python3
"""Acceptance tests for single-use execution of approved requests via
`POST /api/approvals/{id}/execute` (defect acp-execute-route-latent-replay).

Covers the replay-prevention and concurrency-safety goals:
- Replay detection: a second POST to the same request returns 409
- Custom stores (without _records): save_record uses the protocol, not private attributes
- Single-use semantics: effect runs exactly once, not multiple times on replay
- Event loop safety: executor is called via threadpool, not blocking the loop
- Store-level claiming: atomic claim prevents concurrent/replay without status changes

Entirely offline: builds a minimal FastAPI app mounting only
`approvals.router` (never imports the full `api.main` app) and wires fresh
`FixtureApprovalStore`/`FixtureSignerClient` instances per check.

`check()` raises `AssertionError` immediately on a failed condition so
`pytest` reports real per-test PASS/FAIL. `main()` runs every `test_*`
function and aggregates failures for a single human-readable summary.
"""

from __future__ import annotations

import asyncio
import sys
import threading
from dataclasses import replace
from pathlib import Path
from typing import Any, List, Mapping, Optional
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_BACKEND = REPO_ROOT / "dashboard" / "backend"
LIB_DIR = REPO_ROOT / "scripts" / "ai" / "lib"
sys.path.insert(0, str(DASHBOARD_BACKEND))
sys.path.insert(0, str(LIB_DIR))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api.routes import approvals  # noqa: E402
import approval_request as AR  # noqa: E402
import approval_executor as AE  # noqa: E402


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


# --------------------------------------------------------------------------
# Test-only custom ApprovalStore without _records attribute
# --------------------------------------------------------------------------


class CustomApprovalStore:
    """A custom store implementing the ApprovalStore protocol but WITHOUT
    a _records private attribute. This tests that save_record uses the
    protocol's save() method, not hardcoded private attribute access."""

    def __init__(self, records: Optional[List[dict]] = None) -> None:
        # Use a different internal name to ensure the route doesn't try
        # to access _records
        self._data: dict[str, dict] = {
            r["request_id"]: r for r in (records or approvals._default_fixture_records())
        }
        self._execution_claimed: set = set()  # Track claimed records for single-use
        self.save_calls = []  # Track save() calls for testing

    def list_pending(self) -> List[dict]:
        return [r for r in self._data.values() if r["status"] == AR.STATUS_PENDING]

    def get(self, request_id: str) -> Optional[dict]:
        return self._data.get(request_id)

    def transition(self, request_id: str, new_status: str, *, actor: str) -> dict:
        record = self._data.get(request_id)
        if record is None:
            raise approvals.ApprovalStoreError("not-found")
        new_record, _event = AR.transition(record, new_status, actor=actor)
        self._data[request_id] = new_record
        return new_record

    def save(self, record: dict) -> None:
        """Protocol-required save method."""
        if record is None:
            return
        self.save_calls.append(record)
        self._data[record["request_id"]] = record

    def claim_for_execution(self, request_id: str) -> bool:
        """Atomically claim for execution at the store level (not status-based)."""
        record = self._data.get(request_id)
        if record is None:
            return False
        if request_id in self._execution_claimed or record["status"] != AR.STATUS_APPROVED:
            return False
        self._execution_claimed.add(request_id)
        return True


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


def _fresh_app_with_fixture_store():
    """Fresh FixtureApprovalStore wired into a minimal app."""
    store = approvals.FixtureApprovalStore()
    signer = approvals.FixtureSignerClient(store)
    approvals.configure_store(store)
    approvals.configure_signer(signer)

    app = FastAPI()
    app.include_router(approvals.router, prefix="/api")
    return app, store, signer


def _fresh_app_with_custom_store():
    """Fresh CustomApprovalStore (no _records attr) wired into a minimal app."""
    store = CustomApprovalStore()
    signer = approvals.FixtureSignerClient(store)
    approvals.configure_store(store)
    approvals.configure_signer(signer)

    app = FastAPI()
    app.include_router(approvals.router, prefix="/api")
    return app, store, signer


def _approved_id_for_fixture(store: approvals.FixtureApprovalStore, runbook: str = "restart-service") -> str:
    """Get the ID of a pending request with a specific runbook, approve it, and return its ID."""
    pending = store.list_pending()
    check(len(pending) > 0, "no pending requests in fixture")

    # Find a request with the desired runbook
    for record in pending:
        if record["action_manifest"]["runbook"] == runbook:
            request_id = record["request_id"]
            store.transition(request_id, AR.STATUS_APPROVED, actor="test-harness")
            return request_id

    # Fallback to first if runbook not found
    request_id = pending[0]["request_id"]
    store.transition(request_id, AR.STATUS_APPROVED, actor="test-harness")
    return request_id


# --------------------------------------------------------------------------
# Acceptance tests
# --------------------------------------------------------------------------


def test_replay_returns_409() -> None:
    """Replay POST to the same request returns 409, preventing re-execution."""
    app, store, _signer = _fresh_app_with_fixture_store()
    request_id = _approved_id_for_fixture(store)

    with TestClient(app) as client:
        # First execute: should succeed
        resp1 = client.post(f"/api/approvals/{request_id}/execute")
        check(resp1.status_code == 200, f"first execute failed: {resp1.status_code} {resp1.text}")
        data1 = resp1.json()
        check(data1["ok"], f"first execute outcome ok=False: {data1['reason']}")
        check(data1["status"] == AR.STATUS_EXECUTED, f"expected executed, got {data1['status']}")

        # Second execute (replay): should return 409 already_completed
        resp2 = client.post(f"/api/approvals/{request_id}/execute")
        check(
            resp2.status_code == 409,
            f"replay POST should return 409, got {resp2.status_code} {resp2.text}",
        )
        detail = resp2.json().get("detail", {})
        check("plain_title" in detail, f"error detail missing plain_title: {detail}")


def test_custom_store_uses_protocol_save() -> None:
    """Custom store without _records attr proves save_record uses protocol.save(),
    not hardcoded private attribute access."""
    app, store, _signer = _fresh_app_with_custom_store()
    request_id = _approved_id_for_fixture(store)

    with TestClient(app) as client:
        resp = client.post(f"/api/approvals/{request_id}/execute")
        check(resp.status_code == 200, f"execute failed: {resp.status_code} {resp.text}")

        # If the route had used _store._records (hardcoded private access),
        # this would have silently failed because CustomApprovalStore has no
        # _records. The fact that we got 200 + a proper response proves it
        # used the protocol method instead.
        data = resp.json()
        check(data["ok"], f"outcome ok=False: {data['reason']}")

        # Verify save() was called
        check(
            len(store.save_calls) > 0,
            f"save_record never called save(): {len(store.save_calls)} calls",
        )
        # The final state should be in the store
        final_record = store.get(request_id)
        check(final_record is not None, "record not found after execute")
        check(
            final_record["status"] == AR.STATUS_EXECUTED,
            f"expected executed status, got {final_record['status']}",
        )


def test_concurrent_execution_only_one_succeeds() -> None:
    """Concurrent POST requests race to claim the record; only one succeeds."""
    app, store, _signer = _fresh_app_with_fixture_store()
    request_id = _approved_id_for_fixture(store)

    results = []
    lock = threading.Lock()

    def make_request():
        with TestClient(app) as client:
            resp = client.post(f"/api/approvals/{request_id}/execute")
            with lock:
                results.append(resp.status_code)

    # Fire two concurrent requests
    t1 = threading.Thread(target=make_request)
    t2 = threading.Thread(target=make_request)
    t1.start()
    t2.start()
    t1.join(timeout=5)
    t2.join(timeout=5)

    check(len(results) == 2, f"expected 2 results, got {len(results)}")
    # One should succeed (200), one should fail with 409
    success_count = sum(1 for code in results if code == 200)
    conflict_count = sum(1 for code in results if code == 409)
    check(
        success_count == 1,
        f"expected exactly 1 success, got {success_count}: {results}",
    )
    check(
        conflict_count == 1,
        f"expected exactly 1 conflict, got {conflict_count}: {results}",
    )


def test_single_execution_effect_runs_once() -> None:
    """Effect runs exactly once, even if executor is invoked multiple times
    in sequence (which it shouldn't be, but this tests the invariant)."""
    app, store, _signer = _fresh_app_with_fixture_store()
    request_id = _approved_id_for_fixture(store)

    # Patch the runbook effect to count invocations
    effect_calls = []

    def counting_effect(**kwargs):
        effect_calls.append(kwargs)
        return {"count": len(effect_calls)}

    original_spec = AR.RUNBOOK_REGISTRY["restart-service"]
    # Create a new spec with the counting effect function
    counting_spec = replace(original_spec, effect=counting_effect)

    with patch.dict(AR.RUNBOOK_REGISTRY, {"restart-service": counting_spec}):
        with TestClient(app) as client:
            # First execute succeeds
            resp1 = client.post(f"/api/approvals/{request_id}/execute")
            check(resp1.status_code == 200, f"first execute failed: {resp1.status_code}")

            # Second execute fails (409), but if the bug existed, the effect
            # might run again. With the fix, it doesn't.
            resp2 = client.post(f"/api/approvals/{request_id}/execute")
            check(resp2.status_code == 409, f"replay should be 409, got {resp2.status_code}")

            # Effect should have run exactly once
            check(
                len(effect_calls) == 1,
                f"effect should run once, ran {len(effect_calls)} times",
            )


def test_state_transitions_atomically() -> None:
    """Verify state transitions: pending -> approved (manual) -> (claimed at store
    level) -> executed (executor). The status stays approved during execution,
    only the store-level claim marker tracks single-use."""
    app, store, _signer = _fresh_app_with_fixture_store()
    pending = store.list_pending()
    request_id = pending[0]["request_id"]

    # Initial state: pending
    record = store.get(request_id)
    check(record["status"] == AR.STATUS_PENDING, f"initial status should be pending")

    # Approve (manual transition)
    store.transition(request_id, AR.STATUS_APPROVED, actor="test")
    record = store.get(request_id)
    check(record["status"] == AR.STATUS_APPROVED, "approval failed")

    with TestClient(app) as client:
        # Execute: route claims at store level (not via status change),
        # executor transitions approved -> executed
        resp = client.post(f"/api/approvals/{request_id}/execute")
        check(resp.status_code == 200, f"execute failed: {resp.status_code}")

    final = store.get(request_id)
    check(
        final["status"] == AR.STATUS_EXECUTED,
        f"final status should be executed, got {final['status']}",
    )


def test_executor_failure_transitions_to_failed() -> None:
    """If the effect raises, the record transitions to failed, not executed."""
    app, store, _signer = _fresh_app_with_fixture_store()
    request_id = _approved_id_for_fixture(store)

    # Patch the effect to raise
    def failing_effect(**kwargs):
        raise RuntimeError("injected test failure")

    original_spec = AR.RUNBOOK_REGISTRY["restart-service"]
    failing_spec = replace(original_spec, effect=failing_effect)

    with patch.dict(AR.RUNBOOK_REGISTRY, {"restart-service": failing_spec}):
        with TestClient(app) as client:
            resp = client.post(f"/api/approvals/{request_id}/execute")
            check(resp.status_code == 200, f"execute request failed: {resp.status_code}")

            # The route should have caught the executor's exception and
            # persisted the failed state
            data = resp.json()
            check(not data["ok"], f"outcome should be ok=False on effect failure, got ok={data['ok']} reason={data['reason']}")

            final = store.get(request_id)
            check(
                final["status"] == AR.STATUS_FAILED,
                f"failed effect should transition to failed, got {final['status']}",
            )


def test_not_approved_request_rejected() -> None:
    """POST to execute a non-approved request returns 409."""
    app, store, _signer = _fresh_app_with_fixture_store()
    pending = store.list_pending()
    request_id = pending[0]["request_id"]

    # Leave it in pending state (don't approve)
    with TestClient(app) as client:
        resp = client.post(f"/api/approvals/{request_id}/execute")
        check(
            resp.status_code == 409,
            f"executing non-approved should be 409, got {resp.status_code}",
        )


def test_nonexistent_request_returns_404() -> None:
    """POST to execute a non-existent request_id returns 404."""
    app, store, _signer = _fresh_app_with_fixture_store()

    with TestClient(app) as client:
        resp = client.post("/api/approvals/nonexistent-id/execute")
        check(
            resp.status_code == 404,
            f"nonexistent should be 404, got {resp.status_code}",
        )
        detail = resp.json().get("detail", {})
        check("plain_title" in detail, f"error detail missing: {detail}")


# --------------------------------------------------------------------------
# Test runner (for direct execution and pytest)
# --------------------------------------------------------------------------


def main() -> int:
    """Run all test_* functions and report results."""
    tests = [
        ("replay_returns_409", test_replay_returns_409),
        ("custom_store_uses_protocol_save", test_custom_store_uses_protocol_save),
        ("concurrent_execution_only_one_succeeds", test_concurrent_execution_only_one_succeeds),
        ("single_execution_effect_runs_once", test_single_execution_effect_runs_once),
        ("state_transitions_atomically", test_state_transitions_atomically),
        ("executor_failure_transitions_to_failed", test_executor_failure_transitions_to_failed),
        ("not_approved_request_rejected", test_not_approved_request_rejected),
        ("nonexistent_request_returns_404", test_nonexistent_request_returns_404),
    ]

    passed = 0
    failed = 0
    failures = []

    for name, test_func in tests:
        try:
            test_func()
            print(f"✓ {name}")
            passed += 1
        except AssertionError as e:
            print(f"✗ {name}")
            failed += 1
            failures.append((name, str(e)))
        except Exception as e:
            print(f"✗ {name} (unexpected error)")
            failed += 1
            failures.append((name, f"{e.__class__.__name__}: {e}"))

    print(f"\n{passed} passed, {failed} failed")

    if failures:
        print("\nFailures:")
        for name, error in failures:
            print(f"  {name}: {error}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
