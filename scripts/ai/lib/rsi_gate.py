"""Owner-approval binding, ownership leases and daily run budget for RSI repair dispatch.

Pure local state under one directory (default: the RSI ledger directory), serialized by a
single flock so concurrent triggers across processes/worktrees agree.  Nothing here launches
work; the dispatcher consults it only when policy `rsi.approval_binding_enabled` is true.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import socket
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

MAX_TTL_S = 24 * 3600
SCOPES = ("diagnose", "apply")  # apply covers diagnose


def _store_dir() -> Path:
    env = os.environ.get("RSI_GATE_DIR") or os.environ.get("RSI_RUNTIME_DIR")
    return Path(env) if env else Path(__file__).resolve().parents[3] / ".agent" / "collaboration"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _parse(value) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


@contextmanager
def _locked(store: Path):
    store.mkdir(parents=True, exist_ok=True)
    with (store / "rsi-gate.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def _read(path: Path) -> dict:
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError):
        raise RuntimeError(f"corrupt gate state: {path}")  # fail closed; never treat as empty


def _write(path: Path, data: dict) -> None:
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as handle:
        tmp = Path(handle.name)
        try:
            json.dump(data, handle, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)


def subject_hash(incident: dict) -> str:
    """Hash of the exact failure identity; any change to producer/path/authority/error voids approval."""
    ident = [incident.get(k, "") for k in ("producer", "path", "authority", "error")]
    return hashlib.sha256(json.dumps(ident, separators=(",", ":")).encode()).hexdigest()


def bind(incident: dict, scope: str, ttl_s: int, by: str, *, store: Path | None = None, now: datetime | None = None) -> dict:
    if scope not in SCOPES:
        raise ValueError(f"scope must be one of {SCOPES}")
    if not 0 < int(ttl_s) <= MAX_TTL_S:
        raise ValueError(f"ttl must be 1..{MAX_TTL_S} seconds")
    if not str(by).strip():
        raise ValueError("approver identity required")
    now = now or _now()
    record = {"incident_id": incident["id"], "subject_sha256": subject_hash(incident), "scope": scope,
              "by": str(by), "bound_at": _iso(now), "expires_at": _iso(now + timedelta(seconds=int(ttl_s)))}
    store = store or _store_dir()
    with _locked(store):
        path = store / "rsi-approvals.json"
        data = _read(path)
        data[incident["id"]] = record
        _write(path, data)
    return record


def check(incident: dict, scope: str, *, authorities=("owner",), store: Path | None = None,
          now: datetime | None = None) -> tuple[bool, str]:
    """Return (ok, reason).  Any doubt blocks."""
    store = store or _store_dir()
    now = now or _now()
    with _locked(store):
        try:
            record = _read(store / "rsi-approvals.json").get(incident.get("id"))
        except RuntimeError:
            return False, "approval_store_corrupt"
    if not isinstance(record, dict):
        return False, "no_approval"
    if record.get("by") not in authorities:
        return False, "approver_not_authorized"
    expires = _parse(record.get("expires_at"))
    if expires is None or expires <= now:
        return False, "approval_expired"
    if record.get("subject_sha256") != subject_hash(incident):
        return False, "approval_subject_mismatch"
    granted = record.get("scope")
    if granted not in SCOPES or SCOPES.index(granted) < SCOPES.index(scope):
        return False, "approval_scope_insufficient"
    return True, "ok"


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def claim(row_id: str, owner: str, ttl_s: int, *, store: Path | None = None, now: datetime | None = None,
          pid: int | None = None) -> bool:
    """Atomically claim a row.  Expired leases and leases whose same-host owner pid died are reclaimable."""
    store = store or _store_dir()
    now = now or _now()
    pid = os.getpid() if pid is None else pid
    host = socket.gethostname()
    with _locked(store):
        path = store / "rsi-leases.json"
        leases = _read(path)
        held = leases.get(row_id)
        if isinstance(held, dict):
            expires = _parse(held.get("expires_at"))
            stale = expires is None or expires <= now or (
                held.get("host") == host and isinstance(held.get("pid"), int) and not _pid_alive(held["pid"]))
            if not stale:
                return False
        leases[row_id] = {"owner": owner, "pid": pid, "host": host, "claimed_at": _iso(now),
                          "expires_at": _iso(now + timedelta(seconds=int(ttl_s)))}
        _write(path, leases)
        return True


def release(row_id: str, owner: str, *, store: Path | None = None) -> None:
    store = store or _store_dir()
    with _locked(store):
        path = store / "rsi-leases.json"
        leases = _read(path)
        if isinstance(leases.get(row_id), dict) and leases[row_id].get("owner") == owner:
            del leases[row_id]
            _write(path, leases)


def reserve_daily_run(state_path: Path, cap: int, *, today: str | None = None) -> tuple[bool, int]:
    """Reserve one repair run in the PRSI runtime state (same file/lock as the token budget).

    Returns (reserved, runs_today).  Reservation is kept even when the run later fails.
    cap <= 0 blocks everything: an unconfigured budget never means unlimited.
    """
    today = today or _now().strftime("%Y-%m-%d")
    lock_path = state_path.with_name(state_path.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = _read(state_path)
        if state.get("date") != today:
            state = {"date": today, "remote_tokens_used": 0, "counterfactual_samples": 0}
        used = int(state.get("rsi_runs_today", 0) or 0)
        if cap <= 0 or used >= cap:
            return False, used
        state["rsi_runs_today"] = used + 1
        state["last_updated"] = _iso(_now())
        _write(state_path, state)
        return True, used + 1
