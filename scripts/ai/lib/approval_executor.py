"""Audited executor for approved `aq.approval-request.v1` records — Approval
Control Plane P0 (fail-closed, in-memory/stub effects only).

Implements the audited action contract from
`.agents/plans/approval-control-plane/ACP-P0-DESIGN-20260816.md` §"The
audited action contract (executor)": load the record by id, re-validate +
recompute its canonical hash and ABORT before any effect runs if that hash
differs from the stored `binding.canonical_hash` (tamper/drift -> fail
closed), resolve `action_manifest.runbook` in the registry, execute ONLY the
typed `params` present in the hashed record (no runtime injection — review
finding #9; there is no parameter argument to this module's entrypoint other
than the record itself), and transition `approved -> executed` or
`approved -> failed` as a final audited event. Every step appends an
audited event to the returned event chain — nothing runs outside it
(audit-completeness).

For P0, "approval" is a trusted test stub: this module takes NO WebAuthn
assertion and performs NO signature verification of its own. It trusts
whatever `load_record` returns; the caller (a test, later a real confined
service) is responsible for only ever handing this module a record whose
`status` is already `"approved"` (produced via `approval_request.transition`
in P0; produced by a real WebAuthn-verified approval in P1). The contract
below — load, re-validate, recompute-hash-or-abort, resolve, execute,
transition — is exactly what P1 keeps; only how a record reaches `approved`
changes.

Runbook execution is the P0 in-memory stub registry
(`approval_request.RUNBOOK_REGISTRY[...].effect`), NOT the real audited AQ
action path — no WebAuthn, no key signing, no Nix, no subprocess, no
network. A later slice swaps each registry entry's `effect` for a call into
the real path; this module's contract does not change when that happens.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional

_LIB = os.path.dirname(os.path.abspath(__file__))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import approval_request as AR  # noqa: E402

# --------------------------------------------------------------------------
# Typed, safe-to-log outcome reasons
# --------------------------------------------------------------------------

REASON_EXECUTED = "executed"
REASON_NOT_FOUND = "request-not-found"
REASON_INVALID_RECORD = "record-invalid"
REASON_NOT_APPROVED = "record-not-approved"
REASON_TAMPER_DETECTED = "canonical-hash-mismatch"
REASON_UNKNOWN_RUNBOOK = "unknown-runbook"
REASON_EFFECT_FAILED = "effect-raised"


@dataclass(frozen=True)
class ExecutionOutcome:
    """Typed, total result of `execute_request`. `ok=True` iff
    `reason == REASON_EXECUTED`. `events` is the full ordered audit chain
    (never empty — even the earliest abort emits at least one event).
    `record` is the final record state if one was loaded (`None` only for
    `REASON_NOT_FOUND`); its `status` reflects any transition that actually
    happened (`failed`/`executed`), or is unchanged from the input for an
    abort that happened before any transition was attempted."""

    ok: bool
    reason: str
    events: tuple
    record: Optional[dict]


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _emit(events: list, moment: datetime, event_type: str, request_id: str, **payload: Any) -> dict:
    event = {"event": event_type, "request_id": request_id, "at": _iso(moment), **payload}
    events.append(event)
    return event


def execute_request(
    request_id: str,
    *,
    load_record: Callable[[str], Optional[Mapping[str, Any]]],
    save_record: Callable[[dict], None],
    actor: str = "audited-executor",
    now: Optional[datetime] = None,
) -> ExecutionOutcome:
    """Run the audited executor contract for `request_id`.

    `load_record`/`save_record` are the P0 trusted stubs standing in for the
    confined record store P1 provides (design invariant 6) — this module
    has no filesystem/service opinion of its own. Total function: never
    raises (any internal fault is caught and reported as an aborted
    outcome), never runs an effect outside the returned event chain, never
    executes anything if the canonical hash does not match, never executes
    anything on a record that is not already `status == "approved"`."""
    events: list[dict] = []
    moment = now or datetime.now(timezone.utc)

    try:
        record = load_record(request_id)
        if record is None:
            _emit(events, moment, "execution_aborted", request_id, reason=REASON_NOT_FOUND)
            return ExecutionOutcome(False, REASON_NOT_FOUND, tuple(events), None)
        _emit(events, moment, "record_loaded", request_id)

        verdict = AR.validate(record)
        if not verdict.ok:
            _emit(
                events, moment, "execution_aborted", request_id,
                reason=REASON_INVALID_RECORD, detail=verdict.reason,
            )
            return ExecutionOutcome(False, REASON_INVALID_RECORD, tuple(events), record)
        _emit(events, moment, "record_validated", request_id)

        if record["status"] != AR.STATUS_APPROVED:
            _emit(
                events, moment, "execution_aborted", request_id,
                reason=REASON_NOT_APPROVED, detail=record["status"],
            )
            return ExecutionOutcome(False, REASON_NOT_APPROVED, tuple(events), record)

        # The load-bearing check: recompute the canonical hash over the
        # record's content fields and compare to what was bound at creation
        # time. ANY divergence — a hand-edited param, a swapped runbook, a
        # forged declared_effects list — aborts here, before the runbook is
        # even resolved, let alone executed (review finding #9: no runtime
        # param injection is possible because the ONLY params this function
        # ever sees are the ones already inside this hash-verified record).
        recomputed_hash = AR.compute_hash(record)
        stored_hash = record["binding"]["canonical_hash"]
        if recomputed_hash != stored_hash:
            _emit(
                events, moment, "tamper_detected", request_id,
                expected=stored_hash, recomputed=recomputed_hash,
            )
            failed_record, transition_event = AR.transition(
                record, AR.STATUS_FAILED, actor=actor, now=moment
            )
            events.append(transition_event)
            save_record(failed_record)
            return ExecutionOutcome(False, REASON_TAMPER_DETECTED, tuple(events), failed_record)
        _emit(events, moment, "hash_verified", request_id, canonical_hash=stored_hash)

        manifest = record["action_manifest"]
        runbook = manifest["runbook"]
        spec = AR.RUNBOOK_REGISTRY.get(runbook)
        if spec is None:  # pragma: no cover - already excluded by validate() above; defense-in-depth
            _emit(
                events, moment, "execution_aborted", request_id,
                reason=REASON_UNKNOWN_RUNBOOK, detail=runbook,
            )
            failed_record, transition_event = AR.transition(
                record, AR.STATUS_FAILED, actor=actor, now=moment
            )
            events.append(transition_event)
            save_record(failed_record)
            return ExecutionOutcome(False, REASON_UNKNOWN_RUNBOOK, tuple(events), failed_record)
        _emit(events, moment, "runbook_resolved", request_id, runbook=runbook)

        params = manifest["params"]
        try:
            effect_result = spec.effect(**params)
        except Exception as exc:  # noqa: BLE001 - a raising stub effect must fail closed, never propagate
            _emit(
                events, moment, "effect_failed", request_id,
                runbook=runbook, error=exc.__class__.__name__,
            )
            failed_record, transition_event = AR.transition(
                record, AR.STATUS_FAILED, actor=actor, now=moment
            )
            events.append(transition_event)
            save_record(failed_record)
            return ExecutionOutcome(False, REASON_EFFECT_FAILED, tuple(events), failed_record)
        _emit(events, moment, "effect_executed", request_id, runbook=runbook, result=effect_result)

        executed_record, transition_event = AR.transition(
            record, AR.STATUS_EXECUTED, actor=actor, now=moment
        )
        events.append(transition_event)
        save_record(executed_record)
        return ExecutionOutcome(True, REASON_EXECUTED, tuple(events), executed_record)
    except Exception as exc:  # noqa: BLE001 - total function, never raises into the caller
        _emit(
            events, moment, "execution_aborted", request_id,
            reason=AR.REJECT_INTERNAL, detail=f"unhandled:{exc.__class__.__name__}",
        )
        return ExecutionOutcome(False, AR.REJECT_INTERNAL, tuple(events), None)
