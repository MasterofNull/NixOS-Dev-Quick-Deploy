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
import re
import shlex
import shutil
import subprocess
import sys
import time
import uuid
from urllib.parse import urlsplit
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
_STATE_FILE = _ATTENTION_DIR / "notify-state.json"
_NOTIFY_RATE_LIMIT_S = int(os.environ.get("ATTENTION_NOTIFY_RATE_LIMIT_S", "1800"))
_NOTIFY_WAIT_S = int(os.environ.get("ATTENTION_NOTIFY_WAIT_S", "900"))
_SNOOZE_S = 3600
_MAX_HELPERS = 4
_SEV_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}
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
    dedup_key: Optional[str] = None  # stable identity (source + kind); title may vary
    why: str = ""                    # one line: why it matters
    next_step: str = ""              # one line: recommended response
    command: str = ""                # exact copy-paste command
    link: str = ""                   # deep link (URL) for the alert

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


def _emit_contention_event(
    attempt: int,
    duration_ms: float,
    error_code: str | None,
    operation: str = "unknown",
) -> None:
    """Emit queue_lock_contention to hybrid-events.jsonl for retry-rate monitoring (Slice 93.14)."""
    telemetry_path = _REPO_ROOT / ".agents" / "telemetry" / "hybrid-events.jsonl"
    try:
        event = {
            "event": "queue_lock_contention",
            "event_type": "queue_lock_contention",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": "attention_queue.py",
            "operation": operation,
            "queue_path": str(_QUEUE_FILE),
            "retry_count": attempt - 1,
            "elapsed_ms": round(duration_ms, 2),
            "acquired": error_code is None,
            "error_code": error_code,
        }
        with open(telemetry_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    except OSError:
        pass  # telemetry is best-effort


def _acquire_lock(fh, exclusive: bool = True, operation: str = "unknown") -> bool:
    """Try to acquire fcntl lock with retries. Returns True on success."""
    lock_type = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
    t_start = time.monotonic()
    for attempt in range(1, _LOCK_RETRY + 1):
        try:
            fcntl.flock(fh, lock_type | fcntl.LOCK_NB)
            if attempt > 1:
                # Emit contention event only when retries were needed
                _emit_contention_event(attempt, (time.monotonic() - t_start) * 1000, None, operation)
            return True
        except BlockingIOError as e:
            time.sleep(_LOCK_RETRY_DELAY_S)
            if attempt == _LOCK_RETRY:
                _emit_contention_event(attempt, (time.monotonic() - t_start) * 1000, str(e.errno), operation)
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


# ── desktop notifications (actionable, deduped, rate-limited) ────────────────

_SECRET_RE = re.compile(
    r"(?i)(bearer\s+[a-z0-9._\-]{8,}|sk-[a-z0-9_\-]{10,}|"
    r"(?:token|secret|password|passwd|api[_-]?key)\s*[=:]\s*\S+)"
)


def _identity(source: str, title: str, dedup_key: Optional[str] = None) -> str:
    return _dedup_key(source, dedup_key if dedup_key else title)


def _alert_identity(a: dict) -> str:
    return a.get("identity") or _dedup_key(a.get("source", ""), a.get("title", ""))


def _state_update(identity: str, fn=None) -> dict:
    """Read (and optionally mutate via fn(entry)) per-identity notify state.

    State outlives individual alerts so rate-limit, replace-id and snooze
    survive TTL expiry and re-push. Own flock; never nested in the queue lock.
    """
    _ensure_dirs()
    lock = _STATE_FILE.with_suffix(".lock")
    with open(lock, "a+") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            try:
                state = json.loads(_STATE_FILE.read_text())
            except (OSError, ValueError):
                state = {}
            entry = state.setdefault(identity, {})
            if fn is not None:
                fn(entry)
                tmp = _STATE_FILE.with_suffix(".tmp")
                tmp.write_text(json.dumps(state))
                tmp.replace(_STATE_FILE)
            return dict(entry)
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


def redact(text: str) -> str:
    return _SECRET_RE.sub("[redacted]", text or "")


def _redact(text: str) -> str:
    return _SECRET_RE.sub("[redacted]", text or "")


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def dashboard_link(alert_id: str) -> str:
    base = (os.environ.get("DASHBOARD_URL") or os.environ.get("DASHBOARD_API_URL")
            or f"http://127.0.0.1:{os.environ.get('DASHBOARD_API_PORT', '8889')}")
    return f"{base.rstrip('/')}/api/alerts/{alert_id}/view"


def _origin(url: str) -> Optional[tuple]:
    try:
        u = urlsplit(url)
        if u.scheme not in ("http", "https") or not u.hostname:
            return None
        return (u.scheme, u.hostname.lower(), u.port or (443 if u.scheme == "https" else 80))
    except ValueError:
        return None


def safe_open_url(link: str, alert_id: str) -> str:
    """Alert-supplied links are agent-authored: only the dashboard origin is opened."""
    default = dashboard_link(alert_id)
    link = (link or "").strip()
    if not link or link.startswith("-") or any(c.isspace() or ord(c) < 32 for c in link):
        return default
    o = _origin(link)
    return link if o is not None and o == _origin(default) else default


def host_allowed(host_header: str) -> bool:
    """Loopback (any port) plus ATTENTION_VIEW_ALLOWED_HOSTS (comma list, host or host:port)."""
    h = (host_header or "").strip().lower()
    if not h:
        return False
    extra = {x.strip().lower() for x in os.environ.get("ATTENTION_VIEW_ALLOWED_HOSTS", "").split(",") if x.strip()}
    if h in extra:
        return True
    name = h[1:h.index("]")] if h.startswith("[") and "]" in h else h.rsplit(":", 1)[0] if h.count(":") == 1 else h
    return name in ("localhost", "127.0.0.1", "::1") or name in extra


def format_notification(alert: dict, max_body: int = 480) -> tuple:
    """Return (summary, body): specific title; what / why / next / command / id."""
    summary = _redact(alert.get("title", "Attention required"))[:100]
    detail = _redact(alert.get("detail", "")).strip()
    what = detail.splitlines()[0].strip() if detail else ""
    why = _redact(alert.get("why") or "") or (
        "Needs your decision before the stack acts." if alert.get("autonomy_boundary") == "human_gate"
        else "Needs attention.")
    nxt = _redact(alert.get("next_step") or alert.get("proposed_action") or "")
    cmd = _redact(alert.get("command") or "") or f"aq-approve show {alert.get('id', '?')}"
    lines = []
    if what and what != summary:
        lines.append(what[:160])
    lines.append(f"Why: {why[:140]}")
    if nxt:
        lines.append(f"Next: {nxt[:140]}")
    lines.append(f"Run: {cmd[:120]}")
    lines.append(f"ID: {alert.get('id', '?')}")
    body = "\n".join(lines)
    if len(body) > max_body:
        body = body[: max_body - 1] + "…"
    return _esc(summary), _esc(body)


def _actions_for(alert: dict) -> list:
    acts = []
    if alert.get("executor"):
        acts.append(("review", "Review & approve"))
    acts += [("open", "Open details"), ("show", "Show in terminal"),
             ("snooze", "Snooze 1h"), ("dismiss", "Dismiss")]
    return acts


_ACTIONS_SUPPORTED: Optional[bool] = None


def _actions_supported() -> bool:
    global _ACTIONS_SUPPORTED
    if _ACTIONS_SUPPORTED is None:
        try:
            out = subprocess.run(["notify-send", "--help"], capture_output=True, text=True, timeout=3)
            _ACTIONS_SUPPORTED = "--action" in (out.stdout + out.stderr)
        except (OSError, subprocess.TimeoutExpired):
            _ACTIONS_SUPPORTED = False
    return _ACTIONS_SUPPORTED


def _terminal_argv(cmd: str) -> Optional[list]:
    """argv that runs `cmd` in the owner's terminal and keeps the window open.

    Override with ATTENTION_TERMINAL_CMD (shlex template, `{cmd}` placeholder
    replaced by a single argument).
    """
    wrapped = f"{cmd}; echo; read -r -p 'Press Enter to close ' _"
    tpl = os.environ.get("ATTENTION_TERMINAL_CMD")
    if tpl:
        return [wrapped if t == "{cmd}" else t for t in shlex.split(tpl)]
    if shutil.which("xdg-terminal-exec"):
        return ["xdg-terminal-exec", "bash", "-c", wrapped]
    term = os.environ.get("TERMINAL")
    if term and shutil.which(term.split()[0]):
        return shlex.split(term) + ["-e", "bash", "-c", wrapped]
    for t in ("kitty", "foot", "alacritty", "konsole", "xterm"):
        if shutil.which(t):
            return [t, "-e", "bash", "-c", wrapped]
    if shutil.which("gnome-terminal"):
        return ["gnome-terminal", "--", "bash", "-c", wrapped]
    return None


def handle_action(key: str, alert_id: str, popen=subprocess.Popen) -> bool:
    """Run a notification button. Never approves without a prompt."""
    alert = get_by_id(alert_id) or {}
    detach = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                  stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        if key == "open":
            popen(["xdg-open", safe_open_url(alert.get("link") or "", alert_id)], **detach)
        elif key in ("show", "review"):
            verb = "review" if key == "review" else "show"
            argv = _terminal_argv(f"aq-approve {verb} {shlex.quote(alert_id)}")
            if not argv:
                return False
            popen(argv, **detach)
        elif key == "snooze":
            return snooze(alert_id, _SNOOZE_S)
        elif key == "dismiss":
            return resolve(alert_id, "dismissed", resolved_by="owner")
        else:
            return False
    except OSError:
        return False
    return True


def _spawn_notifier(alert_id: str) -> None:
    """Detached helper so push() never blocks on the notification."""
    try:
        subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--notify", alert_id],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True,
        )
    except OSError:
        pass


def _maybe_notify(alert: dict, escalated: bool) -> None:
    """Apply gating (snooze, rate limit per identity) then spawn the notifier."""
    if alert.get("autonomy_boundary") != "human_gate" or alert.get("severity") not in ("critical", "high"):
        return
    # Route all sub-agent and system alerts into coordinator feed/inbox rather than desktop popups:
    # Desktop notify-send popups are disabled unless ATTENTION_DESKTOP_NOTIFY=1 is explicitly requested.
    if os.environ.get("ATTENTION_DESKTOP_NOTIFY", "0") != "1":
        return
    ident = _alert_identity(alert)
    st = _state_update(ident)
    now = time.time()
    if st.get("snoozed_until", 0) > now:
        return
    if not escalated and now - st.get("notified_at", 0) < _NOTIFY_RATE_LIMIT_S:
        return
    _state_update(ident, lambda e: e.update(notified_at=now, severity=alert["severity"]))
    _spawn_notifier(alert["id"])


def _acquire_helper_slot():
    """flock-based cap on concurrent waiting helpers; None -> body-only popup."""
    _ensure_dirs()
    for i in range(_MAX_HELPERS):
        try:
            fh = open(_ATTENTION_DIR / f"notify-slot-{i}.lock", "a+")
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fh  # held until process exit
        except OSError:
            fh.close()
    return None


def _notify_main(alert_id: str) -> int:
    """Helper process body: show (or replace) the notification, wait for a button."""
    alert = get_by_id(alert_id)
    if not alert or alert.get("status") != "pending":
        return 0
    ident = _alert_identity(alert)
    summary, body = format_notification(alert)
    urgency = "critical" if alert.get("severity") == "critical" else "normal"
    cmd = ["notify-send", "-a", "AI Stack", "-u", urgency, "-p"]
    rid = _state_update(ident).get("notify_id")
    if rid:
        cmd += ["-r", str(rid)]
    slot = _acquire_helper_slot()
    with_actions = slot is not None and _actions_supported()
    if with_actions:
        cmd += [f"--action={k}={lbl}" for k, lbl in _actions_for(alert)]
    cmd += [summary, body]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    except OSError:
        return 0
    try:
        out, _ = proc.communicate(timeout=_NOTIFY_WAIT_S if with_actions else 5)
    except subprocess.TimeoutExpired:
        proc.kill()
        out = proc.communicate()[0] or ""
    lines = [l.strip() for l in (out or "").splitlines() if l.strip()]
    if lines and lines[0].isdigit():
        nid = int(lines.pop(0))
        _state_update(ident, lambda e: e.update(notify_id=nid))
    if lines:
        handle_action(lines[-1], alert_id)
    return 0


def snooze(alert_id: str, seconds: int = _SNOOZE_S) -> bool:
    """Suppress desktop notifications for this alert's identity for `seconds`."""
    a = get_by_id(alert_id)
    if not a or a.get("status") != "pending":
        return False
    until = time.time() + seconds
    _state_update(_alert_identity(a), lambda e: e.update(snoozed_until=until))
    return True


def is_snoozed(alert: dict) -> bool:
    return _state_update(_alert_identity(alert)).get("snoozed_until", 0) > time.time()


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
    dedup_key: Optional[str] = None,
    why: str = "",
    next_step: str = "",
    command: str = "",
    link: str = "",
) -> Optional[str]:
    """Push an alert onto the queue. Returns alert id, or None if deduped/skipped.

    dedup_key (optional) is a stable identity (e.g. "qa-phase-0"); when given, a
    pending alert with the same source+key is UPDATED in place if its content
    changed (returns its id) instead of creating a new alert. Without it, dedup
    is by title as before. why/next_step/command/link feed the desktop
    notification and `aq-approve show`.

    auto_ok alerts are written directly to archive and never block the queue.
    """
    spec = AlertSpec(
        source=source, severity=severity, autonomy_boundary=autonomy_boundary,
        title=title, detail=detail, proposed_action=proposed_action,
        payload=payload or {}, executor=executor, ttl_s=ttl_s,
        dedup_key=dedup_key, why=why, next_step=next_step, command=command, link=link,
    )
    spec.validate()

    alert_id = f"attn-{uuid.uuid4().hex[:16]}"
    now = _now_iso()
    alert = {
        "id": alert_id,
        "source": source,
        "severity": severity,
        "autonomy_boundary": autonomy_boundary,
        "identity": _identity(source, title, dedup_key),
        "title": title,
        "detail": detail,
        "why": why,
        "next_step": next_step,
        "command": command,
        "link": link,
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
    dedup = _identity(source, title, dedup_key)
    notify_alert, escalated = None, False

    with open(_QUEUE_FILE, "a+", encoding="utf-8") as fh:
        if not _acquire_lock(fh, exclusive=True, operation="push"):
            raise RuntimeError("attention_queue: could not acquire write lock after retries")
        try:
            data = _load_queue(fh)
            alerts = data.get("alerts", [])

            # GC expired alerts
            alerts, expired = _gc_expired(alerts)
            for exp in expired:
                _append_archive(exp)

            # Dedup: same identity pending -> update in place if changed, else skip
            existing = next((a for a in alerts if a["status"] == "pending"
                             and _alert_identity(a) == dedup), None)
            if existing is not None:
                fields = {"title": title, "detail": detail, "why": why, "next_step": next_step,
                          "command": command, "link": link, "severity": severity,
                          "proposed_action": proposed_action}
                changed = dedup_key and any(existing.get(k) != v for k, v in fields.items())
                if not changed:
                    _save_queue(fh, {**data, "alerts": alerts})
                    return None  # deduped
                escalated = _SEV_RANK[severity] > _SEV_RANK.get(existing.get("severity"), 0)
                existing.update(fields, identity=dedup, payload=payload or {},
                                updated_at=now, expires_at=_expires_iso(ttl_s))
                _save_queue(fh, {**data, "alerts": alerts})
                _write_mirror_snapshot(alerts)
                notify_alert = dict(existing)
                alert_id = existing["id"]

            if notify_alert is None:
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
                notify_alert = alert
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)

    _maybe_notify(notify_alert, escalated)
    return alert_id


def get_pending(source_filter: Optional[str] = None, include_snoozed: bool = True) -> List[dict]:
    """Return all pending alerts, optionally filtered by source. Read-only, no lock needed.

    include_snoozed=False drops alerts whose identity is snoozed (callers that notify).
    """
    if not _QUEUE_FILE.exists():
        return []
    try:
        data = json.loads(_QUEUE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    alerts = [a for a in data.get("alerts", []) if a.get("status") == "pending"]
    if source_filter:
        alerts = [a for a in alerts if a.get("source") == source_filter]
    if not include_snoozed:
        try:
            state = json.loads(_STATE_FILE.read_text())
        except (OSError, ValueError):
            state = {}
        now = time.time()
        alerts = [a for a in alerts
                  if state.get(_alert_identity(a), {}).get("snoozed_until", 0) <= now]
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

    new_status must be one of: approved, rejected, deferred, dismissed.
    Callers (aq-approve, aq-reject) must call this — never mutate JSON directly.
    """
    if new_status not in ("approved", "rejected", "deferred", "dismissed"):
        raise ValueError(f"invalid status {new_status!r}")
    if not _QUEUE_FILE.exists():
        return False

    with open(_QUEUE_FILE, "r+", encoding="utf-8") as fh:
        if not _acquire_lock(fh, exclusive=True, operation="resolve"):
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


def claim_for_execution(alert_id: str, actor: str = "unknown") -> tuple:
    """Atomically claim a pending alert BEFORE its executor side effect runs.

    Under a blocking exclusive lock, transitions pending -> executing. Exactly
    one caller wins; everyone else (concurrent approve, approve after reject /
    expiry / prior claim) gets (False, reason) and must not execute anything.
    Returns (claimed, reason_or_status, alert_snapshot_or_None).
    """
    if not _QUEUE_FILE.exists():
        return (False, "not_found", None)
    with open(_QUEUE_FILE, "r+", encoding="utf-8") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)  # blocking: claim must serialize, not fail
        try:
            data = _load_queue(fh)
            for a in data.get("alerts", []):
                if a.get("id") != alert_id:
                    continue
                if a.get("status") != "pending":
                    return (False, str(a.get("status")), None)
                try:
                    exp = datetime.fromisoformat(
                        str(a.get("expires_at", "")).replace("Z", "+00:00")
                    ).timestamp()
                    if time.time() > exp:
                        return (False, "expired", None)
                except ValueError:
                    pass
                a["status"] = "executing"
                a["claimed_by"] = actor
                a["claimed_at"] = _now_iso()
                _save_queue(fh, data)
                _write_mirror_snapshot(data["alerts"])
                return (True, "executing", dict(a))
            return (False, "not_found", None)
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def finalize_claim(alert_id: str, ok: bool, actor: str = "unknown", error: str = "") -> bool:
    """Move a claimed (executing) alert to a terminal state: approved or failed.

    Never returns it to pending, so a failed executor is not silently re-run.
    """
    if not _QUEUE_FILE.exists():
        return False
    with open(_QUEUE_FILE, "r+", encoding="utf-8") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            data = _load_queue(fh)
            alerts = data.get("alerts", [])
            done = None
            for a in alerts:
                if a.get("id") == alert_id and a.get("status") == "executing":
                    a["status"] = "approved" if ok else "failed"
                    a["resolved_at"] = _now_iso()
                    a["resolved_by"] = actor
                    if error:
                        a["error"] = error[:500]
                    done = dict(a)
                    break
            if done is None:
                return False
            data["alerts"] = [a for a in alerts if a.get("id") != alert_id]
            _save_queue(fh, data)
            _write_mirror_snapshot(data["alerts"])
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)
    _append_archive(done)
    return True


def extend_ttl(alert_id: str, extra_hours: int) -> bool:
    """Extend the TTL of a pending alert (aq-defer). Returns True on success."""
    if not _QUEUE_FILE.exists():
        return False
    with open(_QUEUE_FILE, "r+", encoding="utf-8") as fh:
        if not _acquire_lock(fh, exclusive=True, operation="extend_ttl"):
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
    return len(get_pending(include_snoozed=False))


if __name__ == "__main__":  # detached notifier helper: attention_queue.py --notify <id>
    if len(sys.argv) == 3 and sys.argv[1] == "--notify":
        sys.exit(_notify_main(sys.argv[2]))
    sys.exit("usage: attention_queue.py --notify <alert-id>")
