#!/usr/bin/env python3
"""Focused offline contract tests for the C1B receipt transport."""
from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ai" / "lib"))
from workflow_deviation import build  # noqa: E402
import workflow_deviation_io as receipt_io  # noqa: E402
import workflow_deviation_transport as transport  # noqa: E402
from workflow_deviation_io import DeviationWriteError, append_receipt  # noqa: E402
from workflow_deviation_transport import (  # noqa: E402
    ACK_VERSION, HEALTH_REQUEST_VERSION, SUBMIT_VERSION, ReceiptBroker, _read_frame,
    _write_frame, client_request, record_digest, TransportUnavailable, validate_broker_response,
)


NOW = datetime(2026, 8, 8, tzinfo=timezone.utc)


def record(**changes):
    result = build(occurred_at=NOW.isoformat().replace("+00:00", "Z"),
                   source={"lane": "local", "component": "test", "phase": "c1b"},
                   reason_code="observation.failed", summary="bounded receipt",
                   root_issue_key="workflow.deviation.broker",
                   evidence=[{"kind": "test", "ref": "fixture", "digest": "a" * 64}])
    result.update(changes)
    return result


def request(broker, value, peer=None):
    return broker.handle(value, peer or (1, os.geteuid(), os.getegid()))


class FakeConnection:
    """No-network socket seam for frame/deadline/concurrency tests."""
    def __init__(self, chunks=(), *, peer_uid=None):
        self.chunks = list(chunks)
        self.sent = b""
        self.peer_uid = os.geteuid() if peer_uid is None else peer_uid
        self.closed = False

    def settimeout(self, _timeout):
        pass

    def recv(self, _size):
        return self.chunks.pop(0) if self.chunks else b""

    def sendall(self, payload):
        self.sent += payload

    def getsockopt(self, *_args):
        return __import__("struct").pack("3i", 1, self.peer_uid, os.getegid())

    def close(self):
        self.closed = True


def run():
    # Closed response parser is pure: arbitrary/ill-typed reply objects cannot
    # be returned to an agent client as a broker result.
    item = record()
    request_value = {"schema_version": SUBMIT_VERSION, "record": item}
    valid_ack = {"schema_version": ACK_VERSION, "ok": True, "deviation_id": item["deviation_id"], "record_digest": record_digest(item), "reason": None}
    assert validate_broker_response(request_value, valid_ack) == valid_ack
    for invalid in ({}, {"schema_version": ACK_VERSION, "ok": True, "deviation_id": "wrong", "record_digest": "0" * 64, "reason": None}):
        try:
            validate_broker_response(request_value, invalid)
        except TransportUnavailable:
            pass
        else:
            raise AssertionError("client must reject non-closed or unbound acknowledgements")
    valid_health = {"schema_version": "aq.workflow-deviation.health.v1", "contract_version": SUBMIT_VERSION,
                    "state": "ready", "process_epoch": "a" * 32, "accepted_unique": 0, "replayed": 0,
                    "denied": 0, "busy": 0, "inflight": 0, "oldest_receipt_epoch": 0,
                    "last_reason": None, "identity_assurance": "same_uid_transport_only"}
    assert validate_broker_response({"schema_version": HEALTH_REQUEST_VERSION}, valid_health) == valid_health
    for bad_key, bad_value in (("accepted_unique", True), ("process_epoch", "g" * 32)):
        invalid_health = dict(valid_health); invalid_health[bad_key] = bad_value
        try:
            validate_broker_response({"schema_version": HEALTH_REQUEST_VERSION}, invalid_health)
        except TransportUnavailable:
            pass
        else:
            raise AssertionError("health counters and epoch must have closed scalar types")
    oversize = FakeConnection([b"x" * (64 * 1024)])
    assert _read_frame(oversize, deadline=time.monotonic() + 1)[1] == "oversize"
    invalid_utf8 = FakeConnection([b"\xff\n"])
    assert _read_frame(invalid_utf8, deadline=time.monotonic() + 1)[1] == "malformed"
    slow = FakeConnection([])
    assert _read_frame(slow, deadline=time.monotonic() - 1)[1] == "malformed"
    class ClientFake(FakeConnection):
        def __init__(self, response):
            super().__init__([json.dumps(response).encode() + b"\n"])
        def connect(self, _path): pass
    saved_socket, saved_verify, saved_peer = transport.socket.socket, transport._verified_socket, transport.peer_credentials
    try:
        transport.socket.socket = lambda *_args: ClientFake(valid_ack)
        transport._verified_socket = lambda *_args: (1, 1)
        assert client_request("/verified.sock", os.geteuid(), request_value) == valid_ack
        inodes = iter(((1, 1), (1, 2)))
        transport._verified_socket = lambda *_args: next(inodes)
        try:
            client_request("/replaced.sock", os.geteuid(), request_value)
        except TransportUnavailable:
            pass
        else:
            raise AssertionError("replaced socket inode must deny")
        transport._verified_socket = lambda *_args: (1, 1)
        transport.peer_credentials = lambda _conn: (1, os.geteuid() + 1, 1)
        try:
            client_request("/wrong-peer.sock", os.geteuid(), request_value)
        except TransportUnavailable:
            pass
        else:
            raise AssertionError("wrong broker peer UID must deny")
    finally:
        transport.socket.socket, transport._verified_socket, transport.peer_credentials = saved_socket, saved_verify, saved_peer
    print("PASS: closed response, oversize, invalid UTF-8, and deadline frames fail closed")

    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "receipts.jsonl"
        broker = ReceiptBroker(path, os.geteuid(), clock=lambda: NOW)
        item = record()
        ack = request(broker, {"schema_version": SUBMIT_VERSION, "record": item})
        assert ack == {"schema_version": ACK_VERSION, "ok": True, "deviation_id": item["deviation_id"], "record_digest": record_digest(item), "reason": None}
        assert request(broker, {"schema_version": SUBMIT_VERSION, "record": item}) == ack
        assert len(path.read_text().splitlines()) == 1
        assert request(broker, {"schema_version": HEALTH_REQUEST_VERSION})["accepted_unique"] == 1
        assert request(broker, {"schema_version": SUBMIT_VERSION, "record": item}, (1, os.geteuid() + 1, 1))["reason"] == "peer_denied"
        assert request(broker, {"extra": 1})["reason"] == "malformed"
        assert request(broker, {"schema_version": "wrong", "record": item})["reason"] == "version_unsupported"
        forged = dict(item); forged["severity"] = "low"
        assert request(broker, {"schema_version": SUBMIT_VERSION, "record": forged})["reason"] == "derived_field_mismatch"
        changed = dict(item); changed["summary"] = "changed bytes retaining old id"
        assert request(broker, {"schema_version": SUBMIT_VERSION, "record": changed})["reason"] == "derived_field_mismatch"
        try:
            append_receipt(path, changed)
        except DeviationWriteError as exc:
            assert str(exc) == "derived-field-mismatch"
        else:
            raise AssertionError("old ID paired with changed bytes must fail derived validation")
        stale = build(occurred_at=(NOW - timedelta(days=8)).isoformat().replace("+00:00", "Z"), source={"lane":"local","component":"test","phase":"c1b"}, reason_code="observation.failed", summary="stale", root_issue_key="workflow.deviation.broker", evidence=[])
        assert request(broker, {"schema_version": SUBMIT_VERSION, "record": stale})["reason"] == "timestamp_stale"
        future = build(occurred_at=(NOW + timedelta(minutes=6)).isoformat().replace("+00:00", "Z"), source={"lane":"local","component":"test","phase":"c1b"}, reason_code="observation.failed", summary="future", root_issue_key="workflow.deviation.broker", evidence=[])
        assert request(broker, {"schema_version": SUBMIT_VERSION, "record": future})["reason"] == "timestamp_future"
        path.unlink(); path.symlink_to(Path(temp) / "target")
        assert request(ReceiptBroker(path, os.geteuid(), clock=lambda: NOW), {"schema_version": SUBMIT_VERSION, "record": item})["reason"] == "storage_unsafe"

    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "partial.jsonl"
        saved_write = receipt_io.os.write
        calls = {"value": 0}
        def partial_write(fd, value):
            calls["value"] += 1
            return saved_write(fd, value[:1] if calls["value"] == 1 else value)
        receipt_io.os.write = partial_write
        try:
            assert append_receipt(path, record()).outcome == "stored"
        finally:
            receipt_io.os.write = saved_write
        assert calls["value"] >= 2 and len(path.read_text().splitlines()) == 1
        def zero_write(_fd, _value): return 0
        receipt_io.os.write = zero_write
        try:
            append_receipt(Path(temp) / "zero.jsonl", record())
        except DeviationWriteError as exc:
            assert str(exc) == "deviation-write-short"
        else:
            raise AssertionError("zero write must fail closed")
        finally:
            receipt_io.os.write = saved_write
        print("PASS: partial and zero receipt writes cannot produce success")

    with tempfile.TemporaryDirectory() as temp:
        broker = ReceiptBroker(Path(temp) / "busy.jsonl", os.geteuid(), clock=lambda: NOW)
        broker.inflight = 4
        fifth = FakeConnection()
        broker.handle_connection(fifth)
        assert json.loads(fifth.sent)["reason"] == "busy" and broker.busy == 1 and broker.denied == 1
        broker._rate[os.geteuid()] = [time.monotonic()] * 60
        assert request(broker, {"schema_version": HEALTH_REQUEST_VERSION})["reason"] == "busy"
        assert broker.busy == 2 and broker.denied == 2
        corrupt = Path(temp) / "corrupt.jsonl"
        corrupt.write_text("{not-json}\n")
        degraded = ReceiptBroker(corrupt, os.geteuid()).health()
        assert degraded["state"] == "degraded"
        print("PASS: fifth connection, per-UID rate, and corrupt health are truthful")

    with tempfile.TemporaryDirectory() as temp:
        directory = Path(temp)
        socket_path = directory / "control.sock"
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            listener.bind(str(socket_path)); listener.listen(1)
        except PermissionError:
            # The managed test sandbox denies AF_UNIX bind. Production never
            # self-binds; the systemd socket-activation seam is therefore
            # exercised only in a permitted host/integration environment.
            listener.close()
            print("PASS: managed sandbox blocks AF_UNIX injection; host socket integration deferred to C2")
        else:
            seen = {}

            def serve_once():
                conn, _ = listener.accept()
                seen["request"], error = _read_frame(conn, deadline=time.monotonic() + 2)
                assert error is None
                _write_frame(conn, {"schema_version": ACK_VERSION, "ok": False, "deviation_id": None, "record_digest": None, "reason": "malformed"})
                conn.close(); listener.close()

            worker = threading.Thread(target=serve_once); worker.start()
            response = client_request(str(socket_path), os.geteuid(), {"schema_version": HEALTH_REQUEST_VERSION})
            worker.join()
            assert response["reason"] == "malformed" and seen["request"]["schema_version"] == HEALTH_REQUEST_VERSION
        try:
            client_request(str(directory / "missing.sock"), os.geteuid(), {"schema_version": HEALTH_REQUEST_VERSION})
        except TransportUnavailable:
            pass
        else:
            raise AssertionError("missing broker must be a typed unavailable error without fallback")

    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "race.jsonl"
        broker = ReceiptBroker(path, os.geteuid(), clock=lambda: NOW)
        item = record()
        results, errors = [], []
        start = threading.Barrier(3)

        def direct():
            try:
                start.wait(); results.append(("direct", append_receipt(path, item).outcome))
            except BaseException as exc:  # surface thread faults as test evidence
                errors.append(("direct", type(exc).__name__, str(exc)))

        def through_broker():
            try:
                start.wait()
                acknowledgement = request(broker, {"schema_version": SUBMIT_VERSION, "record": item})
                results.append(("broker", acknowledgement["ok"], acknowledgement["reason"]))
            except BaseException as exc:
                errors.append(("broker", type(exc).__name__, str(exc)))

        left = threading.Thread(target=direct); right = threading.Thread(target=through_broker)
        left.start(); right.start(); start.wait(); left.join(); right.join()
        assert not errors, f"cross-writer terminal errors: {errors!r} results={results!r}"
        assert len(path.read_text().splitlines()) == 1
        direct_outcome = next(value for lane, value, *rest in results if lane == "direct")
        broker_result = next((value, reason) for lane, value, *rest in results if lane == "broker" for reason in rest)
        assert direct_outcome in {"stored", "replayed"}
        assert broker_result == (True, None), f"unexpected broker terminal response: {results!r}"
        # One producer stored and the other observed the durable replay.  The
        # broker counter disambiguates the scheduling order without assuming
        # that the direct writer always wins the race.
        assert (direct_outcome == "stored") == (broker.accepted_unique == 0)
        assert (direct_outcome == "replayed") == (broker.accepted_unique == 1)
        assert append_receipt(path, item).outcome == "replayed"
        corrupt = Path(temp) / "corrupt.jsonl"
        corrupt_value = dict(item); corrupt_value["summary"] = "corrupt durable bytes"
        corrupt.write_text(json.dumps(corrupt_value, sort_keys=True, separators=(",", ":")) + "\n")
        assert request(ReceiptBroker(corrupt, os.geteuid(), clock=lambda: NOW), {"schema_version": SUBMIT_VERSION, "record": item})["reason"] == "conflict"

    module_text = (ROOT / "nix/modules/services/workflow-deviation-broker.nix").read_text()
    assert "AQ_WORKFLOW_DEVIATION_BROKER_UID=${toString primaryUid}" in module_text
    assert "AQ_WORKFLOW_DEVIATION_BROKER_UID=%U" not in module_text
    print("PASS: Nix injects configured numeric UID, never a runtime specifier")
    print("workflow-deviation-broker: PASS")


if __name__ == "__main__":
    run()
