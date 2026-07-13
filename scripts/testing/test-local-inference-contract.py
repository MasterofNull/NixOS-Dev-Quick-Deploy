#!/usr/bin/env python3
"""Focused L1A contract, resolver, parity, QA, and dashboard health checks."""

from __future__ import annotations

import copy
import importlib.util
import json
import math
import sys
import tempfile
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "scripts/ai/lib/local_inference_contract.py"
FIXTURE = ROOT / "scripts/testing/fixtures/local-inference-contract-v1-golden.json"
SCHEMA_DIR = ROOT / "config/schemas"
FAILURES: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        FAILURES.append(message)


def load_contract():
    spec = importlib.util.spec_from_file_location("l1a_contract_test", LIB)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


LIC = load_contract()


def fixture() -> dict:
    return LIC.parse_json_strict(FIXTURE.read_bytes())


def base() -> tuple[dict, dict, dict]:
    vector = fixture()["vectors"][0]
    return LIC.normalize_chat_request(vector["chat"]), copy.deepcopy(vector["trusted"]), vector


def expect_reason(fn, reason: str, label: str) -> None:
    try:
        fn()
        FAILURES.append(f"{label}: expected {reason}")
    except LIC.ContractError as exc:
        check(exc.reason_code == reason, f"{label}: expected {reason}, got {exc.reason_code}")


def test_schema_contracts() -> None:
    schemas = {}
    for name in ("request", "result", "event", "error"):
        schema = LIC.parse_json_strict((SCHEMA_DIR / f"local-inference-{name}.schema.json").read_bytes())
        jsonschema.Draft202012Validator.check_schema(schema)
        LIC._schema_is_offline_strict(schema)
        schemas[name] = schema
    request, _, _ = base()
    jsonschema.Draft202012Validator(schemas["request"], format_checker=jsonschema.FormatChecker()).validate(request)
    bad = copy.deepcopy(request)
    bad["request_id"] = "not-a-uuid"
    expect_reason(
        lambda: LIC._validate_with_schema(bad, schemas["request"]),
        "schema_validation_failed",
        "UUID format",
    )
    bad = copy.deepcopy(request)
    bad["requester"]["ambient_admin"] = True
    expect_reason(
        lambda: LIC._validate_with_schema(bad, schemas["request"]),
        "schema_validation_failed",
        "unknown nested field",
    )


def test_terminal_conditionals() -> None:
    plan = json.loads(fixture()["vectors"][0]["expected_canonical_utf8"])
    digest = "a" * 64
    result = {
        "contract_version": "1.0", "request_id": "11111111-1111-4111-8111-111111111111",
        "run_id": "55555555-5555-4555-8555-555555555555", "trace_id": "22222222-2222-4222-8222-222222222222",
        "session_id": None, "sequence": 1, "status": "complete", "resolved_plan": plan,
        "artifact": {"format": "text", "content": "ok", "schema_valid": True}, "claims": [],
        "validation": {"results": [], "missing_evidence": []},
        "effects": {"changed_files": [], "executed_tools": []},
        "usage": {"input_tokens": 1, "output_tokens": 1, "tool_calls": 0},
        "timing": {"queue_ms": 0, "ttft_ms": 1, "inference_ms": 1, "total_ms": 2},
        "provenance": {"producer": "fixture", "template_version": "v1", "context_digest": digest, "input_digest": digest, "output_digest": digest},
        "error": None, "limitations": [], "next_action": "none",
    }
    result_schema = json.loads((SCHEMA_DIR / "local-inference-result.schema.json").read_text())
    jsonschema.Draft202012Validator(result_schema, format_checker=jsonschema.FormatChecker()).validate(result)
    bad_result = {**result, "status": "failed"}
    check(not jsonschema.Draft202012Validator(result_schema).is_valid(bad_result), "failed result accepted null error")
    error = {
        "contract_version": "1.0", "code": "cancelled", "message": "cancelled",
        "retryable": False, "reason_code": "operator_cancelled", "evidence_ref": None,
    }
    failed_cancelled = {**result, "status": "failed", "error": error}
    check(not jsonschema.Draft202012Validator(result_schema).is_valid(failed_cancelled),
          "failed result accepted cancelled error code")
    event_schema = json.loads((SCHEMA_DIR / "local-inference-event.schema.json").read_text())
    event = {
        "contract_version": "1.0", "request_id": result["request_id"], "run_id": result["run_id"],
        "trace_id": result["trace_id"], "sequence": 1, "event_type": "completed", "terminal": True,
        "payload": {"content_delta": None, "usage_delta": {"input_tokens": 0, "output_tokens": 0}, "tool": None, "validation_check": None},
        "error": None,
    }
    jsonschema.Draft202012Validator(event_schema, format_checker=jsonschema.FormatChecker()).validate(event)
    check(not jsonschema.Draft202012Validator(event_schema).is_valid({**event, "terminal": False}),
          "completed event accepted terminal=false")
    failed_event = {**event, "event_type": "failed", "error": error}
    check(not jsonschema.Draft202012Validator(event_schema).is_valid(failed_event),
          "failed event accepted cancelled error code")
    error_schema = json.loads((SCHEMA_DIR / "local-inference-error.schema.json").read_text())
    cancelled = {
        "contract_version": "1.0", "code": "cancelled", "message": "cancelled",
        "retryable": True, "reason_code": "operator_cancelled", "evidence_ref": None,
    }
    check(not jsonschema.Draft202012Validator(error_schema).is_valid(cancelled),
          "cancelled error accepted retryable=true")
    invalid_request = {**cancelled, "code": "invalid_request", "retryable": True}
    check(not jsonschema.Draft202012Validator(error_schema).is_valid(invalid_request),
          "invalid_request error accepted retryable=true")


def test_canonical_json_guards() -> None:
    expect_reason(lambda: LIC.parse_json_strict('{"a":1,"a":2}'), "duplicate_json_key", "duplicate JSON")
    expect_reason(lambda: LIC.parse_json_strict('{"a":NaN}'), "non_finite_number", "non-finite JSON")
    expect_reason(lambda: LIC.canonical_json_bytes({"a": math.inf}), "non_finite_number", "non-finite canonical")
    check(LIC.canonical_json_bytes({"é": "e\u0301"}) == '{"é":"é"}'.encode(), "NFC canonical bytes drift")


def test_golden_parity_and_mutation() -> None:
    outcome = LIC.run_golden_vectors(ROOT)
    check(outcome["parity_status"] == "pass" and outcome["vector_count"] == 1, "golden parity did not pass")
    mutated = fixture()
    check(set(mutated["vectors"][0]["chat"]) != set(mutated["vectors"][0]["delegate"]),
          "chat/delegate fixture shapes are not distinct")
    mutated["vectors"][0]["chat"]["route"]["mode"] = "direct"
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "mutated.json"
        path.write_text(json.dumps(mutated), encoding="utf-8")
        expect_reason(lambda: LIC.run_golden_vectors(ROOT, path), "golden_parity_mismatch", "chat mutation")
    mutated = fixture()
    mutated["vectors"][0]["delegate"]["dispatch"]["execution_mode"] = "direct"
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "mutated-delegate.json"
        path.write_text(json.dumps(mutated), encoding="utf-8")
        expect_reason(lambda: LIC.run_golden_vectors(ROOT, path), "golden_parity_mismatch", "delegate mutation")


def test_trusted_authority_intersection() -> None:
    request, trusted, _ = base()
    plan = LIC.resolve_request(request, trusted)
    check(plan["effective_role"] == "implementer", "unassigned trusted role did not use implementer constraints")
    check(plan["tools"] == ["read_file", "rg"], "trusted tool intersection drift")
    forged_role = copy.deepcopy(request)
    forged_role["requester"]["requested_role"] = "orchestrator"
    check(LIC.resolve_request(forged_role, trusted)["effective_role"] == "implementer",
          "requested orchestrator role self-granted authority")
    high = copy.deepcopy(request)
    high["budget"]["priority"] = "interactive"
    expect_reason(lambda: LIC.resolve_request(high, trusted), "priority_exceeds_ceiling", "forged priority")
    unavailable = copy.deepcopy(request)
    unavailable["execution"]["requested_profile"] = "default"
    expect_reason(lambda: LIC.resolve_request(unavailable, trusted), "requested_profile_unavailable", "implicit default")
    escaped = copy.deepcopy(trusted)
    escaped["resolved_paths"]["src/app.py"] = "/outside/app.py"
    expect_reason(lambda: LIC.resolve_request(request, escaped), "canonical_path_escape", "injected path escape")
    invalid_budget = copy.deepcopy(request)
    invalid_budget["budget"]["output_tokens"] = 0
    expect_reason(lambda: LIC.resolve_request(invalid_budget, trusted), "budget_invalid", "invalid budget")
    contradictory_effects = copy.deepcopy(request)
    contradictory_effects["execution"]["side_effects"] = "none"
    expect_reason(
        lambda: LIC.resolve_request(contradictory_effects, trusted),
        "side_effect_tool_mismatch",
        "side-effect/tool contradiction",
    )


def test_forged_grants_and_lease_scope() -> None:
    request, trusted, _ = base()
    write = copy.deepcopy(request)
    write["execution"].update({"side_effects": "write", "approval_ref": "forged"})
    write["execution"]["tool_lease"] = {
        "lease_id": "forged", "expires_at": "2026-07-14T00:00:00Z", "repo_root": "/repo",
        "cwd": "", "path_globs": ["src/*"], "command_prefixes": [],
    }
    expect_reason(lambda: LIC.resolve_request(write, trusted), "approval_unverified", "forged approval")
    missing = copy.deepcopy(write)
    missing["execution"]["approval_ref"] = None
    missing["execution"]["tool_lease"] = {
        "lease_id": None, "expires_at": None, "repo_root": "/", "cwd": "",
        "path_globs": [], "command_prefixes": [],
    }
    expect_reason(lambda: LIC.resolve_request(missing, trusted), "write_authority_missing", "missing write grants")
    lease_request = copy.deepcopy(request)
    lease_request["execution"]["tool_lease"] = copy.deepcopy(write["execution"]["tool_lease"])
    expect_reason(lambda: LIC.resolve_request(lease_request, trusted), "lease_unverified", "forged lease")
    issued = {
        "lease_id": "lease-1", "expires_at": "2026-07-14T00:00:00Z", "repo_root": "/repo",
        "cwd": "", "path_globs": ["src/*"], "command_prefixes": [], "tools": ["read_file", "rg"],
    }
    scoped = copy.deepcopy(request)
    scoped["execution"]["tool_lease"] = {
        "lease_id": "lease-1", "expires_at": issued["expires_at"], "repo_root": "/repo",
        "cwd": "", "path_globs": ["**"], "command_prefixes": [],
    }
    trusted_scoped = copy.deepcopy(trusted)
    trusted_scoped["authority_leases"] = [issued]
    expect_reason(lambda: LIC.resolve_request(scoped, trusted_scoped), "lease_scope_widening", "lease widening")
    issued["expires_at"] = "2026-07-12T00:00:00Z"
    scoped["execution"]["tool_lease"].update({"expires_at": issued["expires_at"], "path_globs": ["src/*"]})
    expect_reason(lambda: LIC.resolve_request(scoped, trusted_scoped), "lease_expired", "expired lease")


def test_health_fail_closed() -> None:
    health = LIC.contract_health(ROOT)
    check(health["status"] == "healthy" and health["parity_status"] == "pass", "contract health not healthy")
    check(set(health["schemas"].values()) == {"structural_valid"}, "runtime schema status not dependency-light")
    with tempfile.TemporaryDirectory() as td:
        missing = LIC.contract_health(ROOT, Path(td) / "missing.json")
        check(missing["status"] == "unavailable" and missing["reason_code"] == "contract_fixture_missing",
              "missing fixture did not fail unavailable")
        malformed_path = Path(td) / "bad.json"
        malformed_path.write_text("not json", encoding="utf-8")
        malformed = LIC.contract_health(ROOT, malformed_path)
        check(malformed["status"] == "degraded" and malformed["parity_status"] == "fail",
              "malformed fixture did not fail degraded")


def test_dashboard_and_qa_wiring() -> None:
    backend = ROOT / "dashboard/backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    from api.routes import aistack
    aistack._LOCAL_INFERENCE_CONTRACT_MODULE = None
    health = aistack._local_inference_contract_health()
    check(health["status"] == "healthy" and health["mode"] == "fixture_only", "backend health projection failed")
    class Invalid:
        @staticmethod
        def contract_health(_root):
            return {"status": "healthy"}
    aistack._LOCAL_INFERENCE_CONTRACT_MODULE = Invalid()
    degraded = aistack._local_inference_contract_health()
    check(degraded["status"] == "degraded" and degraded["reason_code"] == "invalid_health_projection",
          "backend accepted malformed health projection")
    class InventedHealthy:
        @staticmethod
        def contract_health(_root):
            return {
                "status": "healthy", "contract_version": "1.0", "schemas": {},
                "parity_status": "pass", "vector_count": 0, "digest": None,
                "reason_code": "attacker_supplied_reason",
            }
    aistack._LOCAL_INFERENCE_CONTRACT_MODULE = InventedHealthy()
    invented = aistack._local_inference_contract_health()
    check(invented["status"] == "degraded" and invented["reason_code"] == "invalid_health_projection",
          "backend accepted invented healthy projection")
    js = (ROOT / "assets/dashboard.js").read_text(encoding="utf-8")
    check("local_inference_contract" in js and '"· parity"' in js and '"· vectors"' in js,
          "dashboard contract health rows missing")
    phase0 = (ROOT / "scripts/testing/harness_qa/phases/phase0.py").read_text(encoding="utf-8")
    bash = (ROOT / "scripts/ai/_aq-qa-bash").read_text(encoding="utf-8")
    backend_src = (ROOT / "dashboard/backend/api/routes/aistack.py").read_text(encoding="utf-8")
    check('"local_inference_contract": _local_inference_contract_health()' in backend_src,
          "harness overview does not attach contract health")
    check('"0.10.37"' in phase0 and '"0.10.37"' in bash, "dual QA ID 0.10.37 missing")
    registry = json.loads((ROOT / "config/validation-check-registry.json").read_text())
    entry = next((item for item in registry["checks"] if item.get("id") == "local-inference-contract-l1a"), None)
    required_triggers = {
        "config/schemas/local-inference-request.schema.json", "config/schemas/local-inference-result.schema.json",
        "config/schemas/local-inference-event.schema.json", "config/schemas/local-inference-error.schema.json",
        "scripts/ai/lib/local_inference_contract.py",
        "scripts/testing/fixtures/local-inference-contract-v1-golden.json",
        "scripts/testing/test-local-inference-contract.py", "scripts/testing/harness_qa/phases/phase0.py",
        "scripts/ai/_aq-qa-bash", "config/validation-check-registry.json",
        "dashboard/backend/api/routes/aistack.py", "assets/dashboard.js",
    }
    check(bool(entry) and required_triggers.issubset(set(entry["trigger_paths"])),
          "focused CI contract triggers omit an authorized behavior surface")


def main() -> int:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    for test in tests:
        try:
            test()
        except Exception as exc:  # noqa: BLE001
            FAILURES.append(f"{test.__name__} raised {type(exc).__name__}: {exc}")
    if FAILURES:
        print(f"FAIL ({len(FAILURES)}):")
        for failure in FAILURES:
            print(f"  - {failure}")
        return 1
    print(f"PASS: {len(tests)} local-inference L1A contract checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
