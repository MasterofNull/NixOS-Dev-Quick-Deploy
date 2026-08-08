#!/usr/bin/env python3
"""Offline hermetic server round-trip tests — C6-B2 `revocation_epoch_transport` /
`aq-revocation-epoch-authority`.

Complements `test-revocation-epoch.py` (which exercises `revocation_epoch.apply_bump` directly,
in-process, no socket). This file proves the TRANSPORT wired around it behaves the same way over
a real `AF_UNIX` socket, using `revocation_epoch_transport.serve()` bound to a temp-dir socket on
a background thread and `revocation_epoch_transport.send_request()` as the client — no systemd,
no real owner private key (there is none to hold anywhere in this codebase; every "signed" bump
below uses a throwaway Ed25519 keypair), no network.

Covers the freeze's C6-B2 validation ask: a signed bump sent over the socket advances the
StateDirectory-equivalent (temp-dir) epoch file; a replayed `{request_id, idempotency_key}`
denies; a malformed/garbage frame fails closed (typed deny, server keeps serving); an
unavailable owner-key allowlist fails closed.
"""
from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "scripts" / "ai" / "lib"
sys.path.insert(0, str(LIB_DIR))

import revocation_epoch as re_lib  # noqa: E402
import revocation_epoch_transport as ret  # noqa: E402

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
    request_id: str | None = None,
    idempotency_key: str | None = None,
    reason_code: str = "operator-revoke",
    scope: str = "fleet",
    ttl_seconds: int = 3600,
) -> dict:
    now = datetime.now(timezone.utc)
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


class _ServerHarness:
    """Binds `revocation_epoch_transport.serve()` to a real UDS under a fresh temp dir, on a
    daemon thread — mirrors what the confined Nix unit's `ExecStart` does, minus systemd. Each
    harness gets its own socket/epoch/ledger/owner-keys paths, so tests never share state."""

    def __init__(self, initial_epoch: str = "0") -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.epoch_path = root / "epoch"
        self.epoch_path.write_text(initial_epoch, encoding="utf-8")
        self.ledger_dir = root / "ledger"
        self.owner_keys_path = root / "owner-keys.json"
        self.socket_path = str(root / "control.sock")
        self._thread: threading.Thread | None = None

    def write_keys(self, keys_dict: dict) -> None:
        self.owner_keys_path.write_text(json.dumps(keys_dict), encoding="utf-8")

    def remove_keys(self) -> None:
        try:
            self.owner_keys_path.unlink()
        except FileNotFoundError:
            pass

    def start(self) -> None:
        # Resolved synchronously in THIS thread before the handler closure is handed to the
        # server thread — no cross-thread env race (build_env_handler reads os.environ exactly
        # once, at construction time).
        os.environ["AQ_REVOCATION_EPOCH_OWNER_KEYS_PATH"] = str(self.owner_keys_path)
        os.environ["AQ_REVOCATION_EPOCH_EPOCH_PATH"] = str(self.epoch_path)
        os.environ["AQ_REVOCATION_EPOCH_LEDGER_DIR"] = str(self.ledger_dir)
        handler = ret.build_env_handler()
        self._thread = threading.Thread(
            target=ret.serve, args=(self.socket_path, handler), daemon=True
        )
        self._thread.start()
        deadline = time.time() + 5.0
        while not os.path.exists(self.socket_path):
            if time.time() > deadline:
                raise RuntimeError("server socket never appeared")
            time.sleep(0.02)

    def send(self, request: dict) -> dict:
        return ret.send_request(self.socket_path, request)

    def cleanup(self) -> None:
        self.tmp.cleanup()


# --------------------------------------------------------------------------
# 1. Valid signed bump sent OVER THE SOCKET advances the epoch by exactly +1
# --------------------------------------------------------------------------


def test_valid_signed_bump_over_socket_advances_epoch() -> None:
    priv, pub_hex = _make_keypair()
    harness = _ServerHarness(initial_epoch="5")
    try:
        harness.write_keys(_owner_keys("test-owner-1", pub_hex))
        harness.start()
        doc = _sign(_base_bump(actor_key_id="test-owner-1", expected_epoch=5), priv)
        response = harness.send({"bump": doc})
        check("socket valid bump: ok=True", response.get("ok") is True)
        check("socket valid bump: reason=ok", response.get("reason") == re_lib.BUMP_OK)
        check(
            "socket valid bump: epoch advances 5 -> 6 on the durable store",
            re_lib.read_epoch(harness.epoch_path) == 6,
        )
        check(
            "socket valid bump: response carries a redacted receipt (no signature/key material)",
            response.get("receipt", {}).get("old_epoch") == 5
            and response.get("receipt", {}).get("new_epoch") == 6
            and "signature" not in response.get("receipt", {}),
        )
    finally:
        harness.cleanup()


# --------------------------------------------------------------------------
# 2. Replay over the socket denies (same request_id/idempotency_key, second
#    send), even with expected_epoch correctly updated -- isolates the
#    replay-ledger deny from an epoch-mismatch deny.
# --------------------------------------------------------------------------


def test_replay_over_socket_denies() -> None:
    priv, pub_hex = _make_keypair()
    harness = _ServerHarness(initial_epoch="0")
    try:
        harness.write_keys(_owner_keys("test-owner-1", pub_hex))
        harness.start()
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
        first = harness.send({"bump": doc1})
        check("replay setup: first socket bump succeeds", first.get("ok") is True)
        check("replay setup: epoch advances to 1", re_lib.read_epoch(harness.epoch_path) == 1)

        doc2 = _sign(
            _base_bump(
                actor_key_id="test-owner-1",
                expected_epoch=1,  # correctly updated -- isolates replay from epoch-mismatch
                request_id=shared_request_id,
                idempotency_key=shared_idem_key,
            ),
            priv,
        )
        second = harness.send({"bump": doc2})
        check("replay over socket: denied", second.get("ok") is False)
        check(
            "replay over socket: reason=replay-request",
            second.get("reason") == re_lib.DENY_REPLAY,
        )
        check(
            "replay over socket: epoch still 1 (no second advance)",
            re_lib.read_epoch(harness.epoch_path) == 1,
        )
    finally:
        harness.cleanup()


# --------------------------------------------------------------------------
# 3. Fail-closed on a bad frame -- malformed JSON, wrong top-level shape,
#    and raw garbage bytes all deny with a typed reason; the server keeps
#    serving afterward (proven by a valid bump succeeding right after).
# --------------------------------------------------------------------------


def test_malformed_json_frame_fails_closed() -> None:
    harness = _ServerHarness(initial_epoch="0")
    try:
        harness.write_keys(_owner_keys("test-owner-1", "0" * 64))
        harness.start()
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        sock.connect(harness.socket_path)
        try:
            sock.sendall(b"not-valid-json-{{\n")
            framed = ret.read_frame(sock)
            check("malformed JSON frame: server replies (connection not dropped)", framed.get("ok") is True)
            response = framed.get("frame", {})
            check("malformed JSON frame: ok=False", response.get("ok") is False)
            check(
                "malformed JSON frame: reason=request-malformed-json",
                response.get("reason") == ret.DENY_MALFORMED_JSON,
            )
        finally:
            sock.close()
    finally:
        harness.cleanup()


def test_wrong_top_level_shape_fails_closed() -> None:
    harness = _ServerHarness(initial_epoch="0")
    try:
        harness.write_keys(_owner_keys("test-owner-1", "0" * 64))
        harness.start()
        response = harness.send({"not_a_bump_field": True})
        check("wrong top-level shape: denied", response.get("ok") is False)
        check(
            "wrong top-level shape: reason=request-malformed-bump",
            response.get("reason") == ret.DENY_MALFORMED_BUMP,
        )
        check("wrong top-level shape: epoch unchanged", re_lib.read_epoch(harness.epoch_path) == 0)
    finally:
        harness.cleanup()


def test_garbage_bytes_then_server_still_serves_a_valid_bump() -> None:
    priv, pub_hex = _make_keypair()
    harness = _ServerHarness(initial_epoch="0")
    try:
        harness.write_keys(_owner_keys("test-owner-1", pub_hex))
        harness.start()

        # Connect, send raw non-UTF8/garbage bytes with a newline, then disconnect without
        # reading the reply -- must not crash the server loop.
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        sock.connect(harness.socket_path)
        sock.sendall(b"\xff\xfe\x00garbage-not-utf8\n")
        sock.close()

        # Server must still be serving: a valid signed bump right after succeeds normally.
        doc = _sign(_base_bump(actor_key_id="test-owner-1", expected_epoch=0), priv)
        response = harness.send({"bump": doc})
        check(
            "server survives a garbage-bytes connection and keeps serving",
            response.get("ok") is True,
        )
        check(
            "server survives garbage bytes: epoch advances 0 -> 1 for the next valid request",
            re_lib.read_epoch(harness.epoch_path) == 1,
        )
    finally:
        harness.cleanup()


# --------------------------------------------------------------------------
# 4. Owner-key allowlist unavailable (deleted) -> fail-closed, never a bypass.
# --------------------------------------------------------------------------


def test_owner_keys_unavailable_fails_closed() -> None:
    priv, pub_hex = _make_keypair()
    harness = _ServerHarness(initial_epoch="0")
    try:
        harness.write_keys(_owner_keys("test-owner-1", pub_hex))
        harness.start()
        harness.remove_keys()  # allowlist vanishes after the handler was built -- read fresh per request
        doc = _sign(_base_bump(actor_key_id="test-owner-1", expected_epoch=0), priv)
        response = harness.send({"bump": doc})
        check("owner-keys-allowlist unavailable: denied", response.get("ok") is False)
        check(
            "owner-keys-allowlist unavailable: reason=owner-keys-unavailable",
            response.get("reason") == ret.DENY_OWNER_KEYS_UNAVAILABLE,
        )
        check("owner-keys-allowlist unavailable: epoch unchanged", re_lib.read_epoch(harness.epoch_path) == 0)
    finally:
        harness.cleanup()


def main() -> int:
    test_valid_signed_bump_over_socket_advances_epoch()
    test_replay_over_socket_denies()
    test_malformed_json_frame_fails_closed()
    test_wrong_top_level_shape_fails_closed()
    test_garbage_bytes_then_server_still_serves_a_valid_bump()
    test_owner_keys_unavailable_fails_closed()

    print(f"\n{passed} passed, {failed} failed (of {passed + failed} assertions)")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
