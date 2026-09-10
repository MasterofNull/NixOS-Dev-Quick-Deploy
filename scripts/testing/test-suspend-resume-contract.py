#!/usr/bin/env python3
"""Deterministically validate the AQ-OS suspend/resume workload contract."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = ROOT / "config/suspend-resume-workloads.json"
ALLOWED_CLASSES = {"managed-daemon", "resumable-job"}
ALLOWED_STATUS = {"implemented", "partial", "planned", "not_implemented"}
ALLOWED_COMPLIANCE = {"compliant", "partial", "blocked"}
TOP_LEVEL_FIELDS = {"schema_version", "policy", "workloads"}
WORKLOAD_FIELDS = {
    "id",
    "workload_class",
    "implementation_paths",
    "suspend_behavior",
    "state_safety",
    "readiness",
    "resume_outcomes",
    "observability",
    "compliance",
    "next_slice",
}


def nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_static_evidence(workloads: dict[str, dict], errors: list[str]) -> None:
    llama = workloads.get("llama-cpp-inference", {})
    if llama:
        nix_text = (ROOT / "nix/modules/roles/ai-stack.nix").read_text(encoding="utf-8")
        dispatch_text = (ROOT / "scripts/ai/lib/dispatch.py").read_text(encoding="utf-8")
        if (
            "systemd.services.llama-cpp-resume" not in nix_text
            or "restart --no-block llama-cpp.service" not in nix_text
        ):
            errors.append("llama-cpp-inference lacks its declared resume hook")
        if (
            "def _wait_for_service" not in dispatch_text
            or 'AQ_SERVICE_WAIT_S", "180"' not in dispatch_text
        ):
            errors.append("llama-cpp-inference lacks its declared 180s readiness wait")

    training = workloads.get("local-training-loop", {})
    if training:
        text = (ROOT / "scripts/ai/aq-local-training-loop").read_text(encoding="utf-8")
        if "SIGHUP" not in text or "SIGTERM" not in text:
            errors.append("local-training-loop lacks declared signal handling")

    dogfood = workloads.get("local-dogfood-run", {})
    behavior = dogfood.get("suspend_behavior", {}) if isinstance(dogfood, dict) else {}
    if behavior.get("implementation_status") != "not_implemented":
        errors.append("local-dogfood-run must remain not_implemented until SR-4")


def validate_payload(payload: object, *, static_evidence: bool = True) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["contract must be an object"]
    unknown_top = set(payload) - TOP_LEVEL_FIELDS
    if unknown_top:
        errors.append(f"unknown top-level field(s): {', '.join(sorted(unknown_top))}")
    if payload.get("schema_version") != "1.0":
        errors.append("schema_version must be 1.0")

    policy = payload.get("policy")
    if not isinstance(policy, dict):
        errors.append("policy must be an object")
    else:
        for field in ("purpose", "scope", "registration_rule"):
            if not nonempty_string(policy.get(field)):
                errors.append(f"policy.{field} must be a non-empty string")
        evidence = policy.get("required_evidence")
        required = {
            "bounded readiness or reconciliation",
            "typed resume outcome",
            "telemetry, dashboard, and QA evidence",
        }
        if not isinstance(evidence, list) or not required.issubset(set(evidence)):
            errors.append("policy.required_evidence omits a required evidence class")

    records = payload.get("workloads")
    if not isinstance(records, list) or not records:
        errors.append("workloads must be a non-empty list")
        records = []

    indexed: dict[str, dict] = {}
    for index, record in enumerate(records):
        prefix = f"workloads[{index}]"
        if not isinstance(record, dict):
            errors.append(f"{prefix} must be an object")
            continue
        missing = WORKLOAD_FIELDS - set(record)
        unknown = set(record) - WORKLOAD_FIELDS
        if missing:
            errors.append(f"{prefix} missing fields: {', '.join(sorted(missing))}")
        if unknown:
            errors.append(f"{prefix} unknown fields: {', '.join(sorted(unknown))}")
        if missing:
            continue

        workload_id = record.get("id")
        if not nonempty_string(workload_id):
            errors.append(f"{prefix}.id must be a non-empty string")
            continue
        if workload_id in indexed:
            errors.append(f"duplicate workload id: {workload_id}")
        indexed[workload_id] = record

        if record.get("workload_class") not in ALLOWED_CLASSES:
            errors.append(f"{workload_id}.workload_class is not allowed")
        paths = record.get("implementation_paths")
        if not isinstance(paths, list) or not paths:
            errors.append(f"{workload_id}.implementation_paths must be non-empty")
        else:
            for relpath in paths:
                if not nonempty_string(relpath) or not (ROOT / str(relpath)).is_file():
                    errors.append(f"{workload_id} references missing file: {relpath}")

        behavior = record.get("suspend_behavior")
        if not isinstance(behavior, dict):
            errors.append(f"{workload_id}.suspend_behavior must be an object")
            behavior_status = None
        else:
            if not all(nonempty_string(behavior.get(key)) for key in ("mode", "resume_trigger")):
                errors.append(f"{workload_id}.suspend_behavior lacks mode/resume_trigger")
            behavior_status = behavior.get("implementation_status")
            if behavior_status not in ALLOWED_STATUS:
                errors.append(f"{workload_id}.suspend_behavior status is not allowed")

        safety = record.get("state_safety")
        if (
            not isinstance(safety, dict)
            or not isinstance(safety.get("checkpoint_required"), bool)
            or not all(nonempty_string(safety.get(key)) for key in ("idempotency", "signal_behavior"))
        ):
            errors.append(f"{workload_id}.state_safety is incomplete")

        readiness = record.get("readiness")
        if not isinstance(readiness, dict):
            errors.append(f"{workload_id}.readiness must be an object")
            readiness_status = None
        else:
            readiness_status = readiness.get("implementation_status")
            if (
                not all(nonempty_string(readiness.get(key)) for key in ("strategy", "evidence"))
                or not isinstance(readiness.get("max_wait_seconds"), int)
                or readiness.get("max_wait_seconds", 0) <= 0
                or readiness_status not in ALLOWED_STATUS
            ):
                errors.append(f"{workload_id}.readiness is not bounded and valid")

        outcomes = record.get("resume_outcomes")
        if not isinstance(outcomes, dict):
            errors.append(f"{workload_id}.resume_outcomes must be an object")
            outcome_status = None
        else:
            required_outcomes = outcomes.get("required")
            outcome_status = outcomes.get("implementation_status")
            if (
                not isinstance(required_outcomes, list)
                or len(required_outcomes) < 3
                or not all(nonempty_string(item) for item in required_outcomes)
                or outcome_status not in ALLOWED_STATUS
            ):
                errors.append(f"{workload_id}.resume_outcomes is incomplete")

        observability = record.get("observability")
        if not isinstance(observability, dict):
            errors.append(f"{workload_id}.observability must be an object")
            observable_statuses: list[object] = []
        else:
            observable_statuses = [observability.get(key) for key in ("telemetry", "dashboard", "qa")]
            if any(status not in ALLOWED_STATUS for status in observable_statuses):
                errors.append(f"{workload_id}.observability status is not allowed")

        compliance = record.get("compliance")
        if compliance not in ALLOWED_COMPLIANCE:
            errors.append(f"{workload_id}.compliance is not allowed")
        evidence_statuses = [behavior_status, readiness_status, outcome_status, *observable_statuses]
        if compliance == "compliant" and any(status != "implemented" for status in evidence_statuses):
            errors.append(f"{workload_id}.compliant requires every evidence area implemented")
        if compliance == "blocked" and "not_implemented" not in evidence_statuses:
            errors.append(f"{workload_id}.blocked requires a not_implemented evidence area")
        if not nonempty_string(record.get("next_slice")):
            errors.append(f"{workload_id}.next_slice must be non-empty")

    expected = {"llama-cpp-inference", "local-training-loop", "local-dogfood-run"}
    missing_known = expected - set(indexed)
    if missing_known:
        errors.append(f"missing known workload(s): {', '.join(sorted(missing_known))}")
    if indexed.get("llama-cpp-inference", {}).get("compliance") != "partial":
        errors.append("llama-cpp-inference must remain partial until SR-3")
    if static_evidence and not missing_known:
        validate_static_evidence(indexed, errors)
    return errors


def run_adversarial_tests(payload: dict) -> int:
    cases = {
        "compliant-with-gaps": lambda doc: doc["workloads"][0].update(compliance="compliant"),
        "blocked-without-gap": lambda doc: doc["workloads"][0].update(compliance="blocked"),
        "unknown-top-level": lambda doc: doc.update(unexpected=True),
        "unknown-workload-field": lambda doc: doc["workloads"][0].update(unexpected=True),
    }
    failures = []
    for name, mutate in cases.items():
        candidate = copy.deepcopy(payload)
        mutate(candidate)
        if not validate_payload(candidate, static_evidence=False):
            failures.append(name)
    if failures:
        print(f"ERROR: adversarial cases passed: {', '.join(failures)}", file=sys.stderr)
        return 1
    print(f"PASS: {len(cases)} adversarial suspend/resume cases fail closed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--require-workload-id", action="append", default=[])
    args = parser.parse_args()
    try:
        payload = json.loads(args.contract.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: invalid suspend/resume contract: {exc}", file=sys.stderr)
        return 1
    if args.self_test:
        return run_adversarial_tests(payload)
    errors = validate_payload(payload)
    records = payload.get("workloads", []) if isinstance(payload, dict) else []
    registered_ids = {
        record.get("id")
        for record in records
        if isinstance(record, dict) and nonempty_string(record.get("id"))
    }
    for required_id in args.require_workload_id:
        if required_id not in registered_ids:
            errors.append(
                f"AQ_SUSPEND_CONTRACT marker has no matching workload record: {required_id}"
            )
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"PASS: suspend/resume contract valid for {len(payload['workloads'])} workloads")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
