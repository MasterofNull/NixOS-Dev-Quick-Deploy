#!/usr/bin/env python3
"""Acceptance tests for the Approval Control Plane P3 runbook engine
(`scripts/ai/lib/approval_runbook_engine.py`).

Covers the P3 validation goals from
`.agents/plans/approval-control-plane/ACP-P3-DESIGN-20260816.md` (as folded
into the build task): idempotent-resume, scope-bound, authorized-once,
retry-reauth, fail-closed, audit-chain, no-shell, declaration-coupled. Fully
offline: no network, no live system mutation — a `state` dict stands in for
the real system every STUB atom would otherwise touch, and `MemoryRunLedger`/
`FileRunLedger` (temp-dir backed) stand in for the durable per-run ledger.

`check()` raises `AssertionError` immediately on a failed condition (mirrors
`test-approval-request.py`/`test-approval-signer.py`) so `pytest` reports
real per-test PASS/FAIL. `main()` runs every `test_*` function and aggregates
failures for a single human-readable summary when run directly.
"""

from __future__ import annotations

import inspect
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "scripts" / "ai" / "lib"
sys.path.insert(0, str(LIB_DIR))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat  # noqa: E402

import approval_request as AR  # noqa: E402
import approval_runbook_engine as ARE  # noqa: E402
import approval_signer as AS  # noqa: E402

ENGINE_SOURCE = (LIB_DIR / "approval_runbook_engine.py").read_text(encoding="utf-8")


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


# --------------------------------------------------------------------------
# Fixture helpers
# --------------------------------------------------------------------------


def _keypair():
    private_key = Ed25519PrivateKey.generate()
    public_hex = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    return private_key, public_hex


def _sign(record: dict, private_key: Ed25519PrivateKey) -> str:
    """Produce a valid P1-shaped Ed25519 signature over `record`'s canonical
    hash, using the SAME domain-separated signable bytes
    `approval_signer.verify_execution_authorization` checks against. This
    bypasses the WebAuthn ceremony itself (already covered end-to-end by
    `test-approval-signer.py`); P3 only needs a real signature to exercise
    its own authorization-gating contract."""
    canonical_hash = AR.compute_hash(record)
    return private_key.sign(AS._signable_bytes(canonical_hash)).hex()  # noqa: SLF001 - same-family test reuse


def _authorized_record(*, runbook: str, params: dict, request_id: str, private_key: Ed25519PrivateKey) -> dict:
    record = AR.create_request(request_id=request_id, created_by="test", runbook=runbook, params=params)
    approved, _ = AR.transition(record, AR.STATUS_APPROVED, actor="owner-webauthn-stub")
    return approved


def _make_authorize(record: dict, private_key: Ed25519PrivateKey, public_hex: str, signed_at: datetime, ttl=ARE.DEFAULT_AUTHORIZATION_TTL) -> ARE.AuthorizationCheck:
    signature = _sign(record, private_key)
    return ARE.make_signature_authorization_check(
        signature=signature, owner_public_key=public_hex, signed_at=signed_at, ttl=ttl
    )


def _instrument(steps: tuple, verify_counts: dict, action_counts: dict) -> tuple:
    """Wrap each step's `verify`/`action` with call counters, preserving the
    original behavior exactly. Lets a test assert an atom was (or was NOT)
    actually invoked, independent of what the ledger says."""
    wrapped = []
    for step in steps:
        orig_verify, orig_action, step_id = step.verify, step.action, step.step_id

        def make_verify(fn, sid):
            def v(params, state):
                verify_counts[sid] = verify_counts.get(sid, 0) + 1
                return fn(params, state)
            return v

        def make_action(fn, sid):
            def a(params, state):
                action_counts[sid] = action_counts.get(sid, 0) + 1
                return fn(params, state)
            return a

        wrapped.append(
            ARE.RunbookStepSpec(
                step_id=step.step_id, kind=step.kind, atom=step.atom, effect_name=step.effect_name,
                param_names=step.param_names, verify=make_verify(orig_verify, step_id), action=make_action(orig_action, step_id),
            )
        )
    return tuple(wrapped)


# --------------------------------------------------------------------------
# 1. idempotent-resume
# --------------------------------------------------------------------------


def test_idempotent_resume_ledger_driven() -> None:
    """A run interrupted after step k (a genuine step failure), retried,
    completes without re-invoking the already-applied steps' actions."""
    private_key, public_hex = _keypair()
    request_id = "01RUN-IDEMP-A"
    signed_at = datetime.now(timezone.utc)
    record = _authorized_record(runbook="emit-grant", params={"grant_subject": "svc-a"}, request_id=request_id, private_key=private_key)
    authorize = _make_authorize(record, private_key, public_hex, signed_at)

    action_counts: dict = {}
    verify_counts: dict = {}
    steps = _instrument(ARE.STEP_REGISTRY["emit-grant"], verify_counts, action_counts)

    # Break the 3rd step's action so the run halts there.
    real_third_action = steps[2].action
    fail_once = {"armed": True}

    def flaky_action(params, state):
        if fail_once["armed"]:
            fail_once["armed"] = False
            raise RuntimeError("simulated crash mid-runbook")
        return real_third_action(params, state)

    broken_steps = steps[:2] + (
        ARE.RunbookStepSpec(steps[2].step_id, steps[2].kind, steps[2].atom, steps[2].effect_name, steps[2].param_names, steps[2].verify, flaky_action),
    ) + steps[3:]

    ledger = ARE.MemoryRunLedger()
    state: dict = {}
    outcome1 = ARE.execute_runbook(record, broken_steps, run_id=request_id, authorize=authorize, ledger=ledger, state=state, now=signed_at)
    check(not outcome1.ok, "run did not halt on the simulated crash")
    check(outcome1.reason == ARE.REASON_STEP_HALTED, f"expected step-halted, got {outcome1.reason}")
    check(outcome1.halted_step_id == steps[2].step_id, "halted at the wrong step")
    check(action_counts.get(steps[0].step_id) == 1, "step 1 action did not run exactly once before the crash")
    check(action_counts.get(steps[1].step_id) == 1, "step 2 action did not run exactly once before the crash")
    check(steps[3].step_id not in action_counts, "step 4 ran despite the halt at step 3")

    # Retry: same run_id/ledger/state, now with the flaky step's second call
    # succeeding (fail_once already disarmed) — resume must NOT re-invoke
    # steps 1-2's actions (they are ledger-complete).
    outcome2 = ARE.execute_runbook(record, broken_steps, run_id=request_id, authorize=authorize, ledger=ledger, state=state, now=signed_at)
    check(outcome2.ok, f"retry did not complete: {outcome2.reason}")
    check(action_counts[steps[0].step_id] == 1, "step 1 action re-invoked on retry (double-apply)")
    check(action_counts[steps[1].step_id] == 1, "step 2 action re-invoked on retry (double-apply)")
    check(action_counts.get(steps[2].step_id, 0) == 1, "step 3 action was not (or was more than once) invoked on retry")
    check(action_counts.get(steps[3].step_id, 0) == 1, "step 4 action did not run after resume completed")

    statuses = {so.step_id: so.status for so in outcome2.step_outcomes}
    check(statuses[steps[0].step_id] == ARE.STEP_APPLIED and steps[0].step_id, "step 1 outcome not reflected on resume")


def test_idempotent_resume_precheck_is_the_real_guard() -> None:
    """The Antigravity review revision: idempotency must survive a LOST
    ledger. Run a runbook to completion once (ledger + state both populated),
    then re-run against a BRAND NEW empty ledger but the SAME state (as if
    the ledger file were lost/corrupted but the real system already has the
    effects applied). Every step's PRE-CHECK (not the ledger) must report
    already-applied, so no action is invoked a second time."""
    private_key, public_hex = _keypair()
    request_id = "01RUN-IDEMP-B"
    signed_at = datetime.now(timezone.utc)
    record = _authorized_record(runbook="rotate-key", params={"subject": "svc-b"}, request_id=request_id, private_key=private_key)

    action_counts: dict = {}
    verify_counts: dict = {}
    steps = _instrument(ARE.STEP_REGISTRY["rotate-key"], verify_counts, action_counts)

    state: dict = {}
    ledger1 = ARE.MemoryRunLedger()
    authorize1 = _make_authorize(record, private_key, public_hex, signed_at)
    outcome1 = ARE.execute_runbook(record, steps, run_id=request_id, authorize=authorize1, ledger=ledger1, state=state, now=signed_at)
    check(outcome1.ok, f"first run did not complete: {outcome1.reason}")
    check(all(c == 1 for c in action_counts.values()), "an action ran more than once on the first, clean run")

    # Simulate a lost ledger: fresh empty MemoryRunLedger, SAME `state`.
    ledger2 = ARE.MemoryRunLedger()
    authorize2 = _make_authorize(record, private_key, public_hex, signed_at)
    outcome2 = ARE.execute_runbook(record, steps, run_id=request_id, authorize=authorize2, ledger=ledger2, state=state, now=signed_at)
    check(outcome2.ok, f"re-run with a lost ledger did not complete: {outcome2.reason}")
    check(all(so.status == ARE.STEP_SKIPPED for so in outcome2.step_outcomes), "lost-ledger re-run did not pre-check-skip every step")
    check(all(c == 1 for c in action_counts.values()), "an action was invoked again despite the pre-check reporting already-applied")
    check(all(c == 2 for c in verify_counts.values()), "pre-check verify was not actually re-run against the lost-ledger state")


def test_idempotent_resume_durable_file_ledger_across_restart() -> None:
    """Same lost-ledger property, but exercised through the REAL
    file-backed, fsync'd `FileRunLedger` — a fresh instance pointed at the
    same directory stands in for a process restart."""
    private_key, public_hex = _keypair()
    request_id = "01RUN-IDEMP-C"
    signed_at = datetime.now(timezone.utc)
    record = _authorized_record(runbook="epoch-revoke", params={"epoch_scope": "svc-c"}, request_id=request_id, private_key=private_key)
    steps = ARE.STEP_REGISTRY["epoch-revoke"]

    with tempfile.TemporaryDirectory() as tmp:
        ledger_a = ARE.FileRunLedger(tmp)
        state: dict = {}
        authorize_a = _make_authorize(record, private_key, public_hex, signed_at)
        outcome1 = ARE.execute_runbook(record, steps, run_id=request_id, authorize=authorize_a, ledger=ledger_a, state=state, now=signed_at)
        check(outcome1.ok, f"file-ledger first run did not complete: {outcome1.reason}")

        # Fresh FileRunLedger instance, same directory == "process restart".
        ledger_b = ARE.FileRunLedger(tmp)
        persisted = ledger_b.load(request_id)
        check(persisted is not None, "FileRunLedger did not persist step outcomes durably")
        check(all(v.get("status") == ARE.STEP_APPLIED for k, v in persisted.items()), "persisted ledger entries are not all applied")

        authorize_b = _make_authorize(record, private_key, public_hex, signed_at)
        outcome2 = ARE.execute_runbook(record, steps, run_id=request_id, authorize=authorize_b, ledger=ledger_b, state=state, now=signed_at)
        check(outcome2.ok, "resume against a reopened file ledger did not complete")
        check(all(so.status == ARE.STEP_APPLIED for so in outcome2.step_outcomes), "resume did not ledger-hit every already-completed step")
        event_types = [e["event"] for e in outcome2.events]
        check(event_types.count("step_ledger_hit") == len(steps), "reopened-ledger resume did not fast-path every step via ledger hit")


# --------------------------------------------------------------------------
# 2. scope-bound
# --------------------------------------------------------------------------


def test_scope_bound_rejects_param_injection() -> None:
    private_key, public_hex = _keypair()
    request_id = "01RUN-SCOPE-A"
    signed_at = datetime.now(timezone.utc)
    record = _authorized_record(runbook="emit-grant", params={"grant_subject": "svc-d"}, request_id=request_id, private_key=private_key)
    authorize = _make_authorize(record, private_key, public_hex, signed_at)

    action_counts: dict = {}
    verify_counts: dict = {}
    legit_steps = _instrument(ARE.STEP_REGISTRY["emit-grant"], verify_counts, action_counts)
    injected = ARE.RunbookStepSpec(
        step_id="emit-grant.malicious", kind=ARE.KIND_ATOM_CALL, atom="aq-event",
        effect_name="define-scope", param_names=("not_a_hashed_param",),
        verify=lambda p, s: False, action=lambda p, s: {"pwned": True},
    )
    malicious_steps = legit_steps + (injected,)

    ledger = ARE.MemoryRunLedger()
    outcome = ARE.execute_runbook(record, malicious_steps, run_id=request_id, authorize=authorize, ledger=ledger, state={}, now=signed_at)
    check(not outcome.ok, "a step referencing a non-hashed param was accepted")
    check(outcome.reason == ARE.REASON_SCOPE_PARAM, f"expected scope-param rejection, got {outcome.reason}")
    check(not action_counts, "an action ran despite the run being rejected for scope violation")
    check(ledger.load(request_id) is None, "ledger was written to despite a rejected (never-started) run")


def test_scope_bound_rejects_undeclared_effect() -> None:
    private_key, public_hex = _keypair()
    request_id = "01RUN-SCOPE-B"
    signed_at = datetime.now(timezone.utc)
    record = _authorized_record(runbook="epoch-revoke", params={"epoch_scope": "svc-e"}, request_id=request_id, private_key=private_key)
    authorize = _make_authorize(record, private_key, public_hex, signed_at)

    action_counts: dict = {}
    verify_counts: dict = {}
    legit_steps = _instrument(ARE.STEP_REGISTRY["epoch-revoke"], verify_counts, action_counts)
    injected = ARE.RunbookStepSpec(
        step_id="epoch-revoke.escalate", kind=ARE.KIND_ATOM_CALL, atom="aq-epoch-bump",
        effect_name="delete-everything", param_names=("epoch_scope",),
        verify=lambda p, s: False, action=lambda p, s: {"pwned": True},
    )
    malicious_steps = legit_steps + (injected,)

    ledger = ARE.MemoryRunLedger()
    outcome = ARE.execute_runbook(record, malicious_steps, run_id=request_id, authorize=authorize, ledger=ledger, state={}, now=signed_at)
    check(not outcome.ok, "a step with an undeclared effect was accepted")
    check(outcome.reason == ARE.REASON_SCOPE_EFFECT, f"expected scope-effect rejection, got {outcome.reason}")
    check(not action_counts, "an action ran despite the run being rejected for an undeclared effect")


def test_scope_bound_registry_self_check_passes() -> None:
    """The shipped `STEP_REGISTRY` itself must pass the same scope check
    used against a hand-crafted attack — proving the two are the same code
    path, not two diverging implementations."""
    for runbook, steps in ARE.STEP_REGISTRY.items():
        spec = AR.RUNBOOK_REGISTRY[runbook]
        params = {k: ("a" * 5) for k in spec.param_schema}
        record = AR.create_request(request_id=f"01SELFCHECK-{runbook}", created_by="t", runbook=runbook, params=params)
        violation = ARE._validate_step_scope(steps, record)  # noqa: SLF001 - same-family test reuse
        check(violation is None, f"{runbook}: shipped STEP_REGISTRY fails its own scope check: {violation}")


def test_unregistered_runbook_rejected() -> None:
    """`restart-service` is a valid P0 runbook (so it can be requested/
    approved) but has no P3 step sequence yet — `run_registered_runbook`
    must reject it distinctly, never silently no-op or execute nothing
    while claiming success."""
    private_key, public_hex = _keypair()
    request_id = "01RUN-UNREG"
    signed_at = datetime.now(timezone.utc)
    record = _authorized_record(runbook="restart-service", params={"service": "switchboard"}, request_id=request_id, private_key=private_key)
    authorize = _make_authorize(record, private_key, public_hex, signed_at)
    outcome = ARE.run_registered_runbook(record, run_id=request_id, authorize=authorize, ledger=ARE.MemoryRunLedger(), state={}, now=signed_at)
    check(not outcome.ok and outcome.reason == ARE.REASON_UNREGISTERED_RUNBOOK, f"expected unregistered-runbook rejection, got {outcome.reason}")


# --------------------------------------------------------------------------
# 3. authorized-once
# --------------------------------------------------------------------------


def test_authorized_once_signature_not_replayable_across_request_ids() -> None:
    """A signature over request A's canonical_hash must NOT authorize
    request B, even with content-identical params — the P0 request_id
    binding (canonical_hash includes request_id) makes this impossible at
    the cryptographic layer, and the engine must surface that as a denial,
    never a silent pass-through."""
    private_key, public_hex = _keypair()
    signed_at = datetime.now(timezone.utc)
    record_a = _authorized_record(runbook="emit-grant", params={"grant_subject": "svc-f"}, request_id="01RUN-REPLAY-A", private_key=private_key)
    record_b = _authorized_record(runbook="emit-grant", params={"grant_subject": "svc-f"}, request_id="01RUN-REPLAY-B", private_key=private_key)
    check(record_a["summary"] == record_b["summary"], "fixture content is not actually identical across the two requests")

    signature_a = _sign(record_a, private_key)
    verdict_direct = AS.verify_execution_authorization(record_b, signature_a, public_hex)
    check(not verdict_direct.ok, "a copied signature from request A verified against request B's record")

    stolen_authorize = ARE.make_signature_authorization_check(signature=signature_a, owner_public_key=public_hex, signed_at=signed_at)
    outcome = ARE.run_registered_runbook(record_b, run_id="01RUN-REPLAY-B", authorize=stolen_authorize, ledger=ARE.MemoryRunLedger(), state={}, now=signed_at)
    check(not outcome.ok, "engine executed request B using a signature stolen from request A")
    check(outcome.reason == ARE.REASON_UNAUTHORIZED, f"expected unauthorized, got {outcome.reason}")
    event_types = [e["event"] for e in outcome.events]
    check("authorization_denied" in event_types, "no authorization_denied event recorded for the replay attempt")


# --------------------------------------------------------------------------
# 4. retry-reauth
# --------------------------------------------------------------------------


def test_retry_reauth_rejects_stale_authorization() -> None:
    """A retry hours after the authorizing signature was produced must be
    rejected on freshness grounds, even though the signature itself is
    cryptographically valid and step progress could otherwise resume."""
    private_key, public_hex = _keypair()
    request_id = "01RUN-STALE"
    signed_at = datetime.now(timezone.utc)
    record = _authorized_record(runbook="rotate-key", params={"subject": "svc-g"}, request_id=request_id, private_key=private_key)
    signature = _sign(record, private_key)
    ttl = timedelta(minutes=15)
    authorize = ARE.make_signature_authorization_check(signature=signature, owner_public_key=public_hex, signed_at=signed_at, ttl=ttl)

    ledger = ARE.MemoryRunLedger()
    fresh_outcome = ARE.execute_runbook(record, ARE.STEP_REGISTRY["rotate-key"], run_id=request_id, authorize=authorize, ledger=ledger, state={}, now=signed_at + timedelta(seconds=5))
    check(fresh_outcome.ok, f"a fresh, well-within-TTL authorization was rejected: {fresh_outcome.reason}")

    # A second request never approved/run, retried with the SAME
    # authorization long after signing.
    request_id2 = "01RUN-STALE-2"
    record2 = _authorized_record(runbook="rotate-key", params={"subject": "svc-h"}, request_id=request_id2, private_key=private_key)
    signature2 = _sign(record2, private_key)
    authorize2 = ARE.make_signature_authorization_check(signature=signature2, owner_public_key=public_hex, signed_at=signed_at, ttl=ttl)
    stale_outcome = ARE.execute_runbook(record2, ARE.STEP_REGISTRY["rotate-key"], run_id=request_id2, authorize=authorize2, ledger=ARE.MemoryRunLedger(), state={}, now=signed_at + timedelta(hours=3))
    check(not stale_outcome.ok, "a 3-hour-stale authorization (TTL=15m) was accepted")
    check(stale_outcome.reason == ARE.REASON_AUTHORIZATION_STALE, f"expected stale-authorization reason, got {stale_outcome.reason}")

    # Retry mid-run (progress already exists) with a now-stale
    # authorization must ALSO be rejected — resume applies to step
    # progress, never to authorization itself.
    request_id3 = "01RUN-STALE-3"
    record3 = _authorized_record(runbook="rotate-key", params={"subject": "svc-i"}, request_id=request_id3, private_key=private_key)
    signature3 = _sign(record3, private_key)
    ledger3 = ARE.MemoryRunLedger()
    authorize3_fresh = ARE.make_signature_authorization_check(signature=signature3, owner_public_key=public_hex, signed_at=signed_at, ttl=ttl)
    partial = ARE.execute_runbook(record3, ARE.STEP_REGISTRY["rotate-key"][:2], run_id=request_id3, authorize=authorize3_fresh, ledger=ledger3, state={}, now=signed_at + timedelta(seconds=5))
    check(partial.ok, "partial 2-step run did not complete cleanly")
    authorize3_stale = ARE.make_signature_authorization_check(signature=signature3, owner_public_key=public_hex, signed_at=signed_at, ttl=ttl)
    retry_stale = ARE.execute_runbook(record3, ARE.STEP_REGISTRY["rotate-key"], run_id=request_id3, authorize=authorize3_stale, ledger=ledger3, state={}, now=signed_at + timedelta(hours=2))
    check(not retry_stale.ok and retry_stale.reason == ARE.REASON_AUTHORIZATION_STALE, "a stale-authorization retry against a partially-complete run was not rejected")
    check(not retry_stale.step_outcomes, "a rejected-for-staleness retry still reported step outcomes (steps must not even be reached)")


# --------------------------------------------------------------------------
# 5. fail-closed
# --------------------------------------------------------------------------


def test_fail_closed_halts_and_supports_retry_or_abort() -> None:
    private_key, public_hex = _keypair()
    request_id = "01RUN-FAILCLOSED"
    signed_at = datetime.now(timezone.utc)
    record = _authorized_record(runbook="activate-foundation-c-slice", params={"slice": "svc-j"}, request_id=request_id, private_key=private_key)

    action_counts: dict = {}
    verify_counts: dict = {}
    steps = _instrument(ARE.STEP_REGISTRY["activate-foundation-c-slice"], verify_counts, action_counts)
    real_second = steps[1].action

    def always_fails(params, state):
        raise ValueError("atom permanently broken")

    broken = (steps[0],) + (ARE.RunbookStepSpec(steps[1].step_id, steps[1].kind, steps[1].atom, steps[1].effect_name, steps[1].param_names, steps[1].verify, always_fails),) + steps[2:]

    ledger = ARE.MemoryRunLedger()
    state: dict = {}
    authorize = _make_authorize(record, private_key, public_hex, signed_at)
    outcome = ARE.execute_runbook(record, broken, run_id=request_id, authorize=authorize, ledger=ledger, state=state, now=signed_at)
    check(not outcome.ok, "a permanently-failing step did not halt the run")
    check(outcome.reason == ARE.REASON_STEP_HALTED, f"expected step-halted, got {outcome.reason}")
    check(outcome.halted_step_id == steps[1].step_id, "halted_step_id does not name the actually-failing step")
    check(steps[2].step_id not in action_counts and steps[3].step_id not in action_counts, "a later step ran after an earlier one halted (blind continue)")
    persisted = ledger.load(request_id)
    check(persisted[steps[1].step_id]["status"] == ARE.STEP_FAILED, "the failed step was not recorded plainly in the ledger")

    # Intervention path 1: retry with the atom fixed.
    fixed = (steps[0], ARE.RunbookStepSpec(steps[1].step_id, steps[1].kind, steps[1].atom, steps[1].effect_name, steps[1].param_names, steps[1].verify, real_second)) + steps[2:]
    authorize_retry = _make_authorize(record, private_key, public_hex, signed_at)
    retry_outcome = ARE.execute_runbook(record, fixed, run_id=request_id, authorize=authorize_retry, ledger=ledger, state=state, now=signed_at)
    check(retry_outcome.ok, f"retry after fixing the atom did not complete: {retry_outcome.reason}")
    check(action_counts[steps[0].step_id] == 1, "retry re-invoked the already-applied first step")

    # Intervention path 2: abort a different, still-broken run.
    request_id2 = "01RUN-ABORT"
    record2 = _authorized_record(runbook="activate-foundation-c-slice", params={"slice": "svc-k"}, request_id=request_id2, private_key=private_key)
    ledger2 = ARE.MemoryRunLedger()
    authorize2 = _make_authorize(record2, private_key, public_hex, signed_at)
    broken2 = (ARE.STEP_REGISTRY["activate-foundation-c-slice"][0],) + (ARE.RunbookStepSpec("x", ARE.KIND_ATOM_CALL, "aq-event", "load-config", ("slice",), lambda p, s: False, always_fails),)
    halted2 = ARE.execute_runbook(record2, broken2, run_id=request_id2, authorize=authorize2, ledger=ledger2, state={}, now=signed_at)
    check(not halted2.ok, "setup error: second run did not halt")
    ARE.abort_run(request_id2, ledger=ledger2, actor="test-operator")
    authorize2_again = _make_authorize(record2, private_key, public_hex, signed_at)
    after_abort = ARE.execute_runbook(record2, ARE.STEP_REGISTRY["activate-foundation-c-slice"], run_id=request_id2, authorize=authorize2_again, ledger=ledger2, state={}, now=signed_at)
    check(not after_abort.ok and after_abort.reason == ARE.REASON_RUN_ABORTED, "a run() call after abort_run() silently proceeded instead of rejecting")


# --------------------------------------------------------------------------
# 6. audit-chain
# --------------------------------------------------------------------------


def test_audit_chain_full_happy_path() -> None:
    private_key, public_hex = _keypair()
    request_id = "01RUN-AUDIT"
    signed_at = datetime.now(timezone.utc)
    record = _authorized_record(runbook="emit-grant", params={"grant_subject": "svc-l"}, request_id=request_id, private_key=private_key)
    authorize = _make_authorize(record, private_key, public_hex, signed_at)

    outcome = ARE.execute_runbook(record, ARE.STEP_REGISTRY["emit-grant"], run_id=request_id, authorize=authorize, ledger=ARE.MemoryRunLedger(), state={}, now=signed_at)
    check(outcome.ok, f"happy-path run did not complete: {outcome.reason}")

    event_types = [e["event"] for e in outcome.events]
    expected = ["record_validated", "hash_verified", "authorization_verified", "scope_validated"] + ["step_applied"] * 4 + ["run_completed"]
    check(event_types == expected, f"audit chain shape drift: {event_types}")
    check(all(e["run_id"] == request_id for e in outcome.events), "an audit event referenced a different run_id")
    check(len(outcome.step_outcomes) == 4 and all(so.status == ARE.STEP_APPLIED for so in outcome.step_outcomes), "step_outcomes did not reflect 4 applied steps")


def test_audit_chain_records_rejection_without_step_events() -> None:
    private_key, public_hex = _keypair()
    request_id = "01RUN-AUDIT-REJECT"
    signed_at = datetime.now(timezone.utc)
    record = _authorized_record(runbook="emit-grant", params={"grant_subject": "svc-m"}, request_id=request_id, private_key=private_key)
    # Wrong key -> bad signature -> rejected before any step event.
    _, wrong_public_hex = _keypair()
    signature = _sign(record, private_key)
    authorize = ARE.make_signature_authorization_check(signature=signature, owner_public_key=wrong_public_hex, signed_at=signed_at)
    outcome = ARE.execute_runbook(record, ARE.STEP_REGISTRY["emit-grant"], run_id=request_id, authorize=authorize, ledger=ARE.MemoryRunLedger(), state={}, now=signed_at)
    check(not outcome.ok and outcome.reason == ARE.REASON_UNAUTHORIZED, "a signature verified against the wrong public key was accepted")
    event_types = [e["event"] for e in outcome.events]
    check(event_types == ["record_validated", "hash_verified", "authorization_denied"], f"unexpected audit chain for a denied authorization: {event_types}")


# --------------------------------------------------------------------------
# 7. no-shell
# --------------------------------------------------------------------------


def test_no_shell_static_source_check() -> None:
    check("shell=True" not in ENGINE_SOURCE, "approval_runbook_engine.py contains a shell=True call")
    check("import subprocess" not in ENGINE_SOURCE and "from subprocess" not in ENGINE_SOURCE, "approval_runbook_engine.py imports subprocess at all — every atom here is a pure in-memory/file-ledger stub, no process spawn is legitimate at this slice")
    check("os.system" not in ENGINE_SOURCE, "approval_runbook_engine.py calls os.system")


def test_no_shell_atom_signatures_cannot_carry_key_material() -> None:
    """Every registered atom's `verify`/`action` accepts EXACTLY
    `(params, state)` — no atom callable in the shipped registry could ever
    receive an `owner_key`/private-key-shaped argument, structurally
    enforcing design point (e)."""
    for runbook, steps in ARE.STEP_REGISTRY.items():
        for step in steps:
            for fn, label in ((step.verify, "verify"), (step.action, "action")):
                sig = inspect.signature(fn)
                names = list(sig.parameters.keys())
                check(len(names) == 2, f"{runbook}.{step.step_id}.{label} does not take exactly 2 positional args: {names}")
                check(
                    not any(kw in n.lower() for n in names for kw in ("key", "secret", "private")),
                    f"{runbook}.{step.step_id}.{label} has a suspiciously key-shaped parameter: {names}",
                )


# --------------------------------------------------------------------------
# 8. declaration-coupled
# --------------------------------------------------------------------------


def test_declaration_coupled_activate_runbooks() -> None:
    for runbook in ("activate-signer-service", "activate-foundation-c-slice"):
        steps = ARE.STEP_REGISTRY[runbook]
        declarative = [s for s in steps if s.kind == ARE.KIND_DECLARATIVE_UPDATE]
        check(len(declarative) == 1, f"{runbook}: expected exactly 1 declarative-update step, found {len(declarative)}")
        step = declarative[0]
        check(step.atom == "nixos-rebuild", f"{runbook}: declarative-update step does not use the nixos-rebuild atom: {step.atom}")
        result = step.action({k: "svc-n" for k in step.param_names}, {})
        for field in ("nix_declaration_updated", "staged", "rebuild"):
            check(field in result, f"{runbook}: declarative-update stub result missing {field!r}: {result}")


def test_declaration_coupled_transient_runbooks_have_no_declarative_step() -> None:
    for runbook in ("rotate-key", "epoch-revoke", "emit-grant"):
        steps = ARE.STEP_REGISTRY[runbook]
        check(
            all(s.kind != ARE.KIND_DECLARATIVE_UPDATE for s in steps),
            f"{runbook}: has a declarative-update step but is not an activate-* runbook (Rule 13 scope is activate-* only per design point (f))",
        )
        check(all(s.kind == ARE.KIND_ATOM_CALL for s in steps), f"{runbook}: has a non-atom-call, non-declarative step kind")


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
    print(f"PASS: {len(tests)} approval-runbook-engine P3 checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
