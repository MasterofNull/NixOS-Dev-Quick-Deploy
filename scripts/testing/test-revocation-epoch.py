#!/usr/bin/env python3
"""Offline hermetic acceptance tests — C6-B1 revocation-epoch authority primitive.

Covers `.agents/plans/aqos-foundation-c/C6-FREEZE-20260807.md` (C6-B1 scope) and
the fail-closed invariants in `C6-DESIGN-AND-AUTHORIZATION.md` §2: no
bootstrap-to-zero, no env fallback, no direct epoch-file-write bypass, no
advisory success, no auto-reissue. Uses a throwaway Ed25519 keypair + a test
owner-key allowlist + a temp epoch file + a temp replay-ledger directory.
Offline only: no network, no real owner private-key material (there is none
to hold anywhere in this codebase).
"""
from __future__ import annotations

import json
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "scripts" / "ai" / "lib"
sys.path.insert(0, str(LIB_DIR))

import revocation_epoch as re_lib  # noqa: E402

OWNER_KEYS_PATH = REPO_ROOT / "config" / "aqos" / "c6-owner-public-keys.json"

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


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _make_keypair() -> tuple[bytes, str]:
    """Returns (private_key_bytes, public_key_hex) for a fresh throwaway
    Ed25519 keypair — never anything real."""
    private_key = Ed25519PrivateKey.generate()
    priv_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return priv_bytes, pub_bytes.hex()


def _owner_keys(key_id: str, pubkey_hex: str, status: str = "active") -> dict:
    return {
        "schema_version": "1",
        "revision": 1,
        "keys": [
            {
                "key_id": key_id,
                "ed25519_public_key": pubkey_hex,
                "status": status,
                "not_before": None,
                "not_after": None,
            }
        ],
    }


def _base_bump(
    *,
    actor_key_id: str,
    expected_epoch: int,
    reason_code: str = "operator-revoke",
    scope: str = "fleet",
    request_id: str | None = None,
    idempotency_key: str | None = None,
    issued_at: datetime | None = None,
    ttl_seconds: int = 3600,
) -> dict:
    now = issued_at or datetime.now(timezone.utc)
    return {
        "schema_version": re_lib.BUMP_SCHEMA_VERSION,
        "request_id": request_id or f"req::{uuid.uuid4()}",
        "idempotency_key": idempotency_key or f"idem::{uuid.uuid4()}",
        "issued_at": _iso(now),
        "expires_at": _iso(now + timedelta(seconds=ttl_seconds)),
        "actor_key_id": actor_key_id,
        "expected_epoch": expected_epoch,
        "reason_code": reason_code,
        "scope": scope,
        "signature": "",
    }


def _sign(doc: dict, priv_bytes: bytes) -> dict:
    signed = dict(doc)
    signed["signature"] = re_lib.sign_bump(signed, priv_bytes)
    return signed


class _TempEnv:
    """Fresh temp epoch file + ledger dir per test."""

    def __init__(self, initial_epoch: str | None = "0") -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.epoch_path = Path(self.tmp.name) / "epoch"
        if initial_epoch is not None:
            self.epoch_path.write_text(initial_epoch, encoding="utf-8")
        self.ledger_dir = Path(self.tmp.name) / "ledger"

    def ledger(self) -> re_lib.DurableReplayLedger:
        """A NEW `DurableReplayLedger` instance pointed at the SAME
        directory — simulates a process restart with zero carried-over
        in-process memory, while proving on-disk durability."""
        return re_lib.DurableReplayLedger(str(self.ledger_dir))

    def cleanup(self) -> None:
        self.tmp.cleanup()


# --------------------------------------------------------------------------
# 1. Valid signed bump advances epoch by exactly +1
# --------------------------------------------------------------------------


def test_valid_bump_advances_epoch_by_exactly_one() -> None:
    priv, pub_hex = _make_keypair()
    keys = _owner_keys("test-owner-1", pub_hex)
    env = _TempEnv(initial_epoch="5")
    try:
        doc = _sign(_base_bump(actor_key_id="test-owner-1", expected_epoch=5), priv)
        result = re_lib.apply_bump(doc, env.epoch_path, env.ledger(), keys)
        check("valid bump: ok=True", result["ok"] is True)
        check("valid bump: reason=ok", result.get("reason") == re_lib.BUMP_OK)
        new_val = re_lib.read_epoch(env.epoch_path)
        check("valid bump: epoch advances 5 -> 6 (exactly +1)", new_val == 6)
        check(
            "valid bump: receipt old/new epoch correct",
            result["receipt"]["old_epoch"] == 5 and result["receipt"]["new_epoch"] == 6,
        )
    finally:
        env.cleanup()


# --------------------------------------------------------------------------
# 2-7. Deny paths that must never advance the epoch
# --------------------------------------------------------------------------


def test_forged_signature_denies() -> None:
    priv, pub_hex = _make_keypair()
    other_priv, _ = _make_keypair()
    keys = _owner_keys("test-owner-1", pub_hex)
    env = _TempEnv(initial_epoch="0")
    try:
        # Signed with a DIFFERENT key than the one in the allowlist for
        # this key_id -- a forged / mismatched signature.
        doc = _sign(_base_bump(actor_key_id="test-owner-1", expected_epoch=0), other_priv)
        result = re_lib.apply_bump(doc, env.epoch_path, env.ledger(), keys)
        check("forged signature: denied", result["ok"] is False)
        check("forged signature: reason=bad-signature", result["reason"] == re_lib.DENY_BAD_SIGNATURE)
        check("forged signature: epoch unchanged", re_lib.read_epoch(env.epoch_path) == 0)
    finally:
        env.cleanup()


def test_unknown_key_denies() -> None:
    priv, pub_hex = _make_keypair()
    keys = _owner_keys("some-other-key-id", pub_hex)
    env = _TempEnv(initial_epoch="0")
    try:
        doc = _sign(_base_bump(actor_key_id="test-owner-1", expected_epoch=0), priv)
        result = re_lib.apply_bump(doc, env.epoch_path, env.ledger(), keys)
        check("unknown key: denied", result["ok"] is False)
        check("unknown key: reason=unknown-key-id", result["reason"] == re_lib.DENY_UNKNOWN_KEY)
        check("unknown key: epoch unchanged", re_lib.read_epoch(env.epoch_path) == 0)
    finally:
        env.cleanup()


def test_revoked_key_denies() -> None:
    priv, pub_hex = _make_keypair()
    keys = _owner_keys("test-owner-1", pub_hex, status="revoked")
    env = _TempEnv(initial_epoch="0")
    try:
        doc = _sign(_base_bump(actor_key_id="test-owner-1", expected_epoch=0), priv)
        result = re_lib.apply_bump(doc, env.epoch_path, env.ledger(), keys)
        check("revoked key: denied", result["ok"] is False)
        check("revoked key: reason=key-not-active", result["reason"] == re_lib.DENY_KEY_NOT_ACTIVE)
        check("revoked key: epoch unchanged", re_lib.read_epoch(env.epoch_path) == 0)
    finally:
        env.cleanup()


def test_wrong_scope_denies() -> None:
    priv, pub_hex = _make_keypair()
    keys = _owner_keys("test-owner-1", pub_hex)
    env = _TempEnv(initial_epoch="0")
    try:
        doc = _base_bump(actor_key_id="test-owner-1", expected_epoch=0)
        doc["scope"] = "single-host"
        doc = _sign(doc, priv)
        result = re_lib.apply_bump(doc, env.epoch_path, env.ledger(), keys)
        check("wrong scope: denied", result["ok"] is False)
        check("wrong scope: reason=scope-not-fleet", result["reason"] == re_lib.DENY_SCOPE)
        check("wrong scope: epoch unchanged", re_lib.read_epoch(env.epoch_path) == 0)
    finally:
        env.cleanup()


def test_bad_reason_code_denies() -> None:
    priv, pub_hex = _make_keypair()
    keys = _owner_keys("test-owner-1", pub_hex)
    env = _TempEnv(initial_epoch="0")
    try:
        doc = _base_bump(actor_key_id="test-owner-1", expected_epoch=0)
        doc["reason_code"] = "because-i-said-so"
        doc = _sign(doc, priv)
        result = re_lib.apply_bump(doc, env.epoch_path, env.ledger(), keys)
        check("bad reason_code: denied", result["ok"] is False)
        check(
            "bad reason_code: reason=reason-code-invalid",
            result["reason"] == re_lib.DENY_REASON_CODE,
        )
        check("bad reason_code: epoch unchanged", re_lib.read_epoch(env.epoch_path) == 0)
    finally:
        env.cleanup()


def test_expired_bump_denies() -> None:
    priv, pub_hex = _make_keypair()
    keys = _owner_keys("test-owner-1", pub_hex)
    env = _TempEnv(initial_epoch="0")
    try:
        past = datetime.now(timezone.utc) - timedelta(hours=2)
        doc = _sign(
            _base_bump(
                actor_key_id="test-owner-1",
                expected_epoch=0,
                issued_at=past,
                ttl_seconds=60,  # expires_at = past + 60s -- long gone
            ),
            priv,
        )
        result = re_lib.apply_bump(doc, env.epoch_path, env.ledger(), keys)
        check("expired bump: denied", result["ok"] is False)
        check("expired bump: reason=bump-expired", result["reason"] == re_lib.DENY_EXPIRED)
        check("expired bump: epoch unchanged", re_lib.read_epoch(env.epoch_path) == 0)
    finally:
        env.cleanup()


# --------------------------------------------------------------------------
# 8. expected_epoch mismatch (stale bump) -> DENY, optimistic concurrency
# --------------------------------------------------------------------------


def test_expected_epoch_mismatch_denies() -> None:
    priv, pub_hex = _make_keypair()
    keys = _owner_keys("test-owner-1", pub_hex)
    env = _TempEnv(initial_epoch="7")
    try:
        doc = _sign(_base_bump(actor_key_id="test-owner-1", expected_epoch=3), priv)
        result = re_lib.apply_bump(doc, env.epoch_path, env.ledger(), keys)
        check("stale expected_epoch: denied", result["ok"] is False)
        check(
            "stale expected_epoch: reason=expected-epoch-mismatch",
            result["reason"] == re_lib.DENY_EPOCH_MISMATCH,
        )
        check("stale expected_epoch: epoch unchanged (still 7)", re_lib.read_epoch(env.epoch_path) == 7)
    finally:
        env.cleanup()


# --------------------------------------------------------------------------
# 9. REPLAY denies even across a restart-simulated fresh ledger instance
#    on the same directory. Isolated from expected_epoch-mismatch by
#    correctly updating expected_epoch on the replayed request_id/
#    idempotency_key -- proves the ledger (not epoch drift) is what denies.
# --------------------------------------------------------------------------


def test_replay_denies_even_across_fresh_ledger_instance() -> None:
    priv, pub_hex = _make_keypair()
    keys = _owner_keys("test-owner-1", pub_hex)
    env = _TempEnv(initial_epoch="0")
    try:
        shared_request_id = f"req::{uuid.uuid4()}"
        shared_idem_key = f"idem::{uuid.uuid4()}"

        doc1 = _sign(
            _base_bump(
                actor_key_id="test-owner-1",
                expected_epoch=0,
                request_id=shared_request_id,
                idempotency_key=shared_idem_key,
            ),
            priv,
        )
        first = re_lib.apply_bump(doc1, env.epoch_path, env.ledger(), keys)
        check("replay setup: first apply succeeds", first["ok"] is True)
        check("replay setup: epoch advances to 1", re_lib.read_epoch(env.epoch_path) == 1)

        # Fresh ledger instance on the SAME directory -- simulates a
        # service restart with no in-process memory carried over.
        restarted_ledger = env.ledger()

        # A second, freshly-signed request reusing the SAME request_id/
        # idempotency_key, this time with a CORRECTLY updated
        # expected_epoch (1). If this were denied by epoch-mismatch
        # instead of replay, that would be a false negative for this
        # test -- expected_epoch is deliberately made to match so the
        # only possible deny reason left is the replay ledger.
        doc2 = _sign(
            _base_bump(
                actor_key_id="test-owner-1",
                expected_epoch=1,
                request_id=shared_request_id,
                idempotency_key=shared_idem_key,
            ),
            priv,
        )
        second = re_lib.apply_bump(doc2, env.epoch_path, restarted_ledger, keys)
        check("replay: denied on fresh ledger instance (same dir)", second["ok"] is False)
        check("replay: reason=replay-request", second["reason"] == re_lib.DENY_REPLAY)
        check("replay: epoch still 1 (no second advance)", re_lib.read_epoch(env.epoch_path) == 1)
    finally:
        env.cleanup()


# --------------------------------------------------------------------------
# 10-12. Missing/malformed epoch store -> typed error, never a silent 0.
#        No-bootstrap-to-zero proven end-to-end through apply_bump too.
# --------------------------------------------------------------------------


def test_missing_epoch_store_is_typed_error_not_zero() -> None:
    tmp = tempfile.TemporaryDirectory()
    try:
        missing_path = Path(tmp.name) / "epoch-does-not-exist"
        raised = False
        reason = None
        try:
            re_lib.read_epoch(missing_path)
        except re_lib.EpochStoreError as exc:
            raised = True
            reason = exc.reason
        check("missing epoch store: raises EpochStoreError (not silent 0)", raised is True)
        check(
            "missing epoch store: reason=epoch-store-missing",
            reason == re_lib.EPOCH_ERR_MISSING,
        )
    finally:
        tmp.cleanup()


def test_malformed_epoch_store_is_typed_error() -> None:
    tmp = tempfile.TemporaryDirectory()
    try:
        bad_vectors = [
            ("not-a-number", "non-numeric"),
            ("-1", "negative"),
            ("007", "leading-zero"),
            ("1.5", "float"),
            ("", "empty"),
            ("0x5", "hex-prefixed"),
            ("5 6", "trailing-garbage"),
        ]
        for bad_content, label in bad_vectors:
            path = Path(tmp.name) / f"epoch-{label}"
            path.write_text(bad_content, encoding="utf-8")
            raised = False
            reason = None
            try:
                re_lib.read_epoch(path)
            except re_lib.EpochStoreError as exc:
                raised = True
                reason = exc.reason
            check(f"malformed epoch store ({label}): raises EpochStoreError", raised is True)
            check(
                f"malformed epoch store ({label}): reason=epoch-store-malformed",
                reason == re_lib.EPOCH_ERR_MALFORMED,
            )

        # Control case: surrounding whitespace around an otherwise-strict
        # integer IS accepted (stripped before the strict-decimal check).
        control_path = Path(tmp.name) / "epoch-whitespace-padded"
        control_path.write_text(" 3 \n", encoding="utf-8")
        value = re_lib.read_epoch(control_path)
        check("epoch store control (padded valid int): strips to 3", value == 3)
    finally:
        tmp.cleanup()


def test_no_bootstrap_to_zero_end_to_end() -> None:
    """A missing epoch store must deny the WHOLE apply_bump flow -- never
    silently treated as epoch 0 and allowed to proceed."""
    priv, pub_hex = _make_keypair()
    keys = _owner_keys("test-owner-1", pub_hex)
    tmp = tempfile.TemporaryDirectory()
    try:
        missing_epoch_path = Path(tmp.name) / "epoch-does-not-exist"
        ledger = re_lib.DurableReplayLedger(str(Path(tmp.name) / "ledger"))
        doc = _sign(_base_bump(actor_key_id="test-owner-1", expected_epoch=0), priv)
        result = re_lib.apply_bump(doc, missing_epoch_path, ledger, keys)
        check("no-bootstrap-to-zero: apply_bump denies on missing store", result["ok"] is False)
        check(
            "no-bootstrap-to-zero: reason=epoch-store-missing (never treated as 0)",
            result["reason"] == re_lib.EPOCH_ERR_MISSING,
        )
        check(
            "no-bootstrap-to-zero: store still absent (nothing was created)",
            not missing_epoch_path.exists(),
        )
    finally:
        tmp.cleanup()


# --------------------------------------------------------------------------
# 13. The real placeholder all-zeros owner key must fail closed.
# --------------------------------------------------------------------------


def test_placeholder_owner_key_denies() -> None:
    real_keys = json.loads(OWNER_KEYS_PATH.read_text(encoding="utf-8"))
    placeholder_entry = real_keys["keys"][0]
    check(
        "placeholder key fixture sanity: key_id=owner-2026-08",
        placeholder_entry.get("key_id") == "owner-2026-08",
    )
    check(
        "placeholder key fixture sanity: all-zeros public key (64 hex chars)",
        placeholder_entry.get("ed25519_public_key") == "0" * 64,
    )

    # Sign with a REAL (non-placeholder) throwaway keypair -- the
    # placeholder key material cannot possibly match any real signature;
    # this proves the deny is a genuine cryptographic verification
    # failure, not a special-cased "is this all zeros" shortcut.
    priv, _real_pub_hex = _make_keypair()
    env = _TempEnv(initial_epoch="0")
    try:
        doc = _sign(
            _base_bump(actor_key_id=placeholder_entry["key_id"], expected_epoch=0),
            priv,
        )
        result = re_lib.apply_bump(doc, env.epoch_path, env.ledger(), real_keys)
        check("placeholder all-zeros key: denied", result["ok"] is False)
        check(
            "placeholder all-zeros key: reason=bad-signature",
            result["reason"] == re_lib.DENY_BAD_SIGNATURE,
        )
        check(
            "placeholder all-zeros key: epoch unchanged",
            re_lib.read_epoch(env.epoch_path) == 0,
        )
    finally:
        env.cleanup()


def main() -> int:
    test_valid_bump_advances_epoch_by_exactly_one()
    test_forged_signature_denies()
    test_unknown_key_denies()
    test_revoked_key_denies()
    test_wrong_scope_denies()
    test_bad_reason_code_denies()
    test_expired_bump_denies()
    test_expected_epoch_mismatch_denies()
    test_replay_denies_even_across_fresh_ledger_instance()
    test_missing_epoch_store_is_typed_error_not_zero()
    test_malformed_epoch_store_is_typed_error()
    test_no_bootstrap_to_zero_end_to_end()
    test_placeholder_owner_key_denies()

    print(f"\n{passed} passed, {failed} failed (of {passed + failed} assertions)")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
