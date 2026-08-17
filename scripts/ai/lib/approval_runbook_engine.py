"""Idempotent, audited, resumable runbook executor — Approval Control Plane
P3 (pure library CORE; no live atom execution, no subprocess, no socket
server, no owner key handling).

Implements `.agents/plans/approval-control-plane/ACP-P3-DESIGN-20260816.md`
(authoritative — including the "Review fold — Antigravity + local" section:
atom pre-check idempotency, param-injection allowlists + no shell-spawning/
array-args, retry re-authorization, forward-retry partial-state, declarative
coupling). Completes the approve-to-action arc: P0 record
(`approval_request.py`) -> P1 signer (`approval_signer.py`) -> **P3 runs the
whole multi-step sequence the human never sees.** A runbook is the named,
idempotent workflow one approval authorizes — `activate-signer-service`,
`rotate-key`, `epoch-revoke`, `emit-grant`, `activate-foundation-c-slice` —
each an ordered sequence of typed `RunbookStepSpec`s wrapping a STUB atom
(record-only; no real `aq-provision-signer-key`/`aq-epoch-bump`/`aq-event`/
`nixos-rebuild` call — that swap is a later slice, same contract).

Execution semantics (design "Execution semantics", the hard requirements):
  1. Idempotent + resumable. Every step's atom implements a `verify`
     PRE-CHECK run BEFORE its action; if the effect is already present, the
     step is SKIPPED — independent of the step-outcome ledger (Antigravity
     revision: "idempotency is a property of the atom's pre-check, not just
     the engine's checkpoint" — a stale/lost ledger can never cause a
     double-apply). The ledger (`RunLedger`) is what makes *resume* fast
     (already-completed steps short-circuit without even calling `verify`),
     never what makes it *safe* — safety is the pre-check, always.
  2. Audited end to end. Every step — and every abort/reject/authorization
     decision — appends one event to an ordered chain (mirrors
     `approval_executor._emit`). Nothing runs outside it.
  3. Authorized once, bound throughout. `execute_runbook` calls its injected
     `authorize` callback (production wiring: `make_signature_authorization_
     check`, which wraps `approval_signer.verify_execution_authorization` —
     the ONLY authorization signal, per that module's design invariant 6;
     `record["status"]` is never consulted here either) BEFORE any step, and
     calls it AGAIN, fresh, on every retry — no caching across calls, so a
     stale/expired authorization is rejected on retry even if step progress
     resumes (design review: "resume applies to idempotent step progress,
     never to the authorization itself"). A step's args are a `params`
     dict built ONLY by projecting the approved record's hashed
     `action_manifest.params` onto that step's declared `param_names` — no
     runtime injection is possible because no other value ever reaches an
     atom.
  4. Fail-closed + intervenable. A failing step's action HALTS the run
     immediately (no blind continue to the next step); the failure is
     recorded plainly in both the ledger and the event chain. `execute_
     runbook` is itself the retry path (call it again — authorization is
     re-checked, completed steps ledger-skip, the halted step's pre-check
     runs again); `abort_run` is the terminal alternative (marks the run
     `aborted` in the ledger; a later `execute_runbook` call on an aborted
     run_id is rejected, never silently resumed).
  5. NixOS-declarative aware. A step whose atom performs the "update the Nix
     declaration + stage + rebuild" triple is typed `KIND_DECLARATIVE_UPDATE`
     (not a bare `KIND_ATOM_CALL`) — used by exactly the `activate-*`
     runbooks' rebuild-carrying step (Rule 13; design "declaration-coupling
     reinforced").

Scope-bound (design point (d) / validation goal "scope-bound"): before ANY
step runs, every step in the sequence is checked against the record actually
being executed — `step.param_names` must be a subset of
`record["action_manifest"]["params"]` keys, and `step.effect_name` must be a
member of `record["action_manifest"]["declared_effects"]`. Either violation
REJECTS the whole run before a single atom executes. This is checked twice:
once at import time against the registered `STEP_REGISTRY` (self-consistency
— `_validate_registry` asserts each runbook's step `effect_name` sequence
equals its `RunbookSpec.declared_effects` tuple exactly, in order), and once
at run time against the record `execute_runbook` was actually handed (in
case a caller passes a hand-built/tampered `steps` sequence directly, which
is exactly how `test-approval-runbook-engine.py`'s scope-bound test exercises
the rejection path without needing to monkeypatch module globals).

No atom in this module ever imports `subprocess`, spawns a shell, or accepts
a parameter that could carry key material — every atom callable's signature
is exactly `(params: Mapping[str, Any], state: MutableMapping[str, Any]) ->
dict`. A step needing the owner key (design point (e)) is typed
`KIND_SIGNER_CALL`; the engine dispatches it through the SAME `(params,
state)` atom signature as every other kind — there is no code path by which
a step's action could receive `owner_key`/private key bytes, because the
engine itself never holds them (the one WebAuthn tap that gated `authorize`
IS the key-touching moment; per this build's registry, no currently-shipped
runbook step needs a second one, so `KIND_SIGNER_CALL` is defined and
dispatch-supported but unused by `STEP_REGISTRY` below — a documented
contract, not a placeholder).

Scope fence (per the design packet + task bounds): no real atom execution
(every atom below is a deterministic, in-memory/file-ledger STUB — no
`aq-provision-signer-key`/`aq-epoch-bump`/`aq-event`/`nixos-rebuild` process
is ever spawned), no live `nixos-rebuild`/`systemctl`, no P1 service
internals (calls only the pure `approval_signer.verify_execution_authorization`
contract function), no UI (P2). Default-OFF: nothing in this module is wired
into any live dispatch path.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, MutableMapping, Optional, Sequence

_LIB = os.path.dirname(os.path.abspath(__file__))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import approval_request as AR  # noqa: E402
import approval_signer as AS  # noqa: E402

# --------------------------------------------------------------------------
# Step kinds (design point (f) — declarative coupling)
# --------------------------------------------------------------------------

KIND_ATOM_CALL = "atom-call"
KIND_DECLARATIVE_UPDATE = "declarative-update"
KIND_SIGNER_CALL = "signer-call"
STEP_KINDS = (KIND_ATOM_CALL, KIND_DECLARATIVE_UPDATE, KIND_SIGNER_CALL)

# Atom callable contract: NEVER receives key material, NEVER spawns a shell,
# ONLY ever sees the step's scope-projected params + the (stub, in-memory or
# file-ledger backed) simulated system `state`.
AtomVerify = Callable[[Mapping[str, Any], MutableMapping[str, Any]], bool]
AtomAction = Callable[[Mapping[str, Any], MutableMapping[str, Any]], dict]


@dataclass(frozen=True)
class RunbookStepSpec:
    """One ordered step of a registered runbook. `param_names` is the
    CLOSED subset of the runbook's `param_schema` keys this step's atom is
    allowed to see (design point (d)); `effect_name` MUST be a member of the
    runbook's `declared_effects` tuple, at the position matching declaration
    order (`_validate_registry` asserts this at import time)."""

    step_id: str
    kind: str
    atom: str
    effect_name: str
    param_names: tuple
    verify: AtomVerify
    action: AtomAction


# --------------------------------------------------------------------------
# Typed, safe-to-log step outcomes + run reasons
# --------------------------------------------------------------------------

STEP_SKIPPED = "skipped"  # pre-check reported the effect already present
STEP_APPLIED = "applied"  # action ran successfully
STEP_FAILED = "failed"  # action raised; run halts here
STEP_STATUSES = (STEP_SKIPPED, STEP_APPLIED, STEP_FAILED)


@dataclass(frozen=True)
class StepOutcome:
    step_id: str
    status: str
    at: str
    detail: Any = None


REASON_COMPLETED = "completed"
REASON_RECORD_INVALID = "record-invalid"
REASON_HASH_DRIFT = "canonical-hash-drift"
REASON_RUN_ABORTED = "run-already-aborted"
REASON_UNAUTHORIZED = "unauthorized"
REASON_AUTHORIZATION_STALE = "authorization-stale"
REASON_UNREGISTERED_RUNBOOK = "runbook-not-registered-for-engine"
REASON_SCOPE_PARAM = "step-param-out-of-hashed-scope"
REASON_SCOPE_EFFECT = "step-effect-out-of-declared-effects"
REASON_SCOPE_EFFECT_ORDER = "step-effects-do-not-match-declared-order"
REASON_STEP_HALTED = "step-halted"
REASON_INTERNAL = "internal-error"


@dataclass(frozen=True)
class RunOutcome:
    """Total, never-raising result of `execute_runbook`. `ok=True` iff
    `reason == REASON_COMPLETED`. `events` is the full ordered audit chain
    (never empty). `step_outcomes` reflects every step reached this call
    (ledger-hit steps included, so a caller can see the full picture even on
    a fast resume)."""

    ok: bool
    reason: str
    events: tuple
    step_outcomes: tuple
    halted_step_id: Optional[str] = None


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _emit(events: list, moment: datetime, event_type: str, run_id: str, **payload: Any) -> dict:
    event = {"event": event_type, "run_id": run_id, "at": _iso(moment), **payload}
    events.append(event)
    return event


# --------------------------------------------------------------------------
# Authorization — design point (a). `authorize` is injected so tests can
# exercise the stale/expired-on-retry path without a real WebAuthn ceremony;
# `make_signature_authorization_check` is the production wiring, and it is
# the ONLY place this module calls into `approval_signer`.
# --------------------------------------------------------------------------

AUTH_OK = "ok"
DENY_BAD_AUTHORIZATION = "bad-authorization-signature"
DENY_AUTHORIZATION_STALE = "authorization-stale"


@dataclass(frozen=True)
class AuthorizationVerdict:
    ok: bool
    reason: str
    detail: str = ""


# `(record, now) -> AuthorizationVerdict`. Called fresh by `execute_runbook`
# on every invocation (initial run AND every retry) — never cached, never
# reused across calls.
AuthorizationCheck = Callable[[Mapping[str, Any], datetime], AuthorizationVerdict]

DEFAULT_AUTHORIZATION_TTL = timedelta(minutes=15)


def make_signature_authorization_check(
    *,
    signature: Any,
    owner_public_key: Any,
    signed_at: datetime,
    ttl: timedelta = DEFAULT_AUTHORIZATION_TTL,
) -> AuthorizationCheck:
    """Production-shaped `AuthorizationCheck`: wraps
    `approval_signer.verify_execution_authorization(record, signature,
    owner_public_key)` — the P1 contract, the ONLY authorization signal
    (`record["status"]` is never consulted, neither here nor by that
    function) — with a freshness bound. `signed_at` is the caller-attested
    moment P1's `sign_request` actually produced `signature`; a call more
    than `ttl` after `signed_at` is a stale/expired authorization and is
    rejected (design review fold: "a runbook retried hours later must NOT
    resume on a stale signature" — P1's own challenge TTL bounds how long an
    UNSIGNED challenge may sit; this bounds how long an ALREADY-SIGNED
    authorization may be used to (re)start/resume a P3 run)."""

    def _check(record: Mapping[str, Any], now: datetime) -> AuthorizationVerdict:
        verdict = AS.verify_execution_authorization(record, signature, owner_public_key)
        if not verdict.ok:
            return AuthorizationVerdict(False, DENY_BAD_AUTHORIZATION, verdict.reason)
        age = now - signed_at
        if age > ttl:
            return AuthorizationVerdict(False, DENY_AUTHORIZATION_STALE, f"age_seconds={age.total_seconds():.0f}")
        return AuthorizationVerdict(True, AUTH_OK)

    return _check


# --------------------------------------------------------------------------
# RunLedger — durable per-run step-outcome store (design point (b)). This is
# the RESUME optimization, never the safety guard (that is always each
# atom's `verify` pre-check — see module docstring). Two implementations:
# `MemoryRunLedger` for in-process tests, `FileRunLedger` for a genuinely
# durable (fsync'd, atomic-replace) store a test can reopen fresh to
# simulate a process restart — mirrors `approval_signer.PendingChallengeStore`'s
# atomicity pattern (tempfile + fsync(file) + os.replace + fsync(dir)).
# --------------------------------------------------------------------------

_ABORTED_MARKER = "__aborted__"


class MemoryRunLedger:
    def __init__(self) -> None:
        self._runs: dict[str, dict] = {}

    def load(self, run_id: str) -> Optional[dict]:
        found = self._runs.get(run_id)
        return dict(found) if found is not None else None

    def save(self, run_id: str, ledger: Mapping[str, Any]) -> None:
        self._runs[run_id] = dict(ledger)


class FileRunLedger:
    """One JSON file per `run_id` (named by a filesystem-safe digest of the
    id) under `ledger_dir`. Every `save` is a fresh tempfile + fsync +
    `os.replace` + directory fsync — a crash mid-write never leaves a
    half-written ledger file. A brand-new `FileRunLedger(ledger_dir)`
    instance pointed at the same directory sees exactly what the last
    completed `save` wrote — the "simulated process restart" a resumability
    test needs."""

    def __init__(self, ledger_dir: Any) -> None:
        self._dir = str(ledger_dir)
        os.makedirs(self._dir, mode=0o700, exist_ok=True)

    def _path(self, run_id: str) -> str:
        import hashlib

        digest = hashlib.sha256(run_id.encode("utf-8")).hexdigest()
        return os.path.join(self._dir, f"{digest}.json")

    def load(self, run_id: str) -> Optional[dict]:
        try:
            raw = Path(self._path(run_id)).read_bytes()
        except OSError:
            return None
        try:
            doc = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return None
        return doc if isinstance(doc, dict) else None

    def save(self, run_id: str, ledger: Mapping[str, Any]) -> None:
        path = self._path(run_id)
        fd, tmp_path = tempfile.mkstemp(dir=self._dir, prefix=".run.", suffix=".tmp")
        try:
            os.write(fd, json.dumps(dict(ledger), sort_keys=True).encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, path)
        dir_fd = os.open(self._dir, os.O_DIRECTORY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)


# --------------------------------------------------------------------------
# Scope-bound check (design point (d) / validation goal "scope-bound")
# --------------------------------------------------------------------------


def _validate_step_scope(steps: Sequence[RunbookStepSpec], record: Mapping[str, Any]) -> Optional[tuple]:
    """Returns `(reason, detail)` for the FIRST scope violation found, or
    `None` if every step in `steps` is fully within `record`'s hashed
    `action_manifest` (both `params` keys and `declared_effects`
    membership). Pure, never raises on well-formed input (caller has already
    run `AR.validate(record)` by the time this is reached)."""
    manifest = record["action_manifest"]
    param_keys = set(manifest["params"].keys())
    declared = set(manifest["declared_effects"])
    for step in steps:
        if not set(step.param_names).issubset(param_keys):
            return (REASON_SCOPE_PARAM, f"{step.step_id}:{sorted(set(step.param_names) - param_keys)}")
        if step.effect_name not in declared:
            return (REASON_SCOPE_EFFECT, f"{step.step_id}:{step.effect_name}")
    return None


# --------------------------------------------------------------------------
# execute_runbook — the engine CORE
# --------------------------------------------------------------------------


def execute_runbook(
    record: Mapping[str, Any],
    steps: Sequence[RunbookStepSpec],
    *,
    run_id: str,
    authorize: AuthorizationCheck,
    ledger: Any,
    state: MutableMapping[str, Any],
    actor: str = "runbook-engine",
    now: Optional[datetime] = None,
) -> RunOutcome:
    """Run (or resume, or retry) `steps` against `record`. Total function:
    never raises. `ledger` is a `MemoryRunLedger`/`FileRunLedger` (or
    anything duck-typing `.load(run_id) -> Optional[dict]` /
    `.save(run_id, dict) -> None`); `state` is the STUB simulated-system dict
    every atom's `verify`/`action` reads and mutates — callers pass the SAME
    `state` object across a resume/retry to get real idempotent-resume
    behavior, and a fresh empty dict to simulate a from-scratch environment.

    Order of gates, all BEFORE any step's action runs (design point (a) +
    (d)): record well-formed -> canonical hash matches binding (tamper) ->
    run not already aborted -> `authorize(record, now)` passes, called FRESH
    every call -> every step in scope (params subset of hashed params,
    effect in declared_effects). Only then does the step loop start."""
    events: list[dict] = []
    moment = now or datetime.now(timezone.utc)
    step_outcomes: list[StepOutcome] = []

    try:
        verdict = AR.validate(record)
        if not verdict.ok:
            _emit(events, moment, "run_rejected", run_id, reason=REASON_RECORD_INVALID, detail=verdict.reason)
            return RunOutcome(False, REASON_RECORD_INVALID, tuple(events), tuple(step_outcomes))
        _emit(events, moment, "record_validated", run_id)

        recomputed = AR.compute_hash(record)
        stored = record["binding"]["canonical_hash"]
        if recomputed != stored:
            _emit(events, moment, "tamper_detected", run_id, expected=stored, recomputed=recomputed)
            return RunOutcome(False, REASON_HASH_DRIFT, tuple(events), tuple(step_outcomes))
        _emit(events, moment, "hash_verified", run_id, canonical_hash=stored)

        run_ledger = ledger.load(run_id) or {}
        if run_ledger.get(_ABORTED_MARKER):
            _emit(events, moment, "run_rejected", run_id, reason=REASON_RUN_ABORTED)
            return RunOutcome(False, REASON_RUN_ABORTED, tuple(events), tuple(step_outcomes))

        # Authorization is re-checked on EVERY call — initial run and every
        # retry alike (design point (a), review "retry re-authorization").
        auth = authorize(record, moment)
        if not auth.ok:
            reason = REASON_AUTHORIZATION_STALE if auth.reason == DENY_AUTHORIZATION_STALE else REASON_UNAUTHORIZED
            _emit(events, moment, "authorization_denied", run_id, reason=auth.reason, detail=auth.detail)
            return RunOutcome(False, reason, tuple(events), tuple(step_outcomes))
        _emit(events, moment, "authorization_verified", run_id)

        scope_violation = _validate_step_scope(steps, record)
        if scope_violation is not None:
            reason, detail = scope_violation
            _emit(events, moment, "run_rejected", run_id, reason=reason, detail=detail)
            return RunOutcome(False, reason, tuple(events), tuple(step_outcomes))
        _emit(events, moment, "scope_validated", run_id, step_count=len(steps))

        for step in steps:
            existing = run_ledger.get(step.step_id)
            if isinstance(existing, dict) and existing.get("status") in (STEP_APPLIED, STEP_SKIPPED):
                outcome = StepOutcome(step.step_id, existing["status"], existing.get("at", ""), existing.get("detail"))
                step_outcomes.append(outcome)
                _emit(events, moment, "step_ledger_hit", run_id, step_id=step.step_id, status=outcome.status)
                continue

            # The ONLY params this atom ever sees: the closed projection of
            # the record's hashed params onto this step's declared names —
            # no other value can reach `verify`/`action` (design point (d)).
            params = {k: record["action_manifest"]["params"][k] for k in step.param_names}

            try:
                already = step.verify(params, state)
            except Exception as exc:  # noqa: BLE001 - a raising pre-check must fail closed, never propagate
                outcome = StepOutcome(step.step_id, STEP_FAILED, _iso(moment), exc.__class__.__name__)
                step_outcomes.append(outcome)
                run_ledger[step.step_id] = {"status": STEP_FAILED, "at": _iso(moment), "detail": exc.__class__.__name__}
                ledger.save(run_id, run_ledger)
                _emit(events, moment, "step_failed", run_id, step_id=step.step_id, phase="verify", error=exc.__class__.__name__)
                return RunOutcome(False, REASON_STEP_HALTED, tuple(events), tuple(step_outcomes), halted_step_id=step.step_id)

            if already:
                outcome = StepOutcome(step.step_id, STEP_SKIPPED, _iso(moment))
                step_outcomes.append(outcome)
                run_ledger[step.step_id] = {"status": STEP_SKIPPED, "at": _iso(moment), "detail": None}
                ledger.save(run_id, run_ledger)
                _emit(events, moment, "step_skipped_precheck", run_id, step_id=step.step_id, kind=step.kind, atom=step.atom)
                continue

            try:
                result = step.action(params, state)
            except Exception as exc:  # noqa: BLE001 - a raising action must fail closed, never propagate
                outcome = StepOutcome(step.step_id, STEP_FAILED, _iso(moment), exc.__class__.__name__)
                step_outcomes.append(outcome)
                run_ledger[step.step_id] = {"status": STEP_FAILED, "at": _iso(moment), "detail": exc.__class__.__name__}
                ledger.save(run_id, run_ledger)
                _emit(events, moment, "step_failed", run_id, step_id=step.step_id, phase="action", error=exc.__class__.__name__)
                return RunOutcome(False, REASON_STEP_HALTED, tuple(events), tuple(step_outcomes), halted_step_id=step.step_id)

            outcome = StepOutcome(step.step_id, STEP_APPLIED, _iso(moment), result)
            step_outcomes.append(outcome)
            run_ledger[step.step_id] = {"status": STEP_APPLIED, "at": _iso(moment), "detail": result}
            ledger.save(run_id, run_ledger)
            _emit(events, moment, "step_applied", run_id, step_id=step.step_id, kind=step.kind, atom=step.atom, result=result)

        _emit(events, moment, "run_completed", run_id)
        return RunOutcome(True, REASON_COMPLETED, tuple(events), tuple(step_outcomes))
    except Exception as exc:  # noqa: BLE001 - total function, never raises into the caller
        _emit(events, moment, "run_rejected", run_id, reason=REASON_INTERNAL, detail=f"unhandled:{exc.__class__.__name__}")
        return RunOutcome(False, REASON_INTERNAL, tuple(events), tuple(step_outcomes))


def abort_run(run_id: str, *, ledger: Any, actor: str = "operator", now: Optional[datetime] = None) -> dict:
    """Mark `run_id` terminally aborted (design point (c) — the operator
    intervention alternative to retry). Idempotent: aborting an
    already-aborted run just re-records the marker. A later `execute_runbook`
    call for this `run_id` always rejects with `REASON_RUN_ABORTED`, never
    silently resumes — an abort is a one-way door in this engine, matching
    the "no silent partial success" fail-closed invariant."""
    moment = now or datetime.now(timezone.utc)
    run_ledger = ledger.load(run_id) or {}
    run_ledger[_ABORTED_MARKER] = {"actor": actor, "at": _iso(moment)}
    ledger.save(run_id, run_ledger)
    return {"event": "run_aborted", "run_id": run_id, "actor": actor, "at": _iso(moment)}


def run_registered_runbook(
    record: Mapping[str, Any],
    *,
    run_id: str,
    authorize: AuthorizationCheck,
    ledger: Any,
    state: MutableMapping[str, Any],
    actor: str = "runbook-engine",
    now: Optional[datetime] = None,
    registry: Optional[Mapping[str, tuple]] = None,
) -> RunOutcome:
    """Convenience wrapper: resolve `record["action_manifest"]["runbook"]`
    through `registry` (defaults to the module-level `STEP_REGISTRY`) and
    call `execute_runbook`. A runbook registered in `approval_request.
    RUNBOOK_REGISTRY` (so it can be requested/approved at all) but with no
    P3 step sequence yet (e.g. `restart-service`) is rejected here with
    `REASON_UNREGISTERED_RUNBOOK` — distinct from an unknown-to-P0-entirely
    runbook, which `AR.validate(record)` already rejects earlier."""
    moment = now or datetime.now(timezone.utc)
    reg = STEP_REGISTRY if registry is None else registry
    manifest = record.get("action_manifest") if isinstance(record, Mapping) else None
    runbook_name = manifest.get("runbook") if isinstance(manifest, Mapping) else None
    steps = reg.get(runbook_name) if isinstance(runbook_name, str) else None
    if steps is None:
        events = [
            {
                "event": "run_rejected",
                "run_id": run_id,
                "at": _iso(moment),
                "reason": REASON_UNREGISTERED_RUNBOOK,
                "detail": str(runbook_name),
            }
        ]
        return RunOutcome(False, REASON_UNREGISTERED_RUNBOOK, tuple(events), tuple())
    return execute_runbook(
        record, steps, run_id=run_id, authorize=authorize, ledger=ledger, state=state, actor=actor, now=moment
    )


# --------------------------------------------------------------------------
# STUB atoms + the 5 registered runbooks' step sequences. Every atom
# operates ONLY on the caller-supplied `state` dict (simulated system state
# — never a real file/socket/process) and the step's scope-projected
# `params`. Atom names are the 4 real atoms the design packet names
# (`aq-provision-signer-key`, `aq-epoch-bump`, `aq-event`, `nixos-rebuild`);
# a later slice swaps each `verify`/`action` pair for a call into the real
# audited AQ action path without changing `RunbookStepSpec`'s shape or
# `execute_runbook`'s contract (mirrors `approval_executor.py`'s stub-to-real
# effect swap note).
# --------------------------------------------------------------------------


def _state_key(prefix: str, params: Mapping[str, Any]) -> str:
    """Deterministic simulated-state key: stable regardless of dict
    insertion order, unique per (prefix, param values) pair."""
    return prefix + "::" + "|".join(f"{k}={params[k]}" for k in sorted(params))


def _make_atom(atom_name: str, state_prefix: str, result_fields: Mapping[str, Any]) -> tuple:
    """Factory for a STUB atom's `(verify, action)` pair. `verify` is the
    idempotency PRE-CHECK (checks simulated `state`, never the engine's own
    ledger — Antigravity revision). `action` performs the stub, in-memory-
    only mutation and returns a deterministic, JSON-safe result dict.
    Neither callable's signature accepts anything beyond `(params, state)` —
    no atom can ever see key material through this factory."""

    def verify(params: Mapping[str, Any], state: MutableMapping[str, Any]) -> bool:
        return bool(state.get(_state_key(state_prefix, params)))

    def action(params: Mapping[str, Any], state: MutableMapping[str, Any]) -> dict:
        state[_state_key(state_prefix, params)] = True
        result = {"atom": atom_name}
        result.update(params)
        result.update(result_fields)
        return result

    return verify, action


def _declarative_atom(atom_name: str, state_prefix: str) -> tuple:
    """STUB atom for a `KIND_DECLARATIVE_UPDATE` step: records that the Nix
    declaration was updated + staged + a rebuild was triggered — Rule 13
    (never a bare transient command). NOT a real `nixos-rebuild` invocation:
    no file write, no subprocess, no systemd call."""
    return _make_atom(
        atom_name, state_prefix, {"nix_declaration_updated": True, "staged": True, "rebuild": "recorded (stub)"}
    )


def _step(runbook: str, effect_name: str, param_names: tuple, *, kind: str, atom: str) -> RunbookStepSpec:
    prefix = f"{runbook}:{effect_name}"
    verify, action = _declarative_atom(atom, prefix) if kind == KIND_DECLARATIVE_UPDATE else _make_atom(
        atom, prefix, {"result": "recorded (stub)"}
    )
    return RunbookStepSpec(
        step_id=f"{runbook}.{effect_name}", kind=kind, atom=atom, effect_name=effect_name,
        param_names=param_names, verify=verify, action=action,
    )


STEP_REGISTRY: dict[str, tuple] = {
    "activate-signer-service": (
        _step("activate-signer-service", "provision-key", ("service",), kind=KIND_ATOM_CALL, atom="aq-provision-signer-key"),
        _step("activate-signer-service", "wire-allowlist", ("service",), kind=KIND_ATOM_CALL, atom="aq-event"),
        _step("activate-signer-service", "emit-grant", ("service",), kind=KIND_ATOM_CALL, atom="aq-event"),
        _step("activate-signer-service", "rebuild", ("service",), kind=KIND_DECLARATIVE_UPDATE, atom="nixos-rebuild"),
    ),
    "rotate-key": (
        _step("rotate-key", "generate-key", ("subject",), kind=KIND_ATOM_CALL, atom="aq-provision-signer-key"),
        _step("rotate-key", "update-config", ("subject",), kind=KIND_ATOM_CALL, atom="aq-event"),
        _step("rotate-key", "revoke-old-key", ("subject",), kind=KIND_ATOM_CALL, atom="aq-epoch-bump"),
        _step("rotate-key", "confirm-sessions", ("subject",), kind=KIND_ATOM_CALL, atom="aq-event"),
    ),
    "epoch-revoke": (
        _step("epoch-revoke", "identify-epoch", ("epoch_scope",), kind=KIND_ATOM_CALL, atom="aq-event"),
        _step("epoch-revoke", "revoke-epoch", ("epoch_scope",), kind=KIND_ATOM_CALL, atom="aq-epoch-bump"),
        _step("epoch-revoke", "propagate-revoke", ("epoch_scope",), kind=KIND_ATOM_CALL, atom="aq-event"),
        _step("epoch-revoke", "verify-revoke", ("epoch_scope",), kind=KIND_ATOM_CALL, atom="aq-event"),
    ),
    "emit-grant": (
        _step("emit-grant", "define-scope", ("grant_subject",), kind=KIND_ATOM_CALL, atom="aq-event"),
        _step("emit-grant", "generate-grant-id", ("grant_subject",), kind=KIND_ATOM_CALL, atom="aq-event"),
        _step("emit-grant", "record-grant", ("grant_subject",), kind=KIND_ATOM_CALL, atom="aq-event"),
        _step("emit-grant", "confirm-grant", ("grant_subject",), kind=KIND_ATOM_CALL, atom="aq-event"),
    ),
    "activate-foundation-c-slice": (
        _step("activate-foundation-c-slice", "check-deps", ("slice",), kind=KIND_ATOM_CALL, atom="aq-event"),
        _step("activate-foundation-c-slice", "load-config", ("slice",), kind=KIND_ATOM_CALL, atom="aq-event"),
        _step("activate-foundation-c-slice", "activate-slice", ("slice",), kind=KIND_DECLARATIVE_UPDATE, atom="nixos-rebuild"),
        _step("activate-foundation-c-slice", "verify-health", ("slice",), kind=KIND_ATOM_CALL, atom="aq-event"),
    ),
}


def _validate_registry() -> None:
    """Import-time self-check: every registered runbook's step `effect_name`
    sequence equals its `approval_request.RunbookSpec.declared_effects`
    tuple exactly, in order, and every step's `param_names` is a subset of
    that runbook's `param_schema` keys. A registry that fails this can never
    ship — this is defense-in-depth on TOP of the run-time
    `_validate_step_scope` check (which guards a caller-supplied `steps`
    sequence, not just this module's own registry)."""
    for runbook, steps in STEP_REGISTRY.items():
        spec = AR.RUNBOOK_REGISTRY.get(runbook)
        assert spec is not None, f"STEP_REGISTRY[{runbook!r}] has no matching approval_request.RUNBOOK_REGISTRY entry"
        effect_sequence = tuple(s.effect_name for s in steps)
        assert effect_sequence == spec.declared_effects, (
            f"{runbook}: step effect order {effect_sequence} != declared_effects {spec.declared_effects}"
        )
        allowed_params = set(spec.param_schema.keys())
        for step in steps:
            assert set(step.param_names).issubset(allowed_params), (
                f"{runbook}.{step.step_id}: param_names {step.param_names} not subset of {allowed_params}"
            )
            assert step.kind in STEP_KINDS, f"{runbook}.{step.step_id}: unknown kind {step.kind!r}"


_validate_registry()
