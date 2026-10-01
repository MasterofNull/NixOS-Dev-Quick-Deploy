"""Small, shared RSI lifecycle guard for every agent entrypoint.

The guard is deliberately local and synchronous: a failed hook, blocked write,
or incomplete run must leave durable evidence even when the model loop itself
is unavailable.  It never starts another agent loop, so recording a failure
cannot recurse or amplify token use.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
# Env overrides exist so CLIs and tests can target an isolated ledger; unset = canonical paths.
_RUNTIME = Path(os.environ.get("RSI_RUNTIME_DIR") or _REPO_ROOT / ".agent" / "collaboration")
_BACKLOG = Path(os.environ.get("RSI_BACKLOG_FILE") or _REPO_ROOT / ".agent" / "memory" / "issues-backlog.md")
_WORKAROUNDS = Path(os.environ.get("RSI_WORKAROUNDS_FILE") or _REPO_ROOT / ".agent" / "WORKAROUND-REGISTER.md")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:72] or "unknown"


def _append(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)


def _event(agent: str, event_type: str, payload: dict[str, str], subject: str) -> None:
    try:
        lib = Path(__file__).resolve().parent
        if str(lib) not in sys.path:
            sys.path.insert(0, str(lib))
        import event_log  # type: ignore
        event_log.emit(agent, event_type, payload=payload, subject=subject)
    except Exception as exc:
        # The backlog is the mandatory durable surface; event-bus mirroring is
        # useful telemetry but must not hide the original failure.
        print(f"RSI telemetry unavailable: {type(exc).__name__}", file=sys.stderr)


def check(repo_root: Path = _REPO_ROOT) -> tuple[bool, str]:
    """Verify that operational state has a writable canonical home."""
    runtime = repo_root / ".agent" / "collaboration"
    memory = repo_root / ".agent" / "memory"
    try:
        runtime.mkdir(parents=True, exist_ok=True)
        memory.mkdir(parents=True, exist_ok=True)
        for directory in (runtime, memory):
            with tempfile.TemporaryFile(dir=directory) as probe:
                probe.write(b"ok\n")
                probe.flush()
    except OSError as exc:
        return False, f"canonical .agent runtime is not writable: {exc}"
    return True, "canonical .agent runtime writable"


def start(agent: str, subject: str, objective: str = "") -> None:
    ok, detail = check()
    payload = {"objective": objective[:240], "check": detail}
    _event(agent, "rsi.start", payload, subject)
    if not ok:
        failure(agent, subject, "rsi-lifecycle", ".agent/collaboration", "rsi", detail,
                severity="critical", root_fix="restore writable canonical .agent runtime")


def _clean(value: str) -> str:
    value = re.sub(r"(?i)(bearer\s+)[\w.\-/+=]+", r"\1[REDACTED]", str(value))
    value = re.sub(r'''(?i)((?:password|token|api[_-]?key|secret)["']?\s*(?:[=:]\s*|\s+))(?:"[^"]*"|'[^']*'|[^\s,;]+)''',
                   r"\1[REDACTED]", value)
    return value.replace("\n", " ").replace("\r", " ")[:500]


def _save(path: Path, state: dict) -> None:
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        try:
            json.dump(state, handle, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def failure(agent: str, subject: str, producer: str, path: str, authority: str,
            os_error: str, *, severity: str = "medium", root_fix: str = "",
            workaround: str = "") -> str:
    """Register one failure; workarounds require an explicit root-fix plan."""
    if workaround and not root_fix:
        raise ValueError("--workaround requires --root-fix")
    if severity not in {"low", "medium", "high", "critical"}:
        raise ValueError("severity must be low, medium, high or critical")
    agent, subject, producer, path, authority, os_error, root_fix, workaround = map(
        _clean, (agent, subject, producer, path, authority, os_error, root_fix, workaround))
    stamp = _now()
    # Subject is a run identifier, not part of the failure identity.
    identity = json.dumps([producer, path, authority, os_error], separators=(",", ":"))
    slug = hashlib.sha256(identity.encode()).hexdigest()[:24]
    line = (
        f"\n[OPEN] rsi-{slug} — {producer} failure in {subject}. "
        f"Root cause evidence: producer={producer}; path={path}; authority={authority}; "
        f"os_error={os_error}. Detected={stamp}.\n"
        f"  Severity: {severity}\n"
        f"  Action: {root_fix or 'investigate producer/path/authority before changing behavior'}\n"
        f"  File: {path}\n"
    )
    _RUNTIME.mkdir(parents=True, exist_ok=True)
    ledger = _RUNTIME / "rsi-incidents.json"
    with (_RUNTIME / "rsi-incidents.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = json.loads(ledger.read_text()) if ledger.exists() else {"version": 1, "incidents": {}}
        incidents = state["incidents"]
        previous = incidents.get(slug)
        if previous is None and len(incidents) >= 1000:
            raise ValueError("RSI incident capacity reached (1000); archive resolved evidence explicitly")
        incident = dict(previous or {})
        incident.update(id=slug, producer=producer, path=path, authority=authority,
                        error=os_error, root_fix=root_fix, status="open", agent=agent,
                        subject=subject, severity=severity, last_seen=stamp,
                        first_seen=incident.get("first_seen", stamp),
                        count=incident.get("count", 0) + 1)
        incidents[slug] = incident
        _save(ledger, state)
        if not incident.get("backlog_written") or (previous and previous.get("status") == "resolved"):
            _append(_BACKLOG, line)
            incident["backlog_written"] = True
            _save(ledger, state)
        if workaround and (previous is None or previous.get("workaround") != workaround):
            _append(_WORKAROUNDS, (
            f"\n- {stamp} [{slug}] Workaround used: {workaround}. "
            f"Root fix tracked: {root_fix}. Producer={producer}; path={path}; authority={authority}.\n"
            ))
            incident["workaround"] = workaround
            _save(ledger, state)
    _event(agent, "rsi.failure", {
        "producer": producer, "path": path, "authority": authority,
        "os_error": os_error[:500], "severity": severity,
        "root_fix": root_fix[:500], "workaround": workaround[:500],
    }, subject)
    return slug


def resolve(incident_id: str, root_cause: str, regression: str, validation: str) -> None:
    if not all(value.strip() for value in (root_cause, regression, validation)):
        raise ValueError("resolution requires root cause, regression and validation evidence")
    ledger = _RUNTIME / "rsi-incidents.json"
    with (_RUNTIME / "rsi-incidents.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = json.loads(ledger.read_text())
        incident = state["incidents"][incident_id]
        incident.update(status="resolved", resolved_at=_now(),
                        resolution=dict(zip(("root_cause", "regression", "validation"),
                                            map(_clean, (root_cause, regression, validation)))))
        _save(ledger, state)


def annotate(incident_id: str, note: str) -> None:
    """Attach a bounded operator/steward note without changing incident status."""
    if not note.strip():
        raise ValueError("note must not be empty")
    ledger = _RUNTIME / "rsi-incidents.json"
    with (_RUNTIME / "rsi-incidents.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = json.loads(ledger.read_text())
        state["incidents"][incident_id]["note"] = _clean(note)
        _save(ledger, state)


def complete(agent: str, subject: str, evidence: str = "") -> None:
    _event(agent, "rsi.complete", {"evidence": evidence[:500]}, subject)


def main() -> int:
    parser = argparse.ArgumentParser(description="Record durable RSI lifecycle evidence")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("check")
    p = sub.add_parser("start")
    p.add_argument("--agent", required=True); p.add_argument("--subject", required=True)
    p.add_argument("--objective", default="")
    p = sub.add_parser("failure")
    for name in ("agent", "subject", "producer", "path", "authority", "os-error"):
        p.add_argument("--" + name, required=True)
    p.add_argument("--severity", default="medium"); p.add_argument("--root-fix", default="")
    p.add_argument("--workaround", default="")
    p = sub.add_parser("complete")
    p.add_argument("--agent", required=True); p.add_argument("--subject", required=True)
    p.add_argument("--evidence", default="")
    p = sub.add_parser("resolve")
    for name in ("id", "root-cause", "regression", "validation"):
        p.add_argument("--" + name, required=True)
    args = parser.parse_args()
    if args.command == "check":
        ok, detail = check(); print(detail); return 0 if ok else 1
    if args.command == "start": start(args.agent, args.subject, args.objective); return 0
    if args.command == "complete": complete(args.agent, args.subject, args.evidence); return 0
    try:
        if args.command == "resolve":
            resolve(args.id, args.root_cause, args.regression, args.validation)
            return 0
        failure(args.agent, args.subject, args.producer, args.path, args.authority,
                args.os_error, severity=args.severity, root_fix=args.root_fix,
                workaround=args.workaround)
    except (ValueError, OSError, KeyError) as exc:
        print(str(exc), file=sys.stderr); return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
