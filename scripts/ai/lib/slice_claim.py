#!/usr/bin/env python3
"""Advisory, transaction-safe slice/path claim registry.

Claims improve coordination between cooperative lanes; they are inert until a
dispatcher or edit entrypoint elects to enforce them. They are not an access
control boundary and do not independently prevent collisions.
"""
from __future__ import annotations

import fcntl
import json
import os
import secrets
import tempfile
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import PurePosixPath
from typing import Any, Iterator


DEFAULT_STORE = ".agent/collaboration/slice-claims.json"
DEFAULT_TTL_SECONDS = 7200


@dataclass(frozen=True)
class Claim:
    slice_id: str
    lane: str
    paths: tuple[str, ...]
    created_at: float
    expires_at: float
    owner_token: str

    def to_json(self, *, include_token: bool = False) -> dict[str, Any]:
        result = asdict(self)
        result["paths"] = list(self.paths)
        if not include_token:
            result.pop("owner_token")
        return result


def _norm(path: str) -> str:
    """Accept only canonical, non-root POSIX paths relative to the repository."""
    if not isinstance(path, str) or not path or path != path.strip() or "\\" in path:
        raise ValueError("path must be a canonical non-empty POSIX relative path")
    parsed = PurePosixPath(path)
    if parsed.is_absolute() or path in {".", ".."} or any(part in {".", ".."} for part in parsed.parts):
        raise ValueError("path must not be absolute or contain dot components")
    canonical = parsed.as_posix()
    if canonical in {"", ".", "/"} or path != canonical:
        raise ValueError("path must already be canonical POSIX form")
    return canonical


def _normal_paths(paths: list[str]) -> list[str]:
    try:
        normalized = sorted({_norm(path) for path in paths})
    except (TypeError, ValueError) as exc:
        raise ValueError(str(exc)) from exc
    if not normalized:
        raise ValueError("no paths given")
    return normalized


def _overlaps(a: str, b: str) -> bool:
    pa, pb = PurePosixPath(a), PurePosixPath(b)
    return pa == pb or pa in pb.parents or pb in pa.parents


def _parse_claim(row: object, now: float) -> Claim | None:
    if not isinstance(row, dict):
        return None
    try:
        paths = tuple(_normal_paths(row["paths"]))
        claim = Claim(
            slice_id=str(row["slice_id"]), lane=str(row["lane"]), paths=paths,
            created_at=float(row["created_at"]), expires_at=float(row["expires_at"]),
            owner_token=str(row["owner_token"]),
        )
    except (KeyError, TypeError, ValueError):
        return None
    if not claim.slice_id or not claim.lane or len(claim.owner_token) < 32:
        return None
    return claim if claim.expires_at > now else None


def _read_claims(store_path: str | os.PathLike, now: float) -> list[Claim]:
    try:
        with open(store_path, encoding="utf-8") as handle:
            raw = json.load(handle)
        rows = raw.get("claims", []) if isinstance(raw, dict) else []
        if not isinstance(rows, list):
            return []
    except (OSError, ValueError, json.JSONDecodeError):
        return []
    return sorted((claim for row in rows if (claim := _parse_claim(row, now)) is not None),
                  key=lambda claim: (claim.slice_id, claim.lane))


def load_claims(store_path: str | os.PathLike = DEFAULT_STORE, *, now: float | None = None) -> list[Claim]:
    """Read active, well-formed claims without exposing owner tokens."""
    return _read_claims(store_path, time.time() if now is None else now)


def _lock_path(store_path: str | os.PathLike) -> str:
    return f"{store_path}.lock"


@contextmanager
def _transaction_lock(store_path: str | os.PathLike) -> Iterator[None]:
    """Exclusive cross-process lock for read/prune/check/write transactions."""
    directory = os.path.dirname(str(store_path)) or "."
    os.makedirs(directory, exist_ok=True)
    handle = open(_lock_path(store_path), "a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _write(store_path: str | os.PathLike, claims: list[Claim]) -> None:
    directory = os.path.dirname(str(store_path)) or "."
    os.makedirs(directory, exist_ok=True)
    payload = json.dumps({"claims": [claim.to_json(include_token=True) for claim in claims]},
                         indent=2, sort_keys=True) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=f".{os.path.basename(str(store_path))}.", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, store_path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _public_conflicts(claims: list[Claim]) -> list[dict[str, Any]]:
    return [claim.to_json() for claim in claims]


def take_claim(store_path: str | os.PathLike, slice_id: str, lane: str, paths: list[str], *,
               ttl_seconds: int = DEFAULT_TTL_SECONDS, owner_token: str | None = None,
               now: float | None = None) -> dict[str, Any]:
    """Take a claim or refresh it with its existing owner token."""
    try:
        norm_paths = _normal_paths(paths)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    if not isinstance(slice_id, str) or not slice_id or not isinstance(lane, str) or not lane:
        return {"ok": False, "error": "slice_id and lane are required"}
    if not isinstance(ttl_seconds, int) or ttl_seconds <= 0 or ttl_seconds > 86400:
        return {"ok": False, "error": "ttl_seconds must be between 1 and 86400"}
    current_time = time.time() if now is None else now
    with _transaction_lock(store_path):
        claims = _read_claims(store_path, current_time)
        existing = next((claim for claim in claims if claim.slice_id == slice_id and claim.lane == lane), None)
        if existing is not None and owner_token != existing.owner_token:
            _write(store_path, claims)
            return {"ok": False, "conflicts": _public_conflicts([existing])}
        others = [claim for claim in claims if claim is not existing]
        conflicts = [claim for claim in others if any(_overlaps(path, claimed) for path in norm_paths for claimed in claim.paths)]
        if conflicts:
            _write(store_path, claims)
            return {"ok": False, "conflicts": _public_conflicts(conflicts)}
        is_new = existing is None
        token = secrets.token_urlsafe(32) if is_new else existing.owner_token
        claim = Claim(slice_id, lane, tuple(norm_paths), current_time, current_time + ttl_seconds, token)
        _write(store_path, sorted(others + [claim], key=lambda item: (item.slice_id, item.lane)))
    result: dict[str, Any] = {"ok": True, "claim": claim.to_json()}
    if is_new:
        result["owner_token"] = token
    return result


def release_claim(store_path: str | os.PathLike, slice_id: str, lane: str, *, owner_token: str | None,
                  now: float | None = None) -> dict[str, Any]:
    """Release only the exact claim held by the supplied owner token."""
    current_time = time.time() if now is None else now
    with _transaction_lock(store_path):
        claims = _read_claims(store_path, current_time)
        target = next((claim for claim in claims if claim.slice_id == slice_id and claim.lane == lane), None)
        if target is None:
            _write(store_path, claims)
            return {"ok": False, "error": "claim not found", "released": 0}
        if owner_token != target.owner_token:
            _write(store_path, claims)
            return {"ok": False, "error": "owner token does not match", "released": 0}
        _write(store_path, [claim for claim in claims if claim is not target])
    return {"ok": True, "released": 1}


def check_paths(store_path: str | os.PathLike, paths: list[str], lane: str, *,
                now: float | None = None) -> dict[str, Any]:
    """Read-only advisory check. It does not reserve or enforce any path."""
    try:
        norm_paths = _normal_paths(paths)
    except ValueError as exc:
        return {"clear": False, "error": str(exc), "conflicts": []}
    with _transaction_lock(store_path):
        claims = _read_claims(store_path, time.time() if now is None else now)
    conflicts = [claim for claim in claims if any(_overlaps(path, claimed) for path in norm_paths for claimed in claim.paths)]
    return {"clear": not conflicts, "conflicts": _public_conflicts(conflicts)}
