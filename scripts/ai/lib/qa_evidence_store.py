#!/usr/bin/env python3
"""Strict persistence and verification boundary for immutable QA evidence.

Production authority is fixed.  Tests may inject an isolated root explicitly through
``QAEvidenceStore.for_isolated_test``; environment variables never redirect authority.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import secrets
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


PRODUCTION_ROOT = Path("/var/lib/ai-stack/hybrid/telemetry")
REPO_PROJECTION = Path(__file__).resolve().parents[3] / ".agents" / "telemetry"
POINTER_NAME = "latest-qa-results.json"
LOCK_NAME = ".qa-evidence.lock"
SEQUENCE_NAME = ".qa-evidence-sequence"
ARTIFACT_SCHEMA = "aq.qa-evidence.v1"
POINTER_SCHEMA = "aq.qa-evidence-pointer.v1"
MAX_ARTIFACT_BYTES = 2 * 1024 * 1024
MAX_POINTER_BYTES = 4 * 1024
MAX_RETAINED_BYTES = 64 * 1024 * 1024
MAX_ARTIFACTS = 64
MAX_AGE_SECONDS = 7 * 24 * 60 * 60
_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class EvidenceStoreError(RuntimeError):
    """A stable, fail-closed QA evidence boundary error."""

    def __init__(self, reason_code: str, detail: str = "") -> None:
        self.reason_code = reason_code
        super().__init__(f"{reason_code}: {detail}" if detail else reason_code)


@dataclass(frozen=True)
class Invocation:
    run_id: str
    start_sequence: int
    started_at: str


@dataclass(frozen=True)
class VerifiedEvidence:
    payload: dict[str, Any]
    pointer: dict[str, Any]
    artifact_path: Path
    age_seconds: float
    hash_verified: bool = True


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _utc_now()).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def _decode_mount_path(value: str) -> str:
    return value.replace("\\040", " ").replace("\\011", "\t").replace("\\012", "\n").replace("\\134", "\\")


def mount_targets(mountinfo_text: str) -> set[Path]:
    """Parse mount targets from bounded Linux mountinfo text without probing mounts."""
    if len(mountinfo_text.encode()) > 4 * 1024 * 1024:
        raise EvidenceStoreError("MOUNTINFO_TOO_LARGE")
    targets: set[Path] = set()
    for line in mountinfo_text.splitlines()[:65536]:
        fields = line.split()
        if len(fields) >= 5 and "-" in fields:
            targets.add(Path(_decode_mount_path(fields[4])))
    return targets


def _default_mountinfo() -> str:
    try:
        return Path("/proc/self/mountinfo").read_text(encoding="utf-8", errors="strict")
    except OSError as exc:
        raise EvidenceStoreError("MOUNTINFO_UNAVAILABLE", str(exc)) from exc


def _assert_real_directory(path: Path, *, mountinfo_text: str, allow_ancestor_mount: bool) -> Path:
    if not path.is_absolute() or ".." in path.parts:
        raise EvidenceStoreError("ROOT_PATH_INVALID", str(path))
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError as exc:
            raise EvidenceStoreError("ROOT_MISSING", str(current)) from exc
        if stat.S_ISLNK(mode):
            raise EvidenceStoreError("ROOT_SYMLINK", str(current))
    if not stat.S_ISDIR(path.lstat().st_mode):
        raise EvidenceStoreError("ROOT_NOT_DIRECTORY", str(path))
    resolved = path.resolve(strict=True)
    if resolved != path:
        raise EvidenceStoreError("ROOT_RESOLVED_ESCAPE", f"{path} -> {resolved}")
    targets = mount_targets(mountinfo_text)
    if path in targets:
        raise EvidenceStoreError("ROOT_MOUNT_TARGET", str(path))
    if not allow_ancestor_mount:
        for target in targets:
            if target != Path(path.anchor) and target in path.parents:
                raise EvidenceStoreError("ROOT_REDIRECTED_ANCESTOR", str(target))
    return resolved


def validate_repo_projection(*, mountinfo_text: str | None = None) -> Path:
    """Prove the repository projection remains a real, distinct directory."""
    root = _assert_real_directory(
        REPO_PROJECTION,
        mountinfo_text=mountinfo_text if mountinfo_text is not None else _default_mountinfo(),
        allow_ancestor_mount=True,
    )
    if root == PRODUCTION_ROOT or root.resolve() == PRODUCTION_ROOT.resolve(strict=False):
        raise EvidenceStoreError("REPO_PROJECTION_REDIRECTED")
    return root


class QAEvidenceStore:
    """Exclusive-lock writer and strict verified reader for QA artifacts."""

    def __init__(
        self,
        root: Path = PRODUCTION_ROOT,
        *,
        isolated_test: bool = False,
        mountinfo_text: str | None = None,
    ) -> None:
        root = Path(root)
        if root != PRODUCTION_ROOT and not isolated_test:
            raise EvidenceStoreError("TEST_ROOT_REQUIRES_ISOLATION")
        if isolated_test:
            if not root.is_absolute() or root == REPO_PROJECTION or root == PRODUCTION_ROOT:
                raise EvidenceStoreError("TEST_ROOT_INVALID", str(root))
            if not root.exists():
                root.mkdir(mode=0o700, parents=True)
        self.root = _assert_real_directory(
            root,
            mountinfo_text=mountinfo_text if mountinfo_text is not None else _default_mountinfo(),
            allow_ancestor_mount=isolated_test,
        )
        self.isolated_test = isolated_test
        self.pointer_path = self.root / POINTER_NAME
        self.lock_path = self.root / LOCK_NAME
        self.sequence_path = self.root / SEQUENCE_NAME

    @classmethod
    def production(cls) -> "QAEvidenceStore":
        validate_repo_projection()
        return cls(PRODUCTION_ROOT)

    @classmethod
    def for_isolated_test(cls, root: Path, *, mountinfo_text: str = "") -> "QAEvidenceStore":
        return cls(root, isolated_test=True, mountinfo_text=mountinfo_text)

    def _open_lock(self) -> Any:
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(self.lock_path, flags, 0o600)
        except OSError as exc:
            raise EvidenceStoreError("LOCK_UNAVAILABLE", str(exc)) from exc
        os.fchmod(fd, 0o600)
        return os.fdopen(fd, "r+")

    def _atomic_write(self, target: Path, content: bytes, *, cap: int) -> None:
        if len(content) > cap:
            raise EvidenceStoreError("ARTIFACT_TOO_LARGE" if cap == MAX_ARTIFACT_BYTES else "POINTER_TOO_LARGE")
        if target.parent != self.root or target.is_symlink():
            raise EvidenceStoreError("TARGET_CONTAINMENT", str(target))
        temporary = self.root / f".{target.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp"
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            with os.fdopen(fd, "wb", closefd=False) as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.close(fd)
            fd = -1
            os.replace(temporary, target)
            os.chmod(target, 0o600, follow_symlinks=False)
            directory_fd = os.open(self.root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if fd >= 0:
                os.close(fd)
            if temporary.exists():
                failed = self.root / "retired"
                failed.mkdir(mode=0o700, exist_ok=True)
                os.replace(temporary, failed / f"failed-{int(_utc_now().timestamp())}-{temporary.name}")

    def reserve_invocation(self, run_id: str | None = None) -> Invocation:
        run_id = run_id or f"qa-{_utc_now().strftime('%Y%m%dT%H%M%S%fZ')}-{secrets.token_hex(4)}"
        if not _RUN_ID.fullmatch(run_id):
            raise EvidenceStoreError("RUN_ID_INVALID")
        with self._open_lock() as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            sequence = 0
            if self.sequence_path.exists():
                if self.sequence_path.is_symlink():
                    raise EvidenceStoreError("SEQUENCE_SYMLINK")
                try:
                    sequence = int(self.sequence_path.read_text(encoding="ascii").strip())
                except (OSError, ValueError) as exc:
                    raise EvidenceStoreError("SEQUENCE_INVALID", str(exc)) from exc
            sequence += 1
            self._atomic_write(self.sequence_path, f"{sequence}\n".encode(), cap=MAX_POINTER_BYTES)
        return Invocation(run_id=run_id, start_sequence=sequence, started_at=_iso())

    def publish(self, invocation: Invocation, results: Mapping[str, Any], *, environment: Mapping[str, Any] | None = None) -> dict[str, Any]:
        completed_at = _iso()
        payload = {
            "schema_version": ARTIFACT_SCHEMA,
            "producer": {"id": "aq-qa", "assurance": "harness_local"},
            "privacy": "internal",
            "run_id": invocation.run_id,
            "start_sequence": invocation.start_sequence,
            "started_at": invocation.started_at,
            "completed_at": completed_at,
            "environment": dict(environment or {}),
            "results": dict(results),
        }
        raw = _canonical_json(payload)
        digest = hashlib.sha256(raw).hexdigest()
        artifact_name = f"qa-results-{invocation.start_sequence:020d}-{invocation.run_id}-{digest[:16]}.json"
        artifact = self.root / artifact_name
        pointer = {
            "schema_version": POINTER_SCHEMA,
            "revision": 1,
            "run_id": invocation.run_id,
            "start_sequence": invocation.start_sequence,
            "target": artifact_name,
            "byte_length": len(raw),
            "sha256": digest,
            "completed_at": completed_at,
        }
        pointer_raw = _canonical_json(pointer)
        with self._open_lock() as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            if artifact.exists():
                raise EvidenceStoreError("ARTIFACT_COLLISION", artifact_name)
            if len(raw) > MAX_ARTIFACT_BYTES:
                quarantine = self.root / f"quarantine-{artifact_name}"
                self._atomic_write(quarantine, raw, cap=max(len(raw), MAX_ARTIFACT_BYTES + 1))
                raise EvidenceStoreError("ARTIFACT_TOO_LARGE", artifact_name)
            self._atomic_write(artifact, raw, cap=MAX_ARTIFACT_BYTES)
            current_sequence = -1
            if self.pointer_path.exists():
                try:
                    current_sequence = self._read_pointer().get("start_sequence", -1)
                except EvidenceStoreError:
                    pass
            published = invocation.start_sequence > current_sequence
            if published:
                self._atomic_write(self.pointer_path, pointer_raw, cap=MAX_POINTER_BYTES)
            self._retain_locked(protected=artifact if published else self._pointer_target_or_none())
        return {"published": published, "artifact": artifact_name, "pointer": pointer if published else None}

    def _read_pointer(self) -> dict[str, Any]:
        if not self.pointer_path.exists() or self.pointer_path.is_symlink():
            raise EvidenceStoreError("POINTER_MISSING")
        raw = self.pointer_path.read_bytes()
        if len(raw) > MAX_POINTER_BYTES:
            raise EvidenceStoreError("POINTER_TOO_LARGE")
        try:
            pointer = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise EvidenceStoreError("POINTER_INVALID_JSON", str(exc)) from exc
        required = {"schema_version", "revision", "run_id", "start_sequence", "target", "byte_length", "sha256", "completed_at"}
        if pointer.get("schema_version") != POINTER_SCHEMA or set(pointer) != required:
            raise EvidenceStoreError("POINTER_SCHEMA_INVALID")
        if pointer["revision"] != 1 or not isinstance(pointer["start_sequence"], int) or pointer["start_sequence"] < 1:
            raise EvidenceStoreError("POINTER_REVISION_INVALID")
        if not _RUN_ID.fullmatch(str(pointer["run_id"])):
            raise EvidenceStoreError("POINTER_RUN_ID_INVALID")
        return pointer

    def _target(self, name: str) -> Path:
        candidate = Path(name)
        if candidate.is_absolute() or len(candidate.parts) != 1 or candidate.name != name or ".." in candidate.parts:
            raise EvidenceStoreError("TARGET_PATH_INVALID", name)
        target = self.root / candidate
        if target.is_symlink() or target.parent.resolve(strict=True) != self.root:
            raise EvidenceStoreError("TARGET_CONTAINMENT", name)
        return target

    def _pointer_target_or_none(self) -> Path | None:
        try:
            return self._target(self._read_pointer()["target"])
        except EvidenceStoreError:
            return None

    def read_latest(self, *, max_age_seconds: int = 86400) -> VerifiedEvidence:
        pointer = self._read_pointer()
        artifact = self._target(pointer["target"])
        try:
            raw = artifact.read_bytes()
        except OSError as exc:
            raise EvidenceStoreError("ARTIFACT_MISSING", str(exc)) from exc
        if len(raw) != pointer["byte_length"] or hashlib.sha256(raw).hexdigest() != pointer["sha256"]:
            raise EvidenceStoreError("ARTIFACT_HASH_INVALID")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise EvidenceStoreError("ARTIFACT_INVALID_JSON", str(exc)) from exc
        if payload.get("schema_version") != ARTIFACT_SCHEMA:
            raise EvidenceStoreError("ARTIFACT_SCHEMA_INVALID")
        if payload.get("run_id") != pointer["run_id"] or payload.get("start_sequence") != pointer["start_sequence"]:
            raise EvidenceStoreError("ARTIFACT_POINTER_MISMATCH")
        producer = payload.get("producer") or {}
        if producer.get("id") != "aq-qa" or producer.get("assurance") != "harness_local":
            raise EvidenceStoreError("PRODUCER_UNAUTHORIZED")
        try:
            completed = datetime.fromisoformat(pointer["completed_at"].replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise EvidenceStoreError("COMPLETION_TIME_INVALID") from exc
        age = (_utc_now() - completed).total_seconds()
        if age < -300 or age > max_age_seconds:
            raise EvidenceStoreError("ARTIFACT_STALE")
        return VerifiedEvidence(payload=payload, pointer=pointer, artifact_path=artifact, age_seconds=max(age, 0.0))

    def _retain_locked(self, *, protected: Path | None) -> None:
        artifacts = []
        for path in self.root.glob("qa-results-*.json"):
            if path.is_symlink() or path == protected:
                continue
            info = path.stat()
            artifacts.append((info.st_mtime, info.st_size, path))
        artifacts.sort()
        total = sum(size for _, size, _ in artifacts) + (protected.stat().st_size if protected and protected.exists() else 0)
        count = len(artifacts) + (1 if protected and protected.exists() else 0)
        now = _utc_now().timestamp()
        archive = self.root / "retired"
        for mtime, size, path in artifacts:
            if count <= MAX_ARTIFACTS and total <= MAX_RETAINED_BYTES and now - mtime <= MAX_AGE_SECONDS:
                continue
            if not archive.exists():
                archive.mkdir(mode=0o700)
            destination = archive / f"{int(now)}-{path.name}"
            os.replace(path, destination)
            os.chmod(destination, 0o600, follow_symlinks=False)
            count -= 1
            total -= size
        if archive.exists():
            directory_fd = os.open(archive, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)


def production_store() -> QAEvidenceStore:
    return QAEvidenceStore.production()
