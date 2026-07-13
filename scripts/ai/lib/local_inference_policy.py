#!/usr/bin/env python3
"""Pure L2A caller/task policy and shadow request builder.

Only the dashboard fixture-health loader may import this module at runtime in
L2A. Live inference callers and execution paths intentionally do not.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


_HERE = Path(__file__).resolve().parent
_BUDGET_KEYS = ("input_tokens", "output_tokens", "deadline_ms", "queue_wait_ms", "max_tool_calls")
_SIDE_EFFECT_RANK = {"none": 0, "read": 1, "write": 2}
_POLICY_ROOT_KEYS = {
    "contract_version", "policy_version", "profile_catalog", "profile_decisions", "caller_tiers",
    "task_classes", "blocked_domains", "context", "strict_json",
}
_PROFILE_DECISIONS = {
    "default": "legacy_excluded",
    "embedded-assist": "registered",
    "continue-local": "registered",
    "local-coding": "conflicted_unavailable",
    "local-tool-calling": "registered_read_only_target",
    "local-agent": "registered",
    "ralph": "mode_only",
}


def _load_sibling(filename: str, module_name: str):
    existing = sys.modules.get(module_name)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(module_name, _HERE / filename)
    if spec is None or spec.loader is None:
        raise ImportError(module_name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


LIC = _load_sibling("local_inference_contract.py", "aq_l2a_contract_dependency")
CTX = _load_sibling("local_inference_context.py", "aq_l2a_context_dependency")


@dataclass(frozen=True)
class PolicyError(ValueError):
    code: str
    reason_code: str
    safe_message: str

    def __str__(self) -> str:
        return f"{self.code}:{self.reason_code}"


def _fail(reason: str, message: str, code: str = "invalid_request") -> None:
    raise PolicyError(code, reason, message)


def _positive_budgets(value: Any, reason: str) -> dict[str, int]:
    if not isinstance(value, Mapping) or set(value) != set(_BUDGET_KEYS):
        _fail(reason, "Budget fact fields are invalid")
    result: dict[str, int] = {}
    for key in _BUDGET_KEYS:
        item = value[key]
        minimum = 0 if key == "max_tool_calls" else 1
        if not isinstance(item, int) or isinstance(item, bool) or item < minimum:
            _fail(reason, "Budget facts must be bounded integers")
        result[key] = item
    return result


def _validate_policy_shape(policy: Any) -> dict[str, Any]:
    if not isinstance(policy, dict) or set(policy) != _POLICY_ROOT_KEYS:
        _fail("policy_shape_invalid", "Policy root fields are invalid", "malformed_result")
    if policy.get("contract_version") != "1.0" or not isinstance(policy.get("policy_version"), str):
        _fail("policy_version_invalid", "Policy version is invalid", "malformed_result")
    if policy.get("profile_catalog") != {
        "source": "config/switchboard-profiles.yaml", "realization": "immutable_injected_snapshot"
    }:
        _fail("profile_catalog_contract_invalid", "Profile catalog reference is invalid", "malformed_result")
    if policy.get("profile_decisions") != _PROFILE_DECISIONS:
        _fail("profile_decisions_invalid", "Profile transition decisions are invalid", "malformed_result")
    callers = policy.get("caller_tiers")
    if not isinstance(callers, dict) or set(callers) != {"flagship", "standard", "budget", "deterministic"}:
        _fail("caller_policy_invalid", "Caller-tier policy is invalid", "malformed_result")
    for caller in callers.values():
        if not isinstance(caller, dict) or set(caller) != {"budgets", "inline_max_chars"}:
            _fail("caller_policy_invalid", "Caller-tier fields are invalid", "malformed_result")
        _positive_budgets(caller["budgets"], "caller_budget_invalid")
        if not isinstance(caller["inline_max_chars"], int) or isinstance(caller["inline_max_chars"], bool):
            _fail("caller_policy_invalid", "Caller context budget is invalid", "malformed_result")
    if not isinstance(policy.get("task_classes"), dict) or not isinstance(policy.get("context"), dict):
        _fail("policy_shape_invalid", "Task or context policy is invalid", "malformed_result")
    return copy.deepcopy(policy)


def load_policy(repo_root: Path, *, full_schema_validation: bool = True) -> dict[str, Any]:
    """Load and validate the committed shadow policy without environment overlays."""
    policy_path = repo_root / "config" / "local-inference-policy.json"
    schema_path = repo_root / "config" / "schemas" / "local-inference-policy.schema.json"
    try:
        policy = LIC.parse_json_strict(policy_path.read_bytes())
        schema = LIC.parse_json_strict(schema_path.read_bytes())
        LIC._schema_structure_offline_strict(schema)
        if full_schema_validation:
            LIC._schema_is_offline_strict(schema)
            LIC._validate_with_schema(policy, schema)
        return _validate_policy_shape(policy)
    except PolicyError:
        raise
    except FileNotFoundError:
        raise
    except Exception as exc:
        raise PolicyError("malformed_result", "policy_validation_failed", "Policy validation failed") from exc


def build_caller_request(base_request: Mapping[str, Any], caller_tier: str, profile: str) -> dict[str, Any]:
    """Deterministically adapt a validated-shaped draft for one untrusted caller tier."""
    if caller_tier not in {"flagship", "standard", "budget", "deterministic"}:
        _fail("caller_tier_invalid", "Caller tier is invalid")
    request = copy.deepcopy(dict(base_request))
    try:
        request["requester"]["model_class"] = caller_tier
        request["execution"]["requested_profile"] = profile
    except (KeyError, TypeError) as exc:
        raise PolicyError("invalid_request", "request_shape_invalid", "Request shape is invalid") from exc
    return request


def _validate_trusted_l1(trusted: Any) -> dict[str, Any]:
    required = {
        "assigned_role", "priority_ceiling", "verified_approvals", "approval_tools",
        "authority_leases", "available_profiles", "eligible_task_classes", "eligible_tools",
        "role_tools", "runtime_tools", "policy_budgets", "runtime_budgets", "repository_root",
        "resolved_paths", "now", "config_version",
    }
    if not isinstance(trusted, Mapping) or not required.issubset(trusted):
        _fail("trusted_facts_invalid", "Trusted resolver facts are incomplete", "unauthorized")
    result = copy.deepcopy(dict(trusted))
    _positive_budgets(result["runtime_budgets"], "runtime_budget_invalid")
    for key in ("available_profiles", "eligible_tools", "role_tools", "resolved_paths"):
        if not isinstance(result[key], Mapping):
            _fail("trusted_facts_invalid", "Trusted resolver fact type is invalid", "unauthorized")
    for key in ("verified_approvals", "authority_leases", "eligible_task_classes", "runtime_tools"):
        if not isinstance(result[key], list):
            _fail("trusted_facts_invalid", "Trusted resolver fact type is invalid", "unauthorized")
    return result


def _resolve_policy_facts(
    request: Mapping[str, Any],
    trusted: Mapping[str, Any],
    trusted_ingress: Mapping[str, Any],
    profile_facts: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if not isinstance(trusted_ingress, Mapping) or set(trusted_ingress) != {
        "authenticated_model_class", "profile_snapshot_revision", "response_format_supported"
    }:
        _fail("trusted_ingress_invalid", "Trusted ingress facts are invalid", "unauthorized")
    caller_tier = trusted_ingress["authenticated_model_class"]
    if caller_tier not in policy["caller_tiers"]:
        _fail("trusted_caller_tier_invalid", "Authenticated caller tier is invalid", "unauthorized")
    if not isinstance(trusted_ingress["profile_snapshot_revision"], str) or not isinstance(
        trusted_ingress["response_format_supported"], bool
    ):
        _fail("trusted_ingress_invalid", "Trusted ingress fact type is invalid", "unauthorized")
    try:
        task_class = request["task"]["task_class"]
        domain = request["task"]["domain"]
        execution = request["execution"]
        profile = execution["requested_profile"]
    except (KeyError, TypeError) as exc:
        raise PolicyError("invalid_request", "request_shape_invalid", "Request shape is invalid") from exc
    if domain in policy["blocked_domains"]:
        _fail("task_domain_ineligible", "Task domain is ineligible for local inference", "ineligible")
    task_rule = policy["task_classes"].get(task_class)
    if not isinstance(task_rule, Mapping) or task_rule.get("eligible") is not True:
        _fail("task_class_ineligible", "Task class is ineligible for local inference", "ineligible")
    side_effects = execution.get("side_effects")
    if side_effects not in _SIDE_EFFECT_RANK or _SIDE_EFFECT_RANK[side_effects] > _SIDE_EFFECT_RANK[task_rule["max_side_effects"]]:
        _fail("task_side_effects_ineligible", "Requested side effects exceed task policy", "ineligible")
    if execution.get("mode") not in task_rule["allowed_modes"] or execution.get("preferred_lane") not in task_rule["allowed_lanes"]:
        _fail("task_route_ineligible", "Requested mode or lane is ineligible", "ineligible")
    decision = policy["profile_decisions"].get(profile)
    if decision not in {"registered", "registered_read_only_target"}:
        _fail("profile_policy_unavailable", "Requested profile is unavailable by transition policy", "unavailable_profile")
    fact = profile_facts.get(profile) if isinstance(profile_facts, Mapping) else None
    if not isinstance(fact, Mapping) or set(fact) != {"status", "model", "budgets"}:
        _fail("profile_facts_invalid", "Injected profile facts are invalid", "unauthorized")
    if fact["status"] != "available" or not isinstance(fact["model"], str) or not fact["model"]:
        _fail("profile_snapshot_unavailable", "Requested profile is unavailable in the injected snapshot", "unavailable_profile")
    profile_budget = _positive_budgets(fact["budgets"], "profile_budget_invalid")
    caller_budget = _positive_budgets(policy["caller_tiers"][caller_tier]["budgets"], "caller_budget_invalid")
    task_budget = _positive_budgets(task_rule["budgets"], "task_budget_invalid")
    policy_budget = {key: min(caller_budget[key], task_budget[key], profile_budget[key]) for key in _BUDGET_KEYS}
    trusted_l1 = _validate_trusted_l1(trusted)
    trusted_l1["available_profiles"] = {profile: fact["model"]}
    trusted_l1["eligible_task_classes"] = [task_class]
    current_tools = set(trusted_l1["eligible_tools"].get(task_class, []))
    trusted_l1["eligible_tools"] = {task_class: sorted(current_tools & set(task_rule["allowed_tools"]))}
    trusted_l1["policy_budgets"] = policy_budget
    trusted_l1["config_version"] = policy["policy_version"]
    return trusted_l1, dict(task_rule), dict(policy["caller_tiers"][caller_tier])


def build_and_resolve(
    request: Mapping[str, Any],
    trusted: Mapping[str, Any],
    trusted_ingress: Mapping[str, Any],
    profile_facts: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Prepare one shadow request and resolve it through the L1A authority intersection."""
    policy = _validate_policy_shape(policy)
    trusted_l1, _task_rule, caller_rule = _resolve_policy_facts(
        request, trusted, trusted_ingress, profile_facts, policy
    )
    built = copy.deepcopy(dict(request))
    try:
        effective_chars = min(built["context"]["inline_max_chars"], caller_rule["inline_max_chars"])
        prepared = CTX.prepare_context(
            built["context"]["messages"],
            inline_max_chars=effective_chars,
            rule_ids=policy["context"]["redaction_rule_ids"],
            artifact_format=built["artifact"]["format"],
            response_format_supported=trusted_ingress["response_format_supported"],
        )
        built["context"]["messages"] = prepared["messages"]
        built["context"]["summary"] = prepared["summary"]
        built["context"]["inline_max_chars"] = effective_chars
        built["context"]["context_adapter_version"] = policy["context"]["adapter_version"]
        built["context"]["compaction_policy_version"] = policy["context"]["compaction_policy_version"]
        plan = LIC.resolve_request(built, trusted_l1)
    except PolicyError:
        raise
    except CTX.ContextError as exc:
        raise PolicyError(exc.code, exc.reason_code, exc.safe_message) from exc
    except LIC.ContractError as exc:
        raise PolicyError(exc.code, exc.reason_code, exc.safe_message) from exc
    except (KeyError, TypeError) as exc:
        raise PolicyError("invalid_request", "request_shape_invalid", "Request shape is invalid") from exc
    return {"request": built, "resolved_plan": plan, "context_metadata": prepared}


def run_golden_vectors(
    repo_root: Path,
    fixture_path: Path | None = None,
    *,
    full_schema_validation: bool = True,
) -> dict[str, Any]:
    """Run caller-tier shadow parity against pinned canonical plan bytes."""
    policy = load_policy(repo_root, full_schema_validation=full_schema_validation)
    fixture = fixture_path or repo_root / "scripts" / "testing" / "fixtures" / "local-inference-l2a-golden.json"
    document = LIC.parse_json_strict(fixture.read_bytes())
    if not isinstance(document, dict) or set(document) != {
        "contract_version", "policy_version", "vectors", "redaction_vector_count", "compaction_vector_count"
    }:
        _fail("l2a_fixture_shape_invalid", "L2A golden fixture shape is invalid", "malformed_result")
    if document["contract_version"] != "1.0" or document["policy_version"] != policy["policy_version"]:
        _fail("l2a_fixture_version_invalid", "L2A golden fixture version is invalid", "malformed_result")
    l1_document = LIC.parse_json_strict(
        (repo_root / "scripts" / "testing" / "fixtures" / "local-inference-contract-v1-golden.json").read_bytes()
    )
    l1_vectors = {item["id"]: item for item in l1_document["vectors"]}
    request_schema = LIC.parse_json_strict(
        (repo_root / "config" / "schemas" / "local-inference-request.schema.json").read_bytes()
    )
    checked = 0
    for vector in document["vectors"]:
        if set(vector) != {
            "id", "l1_vector_id", "profile", "caller_tiers", "trusted_ingress",
            "profile_facts", "expected_canonical_utf8",
        }:
            _fail("l2a_vector_shape_invalid", "L2A golden vector shape is invalid", "malformed_result")
        base_vector = l1_vectors.get(vector["l1_vector_id"])
        if base_vector is None:
            _fail("l2a_base_vector_missing", "L2A base vector is missing", "malformed_result")
        base_request = LIC.normalize_chat_request(base_vector["chat"])
        observed: list[bytes] = []
        for tier in vector["caller_tiers"]:
            request = build_caller_request(base_request, tier, vector["profile"])
            outcome = build_and_resolve(
                request, base_vector["trusted"], vector["trusted_ingress"][tier],
                vector["profile_facts"], policy,
            )
            if full_schema_validation:
                LIC._validate_with_schema(outcome["request"], request_schema)
            observed.append(LIC.canonical_json_bytes(outcome["resolved_plan"]))
        expected = vector["expected_canonical_utf8"].encode("utf-8")
        if not observed or any(item != expected for item in observed) or len(set(observed)) != 1:
            _fail("l2a_golden_parity_mismatch", "L2A caller-tier parity mismatch", "malformed_result")
        checked += len(observed)
    if checked < 4:
        _fail("l2a_fixture_incomplete", "L2A fixture must cover all caller tiers", "malformed_result")
    digest = hashlib.sha256(
        (repo_root / "config" / "local-inference-policy.json").read_bytes() + fixture.read_bytes()
    ).hexdigest()
    return {
        "caller_tier_parity": "pass", "vector_count": checked, "digest": digest,
        "redaction_vector_count": document["redaction_vector_count"],
        "compaction_vector_count": document["compaction_vector_count"],
    }


def _context_health_vectors(policy: Mapping[str, Any]) -> tuple[int, int]:
    rules = policy["context"]["redaction_rule_ids"]
    samples = [
        "api_key=AQ_SYNTHETIC_VALUE", "Bearer AQ_SYNTHETIC_BEARER_VALUE",
        "-----BEGIN PRIVATE KEY-----\nAQ_SYNTHETIC\n-----END PRIVATE KEY-----",
        "operator@example.invalid",
    ]
    redactions = 0
    for sample in samples:
        result = CTX.prepare_context(
            [{"role": "user", "content": sample, "call_id": None}], inline_max_chars=1000, rule_ids=rules
        )
        if sample in result["messages"][0]["content"] or not result["redactions"]:
            _fail("redaction_health_failed", "Redaction health vector failed", "malformed_result")
        redactions += 1
    messages = [
        {"role": "system", "content": "system", "call_id": None},
        {"role": "user", "content": "old " * 30, "call_id": None},
        {"role": "assistant", "content": "call", "call_id": "call-1"},
        {"role": "tool", "content": "result", "call_id": "call-1"},
        {"role": "user", "content": "newest", "call_id": None},
    ]
    first = CTX.prepare_context(messages, inline_max_chars=120, rule_ids=rules)
    second = CTX.prepare_context(messages, inline_max_chars=120, rule_ids=rules)
    if first != second or first["compacted_count"] < 1:
        _fail("compaction_health_failed", "Compaction determinism vector failed", "malformed_result")
    unicode_a = CTX.prepare_context(
        [{"role": "user", "content": "e\u0301", "call_id": None}], inline_max_chars=20, rule_ids=rules
    )
    unicode_b = CTX.prepare_context(
        [{"role": "user", "content": "é", "call_id": None}], inline_max_chars=20, rule_ids=rules
    )
    if unicode_a["context_digest"] != unicode_b["context_digest"]:
        _fail("compaction_unicode_failed", "Unicode compaction vector failed", "malformed_result")
    if not any(item["call_id"] == "call-1" for item in first["messages"]):
        _fail("compaction_pair_failed", "Tool-pair preservation vector failed", "malformed_result")
    return redactions, 3


def policy_health(repo_root: Path, fixture_path: Path | None = None) -> dict[str, Any]:
    """Return bounded shadow health without prompts, secrets, regexes, or exception text."""
    health: dict[str, Any] = {
        "status": "unavailable", "mode": "shadow_fixture_only", "policy_version": "unknown",
        "schema_status": "unavailable", "caller_tier_parity": "unavailable", "vector_count": 0,
        "context_adapter_version": "unknown", "compaction_policy_version": "unknown",
        "redaction_vector_count": 0, "compaction_vector_count": 0,
        "profile_decisions": copy.deepcopy(_PROFILE_DECISIONS), "digest": None,
        "freshness": "commit_fixture", "reason_code": "policy_assets_missing",
    }
    try:
        policy = load_policy(repo_root, full_schema_validation=True)
        health.update({
            "policy_version": policy["policy_version"], "schema_status": "valid",
            "context_adapter_version": policy["context"]["adapter_version"],
            "compaction_policy_version": policy["context"]["compaction_policy_version"],
            "profile_decisions": copy.deepcopy(policy["profile_decisions"]),
        })
        parity = run_golden_vectors(repo_root, fixture_path, full_schema_validation=False)
        redactions, compactions = _context_health_vectors(policy)
        if parity["redaction_vector_count"] != redactions or parity["compaction_vector_count"] != compactions:
            _fail("l2a_fixture_count_mismatch", "Context vector counts do not match evidence", "malformed_result")
        health.update(parity)
        health["status"] = "healthy"
        health["reason_code"] = "policy_fixture_parity_pass"
    except FileNotFoundError:
        health["reason_code"] = "policy_fixture_missing"
    except PolicyError as exc:
        health["status"] = "degraded"
        health["schema_status"] = "invalid" if "policy" in exc.reason_code else health["schema_status"]
        health["caller_tier_parity"] = "fail"
        health["reason_code"] = "policy_schema_invalid" if health["schema_status"] == "invalid" else "policy_fixture_invalid"
    except Exception:
        health["status"] = "degraded"
        health["caller_tier_parity"] = "fail"
        health["reason_code"] = "policy_fixture_invalid"
    return health


__all__ = [
    "PolicyError", "build_and_resolve", "build_caller_request", "load_policy",
    "policy_health", "run_golden_vectors",
]
