#!/usr/bin/env python3
"""Acceptance tests for the Approval Control Plane P0 record + executor
(`scripts/ai/lib/approval_request.py`, `scripts/ai/lib/approval_executor.py`).

Covers the 7 validation goals from
`.agents/plans/approval-control-plane/ACP-P0-DESIGN-20260816.md`
§"Validation goals": golden-canonical, privacy-leak, closed-schema,
bounded-action, state-machine, executor-tamper, audit-completeness. Fully
offline: no network, no filesystem beyond an in-memory dict store standing
in for the P1 confined record store (design invariant 6).

`check()` raises `AssertionError` immediately on a failed condition (unlike
some sibling test files in this directory that only *collect* failures into
a list) so that running this file under `pytest` reports a real per-test
PASS/FAIL rather than silently green-lighting a collected-but-never-asserted
failure. `main()` still runs every `test_*` function and aggregates
failures for a single human-readable summary when run directly.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "scripts" / "ai" / "lib"
sys.path.insert(0, str(LIB_DIR))

import approval_executor as AE  # noqa: E402
import approval_request as AR  # noqa: E402

# --------------------------------------------------------------------------
# Golden fixture — fixed request_id/created_at/created_by/runbook/params so
# `compute_hash` is deterministic across runs and machines.
# --------------------------------------------------------------------------

GOLDEN_REQUEST_ID = "01J00000000000000000000000"
GOLDEN_CREATED_AT = "2026-08-16T00:00:00Z"
GOLDEN_CREATED_BY = "aq-loop"
GOLDEN_RUNBOOK = "activate-signer-service"
GOLDEN_PARAMS = {"service": "c2-scheduler-context-issuer"}
GOLDEN_TARGET_FILES = ["config/aqos/signer-service.nix"]
GOLDEN_GRANT_SUBJECT = "c2-ACTIVATE"
GOLDEN_DESIGN_SHA256 = "a" * 64

# Pinned cross-run/cross-machine golden hash for the fixture above. Computed
# once from `canonicalize()`'s deterministic output; any change to the
# canonicalization scheme, the runbook registry entry, or the fixture
# values below MUST update this constant deliberately (it is the whole
# point of the golden-canonical test to catch an accidental drift here).
GOLDEN_CANONICAL_HASH = "b52bea91b5462469b884ca3fd0260d68ecbf18003fd4cdffee44e861aed37819"


def _fixture_record() -> dict:
    return AR.create_request(
        request_id=GOLDEN_REQUEST_ID,
        created_at=GOLDEN_CREATED_AT,
        created_by=GOLDEN_CREATED_BY,
        runbook=GOLDEN_RUNBOOK,
        params=dict(GOLDEN_PARAMS),
        target_files=list(GOLDEN_TARGET_FILES),
        grant_subject=GOLDEN_GRANT_SUBJECT,
        design_sha256=GOLDEN_DESIGN_SHA256,
    )


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def expect_raises(fn, exc_type, reason: str = None, label: str = "") -> None:
    try:
        fn()
    except exc_type as exc:
        if reason is not None:
            check(
                getattr(exc, "reason", None) == reason,
                f"{label}: expected reason {reason!r}, got {getattr(exc, 'reason', None)!r}",
            )
        return
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(f"{label}: expected {exc_type.__name__}, got {type(exc).__name__}: {exc}") from exc
    raise AssertionError(f"{label}: expected {exc_type.__name__}, nothing raised")


# --------------------------------------------------------------------------
# 1. golden-canonical
# --------------------------------------------------------------------------


def test_golden_canonical() -> None:
    record = _fixture_record()
    check(
        record["binding"]["canonical_hash"] == GOLDEN_CANONICAL_HASH,
        f"golden hash drift: got {record['binding']['canonical_hash']}",
    )
    check(
        AR.compute_hash(record) == GOLDEN_CANONICAL_HASH,
        "compute_hash() recomputation does not match the stored binding hash",
    )

    # Cross-run determinism: rebuild the identical fixture in a fresh call
    # and confirm byte-identical canonical output + hash.
    record_again = _fixture_record()
    check(
        AR.canonicalize(record) == AR.canonicalize(record_again),
        "canonicalize() is not deterministic across repeated builds",
    )
    check(record["binding"]["canonical_hash"] == record_again["binding"]["canonical_hash"], "hash not stable across repeated builds")

    # Field-order independence: shuffle top-level and nested key order and
    # confirm the canonical bytes are unaffected (sort_keys=True).
    shuffled = {k: record[k] for k in reversed(list(record.keys()))}
    shuffled["action_manifest"] = {k: record["action_manifest"][k] for k in reversed(list(record["action_manifest"].keys()))}
    check(
        AR.canonicalize(record) == AR.canonicalize(shuffled),
        "canonicalize() is sensitive to key insertion order",
    )


# --------------------------------------------------------------------------
# 2. privacy-leak
# --------------------------------------------------------------------------


def test_request_id_binding() -> None:
    """ACP-P1 review finding 2 (CRITICAL, verified): the canonical hash binds the
    immutable `request_id`, so two content-identical requests with different ids
    do NOT share a hash — an owner signature over one cannot be replayed against a
    content-identical sibling. Also asserts the preserved invariant: a legal
    `status` transition does NOT change the hash (`status` stays excluded)."""
    a = AR.create_request(
        request_id="01J0000000000000000000000A", created_by="x",
        runbook="restart-service", params={"service": "switchboard"})
    b = AR.create_request(
        request_id="01J0000000000000000000000B", created_by="x",
        runbook="restart-service", params={"service": "switchboard"})
    check(a["summary"] == b["summary"] and a["action_manifest"] == b["action_manifest"],
          "fixture content is not actually identical")
    check(AR.compute_hash(a) != AR.compute_hash(b),
          "content-identical requests with different request_id share a canonical_hash (cross-request signature reuse)")
    check(AR.validate(a).ok and AR.validate(b).ok, "instance-bound records failed validate()")
    approved, _ = AR.transition(a, AR.STATUS_APPROVED, actor="owner")
    check(AR.compute_hash(approved) == AR.compute_hash(a),
          "a legal status transition changed the canonical_hash (status must stay excluded)")


def test_privacy_leak() -> None:
    clean = "Activate the c2-scheduler-context-issuer service"
    check(AR._scan_privacy_leak(clean) is None, "clean summary text flagged as a leak")

    leaks = {
        AR.LEAK_HEX64: "digest " + ("a" * 64),
        AR.LEAK_RUN_SECRETS: "reads /run/secrets/aq-lease-signing-key",
        AR.LEAK_FILESYSTEM_PATH: "writes config/aqos/lease-signer-keys.json under /etc/aqos/keys",
        AR.LEAK_KEY_ID: "rotates key_id abc123",
        AR.LEAK_SOCKET_PATH: "dials unix:///run/aq/epoch.sock",
        AR.LEAK_SHA256_LITERAL: "verifies the sha256 digest",
    }
    for expected_reason, text in leaks.items():
        got = AR._scan_privacy_leak(text)
        check(got == expected_reason, f"privacy scan for {text!r}: expected {expected_reason}, got {got}")

    # End-to-end: a record whose summary.title was hand-edited to leak a
    # hex-64 digest is rejected by validate() with a LEAK_* reason, even
    # though every other field is otherwise well-formed.
    record = _fixture_record()
    leaked = copy.deepcopy(record)
    leaked["summary"]["title"] = "Rotate key " + ("b" * 64)
    verdict = AR.validate(leaked)
    check(not verdict.ok, "record with a hex-64 leak in summary.title was accepted")
    check(verdict.reason == AR.LEAK_HEX64, f"expected {AR.LEAK_HEX64}, got {verdict.reason}")

    leaked_path = copy.deepcopy(record)
    leaked_path["summary"]["why"] = "reads /run/secrets/aq-lease-signing-key first"
    verdict = AR.validate(leaked_path)
    check(not verdict.ok, "record with a /run/secrets leak in summary.why was accepted")
    check(verdict.reason == AR.LEAK_RUN_SECRETS, f"expected {AR.LEAK_RUN_SECRETS}, got {verdict.reason}")


# --------------------------------------------------------------------------
# 3. closed-schema
# --------------------------------------------------------------------------


def test_closed_schema() -> None:
    record = _fixture_record()

    unknown_top = copy.deepcopy(record)
    unknown_top["smuggled_field"] = "nope"
    verdict = AR.validate(unknown_top)
    check(not verdict.ok and verdict.reason == AR.REJECT_TOP_LEVEL_SCHEMA, "unknown top-level key was accepted")

    missing_top = copy.deepcopy(record)
    del missing_top["technical_trail"]
    verdict = AR.validate(missing_top)
    check(not verdict.ok and verdict.reason == AR.REJECT_TOP_LEVEL_SCHEMA, "missing top-level key was accepted")

    wrong_type_status = copy.deepcopy(record)
    wrong_type_status["status"] = 123
    verdict = AR.validate(wrong_type_status)
    check(not verdict.ok and verdict.reason == AR.REJECT_UNKNOWN_STATUS, "non-string status was accepted")

    wrong_type_summary = copy.deepcopy(record)
    wrong_type_summary["summary"] = "not a mapping"
    verdict = AR.validate(wrong_type_summary)
    check(not verdict.ok and verdict.reason == AR.REJECT_SUMMARY_SCHEMA, "non-dict summary was accepted")

    unknown_summary_key = copy.deepcopy(record)
    unknown_summary_key["summary"]["extra"] = "nope"
    verdict = AR.validate(unknown_summary_key)
    check(not verdict.ok and verdict.reason == AR.REJECT_SUMMARY_SCHEMA, "unknown summary key was accepted")

    unknown_manifest_key = copy.deepcopy(record)
    unknown_manifest_key["action_manifest"]["extra"] = "nope"
    verdict = AR.validate(unknown_manifest_key)
    check(not verdict.ok and verdict.reason == AR.REJECT_ACTION_MANIFEST_SCHEMA, "unknown action_manifest key was accepted")

    unknown_trail_key = copy.deepcopy(record)
    unknown_trail_key["technical_trail"]["extra"] = "nope"
    verdict = AR.validate(unknown_trail_key)
    check(not verdict.ok and verdict.reason == AR.REJECT_TECHNICAL_TRAIL_SCHEMA, "unknown technical_trail key was accepted")

    unknown_binding_key = copy.deepcopy(record)
    unknown_binding_key["binding"]["extra"] = "nope"
    verdict = AR.validate(unknown_binding_key)
    check(not verdict.ok and verdict.reason == AR.REJECT_BINDING_SCHEMA, "unknown binding key was accepted")


# --------------------------------------------------------------------------
# 4. bounded-action
# --------------------------------------------------------------------------


def test_bounded_action() -> None:
    record = _fixture_record()

    unregistered = copy.deepcopy(record)
    unregistered["action_manifest"]["runbook"] = "delete-everything"
    verdict = AR.validate(unregistered)
    check(not verdict.ok and verdict.reason == AR.REJECT_UNKNOWN_RUNBOOK, "unregistered runbook was accepted")
    expect_raises(
        lambda: AR.create_request(
            request_id="x", created_by="t", runbook="delete-everything", params={"service": "x"}
        ),
        AR.ApprovalValidationError,
        AR.REJECT_UNKNOWN_RUNBOOK,
        "create_request unregistered runbook",
    )

    expect_raises(
        lambda: AR.create_request(request_id="x", created_by="t", runbook=GOLDEN_RUNBOOK, params={}),
        AR.ApprovalValidationError,
        AR.REJECT_PARAM_KEYS,
        "create_request missing required param",
    )
    expect_raises(
        lambda: AR.create_request(
            request_id="x", created_by="t", runbook=GOLDEN_RUNBOOK,
            params={"service": "c2-scheduler-context-issuer", "extra": "nope"},
        ),
        AR.ApprovalValidationError,
        AR.REJECT_PARAM_KEYS,
        "create_request unknown extra param",
    )
    expect_raises(
        lambda: AR.create_request(
            request_id="x", created_by="t", runbook=GOLDEN_RUNBOOK, params={"service": "BAD NAME!"}
        ),
        AR.ApprovalValidationError,
        AR.REJECT_PARAM_PATTERN,
        "create_request param fails pattern",
    )
    expect_raises(
        lambda: AR.create_request(
            request_id="x", created_by="t", runbook=GOLDEN_RUNBOOK, params={"service": 12345}
        ),
        AR.ApprovalValidationError,
        AR.REJECT_PARAM_TYPE,
        "create_request param wrong type",
    )

    tampered_effects = copy.deepcopy(record)
    tampered_effects["action_manifest"]["declared_effects"] = tampered_effects["action_manifest"]["declared_effects"] + [
        "delete-everything"
    ]
    verdict = AR.validate(tampered_effects)
    check(
        not verdict.ok and verdict.reason == AR.REJECT_DECLARED_EFFECTS_MISMATCH,
        "forged declared_effects entry was accepted",
    )

    freeform_summary = copy.deepcopy(record)
    freeform_summary["summary"]["title"] = "Totally different free-text title"
    verdict = AR.validate(freeform_summary)
    check(
        not verdict.ok and verdict.reason == AR.REJECT_SUMMARY_MISMATCH,
        "hand-written summary.title diverging from the runbook template was accepted",
    )


# --------------------------------------------------------------------------
# 5. state-machine
# --------------------------------------------------------------------------


def test_state_machine() -> None:
    all_illegal = [
        (AR.STATUS_PENDING, AR.STATUS_EXECUTED),
        (AR.STATUS_PENDING, AR.STATUS_FAILED),
        (AR.STATUS_PENDING, AR.STATUS_PENDING),
        (AR.STATUS_APPROVED, AR.STATUS_DENIED),
        (AR.STATUS_APPROVED, AR.STATUS_PENDING),
        (AR.STATUS_APPROVED, AR.STATUS_APPROVED),
        (AR.STATUS_APPROVED, AR.STATUS_EXPIRED),
        (AR.STATUS_EXECUTED, AR.STATUS_FAILED),
        (AR.STATUS_EXECUTED, AR.STATUS_APPROVED),
        (AR.STATUS_DENIED, AR.STATUS_APPROVED),
        (AR.STATUS_FAILED, AR.STATUS_EXECUTED),
        (AR.STATUS_EXPIRED, AR.STATUS_APPROVED),
    ]
    for from_status, to_status in all_illegal:
        record = _fixture_record()
        record["status"] = from_status
        expect_raises(
            lambda r=record, t=to_status: AR.transition(r, t, actor="test"),
            AR.ApprovalStateError,
            AR.REJECT_ILLEGAL_TRANSITION,
            f"illegal transition {from_status}->{to_status}",
        )

    # unknown target status string entirely
    record = _fixture_record()
    expect_raises(
        lambda: AR.transition(record, "sideways", actor="test"),
        AR.ApprovalStateError,
        AR.REJECT_ILLEGAL_TRANSITION,
        "transition to an unknown status string",
    )

    # legal happy path: pending -> approved -> executed (state only; the
    # executor contract is exercised separately below)
    record = _fixture_record()
    approved, evt1 = AR.transition(record, AR.STATUS_APPROVED, actor="owner-webauthn-stub")
    check(approved["status"] == AR.STATUS_APPROVED, "approved record did not carry the new status")
    check(evt1["from_status"] == AR.STATUS_PENDING and evt1["to_status"] == AR.STATUS_APPROVED, "approval event shape wrong")
    check(
        approved["binding"]["canonical_hash"] == record["binding"]["canonical_hash"],
        "canonical_hash changed across a legal status transition",
    )
    executed, evt2 = AR.transition(approved, AR.STATUS_EXECUTED, actor="audited-executor")
    check(executed["status"] == AR.STATUS_EXECUTED, "executed record did not carry the new status")
    check(evt2["from_status"] == AR.STATUS_APPROVED and evt2["to_status"] == AR.STATUS_EXECUTED, "executed event shape wrong")

    # legal: pending -> denied (terminal)
    record = _fixture_record()
    denied, evt3 = AR.transition(record, AR.STATUS_DENIED, actor="owner-webauthn-stub")
    check(denied["status"] == AR.STATUS_DENIED, "denied record did not carry the new status")
    check(evt3["to_status"] == AR.STATUS_DENIED, "denial event shape wrong")

    # legal: pending -> expired (terminal)
    record = _fixture_record()
    expired, evt4 = AR.transition(record, AR.STATUS_EXPIRED, actor="ttl-sweep")
    check(expired["status"] == AR.STATUS_EXPIRED, "expired record did not carry the new status")
    check(evt4["to_status"] == AR.STATUS_EXPIRED, "expiry event shape wrong")

    # legal: approved -> failed (terminal, executor error path)
    record = _fixture_record()
    approved, _ = AR.transition(record, AR.STATUS_APPROVED, actor="owner-webauthn-stub")
    failed, evt5 = AR.transition(approved, AR.STATUS_FAILED, actor="audited-executor")
    check(failed["status"] == AR.STATUS_FAILED, "failed record did not carry the new status")
    check(evt5["to_status"] == AR.STATUS_FAILED, "failure event shape wrong")

    # an invalid input record refuses to transition at all
    invalid = _fixture_record()
    invalid["summary"]["title"] = "leak " + ("c" * 64)
    expect_raises(
        lambda: AR.transition(invalid, AR.STATUS_APPROVED, actor="test"),
        AR.ApprovalStateError,
        AR.REJECT_INVALID_RECORD,
        "transition of an already-invalid record",
    )


# --------------------------------------------------------------------------
# 6. executor-tamper
# --------------------------------------------------------------------------


def _store():
    data: dict = {}

    def load(request_id: str):
        return data.get(request_id)

    def save(record: dict) -> None:
        data[record["request_id"]] = record

    return data, load, save


def test_executor_tamper() -> None:
    # Case A: stored canonical_hash is simply corrupted (bit flip).
    record = _fixture_record()
    approved, _ = AR.transition(record, AR.STATUS_APPROVED, actor="owner-webauthn-stub")
    tampered_hash = copy.deepcopy(approved)
    good_hash = tampered_hash["binding"]["canonical_hash"]
    tampered_hash["binding"]["canonical_hash"] = ("0" if good_hash[0] != "0" else "1") + good_hash[1:]

    data, load, save = _store()
    save(tampered_hash)
    outcome = AE.execute_request(record["request_id"], load_record=load, save_record=save)
    check(not outcome.ok, "corrupted canonical_hash executed instead of aborting")
    check(outcome.reason == AE.REASON_TAMPER_DETECTED, f"expected tamper reason, got {outcome.reason}")
    check(outcome.record["status"] == AR.STATUS_FAILED, "tampered record was not transitioned to failed")
    event_types = [e["event"] for e in outcome.events]
    check("tamper_detected" in event_types, "no tamper_detected event in the audit chain")
    check("effect_executed" not in event_types, "an effect ran despite a canonical_hash mismatch")

    # Case B: params silently swapped post-creation WITHOUT recomputing the
    # hash (the no-runtime-injection scenario — review finding #9). `summary`
    # is ALSO re-rendered for the new params so the record is otherwise
    # fully self-consistent (passes every check `validate()` performs on
    # content shape/semantic binding) — only the stale `canonical_hash`
    # betrays that these params are not the ones the request was bound to.
    # This isolates the hash check from the (already-covered, in
    # `test_bounded_action`) summary/param semantic-binding check.
    record2 = _fixture_record()
    approved2, _ = AR.transition(record2, AR.STATUS_APPROVED, actor="owner-webauthn-stub")
    swapped_params = copy.deepcopy(approved2)
    new_params = {"service": "a-completely-different-service"}
    swapped_params["action_manifest"]["params"] = new_params
    swapped_params["summary"] = AR.render_summary(AR.RUNBOOK_REGISTRY[GOLDEN_RUNBOOK], new_params)
    # canonical_hash intentionally left as the ORIGINAL value — this is
    # exactly what a compromised caller trying to inject different params
    # at execute time would look like.
    check(
        swapped_params["binding"]["canonical_hash"] == approved2["binding"]["canonical_hash"],
        "test setup error: hash should still equal the original",
    )
    check(
        AR.validate(swapped_params).ok,
        "test setup error: self-consistent swapped-params record should pass validate() up to the hash check",
    )

    data2, load2, save2 = _store()
    save2(swapped_params)
    outcome2 = AE.execute_request(record2["request_id"], load_record=load2, save_record=save2)
    check(not outcome2.ok, "swapped params executed instead of aborting")
    check(outcome2.reason == AE.REASON_TAMPER_DETECTED, f"expected tamper reason, got {outcome2.reason}")
    event_types2 = [e["event"] for e in outcome2.events]
    check("effect_executed" not in event_types2, "an effect ran with injected/swapped params")
    check(
        "a-completely-different-service" not in str(outcome2.events),
        "the injected param value leaked into the audit event chain",
    )

    # Non-approved record: executor must not even attempt hash verification
    # or a transition (pending -> failed is not a legal transition).
    pending_record = _fixture_record()
    data3, load3, save3 = _store()
    save3(pending_record)
    outcome3 = AE.execute_request(pending_record["request_id"], load_record=load3, save_record=save3)
    check(not outcome3.ok, "a still-pending record was executed")
    check(outcome3.reason == AE.REASON_NOT_APPROVED, f"expected not-approved reason, got {outcome3.reason}")
    check(outcome3.record["status"] == AR.STATUS_PENDING, "pending record's status was mutated by an aborted execute")

    # Unknown request id: executor aborts cleanly, no record.
    outcome4 = AE.execute_request("does-not-exist", load_record=lambda rid: None, save_record=lambda r: None)
    check(not outcome4.ok and outcome4.reason == AE.REASON_NOT_FOUND, "unknown request_id did not abort not-found")
    check(outcome4.record is None, "not-found outcome carried a record")


# --------------------------------------------------------------------------
# 7. audit-completeness
# --------------------------------------------------------------------------


def test_audit_completeness() -> None:
    record = _fixture_record()
    approved, approval_event = AR.transition(record, AR.STATUS_APPROVED, actor="owner-webauthn-stub")

    data, load, save = _store()
    save(approved)
    outcome = AE.execute_request(record["request_id"], load_record=load, save_record=save)

    check(outcome.ok, f"happy-path execution did not succeed: {outcome.reason}")
    check(outcome.reason == AE.REASON_EXECUTED, f"expected executed reason, got {outcome.reason}")
    check(outcome.record["status"] == AR.STATUS_EXECUTED, "final record status is not executed")

    event_types = [e["event"] for e in outcome.events]
    expected_chain = [
        "record_loaded",
        "record_validated",
        "hash_verified",
        "runbook_resolved",
        "effect_executed",
        "approval_state_transition",
    ]
    check(event_types == expected_chain, f"audit chain shape drift: {event_types}")

    final_transition = outcome.events[-1]
    check(final_transition["from_status"] == AR.STATUS_APPROVED, "final transition did not originate from approved")
    check(final_transition["to_status"] == AR.STATUS_EXECUTED, "final transition did not land on executed")

    effect_event = outcome.events[4]
    check(effect_event["runbook"] == GOLDEN_RUNBOOK, "effect_executed event missing runbook name")
    check(
        effect_event["result"] == {"runbook": GOLDEN_RUNBOOK, "service": GOLDEN_PARAMS["service"], "result": "activated"},
        f"effect_executed result drift: {effect_event['result']}",
    )

    check(load(record["request_id"])["status"] == AR.STATUS_EXECUTED, "save_record did not persist the executed status")

    # every event references the same request_id (no cross-request leakage)
    check(
        all(e["request_id"] == record["request_id"] for e in outcome.events),
        "an audit event referenced a different request_id",
    )


def main() -> int:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    failures = []
    for test in tests:
        try:
            test()
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{test.__name__}: {exc}")
    if failures:
        print(f"FAIL ({len(failures)}):")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print(f"PASS: {len(tests)} approval-request P0 checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
