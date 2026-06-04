"""
attention_queue.py — Phase 86 Human-in-the-Loop alert queue library.

Single writer interface for all alert producers. NO code outside this module
should read or write .agents/attention/ATTENTION.json directly.

Concurrency model:
  - fcntl.LOCK_EX on file descriptor for all reads and writes (max 3 × 50ms retry)
  - aq-approve / aq-reject re-check status == "pending" under lock before mutating
  - Dedup: hash(source + title) skips push if identical pending alert exists
  - GC: alerts past expires_at are moved to ATTENTION_ARCHIVE.jsonl on each push

Autonomy boundaries:
  auto_ok        — system handled it; logged to archive immediately, never blocks
  rebuild_required — staged a Nix change; pending until human runs nixos-rebuild
  human_gate     — must not execute until aq-approve runs

Usage:
    from attention_queue import push, get_pending, resolve, AlertSpec
    push("health-spider", "critical", "human_gate",
         title="Service llama-cpp DOWN",
         detail="HTTP 000 for 3 consecutive checks",
         proposed_action="Restart llama-cpp.service via: sudo systemctl restart llama-cpp.service")
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent.parent
# Allow processes (e.g. coordinator running from Nix store) to set the live path.
_ATTENTION_DIR = Path(os.environ["ATTENTION_QUEUE_DIR"]) if "ATTENTION_QUEUE_DIR" in os.environ else _REPO_ROOT / ".agents" / "attention"
_QUEUE_FILE = _ATTENTION_DIR / "ATTENTION.json"
_ARCHIVE_FILE = _ATTENTION_DIR / "ATTENTION_ARCHIVE.jsonl"

_SCHEMA_VERSION = "1.0"
_DEFAULT_TTL_S = 86400      # 24h
_MAX_ACTIVE = 50            # overflow cap — oldest get auto-deferred
_LOCK_RETRY = 3
_LOCK_RETRY_DELAY_S = 0.05  # 50ms

# Phase 117.2 — mirror snapshot for ai-system-state (runs as ai-hybrid, can't read
# live repo path when /home/hyperd is 700). Written by the calling process (ai-hybrid
# or hyperd); ai-system-state reads it as a fallback. Silent no-op if path unwritable.
_MIRROR_PATH = Path(
    os.environ.get(
        "ATTENTION_MIRROR_PATH",
        "/var/lib/ai-stack/hybrid/telemetry/attention-snapshot.json",
    )
)


# ── data types ────────────────────────────────────────────────────────────────

@dataclass
class AlertSpec:
    source: str
    severity: str            # critical | high | medium | low
    autonomy_boundary: str   # auto_ok | rebuild_required | human_gate
    title: str               # ≤80 chars
    detail: str
    proposed_action: str
    payload: dict = field(default_factory=dict)
    executor: Optional[str] = None   # shell cmd or Python callable key to run on approve
    ttl_s: int = _DEFAULT_TTL_S

    _VALID_SEVERITY = {"critical", "high", "medium", "low"}
    _VALID_BOUNDARY = {"auto_ok", "rebuild_required", "human_gate"}

    def validate(self) -> None:
        if self.severity not in self._VALID_SEVERITY:
            raise ValueError(f"severity must be one of {self._VALID_SEVERITY}")
        if self.autonomy_boundary not in self._VALID_BOUNDARY:
            raise ValueError(f"autonomy_boundary must be one of {self._VALID_BOUNDARY}")
        if not self.title.strip():
            raise ValueError("title must not be empty")
        if len(self.title) > 80:
            raise ValueError(f"title must be ≤80 chars, got {len(self.title)}")
        if not (60 <= self.ttl_s <= 86400 * 7):
            raise ValueError(f"ttl_s must be 60–604800, got {self.ttl_s}")


# ── internal helpers ─────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _expires_iso(ttl_s: int) -> str:
    return datetime.fromtimestamp(
        time.time() + ttl_s, tz=timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")


def _dedup_key(source: str, title: str) -> str:
    return hashlib.sha256(f"{source}:{title}".encode()).hexdigest()[:16]


def _ensure_dirs() -> None:
    _ATTENTION_DIR.mkdir(parents=True, exist_ok=True)


def _load_queue(fh) -> dict:
    """Read and parse the queue file. fh must be open with lock held."""
    fh.seek(0)
    content = fh.read()
    if not content.strip():
        return {"schema_version": _SCHEMA_VERSION, "alerts": []}
    return json.loads(content)


def _save_queue(fh, data: dict) -> None:
    """Write queue back to file. fh must be open with lock held."""
    fh.seek(0)
    fh.truncate()
    fh.write(json.dumps(data, indent=2))
    fh.flush()
    os.fsync(fh.fileno())


def _write_mirror_snapshot(alerts: list) -> None:
    """Write a lightweight snapshot to the /var/lib mirror path for ai-system-state.

    Called after any queue mutation. Silent no-op when path is unwritable (before
    tmpfiles 0770 fix is deployed, or when running without write access).
    """
    pending = [a for a in alerts if a.get("status") == "pending"]
    cutoff = (datetime.now(timezone.utc).replace(microsecond=0).isoformat()[:16]).replace("T", " ")
    snapshot = {
        "pending_human_gate": len(pending),
        "pending_items": [(a.get("title") or "?")[:60] for a in pending[:5]],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        _MIRROR_PATH.write_text(json.dumps(snapshot))
    except OSError:
        pass


def _append_archive(alert: dict) -> None:
    """Append a resolved/expired alert to the append-only archive."""
    _ensure_dirs()
    with open(_ARCHIVE_FILE, "a", encoding="utf-8") as af:
        af.write(json.dumps(alert) + "\n")


def _emit_contention_event(attempt: int, duration_ms: float, error_code: str | None) -> None:
    """Emit queue_lock_contention to hybrid-events.jsonl for Rust threshold gate (92.5)."""
    telemetry_path = _REPO_ROOT / ".agents" / "telemetry" / "hybrid-events.jsonl"
    try:
        event = {
            "event_type": "queue_lock_contention",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": "attention_queue.py",
            "details": {
                "lock_operation": "fcntl.flock",
                "attempt_count": attempt,
                "duration_ms": round(duration_ms, 2),
                "error_code": error_code,
            },
        }
        with open(telemetry_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    except OSError:
        pass  # telemetry is best-effort


def _acquire_lock(fh, exclusive: bool = True) -> bool:
    """Try to acquire fcntl lock with retries. Returns True on success."""
    lock_type = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
    t_start = time.monotonic()
    for attempt in range(1, _LOCK_RETRY + 1):
        try:
            fcntl.flock(fh, lock_type | fcntl.LOCK_NB)
            if attempt > 1:
                # Emit contention event only when retries were needed
                _emit_contention_event(attempt, (time.monotonic() - t_start) * 1000, None)
            return True
        except BlockingIOError as e:
            time.sleep(_LOCK_RETRY_DELAY_S)
            if attempt == _LOCK_RETRY:
                _emit_contention_event(attempt, (time.monotonic() - t_start) * 1000, str(e.errno))
    return False


def _gc_expired(alerts: List[dict]) -> tuple[List[dict], List[dict]]:
    """Split alerts into (active, expired). Expired = past expires_at and still pending."""
    now = time.time()
    active, expired = [], []
    for a in alerts:
        if a.get("status") == "pending":
            expires_at = a.get("expires_at", "")
            try:
                exp_ts = datetime.fromisoformat(expires_at.replace("Z", "+00:00")).timestamp()
                if now > exp_ts:
                    a = {**a, "status": "expired", "resolved_at": _now_iso()}
                    expired.append(a)
                    continue
            except (ValueError, AttributeError):
                pass
        active.append(a)
    return active, expired


def _notify_desktop(title: str, severity: str, boundary: str) -> None:
    """Fire notify-send for critical/high human_gate alerts only."""
    if boundary != "human_gate" or severity not in ("critical", "high"):
        return
    try:
        urgency = "critical" if severity == "critical" else "normal"
        subprocess.run(
            ["notify-send", "-u", urgency, "AI Stack: Attention Required", title],
            timeout=3, capture_output=True, check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass  # notify-send not available — terminal hook still fires


# ── public API ────────────────────────────────────────────────────────────────

def push(
    source: str,
    severity: str,
    autonomy_boundary: str,
    title: str,
    detail: str,
    proposed_action: str,
    payload: Optional[dict] = None,
    executor: Optional[str] = None,
    ttl_s: int = _DEFAULT_TTL_S,
) -> Optional[str]:
    """Push an alert onto the queue. Returns alert id, or None if deduped/skipped.

    auto_ok alerts are written directly to archive and never block the queue.
    """
    spec = AlertSpec(
        source=source, severity=severity, autonomy_boundary=autonomy_boundary,
        title=title, detail=detail, proposed_action=proposed_action,
        payload=payload or {}, executor=executor, ttl_s=ttl_s,
    )
    spec.validate()

    alert_id = f"attn-{str(uuid.uuid4())[:8]}"
    now = _now_iso()
    alert = {
        "id": alert_id,
        "source": source,
        "severity": severity,
        "autonomy_boundary": autonomy_boundary,
        "title": title,
        "detail": detail,
        "payload": payload or {},
        "proposed_action": proposed_action,
        "executor": executor,
        "status": "auto_executed" if autonomy_boundary == "auto_ok" else "pending",
        "created_at": now,
        "expires_at": _expires_iso(ttl_s),
        "resolved_at": now if autonomy_boundary == "auto_ok" else None,
        "resolved_by": "system",
    }

    # auto_ok: archive immediately, never touch the active queue
    if autonomy_boundary == "auto_ok":
        _ensure_dirs()
        _append_archive(alert)
        return alert_id

    _ensure_dirs()
    dedup = _dedup_key(source, title)

    with open(_QUEUE_FILE, "a+", encoding="utf-8") as fh:
        if not _acquire_lock(fh, exclusive=True):
            raise RuntimeError("attention_queue: could not acquire write lock after retries")
        try:
            data = _load_queue(fh)
            alerts = data.get("alerts", [])

            # GC expired alerts
            alerts, expired = _gc_expired(alerts)
            for exp in expired:
                _append_archive(exp)

            # Dedup: skip if identical pending alert exists
            existing_keys = {_dedup_key(a["source"], a["title"]) for a in alerts if a["status"] == "pending"}
            if dedup in existing_keys:
                _save_queue(fh, {**data, "alerts": alerts})
                return None  # deduped

            # Overflow cap: auto-defer oldest if at limit
            pending = [a for a in alerts if a["status"] == "pending"]
            if len(pending) >= _MAX_ACTIVE:
                oldest = sorted(pending, key=lambda a: a["created_at"])[0]
                for a in alerts:
                    if a["id"] == oldest["id"]:
                        a["status"] = "deferred"
                        a["expires_at"] = _expires_iso(3600)  # defer 1h

            alerts.append(alert)
            updated = {**data, "alerts": alerts}
            _save_queue(fh, updated)
            _write_mirror_snapshot(updated["alerts"])
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)

    _notify_desktop(title, severity, autonomy_boundary)
    return alert_id


def get_pending(source_filter: Optional[str] = None) -> List[dict]:
    """Return all pending alerts, optionally filtered by source. Read-only, no lock needed."""
    if not _QUEUE_FILE.exists():
        return []
    try:
        data = json.loads(_QUEUE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    alerts = [a for a in data.get("alerts", []) if a.get("status") == "pending"]
    if source_filter:
        alerts = [a for a in alerts if a.get("source") == source_filter]
    return sorted(alerts, key=lambda a: a.get("created_at", ""))


def get_all(include_archived: bool = False) -> List[dict]:
    """Return all alerts from the active queue."""
    if not _QUEUE_FILE.exists():
        return []
    try:
        data = json.loads(_QUEUE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    return data.get("alerts", [])


def get_by_id(alert_id: str) -> Optional[dict]:
    """Find an alert by id in the active queue."""
    for a in get_all():
        if a.get("id") == alert_id:
            return a
    return None


def resolve(alert_id: str, new_status: str, resolved_by: str = "human") -> bool:
    """Set status on a pending alert. Returns True on success.

    new_status must be one of: approved, rejected, deferred.
    Callers (aq-approve, aq-reject) must call this — never mutate JSON directly.
    """
    if new_status not in ("approved", "rejected", "deferred"):
        raise ValueError(f"invalid status {new_status!r}")
    if not _QUEUE_FILE.exists():
        return False

    with open(_QUEUE_FILE, "r+", encoding="utf-8") as fh:
        if not _acquire_lock(fh, exclusive=True):
            raise RuntimeError("attention_queue: could not acquire write lock after retries")
        try:
            data = _load_queue(fh)
            alerts = data.get("alerts", [])
            found = False
            for a in alerts:
                if a.get("id") == alert_id:
                    if a.get("status") != "pending":
                        return False  # already resolved
                    a["status"] = new_status
                    a["resolved_at"] = _now_iso()
                    a["resolved_by"] = resolved_by
                    found = True
                    resolved_alert = dict(a)
                    break
            if not found:
                return False
            # Move resolved alert to archive, remove from active queue
            data["alerts"] = [a for a in alerts if a.get("id") != alert_id]
            _save_queue(fh, data)
            _write_mirror_snapshot(data["alerts"])
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)

    _append_archive(resolved_alert)
    return True


def extend_ttl(alert_id: str, extra_hours: int) -> bool:
    """Extend the TTL of a pending alert (aq-defer). Returns True on success."""
    if not _QUEUE_FILE.exists():
        return False
    with open(_QUEUE_FILE, "r+", encoding="utf-8") as fh:
        if not _acquire_lock(fh, exclusive=True):
            raise RuntimeError("attention_queue: could not acquire write lock after retries")
        try:
            data = _load_queue(fh)
            for a in data.get("alerts", []):
                if a.get("id") == alert_id and a.get("status") == "pending":
                    a["expires_at"] = _expires_iso(extra_hours * 3600)
                    _save_queue(fh, data)
                    return True
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)
    return False


def pending_count() -> int:
    """Fast read of pending alert count. Used by shell hook (<100ms required)."""
    return len(get_pending())
