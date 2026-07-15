#!/usr/bin/env python3
"""Pure executable contract for Local Delegation Reliability R0.

This module deliberately does not import or call any live delegation surface.  It models
the contracts that R1-R4 must later adopt and provides deterministic fixture primitives.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence


PHASES = ("admitted", "queued", "prefill", "generating", "tool", "checkpoint", "terminal")
TERMINALS = {
    "queue_timeout", "prefill_timeout", "generation_silence", "tool_timeout",
    "orphaned", "operator_cap", "cancelled", "cancel_failed", "completed",
    "context_overflow", "oom_cleanup", "phase_evidence_unavailable",
    "stagnation_duplicate_evidence", "capability_exhausted",
}
LOW_CARDINALITY_METRICS = (
    "phase_duration_seconds", "phase_silence_seconds", "progress_renewals_total",
    "progress_rejections_total", "budget_provenance_total", "queue_age_seconds",
    "slot_contention_latency_ms", "lease_contention_latency_ms", "identity_collisions_total",
    "epoch_yields_total", "epoch_requeues_total", "cancellation_term_total",
    "cancellation_kill_total", "cancellation_failures_total", "oom_cleanup_total",
    "telemetry_integrity_rejections_total", "terminal_reasons_total",
    "compaction_bytes_saved", "compaction_cycles_total",
)
VOLATILE_KEYS = {"timestamp", "ts", "nonce", "transport_id", "request_id", "heartbeat_at"}
LIVE_IMPORT_MARKERS = (
    "dispatch", "task_registry", "task_config", "agent_executor", "switchboard", "llm_config"
)


class ContractError(ValueError):
    """A deterministic, sanitized contract rejection."""


def validate_json_schema(instance: Any, schema: Mapping[str, Any], root: Mapping[str, Any] | None = None, path: str = "$" ) -> None:
    """Validate the closed subset of Draft 2020-12 used by the committed policy."""
    root = root or schema
    if "$ref" in schema:
        target: Any = root
        for part in schema["$ref"].removeprefix("#/").split("/"):
            target = target[part]
        validate_json_schema(instance, target, root, path); return
    expected = schema.get("type")
    types = expected if isinstance(expected, list) else [expected] if expected else []
    type_ok = {
        "object": lambda v: isinstance(v, dict), "array": lambda v: isinstance(v, list),
        "string": lambda v: isinstance(v, str), "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "null": lambda v: v is None,
    }
    if types and not any(type_ok[t](instance) for t in types): raise ContractError(f"schema_type_invalid:{path}")
    if "const" in schema and instance != schema["const"]: raise ContractError(f"schema_const_invalid:{path}")
    if "enum" in schema and instance not in schema["enum"]: raise ContractError(f"schema_enum_invalid:{path}")
    if isinstance(instance, dict):
        required = set(schema.get("required", []))
        if not required.issubset(instance): raise ContractError(f"schema_required_missing:{path}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False and not set(instance).issubset(properties):
            raise ContractError(f"schema_unknown_property:{path}")
        for key, value in instance.items():
            if key in properties: validate_json_schema(value, properties[key], root, f"{path}.{key}")
    if isinstance(instance, list):
        if len(instance) < schema.get("minItems", 0): raise ContractError(f"schema_min_items:{path}")
        if schema.get("uniqueItems") and len({canonical_json(v) for v in instance}) != len(instance): raise ContractError(f"schema_unique_items:{path}")
        if "items" in schema:
            for index, value in enumerate(instance): validate_json_schema(value, schema["items"], root, f"{path}[{index}]")
    if isinstance(instance, int) and not isinstance(instance, bool) and "minimum" in schema and instance < schema["minimum"]:
        raise ContractError(f"schema_minimum:{path}")
    if isinstance(instance, int) and not isinstance(instance, bool) and "maximum" in schema and instance > schema["maximum"]:
        raise ContractError(f"schema_maximum:{path}")
    if isinstance(instance, str) and "pattern" in schema and not re.search(schema["pattern"], instance):
        raise ContractError(f"schema_pattern:{path}")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def validate_policy(policy: Mapping[str, Any], schema: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if schema is not None: validate_json_schema(policy, schema)
    required = {"schema_version", "identity", "budgets", "liveness", "admission", "progress", "context", "metrics", "compatibility_aliases"}
    if set(policy) != required:
        raise ContractError("policy_shape_invalid")
    if policy["schema_version"] != "aq.local-delegation-policy.v1":
        raise ContractError("policy_version_invalid")
    if policy["admission"].get("authority") != "switchboard":
        raise ContractError("competing_slot_authority")
    if policy["admission"]["epoch"].get("exhaustion_action") != "checkpoint_yield_requeue":
        raise ContractError("self_renewal_forbidden")
    if policy["admission"]["writer_lease"].get("lock_primitive") != "stable_descriptor_lock":
        raise ContractError("unstable_writer_lock")
    if policy["compatibility_aliases"]:
        raise ContractError("r0_alias_legitimization_forbidden")
    if tuple(policy["metrics"]) != LOW_CARDINALITY_METRICS:
        raise ContractError("metric_contract_invalid")
    for name, budget in policy["budgets"].items():
        if budget["min_tokens"] <= 0 or budget["max_tokens"] < budget["min_tokens"]:
            raise ContractError(f"budget_invalid:{name}")
    if policy["progress"]["duplicate_stop"] <= policy["progress"]["duplicate_nudge"]:
        raise ContractError("duplicate_threshold_invalid")
    return json.loads(canonical_json(policy))


def allocate_run_id(prefix: str, monotonic_ns: int, entropy: bytes, seen: set[str] | None = None) -> str:
    if len(entropy) < 12:
        raise ContractError("entropy_too_short")
    material = monotonic_ns.to_bytes(16, "big", signed=False) + entropy
    run_id = f"{prefix}-{monotonic_ns:032x}-{hashlib.blake2s(material, digest_size=16).hexdigest()}"
    if seen is not None:
        if run_id in seen:
            raise ContractError("identity_collision")
        seen.add(run_id)
    return run_id


def propagate_identity(run_id: str, surfaces: Sequence[str]) -> dict[str, str]:
    if not run_id or not re.fullmatch(r"[a-z][a-z0-9-]*-[0-9a-f]{32}-[0-9a-f]{32}", run_id):
        raise ContractError("identity_invalid")
    return {surface: run_id for surface in surfaces}


def resolve_budget(policy: Mapping[str, Any], task_class: str, explicit: int | None = None) -> dict[str, Any]:
    try:
        bounds = policy["budgets"][task_class]
    except KeyError as exc:
        raise ContractError("task_class_unknown") from exc
    value = bounds["max_tokens"] if explicit is None else explicit
    source = "policy" if explicit is None else "explicit"
    if value < bounds["min_tokens"]:
        raise ContractError("budget_undersized")
    if value > bounds["max_tokens"]:
        raise ContractError("budget_exceeds_policy")
    return {"task_class": task_class, "max_tokens": value, "source": source}


def phase_deadline(policy: Mapping[str, Any], phase: str, *, input_tokens: int = 0,
                   prefill_tps: float | None = None, cold_headroom_s: int = 0) -> float | None:
    live = policy["liveness"]
    if phase == "queued": return float(live["queue_s"])
    if phase == "prefill":
        if not prefill_tps or prefill_tps <= 0:
            return float(live["prefill_s"])
        return min(float(live["prefill_s"]), input_tokens / prefill_tps + cold_headroom_s)
    if phase == "generating": return float(live["generation_silence_s"])
    if phase == "tool": return float(live["tool_s"])
    if phase == "orphan": return float(live["orphan_s"])
    if phase == "operator": return live["operator_wall_clock_s"]
    raise ContractError("phase_unknown")


def evaluate_liveness(policy: Mapping[str, Any], phase: str, silence_s: float, *, total_elapsed_s: float = 0) -> str:
    reason = {"queued": "queue_timeout", "prefill": "prefill_timeout", "generating": "generation_silence", "tool": "tool_timeout", "orphan": "orphaned"}.get(phase)
    if reason is None: raise ContractError("phase_unknown")
    if silence_s > phase_deadline(policy, phase): return reason
    operator_cap = policy["liveness"]["operator_wall_clock_s"]
    if operator_cap is not None and total_elapsed_s > operator_cap: return "operator_cap"
    return "continue"


def monotonic_clock_evidence(start_ns: int, end_ns: int, host_start_s: int, host_end_s: int) -> dict[str, Any]:
    if end_ns < start_ns: raise ContractError("monotonic_clock_regressed")
    elapsed_s = (end_ns - start_ns) / 1_000_000_000
    return {"elapsed_s": elapsed_s, "host_drift_s": (host_end_s - host_start_s) - elapsed_s, "lease_clock": "monotonic"}


def validate_calibration(record: Mapping[str, Any], now: int, conservative_prefill_s: int) -> dict[str, Any]:
    required = {"model_revision", "profile_revision", "source", "measured_at", "expires_at", "cache_class", "sample_count", "tps", "uncertainty", "headroom"}
    if set(record) != required: raise ContractError("calibration_shape_invalid")
    if record["cache_class"] not in {"cold", "warm"} or record["sample_count"] < 1 or record["tps"] <= 0:
        raise ContractError("calibration_value_invalid")
    if record["expires_at"] <= now:
        return {"status": "degraded_stale", "prefill_s": conservative_prefill_s, "source": "conservative_policy"}
    return {"status": "fresh", "prefill_s": None, "source": record["source"], "uncertainty": record["uncertainty"], "headroom": record["headroom"]}


@dataclass(frozen=True)
class ProgressRecord:
    run_id: str
    epoch: int
    operation_id: str
    producer: str
    sequence: int
    monotonic_ns: int
    phase: str
    input_fingerprint: str
    result_digest: str
    semantic_delta: str
    correlation_id: str | None = None


@dataclass
class ProgressValidator:
    policy: Mapping[str, Any]
    run_id: str
    epoch: int
    last_sequence: int = 0
    last_monotonic_ns: int = -1
    seen_operations: set[str] = field(default_factory=set)

    def accept(self, record: ProgressRecord) -> str:
        if record.run_id != self.run_id or record.epoch != self.epoch:
            raise ContractError("progress_owner_mismatch")
        if record.producer not in self.policy["progress"]["allowed_producers"]:
            raise ContractError("progress_producer_untrusted")
        if record.sequence != self.last_sequence + 1 or record.monotonic_ns <= self.last_monotonic_ns:
            raise ContractError("progress_sequence_invalid")
        if record.operation_id in self.seen_operations:
            raise ContractError("progress_replay")
        if record.phase not in self.policy["progress"]["renewable_phases"]:
            raise ContractError("progress_phase_nonrenewable")
        if record.semantic_delta not in {"novel", "state_transition", "checkpoint"}:
            raise ContractError("progress_no_semantic_delta")
        if record.phase in {"queued", "prefill", "generating"} and not record.correlation_id:
            raise ContractError("phase_evidence_unavailable")
        self.last_sequence = record.sequence
        self.last_monotonic_ns = record.monotonic_ns
        self.seen_operations.add(record.operation_id)
        return record.phase


def parse_progress_sidecar(payload: str) -> Mapping[str, Any]:
    try:
        value = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ContractError("progress_sidecar_truncated") from exc
    required = {"run_id", "epoch", "operation_id", "producer", "sequence", "monotonic_ns", "phase", "input_fingerprint", "result_digest", "semantic_delta"}
    if not isinstance(value, dict) or not required.issubset(value):
        raise ContractError("progress_sidecar_truncated")
    return value


def normalized_evidence(tool: str, arguments: Mapping[str, Any], result: Any) -> tuple[str, str]:
    def scrub(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {str(k): scrub(v) for k, v in sorted(value.items()) if str(k) not in VOLATILE_KEYS}
        if isinstance(value, list): return [scrub(v) for v in value]
        if isinstance(value, str): return re.sub(r"\s+", " ", value).strip()
        return value
    return digest([tool, scrub(arguments)]), digest(scrub(result))


@dataclass
class DuplicateGuard:
    nudge_at: int
    stop_at: int
    counts: dict[tuple[str, str], int] = field(default_factory=dict)

    def observe(self, fingerprint: tuple[str, str]) -> str:
        count = self.counts.get(fingerprint, 0) + 1
        self.counts[fingerprint] = count
        if count >= self.stop_at: return "stagnation_duplicate_evidence"
        if count >= self.nudge_at: return "nudge_checkpoint"
        return "accepted_novel" if count == 1 else "accepted_repeat"


@dataclass(frozen=True)
class QueueItem:
    run_id: str
    enqueued_at: int
    base_priority: int = 0


def fair_order(items: Iterable[QueueItem], now: int, aging_s: int) -> list[str]:
    def rank(item: QueueItem) -> tuple[int, int, str]:
        aged = item.base_priority + max(0, now - item.enqueued_at) // aging_s
        return (-aged, item.enqueued_at, item.run_id)
    return [item.run_id for item in sorted(items, key=rank)]


def residency_action(residency_s: int, maximum_s: int) -> str:
    return "checkpoint_yield_requeue" if residency_s >= maximum_s else "continue"


@dataclass
class Epoch:
    number: int
    max_calls: int
    max_tokens: int
    max_resource_s: int
    calls: int = 0
    tokens: int = 0
    resource_s: int = 0
    yielded: bool = False

    def consume(self, calls: int, tokens: int, resource_s: int, *, actor: str = "scheduler") -> str:
        if actor != "scheduler": raise ContractError("self_renewal_forbidden")
        if self.yielded: raise ContractError("epoch_already_yielded")
        proposed = (self.calls + calls, self.tokens + tokens, self.resource_s + resource_s)
        if proposed[0] > self.max_calls or proposed[1] > self.max_tokens or proposed[2] > self.max_resource_s:
            self.yielded = True
            return "checkpoint_yield_requeue"
        self.calls, self.tokens, self.resource_s = proposed
        return "continue"


@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    starttime: int
    pgid: int
    session: int


@dataclass
class Cancellation:
    state: str = "running"
    terminal_publications: int = 0
    signals: list[str] = field(default_factory=list)

    def request(self) -> str:
        if self.state == "running": self.state = "cancelling"
        return self.state

    def send_term(self, captured: ProcessIdentity, observed: ProcessIdentity | None) -> str:
        if self.state != "cancelling" or observed != captured: raise ContractError("signal_identity_mismatch")
        if "SIGTERM" not in self.signals: self.signals.append("SIGTERM")
        return "sigterm_sent"

    def observe(self, captured: ProcessIdentity, observed: ProcessIdentity | None,
                *, grace_expired: bool = False, kill_succeeded: bool = True) -> str:
        if self.state != "cancelling": return self.state
        if observed is not None and observed != captured:
            self.state = "cancel_failed"
        elif observed is None:
            self.state = "cancelled"
        elif grace_expired and not kill_succeeded:
            self.state = "cancel_failed"
        elif grace_expired and kill_succeeded:
            if "SIGKILL" not in self.signals: self.signals.append("SIGKILL")
            return "sigkill_sent"
        else:
            return "sigterm_waiting"
        self.terminal_publications += 1
        return self.state

    def complete(self) -> str:
        if self.state == "running":
            self.state = "completed"; self.terminal_publications += 1
        return self.state


@dataclass(frozen=True)
class LeaseRecord:
    owner: str
    run_id: str
    epoch: int
    generation: int
    worktree: str
    paths: tuple[str, ...]
    process: ProcessIdentity


def canonical_paths(worktree: str, paths: Sequence[str], *, symlink_paths: Sequence[str] = ()) -> tuple[str, ...]:
    root = PurePosixPath(worktree)
    if not root.is_absolute(): raise ContractError("worktree_not_absolute")
    result = []
    for raw in paths:
        path = PurePosixPath(raw)
        if path.is_absolute() or ".." in path.parts:
            raise ContractError("lease_path_traversal")
        candidate = str(root / path)
        if candidate in set(symlink_paths): raise ContractError("lease_symlink_traversal")
        result.append(candidate)
    return tuple(sorted(set(result)))


def paths_overlap(left: Sequence[str], right: Sequence[str]) -> bool:
    for a in left:
        for b in right:
            if a == b or a.startswith(b.rstrip("/") + "/") or b.startswith(a.rstrip("/") + "/"):
                return True
    return False


def validate_lease_commit_steps(steps: Sequence[str]) -> str:
    required = ("stable_lock", "generation_cas", "write_new", "file_fsync", "atomic_replace", "directory_fsync")
    if tuple(steps) != required: raise ContractError("lease_commit_order_invalid")
    return "durable_fenced_commit"


@dataclass
class LeaseAuthority:
    stable_lock_inode: int = 1
    record_inode: int = 1
    generation: int = 0
    active: LeaseRecord | None = None
    mutex: threading.RLock = field(default_factory=threading.RLock, repr=False, compare=False)

    def acquire(self, owner: str, run_id: str, epoch: int, worktree: str, paths: Sequence[str], process: ProcessIdentity) -> LeaseRecord:
        with self.mutex:
            canonical = canonical_paths(worktree, paths)
            if self.active and paths_overlap(self.active.paths, canonical): raise ContractError("writer_lease_conflict")
            self.generation += 1
            self.record_inode += 1  # atomic replacement; stable lock inode deliberately unchanged
            self.active = LeaseRecord(owner, run_id, epoch, self.generation, worktree, canonical, process)
            return self.active

    def cas_update(self, expected_generation: int, *, opened_record_inode: int | None = None) -> int:
        with self.mutex:
            if expected_generation != self.generation: raise ContractError("lease_fence_stale")
            if opened_record_inode is not None and opened_record_inode != self.record_inode:
                raise ContractError("old_record_inode_rejected")
            self.record_inode += 1
            return self.record_inode

    def release(self, token: int, observed_process: ProcessIdentity | None) -> None:
        with self.mutex:
            if not self.active or token != self.active.generation: raise ContractError("lease_fence_stale")
            if observed_process is not None: raise ContractError("process_still_alive")
            self.active = None

    def recover_stale(self, expected_generation: int, observed_process: ProcessIdentity | None) -> int:
        with self.mutex:
            if not self.active or expected_generation != self.generation: raise ContractError("lease_fence_stale")
            if observed_process is not None: raise ContractError("stale_recovery_live_owner")
            self.active = None; self.generation += 1; self.record_inode += 1
            return self.generation

    def descriptor_owner_crash(self, process_dead: bool) -> str:
        with self.mutex:
            if not process_dead: raise ContractError("descriptor_release_without_death")
            self.active = None
            return "kernel_descriptor_auto_release"


@dataclass
class Registry:
    generation: int = 0
    records: dict[str, str] = field(default_factory=dict)
    mutex: threading.RLock = field(default_factory=threading.RLock, repr=False, compare=False)

    def snapshot(self) -> tuple[int, dict[str, str]]:
        with self.mutex: return self.generation, dict(self.records)

    def cas(self, expected: int, changes: Mapping[str, str]) -> int:
        with self.mutex:
            if expected != self.generation: raise ContractError("registry_generation_stale")
            self.records.update(changes); self.generation += 1
            return self.generation

    def mutate_retry(self, key: str, value: str) -> int:
        while True:
            generation, _ = self.snapshot()
            try: return self.cas(generation, {key: value})
            except ContractError as exc:
                if str(exc) != "registry_generation_stale": raise


def context_admit(input_tokens: int, reserved_output: int, limit: int) -> str:
    if min(input_tokens, reserved_output, limit) < 0: raise ContractError("context_value_invalid")
    if input_tokens + reserved_output > limit: raise ContractError("context_overflow")
    return "admitted"


def compact_checkpoint(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    provenance = [digest(record) for record in records]
    return {"record_count": len(records), "provenance": provenance, "integrity": digest(provenance)}


def oom_cleanup(process_alive: bool, lease_held: bool, reaped: bool) -> dict[str, Any]:
    if process_alive and not reaped: raise ContractError("oom_process_not_reaped")
    if lease_held and not reaped: raise ContractError("oom_lease_release_before_death")
    return {"terminal_reason": "oom_cleanup", "process_alive": False, "lease_held": False, "cleanup_evidence": "confirmed_death"}


def admission_route(target: str, inference_capable: bool, authority: str) -> str:
    if inference_capable and (target == "llama_direct" or authority != "switchboard"):
        raise ContractError("inference_admission_bypass")
    if target == "slots_poll" and inference_capable:
        raise ContractError("slots_poll_not_authority")
    return "switchboard_admitted" if inference_capable else "observation_only"


def writer_admission_sequence(writer_lease_held: bool, target: str = "switchboard") -> str:
    if not writer_lease_held: raise ContractError("writer_lease_required_before_inference")
    return admission_route(target, True, "switchboard")


def resolve_environment_override(name: str, declared_names: Sequence[str]) -> str:
    if name not in declared_names: raise ContractError("undeclared_environment_alias")
    return "declared_override"


def characterize_source(text: str, predicates: Sequence[str]) -> dict[str, Any]:
    hits = {predicate: predicate in text for predicate in predicates}
    return {"hits": hits, "all_present": all(hits.values())}


def characterize_rules(text: str, rules: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    results: list[bool] = []
    for rule in rules:
        kind, pattern = rule["kind"], rule["pattern"]
        if kind == "regex_present": results.append(re.search(pattern, text, re.MULTILINE | re.DOTALL) is not None)
        elif kind == "regex_count": results.append(len(re.findall(pattern, text, re.MULTILINE | re.DOTALL)) == rule["count"])
        elif kind == "block_absent":
            block = re.search(rule["start"] + r"(?P<body>.*?)" + rule["end"], text, re.MULTILINE | re.DOTALL)
            results.append(bool(block) and re.search(pattern, block.group("body")) is None)
        else: raise ContractError("characterization_kind_unknown")
    return {"results": results, "all_present": all(results)}


def adoption_guard(repo: Path, module_path: str, policy_path: str, live_sources: Sequence[str]) -> dict[str, Any]:
    module_text = (repo / module_path).read_text(encoding="utf-8")
    forbidden_imports = [marker for marker in LIVE_IMPORT_MARKERS if re.search(rf"(?:import|from)\s+[^\n]*{re.escape(marker)}", module_text)]
    consumers = []
    for source in live_sources:
        text = (repo / source).read_text(encoding="utf-8")
        if "local_delegation_reliability" in text or policy_path in text:
            consumers.append(source)
    if forbidden_imports or consumers:
        raise ContractError("premature_live_adoption")
    return {"pure_module": True, "live_consumers": [], "direct_inference_compliant": False}


def source_manifest(repo: Path, entries: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for entry in entries:
        path = repo / entry["path"]
        raw = path.read_bytes().replace(b"\r\n", b"\n")
        actual = hashlib.sha256(raw).hexdigest()
        output.append({"path": entry["path"], "sha256": actual, "matches_frozen": actual == entry["sha256"]})
    return output


def tree_manifest(root: Path) -> list[dict[str, Any]]:
    if not root.exists(): return []
    return [{"path": str(path.relative_to(root)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for path in sorted(root.rglob("*")) if path.is_file()]


def fixture_vector_payload(fixture: Mapping[str, Any]) -> dict[str, Any]:
    keys = ("defects", "identity", "budget_vectors", "phase_vector", "fairness", "environment", "clock_drift_seconds", "metrics", "sanitized_terminal_reasons")
    return {key: fixture[key] for key in keys}


def execute_golden(repo: Path, fixture_path: Path, policy_path: Path, schema_path: Path) -> dict[str, Any]:
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validate_policy(policy, schema)
    manifest = source_manifest(repo, fixture["live_sources"])
    current_evidence: dict[str, list[bool]] = {f"D{i}": [] for i in range(1, 12)}
    for entry, observed in zip(fixture["live_sources"], manifest):
        rules_ok = characterize_rules((repo / entry["path"]).read_text(encoding="utf-8"), entry["characterizations"])["all_present"]
        for defect in entry["defects"]: current_evidence[defect].append(bool(observed["matches_frozen"] and rules_ok))
    current = {defect: bool(values) and all(values) for defect, values in current_evidence.items()}
    seen: set[str] = set()
    ids = [allocate_run_id("aq", fixture["identity"]["same_time_ns"], i.to_bytes(16, "big"), seen) for i in range(fixture["identity"]["count"])]
    process = ProcessIdentity(1, 1, 1, 1)
    cancellation = Cancellation(); cancellation.request(); cancellation.request()
    cancellation.send_term(process, process); cancellation.send_term(process, process)
    cancellation.observe(process, process, grace_expired=True); cancellation.observe(process, process, grace_expired=True)
    cancellation.observe(process, None)
    progress_run = ids[0]
    progress = ProgressValidator(policy, progress_run, 1)
    progress_ok = progress.accept(ProgressRecord(progress_run, 1, "golden-op", "switchboard", 1, 1, "queued", "in", "out", "state_transition", "golden-correlation")) == "queued"
    lease = LeaseAuthority(); lease_record = lease.acquire("dispatcher", ids[1], 1, str(repo.resolve()), ["fixture"], process)
    lease.release(lease_record.generation, None)
    fixed = {
        "D1": len(ids) == len(set(ids)),
        "D2": resolve_budget(policy, "code")["max_tokens"] == policy["budgets"]["code"]["max_tokens"],
        "D3": all(resolve_budget(policy, v["class"])["max_tokens"] == v["expected"] for v in fixture["budget_vectors"]),
        "D4": phase_deadline(policy, "queued") != phase_deadline(policy, "prefill"),
        "D5": Epoch(1, 1, 1, 1).consume(2, 2, 2) == "checkpoint_yield_requeue",
        "D6": len({normalized_evidence("read_file", {"path": str(i)}, i) for i in range(20)}) == 20,
        "D7": len({normalized_evidence("query", {"q": i}, i) for i in range(15)}) == 15,
        "D8": cancellation.signals == ["SIGTERM", "SIGKILL"] and cancellation.terminal_publications == 1,
        "D9": admission_route("switchboard", True, "switchboard") == "switchboard_admitted" and lease.active is None,
        "D10": tuple(policy["metrics"]) == LOW_CARDINALITY_METRICS,
        "D11": progress_ok,
    }
    vector_digest = digest(fixture_vector_payload(fixture))
    manifest_digest = digest([{key: entry[key] for key in ("path", "sha256", "defects", "characterizations")} for entry in fixture["live_sources"]])
    fixed_digest = digest(fixed)
    if fixture["stable_digests"] != {"vectors": vector_digest, "source_manifest": manifest_digest, "fixed_contract": fixed_digest}:
        raise ContractError("golden_digest_mismatch")
    return {"current_characterized": current, "fixed_contract": fixed, "manifest": manifest,
            "vector_digest": vector_digest, "source_manifest_digest": manifest_digest,
            "fixed_contract_digest": fixed_digest}


def contract_health(repo: Path, fixture_path: Path, policy_path: Path, schema_path: Path) -> dict[str, Any]:
    evidence = execute_golden(repo, fixture_path, policy_path, schema_path)
    failures = sorted(key for key in evidence["fixed_contract"] if not evidence["fixed_contract"][key])
    return {"schema_version": "aq.local-delegation-policy.v1", "healthy": not failures,
            "failed_checks": failures, "evidence_digest": digest(evidence)}
