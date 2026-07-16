#!/usr/bin/env python3
"""Pure, read-only Agent Ops projection contract for R0M M0.

All OS and lifecycle facts are injected.  The module never scans the live host, writes an
authority, invokes a process, or performs network I/O.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = "aq.agent-ops-projection.v1"
ACTIVE_STATES = {"queued", "running", "waiting", "cancelling"}
TERMINAL_STATES = {"done", "completed", "failed", "cancelled", "orphaned", "error"}
LANES = {"local", "claude", "codex", "antigravity", "system", "unknown"}
METRICS = (
    "inbox_pending_count",
    "inbox_processing_duration_seconds",
    "cgroup_correlation_failures_total",
)
# M2A: queued grace window constants (dormant — used by projector for M2A new_record rows)
_M2A_QUEUED_GRACE_S = 30   # fresh PID-less dispatcher row visible as degraded/queued
_M2A_FUTURE_SKEW_S = 5     # created_epoch more than this many seconds in the future → stale
MAX_PROCESSES = 4096
MAX_REGISTRY = 4096
MAX_INBOX = 1024
MAX_ARGV = 128
MAX_TEXT = 4096
SENSITIVE_KEYS = {"prompt", "description", "output", "raw_command", "cmdline", "secret"}


class ProjectionError(ValueError):
    pass


def _iso(ts: int) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_id(value: str, fallback: str = "unknown") -> str:
    clean = re.sub(r"[^a-zA-Z0-9._:-]+", "-", value or "").strip("-").lower()
    return (clean or fallback)[:128]


def stable_digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ProcessFact:
    pid: int
    start_time: int
    ppid: int
    pgid: int
    session: int
    cgroup: str | None
    executable: str
    argv: tuple[str, ...]
    readable: bool = True

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ProcessFact":
        if value.get("error") in {"permission_denied", "unavailable"}:
            return cls(int(value["pid"]), 0, 0, 0, 0, None, "", (), False)
        argv = value.get("argv", [])
        executable = value.get("executable")
        if not isinstance(executable, str) or not executable or len(executable) > MAX_TEXT:
            raise ProjectionError("process_executable_invalid")
        if (not isinstance(argv, list) or len(argv) > MAX_ARGV
                or not all(isinstance(v, str) and len(v) <= MAX_TEXT for v in argv)):
            raise ProjectionError("process_argv_invalid")
        return cls(
            int(value["pid"]), int(value["start_time"]), int(value.get("ppid", 0)),
            int(value.get("pgid", 0)), int(value.get("session", 0)),
            value.get("cgroup"), executable, tuple(argv), True,
        )

    def identity(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if k not in {"argv", "readable", "executable"}}


def executable_kind(proc: ProcessFact) -> tuple[str, str]:
    """Return (kind, lane) using argv boundaries, never raw substring matching."""
    if not proc.readable:
        return "unreadable", "unknown"
    if not proc.executable:
        return "unknown", "unknown"
    exe = PurePosixPath(proc.executable).name.lower()
    args = [PurePosixPath(v).name.lower() for v in proc.argv[1:]]
    all_args = [v.lower() for v in proc.argv[1:]]
    if exe == "bwrap":
        return "sandbox_wrapper", "system"
    if exe in {"delegate-to-local", "delegate-to-claude", "delegate-to-codex", "delegate-to-antigravity"}:
        return "managed_task", exe.removeprefix("delegate-to-")
    if exe == "aq-agent-loop" or exe == "agent_executor.py":
        return "managed_child", "local"
    if exe == "codex":
        if "app-server" in all_args or "mcp-server" in all_args:
            return "daemon", "codex"
        if "exec" in all_args:
            return "managed_child", "codex"
        return "interactive_session", "codex"
    if exe in {"claude", "gemini"}:
        if "mcp-server" in all_args:
            return "daemon", "claude" if exe == "claude" else "antigravity"
        return "interactive_session", "claude" if exe == "claude" else "antigravity"
    # Incidental text such as a shell `-c '... exec ...'` is deliberately ignored.
    _ = args
    return "unknown", "unknown"


def _dedup_key(proc: ProcessFact, facts: Mapping[int, ProcessFact]) -> tuple[str, bool]:
    if proc.cgroup and len(proc.cgroup) <= MAX_TEXT and proc.cgroup not in {"/", "/user.slice", "/system.slice"}:
        return f"cgroup:{stable_digest(proc.cgroup)[:16]}", True
    seen: set[int] = set()
    cur = proc
    while cur.ppid in facts and cur.ppid not in seen:
        seen.add(cur.pid)
        cur = facts[cur.ppid]
    return f"ancestry:{cur.pid}:{cur.start_time}", False


def collapse_processes(processes: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    if len(processes) > MAX_PROCESSES:
        raise ProjectionError("process_snapshot_too_large")
    facts = {fact.pid: fact for fact in (ProcessFact.from_mapping(v) for v in processes)}
    groups: dict[str, list[ProcessFact]] = {}
    cgroup_failures = 0
    for fact in facts.values():
        key, used_cgroup = _dedup_key(fact, facts)
        if not used_cgroup and fact.ppid not in facts and fact.ppid not in {0, 1}:
            cgroup_failures += 1
        groups.setdefault(key, []).append(fact)
    output = []
    rank = {"managed_task": 0, "managed_child": 1, "sandbox_wrapper": 2,
            "interactive_session": 3, "daemon": 4, "unknown": 5, "unreadable": 6}
    for key, members in sorted(groups.items()):
        classified = [(executable_kind(member), member) for member in members]
        (kind, lane), representative = min(classified, key=lambda item: (rank[item[0][0]], item[1].pid))
        output.append({
            "dedup_group": key, "kind": kind, "lane": lane,
            "representative": representative, "members": tuple(sorted(m.pid for m in members)),
        })
    return output, cgroup_failures


def _base_work(work_id: str, lane: str, authority: str, *, role: str | None = None,
               model_profile: str | None = None) -> dict[str, Any]:
    return {
        "work_id": _safe_id(work_id), "lane": lane if lane in LANES else "unknown",
        "role": role, "model_profile": model_profile, "authority": authority,
        "state": "untracked", "phase": None, "progress_age_s": None, "pid_identity": None,
        "dedup_group": None, "access": "none", "terminal_reason": None,
        "artifact": "not_applicable", "visibility": "blocked",
        "reason_code": "untracked_process", "freshness": "unavailable",
    }


def _registry_pid(record: Mapping[str, Any]) -> tuple[int, int] | None:
    pid = record.get("pid")
    start = record.get("pid_start_time")
    return (int(pid), int(start)) if pid is not None and start is not None else None


def project_agent_ops(*, now: int, registry: Sequence[Mapping[str, Any]],
                      processes: Sequence[Mapping[str, Any]], inbox: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if len(registry) > MAX_REGISTRY:
        raise ProjectionError("registry_snapshot_too_large")
    if len(inbox) > MAX_INBOX:
        raise ProjectionError("inbox_snapshot_too_large")
    groups, cgroup_failures = collapse_processes(processes)
    process_index: dict[tuple[int, int], tuple[dict[str, Any], ProcessFact]] = {}
    for group in groups:
        for member in group["members"]:
            fact = next(ProcessFact.from_mapping(v) for v in processes if int(v["pid"]) == member)
            process_index[(fact.pid, fact.start_time)] = (group, fact)
    consumed: set[str] = set()
    claimed_identities: set[tuple[int, int]] = set()
    work: list[dict[str, Any]] = []

    for rec in registry:
        # M2A records use task_id/lane; legacy records use id/agent.
        _work_id = rec.get("id") or rec.get("task_id") or "registry-unknown"
        _lane = rec.get("agent") or rec.get("lane") or "unknown"
        item = _base_work(str(_work_id), str(_lane),
                          "delegation_registry", role=rec.get("role"), model_profile=rec.get("profile"))
        status = str(rec.get("status", "unknown")).lower()
        item["access"] = "writer" if rec.get("role") in {"implement", "implementer"} else "read_only"
        item["artifact"] = "present" if rec.get("artifact_present") else ("expected" if status in ACTIVE_STATES else "missing")
        identity = _registry_pid(rec)
        match = process_index.get(identity) if identity else None
        progress = rec.get("progress") if isinstance(rec.get("progress"), Mapping) else None
        trusted_progress = bool(progress and progress.get("trusted") is True and progress.get("producer") in {"dispatcher", "switchboard", "trusted_observer"})
        # A PID+start_time tuple is a single physical process: a second registry row claiming an
        # already-claimed identity is a duplicate task record, not a second live task.
        if status in ACTIVE_STATES and match and identity in claimed_identities:
            item.update(state="conflict", visibility="blocked", reason_code="registry_duplicate_claim", freshness="fresh")
        elif status in ACTIVE_STATES and match:
            claimed_identities.add(identity)
            group, fact = match
            item.update(state=status, pid_identity=fact.identity(), dedup_group=group["dedup_group"],
                        visibility="tracked", reason_code="registry_process_correlated", freshness="fresh")
            consumed.add(group["dedup_group"])
            if trusted_progress:
                item["phase"] = progress.get("phase")
                item["progress_age_s"] = max(0, now - int(progress.get("observed_at", now)))
            elif progress:
                item.update(visibility="degraded", reason_code="progress_untrusted")
        elif status == "queued" and identity is None:
            # M2A queued grace: fresh PID-less dispatcher rows are degraded/queued within the
            # 30-second grace window. Not authoritative — never claimed tracked/running.
            created_epoch = rec.get("created_epoch")
            if isinstance(created_epoch, int):
                skew = created_epoch - now
                age = now - created_epoch
                if skew > _M2A_FUTURE_SKEW_S:
                    item.update(state="stale", visibility="blocked",
                                reason_code="registry_queued_future_skew", freshness="stale")
                elif age > _M2A_QUEUED_GRACE_S:
                    item.update(state="stale", visibility="blocked",
                                reason_code="registry_queued_expired", freshness="stale")
                else:
                    item.update(state="queued", visibility="degraded",
                                reason_code="registry_queued_grace", freshness="fresh")
            else:
                item.update(state="stale", visibility="blocked",
                            reason_code="registry_process_missing", freshness="stale")
        elif status in ACTIVE_STATES:
            item.update(state="stale", visibility="blocked", reason_code="registry_process_missing", freshness="stale")
        elif status in TERMINAL_STATES:
            if match:
                group, fact = match
                item.update(state="conflict", pid_identity=fact.identity(), dedup_group=group["dedup_group"],
                            visibility="blocked", reason_code="terminal_process_alive", freshness="fresh")
                consumed.add(group["dedup_group"])
            else:
                item.update(state="terminal", visibility="tracked", reason_code="terminal_confirmed",
                            terminal_reason=status, freshness="fresh")
        else:
            item.update(state="conflict", reason_code="registry_status_unknown", freshness="stale")
        work.append(item)

    pending_durations: list[int] = []
    for entry in inbox:
        name = str(entry.get("name", "inbox-unknown"))
        item = _base_work(f"antigravity:{name}", "antigravity", "antigravity_inbox", role="reviewer")
        dropped = int(entry.get("dropped_at", now))
        archived = entry.get("archived_at")
        output_present = bool(entry.get("output_present"))
        if archived is not None:
            item.update(state="terminal", visibility="tracked", reason_code="inbox_archived",
                        artifact="present" if output_present else "missing", freshness="fresh",
                        terminal_reason="completed" if output_present else "missing_output")
            pending_durations.append(max(0, int(archived) - dropped))
        elif entry.get("pending") is True:
            item.update(state="queued", visibility="tracked", reason_code="inbox_pending",
                        artifact="present" if output_present else "expected", freshness="fresh",
                        progress_age_s=max(0, now - dropped))
            if output_present:
                item.update(visibility="degraded", reason_code="inbox_output_not_archived")
        else:
            item.update(state="stale", visibility="blocked", reason_code="inbox_state_conflict", freshness="stale")
        work.append(item)

    for group in groups:
        if group["dedup_group"] in consumed:
            continue
        fact: ProcessFact = group["representative"]
        item = _base_work(f"process:{fact.pid}:{fact.start_time}", group["lane"], "process_observer")
        item["dedup_group"] = group["dedup_group"]
        if fact.readable:
            item["pid_identity"] = fact.identity()
        kind = group["kind"]
        if kind == "daemon":
            item.update(state="idle", visibility="tracked", reason_code="idle_daemon", freshness="fresh")
        elif kind == "interactive_session":
            item.update(state="idle", visibility="degraded", reason_code="interactive_session_no_task", freshness="fresh")
        elif kind == "unreadable":
            item.update(state="untracked", visibility="blocked", reason_code="proc_permission_denied", freshness="unavailable")
        else:
            item.update(state="untracked", visibility="blocked", reason_code="process_without_authority", freshness="fresh")
        work.append(item)

    work.sort(key=lambda item: (item["visibility"] != "blocked", item["work_id"]))
    reasons = sorted({item["reason_code"] for item in work if item["visibility"] != "tracked"})
    verdict = "blocked" if any(item["visibility"] == "blocked" for item in work) else ("degraded" if reasons else "tracked")
    return {
        "schema_version": SCHEMA_VERSION, "generated_at": _iso(now),
        "health": {"verdict": verdict, "reason_codes": reasons, "source_freshness": "fresh"},
        "metrics": {
            "inbox_pending_count": sum(1 for entry in inbox if entry.get("pending") is True),
            "inbox_processing_duration_seconds": max(pending_durations) if pending_durations else None,
            "cgroup_correlation_failures_total": cgroup_failures,
        },
        "work": work,
    }


def assert_redacted(projection: Mapping[str, Any]) -> None:
    def walk(value: Any) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                if key in SENSITIVE_KEYS:
                    raise ProjectionError("sensitive_field_exposed")
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(projection)


def contract_health(projection: Mapping[str, Any]) -> dict[str, Any]:
    assert_redacted(projection)
    if projection.get("schema_version") != SCHEMA_VERSION:
        raise ProjectionError("projection_version_invalid")
    if set(projection.get("metrics", {})) != set(METRICS):
        raise ProjectionError("projection_metrics_invalid")
    return {"healthy": True, "digest": stable_digest(projection), "work_count": len(projection.get("work", []))}
