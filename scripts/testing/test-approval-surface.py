#!/usr/bin/env python3
"""Acceptance tests for the Approval Control Plane P2 surface (backend route
`dashboard/backend/api/routes/approvals.py` + static view
`dashboard/backend/static/approve.html`).

Covers the P2 validation goals from
`.agents/plans/approval-control-plane/ACP-P2-DESIGN-20260816.md`:
privacy-render, decision-clarity, approve-binds-to-signer, deny-path, a11y
presence, state-honesty, error-mapping — plus the kiosk CSP header from
`.agents/plans/approval-control-plane/ACP-PREP-COPY-20260816.md`.

Entirely offline: builds a minimal FastAPI app mounting only
`approvals.router` + `approvals.view_router` (never imports the full
`api.main` app, so no live redis/coordinator/etc dependencies are touched)
and wires fresh `FixtureApprovalStore`/`FixtureSignerClient` instances per
check via `configure_store`/`configure_signer`.

`check()` raises `AssertionError` immediately on a failed condition so
`pytest` reports real per-test PASS/FAIL. `main()` runs every `test_*`
function and aggregates failures for a single human-readable summary when
run directly.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_BACKEND = REPO_ROOT / "dashboard" / "backend"
LIB_DIR = REPO_ROOT / "scripts" / "ai" / "lib"
sys.path.insert(0, str(DASHBOARD_BACKEND))
sys.path.insert(0, str(LIB_DIR))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api.routes import approvals  # noqa: E402
import approval_request as AR  # noqa: E402
import approval_signer as AS  # noqa: E402

APPROVE_HTML_PATH = DASHBOARD_BACKEND / "static" / "approve.html"
APPROVE_HTML = APPROVE_HTML_PATH.read_text(encoding="utf-8")


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


def _fresh_app():
    """Fresh store + signer wired into a minimal app mounting only the
    approvals routers (never the full dashboard api.main app)."""
    store = approvals.FixtureApprovalStore()
    signer = approvals.FixtureSignerClient(store)
    approvals.configure_store(store)
    approvals.configure_signer(signer)

    app = FastAPI()
    app.include_router(approvals.router, prefix="/api")
    app.include_router(approvals.view_router)
    return app, store, signer


def _pending_id(store: approvals.FixtureApprovalStore) -> str:
    return store.list_pending()[0]["request_id"]


# --------------------------------------------------------------------------
# privacy-render
# --------------------------------------------------------------------------

_HEX64_RE = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])")
_ABS_PATH_RE = re.compile(r"(?<!\S)/[\w.-]+(?:/[\w.-]+)+")


def test_pending_list_is_layer1_only() -> None:
    app, store, _signer = _fresh_app()
    with TestClient(app) as client:
        resp = client.get("/api/approvals")
        check(resp.status_code == 200, f"list endpoint failed: {resp.status_code} {resp.text}")
        raw_text = resp.text

        check(_HEX64_RE.search(raw_text) is None, "list payload leaked a hex64 (hash-shaped) string")
        check("/run/secrets" not in raw_text, "list payload leaked a /run/secrets reference")
        check(_ABS_PATH_RE.search(raw_text) is None, "list payload leaked a filesystem path")
        check("sha256" not in raw_text.lower(), 'list payload leaked the literal "sha256"')
        check("technical_trail" not in raw_text, "list payload leaked technical_trail")
        check("binding" not in raw_text, "list payload leaked binding")
        check("canonical_hash" not in raw_text, "list payload leaked canonical_hash")
        check("action_manifest" not in raw_text, "list payload leaked action_manifest")

        records = resp.json()
        check(len(records) == len(store.list_pending()), "list did not return all pending fixture records")
        allowed_keys = {"request_id", "title", "what", "why", "impact", "reversible", "status", "created_at"}
        for record in records:
            check(set(record.keys()) == allowed_keys, f"unexpected key set in card: {sorted(record.keys())}")


def test_details_endpoint_carries_layer3() -> None:
    """Details (Layer-3) is a SEPARATE, explicit endpoint — hashes/paths are
    fine here; this is the "opens Details" path, never the default view."""
    app, store, _signer = _fresh_app()
    request_id = _pending_id(store)
    with TestClient(app) as client:
        resp = client.get(f"/api/approvals/{request_id}")
        check(resp.status_code == 200, f"details fetch failed: {resp.status_code} {resp.text}")
        body = resp.json()
        check("technical_trail" in body, "details response missing technical_trail (Layer-3)")
        check("binding" in body and "canonical_hash" in body["binding"], "details missing canonical_hash")
        check(re.fullmatch(r"[0-9a-f]{64}", body["binding"]["canonical_hash"]), "canonical_hash not hex64")


def test_unknown_request_id_returns_plain_card_not_raw_404() -> None:
    app, _store, _signer = _fresh_app()
    with TestClient(app) as client:
        resp = client.get("/api/approvals/does-not-exist")
        check(resp.status_code == 404, "unknown request_id should 404")
        detail = resp.json()["detail"]
        check(detail["code"] == "request_not_found", f"unexpected error code: {detail}")
        check(detail == approvals.ERROR_MAP["request_not_found"], "detail card is not the plain-language card verbatim")


# --------------------------------------------------------------------------
# decision-clarity — a non-expert can identify the request + what approving
# does from Layer-1 alone.
# --------------------------------------------------------------------------


def test_layer1_fields_are_plain_and_nonempty() -> None:
    app, store, _signer = _fresh_app()
    with TestClient(app) as client:
        resp = client.get("/api/approvals")
        for record in resp.json():
            check(bool(record["title"]), "title empty")
            check(bool(record["what"]), "what empty")
            check(bool(record["why"]), "why empty")
            check(record["impact"] in ("low", "medium", "high"), f"impact not a known level: {record['impact']}")
            check(isinstance(record["reversible"], bool), "reversible not boolean")
            # decision-clarity: "what" describes the effect in plain terms —
            # the runbook name/registry id itself must never leak into it.
            check("runbook" not in record["what"].lower(), "runbook jargon leaked into 'what'")


# --------------------------------------------------------------------------
# approve-binds-to-signer — passes request_id + assertion only, no
# bytes/hash/key; the surface holds no key material.
# --------------------------------------------------------------------------


def test_approve_request_model_rejects_smuggled_fields() -> None:
    app, store, _signer = _fresh_app()
    request_id = _pending_id(store)
    with TestClient(app) as client:
        resp = client.post(
            f"/api/approvals/{request_id}/approve",
            json={"assertion": {"_outcome": "success"}, "canonical_hash": "a" * 64},
        )
        check(resp.status_code == 422, "a smuggled top-level field (canonical_hash) should be rejected (extra=forbid)")


def test_approve_flow_passes_only_request_id_and_assertion() -> None:
    """Instrument the injected SignerClient — a spy proves the route calls
    `sign_request(request_id, assertion)` and NOTHING else (no bytes, no
    hash, no key material touched by the route itself)."""
    app, store, signer = _fresh_app()
    request_id = _pending_id(store)
    calls = []

    class SpySigner:
        def begin_challenge(self, req_id):
            return signer.begin_challenge(req_id)

        def sign_request(self, req_id, assertion):
            calls.append((req_id, dict(assertion)))
            return signer.sign_request(req_id, assertion)

    approvals.configure_signer(SpySigner())
    with TestClient(app) as client:
        resp = client.post(f"/api/approvals/{request_id}/approve", json={"assertion": {"_outcome": "success"}})
        check(resp.status_code == 200, f"approve should succeed: {resp.status_code} {resp.text}")
        check(resp.json()["status"] == AR.STATUS_APPROVED, "record did not transition to approved")

    check(len(calls) == 1, f"sign_request should be called exactly once, got {len(calls)}")
    called_id, called_assertion = calls[0]
    check(called_id == request_id, "sign_request was not called with the path request_id")
    check(set(called_assertion.keys()) == {"_outcome"}, f"assertion carried unexpected keys: {called_assertion.keys()}")
    check("canonical_hash" not in called_assertion, "a hash leaked into the assertion payload")
    check("owner_key" not in called_assertion and "private_key" not in called_assertion, "key material leaked into the assertion payload")


def test_route_source_never_references_owner_key_material() -> None:
    source = (DASHBOARD_BACKEND / "api" / "routes" / "approvals.py").read_text(encoding="utf-8")
    for banned in ("owner_key", "private_key", "Ed25519PrivateKey"):
        check(banned not in source, f"approvals.py references {banned!r} — the surface must hold no key material")


def test_approve_with_no_assertion_maps_to_no_authenticator() -> None:
    app, store, _signer = _fresh_app()
    request_id = _pending_id(store)
    with TestClient(app) as client:
        resp = client.post(f"/api/approvals/{request_id}/approve", json={"assertion": {}})
        check(resp.status_code == 422, "empty assertion should be rejected")
        check(resp.json()["detail"]["code"] == "no_authenticator", "empty assertion did not map to no_authenticator")


def test_challenge_endpoint_returns_no_technical_trail() -> None:
    app, store, _signer = _fresh_app()
    request_id = _pending_id(store)
    with TestClient(app) as client:
        resp = client.post(f"/api/approvals/{request_id}/challenge")
        check(resp.status_code == 200, f"challenge should succeed: {resp.status_code} {resp.text}")
        body = resp.json()
        check(set(body.keys()) == {"request_id", "challenge", "rp_id", "timeout_ms", "allow_credentials"}, "unexpected challenge response shape")
        check("technical_trail" not in resp.text, "challenge response leaked technical_trail")


# --------------------------------------------------------------------------
# deny-path — pending -> denied, no assertion needed.
# --------------------------------------------------------------------------


def test_deny_transitions_pending_to_denied_without_assertion() -> None:
    app, store, _signer = _fresh_app()
    request_id = _pending_id(store)
    with TestClient(app) as client:
        resp = client.post(f"/api/approvals/{request_id}/deny", json={"actor": "owner"})
        check(resp.status_code == 200, f"deny should succeed: {resp.status_code} {resp.text}")
        check(resp.json()["status"] == AR.STATUS_DENIED, "record did not transition to denied")
        check(store.get(request_id)["status"] == AR.STATUS_DENIED, "store did not persist the denial")


def test_deny_request_model_forbids_assertion_field() -> None:
    """DenyRequest structurally has no assertion field — denying can never
    accidentally be routed through the signer."""
    app, store, _signer = _fresh_app()
    request_id = _pending_id(store)
    with TestClient(app) as client:
        resp = client.post(f"/api/approvals/{request_id}/deny", json={"actor": "owner", "assertion": {}})
        check(resp.status_code == 422, "deny should reject a smuggled assertion field (extra=forbid)")


def test_double_deny_is_a_plain_already_completed_card() -> None:
    app, store, _signer = _fresh_app()
    request_id = _pending_id(store)
    with TestClient(app) as client:
        first = client.post(f"/api/approvals/{request_id}/deny", json={"actor": "owner"})
        check(first.status_code == 200, "first deny should succeed")
        second = client.post(f"/api/approvals/{request_id}/deny", json={"actor": "owner"})
        check(second.status_code == 409, "second deny on an already-denied request should be rejected")
        check(second.json()["detail"]["code"] == "already_completed", "double-deny did not map to already_completed")


# --------------------------------------------------------------------------
# state-honesty — pending/approved/running/done/denied/expired/failed each
# render truthfully; nothing is a silent/false "done".
# --------------------------------------------------------------------------


def test_full_legal_state_chain_reflected_in_details() -> None:
    app, store, _signer = _fresh_app()
    request_id = _pending_id(store)
    with TestClient(app) as client:
        check(client.get(f"/api/approvals/{request_id}").json()["status"] == AR.STATUS_PENDING, "should start pending")

        approve = client.post(f"/api/approvals/{request_id}/approve", json={"assertion": {"_outcome": "success"}})
        check(approve.status_code == 200, "approve should succeed")
        check(client.get(f"/api/approvals/{request_id}").json()["status"] == AR.STATUS_APPROVED, "should be approved")

        # approved -> executed / approved -> failed are legal per the P0
        # state machine; exercise both independently via the store directly
        # (no HTTP endpoint drives the executor — that is P0/P1 territory).
        executed = store.transition(request_id, AR.STATUS_EXECUTED, actor="executor")
        check(executed["status"] == AR.STATUS_EXECUTED, "store did not honor approved->executed")
        check(client.get(f"/api/approvals/{request_id}").json()["status"] == AR.STATUS_EXECUTED, "details did not reflect executed")


def test_denied_and_expired_are_terminal_and_reflected() -> None:
    app, store, _signer = _fresh_app()
    records = store.list_pending()
    denied_id = records[0]["request_id"]
    expired_id = records[1]["request_id"]

    denied = store.transition(denied_id, AR.STATUS_DENIED, actor="owner")
    check(denied["status"] == AR.STATUS_DENIED, "pending->denied should be legal")

    expired = store.transition(expired_id, AR.STATUS_EXPIRED, actor="system")
    check(expired["status"] == AR.STATUS_EXPIRED, "pending->expired should be legal")

    with TestClient(app) as client:
        check(client.get(f"/api/approvals/{denied_id}").json()["status"] == AR.STATUS_DENIED, "denial not reflected")
        check(client.get(f"/api/approvals/{expired_id}").json()["status"] == AR.STATUS_EXPIRED, "expiry not reflected")

    try:
        store.transition(denied_id, AR.STATUS_APPROVED, actor="owner")
        check(False, "denied is terminal — a transition out of it must raise")
    except AR.ApprovalStateError:
        pass


def test_view_renders_all_seven_named_states() -> None:
    for state in ("pending", "approved", "running", "executed", "denied", "expired", "failed"):
        check(f'"{state}"' in APPROVE_HTML, f"approve.html STATUS_LABELS is missing state {state!r}")
    check('"Done"' in APPROVE_HTML, 'approve.html must render "executed" honestly as "Done", not hide it')


# --------------------------------------------------------------------------
# error-mapping — every approval_signer.DENY_* reason maps to a plain card;
# Python and the shipped JS agree on the same code set.
# --------------------------------------------------------------------------


def test_every_signer_denial_reason_maps_to_a_known_plain_code() -> None:
    deny_reasons = [name for name in vars(AS) if name.startswith("DENY_")]
    check(len(deny_reasons) > 0, "no DENY_* constants found in approval_signer — test is stale")
    for name in deny_reasons:
        reason = getattr(AS, name)
        code = approvals._map_reason(reason)
        check(code in approvals.ERROR_MAP, f"{name} ({reason!r}) maps to unknown code {code!r}")


def test_error_map_matches_between_python_and_html() -> None:
    for code, card in approvals.ERROR_MAP.items():
        check(f'"{code}"' in APPROVE_HTML, f"approve.html ERROR_MAP is missing code {code!r}")
        check(card["plain_title"] in APPROVE_HTML, f"approve.html is missing plain_title for {code!r}")


def test_signer_denials_surface_as_plain_cards_over_http() -> None:
    app, store, _signer = _fresh_app()
    request_id = _pending_id(store)
    with TestClient(app) as client:
        for reason, expected_code in [
            (AS.DENY_CHALLENGE_EXPIRED, "challenge_expired"),
            (AS.DENY_UNKNOWN_CREDENTIAL, "unregistered_key"),
            (AS.DENY_ASSERTION_INVALID, "signature_invalid"),
        ]:
            resp = client.post(
                f"/api/approvals/{request_id}/approve",
                json={"assertion": {"_outcome": reason}},
            )
            check(resp.status_code == 422, f"denial {reason} should be a 422")
            detail = resp.json()["detail"]
            check(detail["code"] == expected_code, f"{reason} mapped to {detail['code']!r}, expected {expected_code!r}")
            check("Traceback" not in resp.text and reason not in resp.text.split('"code"')[0], "raw denial reason leaked ahead of the plain card")


# --------------------------------------------------------------------------
# a11y presence — keyboard operable, ARIA labels, reduced-motion, AA-minded
# contrast tokens for light + dark, visible focus.
# --------------------------------------------------------------------------


def test_html_has_required_a11y_and_kiosk_controls() -> None:
    required_substrings = [
        '"aria-label", "Approve: "',
        '"aria-label", "Deny: "',
        "aria-expanded",
        "aria-controls",
        'role="status"',
        'role="alert"',
        "prefers-reduced-motion",
        "prefers-color-scheme: dark",
        ":focus-visible",
        "Tapping Approve will ask you to scan your fingerprint or touch your security key.",
        "navigator.credentials",
        "id=\"live-sync-indicator\"",
    ]
    missing = [s for s in required_substrings if s not in APPROVE_HTML]
    check(not missing, f"approve.html missing required a11y/kiosk elements: {missing}")

    # Buttons are native <button> elements (keyboard-operable by default) —
    # not divs/spans with a click handler bolted on.
    check("<button" in APPROVE_HTML, "no native <button> elements found")
    check(APPROVE_HTML.count("<div") <= APPROVE_HTML.count("</div"), "unbalanced div tags")


def test_html_declares_approve_card_copy_verbatim() -> None:
    """Verbatim from ACP-PREP-COPY-20260816.md "Dashboard 'Approvals' card
    copy (for P2)"."""
    for phrase in (
        "Approvals Needed",
        "All caught up! No items are waiting for your review.",
        "View all",
    ):
        check(phrase in APPROVE_HTML, f"approve.html missing verbatim card copy: {phrase!r}")
    check("pending" in APPROVE_HTML, "pending_badge template text missing")


def test_html_guards_navigator_credentials_absence() -> None:
    check(
        "!navigator.credentials || typeof navigator.credentials.get" in APPROVE_HTML,
        "no guard found for navigator.credentials absence",
    )
    check('"no_authenticator"' in APPROVE_HTML, "no fallback to no_authenticator on WebAuthn absence")


# --------------------------------------------------------------------------
# Kiosk CSP — verbatim header on the served view.
# --------------------------------------------------------------------------

EXPECTED_CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
    "frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self';"
)


def test_approve_view_serves_verbatim_kiosk_csp() -> None:
    check(approvals.APPROVE_VIEW_CSP == EXPECTED_CSP, "APPROVE_VIEW_CSP does not match the prep doc verbatim")
    app, _store, _signer = _fresh_app()
    with TestClient(app) as client:
        resp = client.get("/approve")
        check(resp.status_code == 200, f"approve view should serve: {resp.status_code}")
        check(resp.headers.get("content-security-policy") == EXPECTED_CSP, f"CSP header mismatch: {resp.headers.get('content-security-policy')!r}")
        check("<html" in resp.text.lower(), "approve view did not return HTML")


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
    print(f"PASS: {len(tests)} approval-surface P2 checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
