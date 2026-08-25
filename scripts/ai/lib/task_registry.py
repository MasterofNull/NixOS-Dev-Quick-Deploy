"""
task_registry — Unified task persistence for local delegation.

Phase 74B — replaces 5 separate inline Python heredocs in delegate-to-local
plus the pending-update subprocess calls for local dispatch.

Handles three output formats from one code path:
  1. .agents/delegation/registry.jsonl  — machine-readable task history
  2. .agent/collaboration/PENDING.json  — cross-session in-flight tracker
  3. .agent/collaboration/HANDOFF.md    — human-readable session resume

File locking (fcntl.LOCK_EX) ensures concurrent background tasks don't
corrupt the registry — a real concern when fanout dispatches 2–4 tasks in
parallel.
"""

import errno
import fcntl
import json
import os
import re as _re
import select
import stat as _stat
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


_MAX_COMPLETED = 750    # max completed/failed entries in PENDING.json
_MAX_HANDOFF_LINES = 300  # max delegation tracking lines in HANDOFF.md

# ── M2A: bounds and vocabulary (dormant — activation requires M2B authorization) ──
_M2A_MAX_REGISTRY_BYTES = 50 * 1024 * 1024
_M2A_MAX_RECORD_BYTES = 4096
_M2A_MAX_LEGACY_LOOKUP_BYTES = 65536
_M2A_MAX_TASK_ID_LEN = 128
_M2A_LOCK_TIMEOUT_S = 10.0
_M2A_RECORD_SCHEMA_VERSION = 1
_M2A_RELEASE_BYTE = b"\x01"

_R01_COMPAT_FACTS_VERSION = "aq.registry-compatibility-facts.v1"
_R01_LOOKUP_RESULT_VERSION = "aq.registry-lookup-result.v1"
_R01_REASON_CODES = frozenset({
    "legacy_oversized_rows_present",
    "registry_duplicate_target",
    "registry_file_too_large",
    "registry_identity_ambiguous",
    "registry_identity_invalid",
    "registry_identity_missing",
    "registry_legacy_m2a_versioned",
    "registry_legacy_row_over_compatibility_bound",
    "registry_read_open_failed",
    "registry_record_bad_framing",
    "registry_record_duplicate_key",
    "registry_record_invalid_utf8",
    "registry_record_malformed",
    "registry_record_not_object",
    "registry_source_changed_during_read",
    "registry_source_not_regular",
    "registry_source_symlink",
    "registry_source_unavailable",
})
_R01_INTEGRITY_CODES = frozenset({
    "registry_duplicate_target",
    "registry_file_too_large",
    "registry_identity_ambiguous",
    "registry_identity_invalid",
    "registry_identity_missing",
    "registry_legacy_m2a_versioned",
    "registry_legacy_row_over_compatibility_bound",
    "registry_record_bad_framing",
    "registry_record_duplicate_key",
    "registry_record_invalid_utf8",
    "registry_record_malformed",
    "registry_record_not_object",
    "registry_source_changed_during_read",
    "registry_source_not_regular",
    "registry_source_symlink",
})
_R01_UNAVAILABLE_CODES = frozenset({
    "registry_read_open_failed",
    "registry_source_unavailable",
})

_M2A_LANES = frozenset({"local", "claude", "codex", "antigravity"})
_M2A_ROLES = frozenset({"implementer", "reviewer", "researcher", "orchestrator", "validator"})
_M2A_ACCESS = frozenset({"writer", "read_only"})
_M2A_TASK_CLASSES = frozenset({
    "code_generation", "code_review", "research", "planning",
    "validation", "analysis", "documentation", "testing", "refactoring", "debugging",
})
_M2A_ARTIFACT_EXPECTATIONS = frozenset({"file_output", "json_output", "markdown_output", "none"})

_M2A_LEGAL_TRANSITIONS: dict[str, frozenset[str]] = {
    "queued":     frozenset({"running", "failed", "cancelled"}),
    "running":    frozenset({"waiting", "cancelling", "done", "failed", "cancelled", "stale"}),
    "waiting":    frozenset({"running", "cancelling", "done", "failed", "cancelled", "stale"}),
    "cancelling": frozenset({"cancelled", "failed", "stale"}),
    "done":       frozenset({"done"}),
    "failed":     frozenset({"failed"}),
    "cancelled":  frozenset({"cancelled"}),
    "stale":      frozenset({"stale"}),
    "orphaned":   frozenset({"orphaned"}),
    "error":      frozenset({"error"}),
}
_M2A_TERMINAL_STATES = frozenset({"done", "failed", "cancelled", "stale", "orphaned", "error"})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class RegistryError(ValueError):
    """Raised by M2A transactional registry operations on contract violations."""


class ExecBarrier:
    """Dormant anonymous-pipe pre-exec barrier primitive — M2A contract foundation.

    DORMANT: No live wrapper imports or invokes this class.
    Activation requires separately authorized M2B wrapper adoption.

    Protocol:
    1. barrier = ExecBarrier()
    2. child_pid = barrier.fork_child(provider_argv)
       Child blocks on pipe read end; parent holds write end.
    3. Parent attaches PID + start_time via TaskRegistry.attach_process().
    4. barrier.release(child_pid, pid_start_time) — writes one bounded release byte.
       Child receives byte, closes both descriptors, execs provider.
    5. barrier.close_without_release() — closes write end (EOF path).
       Child exits(1) without exec.

    Failure modes that never exec the provider:
    - EOF on read end (close_without_release or parent crash)
    - Timeout (barrier_timeout_s seconds) before release byte arrives
    - Malformed release (wrong byte value)
    - Attachment failure (release not called before barrier closed)
    """

    def __init__(self, timeout_s: float = 30.0) -> None:
        self._barrier_timeout_s = timeout_s
        self._read_fd, self._write_fd = os.pipe()
        self._child_pid: Optional[int] = None
        self._released = False

    def fork_child(self, provider_argv: list[str]) -> int:
        """Fork supervisor child. Child blocks until released or failure. Returns child PID."""
        if self._child_pid is not None:
            raise RegistryError("barrier_already_forked")
        if not provider_argv:
            raise RegistryError("barrier_empty_provider_argv")

        child_pid = os.fork()
        if child_pid == 0:
            # Child: close write end, block waiting for exactly one release byte.
            try:
                os.close(self._write_fd)
                ready, _, _ = select.select([self._read_fd], [], [], self._barrier_timeout_s)
                if not ready:
                    os.close(self._read_fd)
                    os._exit(1)
                data = os.read(self._read_fd, 1)
                os.close(self._read_fd)
                if data != _M2A_RELEASE_BYTE:
                    # EOF (b"") or wrong byte: never exec.
                    os._exit(1)
                os.execvp(provider_argv[0], provider_argv)
            except Exception:
                pass
            os._exit(1)

        # Parent: close read end, retain write end.
        os.close(self._read_fd)
        self._child_pid = child_pid
        return child_pid

    def release(self, pid: int, pid_start_time: int) -> None:
        """Write one release byte after verified PID+start_time attachment. At most once."""
        if self._released:
            raise RegistryError("barrier_already_released")
        if self._child_pid is None:
            raise RegistryError("barrier_not_forked")
        if pid != self._child_pid:
            raise RegistryError("barrier_pid_mismatch")
        if not isinstance(pid_start_time, int) or pid_start_time < 0:
            raise RegistryError("barrier_invalid_start_time")
        os.write(self._write_fd, _M2A_RELEASE_BYTE)
        os.close(self._write_fd)
        self._released = True

    def close_without_release(self) -> None:
        """Close write end without releasing — child exits without exec (EOF path)."""
        if self._released:
            return
        try:
            os.close(self._write_fd)
        except OSError:
            pass
        self._released = True


class TaskRegistry:
    """Unified registry for local task dispatch lifecycle."""

    def __init__(self, delegation_dir: Path, repo_root: Optional[Path] = None):
        self.delegation_dir = Path(delegation_dir)
        self.repo_root = Path(repo_root) if repo_root else self.delegation_dir.parent.parent
        self.registry_file = self.delegation_dir / "registry.jsonl"
        self.pending_file = self.repo_root / ".agent" / "collaboration" / "PENDING.json"
        self.handoff_file = self.repo_root / ".agent" / "collaboration" / "HANDOFF.md"

    # ── file-locked write helpers ────────────────────────────────────────────

    def _locked_rewrite(self, path: Path, lines: list[str]) -> None:
        """Atomically rewrite a file under exclusive lock."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                fh.write("\n".join(lines) + "\n")
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)

    def _locked_append(self, path: Path, line: str) -> None:
        """Append a line under exclusive lock."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                fh.write(line + "\n")
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)

    # ── registry.jsonl ───────────────────────────────────────────────────────

    def _read_registry(self) -> list[dict]:
        if not self.registry_file.exists():
            return []
        entries = []
        with open(self.registry_file) as fh:
            fcntl.flock(fh, fcntl.LOCK_SH)
            try:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)
        return entries

    def _update_registry(self, task_id: str, updates: dict) -> None:
        """Apply updates dict to the entry matching task_id."""
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        # Read under shared lock, then rewrite under exclusive lock
        entries = self._read_registry()
        lines = []
        for e in entries:
            if e.get("id") == task_id:
                e.update(updates)
            lines.append(json.dumps(e))
        self._locked_rewrite(self.registry_file, lines)

    def append(
        self,
        task_id: str,
        description: str,
        output_file: str,
        mode: str,
        role: str,
        pid: Optional[int] = None,
    ) -> None:
        """Append a new running task entry to registry.jsonl."""
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "id": task_id,
            "agent": f"local-{mode}",
            "role": role,
            "description": description[:500],
            "output_file": output_file,
            "pid": pid,
            "status": "running",
            "tokens_in": None,
            "tokens_out": None,
            "created": _now(),
        }
        self._locked_append(self.registry_file, json.dumps(entry))

    def update_status(self, task_id: str, status: str) -> None:
        self._update_registry(task_id, {"status": status})

    def update_pid(self, task_id: str, pid: int) -> None:
        self._update_registry(task_id, {"pid": pid})

    def update_tokens(self, task_id: str, tokens_in: Optional[int], tokens_out: Optional[int]) -> None:
        updates: dict = {}
        if tokens_in is not None:
            updates["tokens_in"] = tokens_in
        if tokens_out is not None:
            updates["tokens_out"] = tokens_out
        if updates:
            self._update_registry(task_id, updates)

    def get(self, task_id: str) -> Optional[dict]:
        for e in self._read_registry():
            if e.get("id") == task_id:
                return e
        return None

    def get_output_file(self, task_id: str) -> Optional[str]:
        e = self.get(task_id)
        return e.get("output_file") if e else None

    def get_pid(self, task_id: str) -> Optional[int]:
        e = self.get(task_id)
        pid = e.get("pid") if e else None
        if pid and pid != "None":
            try:
                return int(pid)
            except (ValueError, TypeError):
                pass
        return None

    def list_all(self) -> list[dict]:
        return self._read_registry()

    def list_running(self) -> list[dict]:
        return [e for e in self._read_registry() if e.get("status") == "running"]

    def _pid_alive(self, pid: object) -> bool:
        if pid in (None, "", "null", "None"):
            return False
        try:
            value = int(pid)
        except (TypeError, ValueError):
            return False
        try:
            os.kill(value, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            # POSIX: EPERM means process exists but we lack permission to signal it.
            return True
        return True

    def _heartbeat_alive(self, entry: dict, ttl_s: float = 180.0) -> bool:
        """True if the task's heartbeat file was updated within ttl_s seconds.

        Used as a fallback when os.kill() reports the PID missing due to
        sandbox PID-namespace isolation (the process runs on the host but is
        invisible inside the sandboxed monitor).  The watcher writes the
        heartbeat file every 60s so a 180s TTL gives 3× margin.
        """
        output_path = self._resolve_output_path(entry)
        if not output_path:
            return False
        heartbeat_path = Path(str(output_path) + ".heartbeat.json")
        if not heartbeat_path.exists():
            return False
        try:
            hb = json.loads(heartbeat_path.read_text())
            hb_at = hb.get("heartbeat_at") or hb.get("last_heartbeat") or hb.get("ts")
            if not hb_at:
                return False
            from datetime import datetime, timezone
            ts = datetime.fromisoformat(hb_at.replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - ts).total_seconds()
            return age < ttl_s
        except Exception:
            return False

    def _resolve_output_path(self, entry: dict) -> Optional[Path]:
        output_file = entry.get("output_file")
        if not output_file:
            return None
        path = Path(output_file)
        return path if path.is_absolute() else self.repo_root / path

    def _infer_terminal_status(self, entry: dict) -> tuple[str, str]:
        output_path = self._resolve_output_path(entry)
        if output_path:
            progress_path = Path(str(output_path) + ".progress.json")
            if progress_path.exists():
                try:
                    progress = json.loads(progress_path.read_text())
                    status = progress.get("status")
                    if status in {"done", "failed", "cancelled"}:
                        return status, f"progress sidecar reported {status}"
                except Exception:
                    pass
            if output_path.exists():
                try:
                    text = output_path.read_text(errors="replace")
                except Exception:
                    text = ""
                lower = text.lower()
                failure_markers = (
                    "repeated-read stagnation",
                    "exploration stagnation",
                    "analysis checkpoint stagnation",
                    "agent runner error:",
                    "traceback",
                    "timed out",
                    '"status": "failed"',
                    '"success": false',
                )
                if any(marker in lower for marker in failure_markers):
                    return "failed", "output artifact reported failure"
                if '"success": true' in lower or '"status": "done"' in lower:
                    return "done", "output artifact reported success"
                if text.strip() and not text.startswith("Agent task started; waiting for aq-agent-loop output."):
                    return "failed", "process exited before registry completion; output requires review"
        return "stale", "registry said running, but pid is missing or no longer alive"

    def _with_inferred_status(self, entry: dict) -> dict:
        observed = dict(entry)
        current_status = observed.get("status")
        if current_status not in {"running", "done", "completed"}:
            return observed
        if current_status == "running" and self._pid_alive(observed.get("pid")):
            observed["pid_alive"] = True
            return observed
        # Fallback: heartbeat file liveness (survives sandbox PID-namespace isolation).
        # Host PID is invisible inside Claude Code sandbox, so os.kill() returns False
        # even for a running task. Heartbeat file written every 60s proves liveness.
        if current_status == "running" and self._heartbeat_alive(observed):
            observed["pid_alive"] = True
            observed["heartbeat_liveness"] = True
            return observed
        status, reason = self._infer_terminal_status(observed)
        if current_status in {"done", "completed"} and status != "failed":
            return observed
        observed["registry_status"] = current_status
        observed["status"] = status
        observed["inferred_status"] = status
        observed["inferred_reason"] = reason
        observed["inferred_only"] = True
        if current_status == "running":
            observed["pid_alive"] = False
        return observed

    def _artifact_snapshot(self, entry: dict) -> dict:
        output_path = self._resolve_output_path(entry)
        paths = {
            "output": output_path,
            "progress": Path(str(output_path) + ".progress.json") if output_path else None,
            "heartbeat": Path(str(output_path) + ".heartbeat.json") if output_path else None,
            "steps": Path(str(output_path) + ".steps.jsonl") if output_path else None,
        }
        snapshot: dict[str, dict] = {}
        now = time.time()
        for name, path in paths.items():
            if not path:
                snapshot[name] = {"exists": False}
                continue
            try:
                stat = path.stat()
                snapshot[name] = {
                    "exists": True,
                    "path": str(path),
                    "size_bytes": stat.st_size,
                    "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat().replace("+00:00", "Z"),
                    "age_seconds": round(now - stat.st_mtime, 1),
                }
            except FileNotFoundError:
                snapshot[name] = {"exists": False, "path": str(path)}
        return snapshot

    def reconcile_running(self, task_id: Optional[str] = None) -> int:
        """Mark running entries with dead PIDs as terminal before status/check/list reads."""
        changed = 0
        for entry in self._read_registry():
            if task_id and entry.get("id") != task_id:
                continue
            observed = self._with_inferred_status(entry)
            if not observed.get("inferred_only"):
                continue
            updates = {
                "status": observed["status"],
                "stale_since": _now(),
                "stale_reason": observed.get("inferred_reason"),
            }
            self._update_registry(entry.get("id"), updates)
            self.record_completion(entry.get("id"), observed["status"])
            changed += 1
        return changed

    # ── PENDING.json + HANDOFF.md ────────────────────────────────────────────

    def _load_pending(self) -> dict:
        if self.pending_file.exists():
            try:
                return json.loads(self.pending_file.read_text())
            except Exception:
                pass
        return {"in_flight": [], "updated_at": ""}

    def _decay_pending(self, data: dict) -> dict:
        running = [t for t in data.get("in_flight", []) if t.get("status") == "running"]
        finished = [t for t in data.get("in_flight", []) if t.get("status") != "running"]
        data["in_flight"] = running + finished[-_MAX_COMPLETED:]
        return data

    def _save_pending(self, data: dict) -> None:
        data = self._decay_pending(data)
        data["updated_at"] = _now()
        self.pending_file.parent.mkdir(parents=True, exist_ok=True)
        self._locked_rewrite(
            self.pending_file,
            [json.dumps(data, indent=2)],
        )

    def _handoff_append(self, line: str) -> None:
        self._locked_append(self.handoff_file, line)
        # Decay: keep last _MAX_HANDOFF_LINES tracking lines
        if not self.handoff_file.exists():
            return
        lines = self.handoff_file.read_text().splitlines()
        markers = ("[dispatch]", "[done]", "[failed]", "[partial-success]", "[cancelled]")
        static = [l for l in lines if not any(m in l for m in markers)]
        tracking = [l for l in lines if any(m in l for m in markers)]
        if len(tracking) > _MAX_HANDOFF_LINES:
            self._locked_rewrite(
                self.handoff_file,
                static + tracking[-_MAX_HANDOFF_LINES:],
            )

    def record_dispatch(
        self,
        task_id: str,
        agent: str,
        output_file: str,
        objective: str,
    ) -> None:
        """Write dispatch entry to PENDING.json + HANDOFF.md."""
        ts = _now()
        data = self._load_pending()
        data["in_flight"] = [t for t in data.get("in_flight", []) if t.get("id") != task_id]
        data["in_flight"].append({
            "id": task_id,
            "agent": agent,
            "output_file": output_file,
            "objective": objective[:120],
            "dispatched_at": ts,
            "status": "running",
        })
        self._save_pending(data)
        self._handoff_append(
            f'[{ts}] [dispatch] id={task_id} agent={agent} '
            f'output={output_file} obj="{objective[:100]}"'
        )

    def record_completion(self, task_id: str, status: str) -> None:
        """Update PENDING.json + HANDOFF.md with completion status."""
        ts = _now()
        data = self._load_pending()
        for task in data.get("in_flight", []):
            if task.get("id") == task_id:
                task["status"] = status
                task["completed_at"] = ts
                break
        self._save_pending(data)
        self._handoff_append(f"[{ts}] [{status}] id={task_id}")

    # ── Intent Lock v2 (Phase 85) ────────────────────────────────────────────

    def acquire_lock(self, task_id: str, agent_id: str, ttl_s: int = 3600) -> bool:
        """Try to claim a task lock.  Returns True if acquired, False if already held.

        A lock is acquirable when:
          - The entry has no 'claimed_by', OR
          - now > heartbeat_at + ttl_s * 1.5  (stale/dead agent)
        """
        import socket
        if not agent_id:
            agent_id = f"{socket.gethostname()}-{os.getpid()}"

        ts = _now()
        data = self._load_pending()
        acquired = False
        for task in data.get("in_flight", []):
            if task.get("id") != task_id:
                continue
            claimed_by = task.get("claimed_by")
            heartbeat_at = task.get("heartbeat_at") or task.get("claimed_at")
            if not claimed_by:
                acquired = True
            elif heartbeat_at:
                # Parse ISO timestamp to check staleness
                try:
                    from datetime import datetime, timezone
                    hb = datetime.fromisoformat(heartbeat_at.replace("Z", "+00:00"))
                    age = (datetime.now(timezone.utc) - hb).total_seconds()
                    if age > ttl_s * 1.5:
                        acquired = True  # stale lock — take it
                except Exception:
                    acquired = True  # parse failure → assume stale
            if acquired:
                task["claimed_by"] = agent_id
                task["claimed_at"] = ts
                task["ttl_s"] = ttl_s
                task["heartbeat_at"] = ts
            break
        if acquired:
            self._save_pending(data)
        return acquired

    def release_expired_locks(self) -> list:
        """Release PENDING.json entries whose heartbeat has expired.

        Returns list of task IDs that were released.
        """
        data = self._load_pending()
        released = []
        changed = False
        for task in data.get("in_flight", []):
            if task.get("status") != "running":
                continue
            heartbeat_at = task.get("heartbeat_at")
            ttl_s = task.get("ttl_s", 3600)
            if not heartbeat_at or not task.get("claimed_by"):
                continue
            try:
                from datetime import datetime, timezone
                hb = datetime.fromisoformat(heartbeat_at.replace("Z", "+00:00"))
                age = (datetime.now(timezone.utc) - hb).total_seconds()
                if age > ttl_s * 1.5:
                    task.pop("claimed_by", None)
                    task.pop("claimed_at", None)
                    task.pop("heartbeat_at", None)
                    task.pop("ttl_s", None)
                    released.append(task["id"])
                    changed = True
            except Exception:
                pass
        if changed:
            self._save_pending(data)
        return released

    def heartbeat(self, task_id: str, agent_id: str) -> bool:
        """Update heartbeat_at for a claimed task.  Returns True if updated."""
        data = self._load_pending()
        updated = False
        for task in data.get("in_flight", []):
            if task.get("id") == task_id and task.get("claimed_by") == agent_id:
                task["heartbeat_at"] = _now()
                updated = True
                break
        if updated:
            self._save_pending(data)
        return updated

    # ── subcommand helpers (used by dispatch.py CLI) ─────────────────────────

    def cmd_list(self) -> None:
        entries = [self._with_inferred_status(e) for e in self.list_all()]
        if not entries:
            print("No delegated tasks yet.")
            return
        fmt = "{:<32}  {:<8}  {:<12}  {:<10}  {:>6}  {:>7}  {}"
        print(fmt.format("TASK ID", "STATUS", "AGENT", "ROLE", "TOK_IN", "TOK_OUT", "DESCRIPTION"))
        print(fmt.format("-" * 32, "-" * 8, "-" * 12, "-" * 10, "-" * 6, "-" * 7, "-" * 11))
        for e in entries:
            desc = e.get("description", "")[:40]
            ti = str(e.get("tokens_in") or "-")
            to = str(e.get("tokens_out") or "-")
            print(fmt.format(
                e.get("id", "?"),
                e.get("status", "?"),
                e.get("agent", "?"),
                e.get("role", "?"),
                ti, to, desc,
            ))

    def cmd_status(self, task_id: str) -> int:
        e = self.get(task_id)
        if not e:
            print(f"Task not found: {task_id}", file=sys.stderr)
            return 1
        e = self._with_inferred_status(e)
        print(json.dumps(e, indent=2))
        return 0

    def cmd_check(self, task_id: str, repo_root: Optional[Path] = None) -> int:
        output_file = self.get_output_file(task_id)
        if not output_file:
            print(f"Task not found in registry: {task_id}", file=sys.stderr)
            return 1
        p = Path(output_file)
        if not p.is_absolute():
            root = Path(repo_root) if repo_root else self.repo_root
            p = root / output_file
        if not p.exists():
            print(f"Output file not found: {p} (task may still be running)", file=sys.stderr)
            return 1
        print(p.read_text(), end="")
        return 0

    def monitor_payload(self, limit: int = 20) -> dict:
        observed = [self._with_inferred_status(e) for e in self.list_all()]
        active = [
            e for e in observed
            if e.get("status") == "running" or e.get("registry_status") == "running"
        ]
        recent = active[-limit:] if active else observed[-limit:]
        tasks = []
        for entry in recent:
            tasks.append({
                "id": entry.get("id"),
                "agent": entry.get("agent"),
                "role": entry.get("role"),
                "status": entry.get("status"),
                "registry_status": entry.get("registry_status"),
                "pid": entry.get("pid"),
                "pid_alive": entry.get("pid_alive"),
                "inferred_only": entry.get("inferred_only", False),
                "inferred_reason": entry.get("inferred_reason"),
                "created": entry.get("created"),
                "description": entry.get("description", "")[:120],
                "artifacts": self._artifact_snapshot(entry),
            })
        return {
            "ok": True,
            "mode": "read_only",
            "counts": {
                "total": len(observed),
                "running": sum(1 for e in observed if e.get("status") == "running"),
                "inferred_stale": sum(1 for e in observed if e.get("status") == "stale" and e.get("inferred_only")),
                "failed": sum(1 for e in observed if e.get("status") == "failed"),
            },
            "tasks": tasks,
        }

    def cmd_monitor(self, limit: int = 20) -> int:
        print(json.dumps(self.monitor_payload(limit=limit), indent=2))
        return 0

    def repair_stale(self, apply: bool = False) -> dict:
        candidates = []
        for entry in self._read_registry():
            observed = self._with_inferred_status(entry)
            if not observed.get("inferred_only"):
                continue
            if observed.get("registry_status") != "running":
                continue
            if observed.get("pid_alive") is not False:
                continue
            reason = str(observed.get("inferred_reason") or "")
            if reason not in {
                "registry said running, but pid is missing or no longer alive",
                "output artifact reported failure",
                "process exited before registry completion; output requires review",
            }:
                continue
            candidates.append({
                "id": observed.get("id"),
                "from_status": observed.get("registry_status"),
                "to_status": observed.get("status"),
                "reason": reason,
                "pid": observed.get("pid"),
            })
        repaired = 0
        if apply:
            for candidate in candidates:
                task_id = candidate.get("id")
                if not task_id:
                    continue
                self._update_registry(task_id, {
                    "status": candidate["to_status"],
                    "stale_since": _now(),
                    "stale_reason": candidate["reason"],
                })
                self.record_completion(task_id, str(candidate["to_status"]))
                repaired += 1
        return {
            "ok": True,
            "mode": "apply" if apply else "dry_run",
            "candidate_count": len(candidates),
            "repaired_count": repaired,
            "candidates": candidates,
        }

    def cmd_repair_status(self, task_id: str) -> int:
        changed = self.reconcile_running(task_id)
        print(json.dumps({"task_id": task_id, "repaired": changed}, indent=2))
        return 0

    def cmd_repair_stale(self, apply: bool = False) -> int:
        print(json.dumps(self.repair_stale(apply=apply), indent=2))
        return 0

    def cmd_cancel(self, task_id: str) -> int:
        pid = self.get_pid(task_id)
        if pid:
            try:
                os.kill(-(pid), 0)  # check group exists
            except ProcessLookupError:
                pass
            try:
                import signal
                os.kill(pid, signal.SIGTERM)
                try:
                    os.killpg(os.getpgid(pid), signal.SIGTERM)
                except Exception:
                    pass
            except Exception:
                pass
            print(f"[task_registry] Sent SIGTERM to pid {pid} for task {task_id}")
        else:
            print(f"[task_registry] No PID found for {task_id}")
        self.update_status(task_id, "cancelled")
        self.record_completion(task_id, "cancelled")
        return 0

    def cmd_kill_all(self) -> int:
        killed = 0
        for e in self.list_running():
            self.cmd_cancel(e["id"])
            killed += 1
        print(f"[task_registry] Killed {killed} running tasks")
        return 0

    # ── M2A: transactional mutation surface (dormant — activation requires M2B) ──

    def _m2a_lock_path(self) -> Path:
        return self.registry_file.parent / (self.registry_file.name + ".lock")

    @staticmethod
    def _assert_regular_not_symlink(path: Path) -> None:
        """Reject symlinks and non-regular files. Passes if path does not yet exist."""
        try:
            st = os.lstat(path)
        except FileNotFoundError:
            return
        if _stat.S_ISLNK(st.st_mode):
            raise RegistryError(f"registry_source_symlink: {path.name}")
        if not _stat.S_ISREG(st.st_mode):
            raise RegistryError(f"registry_source_not_regular: {path.name}")

    def _m2a_acquire_lock(self) -> int:
        """Open stable sibling lock inode and acquire LOCK_EX with bounded wait. Returns fd."""
        lock_path = self._m2a_lock_path()
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._assert_regular_not_symlink(lock_path)
        fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR | os.O_CLOEXEC, 0o600)
        deadline = time.monotonic() + _M2A_LOCK_TIMEOUT_S
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return fd
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    os.close(fd)
                    raise RegistryError("registry_lock_timeout")
                time.sleep(0.05)

    def _m2a_read_records(self) -> list[dict]:
        """Read one bounded registry inode without creating or mutating filesystem state.

        Mutation callers hold the stable writer lock before entering this method.  Read-only
        callers intentionally do not: atomic replacement gives them a complete old-or-new inode,
        while a later mutation still has to prove freshness with CAS.
        """
        # O_NONBLOCK prevents a substituted FIFO/device from blocking before
        # descriptor type validation; regular-file reads retain normal semantics.
        flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NONBLOCK", 0)
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            fd = os.open(str(self.registry_file), flags)
        except FileNotFoundError:
            return []
        except OSError as exc:
            # Preserve the existing typed symlink rejection on platforms where O_NOFOLLOW
            # reports ELOOP, including for a link swapped in immediately before open.
            if exc.errno == errno.ELOOP:
                raise RegistryError(
                    f"registry_source_symlink: {self.registry_file.name}"
                ) from exc
            raise RegistryError(f"registry_read_open_failed: {exc.errno}") from exc

        try:
            st = os.fstat(fd)
            if not _stat.S_ISREG(st.st_mode):
                raise RegistryError(
                    f"registry_source_not_regular: {self.registry_file.name}"
                )
            if st.st_size > _M2A_MAX_REGISTRY_BYTES:
                raise RegistryError("registry_file_too_large")

            chunks: list[bytes] = []
            remaining = _M2A_MAX_REGISTRY_BYTES + 1
            while remaining:
                chunk = os.read(fd, min(64 * 1024, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            content = b"".join(chunks)
            if len(content) > _M2A_MAX_REGISTRY_BYTES:
                raise RegistryError("registry_file_too_large")
        finally:
            os.close(fd)

        records: list[dict] = []
        for raw_line in content.split(b"\n"):
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            if len(raw_line) > _M2A_MAX_RECORD_BYTES:
                raise RegistryError("registry_record_too_large")
            try:
                rec = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise RegistryError(f"registry_record_malformed: {exc}") from exc
            if not isinstance(rec, dict):
                raise RegistryError("registry_record_not_object")
            records.append(rec)
        return records

    def _m2a_write_records(self, records: list[dict]) -> None:
        """Atomic write under caller-held lock: temp → fsync → rename → fsync parent."""
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        content = (
            "\n".join(json.dumps(r, separators=(",", ":"), ensure_ascii=False) for r in records)
            + "\n"
        ).encode("utf-8")
        tmp_path = self.registry_file.parent / (self.registry_file.name + ".tmp")
        tmp_fd = os.open(
            str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_CLOEXEC, 0o600
        )
        try:
            os.write(tmp_fd, content)
            os.fsync(tmp_fd)
        finally:
            os.close(tmp_fd)
        os.replace(str(tmp_path), str(self.registry_file))
        dir_fd = os.open(str(self.registry_file.parent), os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)

    def _m2a_transact(self, mutator) -> dict:
        """Full transactional cycle: acquire lock → read → mutate → write → release lock."""
        lock_fd = self._m2a_acquire_lock()
        try:
            records = self._m2a_read_records()
            result, new_records = mutator(records)
            if new_records is not records:
                self._m2a_write_records(new_records)
            return result
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)

    @staticmethod
    def _m2a_validate_fields(task_id: str, lane: str, role: str, access: str,
                              task_class: str, artifact_expectation: str) -> None:
        if (not isinstance(task_id, str) or not task_id
                or len(task_id) > _M2A_MAX_TASK_ID_LEN
                or not _re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$", task_id)):
            raise RegistryError("registry_task_id_invalid")
        if lane not in _M2A_LANES:
            raise RegistryError(f"registry_lane_invalid: {lane!r}")
        if role not in _M2A_ROLES:
            raise RegistryError(f"registry_role_invalid: {role!r}")
        if access not in _M2A_ACCESS:
            raise RegistryError(f"registry_access_invalid: {access!r}")
        if task_class not in _M2A_TASK_CLASSES:
            raise RegistryError(f"registry_task_class_invalid: {task_class!r}")
        if artifact_expectation not in _M2A_ARTIFACT_EXPECTATIONS:
            raise RegistryError(f"registry_artifact_expectation_invalid: {artifact_expectation!r}")

    def begin(self, task_id: str, lane: str, role: str, access: str,
              task_class: str, artifact_expectation: str) -> dict:
        """Transactional begin: write a new queued M2A task record. Returns the new record.

        DORMANT: No live wrapper calls this. Activation is M2B wrapper adoption.
        """
        self._m2a_validate_fields(task_id, lane, role, access, task_class, artifact_expectation)
        new_record: dict = {
            "record_version": _M2A_RECORD_SCHEMA_VERSION,
            "task_id": task_id,
            "lane": lane,
            "role": role,
            "access": access,
            "task_class": task_class,
            "artifact_expectation": artifact_expectation,
            "created_epoch": int(time.time()),
            "record_revision": 1,
            "admission_producer": "dispatcher",
            "status": "queued",
        }

        def _mutate(records: list[dict]) -> tuple[dict, list[dict]]:
            for rec in records:
                if rec.get("task_id") == task_id or rec.get("id") == task_id:
                    raise RegistryError(f"registry_duplicate_task_id: {task_id}")
            return new_record, records + [new_record]

        return self._m2a_transact(_mutate)

    def attach_process(self, task_id: str, pid: int, pid_start_time: int,
                       expected_revision: Optional[int] = None) -> dict:
        """Transactional attach-process: add PID+start_time to queued record → running.

        DORMANT: No live wrapper calls this. Activation is M2B wrapper adoption.
        """
        if not isinstance(pid, int) or pid < 1 or pid > 4194304:
            raise RegistryError("registry_pid_invalid")
        if not isinstance(pid_start_time, int) or pid_start_time < 0:
            raise RegistryError("registry_pid_start_time_invalid")

        def _mutate(records: list[dict]) -> tuple[dict, list[dict]]:
            for i, rec in enumerate(records):
                if rec.get("task_id") != task_id and rec.get("id") != task_id:
                    continue
                if rec.get("record_version") != _M2A_RECORD_SCHEMA_VERSION:
                    raise RegistryError("registry_legacy_record_cannot_attach")
                current_rev = rec.get("record_revision", 0)
                if expected_revision is not None and current_rev != expected_revision:
                    raise RegistryError(
                        f"registry_stale_revision: expected {expected_revision}, got {current_rev}"
                    )
                if rec.get("status") != "queued":
                    raise RegistryError(
                        f"registry_illegal_transition: attach_process requires queued, "
                        f"got {rec.get('status')!r}"
                    )
                updated = dict(rec)
                updated["pid"] = pid
                updated["pid_start_time"] = pid_start_time
                updated["status"] = "running"
                updated["record_revision"] = current_rev + 1
                new_records = list(records)
                new_records[i] = updated
                return updated, new_records
            raise RegistryError(f"registry_task_not_found: {task_id}")

        return self._m2a_transact(_mutate)

    def transition_m2a(self, task_id: str, to_status: str,
                       terminal_reason: Optional[str] = None,
                       expected_revision: Optional[int] = None) -> dict:
        """Transactional state transition for M2A records. Returns the updated record.

        DORMANT: No live wrapper calls this. Activation is M2B wrapper adoption.
        """
        if to_status not in _M2A_LEGAL_TRANSITIONS:
            raise RegistryError(f"registry_illegal_to_status: {to_status!r}")
        if terminal_reason is not None:
            if (not isinstance(terminal_reason, str) or len(terminal_reason) > 128
                    or not _re.match(r"^[a-z0-9_.-]*$", terminal_reason)):
                raise RegistryError("registry_terminal_reason_invalid")

        def _mutate(records: list[dict]) -> tuple[dict, list[dict]]:
            for i, rec in enumerate(records):
                if rec.get("task_id") != task_id and rec.get("id") != task_id:
                    continue
                if rec.get("record_version") != _M2A_RECORD_SCHEMA_VERSION:
                    raise RegistryError("registry_legacy_record_cannot_transition")
                current_rev = rec.get("record_revision", 0)
                if expected_revision is not None and current_rev != expected_revision:
                    raise RegistryError(
                        f"registry_stale_revision: expected {expected_revision}, got {current_rev}"
                    )
                current_status = rec.get("status", "")
                allowed = _M2A_LEGAL_TRANSITIONS.get(current_status, frozenset())
                if to_status not in allowed:
                    raise RegistryError(
                        f"registry_illegal_transition: {current_status!r} -> {to_status!r}"
                    )
                updated = dict(rec)
                updated["status"] = to_status
                updated["record_revision"] = current_rev + 1
                if terminal_reason is not None:
                    updated["terminal_reason"] = terminal_reason
                if to_status in _M2A_TERMINAL_STATES:
                    updated["completed_epoch"] = int(time.time())
                new_records = list(records)
                new_records[i] = updated
                return updated, new_records
            raise RegistryError(f"registry_task_not_found: {task_id}")

        return self._m2a_transact(_mutate)

    def show_m2a(self, task_id: str) -> dict:
        """Read a single M2A record by task_id. Enforces regular-file and size bounds.

        DORMANT: No live wrapper calls this. Activation is M2B wrapper adoption.
        """
        for rec in self._m2a_read_records():
            if rec.get("task_id") == task_id or rec.get("id") == task_id:
                return dict(rec)
        raise RegistryError(f"registry_task_not_found: {task_id}")

    def reconcile_m2a(self) -> dict:
        """Mark M2A active records with dead PIDs as stale via one transactional write.

        DORMANT: No live wrapper calls this. Activation is M2B wrapper adoption.
        """
        reconciled: list[str] = []

        def _mutate(records: list[dict]) -> tuple[dict, list[dict]]:
            new_records = list(records)
            now_epoch = int(time.time())
            for i, rec in enumerate(records):
                if rec.get("record_version") != _M2A_RECORD_SCHEMA_VERSION:
                    continue
                if rec.get("status") not in {"running", "waiting", "cancelling"}:
                    continue
                if not self._pid_alive(rec.get("pid")):
                    updated = dict(rec)
                    updated["status"] = "stale"
                    updated["record_revision"] = rec.get("record_revision", 0) + 1
                    updated["stale_reason"] = "pid_not_alive"
                    updated["stale_epoch"] = now_epoch
                    new_records[i] = updated
                    reconciled.append(str(rec.get("task_id") or rec.get("id", "?")))
            return {"reconciled": reconciled, "count": len(reconciled)}, new_records

        return self._m2a_transact(_mutate)

    # ── R0.1: read-only compatibility lookup ──────────────────────────────────

    @staticmethod
    def _m2a_valid_id_str(value: object) -> bool:
        """Pure task-ID validator for record fields (same grammar as the writer)."""
        return (isinstance(value, str) and 1 <= len(value) <= _M2A_MAX_TASK_ID_LEN
                and bool(_re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$", value)))

    @staticmethod
    def _m2a_parse_dup_check(payload: bytes) -> dict:
        """Decode payload as UTF-8 and parse JSON with duplicate-key rejection at every depth."""
        def hook(pairs: list) -> dict:
            seen: set = set()
            result: dict = {}
            for key, value in pairs:
                if key in seen:
                    raise RegistryError("registry_record_duplicate_key")
                seen.add(key)
                result[key] = value
            return result
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RegistryError("registry_record_invalid_utf8") from exc
        try:
            result = json.loads(text, object_pairs_hook=hook)
        except RegistryError:
            raise
        except json.JSONDecodeError as exc:
            raise RegistryError("registry_record_malformed") from exc
        if not isinstance(result, dict):
            raise RegistryError("registry_record_not_object")
        return result

    def _m2a_compat_scan_impl(self, target_id: Optional[str]) -> dict:
        """Physical-line scanner for compatibility lookup and aggregate health.

        Returns dict: error_code, matched_record, is_legacy_target, compat_facts.
        """
        def _make_compat(lookup_health: str, strict_health: str,
                         oversized: Optional[int], ambiguous: Optional[int],
                         reason_codes: list) -> dict:
            if any(code not in _R01_REASON_CODES for code in reason_codes):
                raise RegistryError("registry_compatibility_reason_invalid")
            return {
                "schema_version": _R01_COMPAT_FACTS_VERSION,
                "lookup_health": lookup_health,
                "strict_mutation_health": strict_health,
                "oversized_legacy_rows": oversized,
                "ambiguous_or_corrupt_rows": ambiguous,
                "max_legacy_bound_bytes": _M2A_MAX_LEGACY_LOOKUP_BYTES,
                "reason_codes": sorted(set(reason_codes)),
            }

        def _unavail(code: str) -> dict:
            return {
                "error_code": code, "matched_record": None, "is_legacy_target": False,
                "compat_facts": _make_compat("unavailable", "unavailable", None, None, [code]),
            }

        def _blocked(code: str) -> dict:
            return {
                "error_code": code, "matched_record": None, "is_legacy_target": False,
                "compat_facts": _make_compat("blocked", "blocked", None, None, [code]),
            }

        # Prevent an attacker-substituted FIFO/device from blocking before
        # descriptor validation. Regular-file reads retain normal semantics.
        flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NONBLOCK", 0)
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            fd = os.open(str(self.registry_file), flags)
        except FileNotFoundError:
            return _unavail("registry_source_unavailable")
        except OSError as exc:
            code = ("registry_source_symlink" if exc.errno == errno.ELOOP
                    else "registry_read_open_failed")
            return _blocked(code) if code in _R01_INTEGRITY_CODES else _unavail(code)

        try:
            try:
                st = os.fstat(fd)
            except OSError:
                return _unavail("registry_source_unavailable")
            if not _stat.S_ISREG(st.st_mode):
                return _blocked("registry_source_not_regular")
            if st.st_size > _M2A_MAX_REGISTRY_BYTES:
                return _blocked("registry_file_too_large")

            oversized_legacy_rows = 0
            ambiguous_or_corrupt_rows = 0
            target_match_count = 0
            matched_record: Optional[dict] = None
            is_legacy_target = False
            scan_error: Optional[str] = None
            cumulative = 0
            buf = bytearray()
            eof_reached = False

            def _classify_line(payload: bytes) -> Optional[str]:
                nonlocal oversized_legacy_rows, ambiguous_or_corrupt_rows
                nonlocal target_match_count, matched_record, is_legacy_target

                if not payload.strip():
                    return None

                n = len(payload)
                if n > _M2A_MAX_LEGACY_LOOKUP_BYTES:
                    return "registry_legacy_row_over_compatibility_bound"

                legacy = n > _M2A_MAX_RECORD_BYTES

                try:
                    rec = TaskRegistry._m2a_parse_dup_check(payload)
                except RegistryError as exc:
                    ambiguous_or_corrupt_rows += 1
                    return str(exc)

                id_present = "id" in rec
                task_id_present = "task_id" in rec
                id_val = rec.get("id")
                task_id_val = rec.get("task_id")

                if not id_present and not task_id_present:
                    ambiguous_or_corrupt_rows += 1
                    return "registry_identity_missing"
                if ((id_present and not self._m2a_valid_id_str(id_val))
                        or (task_id_present and not self._m2a_valid_id_str(task_id_val))):
                    ambiguous_or_corrupt_rows += 1
                    return "registry_identity_invalid"
                if id_present and task_id_present and id_val != task_id_val:
                    ambiguous_or_corrupt_rows += 1
                    return "registry_identity_ambiguous"
                row_id = id_val if id_present else task_id_val

                if legacy:
                    oversized_legacy_rows += 1
                    if "record_version" in rec:
                        ambiguous_or_corrupt_rows += 1
                        return "registry_legacy_m2a_versioned"
                    if target_id is not None and row_id == target_id:
                        target_match_count += 1
                        if target_match_count >= 2:
                            return "registry_duplicate_target"
                        is_legacy_target = True
                else:
                    if target_id is not None and row_id == target_id:
                        target_match_count += 1
                        if target_match_count >= 2:
                            return "registry_duplicate_target"
                        if target_match_count == 1 and matched_record is None:
                            matched_record = dict(rec)

                return None

            while True:
                remaining = _M2A_MAX_REGISTRY_BYTES + 1 - cumulative
                if remaining <= 0:
                    break
                try:
                    chunk = os.read(fd, min(65536, remaining))
                except InterruptedError:
                    continue
                except OSError:
                    scan_error = "registry_source_unavailable"
                    break
                if not chunk:
                    eof_reached = True
                    break
                cumulative += len(chunk)
                if cumulative > _M2A_MAX_REGISTRY_BYTES:
                    scan_error = "registry_file_too_large"
                    break
                buf.extend(chunk)
                while True:
                    lf = buf.find(b"\n")
                    if lf == -1:
                        if len(buf) > _M2A_MAX_LEGACY_LOOKUP_BYTES + 2:
                            scan_error = "registry_legacy_row_over_compatibility_bound"
                        break
                    payload = bytes(buf[:lf])
                    buf = buf[lf + 1:]
                    if payload.endswith(b"\r"):
                        payload = payload[:-1]
                    if b"\r" in payload:
                        scan_error = "registry_record_bad_framing"
                        break
                    line_err = _classify_line(payload)
                    if line_err:
                        scan_error = line_err
                        break
                if scan_error:
                    break

            # A final unterminated record is accepted, but a CR there is bare and
            # therefore invalid; CR stripping is permitted only immediately before LF.
            if eof_reached and not scan_error and buf:
                payload = bytes(buf)
                if b"\r" in payload:
                    scan_error = "registry_record_bad_framing"
                else:
                    scan_error = _classify_line(payload)

            if eof_reached and not scan_error:
                # EOF before the initial descriptor size is a changed snapshot even
                # when a later fstat happens to describe the truncated inode cleanly.
                if cumulative != st.st_size:
                    scan_error = "registry_source_changed_during_read"
                try:
                    st2 = os.fstat(fd)
                except OSError:
                    scan_error = "registry_source_unavailable"
                if (not scan_error and
                        (st2.st_dev != st.st_dev or st2.st_ino != st.st_ino
                        or st2.st_size != st.st_size
                        or getattr(st2, "st_mtime_ns", 0) != getattr(st, "st_mtime_ns", 0)
                        or getattr(st2, "st_ctime_ns", 0) != getattr(st, "st_ctime_ns", 0))):
                    scan_error = "registry_source_changed_during_read"

        finally:
            try:
                os.close(fd)
            except OSError:
                pass

        if scan_error:
            lh = "unavailable" if scan_error in _R01_UNAVAILABLE_CODES else "blocked"
            return {
                "error_code": scan_error, "matched_record": None, "is_legacy_target": False,
                "compat_facts": _make_compat(lh, lh, None, None, [scan_error]),
            }

        obs = oversized_legacy_rows if eof_reached else None
        amb = ambiguous_or_corrupt_rows if eof_reached else None
        if oversized_legacy_rows > 0:
            lh, sh, codes = "degraded", "blocked", ["legacy_oversized_rows_present"]
        else:
            lh, sh, codes = "healthy", "healthy", []
        compat = _make_compat(lh, sh, obs, amb, codes)

        return {
            "error_code": None, "matched_record": matched_record,
            "is_legacy_target": is_legacy_target, "compat_facts": compat,
        }

    def lookup_m2a_compatible(self, task_id: str) -> dict:
        """Read-only compatibility lookup returning aq.registry-lookup-result.v1.

        Tolerates classified oversized legacy rows so unrelated bounded targets
        remain reachable. The strict 4 KiB mutation bound is unchanged.
        """
        _blank_compat = {
            "schema_version": _R01_COMPAT_FACTS_VERSION,
            "lookup_health": "unavailable", "strict_mutation_health": "unavailable",
            "oversized_legacy_rows": None, "ambiguous_or_corrupt_rows": None,
            "max_legacy_bound_bytes": _M2A_MAX_LEGACY_LOOKUP_BYTES, "reason_codes": [],
        }

        def _result(ok: bool, record: Optional[dict], error_code: Optional[str],
                    compat: dict) -> dict:
            return {
                "schema_version": _R01_LOOKUP_RESULT_VERSION, "ok": ok,
                "record": record, "error_code": error_code,
                "registry_compatibility": compat,
            }

        if not self._m2a_valid_id_str(task_id):
            return _result(False, None, "registry_task_id_invalid", _blank_compat)

        scan = self._m2a_compat_scan_impl(task_id)
        compat = scan["compat_facts"]
        error_code = scan["error_code"]

        if error_code == "registry_task_not_found":
            return _result(False, None, "registry_task_not_found", compat)
        if error_code:
            return _result(False, None, error_code, compat)
        if scan["is_legacy_target"] and scan["matched_record"] is None:
            return _result(False, None, "registry_target_legacy_oversized", compat)
        if scan["matched_record"] is not None:
            return _result(True, scan["matched_record"], None, compat)
        return _result(False, None, "registry_task_not_found", compat)

    def scan_registry_compat_facts(self) -> dict:
        """Aggregate registry compatibility health for projection injection.

        Returns aq.registry-compatibility-facts.v1 without a target lookup.
        """
        return self._m2a_compat_scan_impl(None)["compat_facts"]
