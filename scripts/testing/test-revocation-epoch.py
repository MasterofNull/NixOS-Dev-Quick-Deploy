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
# 9. A COMMITTED transaction replayed (even across a restart-simulated
#    fresh ledger instance on the same directory, and with expected_epoch
#    correctly updated to isolate this from an epoch-mismatch deny) is
#    idempotent: C6d's `resolve()` `committed` row returns the SAME
#    reconstructed receipt (ok=True) rather than the pre-C6d ledger's
#    `DENY_REPLAY` -- the legacy `DurableReplayLedger` marker is no longer
#    consulted for gating (see `apply_bump`'s docstring), so a second
#    presentation of an identity whose journal entry is already
#    `committed` is exactly-once success, never a deny, and never a
#    second epoch advance.
# --------------------------------------------------------------------------


def test_committed_replay_is_idempotent_not_denied() -> None:
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
        check("idempotent replay setup: first apply succeeds", first["ok"] is True)
        check("idempotent replay setup: epoch advances to 1", re_lib.read_epoch(env.epoch_path) == 1)

        # Fresh ledger instance on the SAME directory -- simulates a
        # service restart with no in-process memory carried over. Proves
        # the journal (filesystem-durable), not any in-process ledger
        # state, is what makes this idempotent.
        restarted_ledger = env.ledger()

        # A second, freshly-signed request reusing the SAME request_id/
        # idempotency_key, this time with a CORRECTLY updated
        # expected_epoch (1) -- deliberately made to match so an
        # epoch-mismatch deny is ruled out and the only thing under test
        # is the committed-replay identity path.
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
        check("committed replay: idempotent success (ok=True, not denied)", second["ok"] is True)
        check("committed replay: reason=ok", second.get("reason") == re_lib.BUMP_OK)
        check(
            "committed replay: SAME reconstructed receipt (old=0, new=1)",
            second.get("receipt", {}).get("old_epoch") == 0
            and second.get("receipt", {}).get("new_epoch") == 1,
        )
        check("committed replay: epoch still 1 (no second advance)", re_lib.read_epoch(env.epoch_path) == 1)
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
# 13. The tracked owner-key allowlist key must fail closed. `fix/c6-
#     mechtest-revert` (now on main) rotated the placeholder all-zeros key
#     to a tracked, REVOKED, non-placeholder key (`owner-mechtest-2026-08`)
#     -- this fixture reads that CURRENT allowlist state rather than
#     asserting the stale placeholder shape, and denies for the reason
#     that actually fires first for a revoked key (`key-not-active`,
#     checked before signature verification -- see `_verify_signature`),
#     never a special-cased "is this a known placeholder" shortcut.
# --------------------------------------------------------------------------


def test_tracked_revoked_owner_key_denies() -> None:
    real_keys = json.loads(OWNER_KEYS_PATH.read_text(encoding="utf-8"))
    tracked_entry = real_keys["keys"][0]
    check(
        "tracked owner key fixture sanity: key_id=owner-mechtest-2026-08",
        tracked_entry.get("key_id") == "owner-mechtest-2026-08",
    )
    check(
        "tracked owner key fixture sanity: status=revoked",
        tracked_entry.get("status") == "revoked",
    )
    check(
        "tracked owner key fixture sanity: non-placeholder public key (not all-zeros)",
        tracked_entry.get("ed25519_public_key") != "0" * 64,
    )

    # Sign with a throwaway keypair the tracked entry never produced --
    # this key is REVOKED, so `key-not-active` fires before signature
    # verification is even reached; a signature this key never actually
    # made would deny on `bad-signature` regardless, so the revoked-status
    # deny proves the allowlist gate, not merely a lucky signature failure.
    priv, _unused_pub_hex = _make_keypair()
    env = _TempEnv(initial_epoch="0")
    try:
        doc = _sign(
            _base_bump(actor_key_id=tracked_entry["key_id"], expected_epoch=0),
            priv,
        )
        result = re_lib.apply_bump(doc, env.epoch_path, env.ledger(), real_keys)
        check("tracked revoked key: denied", result["ok"] is False)
        check(
            "tracked revoked key: reason=key-not-active",
            result["reason"] == re_lib.DENY_KEY_NOT_ACTIVE,
        )
        check(
            "tracked revoked key: epoch unchanged",
            re_lib.read_epoch(env.epoch_path) == 0,
        )
    finally:
        env.cleanup()


# --------------------------------------------------------------------------
# C6d -- deterministic journal recovery (`.agents/plans/aqos-foundation-c/
# C6d-DESIGN-AND-AUTHORIZATION.md` §5). Each vector injects the EXACT
# on-disk state a crash at that durability boundary would leave (offline,
# hermetic -- no real process is killed), then asserts `recover()` and/or a
# live retry reach the design's deterministic outcome. Vectors e/f are the
# SAME on-disk state as d/g respectively (`os.replace` atomicity -- the
# design's own note) and are deliberately not duplicated as separate tests.
# --------------------------------------------------------------------------


def test_vector_a_no_index_no_journal() -> None:
    """Vector a: crash before either index fsync -- no index, no journal.
    `recover()` has nothing to do; a subsequent submission reserves fresh
    and bumps normally."""
    priv, pub_hex = _make_keypair()
    keys = _owner_keys("test-owner-1", pub_hex)
    env = _TempEnv(initial_epoch="0")
    try:
        summary = re_lib.recover(env.epoch_path)
        check("vector a: recover() on clean state releases nothing", summary["orphan_indexes_released"] == 0)
        check("vector a: recover() on clean state resolves nothing", summary["resolved_committed"] == 0)

        doc = _sign(_base_bump(actor_key_id="test-owner-1", expected_epoch=0), priv)
        result = re_lib.apply_bump(doc, env.epoch_path, env.ledger(), keys)
        check("vector a: retry after no-op recover() reserves fresh & bumps", result["ok"] is True)
        check("vector a: epoch advances 0 -> 1", re_lib.read_epoch(env.epoch_path) == 1)
    finally:
        env.cleanup()


def test_vector_b_one_orphan_index() -> None:
    """Vector b: crash after one index fsync, before the second -- one
    orphan index, no journal. `recover()` releases the orphan
    (half-reservation); retry reserves & bumps, no wedged identity."""
    priv, pub_hex = _make_keypair()
    keys = _owner_keys("test-owner-1", pub_hex)
    env = _TempEnv(initial_epoch="0")
    try:
        request_id = f"req::{uuid.uuid4()}"
        idempotency_key = f"idem::{uuid.uuid4()}"
        entry_id = re_lib._entry_id(request_id, idempotency_key)
        journal_dir, by_rid_dir, by_idem_dir = re_lib._derive_state_dirs(env.epoch_path)
        rid_path = by_rid_dir / re_lib._sha256_hex(request_id)

        assert re_lib._create_exclusive_json(rid_path, {"entry_id": entry_id}, 0o600)

        summary = re_lib.recover(env.epoch_path)
        check("vector b: recover() releases the one orphan index", summary["orphan_indexes_released"] == 1)
        check("vector b: orphan index actually gone from disk", not rid_path.exists())

        doc = _sign(
            _base_bump(
                actor_key_id="test-owner-1", expected_epoch=0,
                request_id=request_id, idempotency_key=idempotency_key,
            ),
            priv,
        )
        result = re_lib.apply_bump(doc, env.epoch_path, env.ledger(), keys)
        check("vector b: retry after recover() reserves fresh & bumps (never wedged)", result["ok"] is True)
        check("vector b: epoch advances 0 -> 1", re_lib.read_epoch(env.epoch_path) == 1)
    finally:
        env.cleanup()


def test_vector_c_two_orphan_indexes() -> None:
    """Vector c: crash after both indexes, before intent fsync -- two
    orphan indexes, no journal. `recover()` releases both."""
    priv, pub_hex = _make_keypair()
    keys = _owner_keys("test-owner-1", pub_hex)
    env = _TempEnv(initial_epoch="0")
    try:
        request_id = f"req::{uuid.uuid4()}"
        idempotency_key = f"idem::{uuid.uuid4()}"
        entry_id = re_lib._entry_id(request_id, idempotency_key)
        journal_dir, by_rid_dir, by_idem_dir = re_lib._derive_state_dirs(env.epoch_path)
        rid_path = by_rid_dir / re_lib._sha256_hex(request_id)
        idem_path = by_idem_dir / re_lib._sha256_hex(idempotency_key)

        assert re_lib._create_exclusive_json(rid_path, {"entry_id": entry_id}, 0o600)
        assert re_lib._create_exclusive_json(idem_path, {"entry_id": entry_id}, 0o600)

        summary = re_lib.recover(env.epoch_path)
        check("vector c: recover() releases both orphan indexes", summary["orphan_indexes_released"] == 2)
        check("vector c: request-id index gone", not rid_path.exists())
        check("vector c: idempotency-key index gone", not idem_path.exists())

        doc = _sign(
            _base_bump(
                actor_key_id="test-owner-1", expected_epoch=0,
                request_id=request_id, idempotency_key=idempotency_key,
            ),
            priv,
        )
        result = re_lib.apply_bump(doc, env.epoch_path, env.ledger(), keys)
        check("vector c: retry after recover() reserves fresh & bumps", result["ok"] is True)
        check("vector c: epoch advances 0 -> 1", re_lib.read_epoch(env.epoch_path) == 1)
    finally:
        env.cleanup()


def test_vector_d_intent_epoch_old_aborts_and_retry_bumps() -> None:
    """Vector d (W1 -- the closed defect): crash after intent durable,
    before the epoch temp write -- journal `intent`, epoch still `old`.
    `recover()` aborts the intent (durably, first) then releases both
    indexes; the identical retry rewrites the tombstone `aborted` ->
    `intent` and ACTUALLY BUMPS -- never `DENY_REPLAY`, never
    permanently wedged (the exact defect C6d closes)."""
    priv, pub_hex = _make_keypair()
    keys = _owner_keys("test-owner-1", pub_hex)
    env = _TempEnv(initial_epoch="0")
    try:
        request_id = f"req::{uuid.uuid4()}"
        idempotency_key = f"idem::{uuid.uuid4()}"
        entry_id = re_lib._entry_id(request_id, idempotency_key)
        journal_dir, by_rid_dir, by_idem_dir = re_lib._derive_state_dirs(env.epoch_path)
        rid_path = by_rid_dir / re_lib._sha256_hex(request_id)
        idem_path = by_idem_dir / re_lib._sha256_hex(idempotency_key)

        assert re_lib._create_exclusive_json(rid_path, {"entry_id": entry_id}, 0o600)
        assert re_lib._create_exclusive_json(idem_path, {"entry_id": entry_id}, 0o600)
        intent_entry = {
            "request_id": request_id, "idempotency_key": idempotency_key,
            "actor_key_id": "test-owner-1", "reason_code": "operator-revoke",
            "old_epoch": 0, "new_epoch": 1, "phase": "intent", "attempt_gen": 0,
            "issued_at_authority": "2026-01-01T00:00:00Z", "committed_at": None,
        }
        assert re_lib._create_exclusive_json(journal_dir / entry_id, intent_entry, 0o640)
        # Epoch stays "0" -- the CAS (step 4) never happened; this IS the
        # crash point under test.

        summary = re_lib.recover(env.epoch_path)
        check("vector d: recover() aborts the uncommitted intent", summary["resolved_aborted_and_released"] == 1)
        check(
            "vector d: journal entry rewritten to phase=aborted",
            json.loads((journal_dir / entry_id).read_text(encoding="utf-8"))["phase"] == "aborted",
        )
        check("vector d: both indexes released after abort", not rid_path.exists() and not idem_path.exists())
        check("vector d: epoch still unchanged (0) -- never fabricated", re_lib.read_epoch(env.epoch_path) == 0)

        doc = _sign(
            _base_bump(
                actor_key_id="test-owner-1", expected_epoch=0,
                request_id=request_id, idempotency_key=idempotency_key,
            ),
            priv,
        )
        result = re_lib.apply_bump(doc, env.epoch_path, env.ledger(), keys)
        check("vector d: identical retry ACTUALLY BUMPS (never DENY_REPLAY, never wedged)", result["ok"] is True)
        check("vector d: epoch advances 0 -> 1", re_lib.read_epoch(env.epoch_path) == 1)
        check(
            "vector d: tombstone reused via attempt_gen increment (not a fresh entry_id collision)",
            json.loads((journal_dir / entry_id).read_text(encoding="utf-8"))["attempt_gen"] == 1,
        )
    finally:
        env.cleanup()


def test_vector_g_intent_epoch_new_finalizes() -> None:
    """Vector g: crash after epoch commit, before the phase-commit rewrite
    -- journal `intent`, epoch already `new`. `recover()` finalizes to
    `committed`; the receipt is returned; a later replay of the same
    identity is exactly-once (same receipt, no double-bump)."""
    priv, pub_hex = _make_keypair()
    keys = _owner_keys("test-owner-1", pub_hex)
    env = _TempEnv(initial_epoch="1")  # the epoch CAS already landed (new_epoch=1)
    try:
        request_id = f"req::{uuid.uuid4()}"
        idempotency_key = f"idem::{uuid.uuid4()}"
        entry_id = re_lib._entry_id(request_id, idempotency_key)
        journal_dir, by_rid_dir, by_idem_dir = re_lib._derive_state_dirs(env.epoch_path)
        rid_path = by_rid_dir / re_lib._sha256_hex(request_id)
        idem_path = by_idem_dir / re_lib._sha256_hex(idempotency_key)

        assert re_lib._create_exclusive_json(rid_path, {"entry_id": entry_id}, 0o600)
        assert re_lib._create_exclusive_json(idem_path, {"entry_id": entry_id}, 0o600)
        intent_entry = {
            "request_id": request_id, "idempotency_key": idempotency_key,
            "actor_key_id": "test-owner-1", "reason_code": "operator-revoke",
            "old_epoch": 0, "new_epoch": 1, "phase": "intent", "attempt_gen": 0,
            "issued_at_authority": "2026-01-01T00:00:00Z", "committed_at": None,
        }
        assert re_lib._create_exclusive_json(journal_dir / entry_id, intent_entry, 0o640)

        summary = re_lib.recover(env.epoch_path)
        check("vector g: recover() finalizes the committed-but-unphased intent", summary["resolved_committed"] == 1)
        finalized = json.loads((journal_dir / entry_id).read_text(encoding="utf-8"))
        check("vector g: journal entry finalized to phase=committed", finalized["phase"] == "committed")
        check("vector g: both indexes remain (a real committed transaction)", rid_path.exists() and idem_path.exists())
        check("vector g: epoch unchanged at 1 (no second advance)", re_lib.read_epoch(env.epoch_path) == 1)

        doc = _sign(
            _base_bump(
                actor_key_id="test-owner-1", expected_epoch=1,
                request_id=request_id, idempotency_key=idempotency_key,
            ),
            priv,
        )
        result = re_lib.apply_bump(doc, env.epoch_path, env.ledger(), keys)
        check("vector g: post-finalize replay returns the SAME receipt (exactly-once)", result["ok"] is True)
        check(
            "vector g: replayed receipt matches original old/new epoch",
            result["receipt"]["old_epoch"] == 0 and result["receipt"]["new_epoch"] == 1,
        )
        check("vector g: epoch still 1 (no double-bump)", re_lib.read_epoch(env.epoch_path) == 1)
    finally:
        env.cleanup()


def test_vector_i_dangling_index_after_abort_released() -> None:
    """Vector i: crash during the `aborted` -> index-release sequence
    (partial unlink) -- `aborted` journal plus one dangling index.
    `recover()` releases the dangling index (step 3); retry re-reserves &
    bumps, exactly-once."""
    priv, pub_hex = _make_keypair()
    keys = _owner_keys("test-owner-1", pub_hex)
    env = _TempEnv(initial_epoch="0")
    try:
        request_id = f"req::{uuid.uuid4()}"
        idempotency_key = f"idem::{uuid.uuid4()}"
        entry_id = re_lib._entry_id(request_id, idempotency_key)
        journal_dir, by_rid_dir, by_idem_dir = re_lib._derive_state_dirs(env.epoch_path)
        rid_path = by_rid_dir / re_lib._sha256_hex(request_id)
        idem_path = by_idem_dir / re_lib._sha256_hex(idempotency_key)

        # The abort already rewrote phase=aborted and released the
        # by-request-id index, then crashed BEFORE releasing the
        # by-idempotency-key index -- one dangling index survives.
        assert re_lib._create_exclusive_json(idem_path, {"entry_id": entry_id}, 0o600)
        aborted_entry = {
            "request_id": request_id, "idempotency_key": idempotency_key,
            "actor_key_id": "test-owner-1", "reason_code": "operator-revoke",
            "old_epoch": 0, "new_epoch": 1, "phase": "aborted", "attempt_gen": 0,
            "issued_at_authority": "2026-01-01T00:00:00Z", "committed_at": None,
        }
        assert re_lib._create_exclusive_json(journal_dir / entry_id, aborted_entry, 0o640)
        check("vector i setup: request-id index NOT present (already released)", not rid_path.exists())
        check("vector i setup: idempotency-key index dangling", idem_path.exists())

        summary = re_lib.recover(env.epoch_path)
        check(
            "vector i: recover() releases the dangling index pointing at the aborted entry",
            summary["dangling_indexes_after_abort_released"] == 1,
        )
        check("vector i: dangling index actually gone", not idem_path.exists())

        doc = _sign(
            _base_bump(
                actor_key_id="test-owner-1", expected_epoch=0,
                request_id=request_id, idempotency_key=idempotency_key,
            ),
            priv,
        )
        result = re_lib.apply_bump(doc, env.epoch_path, env.ledger(), keys)
        check("vector i: retry re-reserves fresh and bumps (exactly-once)", result["ok"] is True)
        check("vector i: epoch advances 0 -> 1", re_lib.read_epoch(env.epoch_path) == 1)
    finally:
        env.cleanup()


def test_vector_j_cross_identity_conflict_denies() -> None:
    """Vector j (live path, no crash): the SAME `request_id` re-signed
    with a DIFFERENT `idempotency_key` (both owner-signed) -- the §3.2
    identity gate denies typed `DENY_IDENTITY_CONFLICT`: never the
    original receipt, never a bump, never a second entry; the legitimate
    entry and its indexes are untouched."""
    priv, pub_hex = _make_keypair()
    keys = _owner_keys("test-owner-1", pub_hex)
    env = _TempEnv(initial_epoch="0")
    try:
        shared_request_id = f"req::{uuid.uuid4()}"

        doc1 = _sign(
            _base_bump(actor_key_id="test-owner-1", expected_epoch=0, request_id=shared_request_id),
            priv,
        )
        first = re_lib.apply_bump(doc1, env.epoch_path, env.ledger(), keys)
        check("vector j setup: first bump succeeds", first["ok"] is True)
        check("vector j setup: epoch advances to 1", re_lib.read_epoch(env.epoch_path) == 1)

        journal_dir, by_rid_dir, by_idem_dir = re_lib._derive_state_dirs(env.epoch_path)
        first_entry_id = re_lib._entry_id(shared_request_id, doc1["idempotency_key"])
        rid_index_path = by_rid_dir / re_lib._sha256_hex(shared_request_id)
        first_idem_index_path = by_idem_dir / re_lib._sha256_hex(doc1["idempotency_key"])

        # SAME request_id, a freshly-generated (DIFFERENT) idempotency_key.
        doc2 = _sign(
            _base_bump(actor_key_id="test-owner-1", expected_epoch=1, request_id=shared_request_id),
            priv,
        )
        second = re_lib.apply_bump(doc2, env.epoch_path, env.ledger(), keys)
        check("vector j: cross-identity reuse denied", second["ok"] is False)
        check(
            "vector j: reason=identity-conflict (never the original receipt)",
            second["reason"] == re_lib.DENY_IDENTITY_CONFLICT,
        )
        check("vector j: no receipt handed back for the conflicting identity", second.get("receipt") is None)
        check("vector j: epoch NOT bumped a second time (still 1)", re_lib.read_epoch(env.epoch_path) == 1)
        check(
            "vector j: legitimate entry's by-request-id index untouched",
            rid_index_path.exists()
            and json.loads(rid_index_path.read_text(encoding="utf-8"))["entry_id"] == first_entry_id,
        )
        check("vector j: legitimate entry's by-idempotency-key index untouched", first_idem_index_path.exists())
        check(
            "vector j: legitimate journal entry still committed and unchanged",
            json.loads((journal_dir / first_entry_id).read_text(encoding="utf-8"))["phase"] == "committed",
        )
    finally:
        env.cleanup()


def test_vector_h_audit_pending_persisted_and_reconciled() -> None:
    """Vector h (§5): crash point "after phase-commit, before projection"
    -- design row h requires the committed entry's audit append to be
    "reconciled" and `audit_pending` "cleared" on recovery, which
    presupposes the entry durably PERSISTS `audit_pending` in the first
    place (Finding 1/2). Force the best-effort audit append to fail on a
    live bump (as the binding reviewer did): the immediate receipt
    reports `audit_pending=True`, and -- unlike before this fix -- the
    on-disk committed journal entry now durably records it too (it used
    to carry no such field at all, so `_receipt_ok_from_entry` silently
    reconstructed `False`). `recover()` then retries the append, it
    succeeds, and `audit_pending` is durably cleared to `False` in the
    entry -- the design's "audit reconciled" outcome. The epoch bump
    itself (exactly-once) is unaffected throughout."""
    priv, pub_hex = _make_keypair()
    keys = _owner_keys("test-owner-1", pub_hex)
    env = _TempEnv(initial_epoch="0")
    try:
        request_id = f"req::{uuid.uuid4()}"
        idempotency_key = f"idem::{uuid.uuid4()}"
        entry_id = re_lib._entry_id(request_id, idempotency_key)
        journal_dir, by_rid_dir, by_idem_dir = re_lib._derive_state_dirs(env.epoch_path)
        journal_path = journal_dir / entry_id
        audit_path = env.epoch_path.parent / (env.epoch_path.name + ".audit.jsonl")

        real_append = re_lib._append_audit_receipt

        def _failing_append(epoch_path: Path, receipt: dict) -> None:  # noqa: ARG001
            raise OSError("simulated audit-disk failure (test injection)")

        re_lib._append_audit_receipt = _failing_append
        try:
            doc = _sign(
                _base_bump(
                    actor_key_id="test-owner-1", expected_epoch=0,
                    request_id=request_id, idempotency_key=idempotency_key,
                ),
                priv,
            )
            result = re_lib.apply_bump(doc, env.epoch_path, env.ledger(), keys)
        finally:
            re_lib._append_audit_receipt = real_append  # restore before recover() below

        check("vector h: live bump still succeeds despite audit-append failure", result["ok"] is True)
        check("vector h: immediate receipt reports audit_pending=True", result["receipt"]["audit_pending"] is True)
        check("vector h: epoch advances 0 -> 1 (unaffected by audit failure)", re_lib.read_epoch(env.epoch_path) == 1)
        check("vector h: no audit line was written (the append failed)", not audit_path.exists())

        on_disk_before = json.loads(journal_path.read_text(encoding="utf-8"))
        check("vector h: on-disk committed entry has phase=committed", on_disk_before["phase"] == "committed")
        check(
            "vector h: on-disk committed entry DURABLY persists audit_pending=True (Finding 1)",
            on_disk_before.get("audit_pending") is True,
        )
        pre_receipt = re_lib._receipt_ok_from_entry(on_disk_before)
        check(
            "vector h: a receipt reconstructed from the persisted entry reports audit_pending=True "
            "(never a hardcoded False)",
            pre_receipt["receipt"]["audit_pending"] is True,
        )

        # recover() must retry the audit append (now restored to the real
        # implementation); it succeeds and durably clears audit_pending.
        summary = re_lib.recover(env.epoch_path)
        check("vector h: recover() resolves the committed entry", summary["resolved_committed"] == 1)

        on_disk_after = json.loads(journal_path.read_text(encoding="utf-8"))
        check(
            "vector h: recover() durably clears audit_pending to False in the entry",
            on_disk_after.get("audit_pending") is False,
        )
        check(
            "vector h: the retried append actually wrote exactly one audit line",
            audit_path.exists() and len(audit_path.read_text(encoding="utf-8").strip().splitlines()) == 1,
        )
        check("vector h: epoch still 1 after recover() (exactly-once intact, no double-bump)", re_lib.read_epoch(env.epoch_path) == 1)

        # A receipt reconstructed AFTER reconciliation reports the
        # correct (now-cleared) state, and the epoch bump is untouched.
        reconstructed = re_lib.resolve(
            entry_id, env.epoch_path, journal_dir, by_rid_dir, by_idem_dir, presented=None,
        )
        check(
            "vector h: reconstructed receipt reports audit_pending=False AFTER reconciliation",
            reconstructed["ok"] is True and reconstructed["receipt"]["audit_pending"] is False,
        )
        check(
            "vector h: reconstructed receipt's old/new epoch unaffected (exactly-once)",
            reconstructed["receipt"]["old_epoch"] == 0 and reconstructed["receipt"]["new_epoch"] == 1,
        )
    finally:
        env.cleanup()


def test_case2_live_reverse_cross_identity_conflict_denies() -> None:
    """Live-path mirror of shipped vector j (§3.2 identity gate), REVERSE
    direction: the SAME `idempotency_key` re-signed with a DIFFERENT
    `request_id` (both owner-signed). Vector j only covers same-
    `request_id`/different-`idempotency_key`; this exercises
    `apply_bump`'s `rid_created=True` then `idem_created=False` partial-
    reservation-rollback branch (Finding 4 case 2) on the LIVE path,
    which vector j does not reach (b/g/i reach the equivalent on-disk
    state but only through `recover()`). The binding reviewer confirmed
    the code is already correct here -- this closes the coverage-only
    gap (Finding 2); it is expected to PASS as-is."""
    priv, pub_hex = _make_keypair()
    keys = _owner_keys("test-owner-1", pub_hex)
    env = _TempEnv(initial_epoch="0")
    try:
        shared_idem_key = f"idem::{uuid.uuid4()}"

        doc1 = _sign(
            _base_bump(actor_key_id="test-owner-1", expected_epoch=0, idempotency_key=shared_idem_key),
            priv,
        )
        first = re_lib.apply_bump(doc1, env.epoch_path, env.ledger(), keys)
        check("case-2 live setup: first bump succeeds", first["ok"] is True)
        check("case-2 live setup: epoch advances to 1", re_lib.read_epoch(env.epoch_path) == 1)

        journal_dir, by_rid_dir, by_idem_dir = re_lib._derive_state_dirs(env.epoch_path)
        first_entry_id = re_lib._entry_id(doc1["request_id"], shared_idem_key)
        idem_index_path = by_idem_dir / re_lib._sha256_hex(shared_idem_key)
        first_rid_index_path = by_rid_dir / re_lib._sha256_hex(doc1["request_id"])

        # SAME idempotency_key, a freshly-generated (DIFFERENT) request_id.
        doc2 = _sign(
            _base_bump(actor_key_id="test-owner-1", expected_epoch=1, idempotency_key=shared_idem_key),
            priv,
        )
        second = re_lib.apply_bump(doc2, env.epoch_path, env.ledger(), keys)
        check("case-2 live: reverse cross-identity reuse denied", second["ok"] is False)
        check(
            "case-2 live: reason=identity-conflict (never the original receipt)",
            second["reason"] == re_lib.DENY_IDENTITY_CONFLICT,
        )
        check("case-2 live: no receipt handed back for the conflicting identity", second.get("receipt") is None)
        check("case-2 live: epoch NOT bumped a second time (still 1)", re_lib.read_epoch(env.epoch_path) == 1)

        second_rid_index_path = by_rid_dir / re_lib._sha256_hex(doc2["request_id"])
        check(
            "case-2 live: doc2's own freshly-created request-id index was rolled back (Finding 4 case 2)",
            not second_rid_index_path.exists(),
        )
        check(
            "case-2 live: legitimate entry's by-idempotency-key index untouched",
            idem_index_path.exists()
            and json.loads(idem_index_path.read_text(encoding="utf-8"))["entry_id"] == first_entry_id,
        )
        check("case-2 live: legitimate entry's by-request-id index untouched", first_rid_index_path.exists())
        check(
            "case-2 live: legitimate journal entry still committed and unchanged",
            json.loads((journal_dir / first_entry_id).read_text(encoding="utf-8"))["phase"] == "committed",
        )
    finally:
        env.cleanup()


def test_journal_absent_orphan_index_retryable() -> None:
    """Live-path mirror of the §3.3 orphan-index sweep (identity-gate row
    1): an index survives with no journal counterpart, observed directly
    on a LIVE call (not via `recover()`) -- the call itself releases the
    orphan and returns a typed retryable deny (never `DENY_REPLAY`); the
    identical next call reserves fresh and bumps."""
    priv, pub_hex = _make_keypair()
    keys = _owner_keys("test-owner-1", pub_hex)
    env = _TempEnv(initial_epoch="0")
    try:
        request_id = f"req::{uuid.uuid4()}"
        idempotency_key = f"idem::{uuid.uuid4()}"
        entry_id = re_lib._entry_id(request_id, idempotency_key)
        journal_dir, by_rid_dir, by_idem_dir = re_lib._derive_state_dirs(env.epoch_path)
        rid_path = by_rid_dir / re_lib._sha256_hex(request_id)
        assert re_lib._create_exclusive_json(rid_path, {"entry_id": entry_id}, 0o600)
        check("journal-absent setup: no journal entry present", not (journal_dir / entry_id).exists())

        doc = _sign(
            _base_bump(
                actor_key_id="test-owner-1", expected_epoch=0,
                request_id=request_id, idempotency_key=idempotency_key,
            ),
            priv,
        )
        first = re_lib.apply_bump(doc, env.epoch_path, env.ledger(), keys)
        check("journal-absent: first call denies retryable (not DENY_REPLAY)", first["ok"] is False)
        check("journal-absent: reason=bump-retry-required", first["reason"] == re_lib.DENY_RETRY)
        check("journal-absent: orphan index released by the call itself", not rid_path.exists())
        check("journal-absent: epoch unchanged", re_lib.read_epoch(env.epoch_path) == 0)

        second = re_lib.apply_bump(doc, env.epoch_path, env.ledger(), keys)
        check("journal-absent: identical retry now bumps", second["ok"] is True)
        check("journal-absent: epoch advances 0 -> 1", re_lib.read_epoch(env.epoch_path) == 1)
    finally:
        env.cleanup()


def test_recover_on_clean_state_is_a_noop() -> None:
    """`recover()` on a clean, never-touched authority StateDirectory is a
    complete no-op summary -- proves it never fabricates work on an empty
    journal/index tree, consistent with it running to completion before
    any socket would bind/listen/accept (design §3.4)."""
    env = _TempEnv(initial_epoch="0")
    try:
        summary = re_lib.recover(env.epoch_path)
        check("recover() no-op: error is None", summary.get("error") is None)
        check("recover() no-op: no orphan indexes released", summary["orphan_indexes_released"] == 0)
        check("recover() no-op: nothing resolved committed", summary["resolved_committed"] == 0)
        check("recover() no-op: nothing resolved aborted", summary["resolved_aborted_and_released"] == 0)
        check("recover() no-op: nothing quarantined", summary["resolved_quarantined"] == 0)
        check("recover() no-op: no dangling indexes", summary["dangling_indexes_after_abort_released"] == 0)
        check("recover() no-op: no legacy ledger markers", summary["legacy_ledger_markers_detected"] == 0)
    finally:
        env.cleanup()


# --------------------------------------------------------------------------
# C6a -- `authorize_launch`/`consume_launch` + the atomic single-use launch
# token (`.agents/plans/aqos-foundation-c/C6a-DESIGN-AND-AUTHORIZATION.md`
# §3.5/§4/§5). Direct library calls (no transport/socket, no peer check --
# that is `revocation_epoch_transport.build_launch_handler`'s job, exercised
# live by `test-c6a-authorize-launch-service-coverage.py`).
# --------------------------------------------------------------------------


def _base_launch_fields(**overrides) -> dict:
    fields = {
        "context_digest": "ab12",
        "task_id": "task-1",
        "task_revision": 1,
        "gateway_instance": "gw-1",
    }
    fields.update(overrides)
    return fields


def test_authorize_launch_binds_current_epoch_and_deadline() -> None:
    env = _TempEnv(initial_epoch="5")
    try:
        resp = re_lib.authorize_launch(_base_launch_fields(), env.epoch_path)
        check("authorize_launch: ok", resp.get("ok") is True)
        token = resp.get("token") or {}
        check("authorize_launch: epoch bound to current (5)", token.get("epoch") == 5)
        check("authorize_launch: deadline_ms <= 250", token.get("deadline_ms", 999) <= 250)
        check("authorize_launch: nonce present and hex", isinstance(token.get("nonce"), str) and len(token["nonce"]) == 64)
        check("authorize_launch: binding fields echoed", token.get("task_id") == "task-1" and token.get("gateway_instance") == "gw-1")
    finally:
        env.cleanup()


def test_authorize_launch_malformed_denies() -> None:
    env = _TempEnv(initial_epoch="0")
    try:
        resp = re_lib.authorize_launch({"context_digest": "ab"}, env.epoch_path)
        check("authorize_launch: malformed (missing fields) denies", resp.get("ok") is False)
        check("authorize_launch: malformed reason", resp.get("reason") == re_lib.DENY_LAUNCH_MALFORMED)
        check("authorize_launch: malformed token is None", resp.get("token") is None)
    finally:
        env.cleanup()


def test_consume_launch_succeeds_exactly_once() -> None:
    """Design §3.4/§3.5 -- the `O_EXCL` `issued -> consumed` transition
    admits at most one winning consume; a duplicate consume of the SAME
    token denies `DENY_LAUNCH_ALREADY_CONSUMED` -- the core exactly-once
    assertion."""
    env = _TempEnv(initial_epoch="0")
    try:
        token = re_lib.authorize_launch(_base_launch_fields(), env.epoch_path)["token"]
        consume_req = dict(_base_launch_fields(), nonce=token["nonce"], epoch=token["epoch"])
        first = re_lib.consume_launch(consume_req, env.epoch_path)
        check("consume_launch: first consume succeeds", first.get("ok") is True)
        check("consume_launch: receipt echoes nonce", (first.get("receipt") or {}).get("nonce") == token["nonce"])
        second = re_lib.consume_launch(consume_req, env.epoch_path)
        check("consume_launch: duplicate consume denies", second.get("ok") is False)
        check("consume_launch: duplicate reason is ALREADY_CONSUMED", second.get("reason") == re_lib.DENY_LAUNCH_ALREADY_CONSUMED)
        check("consume_launch: duplicate receipt is None", second.get("receipt") is None)
    finally:
        env.cleanup()


def test_consume_launch_unknown_nonce_denies() -> None:
    env = _TempEnv(initial_epoch="0")
    try:
        resp = re_lib.consume_launch(dict(_base_launch_fields(), nonce="ab" * 32, epoch=0), env.epoch_path)
        check("consume_launch: unknown nonce denies", resp.get("ok") is False)
        check("consume_launch: unknown nonce reason", resp.get("reason") == re_lib.DENY_LAUNCH_UNKNOWN)
    finally:
        env.cleanup()


def test_consume_launch_binding_mismatch_denies() -> None:
    env = _TempEnv(initial_epoch="0")
    try:
        token = re_lib.authorize_launch(_base_launch_fields(), env.epoch_path)["token"]
        wrong_task = dict(_base_launch_fields(task_id="wrong-task"), nonce=token["nonce"], epoch=token["epoch"])
        resp = re_lib.consume_launch(wrong_task, env.epoch_path)
        check("consume_launch: wrong task_id denies binding mismatch", resp.get("ok") is False)
        check("consume_launch: binding mismatch reason", resp.get("reason") == re_lib.DENY_LAUNCH_BINDING_MISMATCH)
        # The genuinely-bound token is still consumable afterward -- the mismatch attempt
        # mutated no ledger state (design §2.2: "every deny is fail-closed").
        correct = dict(_base_launch_fields(), nonce=token["nonce"], epoch=token["epoch"])
        follow_up = re_lib.consume_launch(correct, env.epoch_path)
        check("consume_launch: correctly-bound token still consumable after a mismatch attempt", follow_up.get("ok") is True)
    finally:
        env.cleanup()


def test_consume_launch_expired_denies() -> None:
    env = _TempEnv(initial_epoch="0")
    try:
        issued_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
        token = re_lib.authorize_launch(_base_launch_fields(), env.epoch_path, now=issued_at)["token"]
        past_deadline = issued_at + timedelta(milliseconds=token["deadline_ms"] + 1)
        resp = re_lib.consume_launch(
            dict(_base_launch_fields(), nonce=token["nonce"], epoch=token["epoch"]),
            env.epoch_path, now=past_deadline,
        )
        check("consume_launch: past-deadline consume denies", resp.get("ok") is False)
        check("consume_launch: expired reason", resp.get("reason") == re_lib.DENY_LAUNCH_EXPIRED)
    finally:
        env.cleanup()


def _issued_record_path(env: "_TempEnv", token_nonce: str) -> Path:
    """`launch-ledger/issued/<nonce>` for a given `_TempEnv` -- mirrors
    `_derive_launch_ledger_dirs`'s own layout (siblings of `epoch_path`)."""
    return env.epoch_path.parent / "launch-ledger" / "issued" / token_nonce


def _corrupt_issued_record(env: "_TempEnv", token_nonce: str, **overrides) -> None:
    """Load the genuinely-issued `issued/<nonce>` record and rewrite it with
    the given field overrides -- simulates a corrupted/tampered persisted
    record without touching the durable single-use O_EXCL primitive
    itself (that stays exercised by the legitimate-path tests)."""
    path = _issued_record_path(env, token_nonce)
    record = json.loads(path.read_text(encoding="utf-8"))
    record.update(overrides)
    if any(v is _REMOVE for v in overrides.values()):
        for key, value in list(overrides.items()):
            if value is _REMOVE:
                record.pop(key, None)
    path.write_text(json.dumps(record), encoding="utf-8")


_REMOVE = object()


def test_consume_launch_malformed_persisted_record_denies() -> None:
    """Cohort REJECT binding-review 20260925 finding 1 -- Codex/Antigravity
    reproduced THREE malformed-persisted-record accepts (bad internal
    nonce, oversized `deadline_ms`, a `bool` `task_revision` matching an
    `int` revision via Python's `bool`-is-`int`-subclass equality); a
    fourth vector (a missing required field) is added here for full
    closed-schema coverage. After the fix, EVERY one of these must deny
    `DENY_LAUNCH_UNKNOWN` (fail-closed, malformed persisted state), never
    be consumed."""
    env = _TempEnv(initial_epoch="0")
    try:
        # (a) stored internal nonce disagrees with the ledger key/request nonce.
        token = re_lib.authorize_launch(_base_launch_fields(), env.epoch_path)["token"]
        _corrupt_issued_record(env, token["nonce"], nonce="f" * 64)
        resp_a = re_lib.consume_launch(
            dict(_base_launch_fields(), nonce=token["nonce"], epoch=token["epoch"]), env.epoch_path,
        )
        check("malformed-record: tampered internal nonce denies", resp_a.get("ok") is False)
        check("malformed-record: tampered internal nonce reason is UNKNOWN", resp_a.get("reason") == re_lib.DENY_LAUNCH_UNKNOWN)

        # (b) deadline_ms above the design's <=250ms ceiling.
        token_b = re_lib.authorize_launch(_base_launch_fields(), env.epoch_path)["token"]
        _corrupt_issued_record(env, token_b["nonce"], deadline_ms=100000)
        resp_b = re_lib.consume_launch(
            dict(_base_launch_fields(), nonce=token_b["nonce"], epoch=token_b["epoch"]), env.epoch_path,
        )
        check("malformed-record: oversized deadline_ms denies", resp_b.get("ok") is False)
        check("malformed-record: oversized deadline_ms reason is UNKNOWN", resp_b.get("reason") == re_lib.DENY_LAUNCH_UNKNOWN)

        # (c) task_revision persisted as a bool -- `True == 1` in Python, so a naive
        # equality-only binding check silently accepted this as revision 1.
        token_c = re_lib.authorize_launch(_base_launch_fields(), env.epoch_path)["token"]
        _corrupt_issued_record(env, token_c["nonce"], task_revision=True)
        resp_c = re_lib.consume_launch(
            dict(_base_launch_fields(), nonce=token_c["nonce"], epoch=token_c["epoch"]), env.epoch_path,
        )
        check("malformed-record: bool task_revision denies", resp_c.get("ok") is False)
        check("malformed-record: bool task_revision reason is UNKNOWN", resp_c.get("reason") == re_lib.DENY_LAUNCH_UNKNOWN)

        # (d) a required field missing entirely (closed-schema field-set check).
        token_d = re_lib.authorize_launch(_base_launch_fields(), env.epoch_path)["token"]
        _corrupt_issued_record(env, token_d["nonce"], gateway_instance=_REMOVE)
        resp_d = re_lib.consume_launch(
            dict(_base_launch_fields(), nonce=token_d["nonce"], epoch=token_d["epoch"]), env.epoch_path,
        )
        check("malformed-record: missing field denies", resp_d.get("ok") is False)
        check("malformed-record: missing field reason is UNKNOWN", resp_d.get("reason") == re_lib.DENY_LAUNCH_UNKNOWN)

        # The legitimate issue -> consume-once path is UNDISTURBED by the above --
        # a freshly-issued, untouched token still consumes exactly once.
        good_token = re_lib.authorize_launch(_base_launch_fields(), env.epoch_path)["token"]
        good_req = dict(_base_launch_fields(), nonce=good_token["nonce"], epoch=good_token["epoch"])
        good_first = re_lib.consume_launch(good_req, env.epoch_path)
        check("malformed-record: untouched token still consumes once", good_first.get("ok") is True)
        good_second = re_lib.consume_launch(good_req, env.epoch_path)
        check("malformed-record: untouched token's second consume still ALREADY_CONSUMED", good_second.get("reason") == re_lib.DENY_LAUNCH_ALREADY_CONSUMED)
    finally:
        env.cleanup()


def test_consume_launch_backward_clock_denies_not_yet_valid() -> None:
    """Cohort REJECT binding-review 20260925 finding 2 -- the <=250ms
    `deadline_ms` was only ever an UPPER bound; a `moment < issued_at`
    presentation (backward wall-clock step, or a replayed/backdated
    request) was previously accepted because the old freshness check was
    upper-bound-only. After the fix this denies the NEW
    `DENY_LAUNCH_NOT_YET_VALID`, and the legitimate at-or-after-issuance
    consume still succeeds exactly once."""
    env = _TempEnv(initial_epoch="0")
    try:
        issued_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
        token = re_lib.authorize_launch(_base_launch_fields(), env.epoch_path, now=issued_at)["token"]
        before_issuance = issued_at - timedelta(milliseconds=1000)
        resp = re_lib.consume_launch(
            dict(_base_launch_fields(), nonce=token["nonce"], epoch=token["epoch"]),
            env.epoch_path, now=before_issuance,
        )
        check("backward-clock: moment < issued_at denies", resp.get("ok") is False)
        check("backward-clock: reason is NOT_YET_VALID", resp.get("reason") == re_lib.DENY_LAUNCH_NOT_YET_VALID)

        # The SAME token, presented at-or-after issuance, still consumes exactly once --
        # the lower bound never disturbed a legitimately-timed consume.
        on_time = re_lib.consume_launch(
            dict(_base_launch_fields(), nonce=token["nonce"], epoch=token["epoch"]),
            env.epoch_path, now=issued_at,
        )
        check("backward-clock: at-issuance consume still succeeds", on_time.get("ok") is True)
        duplicate = re_lib.consume_launch(
            dict(_base_launch_fields(), nonce=token["nonce"], epoch=token["epoch"]),
            env.epoch_path, now=issued_at,
        )
        check("backward-clock: duplicate consume still ALREADY_CONSUMED", duplicate.get("reason") == re_lib.DENY_LAUNCH_ALREADY_CONSUMED)
    finally:
        env.cleanup()


def test_same_lock_ordering_bump_before_issuance_read_and_denied() -> None:
    """Design §4 -- "a bump committed before issuance is read and denied":
    a REAL signed `apply_bump` commits first; `authorize_launch` afterward
    binds the NEW epoch; a token presenting the stale (pre-bump) epoch at
    consume denies `DENY_LAUNCH_EPOCH_SUPERSEDED` (its bound epoch no
    longer matches `read_epoch()`)."""
    priv, pub_hex = _make_keypair()
    keys = _owner_keys("test-owner-launch-1", pub_hex)
    env = _TempEnv(initial_epoch="0")
    try:
        doc = _sign(_base_bump(actor_key_id="test-owner-launch-1", expected_epoch=0), priv)
        bump_resp = re_lib.apply_bump(doc, env.epoch_path, env.ledger(), keys)
        check("ordering: real apply_bump commits (0 -> 1)", bump_resp.get("ok") is True)

        issue_resp = re_lib.authorize_launch(_base_launch_fields(), env.epoch_path)
        token = issue_resp["token"]
        check("ordering: post-bump issuance binds the NEW epoch (1)", token.get("epoch") == 1)

        # A hand-crafted request PRESENTING the stale pre-bump epoch (0) against the
        # genuinely-issued token's nonce -- the binding check catches the mismatch first.
        stale_presented = dict(_base_launch_fields(), nonce=token["nonce"], epoch=0)
        stale_resp = re_lib.consume_launch(stale_presented, env.epoch_path)
        check("ordering: presenting the stale epoch denies (binding mismatch)", stale_resp.get("ok") is False)
        check("ordering: stale-epoch presentation reason", stale_resp.get("reason") == re_lib.DENY_LAUNCH_BINDING_MISMATCH)

        # The correctly-bound (new-epoch) consume still succeeds once -- the bump-before-
        # issuance revocation never blocked a launch that was actually issued AFTER it.
        correct_resp = re_lib.consume_launch(dict(_base_launch_fields(), nonce=token["nonce"], epoch=1), env.epoch_path)
        check("ordering: correctly new-epoch-bound consume succeeds", correct_resp.get("ok") is True)
    finally:
        env.cleanup()


def test_same_lock_ordering_bump_after_issuance_ordered_after_denies_supersession() -> None:
    """Design §4 -- "a bump after issuance is ordered strictly after the
    declared launch point": `authorize_launch` issues first (binds the
    OLD epoch); a REAL signed `apply_bump` commits after; the outstanding
    token's `consume_launch` re-reads the epoch under the lock, sees it
    advanced, and denies `DENY_LAUNCH_EPOCH_SUPERSEDED` -- the
    post-issuance bump revokes the not-yet-consumed launch."""
    priv, pub_hex = _make_keypair()
    keys = _owner_keys("test-owner-launch-2", pub_hex)
    env = _TempEnv(initial_epoch="3")
    try:
        token = re_lib.authorize_launch(_base_launch_fields(), env.epoch_path)["token"]
        check("ordering: pre-bump issuance binds the OLD epoch (3)", token.get("epoch") == 3)

        doc = _sign(_base_bump(actor_key_id="test-owner-launch-2", expected_epoch=3), priv)
        bump_resp = re_lib.apply_bump(doc, env.epoch_path, env.ledger(), keys)
        check("ordering: real apply_bump commits after issuance (3 -> 4)", bump_resp.get("ok") is True)

        consume_resp = re_lib.consume_launch(dict(_base_launch_fields(), nonce=token["nonce"], epoch=3), env.epoch_path)
        check("ordering: outstanding pre-bump token denies epoch-superseded", consume_resp.get("ok") is False)
        check("ordering: epoch-superseded reason", consume_resp.get("reason") == re_lib.DENY_LAUNCH_EPOCH_SUPERSEDED)
    finally:
        env.cleanup()


def test_recover_launch_ledger_unconditional_sweep_expires_issued() -> None:
    """Design §5.2 -- the BINDING build requirement: the sweep transitions
    every surviving `issued`-without-`consumed` record to terminal
    `expired` UNCONDITIONALLY (no clock read, no elapsed-time recheck) --
    exercised here on a token whose deadline has NOT elapsed, proving the
    sweep does not wait for or check the deadline before expiring it."""
    env = _TempEnv(initial_epoch="0")
    try:
        token = re_lib.authorize_launch(_base_launch_fields(), env.epoch_path)["token"]
        summary = re_lib.recover_launch_ledger(env.epoch_path)
        check("recover_launch_ledger: no error", summary.get("error") is None)
        check("recover_launch_ledger: sweeps the surviving issued token", summary["issued_expired_unconditional"] == 1)

        post_sweep = re_lib.consume_launch(dict(_base_launch_fields(), nonce=token["nonce"], epoch=token["epoch"]), env.epoch_path)
        check("recover_launch_ledger: post-sweep consume denies (unknown, not expired)", post_sweep.get("ok") is False)
        check("recover_launch_ledger: post-sweep reason is UNKNOWN (issued/<nonce> gone)", post_sweep.get("reason") == re_lib.DENY_LAUNCH_UNKNOWN)
    finally:
        env.cleanup()


def test_recover_launch_ledger_leaves_consumed_terminal() -> None:
    """Design §5.2 -- an `issued/<nonce>` WITH a `consumed/<nonce>` present
    (a crash after the atomic consume) is left exactly as-is by the sweep
    -- exactly-once preserved, never a re-launch, never a re-consume."""
    env = _TempEnv(initial_epoch="0")
    try:
        token = re_lib.authorize_launch(_base_launch_fields(), env.epoch_path)["token"]
        consume_resp = re_lib.consume_launch(dict(_base_launch_fields(), nonce=token["nonce"], epoch=token["epoch"]), env.epoch_path)
        check("recover_launch_ledger setup: consume succeeds before recovery", consume_resp.get("ok") is True)

        summary = re_lib.recover_launch_ledger(env.epoch_path)
        check("recover_launch_ledger: already-consumed token left terminal, not swept", summary["issued_with_consumed_left_terminal"] == 1)
        check("recover_launch_ledger: nothing newly expired", summary["issued_expired_unconditional"] == 0)

        duplicate = re_lib.consume_launch(dict(_base_launch_fields(), nonce=token["nonce"], epoch=token["epoch"]), env.epoch_path)
        check("recover_launch_ledger: a second consume after recovery still denies ALREADY_CONSUMED", duplicate.get("reason") == re_lib.DENY_LAUNCH_ALREADY_CONSUMED)
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
    test_committed_replay_is_idempotent_not_denied()
    test_missing_epoch_store_is_typed_error_not_zero()
    test_malformed_epoch_store_is_typed_error()
    test_no_bootstrap_to_zero_end_to_end()
    test_tracked_revoked_owner_key_denies()

    # C6d -- deterministic journal recovery (crash vectors a-i + live-path
    # conflict vector j; design §5).
    test_vector_a_no_index_no_journal()
    test_vector_b_one_orphan_index()
    test_vector_c_two_orphan_indexes()
    test_vector_d_intent_epoch_old_aborts_and_retry_bumps()
    test_vector_g_intent_epoch_new_finalizes()
    test_vector_i_dangling_index_after_abort_released()
    test_vector_j_cross_identity_conflict_denies()
    test_vector_h_audit_pending_persisted_and_reconciled()
    test_case2_live_reverse_cross_identity_conflict_denies()
    test_journal_absent_orphan_index_retryable()
    test_recover_on_clean_state_is_a_noop()

    # C6a -- authorize_launch/consume_launch single-use launch token
    # (design §3.5 exactly-once proof, §4 same-epoch.lock ordering proof,
    # §5.2 unconditional recovery sweep).
    test_authorize_launch_binds_current_epoch_and_deadline()
    test_authorize_launch_malformed_denies()
    test_consume_launch_succeeds_exactly_once()
    test_consume_launch_unknown_nonce_denies()
    test_consume_launch_binding_mismatch_denies()
    test_consume_launch_expired_denies()
    test_consume_launch_malformed_persisted_record_denies()
    test_consume_launch_backward_clock_denies_not_yet_valid()
    test_same_lock_ordering_bump_before_issuance_read_and_denied()
    test_same_lock_ordering_bump_after_issuance_ordered_after_denies_supersession()
    test_recover_launch_ledger_unconditional_sweep_expires_issued()
    test_recover_launch_ledger_leaves_consumed_terminal()

    print(f"\n{passed} passed, {failed} failed (of {passed + failed} assertions)")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
