#!/usr/bin/env python3
"""Hermetic C6-B3 scheduler revocation-gate and UDS epoch-reader tests."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "scripts" / "ai" / "lib"
sys.path.insert(0, str(LIB))

import capability_lease as cl  # noqa: E402
import dispatch  # noqa: E402
import revocation_epoch  # noqa: E402
import revocation_epoch_transport  # noqa: E402
import slot_queue  # noqa: E402
from scheduler import Band  # noqa: E402


def _load_capability_gate():
    path = REPO / "ai-stack" / "switchboard" / "capability_lease_gate.py"
    spec = importlib.util.spec_from_file_location("c6_test_capability_lease_gate", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CAPABILITY_GATE = _load_capability_gate()


@contextmanager
def _environment(**updates):
    previous = {key: os.environ.get(key) for key in updates}
    try:
        for key, value in updates.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _key_material() -> tuple[bytes, dict]:
    key = Ed25519PrivateKey.generate()
    private = key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    public = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    keys = {
        "schema_version": "1",
        "revision": 1,
        "keys": [{"key_id": "test-scheduler-key", "ed25519_public_key": public, "status": "active"}],
    }
    return private, keys


def _context(private: bytes, *, epoch: int = 4, expires_delta: int = 3600, audience: str | None = None) -> dict:
    moment = datetime.now(timezone.utc).replace(microsecond=0)
    context = {
        "schema": "aq.scheduler-lease-context/1",
        "schema_version": "1",
        "context_id": f"sched-ctx::{time.time_ns()}",
        "lease_id": f"lease::{time.time_ns()}",
        "grant_digest": "a" * 64,
        "task_id": "task-c6-b3",
        "audience": audience or "aq-f2.5-slot-queue",
        "principal": "test-agent",
        "dispatch_mode": "agent",
        "action_class": "run_cmd",
        "trust_tier": 2,
        "policy_revision": 1,
        "issued_at": moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": (moment + timedelta(seconds=expires_delta)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "revocation_epoch": epoch,
        "issuer_key_id": "test-scheduler-key",
        "sig_scheme": cl.SIG_SCHEME_ED25519,
        "signature": "",
    }
    context["signature"] = cl.sign_ed25519(context, private)
    return context


def _with_epoch(epoch_or_values):
    original = revocation_epoch.resolve_current_epoch
    if isinstance(epoch_or_values, list):
        values = iter(epoch_or_values)
        revocation_epoch.resolve_current_epoch = lambda: next(values)
    else:
        revocation_epoch.resolve_current_epoch = lambda: epoch_or_values
    return original


def _acquire(root: Path, context: dict, keys: dict, run_id: str = "run"):
    slot_queue._slot_free = lambda _url: True
    return slot_queue.acquire(
        root,
        run_id,
        "unused-test-endpoint",
        10,
        band=Band.P2_CONSENSUS_VALIDATION,
        scheduler_context=context,
        signer_keys_json=keys,
    )


def test_read_epoch_round_trip() -> None:
    with tempfile.TemporaryDirectory(prefix="c6-epoch-uds-") as tmp:
        root = Path(tmp)
        epoch_path = root / "epoch"
        epoch_path.write_text("7\n", encoding="utf-8")
        with _environment(
            AQ_REVOCATION_EPOCH_EPOCH_PATH=str(epoch_path),
            AQ_REVOCATION_EPOCH_LEDGER_DIR=str(root / "ledger"),
            AQ_REVOCATION_EPOCH_OWNER_KEYS_PATH=str(root / "unused-owner-keys.json"),
        ):
            handler = revocation_epoch_transport.build_env_handler()
            original_send = revocation_epoch_transport.send_request

            class FrameSource:
                def __init__(self, payload: bytes) -> None:
                    self.payload = payload

                def recv(self, _size: int) -> bytes:
                    payload, self.payload = self.payload, b""
                    return payload

            def in_process_send(_path, request, timeout=5.0):
                del timeout
                wire = (json.dumps(request, sort_keys=True) + "\n").encode("utf-8")
                framed = revocation_epoch_transport.read_frame(FrameSource(wire))
                return handler(framed["frame"], None)

            revocation_epoch_transport.send_request = in_process_send
            try:
                assert revocation_epoch.resolve_current_epoch("hermetic-transport") == 7
            finally:
                revocation_epoch_transport.send_request = original_send
            malformed = handler({"op": "read-epoch", "extra": True}, None)
            assert malformed["ok"] is False
            oversized = revocation_epoch_transport.read_frame(FrameSource(b"x" * 2048), max_bytes=1024)
            assert oversized["ok"] is False
            assert oversized["reason"] == revocation_epoch_transport.DENY_OVERSIZE
            assert epoch_path.read_text(encoding="utf-8") == "7\n", "read op mutated epoch"


def test_flag_off_byte_parity() -> None:
    original_epoch = revocation_epoch.resolve_current_epoch
    original_verify = dispatch.verify_ingress_scheduler_context

    def forbidden(*_args, **_kwargs):
        raise AssertionError("flag-OFF hot path called C6 authority/verifier")

    revocation_epoch.resolve_current_epoch = forbidden
    dispatch.verify_ingress_scheduler_context = forbidden
    try:
        with tempfile.TemporaryDirectory(prefix="c6-off-") as tmp, _environment(
            CAPABILITY_SCHEDULER_LEASE_GATE="0",
            AQ_LEASE_POLICY_EPOCH="9",
        ):
            root = Path(tmp)
            slot_queue._slot_free = lambda _url: True
            result = slot_queue.acquire(root, "legacy", "unused-test-endpoint", 10)
            assert result.queue_depth == 1
            slot_queue.release(root, "legacy")
            with slot_queue._LockedState(root) as state:
                assert state.running is None and state.queue == []
            assert CAPABILITY_GATE.resolve_current_epoch() == 9
    finally:
        revocation_epoch.resolve_current_epoch = original_epoch
        dispatch.verify_ingress_scheduler_context = original_verify


def test_flag_on_valid_context_acquires() -> None:
    private, keys = _key_material()
    context = _context(private)
    original = _with_epoch(4)
    try:
        with tempfile.TemporaryDirectory(prefix="c6-valid-") as tmp, _environment(
            CAPABILITY_SCHEDULER_LEASE_GATE="1"
        ):
            root = Path(tmp)
            assert CAPABILITY_GATE.resolve_current_epoch() == 4
            result = _acquire(root, context, keys, "valid")
            assert result.queue_depth == 1
            slot_queue.release(root, "valid")
            markers = list((root / ".agents" / "delegation" / "scheduler-lease-reservations").glob("*.json"))
            assert len(markers) == 1
            assert json.loads(markers[0].read_text(encoding="utf-8"))["reservation_state"] == "released"
    finally:
        revocation_epoch.resolve_current_epoch = original


def test_forged_expired_wrong_audience_deny() -> None:
    private, keys = _key_material()
    valid = _context(private)
    forged = dict(valid)
    forged["action_class"] = "forged"
    candidates = [
        forged,
        _context(private, expires_delta=-60),
        _context(private, audience="wrong-audience"),
    ]
    original = _with_epoch(4)
    try:
        with _environment(CAPABILITY_SCHEDULER_LEASE_GATE="1"):
            for index, candidate in enumerate(candidates):
                with tempfile.TemporaryDirectory(prefix="c6-deny-") as tmp:
                    try:
                        _acquire(Path(tmp), candidate, keys, f"deny-{index}")
                    except slot_queue.SlotQueueLeaseDenied:
                        pass
                    else:
                        raise AssertionError(f"invalid candidate {index} acquired")
                    assert not (Path(tmp) / ".agents" / "delegation" / "scheduler-state.json").exists()
    finally:
        revocation_epoch.resolve_current_epoch = original


def test_replay_denies() -> None:
    private, keys = _key_material()
    context = _context(private)
    original = _with_epoch(4)
    try:
        with tempfile.TemporaryDirectory(prefix="c6-replay-") as tmp, _environment(
            CAPABILITY_SCHEDULER_LEASE_GATE="1"
        ):
            root = Path(tmp)
            _acquire(root, context, keys, "first")
            slot_queue.release(root, "first")
            try:
                _acquire(root, context, keys, "replay")
            except slot_queue.SlotQueueLeaseDenied as exc:
                assert exc.reason == slot_queue.DENY_RESERVATION_REPLAY
            else:
                raise AssertionError("replayed scheduler context acquired")
    finally:
        revocation_epoch.resolve_current_epoch = original


def test_epoch_bump_drops_held_reservation() -> None:
    private, keys = _key_material()
    context = _context(private)
    original = _with_epoch([4, 4, 5])
    try:
        with tempfile.TemporaryDirectory(prefix="c6-revoked-") as tmp, _environment(
            CAPABILITY_SCHEDULER_LEASE_GATE="1"
        ):
            root = Path(tmp)
            try:
                _acquire(root, context, keys, "revoked")
            except slot_queue.SlotQueueLeaseDenied:
                pass
            else:
                raise AssertionError("epoch-bumped held reservation acquired")
            with slot_queue._LockedState(root) as state:
                assert state.running is None and state.queue == []
            marker = next((root / ".agents" / "delegation" / "scheduler-lease-reservations").glob("*.json"))
            assert json.loads(marker.read_text(encoding="utf-8"))["reservation_state"] == "revoked-before-execution"
    finally:
        revocation_epoch.resolve_current_epoch = original


def test_authority_unreachable_denies_never_zero() -> None:
    private, keys = _key_material()
    context = _context(private, epoch=0)
    original = revocation_epoch.resolve_current_epoch

    with _environment(AQ_REVOCATION_EPOCH_SOCKET_PATH=None):
        try:
            original()
        except revocation_epoch.EpochAuthorityError as exc:
            assert exc.reason == revocation_epoch.EPOCH_AUTHORITY_ERR_SOCKET_UNSET
        else:
            raise AssertionError("absent authority socket returned an epoch sentinel")

    def unavailable():
        raise revocation_epoch.EpochAuthorityError("connect-failed")

    revocation_epoch.resolve_current_epoch = unavailable
    try:
        with tempfile.TemporaryDirectory(prefix="c6-unreachable-") as tmp, _environment(
            CAPABILITY_SCHEDULER_LEASE_GATE="1",
            AQ_LEASE_POLICY_EPOCH="0",
        ):
            root = Path(tmp)
            try:
                _acquire(root, context, keys, "unreachable")
            except slot_queue.SlotQueueLeaseDenied as exc:
                assert exc.reason == slot_queue.DENY_EPOCH_AUTHORITY
            else:
                raise AssertionError("unreachable authority fell back to epoch zero")
            assert CAPABILITY_GATE.resolve_current_epoch() is None
            assert not (root / ".agents" / "delegation" / "scheduler-state.json").exists()
    finally:
        revocation_epoch.resolve_current_epoch = original


def main() -> int:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    passed = 0
    for test in tests:
        test()
        passed += 1
        print(f"PASS: {test.__name__}")
    print(f"{passed} passed, 0 failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
