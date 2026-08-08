#!/usr/bin/env python3
"""Confined AF_UNIX transport for workflow-deviation receipts.

This module intentionally owns only receipt transport and durable replay.  It
does not dispatch agents, project workflow events, or make remediation
decisions.  Production obtains its listener exclusively from systemd socket
activation; tests inject an already-open listener.
"""

from __future__ import annotations

import json
import os
import socket
import stat
import struct
import threading
import time
import uuid
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from workflow_deviation import DeviationContractError, validate
from workflow_deviation_io import (
    DeviationWriteError,
    append_receipt,
    receipt_digest,
    receipt_inventory,
)

SUBMIT_VERSION = "aq.workflow-deviation.submit.v1"
ACK_VERSION = "aq.workflow-deviation.ack.v1"
HEALTH_REQUEST_VERSION = "aq.workflow-deviation.health-request.v1"
HEALTH_VERSION = "aq.workflow-deviation.health.v1"
MAX_FRAME_BYTES = 64 * 1024
IDLE_TIMEOUT_S = 0.5
REQUEST_TIMEOUT_S = 2.0
IO_TIMEOUT_S = 5.0
MAX_CONNECTIONS = 4
RATE_PER_MINUTE = 60
_UCRED_FMT = "3i"
_HEX32 = re.compile(r"^[0-9a-f]{32}$")
_REASONS = {
    "malformed", "oversize", "version_unsupported", "derived_field_mismatch",
    "timestamp_stale", "timestamp_future", "peer_denied", "busy", "conflict",
    "storage_unsafe", "storage_failed", "internal",
}


class TransportUnavailable(RuntimeError):
    """The client could not verify or connect to the host broker."""


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def record_digest(record: Mapping[str, Any]) -> str:
    return receipt_digest(record)


def _ack(ok: bool, record: Mapping[str, Any] | None = None, reason: str | None = None) -> dict[str, Any]:
    if ok:
        assert record is not None
        return {"schema_version": ACK_VERSION, "ok": True,
                "deviation_id": record["deviation_id"], "record_digest": record_digest(record), "reason": None}
    if reason not in _REASONS:
        reason = "internal"
    return {"schema_version": ACK_VERSION, "ok": False, "deviation_id": None,
            "record_digest": None, "reason": reason}


def _parse_rfc3339(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp")
    return datetime.fromisoformat(value.replace("Z", "+00:00").replace("z", "+00:00")).astimezone(timezone.utc)


def peer_credentials(conn: socket.socket) -> tuple[int, int, int] | None:
    try:
        raw = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize(_UCRED_FMT))
        return struct.unpack(_UCRED_FMT, raw)
    except (OSError, struct.error):
        return None


def _read_frame(conn: socket.socket, *, deadline: float) -> tuple[dict[str, Any] | None, str | None]:
    buf = bytearray()
    try:
        while b"\n" not in buf:
            if len(buf) >= MAX_FRAME_BYTES:
                return None, "oversize"
            if time.monotonic() >= deadline:
                return None, "malformed"
            conn.settimeout(min(IDLE_TIMEOUT_S, max(0.01, deadline - time.monotonic())))
            chunk = conn.recv(min(4096, MAX_FRAME_BYTES - len(buf)))
            if not chunk:
                break
            buf.extend(chunk)
    except (OSError, socket.timeout):
        return None, "malformed"
    if len(buf) > MAX_FRAME_BYTES:
        return None, "oversize"
    line = bytes(buf).split(b"\n", 1)[0]
    if not line:
        return None, "malformed"
    try:
        value = json.loads(line.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None, "malformed"
    return (value, None) if isinstance(value, dict) else (None, "malformed")


def _write_frame(conn: socket.socket, value: Mapping[str, Any]) -> None:
    payload = _canonical(value) + b"\n"
    if len(payload) > MAX_FRAME_BYTES:
        raise RuntimeError("response-oversize")
    conn.settimeout(IO_TIMEOUT_S)
    conn.sendall(payload)


def validate_broker_response(request: Mapping[str, Any], response: Mapping[str, Any]) -> dict[str, Any]:
    """Accept only the closed response object valid for this exact request."""
    version = request.get("schema_version")
    if version == HEALTH_REQUEST_VERSION:
        keys = {"schema_version", "contract_version", "state", "process_epoch", "accepted_unique",
                "replayed", "denied", "busy", "inflight", "oldest_receipt_epoch", "last_reason",
                "identity_assurance"}
        if set(response) != keys or response.get("schema_version") != HEALTH_VERSION:
            raise TransportUnavailable("broker-response-invalid")
        if response.get("contract_version") != SUBMIT_VERSION or response.get("state") not in {"ready", "degraded"}:
            raise TransportUnavailable("broker-response-invalid")
        if response.get("identity_assurance") != "same_uid_transport_only":
            raise TransportUnavailable("broker-response-invalid")
        if not isinstance(response.get("process_epoch"), str) or not _HEX32.fullmatch(response["process_epoch"]):
            raise TransportUnavailable("broker-response-invalid")
        if response.get("last_reason") is not None and response["last_reason"] not in _REASONS:
            raise TransportUnavailable("broker-response-invalid")
        for key in ("accepted_unique", "replayed", "denied", "busy", "inflight", "oldest_receipt_epoch"):
            if type(response.get(key)) is not int or response[key] < 0:
                raise TransportUnavailable("broker-response-invalid")
        return dict(response)
    if version != SUBMIT_VERSION or set(request) != {"schema_version", "record"}:
        raise TransportUnavailable("broker-response-invalid")
    if set(response) != {"schema_version", "ok", "deviation_id", "record_digest", "reason"}:
        raise TransportUnavailable("broker-response-invalid")
    if response.get("schema_version") != ACK_VERSION or not isinstance(response.get("ok"), bool):
        raise TransportUnavailable("broker-response-invalid")
    if response["ok"]:
        record = request.get("record")
        if not isinstance(record, Mapping) or response.get("reason") is not None:
            raise TransportUnavailable("broker-response-invalid")
        if response.get("deviation_id") != record.get("deviation_id") or response.get("record_digest") != record_digest(record):
            raise TransportUnavailable("broker-response-invalid")
    elif response.get("deviation_id") is not None or response.get("record_digest") is not None or response.get("reason") not in _REASONS:
        raise TransportUnavailable("broker-response-invalid")
    return dict(response)


class ReceiptBroker:
    """Closed request broker; caller peer UID is admission only, never lane identity."""

    def __init__(self, receipt_path: Path, expected_uid: int, clock: Callable[[], datetime] | None = None):
        self.expected_uid = expected_uid
        self.receipt_path = Path(receipt_path)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.epoch = uuid.uuid4().hex
        self.accepted_unique = self.replayed = self.denied = self.busy = self.inflight = 0
        self.last_reason: str | None = None
        self._lock = threading.Lock()
        self._rate: dict[int, list[float]] = {}

    def _deny(self, reason: str) -> dict[str, Any]:
        with self._lock:
            self.denied += 1
            self.last_reason = reason
        return _ack(False, reason=reason)

    def _busy_deny(self) -> dict[str, Any]:
        with self._lock:
            self.busy += 1
            self.denied += 1
            self.last_reason = "busy"
        return _ack(False, reason="busy")

    def _admit_rate(self, uid: int) -> bool:
        now = time.monotonic()
        with self._lock:
            entries = [item for item in self._rate.get(uid, []) if now - item < 60]
            if len(entries) >= RATE_PER_MINUTE:
                self._rate[uid] = entries
                return False
            entries.append(now)
            self._rate[uid] = entries
            return True

    def handle(self, request: Mapping[str, Any], peer: tuple[int, int, int] | None) -> dict[str, Any]:
        if peer is None or peer[1] != self.expected_uid:
            return self._deny("peer_denied")
        if not self._admit_rate(peer[1]):
            return self._busy_deny()
        if set(request) == {"schema_version"} and request.get("schema_version") == HEALTH_REQUEST_VERSION:
            return self.health()
        if set(request) != {"schema_version", "record"}:
            return self._deny("malformed")
        if request.get("schema_version") != SUBMIT_VERSION:
            return self._deny("version_unsupported")
        record = request.get("record")
        if not isinstance(record, Mapping):
            return self._deny("malformed")
        try:
            validate(record)
        except DeviationContractError as exc:
            return self._deny(
                "derived_field_mismatch"
                if str(exc).startswith("derived-") or str(exc) == "deviation-id-invalid"
                else "malformed"
            )
        try:
            now = self.clock()

            def admit_new() -> None:
                occurred = _parse_rfc3339(record["occurred_at"])
                if occurred < now - timedelta(days=7):
                    raise DeviationWriteError("timestamp-stale")
                if occurred > now + timedelta(minutes=5):
                    raise DeviationWriteError("timestamp-future")

            # Replays are identified by the shared inode primitive before the
            # callback, so accepted old evidence remains replayable.
            result = append_receipt(self.receipt_path, record, expected_uid=self.expected_uid, admit_new=admit_new)
            acknowledgement, appended = _ack(True, record), result.outcome == "stored"
        except DeviationWriteError as exc:
            if str(exc) == "derived-field-mismatch":
                return self._deny("derived_field_mismatch")
            if str(exc) == "receipt-conflict":
                return self._deny("conflict")
            if str(exc) == "timestamp-stale":
                return self._deny("timestamp_stale")
            if str(exc) == "timestamp-future":
                return self._deny("timestamp_future")
            if str(exc) == "deviation-target-unsafe":
                return self._deny("storage_unsafe")
            return self._deny("storage_failed")
        except (OSError, ValueError, DeviationContractError):
            return self._deny("storage_failed")
        with self._lock:
            if acknowledgement["ok"] and appended:
                self.accepted_unique += 1
            elif acknowledgement["ok"]:
                self.replayed += 1
            else:
                self.denied += 1
                self.last_reason = acknowledgement["reason"]
        return acknowledgement

    def health(self) -> dict[str, Any]:
        try:
            accepted, oldest = receipt_inventory(self.receipt_path, expected_uid=self.expected_uid)
            state = "ready"
        except (OSError, ValueError, PermissionError, DeviationWriteError):
            accepted, oldest, state = 0, 0, "degraded"
        with self._lock:
            return {"schema_version": HEALTH_VERSION, "contract_version": SUBMIT_VERSION, "state": state,
                    "process_epoch": self.epoch, "accepted_unique": accepted, "replayed": self.replayed,
                    "denied": self.denied, "busy": self.busy, "inflight": self.inflight,
                    "oldest_receipt_epoch": oldest, "last_reason": self.last_reason,
                    "identity_assurance": "same_uid_transport_only"}

    def handle_connection(self, conn: socket.socket) -> None:
        with self._lock:
            saturated = self.inflight >= MAX_CONNECTIONS
            if not saturated:
                self.inflight += 1
        if saturated:
            try:
                _write_frame(conn, self._busy_deny())
            finally:
                conn.close()
            return
        try:
            request, error = _read_frame(conn, deadline=time.monotonic() + REQUEST_TIMEOUT_S)
            response = self._deny(error or "malformed") if error else self.handle(request or {}, peer_credentials(conn))
            _write_frame(conn, response)
        except Exception:  # never give a caller a fabricated success
            try:
                _write_frame(conn, self._deny("internal"))
            except OSError:
                pass
        finally:
            with self._lock:
                self.inflight -= 1
            conn.close()


def serve_listener(listener: socket.socket, broker: ReceiptBroker) -> None:  # pragma: no cover - systemd/live seam
    while True:
        conn, _ = listener.accept()
        thread = threading.Thread(target=broker.handle_connection, args=(conn,), daemon=True)
        thread.start()


def systemd_listener() -> socket.socket:
    if os.environ.get("LISTEN_PID") != str(os.getpid()) or os.environ.get("LISTEN_FDS") != "1":
        raise RuntimeError("systemd-socket-activation-required")
    listener = socket.fromfd(3, socket.AF_UNIX, socket.SOCK_STREAM)
    if listener.family != socket.AF_UNIX or listener.type != socket.SOCK_STREAM:
        listener.close()
        raise RuntimeError("systemd-listener-invalid")
    return listener


def _verified_socket(path: Path, expected_uid: int) -> tuple[int, int]:
    parent = os.lstat(path.parent)
    if (not stat.S_ISDIR(parent.st_mode) or stat.S_ISLNK(parent.st_mode)
            or parent.st_uid != expected_uid or parent.st_mode & 0o022):
        raise TransportUnavailable("socket-parent-unverified")
    info = os.lstat(path)
    if (not stat.S_ISSOCK(info.st_mode) or info.st_nlink != 1 or info.st_uid != expected_uid
            or info.st_mode & 0o007):
        raise TransportUnavailable("socket-unverified")
    return info.st_dev, info.st_ino


def client_request(socket_path: str, expected_uid: int, request: Mapping[str, Any]) -> dict[str, Any]:
    """Verified client request with no direct-file fallback."""
    path = Path(socket_path)
    try:
        before = _verified_socket(path, expected_uid)
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(IO_TIMEOUT_S)
        sock.connect(str(path))
        after = _verified_socket(path, expected_uid)
        if after != before:
            raise TransportUnavailable("socket-replaced")
        peer = peer_credentials(sock)
        if peer is None or peer[1] != expected_uid:
            raise TransportUnavailable("broker-peer-unverified")
        _write_frame(sock, request)
        response, error = _read_frame(sock, deadline=time.monotonic() + IO_TIMEOUT_S)
        if error or response is None:
            raise TransportUnavailable("broker-response-invalid")
        return validate_broker_response(request, response)
    except (OSError, ValueError) as exc:
        raise TransportUnavailable("broker-unavailable") from exc
    finally:
        try:
            sock.close()  # type: ignore[name-defined]
        except (OSError, UnboundLocalError):
            pass


def submit(socket_path: str, expected_uid: int, record: Mapping[str, Any]) -> dict[str, Any]:
    return client_request(socket_path, expected_uid, {"schema_version": SUBMIT_VERSION, "record": dict(record)})


def health(socket_path: str, expected_uid: int) -> dict[str, Any]:
    return client_request(socket_path, expected_uid, {"schema_version": HEALTH_REQUEST_VERSION})


if __name__ == "__main__":  # pragma: no cover - Nix unit exercise only
    receipt = os.environ.get("AQ_WORKFLOW_DEVIATION_LOG_PATH", "").strip()
    expected = os.environ.get("AQ_WORKFLOW_DEVIATION_BROKER_UID", "").strip()
    if not receipt or not expected.isdigit():
        raise SystemExit("workflow-deviation-broker: required environment unavailable")
    serve_listener(systemd_listener(), ReceiptBroker(Path(receipt), int(expected)))
