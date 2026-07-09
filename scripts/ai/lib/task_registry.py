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

import fcntl
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


_MAX_COMPLETED = 750    # max completed/failed entries in PENDING.json
_MAX_HANDOFF_LINES = 300  # max delegation tracking lines in HANDOFF.md


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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
