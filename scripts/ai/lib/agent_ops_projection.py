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


SCHEMA_VERSION = "aq.agent-ops-projection.v2"
REVIEW_FACTS_VERSION = "aq.review-feedback-facts.v1"
ACTIVE_STATES = {"queued", "running", "waiting", "cancelling"}
TERMINAL_STATES = {"done", "completed", "failed", "cancelled", "orphaned", "error"}
LANES = {"local", "claude", "codex", "antigravity", "system", "unknown"}
LEGACY_METRICS = (
    "inbox_pending_count",
    "inbox_processing_duration_seconds",
    "cgroup_correlation_failures_total",
)
REVIEW_METRICS = (
    "review_required_lanes_count",
    "review_received_lanes_count",
    "review_parked_lanes_count",
    "review_unavailable_lanes_count",
    "review_abstained_lanes_count",
    "review_oldest_wait_seconds",
    "review_revision_count",
    "review_open_findings_count",
    "review_critical_undisposed_count",
    "feedback_promotion_pending_count",
    "feedback_freshness_age_seconds",
)
METRICS = LEGACY_METRICS + REVIEW_METRICS
# M2A: queued grace window constants (dormant — used by projector for M2A new_record rows)
_M2A_QUEUED_GRACE_S = 30   # fresh PID-less dispatcher row visible as degraded/queued
_M2A_FUTURE_SKEW_S = 5     # created_epoch more than this many seconds in the future → stale
MAX_PROCESSES = 4096
MAX_REGISTRY = 4096
MAX_INBOX = 1024
MAX_ARGV = 128
MAX_TEXT = 4096
SENSITIVE_KEYS = {
    "argv", "cmdline", "command", "credential", "credentials", "description", "environment",
    "headers", "output", "path", "prompt", "prompt_digest", "raw_command", "raw_error", "secret", "token",
}
REVIEW_FACT_KEYS = {
    "contract_version", "receipt_schema_version", "candidate_schema_version", "subject_hash",
    "pass_id", "baseline_hash", "baseline_state", "terminal_decision", "revision", "superseded",
    "binding_required", "binding_received", "roster_complete", "required_lanes", "received_lanes",
    "parked_lanes", "unavailable_lanes", "abstained_lanes", "oldest_wait_s", "open_findings",
    "critical_undisposed", "disposed_findings", "promotion_state", "promotion_pending",
    "feedback_freshness", "feedback_freshness_age_s", "lanes", "reason_codes",
}
REVIEW_LANE_KEYS = {"lane", "role", "model_tier", "eligibility", "state", "verdict"}
REVIEW_ROLES = {"architect", "implementer", "orchestrator", "reviewer"}
MODEL_TIERS = {"flagship", "economical", "local", "embedded"}
REVIEW_ELIGIBILITY = {"advisory", "binding_flagship", "recused"}
REVIEW_LANE_STATES = {"submitted", "failed", "timed_out", "parked", "unavailable", "nonterminal"}
REVIEW_VERDICTS = {"pass", "revision_required", "fail", "abstain"}
TERMINAL_DECISIONS = {"accepted", "revision_required", "rejected", "incomplete"}
BASELINE_STATES = {"aligned", "mismatched"}
FEEDBACK_FRESHNESS = {"fresh", "stale", "unavailable"}
PROMOTION_STATES = {
    "captured", "triaged", "fixture_bound", "candidate_prepared", "shadow_validated",
    "flagship_accepted", "canary", "promoted", "rolled_back", "non_propagated", "not_assessed",
}
_SAFE_TOKEN = re.compile(r"^[a-z0-9][a-z0-9._:-]*$")
_SAFE_REASON = re.compile(r"^[a-z0-9_]+$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


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


def _exact_keys(value: Mapping[str, Any], expected: set[str], reason: str) -> None:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise ProjectionError(reason)


def _bounded_int(value: Any, reason: str, *, maximum: int = 1_000_000) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
        raise ProjectionError(reason)
    return value


def _bounded_token(value: Any, reason: str, *, maximum: int = 128) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= maximum or not _SAFE_TOKEN.fullmatch(value):
        raise ProjectionError(reason)
    return value


def _default_review_feedback() -> dict[str, Any]:
    return {
        "contract_version": REVIEW_FACTS_VERSION,
        "health": "unavailable",
        "assessment": "not_assessed",
        "subject_hash": None,
        "pass_id": None,
        "baseline_state": "not_assessed",
        "terminal_decision": "not_assessed",
        "revision": None,
        "superseded": None,
        "binding_required": None,
        "binding_received": None,
        "roster_complete": None,
        "required_lanes": None,
        "received_lanes": None,
        "parked_lanes": None,
        "unavailable_lanes": None,
        "abstained_lanes": None,
        "oldest_wait_s": None,
        "finding_state": "not_assessed",
        "open_findings": None,
        "critical_undisposed": None,
        "disposed_findings": None,
        "promotion_state": "not_assessed",
        "promotion_pending": None,
        "freshness": "unavailable",
        "freshness_age_s": None,
        "lanes": [],
        "reason_codes": ["review_feedback_not_assessed"],
    }


def _review_metrics(review: Mapping[str, Any]) -> dict[str, int | None]:
    return {
        "review_required_lanes_count": review["required_lanes"],
        "review_received_lanes_count": review["received_lanes"],
        "review_parked_lanes_count": review["parked_lanes"],
        "review_unavailable_lanes_count": review["unavailable_lanes"],
        "review_abstained_lanes_count": review["abstained_lanes"],
        "review_oldest_wait_seconds": review["oldest_wait_s"],
        "review_revision_count": review["revision"],
        "review_open_findings_count": review["open_findings"],
        "review_critical_undisposed_count": review["critical_undisposed"],
        "feedback_promotion_pending_count": review["promotion_pending"],
        "feedback_freshness_age_seconds": review["freshness_age_s"],
    }


def project_review_feedback(facts: Mapping[str, Any] | None) -> dict[str, Any]:
    """Project already-adjudicated C0.5A facts without consulting any live authority."""
    if facts is None:
        return _default_review_feedback()
    _exact_keys(facts, REVIEW_FACT_KEYS, "review_facts_shape_invalid")
    if facts["contract_version"] != REVIEW_FACTS_VERSION:
        raise ProjectionError("review_facts_version_invalid")
    if facts["receipt_schema_version"] != "aq.review-round-receipt.v1":
        raise ProjectionError("review_receipt_version_invalid")
    if facts["candidate_schema_version"] != "aq.learning-candidate.v1":
        raise ProjectionError("learning_candidate_version_invalid")
    if not isinstance(facts["subject_hash"], str) or not _SHA256.fullmatch(facts["subject_hash"]):
        raise ProjectionError("review_subject_hash_invalid")
    if not isinstance(facts["baseline_hash"], str) or not _SHA256.fullmatch(facts["baseline_hash"]):
        raise ProjectionError("review_baseline_hash_invalid")
    pass_id = _bounded_token(facts["pass_id"], "review_pass_id_invalid")
    baseline_state = facts["baseline_state"]
    decision = facts["terminal_decision"]
    freshness = facts["feedback_freshness"]
    promotion_state = facts["promotion_state"]
    if baseline_state not in BASELINE_STATES: raise ProjectionError("review_baseline_state_invalid")
    if decision not in TERMINAL_DECISIONS: raise ProjectionError("review_terminal_decision_invalid")
    if freshness not in FEEDBACK_FRESHNESS: raise ProjectionError("feedback_freshness_invalid")
    if promotion_state not in PROMOTION_STATES: raise ProjectionError("promotion_state_invalid")
    if not isinstance(facts["superseded"], bool) or not isinstance(facts["roster_complete"], bool):
        raise ProjectionError("review_boolean_invalid")

    values = {
        name: _bounded_int(facts[name], f"review_{name}_invalid",
                           maximum=31_536_000 if name.endswith("_s") else 1_000_000)
        for name in (
            "revision", "binding_required", "binding_received", "required_lanes", "received_lanes",
            "parked_lanes", "unavailable_lanes", "abstained_lanes", "oldest_wait_s", "open_findings",
            "critical_undisposed", "disposed_findings", "promotion_pending", "feedback_freshness_age_s",
        )
    }
    for name in ("binding_required", "binding_received", "required_lanes", "received_lanes",
                 "parked_lanes", "unavailable_lanes", "abstained_lanes"):
        if values[name] > 64:
            raise ProjectionError(f"review_{name}_invalid")
    if values["binding_received"] > values["binding_required"]:
        raise ProjectionError("review_binding_totals_invalid")
    if values["received_lanes"] > values["required_lanes"]:
        raise ProjectionError("review_roster_totals_invalid")
    if values["abstained_lanes"] > values["received_lanes"]:
        raise ProjectionError("review_abstention_totals_invalid")
    if values["parked_lanes"] + values["unavailable_lanes"] > values["required_lanes"]:
        raise ProjectionError("review_unavailable_totals_invalid")

    raw_lanes = facts["lanes"]
    if not isinstance(raw_lanes, list) or len(raw_lanes) > 64:
        raise ProjectionError("review_lanes_invalid")
    lanes: list[dict[str, Any]] = []
    seen_lanes: set[str] = set()
    for raw in raw_lanes:
        _exact_keys(raw, REVIEW_LANE_KEYS, "review_lane_shape_invalid")
        lane = _bounded_token(raw["lane"], "review_lane_id_invalid", maximum=64)
        if lane in seen_lanes: raise ProjectionError("review_lane_duplicate")
        seen_lanes.add(lane)
        if raw["role"] not in REVIEW_ROLES: raise ProjectionError("review_lane_role_invalid")
        if raw["model_tier"] not in MODEL_TIERS: raise ProjectionError("review_lane_model_tier_invalid")
        if raw["eligibility"] not in REVIEW_ELIGIBILITY: raise ProjectionError("review_lane_eligibility_invalid")
        if raw["state"] not in REVIEW_LANE_STATES: raise ProjectionError("review_lane_state_invalid")
        if raw["verdict"] is not None and raw["verdict"] not in REVIEW_VERDICTS:
            raise ProjectionError("review_lane_verdict_invalid")
        if raw["state"] == "submitted" and raw["verdict"] is None:
            raise ProjectionError("review_lane_verdict_missing")
        if raw["state"] != "submitted" and raw["verdict"] is not None:
            raise ProjectionError("review_lane_verdict_unexpected")
        lanes.append({key: raw[key] for key in sorted(REVIEW_LANE_KEYS)})
    lanes.sort(key=lambda lane: lane["lane"])

    if values["required_lanes"] < 1 or values["binding_required"] < 1:
        raise ProjectionError("review_roster_policy_invalid")
    if len(lanes) > values["required_lanes"]:
        raise ProjectionError("review_lane_roster_overflow")
    observed_submitted = sum(lane["state"] == "submitted" for lane in lanes)
    observed_parked = sum(lane["state"] == "parked" for lane in lanes)
    observed_unavailable = sum(lane["state"] == "unavailable" for lane in lanes)
    observed_abstained = sum(
        lane["state"] == "submitted" and lane["verdict"] == "abstain" for lane in lanes
    )
    observed_binding = sum(
        lane["state"] == "submitted"
        and lane["verdict"] == "pass"
        and lane["eligibility"] == "binding_flagship"
        and lane["model_tier"] == "flagship"
        and lane["role"] == "reviewer"
        for lane in lanes
    )
    observed = {
        "received_lanes": observed_submitted,
        "parked_lanes": observed_parked,
        "unavailable_lanes": observed_unavailable,
        "abstained_lanes": observed_abstained,
        "binding_received": observed_binding,
    }
    for name, count in observed.items():
        if values[name] != count:
            raise ProjectionError(f"review_{name}_observation_mismatch")
    if facts["roster_complete"]:
        if len(lanes) != values["required_lanes"] or any(
                lane["state"] == "nonterminal" for lane in lanes):
            raise ProjectionError("review_complete_roster_unrepresented")

    reasons = facts["reason_codes"]
    if (not isinstance(reasons, list) or len(reasons) > 32 or len(set(reasons)) != len(reasons)
            or not all(isinstance(reason, str) and 1 <= len(reason) <= 64
                       and _SAFE_REASON.fullmatch(reason) for reason in reasons)):
        raise ProjectionError("review_reason_codes_invalid")
    derived_reasons = set(reasons)
    finding_state = "blocked" if values["critical_undisposed"] else ("open" if values["open_findings"] else "clear")
    blocked = False
    degraded = False
    blocking_evidence = {
        "review_subject_drift", "review_policy_drift", "review_roster_drift", "review_criteria_drift",
        "review_self_review", "review_material_rewriter",
    }
    if blocking_evidence.intersection(derived_reasons):
        blocked = True
    if baseline_state == "mismatched": blocked = True; derived_reasons.add("review_baseline_mismatch")
    if decision == "rejected": blocked = True; derived_reasons.add("review_rejected")
    if values["critical_undisposed"]: blocked = True; derived_reasons.add("critical_finding_undisposed")
    if facts["superseded"]: blocked = True; derived_reasons.add("review_subject_superseded")
    if decision in {"incomplete", "revision_required"}: degraded = True; derived_reasons.add(f"review_{decision}")
    if not facts["roster_complete"]: degraded = True; derived_reasons.add("review_roster_incomplete")
    if values["binding_received"] < values["binding_required"]: degraded = True; derived_reasons.add("review_quorum_incomplete")
    if values["parked_lanes"]: degraded = True; derived_reasons.add("review_lane_parked")
    if values["unavailable_lanes"]: degraded = True; derived_reasons.add("review_lane_unavailable")
    if freshness != "fresh": degraded = True; derived_reasons.add(f"feedback_{freshness}")
    healthy_contract = (
        baseline_state == "aligned" and decision == "accepted" and facts["roster_complete"]
        and values["binding_received"] >= values["binding_required"]
        and values["critical_undisposed"] == 0 and not facts["superseded"] and freshness == "fresh"
    )
    health = "blocked" if blocked else ("degraded" if degraded or not healthy_contract else "healthy")
    return {
        "contract_version": REVIEW_FACTS_VERSION,
        "health": health,
        "assessment": "assessed",
        "subject_hash": facts["subject_hash"],
        "pass_id": pass_id,
        "baseline_state": baseline_state,
        "terminal_decision": decision,
        "revision": values["revision"],
        "superseded": facts["superseded"],
        "binding_required": values["binding_required"],
        "binding_received": values["binding_received"],
        "roster_complete": facts["roster_complete"],
        "required_lanes": values["required_lanes"],
        "received_lanes": values["received_lanes"],
        "parked_lanes": values["parked_lanes"],
        "unavailable_lanes": values["unavailable_lanes"],
        "abstained_lanes": values["abstained_lanes"],
        "oldest_wait_s": values["oldest_wait_s"],
        "finding_state": finding_state,
        "open_findings": values["open_findings"],
        "critical_undisposed": values["critical_undisposed"],
        "disposed_findings": values["disposed_findings"],
        "promotion_state": promotion_state,
        "promotion_pending": values["promotion_pending"],
        "freshness": freshness,
        "freshness_age_s": values["feedback_freshness_age_s"],
        "lanes": lanes,
        "reason_codes": sorted(derived_reasons),
    }


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
        value = {k: v for k, v in asdict(self).items() if k not in {"argv", "readable", "executable"}}
        value["cgroup"] = f"cgroup:{stable_digest(self.cgroup)[:16]}" if self.cgroup else None
        return value


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
                      processes: Sequence[Mapping[str, Any]], inbox: Sequence[Mapping[str, Any]],
                      dispatch_contract: Mapping[str, Any] | None = None,
                      review_feedback_facts: Mapping[str, Any] | None = None) -> dict[str, Any]:
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
    dispatch = {
        "contract_version": "aq.dispatch.contract.v1",
        "health": "unavailable",
        "broker_state": "not_assessed",
        "adapter_health": {lane: "unavailable" for lane in ("local", "claude", "codex", "antigravity")},
        "counts": {"queued": None, "running": None, "parked": None, "terminal": None},
        "coverage_health": {gate: "unavailable" for gate in ("aq_qa", "agent_ops", "web_dashboard")},
        "reason_codes": ["dispatch_broker_not_assessed"],
    }
    if dispatch_contract is not None:
        dispatch = json.loads(json.dumps(dispatch_contract))
    review_feedback = project_review_feedback(review_feedback_facts)
    metrics = {
        "inbox_pending_count": sum(1 for entry in inbox if entry.get("pending") is True),
        "inbox_processing_duration_seconds": max(pending_durations) if pending_durations else None,
        "cgroup_correlation_failures_total": cgroup_failures,
    }
    metrics.update(_review_metrics(review_feedback))
    return {
        "schema_version": SCHEMA_VERSION, "generated_at": _iso(now),
        "health": {"verdict": verdict, "reason_codes": reasons, "source_freshness": "fresh"},
        "metrics": metrics,
        "dispatch_contract": dispatch,
        "review_feedback": review_feedback,
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
    dispatch = projection.get("dispatch_contract", {})
    review = projection.get("review_feedback", {})
    return {
        "healthy": dispatch.get("health") == "healthy" and review.get("health") == "healthy",
        "dispatch_health": dispatch.get("health", "unavailable"),
        "review_feedback_health": review.get("health", "unavailable"),
        "review_terminal_decision": review.get("terminal_decision", "not_assessed"),
        "feedback_promotion_state": review.get("promotion_state", "not_assessed"),
        "digest": stable_digest(projection),
        "work_count": len(projection.get("work", [])),
    }
