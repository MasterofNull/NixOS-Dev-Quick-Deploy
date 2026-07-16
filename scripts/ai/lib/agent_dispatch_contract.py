#!/usr/bin/env python3
"""Pure C0 contract model for durable agent dispatch.

No live registry, process, socket, provider, filesystem mutation, or network operation is performed.
All facts and policy are injected by callers.
"""
from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator


CONTRACT_VERSION = "aq.dispatch.contract.v1"
TERMINAL_STATES = frozenset({"cancelled", "done", "failed", "stale"})
FORBIDDEN_KEYS = frozenset({
    "argv", "cmdline", "command", "credentials", "environment", "headers", "output",
    "path", "prompt", "prompt_digest", "raw_error", "secret", "token",
})


class ContractError(ValueError):
    """A stable, fail-closed contract violation."""


def canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def assert_private(value: Any) -> None:
    """Reject lifecycle data containing prohibited sensitive surfaces."""
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                raise ContractError("privacy_field_forbidden")
            assert_private(child)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for child in value:
            assert_private(child)


def validate_document(value: Mapping[str, Any], schema: Mapping[str, Any], *, max_bytes: int) -> None:
    if len(canonical_bytes(value)) > max_bytes:
        raise ContractError("envelope_too_large")
    assert_private(value)
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda item: list(item.path))
    if errors:
        raise ContractError("schema_invalid")


def validate_policy(policy: Mapping[str, Any], schema: Mapping[str, Any]) -> None:
    validate_document(policy, schema, max_bytes=262144)
    states = set(policy["transitions"])
    if states != {"submitted", "queued", "starting", "running", "waiting", "parked", "cancelling", "cancelled", "done", "failed", "stale"}:
        raise ContractError("policy_state_set_invalid")
    for source, targets in policy["transitions"].items():
        if not set(targets).issubset(states) or (source in TERMINAL_STATES and targets):
            raise ContractError("policy_transition_invalid")


def initial_status(request: Mapping[str, Any], *, task_id: str, fencing_epoch: int) -> dict[str, Any]:
    if fencing_epoch < 1:
        raise ContractError("fencing_epoch_invalid")
    return {
        "schema_version": "aq.dispatch.status.v1",
        "task_id": task_id,
        "revision": 0,
        "fencing_epoch": fencing_epoch,
        "state": "queued",
        "adapter": request["lane"],
        "lease_owner": None,
        "attempt": 0,
        "earliest_resume_epoch": None,
        "reason": None,
    }


def admit_request(request: Mapping[str, Any], existing: Mapping[str, Mapping[str, Any]], *, task_id: str,
                  fencing_epoch: int) -> tuple[dict[str, Any], bool]:
    """Return the original status for a duplicate key; never imply a second start."""
    key = request["idempotency_key"]
    if key in existing:
        return deepcopy(dict(existing[key])), False
    return initial_status(request, task_id=task_id, fencing_epoch=fencing_epoch), True


def authorize_start(status: Mapping[str, Any], policy: Mapping[str, Any], *, expected_revision: int,
                    expected_fencing_epoch: int, lease_owner: str) -> tuple[dict[str, Any], bool]:
    """Issue exactly one start grant under CAS/fence/lease ownership."""
    if status["attempt"] >= policy["limits"]["max_attempts"]:
        raise ContractError("attempt_budget_exhausted")
    updated = transition_status(
        status, "starting", policy,
        expected_revision=expected_revision,
        expected_fencing_epoch=expected_fencing_epoch,
        expected_lease_owner=None,
        lease_owner=lease_owner,
    )
    return updated, True


def transition_status(status: Mapping[str, Any], target: str, policy: Mapping[str, Any], *,
                      expected_revision: int, expected_fencing_epoch: int,
                      expected_lease_owner: str | None, lease_owner: str | None = None,
                      reason: str | None = None, earliest_resume_epoch: int | None = None) -> dict[str, Any]:
    current = dict(status)
    if current["revision"] != expected_revision:
        raise ContractError("cas_revision_mismatch")
    if current["fencing_epoch"] != expected_fencing_epoch:
        raise ContractError("fencing_epoch_mismatch")
    if current.get("lease_owner") != expected_lease_owner:
        raise ContractError("lease_ownership_mismatch")
    if current["state"] in TERMINAL_STATES:
        if target == current["state"] and reason == current.get("reason"):
            return current
        raise ContractError("terminal_transition_forbidden")
    if target not in policy["transitions"].get(current["state"], []):
        raise ContractError("state_transition_forbidden")
    if target == "parked" and (reason != "quota_parked" or earliest_resume_epoch is None):
        raise ContractError("park_evidence_required")
    if target != "parked" and earliest_resume_epoch is not None:
        raise ContractError("resume_epoch_forbidden")
    result = deepcopy(current)
    result.update(
        revision=current["revision"] + 1,
        state=target,
        lease_owner=lease_owner,
        reason=reason,
        earliest_resume_epoch=earliest_resume_epoch,
    )
    if target == "starting":
        result["attempt"] = current["attempt"] + 1
    return result


def classify_failure(reason: str, retry_after_seconds: int | None, policy: Mapping[str, Any]) -> dict[str, Any]:
    limits = policy["limits"]
    if reason in policy["retry"]["transient_reasons"]:
        delay = 1 if retry_after_seconds is None else retry_after_seconds
        if not 0 <= delay <= limits["max_retry_seconds"]:
            raise ContractError("retry_delay_invalid")
        return {"disposition": "retry", "next_state": "queued", "retry_after_seconds": delay}
    if reason in policy["retry"]["park_reasons"]:
        if retry_after_seconds is None or not limits["max_retry_seconds"] < retry_after_seconds <= limits["max_park_seconds"]:
            raise ContractError("park_delay_invalid")
        return {"disposition": "park", "next_state": "parked", "retry_after_seconds": retry_after_seconds}
    if reason in policy["retry"]["terminal_reasons"]:
        state = "cancelled" if reason == "cancelled" else ("stale" if reason == "executor_lost" else "failed")
        return {"disposition": "terminal", "next_state": state, "retry_after_seconds": None}
    raise ContractError("reason_unknown")


def reconcile_uncertain(status: Mapping[str, Any], *, executor_proven_terminal: bool,
                        expected_revision: int, expected_fencing_epoch: int,
                        expected_lease_owner: str | None, policy: Mapping[str, Any]) -> dict[str, Any]:
    """Uncertain restart evidence closes stale; it never authorizes automatic respawn."""
    if status["state"] in TERMINAL_STATES:
        return dict(status)
    target = "failed" if executor_proven_terminal else "stale"
    reason = "output_incomplete" if executor_proven_terminal else "executor_lost"
    return transition_status(
        status, target, policy,
        expected_revision=expected_revision,
        expected_fencing_epoch=expected_fencing_epoch,
        expected_lease_owner=expected_lease_owner,
        lease_owner=None,
        reason=reason,
    )


def contract_health(policy: Mapping[str, Any], adapters: Sequence[Mapping[str, Any]],
                    coverage: Mapping[str, bool]) -> dict[str, Any]:
    required_caps = set(policy["required_capabilities"])
    declared = {item.get("adapter"): set(item.get("capabilities", [])) for item in adapters}
    adapter_health = {
        lane: "healthy" if lane in declared and required_caps.issubset(declared[lane]) else "blocked"
        for lane in policy["adapters"]
    }
    gate_health = {gate: "healthy" if coverage.get(gate) is True else "blocked" for gate in policy["coverage_gates"]}
    verdict = "healthy" if all(value == "healthy" for value in (*adapter_health.values(), *gate_health.values())) else "blocked"
    return {
        "contract_version": policy["contract_version"],
        "verdict": verdict,
        "adapter_health": adapter_health,
        "coverage_health": gate_health,
    }
