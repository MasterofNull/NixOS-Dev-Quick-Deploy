"""Durable per-dispatch work ledger: append-only JSONL event files, reduced on read.

SSOT: .agents/plans/agent-work-durability-20261119/DESIGN.md (S1, Revision 1 F5/F17, Revision 3).
Every writer must go through append_event(): the flock it takes is what makes a non-terminated
tail seen under the lock provably a crashed writer's leftover rather than a write in progress.
"""
from __future__ import annotations

import fcntl
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LIB_DIR = str(Path(__file__).resolve().parent)
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from delegation_dir import resolve_delegation_dir  # noqa: E402

SCHEMA = 1
TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
BOOT_ID_PATH = Path("/proc/sys/kernel/random/boot_id")
WINDOW_ENV = "AQ_LEDGER_HEARTBEAT_WINDOW_S"
DEFAULT_WINDOW_S = 1800
_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")

INIT_STATUSES = ("queued", "running")
STEP_STATUSES = ("running", "done", "failed", "skipped")
STATUSES = ("queued", "running", "checkpointed", "done", "failed", "abandoned",
            "interrupted", "needs-attention")
TERMINAL_STATUSES = ("done", "failed", "abandoned")
RESUMABLE_STATUSES = ("queued", "checkpointed", "interrupted")
RESUME_POLICIES = ("auto", "confirm", "never")

_INIT_REQUIRED = ("id", "lane", "role", "task")
_INIT_OPTIONAL = ("model", "parent", "brief_path", "worktree", "branch", "findings_path")
EVENT_FIELDS: dict[str, tuple[str, ...]] = {
    "init": (*_INIT_REQUIRED, *_INIT_OPTIONAL, "pr", "resume_policy", "status"),
    "step": ("name", "status", "artifact"),
    "heartbeat": ("detail",),
    "status": ("status", "reason"),
}


class LedgerError(Exception):
    """A ledger operation was refused."""


def validate_dispatch_id(dispatch_id: str) -> str:
    if not _ID_RE.fullmatch(dispatch_id) or ".." in dispatch_id:
        raise LedgerError(f"invalid dispatch id: {dispatch_id!r}")
    return dispatch_id


def ledger_dir(delegation_dir: str | os.PathLike[str] | None = None) -> Path:
    # The resolver's git-less fallback expects a scripts/<area> directory, not scripts/<area>/lib.
    base = Path(delegation_dir) if delegation_dir else resolve_delegation_dir(Path(_LIB_DIR).parent)
    return base / "ledger"


def ledger_path(dispatch_id: str, delegation_dir: str | os.PathLike[str] | None = None) -> Path:
    return ledger_dir(delegation_dir) / f"{validate_dispatch_id(dispatch_id)}.jsonl"


def read_boot_id() -> str:
    try:
        boot_id = BOOT_ID_PATH.read_text(encoding="ascii").strip()
    except OSError as exc:
        raise LedgerError(f"cannot read boot id: {exc}") from exc
    if not boot_id:
        raise LedgerError(f"empty boot id in {BOOT_ID_PATH}")
    return boot_id


def read_pid_start_ticks(pid: int) -> int | None:
    """Field 22 of /proc/<pid>/stat. comm may contain spaces or ")", so split after the last ")"."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_bytes()
        # The first token after ")" is field 3.
        return int(stat[stat.rindex(b")") + 1:].split()[19])
    except (OSError, ValueError, IndexError):
        return None


def heartbeat_window_s() -> int:
    raw = os.environ.get(WINDOW_ENV)
    if raw is None:
        return DEFAULT_WINDOW_S
    try:
        value = int(raw)
    except ValueError:
        value = 0
    if value <= 0:
        raise LedgerError(f"{WINDOW_ENV} must be a positive integer, got {raw!r}")
    return value


def _parse_time(text: str) -> datetime:
    return datetime.strptime(text, TIME_FORMAT).replace(tzinfo=timezone.utc)


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def validate_record(record: object) -> str | None:
    """Return why `record` is not a valid schema-1 event, or None when it is valid."""
    if not isinstance(record, dict):
        return "record is not a JSON object"
    if not _is_int(record.get("schema")) or record["schema"] != SCHEMA:
        return f"unsupported schema {record.get('schema')!r}"
    event = record.get("event")
    if not isinstance(event, str) or event not in EVENT_FIELDS:
        return f"unknown event {event!r}"
    missing = [k for k in ("at", "boot_id", "pid", "pid_start_ticks", *EVENT_FIELDS[event]) if k not in record]
    if missing:
        return f"missing field(s): {', '.join(missing)}"
    try:
        _parse_time(record["at"])
    except (TypeError, ValueError):
        return f"invalid timestamp {record['at']!r}"
    if not isinstance(record["boot_id"], str) or not record["boot_id"]:
        return "boot_id must be a non-empty string"
    if not _is_int(record["pid"]) or record["pid"] <= 0:
        return "pid must be a positive integer"
    if record["pid_start_ticks"] is not None and not _is_int(record["pid_start_ticks"]):
        return "pid_start_ticks must be an integer or null"

    def text(*keys: str) -> str | None:
        bad = [k for k in keys if not isinstance(record[k], str) or not record[k]]
        return f"{', '.join(bad)} must be a non-empty string" if bad else None

    def optional_text(*keys: str) -> str | None:
        bad = [k for k in keys if record[k] is not None and not isinstance(record[k], str)]
        return f"{', '.join(bad)} must be a string or null" if bad else None

    def one_of(key: str, allowed: tuple[str, ...]) -> str | None:
        return None if record[key] in allowed else f"invalid {key} {record[key]!r}"

    if event == "init":
        if record["pr"] is not None and not _is_int(record["pr"]):
            return "pr must be an integer or null"
        return (text(*_INIT_REQUIRED) or optional_text(*_INIT_OPTIONAL)
                or one_of("resume_policy", RESUME_POLICIES) or one_of("status", INIT_STATUSES))
    if event == "step":
        return text("name") or one_of("status", STEP_STATUSES) or optional_text("artifact")
    if event == "heartbeat":
        return optional_text("detail")
    return one_of("status", STATUSES) or optional_text("reason")


def _decode_line(line: bytes) -> tuple[bool, Any]:
    try:
        return True, json.loads(line.decode("utf-8"))
    except (ValueError, RecursionError):
        return False, None


def _torn_offset(data: bytes) -> int | None:
    """Offset of a torn final line (unterminated or undecodable), else None."""
    if not data:
        return None
    terminated = data.endswith(b"\n")
    start = data.rfind(b"\n", 0, len(data) - 1 if terminated else len(data)) + 1
    if terminated and _decode_line(data[start:-1])[0]:
        return None
    return start


def _read_all(fd: int) -> bytes:
    chunks: list[bytes] = []
    offset = 0
    while chunk := os.pread(fd, 65536, offset):
        chunks.append(chunk)
        offset += len(chunk)
    return b"".join(chunks)


def _write_all(fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        view = view[os.write(fd, view):]


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _ensure_dir(directory: Path) -> None:
    created = not directory.exists()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if directory.is_symlink():
        raise LedgerError(f"ledger directory must not be a symlink: {directory}")
    os.chmod(directory, 0o700)
    if created:
        _fsync_dir(directory.parent)


def _quarantine_torn_tail(fd: int, path: Path, data: bytes, offset: int) -> None:
    """Move a torn tail to <file>.torn so the next append cannot turn it into mid-file corruption.

    Caller holds LOCK_EX. The fragment is made durable in the sidecar before the ledger is truncated.
    """
    side = os.open(f"{path}.torn", os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(side, 0o600)
        fragment = data[offset:]
        _write_all(side, fragment if fragment.endswith(b"\n") else fragment + b"\n")
        os.fsync(side)
    finally:
        os.close(side)
    _fsync_dir(path.parent)
    os.ftruncate(fd, offset)
    os.fsync(fd)


def append_event(dispatch_id: str, event: str, *, delegation_dir: str | os.PathLike[str] | None = None,
                 boot_id: str | None = None, pid: int | None = None, **fields: Any) -> dict[str, Any]:
    """Append one durable event. `init` creates the entry; every other event requires it."""
    path = ledger_path(dispatch_id, delegation_dir)
    if event not in EVENT_FIELDS:
        raise LedgerError(f"unknown event {event!r}")
    unknown = sorted(set(fields) - set(EVENT_FIELDS[event]))
    if unknown:
        raise LedgerError(f"unknown field(s) for {event}: {', '.join(unknown)}")
    values: dict[str, Any] = dict.fromkeys(EVENT_FIELDS[event])
    if event == "init":
        values.update(id=dispatch_id, resume_policy="confirm", status="running")
    values.update({k: v for k, v in fields.items() if v is not None})
    if event == "init" and values["id"] != dispatch_id:
        raise LedgerError("init id does not match the dispatch id")
    pid = os.getpid() if pid is None else pid
    record: dict[str, Any] = {
        "schema": SCHEMA,
        "event": event,
        "at": datetime.now(timezone.utc).strftime(TIME_FORMAT),
        "boot_id": read_boot_id() if boot_id is None else boot_id,
        "pid": pid,
        "pid_start_ticks": read_pid_start_ticks(pid),
        **values,
    }
    # Before any filesystem effect: a refused init must not leave an empty (needs-attention) entry.
    error = validate_record(record)
    if error:
        raise LedgerError(error)

    flags = os.O_RDWR | os.O_APPEND | os.O_NOFOLLOW
    if event == "init":
        _ensure_dir(path.parent)
        flags |= os.O_CREAT
    try:
        fd = os.open(path, flags, 0o600)
    except FileNotFoundError:
        raise LedgerError(f"no ledger entry for {dispatch_id!r}; run init first") from None
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            # Stamped under the lock so file order and time order agree.
            record["at"] = datetime.now(timezone.utc).strftime(TIME_FORMAT)
            data = _read_all(fd)
            torn = _torn_offset(data)
            # Refusals are decided on the post-quarantine size so a refused append changes nothing.
            empty = (len(data) if torn is None else torn) == 0
            if event == "init" and not empty:
                raise LedgerError(f"ledger entry already exists: {dispatch_id!r}")
            if event != "init" and empty:
                raise LedgerError(f"ledger entry {dispatch_id!r} has no init record")
            os.fchmod(fd, 0o600)
            if torn is not None:
                _quarantine_torn_tail(fd, path, data, torn)
            line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
            _write_all(fd, line.encode("utf-8", errors="replace"))
            os.fsync(fd)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
    if event == "init":
        _fsync_dir(path.parent)
    return record


def _read_locked(path: Path) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        fcntl.flock(fd, fcntl.LOCK_SH)
        try:
            return _read_all(fd)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def reduce_ledger_file(path: str | os.PathLike[str], *, current_boot_id: str | None = None,
                       now: datetime | None = None, window_s: int | None = None) -> dict[str, Any]:
    """Fold one ledger file into its current state. Read-only.

    Raises FileNotFoundError when the file is absent; any other read failure or any corruption
    before the final line yields status "needs-attention".
    """
    path = Path(path)
    dispatch_id = path.name.removesuffix(".jsonl")
    current_boot_id = read_boot_id() if current_boot_id is None else current_boot_id
    window_s = heartbeat_window_s() if window_s is None else window_s
    now = datetime.now(timezone.utc) if now is None else now
    state: dict[str, Any] = {
        "id": dispatch_id, "lane": None, "model": None, "role": None, "parent": None, "task": None,
        "brief_path": None, "worktree": None, "branch": None, "pr": None, "status": "needs-attention",
        "status_reason": None, "interrupted_reason": None, "steps": [], "findings_path": None,
        "last_heartbeat": None, "resume_policy": None, "boot_id": None, "pid": None,
        "pid_start_ticks": None, "torn_tail": False, "stale_heartbeat": False,
        "auto_resume_allowed": False, "warnings": [], "event_count": 0, "path": str(path),
    }
    warnings: list[str] = state["warnings"]
    corrupt = False
    try:
        validate_dispatch_id(dispatch_id)
        data = _read_locked(path)
    except FileNotFoundError:
        raise
    except (OSError, LedgerError) as exc:
        warnings.append(f"unreadable ledger file: {exc}")
        return state

    lines = data.split(b"\n")
    if lines[-1] == b"":
        lines.pop()
    torn = _torn_offset(data)
    if torn is not None:
        state["torn_tail"] = True
        warnings.append(f"line {len(lines)}: incomplete final record ignored (torn tail)")
        lines.pop()
    if os.path.lexists(f"{path}.torn"):
        warnings.append(f"earlier torn record(s) quarantined in {path.name}.torn")

    steps: dict[str, dict[str, Any]] = {}
    initialized = False
    for number, line in enumerate(lines, start=1):
        decoded, record = _decode_line(line)
        error = validate_record(record) if decoded else "invalid JSON"
        if error is None:
            if record["event"] != "init" and not initialized:
                error = f"{record['event']} event before init"
            elif record["event"] == "init" and initialized:
                error = "duplicate init event"
            elif record["event"] == "init" and record["id"] != dispatch_id:
                error = f"init id {record['id']!r} does not match the file name"
        if error:
            corrupt = True
            warnings.append(f"line {number}: {error}")
            continue
        event = record["event"]
        if event == "init":
            initialized = True
            for key in EVENT_FIELDS["init"]:
                state[key] = record[key]
        elif event == "step":
            previous = steps.get(record["name"], {})
            steps[record["name"]] = {
                "name": record["name"], "status": record["status"], "at": record["at"],
                "artifact": record["artifact"] or previous.get("artifact"),
            }
        elif event == "status":
            state["status"] = record["status"]
            state["status_reason"] = record["reason"]
        # Any event is proof of life, so a queued entry that starts running is not instantly stale.
        state["last_heartbeat"] = record["at"]
        for key in ("boot_id", "pid", "pid_start_ticks"):
            state[key] = record[key]
        state["event_count"] += 1
    state["steps"] = list(steps.values())

    if not initialized:
        corrupt = True
        warnings.append("no valid init event")
    if corrupt:
        state["status"] = "needs-attention"
        return state
    if state["status"] == "interrupted":
        state["interrupted_reason"] = state["status_reason"]
    if state["status"] == "running":
        if state["boot_id"] != current_boot_id:
            state["status"] = "interrupted"
            state["interrupted_reason"] = "prior-boot"
        elif (now - _parse_time(state["last_heartbeat"])).total_seconds() > window_s:
            state["stale_heartbeat"] = True
    state["auto_resume_allowed"] = (state["resume_policy"] == "auto"
                                    and state["status"] in RESUMABLE_STATUSES)
    return state


def list_entries(delegation_dir: str | os.PathLike[str] | None = None, *, current_boot_id: str | None = None,
                 now: datetime | None = None, window_s: int | None = None) -> list[dict[str, Any]]:
    """Reduce every entry. A missing ledger directory is empty; an unreadable one raises."""
    # Before the directory check: bad configuration must fail the same way with or without entries.
    window_s = heartbeat_window_s() if window_s is None else window_s
    try:
        # iterdir, not glob: glob hides permission errors, which would make `check` pass blind.
        paths = sorted(p for p in ledger_dir(delegation_dir).iterdir() if p.name.endswith(".jsonl"))
    except FileNotFoundError:
        return []
    current_boot_id = read_boot_id() if current_boot_id is None else current_boot_id
    entries: list[dict[str, Any]] = []
    for path in paths:
        try:
            entries.append(reduce_ledger_file(path, current_boot_id=current_boot_id, now=now,
                                              window_s=window_s))
        except FileNotFoundError:
            continue  # archived between listing and reading
    return entries
