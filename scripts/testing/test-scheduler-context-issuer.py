#!/usr/bin/env python3
"""Offline hermetic tests for the C2 scheduler-context issuer — Foundation C, C2-SCI
subslice B1.

No network, no service, no `/run/secrets`. Generates two independent throwaway
Ed25519 keypairs offline: one plays the ALREADY-EXISTING C2 lease signer (the presented
lease's authority) and one plays the scheduler-context issuer's own signer (this
module's output). Proves the trust model from
`.agents/plans/aqos-foundation-c/C2-SCHEDULER-CONTEXT-ISSUER-DESIGN-20260806.md`
(rev4): authority is the independently-verified signed lease, never the caller.

Covers: valid mint + re-verify; forged/unverifiable lease -> deny, no mint; expired /
epoch-stale lease -> deny (OBLIG-1); replay of the same {lease_id, grant_digest} ->
deny even under a different task_id (single-use is per-lease, not per-task);
correlation cannot widen authority; expires_at = min(lease.expires_at, cap);
signer-key-unavailable -> deny, no mint. A short transport-layer smoke test covers
`scheduler_context_transport.read_frame`/`get_peer_credentials` on a connected UDS
socketpair (no listening server needed — this subslice ships no enabled service).
"""
from __future__ import annotations

import os
import socket
import sys
from datetime import datetime, timedelta, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LIB_DIR = os.path.join(REPO_ROOT, "scripts", "ai", "lib")
sys.path.insert(0, LIB_DIR)

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat

import capability_lease as cl  # noqa: E402
import scheduler_context_issuer as sci  # noqa: E402
import scheduler_context_transport as sct  # noqa: E402


passed = 0
failed = 0


def check(label: str, condition: bool) -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"PASS: {label}")
    else:
        failed += 1
        print(f"FAIL: {label}")


def _keypair() -> tuple[bytes, str]:
    priv = Ed25519PrivateKey.generate()
    priv_raw = priv.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    pub_hex = priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    return priv_raw, pub_hex


def _keys_json(key_id: str, pub_hex: str, status: str = "active") -> dict:
    return {
        "schema_version": "1",
        "revision": 1,
        "keys": [{"key_id": key_id, "ed25519_public_key": pub_hex, "status": status}],
    }


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_lease(
    *,
    lease_priv: bytes,
    lease_key_id: str,
    lease_id: str = "lease-1",
    grant_digest: str = "digest-1",
    trust_tier: int = 2,
    policy_revision: int = 1,
    actions: tuple[str, ...] = ("run_cmd",),
    issued_at: datetime,
    expires_at: datetime,
    revocation_epoch: int = 0,
    sig_scheme: str = cl.SIG_SCHEME_ED25519,
) -> dict:
    lease = {
        "lease_id": lease_id,
        "version": 1,
        "source": "test",
        "owner": "test",
        "issued_to": "switchboard-local-tool-executor",
        "issued_at": _iso(issued_at),
        "expires_at": _iso(expires_at),
        "permissions": {"actions": list(actions), "resources": [], "constraints": {}},
        "input_schema": {},
        "output_schema": {},
        "trust_tier": trust_tier,
        "zero_trust_behavior": "none",
        "cost_class": "first-party",
        "parent_lease_id": None,
        "revocation_epoch": revocation_epoch,
        "grant_digest": grant_digest,
        "policy_revision": policy_revision,
        "sig_scheme": sig_scheme,
        "issuer_key_id": lease_key_id,
        "signature": "",
    }
    lease["signature"] = cl.sign_ed25519(lease, lease_priv)
    return lease


NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
CORRELATION = {"task_id": "task-1", "principal": "agent-1", "dispatch_mode": "agent"}


def _fresh_env():
    """One fresh pair of independent keypairs/allowlists per test — lease signer
    (authority the presented lease must verify against) and context signer (this
    issuer's own key), matching design §2's distinct key-family requirement."""
    lease_priv, lease_pub_hex = _keypair()
    lease_key_id = "test-lease-signer"
    lease_keys_json = _keys_json(lease_key_id, lease_pub_hex)
    ctx_priv, ctx_pub_hex = _keypair()
    ctx_key_id = "test-context-signer"
    ctx_keys_json = _keys_json(ctx_key_id, ctx_pub_hex)
    return lease_priv, lease_key_id, lease_keys_json, ctx_priv, ctx_key_id, ctx_keys_json


# --------------------------------------------------------------------------
# 1) valid presented lease -> mints a signed context; re-verify.
# --------------------------------------------------------------------------


def test_valid_mint_and_reverify() -> None:
    lease_priv, lease_key_id, lease_keys_json, ctx_priv, ctx_key_id, ctx_keys_json = _fresh_env()
    lease = _build_lease(
        lease_priv=lease_priv, lease_key_id=lease_key_id,
        issued_at=NOW, expires_at=NOW + timedelta(hours=2),
    )
    ledger = sci.InMemorySingleUseLedger()
    result = sci.mint_scheduler_context(
        lease, lease_keys_json, current_epoch=0, correlation=CORRELATION,
        private_key_bytes=ctx_priv, key_id=ctx_key_id, context_ttl_cap_seconds=3600,
        ledger=ledger, now=NOW,
    )
    check("valid lease -> ok=True", result["ok"] is True)
    check("valid lease -> reason MINT_OK", result["reason"] == sci.MINT_OK)
    ctx = result["context"]
    check("context is not None", ctx is not None)
    check("context schema tag", ctx["schema"] == sci.CONTEXT_SCHEMA)
    check("context audience is fixed constant", ctx["audience"] == sci.AUDIENCE)
    check("context lease_id from lease", ctx["lease_id"] == "lease-1")
    check("context grant_digest from lease", ctx["grant_digest"] == "digest-1")
    check("context action_class derived from single action", ctx["action_class"] == "run_cmd")
    check("context trust_tier from lease", ctx["trust_tier"] == 2)
    check("context policy_revision from lease", ctx["policy_revision"] == 1)
    verdict = sci.verify_scheduler_context(ctx, ctx_keys_json)
    check("minted context signature re-verifies under context signer key", verdict.ok)
    check("minted context does NOT verify under the lease signer's own allowlist",
          not sci.verify_scheduler_context(ctx, lease_keys_json).ok)


# --------------------------------------------------------------------------
# 2) unverifiable/forged presented lease -> DENY, no mint.
# --------------------------------------------------------------------------


def test_forged_lease_denied() -> None:
    lease_priv, lease_key_id, lease_keys_json, ctx_priv, ctx_key_id, _ctx_keys_json = _fresh_env()
    lease = _build_lease(
        lease_priv=lease_priv, lease_key_id=lease_key_id,
        issued_at=NOW, expires_at=NOW + timedelta(hours=2),
    )
    forged = dict(lease)
    forged["signature"] = "00" * 64  # not a valid signature over this payload
    ledger = sci.InMemorySingleUseLedger()
    result = sci.mint_scheduler_context(
        forged, lease_keys_json, current_epoch=0, correlation=CORRELATION,
        private_key_bytes=ctx_priv, key_id=ctx_key_id, context_ttl_cap_seconds=3600,
        ledger=ledger, now=NOW,
    )
    check("forged signature -> ok=False", result["ok"] is False)
    check("forged signature -> DENY_LEASE_UNVERIFIED", result["reason"] == sci.DENY_LEASE_UNVERIFIED)
    check("forged signature -> no context minted", result["context"] is None)

    # A lease signed by a keypair NOT in the allowlist at all (a genuine forgery
    # attempt, not just bit-flipped) must deny identically.
    attacker_priv, _attacker_pub = _keypair()
    attacker_lease = _build_lease(
        lease_priv=attacker_priv, lease_key_id=lease_key_id,
        issued_at=NOW, expires_at=NOW + timedelta(hours=2),
    )
    result2 = sci.mint_scheduler_context(
        attacker_lease, lease_keys_json, current_epoch=0, correlation=CORRELATION,
        private_key_bytes=ctx_priv, key_id=ctx_key_id, context_ttl_cap_seconds=3600,
        ledger=ledger, now=NOW,
    )
    check("lease signed by an off-allowlist key -> ok=False", result2["ok"] is False)
    check("lease signed by an off-allowlist key -> DENY_LEASE_UNVERIFIED",
          result2["reason"] == sci.DENY_LEASE_UNVERIFIED)


# --------------------------------------------------------------------------
# 3) expired / epoch-stale presented lease -> DENY (OBLIG-1).
# --------------------------------------------------------------------------


def test_obligation_1_expiry_and_epoch() -> None:
    lease_priv, lease_key_id, lease_keys_json, ctx_priv, ctx_key_id, _ctx_keys_json = _fresh_env()

    expired_lease = _build_lease(
        lease_priv=lease_priv, lease_key_id=lease_key_id,
        issued_at=NOW - timedelta(hours=3), expires_at=NOW - timedelta(hours=1),
    )
    ledger = sci.InMemorySingleUseLedger()
    result = sci.mint_scheduler_context(
        expired_lease, lease_keys_json, current_epoch=0, correlation=CORRELATION,
        private_key_bytes=ctx_priv, key_id=ctx_key_id, context_ttl_cap_seconds=3600,
        ledger=ledger, now=NOW,
    )
    check("expired lease -> ok=False", result["ok"] is False)
    check("expired lease -> DENY_LEASE_EXPIRED", result["reason"] == sci.DENY_LEASE_EXPIRED)
    check("expired lease -> no context minted", result["context"] is None)

    stale_lease = _build_lease(
        lease_priv=lease_priv, lease_key_id=lease_key_id,
        issued_at=NOW, expires_at=NOW + timedelta(hours=2), revocation_epoch=1,
    )
    ledger2 = sci.InMemorySingleUseLedger()
    result2 = sci.mint_scheduler_context(
        stale_lease, lease_keys_json, current_epoch=5, correlation=CORRELATION,
        private_key_bytes=ctx_priv, key_id=ctx_key_id, context_ttl_cap_seconds=3600,
        ledger=ledger2, now=NOW,
    )
    check("epoch-stale lease -> ok=False", result2["ok"] is False)
    check("epoch-stale lease -> DENY_LEASE_EPOCH_STALE", result2["reason"] == sci.DENY_LEASE_EPOCH_STALE)
    check("epoch-stale lease -> no context minted", result2["context"] is None)


# --------------------------------------------------------------------------
# 4) REPLAY: second mint for the same {lease_id, grant_digest} -> DENY, even
#    with a different task_id (single-use is per-lease, not per-task).
# --------------------------------------------------------------------------


def test_single_use_replay_per_lease_not_per_task() -> None:
    lease_priv, lease_key_id, lease_keys_json, ctx_priv, ctx_key_id, ctx_keys_json = _fresh_env()
    lease = _build_lease(
        lease_priv=lease_priv, lease_key_id=lease_key_id,
        issued_at=NOW, expires_at=NOW + timedelta(hours=2),
    )
    ledger = sci.InMemorySingleUseLedger()

    first = sci.mint_scheduler_context(
        lease, lease_keys_json, current_epoch=0, correlation=CORRELATION,
        private_key_bytes=ctx_priv, key_id=ctx_key_id, context_ttl_cap_seconds=3600,
        ledger=ledger, now=NOW,
    )
    check("first mint for a fresh lease -> ok=True", first["ok"] is True)

    different_task_correlation = {"task_id": "task-2-DIFFERENT", "principal": "agent-1", "dispatch_mode": "agent"}
    second = sci.mint_scheduler_context(
        lease, lease_keys_json, current_epoch=0, correlation=different_task_correlation,
        private_key_bytes=ctx_priv, key_id=ctx_key_id, context_ttl_cap_seconds=3600,
        ledger=ledger, now=NOW,
    )
    check("replay under a DIFFERENT task_id -> ok=False (per-lease, not per-task)", second["ok"] is False)
    check("replay -> DENY_REPLAY", second["reason"] == sci.DENY_REPLAY)
    check("replay -> no context minted", second["context"] is None)


# --------------------------------------------------------------------------
# 5) caller-supplied correlation cannot widen authority.
# --------------------------------------------------------------------------


def test_correlation_cannot_widen_authority() -> None:
    lease_priv, lease_key_id, lease_keys_json, ctx_priv, ctx_key_id, _ctx_keys_json = _fresh_env()
    lease = _build_lease(
        lease_priv=lease_priv, lease_key_id=lease_key_id,
        issued_at=NOW, expires_at=NOW + timedelta(hours=2),
        trust_tier=2, policy_revision=1, grant_digest="digest-1", actions=("run_cmd",),
    )
    ledger = sci.InMemorySingleUseLedger()
    hostile_correlation = {
        "task_id": "task-1",
        "principal": "agent-1",
        "dispatch_mode": "agent",
        # every one of these is an attempted authority override — none of
        # these keys are ever read by `_extract_correlation_fields`.
        "trust_tier": 999,
        "action_class": "delete_everything",
        "policy_revision": 999,
        "grant_digest": "attacker-controlled-digest",
        "lease_id": "attacker-controlled-lease-id",
        "revocation_epoch": 0,
    }
    result = sci.mint_scheduler_context(
        lease, lease_keys_json, current_epoch=0, correlation=hostile_correlation,
        private_key_bytes=ctx_priv, key_id=ctx_key_id, context_ttl_cap_seconds=3600,
        ledger=ledger, now=NOW,
    )
    check("mint with hostile correlation still succeeds (correlation ignored, not rejected)", result["ok"] is True)
    ctx = result["context"]
    check("authority trust_tier is the LEASE's, not correlation's 999", ctx["trust_tier"] == 2)
    check("authority action_class is the LEASE's, not correlation's override", ctx["action_class"] == "run_cmd")
    check("authority policy_revision is the LEASE's, not correlation's 999", ctx["policy_revision"] == 1)
    check("authority grant_digest is the LEASE's, not correlation's override", ctx["grant_digest"] == "digest-1")
    check("authority lease_id is the LEASE's, not correlation's override", ctx["lease_id"] == "lease-1")
    # correlation-only fields DO pass through verbatim (that's their entire job).
    check("correlation task_id passes through", ctx["task_id"] == "task-1")
    check("correlation principal passes through", ctx["principal"] == "agent-1")
    check("correlation dispatch_mode passes through", ctx["dispatch_mode"] == "agent")


# --------------------------------------------------------------------------
# 6) expires_at = min(lease.expires_at, cap).
# --------------------------------------------------------------------------


def test_expires_at_is_min_of_lease_and_cap() -> None:
    lease_priv, lease_key_id, lease_keys_json, ctx_priv, ctx_key_id, _ctx_keys_json = _fresh_env()

    # Case A: cap is the binding constraint (lease outlives the cap).
    long_lease = _build_lease(
        lease_priv=lease_priv, lease_key_id=lease_key_id,
        issued_at=NOW, expires_at=NOW + timedelta(hours=10), grant_digest="digest-cap",
    )
    ledger = sci.InMemorySingleUseLedger()
    cap_seconds = 300
    result = sci.mint_scheduler_context(
        long_lease, lease_keys_json, current_epoch=0, correlation=CORRELATION,
        private_key_bytes=ctx_priv, key_id=ctx_key_id, context_ttl_cap_seconds=cap_seconds,
        ledger=ledger, now=NOW,
    )
    check("cap-bound mint -> ok=True", result["ok"] is True)
    expected_cap_expiry = _iso(NOW + timedelta(seconds=cap_seconds))
    check("expires_at == now+cap when cap < lease.expires_at", result["context"]["expires_at"] == expected_cap_expiry)

    # Case B: the lease's own expiry is the binding constraint (cap is generous).
    short_lease = _build_lease(
        lease_priv=lease_priv, lease_key_id=lease_key_id,
        issued_at=NOW, expires_at=NOW + timedelta(minutes=5), grant_digest="digest-lease-bound",
    )
    ledger2 = sci.InMemorySingleUseLedger()
    result2 = sci.mint_scheduler_context(
        short_lease, lease_keys_json, current_epoch=0, correlation=CORRELATION,
        private_key_bytes=ctx_priv, key_id=ctx_key_id, context_ttl_cap_seconds=3600,
        ledger=ledger2, now=NOW,
    )
    check("lease-bound mint -> ok=True", result2["ok"] is True)
    check("expires_at == lease.expires_at when lease.expires_at < now+cap",
          result2["context"]["expires_at"] == _iso(NOW + timedelta(minutes=5)))


# --------------------------------------------------------------------------
# 7) signer-key-unavailable -> typed deny, no mint.
# --------------------------------------------------------------------------


def test_signer_unavailable_denied() -> None:
    lease_priv, lease_key_id, lease_keys_json, _ctx_priv, ctx_key_id, _ctx_keys_json = _fresh_env()
    lease = _build_lease(
        lease_priv=lease_priv, lease_key_id=lease_key_id,
        issued_at=NOW, expires_at=NOW + timedelta(hours=2), grant_digest="digest-no-signer",
    )
    ledger = sci.InMemorySingleUseLedger()
    result = sci.mint_scheduler_context(
        lease, lease_keys_json, current_epoch=0, correlation=CORRELATION,
        private_key_bytes=None, key_id=ctx_key_id, context_ttl_cap_seconds=3600,
        ledger=ledger, now=NOW,
    )
    check("no signer key -> ok=False", result["ok"] is False)
    check("no signer key -> DENY_SIGNER_UNAVAILABLE", result["reason"] == sci.DENY_SIGNER_UNAVAILABLE)
    check("no signer key -> no context minted", result["context"] is None)

    ledger2 = sci.InMemorySingleUseLedger()
    result2 = sci.mint_scheduler_context(
        lease, lease_keys_json, current_epoch=0, correlation=CORRELATION,
        private_key_bytes=b"", key_id=ctx_key_id, context_ttl_cap_seconds=3600,
        ledger=ledger2, now=NOW,
    )
    check("empty signer key bytes -> DENY_SIGNER_UNAVAILABLE", result2["reason"] == sci.DENY_SIGNER_UNAVAILABLE)

    ledger3 = sci.InMemorySingleUseLedger()
    result3 = sci.mint_scheduler_context(
        lease, lease_keys_json, current_epoch=0, correlation=CORRELATION,
        private_key_bytes=b"too-short", key_id=ctx_key_id, context_ttl_cap_seconds=3600,
        ledger=ledger3, now=NOW,
    )
    check("malformed (wrong-length) signer key -> ok=False", result3["ok"] is False)
    check("malformed signer key -> DENY_SIGNER_UNAVAILABLE", result3["reason"] == sci.DENY_SIGNER_UNAVAILABLE)


# --------------------------------------------------------------------------
# Bonus: ledger fault fails closed too (never fails open on a raising ledger).
# --------------------------------------------------------------------------


def test_ledger_fault_fails_closed() -> None:
    lease_priv, lease_key_id, lease_keys_json, ctx_priv, ctx_key_id, _ctx_keys_json = _fresh_env()
    lease = _build_lease(
        lease_priv=lease_priv, lease_key_id=lease_key_id,
        issued_at=NOW, expires_at=NOW + timedelta(hours=2), grant_digest="digest-ledger-fault",
    )

    class _RaisingLedger:
        def check_and_record(self, key):
            raise RuntimeError("simulated durable-store outage")

    result = sci.mint_scheduler_context(
        lease, lease_keys_json, current_epoch=0, correlation=CORRELATION,
        private_key_bytes=ctx_priv, key_id=ctx_key_id, context_ttl_cap_seconds=3600,
        ledger=_RaisingLedger(), now=NOW,
    )
    check("raising ledger -> ok=False (fail-closed, not fail-open)", result["ok"] is False)
    check("raising ledger -> DENY_LEDGER_UNAVAILABLE", result["reason"] == sci.DENY_LEDGER_UNAVAILABLE)
    check("raising ledger -> no context minted", result["context"] is None)


# --------------------------------------------------------------------------
# Transport smoke test — no listening server needed; exercises read_frame /
# get_peer_credentials on a connected UDS socketpair.
# --------------------------------------------------------------------------


def test_transport_frame_io() -> None:
    a, b = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        a.settimeout(2.0)
        b.settimeout(2.0)
        creds = sct.get_peer_credentials(a)
        check("SO_PEERCRED returns a (pid, uid, gid) tuple on a real local socketpair", creds is not None)

        b.sendall(b'{"hello":"world"}\n')
        framed = sct.read_frame(a)
        check("read_frame decodes a well-formed JSON line", framed.get("ok") is True and framed["frame"] == {"hello": "world"})

        b.sendall(b"not json at all\n")
        framed2 = sct.read_frame(a)
        check("read_frame denies malformed JSON", framed2.get("ok") is False and framed2["reason"] == sct.DENY_MALFORMED_JSON)

        b.sendall((b"x" * (sct.MAX_REQUEST_BYTES + 10)))
        framed3 = sct.read_frame(a, max_bytes=1024)
        check("read_frame denies an oversize frame", framed3.get("ok") is False and framed3["reason"] == sct.DENY_OVERSIZE)
    finally:
        a.close()
        b.close()


def main() -> int:
    test_valid_mint_and_reverify()
    test_forged_lease_denied()
    test_obligation_1_expiry_and_epoch()
    test_single_use_replay_per_lease_not_per_task()
    test_correlation_cannot_widen_authority()
    test_expires_at_is_min_of_lease_and_cap()
    test_signer_unavailable_denied()
    test_ledger_fault_fails_closed()
    test_transport_frame_io()

    print(f"\n{passed} passed, {failed} failed (of {passed + failed} assertions)")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
