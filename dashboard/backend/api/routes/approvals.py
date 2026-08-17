"""Approval Control Plane P2 — the approval SURFACE core (backend route).

Implements `.agents/plans/approval-control-plane/ACP-P2-DESIGN-20260816.md`
(authoritative, including its "Review fold — Antigravity + local" section)
using the copy/CSP/error-map materialized in
`.agents/plans/approval-control-plane/ACP-PREP-COPY-20260816.md`. Builds on
the P0 record substrate (`scripts/ai/lib/approval_request.py`) and the P1
signing-service core (`scripts/ai/lib/approval_signer.py`).

This module is a VIEW + a thin route layer, never a second authority:
  - `GET /approvals`            — Layer-1 ONLY pending cards (title/what/why/
    impact/reversible). NEVER emits `technical_trail`/`binding`/hashes/paths.
    `response_model=list[PendingApprovalCard]` enforces this structurally —
    even a bug in `_project_layer1` cannot leak an extra field past Pydantic.
  - `GET /approvals/{request_id}` — Layer-3 details (Details drill-in only).
  - `POST /approvals/{request_id}/challenge` — begins the WebAuthn ceremony
    via the injected `SignerClient` (P1 signer contract); returns the
    challenge bytes the BROWSER needs to call `navigator.credentials.get()`.
  - `POST /approvals/{request_id}/approve` — the ONLY caller-supplied thing
    accepted is the browser's WebAuthn assertion; `ApproveRequest` has no
    bytes/hash/key field and `extra='forbid'` rejects anything smuggled in.
    This route NEVER computes or forwards `canonical_hash` itself — that is
    the (injected) signer's job, exactly as the design's approve flow
    requires ("surface calls acp-signer... NEVER handles the challenge, the
    assertion, or any key").
  - `POST /approvals/{request_id}/deny` — pending -> denied, no assertion.
  - `GET /approve` (`view_router`) — serves the static approval view
    (`static/approve.html`) with the prep doc's verbatim kiosk CSP header.

Record source + signer are INJECTED interfaces (`ApprovalStore`,
`SignerClient` — both `typing.Protocol`), never a live store/service: this
module ships `FixtureApprovalStore`/`FixtureSignerClient` (offline, no
crypto, no disk state beyond the golden fixtures) as its default wiring so
the router works standalone for tests/demos. `configure_store()` /
`configure_signer()` let a future deployment swap in a real projection over
the operator-context store and a real adapter around
`approval_signer.ApprovalSigner` — that wiring, the confined kiosk browser
session, and the systemd/Nix units are deployment-layer work, NOT built
here (scope fence, ACP-P2-DESIGN "Scope fence").

Wiring note for whoever activates this (default-OFF — `dashboard/backend/
api/main.py` does not `include_router()` either router here yet):
    app.include_router(approvals.router, prefix="/api", tags=["approvals"])
    app.include_router(approvals.view_router)
giving `/api/approvals/*` (JSON) and `/approve` (the kiosk-launched view),
matching the prep doc's kiosk launch command
(`chromium --kiosk http://127.0.0.1:<APPROVE_PORT>/approve`).
"""

from __future__ import annotations

import base64
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Protocol

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field

# --------------------------------------------------------------------------
# Predecessor libraries (P0 record substrate + P1 signer contract) live
# under scripts/ai/lib, outside the dashboard backend's own package tree —
# same sys.path pattern api/routes/collaboration.py uses for scripts/ai/lib
# (the agents lib) at the same directory depth.
# --------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[4]
_LIB_DIR = _REPO_ROOT / "scripts" / "ai" / "lib"
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

import approval_request as AR  # noqa: E402
import approval_signer as AS  # noqa: E402

# --------------------------------------------------------------------------
# Response/request models (Pydantic response_model IS the structural privacy
# guarantee for the Layer-1 list — see module docstring).
# --------------------------------------------------------------------------


class PendingApprovalCard(BaseModel):
    """Layer-1 ONLY. Must never gain a technical_trail/binding/hash field."""

    request_id: str
    title: str
    what: str
    why: str
    impact: str
    reversible: bool
    status: str
    created_at: str


class ApprovalDetails(BaseModel):
    """Layer-3 drill-in — the full `aq.approval-request.v1` record, shown
    only when the human explicitly opens Details."""

    model_config = ConfigDict(populate_by_name=True)

    schema_: str = Field(alias="schema")
    request_id: str
    created_at: str
    created_by: str
    status: str
    summary: Dict[str, Any]
    required_authority: str
    action_manifest: Dict[str, Any]
    technical_trail: Dict[str, Any]
    binding: Dict[str, Any]


class ApproveRequest(BaseModel):
    """The ONLY thing the surface may send to approve: the browser's WebAuthn
    assertion. No bytes, no hash, no key field exists here, and `extra`
    is forbidden so nothing can be smuggled in alongside it."""

    model_config = ConfigDict(extra="forbid")

    assertion: Dict[str, Any] = Field(default_factory=dict)


class DenyRequest(BaseModel):
    """Deny needs no assertion — just who denied it."""

    model_config = ConfigDict(extra="forbid")

    actor: str = "owner"


class StatusResponse(BaseModel):
    request_id: str
    status: str


class ChallengeResponse(BaseModel):
    request_id: str
    challenge: str
    rp_id: str
    timeout_ms: int
    allow_credentials: List[str] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Plain-language error map — VERBATIM from ACP-PREP-COPY-20260816.md
# "Plain-language WebAuthn/signer error map (for P2)". Do not paraphrase;
# any wording change must land in the prep doc + here together.
# --------------------------------------------------------------------------


class ErrorCard(BaseModel):
    code: str
    plain_title: str
    plain_body: str
    physical_action: str


_ERROR_MAP_ENTRIES: List[Dict[str, str]] = [
    {"code": "no_authenticator", "plain_title": "No security key found", "plain_body": "We couldn't find a security key or fingerprint reader.", "physical_action": "Plug in your security key, then try again."},
    {"code": "user_verification_failed", "plain_title": "Couldn't verify it's you", "plain_body": "Your fingerprint or PIN didn't match.", "physical_action": "Try your fingerprint or PIN again."},
    {"code": "ceremony_timeout", "plain_title": "Timed out waiting", "plain_body": "We stopped waiting for you to tap your key.", "physical_action": "Tap Approve again and touch your key when it lights up."},
    {"code": "unregistered_key", "plain_title": "Key not recognized", "plain_body": "This security key isn't set up for this system.", "physical_action": "Use the key you registered, or add this one in Settings."},
    {"code": "challenge_expired", "plain_title": "Request expired", "plain_body": "This approval sat too long and is no longer valid.", "physical_action": "Start the approval again from the list."},
    {"code": "signature_invalid", "plain_title": "Approval didn't go through", "plain_body": "The system couldn't confirm your approval.", "physical_action": "Try approving again; if it repeats, contact your admin."},
    {"code": "already_completed", "plain_title": "Already done", "plain_body": "This request was already approved and carried out.", "physical_action": "No action needed — you can close this."},
    {"code": "connection_lost", "plain_title": "Connection lost", "plain_body": "We lost the connection to the system.", "physical_action": "Wait a moment for it to reconnect before approving."},
    {"code": "request_expired", "plain_title": "Request expired", "plain_body": "This request timed out before anyone approved it.", "physical_action": "Ask for a new request if you still need it."},
    {"code": "internal_error", "plain_title": "Something went wrong", "plain_body": "An unexpected problem stopped this approval.", "physical_action": "Try again; if it keeps happening, contact your admin."},
    # P2-authored addition — not in the prep verbatim set. The prep map
    # covers WebAuthn/signer faults only; an unknown request_id (stale list,
    # bad link) needs its own plain card so the route never falls back to a
    # raw 404 body.
    {"code": "request_not_found", "plain_title": "Request not found", "plain_body": "We couldn't find this approval request.", "physical_action": "Refresh the list and try again."},
]

ERROR_MAP: Dict[str, Dict[str, str]] = {entry["code"]: entry for entry in _ERROR_MAP_ENTRIES}


def _error_card(code: str) -> Dict[str, str]:
    return ERROR_MAP.get(code, ERROR_MAP["internal_error"])


# `approval_signer.DENY_*` reason -> plain error-map code. Every reason the
# real P1 module can return is covered so a live signer never surfaces a raw
# reason string to a human.
_REASON_TO_CODE: Dict[str, str] = {
    AS.DENY_INVALID_REQUEST_ID: "request_not_found",
    AS.DENY_NOT_FOUND: "request_not_found",
    AS.DENY_RECORD_INVALID: "internal_error",
    AS.DENY_HASH_DRIFT: "internal_error",
    AS.DENY_EXECUTED_REPLAY: "already_completed",
    AS.DENY_CHALLENGE_REPLAY: "already_completed",
    AS.DENY_NO_PENDING_CHALLENGE: "challenge_expired",
    AS.DENY_CHALLENGE_EXPIRED: "challenge_expired",
    AS.DENY_ASSERTION_MISSING: "no_authenticator",
    AS.DENY_ASSERTION_MALFORMED: "internal_error",
    AS.DENY_ASSERTION_INVALID: "signature_invalid",
    AS.DENY_UNKNOWN_CREDENTIAL: "unregistered_key",
    AS.DENY_CREDENTIAL_NOT_ACTIVE: "unregistered_key",
    AS.DENY_CLONE_SUSPECTED: "signature_invalid",
    AS.DENY_ALLOWLIST_UNAVAILABLE: "internal_error",
    AS.DENY_LEDGER_UNAVAILABLE: "internal_error",
    AS.DENY_RATE_LIMITED: "internal_error",
    AS.DENY_CONCURRENT_SESSION: "internal_error",
    AS.DENY_INTERNAL: "internal_error",
}


def _map_reason(reason: str) -> str:
    return _REASON_TO_CODE.get(reason, "internal_error")


# --------------------------------------------------------------------------
# Injected interfaces — the record SOURCE and the P1 signer are never live
# here (design "Scope fence": "no P1 service internals", "the record SOURCE
# is an injected loader interface"). A future deployment calls
# `configure_store`/`configure_signer` with real implementations.
# --------------------------------------------------------------------------


class ApprovalStoreError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class ApprovalStore(Protocol):
    def list_pending(self) -> List[dict]: ...

    def get(self, request_id: str) -> Optional[dict]: ...

    def transition(self, request_id: str, new_status: str, *, actor: str) -> dict: ...


@dataclass(frozen=True)
class ChallengeResult:
    ok: bool
    reason: str
    challenge_b64: Optional[str] = None
    rp_id: Optional[str] = None
    timeout_ms: Optional[int] = None
    allow_credentials: tuple = ()


@dataclass(frozen=True)
class SignResult:
    ok: bool
    reason: str
    status: Optional[str] = None


class SignerClient(Protocol):
    def begin_challenge(self, request_id: str) -> ChallengeResult: ...

    def sign_request(self, request_id: str, assertion: Mapping[str, Any]) -> SignResult: ...


# --------------------------------------------------------------------------
# FixtureApprovalStore — offline default, seeded from the prep doc's golden
# fixtures adapted to the two runbooks actually registered in
# `approval_request.RUNBOOK_REGISTRY` (`activate-signer-service`,
# `restart-service`). The prep doc's `epoch-revoke`/`emit-grant` names are
# NOT registered runbooks — adding them is P0/P3 registry scope, not P2.
# --------------------------------------------------------------------------


def _default_fixture_records() -> List[dict]:
    return [
        AR.create_request(
            request_id="01J8K9M2N3P4Q5R6S7T8U9V0W1",
            created_by="fixture-seed",
            runbook="activate-signer-service",
            params={"service": "aidb"},
        ),
        AR.create_request(
            request_id="01J8K9M2N3P4Q5R6S7T8U9V0X2",
            created_by="fixture-seed",
            runbook="restart-service",
            params={"service": "hybrid-coordinator"},
        ),
        AR.create_request(
            request_id="01J8K9M2N3P4Q5R6S7T8U9V0Y3",
            created_by="fixture-seed",
            runbook="restart-service",
            params={"service": "switchboard"},
        ),
    ]


class FixtureApprovalStore:
    """In-memory `ApprovalStore` — FIXTURE/DEMO ONLY. A live deployment
    replaces this via `configure_store()` with a real projection over the
    operator-context store (design integration contract #1)."""

    def __init__(self, records: Optional[List[dict]] = None) -> None:
        seed = records if records is not None else _default_fixture_records()
        self._records: Dict[str, dict] = {r["request_id"]: r for r in seed}

    def list_pending(self) -> List[dict]:
        return [r for r in self._records.values() if r["status"] == AR.STATUS_PENDING]

    def get(self, request_id: str) -> Optional[dict]:
        return self._records.get(request_id)

    def transition(self, request_id: str, new_status: str, *, actor: str) -> dict:
        record = self._records.get(request_id)
        if record is None:
            raise ApprovalStoreError("not-found")
        new_record, _event = AR.transition(record, new_status, actor=actor)
        self._records[request_id] = new_record
        return new_record


class FixtureSignerClient:
    """Deterministic, offline stand-in for the P1 WebAuthn signer — FIXTURE/
    DEMO ONLY, holds no key material and performs no real crypto.
    `sign_request` reads an optional `_outcome` field from the caller-
    supplied `assertion` dict: `"success"` (default) signs; any
    `approval_signer.DENY_*` string denies with that reason — this is what
    lets the route/error-map tests exercise every denial path deterministically.
    A live deployment replaces this via `configure_signer()` with a real
    adapter around `approval_signer.ApprovalSigner`."""

    def __init__(self, store: ApprovalStore, *, rp_id: str = "localhost") -> None:
        self._store = store
        self._rp_id = rp_id

    def begin_challenge(self, request_id: str) -> ChallengeResult:
        record = self._store.get(request_id)
        if record is None:
            return ChallengeResult(False, AS.DENY_NOT_FOUND)
        if record["status"] != AR.STATUS_PENDING:
            return ChallengeResult(False, AS.DENY_EXECUTED_REPLAY)
        challenge = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode("ascii")
        return ChallengeResult(
            True,
            AS.CHALLENGE_OK,
            challenge_b64=challenge,
            rp_id=self._rp_id,
            timeout_ms=60_000,
            allow_credentials=(),
        )

    def sign_request(self, request_id: str, assertion: Mapping[str, Any]) -> SignResult:
        if not assertion:
            return SignResult(False, AS.DENY_ASSERTION_MISSING)
        outcome = assertion.get("_outcome", "success")
        if outcome == "success":
            return SignResult(True, AS.SIGN_OK, status=AR.STATUS_APPROVED)
        return SignResult(False, str(outcome))


_store: ApprovalStore = FixtureApprovalStore()
_signer: SignerClient = FixtureSignerClient(_store)


def configure_store(store: ApprovalStore) -> None:
    """Swap in a live `ApprovalStore` (deployment layer, not built here)."""
    global _store
    _store = store


def configure_signer(signer: SignerClient) -> None:
    """Swap in a live `SignerClient` wrapping the real P1
    `approval_signer.ApprovalSigner` (deployment layer, not built here)."""
    global _signer
    _signer = signer


def get_store() -> ApprovalStore:
    return _store


def get_signer() -> SignerClient:
    return _signer


def _project_layer1(record: Mapping[str, Any]) -> Dict[str, Any]:
    summary = record["summary"]
    return {
        "request_id": record["request_id"],
        "title": summary["title"],
        "what": summary["what"],
        "why": summary["why"],
        "impact": summary["impact"],
        "reversible": summary["reversible"],
        "status": record["status"],
        "created_at": record["created_at"],
    }


# --------------------------------------------------------------------------
# JSON API router — mount at prefix "/api" (see module docstring wiring note).
# --------------------------------------------------------------------------

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("", response_model=List[PendingApprovalCard])
async def list_pending_approvals() -> List[dict]:
    """Layer-1 ONLY. `response_model` is the structural privacy guarantee."""
    return [_project_layer1(r) for r in _store.list_pending()]


@router.get("/{request_id}", response_model=ApprovalDetails)
async def get_approval_details(request_id: str):
    """Layer-3 Details drill-in — the full record, never shown by default."""
    record = _store.get(request_id)
    if record is None:
        raise HTTPException(status_code=404, detail=_error_card("request_not_found"))
    verdict = AR.validate(record)
    if not verdict.ok:
        raise HTTPException(status_code=500, detail=_error_card("internal_error"))
    return record


@router.post("/{request_id}/challenge", response_model=ChallengeResponse)
async def begin_approval_challenge(request_id: str):
    """Step 1 of approve: derive the WebAuthn challenge the browser needs
    for `navigator.credentials.get()`. Delegates entirely to the injected
    signer — this route never derives or inspects `canonical_hash` itself."""
    record = _store.get(request_id)
    if record is None:
        raise HTTPException(status_code=404, detail=_error_card("request_not_found"))
    if record["status"] != AR.STATUS_PENDING:
        raise HTTPException(status_code=409, detail=_error_card("already_completed"))

    result = _signer.begin_challenge(request_id)
    if not result.ok:
        raise HTTPException(status_code=409, detail=_error_card(_map_reason(result.reason)))
    return {
        "request_id": request_id,
        "challenge": result.challenge_b64,
        "rp_id": result.rp_id,
        "timeout_ms": result.timeout_ms,
        "allow_credentials": list(result.allow_credentials or ()),
    }


@router.post("/{request_id}/approve", response_model=StatusResponse)
async def approve_request(request_id: str, body: ApproveRequest):
    """Step 2 of approve. The ONLY caller-supplied input is `request_id`
    (path) + `body.assertion` (the browser's WebAuthn assertion) — never
    bytes/hash/key. Delegates verification to the injected signer; this
    route only transitions the record on a genuine `SignResult.ok`."""
    record = _store.get(request_id)
    if record is None:
        raise HTTPException(status_code=404, detail=_error_card("request_not_found"))
    if not body.assertion:
        raise HTTPException(status_code=422, detail=_error_card("no_authenticator"))

    result = _signer.sign_request(request_id, body.assertion)
    if not result.ok:
        raise HTTPException(status_code=422, detail=_error_card(_map_reason(result.reason)))

    try:
        new_record = _store.transition(request_id, AR.STATUS_APPROVED, actor="owner-webauthn")
    except (AR.ApprovalStateError, ApprovalStoreError):
        raise HTTPException(status_code=409, detail=_error_card("already_completed"))
    return {"request_id": request_id, "status": new_record["status"]}


@router.post("/{request_id}/deny", response_model=StatusResponse)
async def deny_request(request_id: str, body: DenyRequest):
    """pending -> denied. No assertion, no signer call."""
    record = _store.get(request_id)
    if record is None:
        raise HTTPException(status_code=404, detail=_error_card("request_not_found"))
    try:
        new_record = _store.transition(request_id, AR.STATUS_DENIED, actor=body.actor)
    except (AR.ApprovalStateError, ApprovalStoreError):
        raise HTTPException(status_code=409, detail=_error_card("already_completed"))
    return {"request_id": request_id, "status": new_record["status"]}


# --------------------------------------------------------------------------
# Static approval view — mount at root (see module docstring wiring note).
# Kiosk launch (systemd-run + dedicated uid + ephemeral profile) is the
# deployment layer and is documented, NOT built, here — see
# ACP-PREP-COPY-20260816.md "Kiosk CSP + launch" and `static/approve.html`'s
# header comment.
# --------------------------------------------------------------------------

view_router = APIRouter(tags=["approvals-view"], include_in_schema=False)

_STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"
_APPROVE_VIEW_PATH = _STATIC_DIR / "approve.html"

# VERBATIM from ACP-PREP-COPY-20260816.md "Kiosk CSP + launch — local
# `caijxh`, verified". Do not paraphrase or relax any directive without
# updating the prep doc + this comment together.
APPROVE_VIEW_CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
    "frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self';"
)


@view_router.get("/approve")
async def approve_view() -> HTMLResponse:
    html = _APPROVE_VIEW_PATH.read_text(encoding="utf-8")
    return HTMLResponse(content=html, headers={"Content-Security-Policy": APPROVE_VIEW_CSP})
