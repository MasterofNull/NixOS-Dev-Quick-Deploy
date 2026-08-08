#!/usr/bin/env python3
"""The sole durable, idempotent receipt primitive for workflow deviations."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import stat
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping

from workflow_deviation import DeviationContractError, validate

MAX_RECEIPT_RECORDS = 100_000
MAX_RECEIPT_BYTES = 64 * 1024 * 1024


class DeviationWriteError(RuntimeError):
    """A receipt could not be safely scanned, replayed, or durably appended."""


@dataclass(frozen=True)
class ReceiptAppendResult:
    outcome: str  # exactly ``stored`` or ``replayed``
    record_digest: str


def canonical_receipt(record: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(record), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def receipt_digest(record: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_receipt(record)).hexdigest()


def _raise_contract_error(exc: DeviationContractError) -> None:
    # A changed body paired with a retained old deterministic ID is a derived
    # field forgery, not a generic caller-validation ambiguity.
    if str(exc) == "deviation-id-invalid":
        raise DeviationWriteError("derived-field-mismatch") from exc
    raise DeviationWriteError("receipt-invalid") from exc


def _open_locked(path: Path, expected_uid: int) -> int:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
    try:
        parent = os.lstat(path.parent)
        if (not stat.S_ISDIR(parent.st_mode) or stat.S_ISLNK(parent.st_mode)
                or parent.st_uid != expected_uid or parent.st_mode & 0o022):
            raise DeviationWriteError("deviation-target-unsafe")
        try:
            existing = os.lstat(path)
            if stat.S_ISLNK(existing.st_mode):
                raise DeviationWriteError("deviation-target-unsafe")
        except FileNotFoundError:
            pass
        flags = os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_CLOEXEC | os.O_NONBLOCK
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(path, flags, 0o640)
        metadata = os.fstat(fd)
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
                or metadata.st_uid != expected_uid or metadata.st_mode & 0o022):
            os.close(fd)
            raise DeviationWriteError("deviation-target-unsafe")
        fcntl.flock(fd, fcntl.LOCK_EX)
        return fd
    except DeviationWriteError:
        raise
    except OSError as exc:
        raise DeviationWriteError(f"deviation-append-failed:{exc.__class__.__name__}") from exc


def _scan_locked(fd: int, requested_id: str) -> tuple[bytes | None, int, int]:
    """Return the prior canonical bytes for requested ID, plus bytes/count.

    A malformed durable stream is never treated as an empty stream.  A line
    with the requested ID but non-matching bytes is explicit durable conflict;
    any other malformed line makes storage unsafe/failed for this receipt.
    """
    try:
        os.lseek(fd, 0, os.SEEK_SET)
        data = bytearray()
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > MAX_RECEIPT_BYTES:
                raise DeviationWriteError("receipt-capacity")
        if data and not data.endswith(b"\n"):
            raise DeviationWriteError("receipt-storage-corrupt")
        prior: bytes | None = None
        records: dict[str, bytes] = {}
        for raw in data.splitlines():
            if not raw:
                raise DeviationWriteError("receipt-storage-corrupt")
            try:
                decoded = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, ValueError) as exc:
                raise DeviationWriteError("receipt-storage-corrupt") from exc
            if not isinstance(decoded, Mapping):
                raise DeviationWriteError("receipt-storage-corrupt")
            same_id = decoded.get("deviation_id") == requested_id
            try:
                validate(decoded)
                canonical = canonical_receipt(decoded)
            except (DeviationContractError, TypeError, ValueError) as exc:
                if same_id:
                    raise DeviationWriteError("receipt-conflict") from exc
                raise DeviationWriteError("receipt-storage-corrupt") from exc
            if raw != canonical:
                if same_id:
                    raise DeviationWriteError("receipt-conflict")
                raise DeviationWriteError("receipt-storage-corrupt")
            record_id = decoded.get("deviation_id")
            if not isinstance(record_id, str):
                raise DeviationWriteError("receipt-storage-corrupt")
            existing = records.get(record_id)
            if existing is not None:
                # A post-amendment producer can never create even an exact
                # duplicate.  Treat any pre-existing duplicate as evidence
                # corruption rather than letting a health counter lie.
                raise DeviationWriteError("receipt-conflict" if same_id else "receipt-storage-corrupt")
            records[record_id] = canonical
            if len(records) > MAX_RECEIPT_RECORDS:
                raise DeviationWriteError("receipt-capacity")
            if same_id:
                if prior is not None and prior != canonical:
                    raise DeviationWriteError("receipt-conflict")
                prior = canonical
        return prior, len(data), len(records)
    except OSError as exc:
        raise DeviationWriteError(f"deviation-read-failed:{exc.__class__.__name__}") from exc


def _write_all(fd: int, payload: bytes) -> None:
    """Append the complete record or fail before fsync/success is possible."""
    offset = 0
    while offset < len(payload):
        written = os.write(fd, payload[offset:])
        if not isinstance(written, int) or written <= 0:
            raise DeviationWriteError("deviation-write-short")
        offset += written


def append_receipt(
    path: Path,
    record: Mapping[str, Any],
    *,
    expected_uid: int | None = None,
    admit_new: Callable[[], None] | None = None,
) -> ReceiptAppendResult:
    """Return ``stored`` or ``replayed`` using the receipt inode as one lock domain.

    Both C1A direct producers and C1B broker producers call this function.
    It never replaces, truncates, or uses a sidecar index/lock.
    """
    try:
        validate(record)
    except DeviationContractError as exc:
        _raise_contract_error(exc)
    path = Path(path)
    uid = os.geteuid() if expected_uid is None else expected_uid
    canonical = canonical_receipt(record)
    digest = hashlib.sha256(canonical).hexdigest()
    fd = _open_locked(path, uid)
    try:
        previous, size, count = _scan_locked(fd, str(record["deviation_id"]))
        if previous is not None:
            if previous == canonical:
                return ReceiptAppendResult("replayed", digest)
            raise DeviationWriteError("receipt-conflict")
        if admit_new is not None:
            admit_new()
        line = canonical + b"\n"
        if count >= MAX_RECEIPT_RECORDS or size + len(line) > MAX_RECEIPT_BYTES:
            raise DeviationWriteError("receipt-capacity")
        os.lseek(fd, 0, os.SEEK_END)
        _write_all(fd, line)
        os.fsync(fd)
        return ReceiptAppendResult("stored", digest)
    except OSError as exc:
        raise DeviationWriteError(f"deviation-append-failed:{exc.__class__.__name__}") from exc
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def receipt_inventory(path: Path, *, expected_uid: int | None = None) -> tuple[int, int]:
    """Validate the full durable stream and return unique count / oldest epoch."""
    path = Path(path)
    fd = _open_locked(path, os.geteuid() if expected_uid is None else expected_uid)
    try:
        # A harmless sentinel scans all lines through the same validation path.
        _previous, _size, count = _scan_locked(fd, "__inventory_absent__")
        os.lseek(fd, 0, os.SEEK_SET)
        data = bytearray()
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > MAX_RECEIPT_BYTES:
                raise DeviationWriteError("receipt-capacity")
        oldest = 0
        for raw in data.splitlines():
            value = json.loads(raw)
            parsed = value["occurred_at"].replace("Z", "+00:00").replace("z", "+00:00")
            epoch = int(datetime.fromisoformat(parsed).timestamp())
            oldest = min(oldest or epoch, epoch)
        return count, oldest
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
