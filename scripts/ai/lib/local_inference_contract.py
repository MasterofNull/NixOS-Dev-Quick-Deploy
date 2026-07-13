#!/usr/bin/env python3
"""Pure L1A local-inference contract normalization and resolution.

Live adapters intentionally do not import this module yet.  Request resolution consumes
only caller data plus injected trusted facts; it performs no I/O, clock, lifecycle, model,
or telemetry operation.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

CONTRACT_VERSION = "1.0"
SCHEMA_FILES = {
    "request": "local-inference-request.schema.json",
    "result": "local-inference-result.schema.json",
    "event": "local-inference-event.schema.json",
    "error": "local-inference-error.schema.json",
}
_BUDGET_KEYS = ("input_tokens", "output_tokens", "deadline_ms", "queue_wait_ms", "max_tool_calls")
_PRIORITY_RANK = {"background": 0, "normal": 1, "interactive": 2}
_ROLES = {"orchestrator", "architect", "implementer", "reviewer"}


@dataclass(frozen=True)
class ContractError(ValueError):
    """Stable fail-closed contract error without backend exception leakage."""

    code: str
    reason_code: str
    safe_message: str
    retryable: bool = False

    def __str__(self) -> str:
        return f"{self.code}:{self.reason_code}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "contract_version": CONTRACT_VERSION,
            "code": self.code,
            "message": self.safe_message,
            "retryable": self.retryable,
            "reason_code": self.reason_code,
            "evidence_ref": None,
        }


def _reject_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError("invalid_request", "duplicate_json_key", "JSON contains a duplicate key")
        result[key] = value
    return result


def parse_json_strict(raw: str | bytes) -> Any:
    """Parse one JSON value, rejecting duplicate keys and non-finite numbers."""
    try:
        return json.loads(
            raw,
            object_pairs_hook=_reject_duplicate,
            parse_constant=lambda _value: (_ for _ in ()).throw(
                ContractError("invalid_request", "non_finite_number", "JSON contains a non-finite number")
            ),
        )
    except ContractError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError("invalid_request", "malformed_json", "Input is not valid JSON") from exc


def _nfc(value: Any) -> Any:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [_nfc(item) for item in value]
    if isinstance(value, tuple):
        return [_nfc(item) for item in value]
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for raw_key, item in value.items():
            if not isinstance(raw_key, str):
                raise ContractError("invalid_request", "non_string_json_key", "JSON object keys must be strings")
            key = unicodedata.normalize("NFC", raw_key)
            if key in normalized:
                raise ContractError("invalid_request", "normalized_duplicate_key", "Unicode normalization creates a duplicate key")
            normalized[key] = _nfc(item)
        return normalized
    if isinstance(value, float) and not math.isfinite(value):
        raise ContractError("invalid_request", "non_finite_number", "JSON contains a non-finite number")
    return value


def canonical_json_bytes(value: Any) -> bytes:
    """Return the contract's recursively NFC-normalized canonical UTF-8 JSON."""
    try:
        return json.dumps(
            _nfc(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    except ContractError:
        raise
    except (TypeError, ValueError) as exc:
        raise ContractError("invalid_request", "non_canonical_value", "Value cannot be canonicalized") from exc


def _copy(value: Any) -> Any:
    return copy.deepcopy(value)


def normalize_chat_request(source: Mapping[str, Any]) -> dict[str, Any]:
    """Independently map the aq-chat source shape to the wire request."""
    ids = source["ids"]
    actor = source["actor"]
    turn = source["turn"]
    route = source["route"]
    limits = source["limits"]
    output = source["output"]
    lease = route.get("lease") or {}
    return {
        "contract_version": CONTRACT_VERSION,
        "request_id": ids["request"], "trace_id": ids["trace"], "session_id": ids.get("session"),
        "parent_run_id": ids.get("parent_run"), "idempotency_key": ids["idempotency"],
        "requester": {"source": "aq-chat", "agent_id": actor["id"], "model_class": actor["class"], "requested_role": actor["role_intent"], "trust_boundary": actor["boundary"]},
        "task": {"objective": turn["text"], "task_class": turn["kind"], "domain": turn["domain"], "repo_paths": _copy(turn.get("paths", [])), "edit_sites": turn.get("edit_count", 0), "anti_goals": _copy(turn.get("avoid", []))},
        "execution": {"mode": route["mode"], "response_mode": route["response"], "preferred_lane": route["lane"], "requested_profile": route["profile"], "side_effects": route["effects"], "allowed_tools": _copy(route.get("tools", [])), "max_tool_calls": route.get("tool_limit", 0), "approval_ref": route.get("approval"), "tool_lease": {"lease_id": lease.get("id"), "expires_at": lease.get("until"), "repo_root": lease.get("root", "/"), "cwd": lease.get("cwd", ""), "path_globs": _copy(lease.get("paths", [])), "command_prefixes": _copy(lease.get("commands", []))}},
        "context": {"messages": _copy(source["conversation"]["messages"]), "artifact_refs": _copy(source["conversation"].get("artifacts", [])), "memory_keys": _copy(source["conversation"].get("memory", [])), "summary": source["conversation"].get("summary", ""), "inline_max_chars": source["conversation"]["char_limit"], "template_version": source["conversation"]["template"], "context_adapter_version": source["conversation"]["adapter"], "compaction_policy_version": source["conversation"]["compaction"]},
        "artifact": {"format": output["kind"], "schema_id": output.get("schema"), "max_chars": output["char_limit"], "acceptance_criteria": _copy(output.get("accept", [])), "evidence_requirements": _copy(output.get("evidence", []))},
        "budget": {"input_tokens": limits["input"], "output_tokens": limits["output"], "deadline_ms": limits["deadline"], "queue_wait_ms": limits["queue"], "priority": limits["priority"]},
        "fallback": {"mode": source["degradation"]["policy"], "allowed_profiles": _copy(source["degradation"].get("profiles", [])), "equivalence_registry_version": source["degradation"]["registry"], "max_attempts": source["degradation"]["attempts"]},
        "validation": {"checks": _copy(source["verification"].get("checks", [])), "require_live": source["verification"]["live"], "reviewer_separation": source["verification"]["separate_reviewer"]},
    }


def normalize_delegate_request(source: Mapping[str, Any]) -> dict[str, Any]:
    """Independently map the delegate-to-local source shape to the wire request."""
    metadata = source["metadata"]
    task = source["task"]
    dispatch = source["dispatch"]
    budget = source["budget"]
    lease = dispatch.get("authority_lease") or {}
    requester = {
        "source": "delegate-to-local", "agent_id": metadata["agent_id"],
        "model_class": metadata["model_tier"], "requested_role": metadata["requested_role"],
        "trust_boundary": metadata["boundary"],
    }
    execution = {
        "mode": dispatch["execution_mode"], "response_mode": dispatch["result_mode"],
        "preferred_lane": dispatch["lane"], "requested_profile": dispatch["profile"],
        "side_effects": dispatch["side_effect_scope"], "allowed_tools": _copy(dispatch.get("tool_names", [])),
        "max_tool_calls": dispatch.get("tool_budget", 0), "approval_ref": dispatch.get("approval_reference"),
        "tool_lease": {"lease_id": lease.get("lease_id"), "expires_at": lease.get("expires_at"), "repo_root": lease.get("repository", "/"), "cwd": lease.get("working_directory", ""), "path_globs": _copy(lease.get("path_scope", [])), "command_prefixes": _copy(lease.get("commands", []))},
    }
    prompt = source["prompt_context"]
    deliverable = source["deliverable"]
    failure = source["failure_policy"]
    gates = source["gates"]
    return {
        "contract_version": CONTRACT_VERSION,
        "request_id": metadata["request_id"], "trace_id": metadata["trace_id"], "session_id": metadata.get("session_id"),
        "parent_run_id": metadata.get("parent_run_id"), "idempotency_key": metadata["idempotency_key"],
        "requester": requester,
        "task": {"objective": task["objective"], "task_class": task["class"], "domain": task["domain"], "repo_paths": _copy(task.get("repository_paths", [])), "edit_sites": task.get("edit_sites", 0), "anti_goals": _copy(task.get("anti_goals", []))},
        "execution": execution,
        "context": {"messages": _copy(prompt["ordered_messages"]), "artifact_refs": _copy(prompt.get("artifact_references", [])), "memory_keys": _copy(prompt.get("memory_references", [])), "summary": prompt.get("compact_summary", ""), "inline_max_chars": prompt["inline_character_cap"], "template_version": prompt["prompt_template_version"], "context_adapter_version": prompt["adapter_version"], "compaction_policy_version": prompt["compaction_version"]},
        "artifact": {"format": deliverable["format"], "schema_id": deliverable.get("schema_id"), "max_chars": deliverable["maximum_characters"], "acceptance_criteria": _copy(deliverable.get("acceptance", [])), "evidence_requirements": _copy(deliverable.get("evidence", []))},
        "budget": {"input_tokens": budget["max_input_tokens"], "output_tokens": budget["max_output_tokens"], "deadline_ms": budget["deadline_ms"], "queue_wait_ms": budget["queue_timeout_ms"], "priority": budget["requested_priority"]},
        "fallback": {"mode": failure["fallback_mode"], "allowed_profiles": _copy(failure.get("equivalent_profiles", [])), "equivalence_registry_version": failure["registry_version"], "max_attempts": failure["attempt_limit"]},
        "validation": {"checks": _copy(gates.get("validation_checks", [])), "require_live": gates["live_required"], "reviewer_separation": gates["independent_review"]},
    }


def _fail(code: str, reason: str, message: str) -> None:
    raise ContractError(code, reason, message)


def _validate_top_shape(request: Mapping[str, Any]) -> None:
    required = {"contract_version", "request_id", "trace_id", "session_id", "parent_run_id", "idempotency_key", "requester", "task", "execution", "context", "artifact", "budget", "fallback", "validation"}
    if set(request) != required:
        _fail("invalid_request", "request_fields_invalid", "Request fields do not match contract version 1.0")
    if request.get("contract_version") != CONTRACT_VERSION:
        _fail("invalid_request", "contract_version_invalid", "Unsupported contract version")


def _parse_time(value: str, reason: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("timezone required")
        return parsed.astimezone(timezone.utc)
    except (AttributeError, ValueError) as exc:
        raise ContractError("invalid_request", reason, "Timestamp must be timezone-aware RFC 3339") from exc


def _within_root(path: str, root: str) -> bool:
    candidate = PurePosixPath(path)
    canonical_root = PurePosixPath(root)
    return candidate.is_absolute() and (candidate == canonical_root or canonical_root in candidate.parents)


def _validate_paths(request: Mapping[str, Any], trusted: Mapping[str, Any]) -> None:
    root = trusted["repository_root"]
    resolved = trusted["resolved_paths"]
    for raw in request["task"]["repo_paths"]:
        lexical = PurePosixPath(raw)
        if lexical.is_absolute() or ".." in lexical.parts or raw not in resolved:
            _fail("unauthorized", "repository_path_invalid", "Repository path is not an injected safe relative path")
        if not _within_root(resolved[raw], root):
            _fail("unauthorized", "canonical_path_escape", "Resolved repository path escapes the trusted root")


def _validated_lease(request: Mapping[str, Any], trusted: Mapping[str, Any]) -> Mapping[str, Any] | None:
    desired = request["execution"]["tool_lease"]
    lease_id = desired.get("lease_id")
    if lease_id is None:
        if desired.get("expires_at") is not None:
            _fail("unauthorized", "lease_shape_invalid", "Lease expiry cannot exist without a lease ID")
        return None
    matches = [lease for lease in trusted["authority_leases"] if lease.get("lease_id") == lease_id]
    if len(matches) != 1:
        _fail("unauthorized", "lease_unverified", "Requested lease was not issued by the trusted authority")
    lease = matches[0]
    if desired.get("expires_at") != lease.get("expires_at") or desired.get("repo_root") != lease.get("repo_root"):
        _fail("unauthorized", "lease_claim_mismatch", "Requested lease claims do not match the authority record")
    now = _parse_time(trusted["now"], "trusted_time_invalid")
    if _parse_time(lease["expires_at"], "lease_expiry_invalid") <= now:
        _fail("unauthorized", "lease_expired", "Requested authority lease has expired")
    if lease.get("repo_root") != trusted["repository_root"]:
        _fail("unauthorized", "lease_repository_mismatch", "Authority lease does not bind the trusted repository")
    for key in ("path_globs", "command_prefixes"):
        if not set(desired.get(key, [])).issubset(set(lease.get(key, []))):
            _fail("unauthorized", "lease_scope_widening", "Requested lease scope exceeds authority scope")
    if desired.get("cwd") != lease.get("cwd"):
        _fail("unauthorized", "lease_cwd_mismatch", "Requested working directory differs from authority lease")
    for path in request["task"]["repo_paths"]:
        if not any(fnmatchcase(path, pattern) for pattern in lease.get("path_globs", [])):
            _fail("unauthorized", "lease_path_denied", "Requested repository path is outside lease scope")
    return lease


def resolve_request(request: Mapping[str, Any], trusted: Mapping[str, Any]) -> dict[str, Any]:
    """Resolve a validated-shaped request using only injected immutable trusted facts."""
    request = _copy(request)
    trusted = _copy(trusted)
    _validate_top_shape(request)
    _validate_paths(request, trusted)
    execution = request["execution"]
    budget = request["budget"]
    profile = execution["requested_profile"]
    available = trusted["available_profiles"]
    if profile not in available:
        _fail("unavailable_profile", "requested_profile_unavailable", "Requested profile is not explicitly available")
    for fallback_profile in request["fallback"]["allowed_profiles"]:
        if fallback_profile not in available:
            _fail("unavailable_profile", "fallback_profile_unavailable", "Requested fallback profile is not explicitly available")
    if request["task"]["task_class"] not in trusted["eligible_task_classes"]:
        _fail("ineligible", "task_class_ineligible", "Task class is not eligible for local inference")
    priority = budget["priority"]
    ceiling = trusted["priority_ceiling"]
    if priority not in _PRIORITY_RANK or ceiling not in _PRIORITY_RANK or _PRIORITY_RANK[priority] > _PRIORITY_RANK[ceiling]:
        _fail("unauthorized", "priority_exceeds_ceiling", "Requested queue priority exceeds trusted assignment")
    assigned = trusted.get("assigned_role")
    effective_role = assigned if assigned is not None else "implementer"
    if effective_role not in _ROLES:
        _fail("unauthorized", "trusted_role_invalid", "Trusted role assignment is invalid")
    approval_ref = execution.get("approval_ref")
    if approval_ref is not None and approval_ref not in trusted["verified_approvals"]:
        _fail("unauthorized", "approval_unverified", "Requested approval reference is not verified")
    lease = _validated_lease(request, trusted)
    side_effects = execution["side_effects"]
    requested_tools = set(execution["allowed_tools"])
    if side_effects == "none" and (requested_tools or execution["max_tool_calls"] != 0):
        _fail("invalid_request", "side_effect_tool_mismatch", "Tool requests contradict side_effects=none")
    if side_effects in {"read", "write"} and (not requested_tools or execution["max_tool_calls"] < 1):
        _fail("invalid_request", "side_effect_tool_mismatch", "Tool side effects require a non-empty bounded tool request")
    if side_effects == "write":
        if effective_role not in {"implementer", "orchestrator"}:
            _fail("unauthorized", "role_cannot_write", "Effective role cannot receive write authority")
        if approval_ref is None or lease is None:
            _fail("unauthorized", "write_authority_missing", "Write requires verified approval and authority lease")
    eligible = set(trusted["eligible_tools"].get(request["task"]["task_class"], []))
    role_tools = set(trusted["role_tools"].get(effective_role, []))
    runtime = set(trusted["runtime_tools"])
    lease_tools = set(lease.get("tools", [])) if lease is not None else runtime
    approval_tools = set(trusted["approval_tools"].get(approval_ref, [])) if approval_ref is not None else runtime
    effective_tools = sorted(requested_tools & eligible & role_tools & runtime & lease_tools & approval_tools)
    if side_effects != "none" and not effective_tools:
        _fail("unauthorized", "no_effective_tools", "No requested tool survives trusted authority intersection")
    policy_budget = trusted["policy_budgets"]
    runtime_budget = trusted["runtime_budgets"]
    requested_budget = {**budget, "max_tool_calls": execution["max_tool_calls"]}
    effective_budget: dict[str, int] = {}
    for key in _BUDGET_KEYS:
        values = (requested_budget[key], policy_budget[key], runtime_budget[key])
        if any(not isinstance(value, int) or isinstance(value, bool) or value < (0 if key == "max_tool_calls" else 1) for value in values):
            _fail("invalid_request", "budget_invalid", "Budgets must be positive integers (tool calls may be zero)")
        effective_budget[key] = min(values)
    effective_budget["max_tool_calls"] = min(effective_budget["max_tool_calls"], len(effective_tools) and effective_budget["max_tool_calls"] or 0)
    capability_delta = sorted(requested_tools - set(effective_tools))
    return {
        "contract_version": CONTRACT_VERSION, "config_version": trusted["config_version"],
        "mode": execution["mode"], "requested_profile": profile, "profile": profile,
        "model": available[profile], "task_class": request["task"]["task_class"],
        "effective_role": effective_role, "side_effects": side_effects,
        "tools": effective_tools, "budgets": effective_budget, "queue_band": priority,
        "fallback": {"mode": request["fallback"]["mode"], "allowed_profiles": sorted(request["fallback"]["allowed_profiles"]), "max_attempts": request["fallback"]["max_attempts"], "equivalence_registry_version": request["fallback"]["equivalence_registry_version"]},
        "capability_delta": capability_delta,
        "reasons": ["explicit_profile_available", "trusted_role_assignment" if assigned else "unassigned_role_implementer_constraints", "componentwise_budget_minimum", "trusted_tool_intersection"],
    }


def _load_schema(path: Path) -> dict[str, Any]:
    value = parse_json_strict(path.read_bytes())
    if not isinstance(value, dict):
        raise ContractError("invalid_request", "schema_not_object", "Schema root must be an object")
    return value


def _validate_with_schema(instance: Any, schema: Mapping[str, Any]) -> None:
    try:
        from jsonschema import Draft202012Validator, FormatChecker
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(instance)
    except ImportError as exc:
        raise ContractError("malformed_result", "validator_unavailable", "Draft 2020-12 validator is unavailable") from exc
    except Exception as exc:
        raise ContractError("invalid_request", "schema_validation_failed", "Document does not satisfy its contract schema") from exc


def _schema_structure_offline_strict(schema: Mapping[str, Any]) -> None:
    """Dependency-light structural guard for the runtime dashboard projection."""
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        raise ContractError("malformed_result", "schema_draft_invalid", "Contract schema draft is invalid")

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and not ref.startswith("#"):
                raise ContractError("malformed_result", "schema_external_reference", "Contract schema contains an external reference")
            if node.get("type") == "object" and node.get("additionalProperties") is not False:
                raise ContractError("malformed_result", "schema_open_object", "Contract schema contains an open object boundary")
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
    walk(schema)


def _schema_is_offline_strict(schema: Mapping[str, Any]) -> None:
    try:
        from jsonschema import Draft202012Validator
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        raise ContractError("malformed_result", "schema_invalid", "Contract schema is invalid") from exc

    _schema_structure_offline_strict(schema)


def run_golden_vectors(
    repo_root: Path,
    fixture_path: Path | None = None,
    *,
    full_schema_validation: bool = True,
) -> dict[str, Any]:
    """Execute offline schemas plus pinned chat/delegation parity vectors."""
    fixture = fixture_path or repo_root / "scripts/testing/fixtures/local-inference-contract-v1-golden.json"
    vectors_doc = parse_json_strict(fixture.read_bytes())
    if set(vectors_doc) != {"contract_version", "vectors"} or vectors_doc["contract_version"] != CONTRACT_VERSION:
        raise ContractError("malformed_result", "fixture_shape_invalid", "Golden fixture has an invalid root shape")
    request_schema = _load_schema(repo_root / "config/schemas" / SCHEMA_FILES["request"])
    _schema_is_offline_strict(request_schema)
    checked = 0
    for vector in vectors_doc["vectors"]:
        if set(vector) != {"id", "chat", "delegate", "trusted", "expected_canonical_utf8"}:
            raise ContractError("malformed_result", "vector_shape_invalid", "Golden vector has an invalid shape")
        chat_request = normalize_chat_request(vector["chat"])
        delegate_request = normalize_delegate_request(vector["delegate"])
        if full_schema_validation:
            _validate_with_schema(chat_request, request_schema)
            _validate_with_schema(delegate_request, request_schema)
        chat_bytes = canonical_json_bytes(resolve_request(chat_request, vector["trusted"]))
        delegate_bytes = canonical_json_bytes(resolve_request(delegate_request, vector["trusted"]))
        expected = vector["expected_canonical_utf8"].encode("utf-8")
        if chat_bytes != expected or delegate_bytes != expected or chat_bytes != delegate_bytes:
            raise ContractError("malformed_result", "golden_parity_mismatch", "Golden resolver parity mismatch")
        checked += 1
    if checked < 1:
        raise ContractError("malformed_result", "fixture_empty", "Golden fixture contains no vectors")
    return {"parity_status": "pass", "vector_count": checked, "digest": hashlib.sha256(fixture.read_bytes()).hexdigest()}


def contract_health(repo_root: Path, fixture_path: Path | None = None) -> dict[str, Any]:
    """Return the bounded read-only dashboard projection; never leak exception text."""
    health: dict[str, Any] = {
        "status": "unavailable", "mode": "fixture_only", "contract_version": CONTRACT_VERSION,
        "schemas": {name: "unavailable" for name in SCHEMA_FILES}, "parity_status": "unavailable",
        "vector_count": 0, "digest": None, "freshness": "commit_fixture", "source": "commit_fixture",
        "reason_code": "contract_assets_missing",
    }
    schema_dir = repo_root / "config/schemas"
    try:
        for name, filename in SCHEMA_FILES.items():
            path = schema_dir / filename
            if not path.is_file():
                return health
            try:
                _schema_structure_offline_strict(_load_schema(path))
                health["schemas"][name] = "structural_valid"
            except (ContractError, OSError):
                health["status"] = "degraded"
                health["schemas"][name] = "invalid"
                health["reason_code"] = "contract_schema_invalid"
                return health
        result = run_golden_vectors(repo_root, fixture_path, full_schema_validation=False)
        health.update(result)
        health["status"] = "healthy"
        health["reason_code"] = "contract_fixture_parity_pass"
    except FileNotFoundError:
        health["reason_code"] = "contract_fixture_missing"
    except (ContractError, OSError):
        health["status"] = "degraded"
        health["parity_status"] = "fail"
        health["reason_code"] = "contract_fixture_invalid"
    return health


__all__ = [
    "CONTRACT_VERSION", "ContractError", "canonical_json_bytes", "contract_health",
    "normalize_chat_request", "normalize_delegate_request", "parse_json_strict",
    "resolve_request", "run_golden_vectors",
]
