#!/usr/bin/env python3
"""Offline focused tests for the B2-C1 pure workflow-shadow contracts."""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts/ai/lib/workflow_shadow_contract.py"
SCHEMA_PATH = ROOT / "config/schemas/workflow-shadow-contracts.schema.json"
REGISTRY_PATH = ROOT / "config/workflow-shadow-phase-tokens.json"
FIXTURE_PATH = ROOT / "scripts/testing/fixtures/workflow-shadow-contract-v1-golden.json"
BLUEPRINT_PATH = ROOT / "config/workflow-blueprints.json"
FAILURES: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        FAILURES.append(message)


def load_module():
    spec = importlib.util.spec_from_file_location("b2_c1_contract_test", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


WSC = load_module()
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
REGISTRY = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
GOLDEN = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
VALIDATOR = jsonschema.Draft202012Validator(SCHEMA, format_checker=jsonschema.FormatChecker())


def expect_reason(call, reason: str, label: str) -> str:
    try:
        call()
        FAILURES.append(f"{label}: expected rejection")
        return ""
    except WSC.ContractError as exc:
        check(exc.reason == reason, f"{label}: expected {reason}, got {exc.reason}")
        return str(exc)


def test_schema_closure_and_versions() -> None:
    jsonschema.Draft202012Validator.check_schema(SCHEMA)
    definitions = SCHEMA["$defs"]
    for name in ("event", "snapshot", "immutable_outbox", "delivery_control", "health"):
        check(definitions[name].get("additionalProperties") is False, f"{name} schema is open")
    check(definitions["health"]["properties"]["counts"].get("additionalProperties") is False,
          "health counts object is open")
    check(definitions["health"]["properties"]["coverage"].get("additionalProperties") is False,
          "health coverage object is open")
    mapped = WSC.map_receipt(GOLDEN["base_receipt"], REGISTRY)
    check(mapped == GOLDEN["expected_contracts"], "mapped contracts drift from golden")
    for kind, contract in mapped.items():
        errors = list(VALIDATOR.iter_errors(contract))
        check(not errors, f"{kind} failed schema: {errors[0].message if errors else ''}")
        unknown = copy.deepcopy(contract)
        unknown["unknown"] = "blocked"
        check(not VALIDATOR.is_valid(unknown), f"{kind} accepted unknown field")
        for other, version in WSC.VERSIONS.items():
            if other != kind:
                crossed = copy.deepcopy(contract)
                crossed["schema_version"] = version
                check(not VALIDATOR.is_valid(crossed), f"{kind} accepted cross-version {other}")
    event = mapped["event"]
    for numeric in (True, "1", -1):
        bad = copy.deepcopy(event)
        bad["revision"] = numeric
        check(not VALIDATOR.is_valid(bad), f"event schema accepted invalid numeric {numeric!r}")
        expect_reason(lambda bad=bad: WSC.validate_contract(bad), "event_revision_invalid", "event integer guard")
    expect_reason(lambda: WSC.parse_json_strict('{"revision":1.0}'), "numeric_type_invalid", "lexical float guard")
    inconsistent = copy.deepcopy(event)
    inconsistent["terminal"] = True
    check(not VALIDATOR.is_valid(inconsistent), "event schema accepted inconsistent terminal state")


def test_canonicalization_and_digests() -> None:
    event = GOLDEN["expected_contracts"]["event"]
    check(WSC.canonical_json_bytes(event).decode("utf-8") == GOLDEN["expected_canonical_event_utf8"],
          "canonical event bytes drift")
    reversed_event = dict(reversed(list(event.items())))
    check(WSC.canonical_json_bytes(reversed_event) == WSC.canonical_json_bytes(event),
          "key order changed canonical bytes")
    check(WSC.canonical_json_bytes({"é": "e\u0301"}) == '{"é":"é"}'.encode("utf-8"),
          "NFC canonicalization drift")
    for bad in (1.0, math.nan, math.inf, -math.inf):
        expect_reason(lambda bad=bad: WSC.canonical_json_bytes({"n": bad}), "numeric_type_invalid", "float guard")
    expect_reason(lambda: WSC.parse_json_strict('{"n":1,"n":2}'), "duplicate_json_key", "duplicate JSON key")
    expect_reason(lambda: WSC.canonical_json_bytes({"e\u0301": 1, "é": 2}), "normalized_key_collision", "NFC key collision")
    for kind, contract in GOLDEN["expected_contracts"].items():
        actual = WSC.domain_digest(f"aq.workflow-shadow.golden.v1.{kind}", contract)
        check(actual == GOLDEN["expected_golden_digests"][kind], f"{kind} golden digest drift")


def test_phase_registry_and_blueprint_source() -> None:
    WSC.validate_phase_registry(REGISTRY)
    blueprint = json.loads(BLUEPRINT_PATH.read_text(encoding="utf-8"))
    actual_ids = sorted({phase["id"] for item in blueprint["blueprints"] for phase in item["phases"]})
    check(actual_ids == GOLDEN["phase_inputs"], "blueprint phase allowlist drift")
    outputs = [WSC.lookup_phase(REGISTRY, value) for value in GOLDEN["phase_inputs"]]
    check(outputs == GOLDEN["expected_phase_outputs"], "opaque phase mapping drift")
    tokens = [item["phase_token"] for item in outputs]
    check(len(tokens) == len(set(tokens)) == 14, "phase-token collision")
    expect_reason(lambda: WSC.lookup_phase(REGISTRY, "free-form-model-phase"), "phase_unknown", "unknown phase")
    duplicate = copy.deepcopy(REGISTRY)
    duplicate["entries"][1]["token"] = duplicate["entries"][0]["token"]
    expect_reason(lambda: WSC.validate_phase_registry(duplicate), "phase_registry_collision", "token collision")
    duplicate = copy.deepcopy(REGISTRY)
    duplicate["entries"][1]["phase_id"] = duplicate["entries"][0]["phase_id"]
    expect_reason(lambda: WSC.validate_phase_registry(duplicate), "phase_registry_collision", "phase-ID collision")
    substituted = copy.deepcopy(REGISTRY)
    substituted["entries"][0]["phase_id"] = "arbitrary_phase"
    substituted["entries"][0]["token"] = "sha256:" + hashlib.sha256(
        (substituted["domain"] + "\x00" + substituted["entries"][0]["phase_id"]).encode("utf-8")
    ).hexdigest()
    expect_reason(lambda: WSC.validate_phase_registry(substituted), "phase_registry_collision", "substituted phase/token pair")
    expect_reason(lambda: WSC.lookup_phase(substituted, "arbitrary_phase"), "phase_registry_collision", "substituted phase lookup")


def _decision_receipt(vector: dict) -> dict:
    receipt = copy.deepcopy(GOLDEN["base_receipt"])
    receipt["expected_revision"] = vector["expected_revision"]
    receipt["revision"] = vector["revision"]
    return receipt


def test_total_decision_model_and_terminal_uniqueness() -> None:
    seen = []
    for vector in GOLDEN["decisions"]:
        result = WSC.decide_receipt(_decision_receipt(vector), vector["stored"])
        seen.append(result["decision"])
        check(result["decision"] == vector["name"], f"decision drift for {vector['name']}")
        accepted = vector["name"] in {"insert", "advance", "exact_replay"}
        check((result["disposition"] == "accepted") == accepted, f"disposition drift for {vector['name']}")
        if vector["name"] == "exact_replay":
            check(result["idempotent"] and not result["emit_event"] and not result["emit_delivery"],
                  "exact replay emitted a record")
        if not accepted:
            check(not result["emit_event"] and not result["emit_delivery"], f"parked {vector['name']} emitted a record")
    check(seen == [item["name"] for item in GOLDEN["decisions"]], "decision order/coverage drift")
    terminal = next(item for item in GOLDEN["decisions"] if item["name"] == "terminal_conflict")
    identity_only = copy.deepcopy(terminal)
    identity_only["stored"]["live_commit_digest"] = GOLDEN["base_receipt"]["live_commit_digest"]
    check(WSC.decide_receipt(_decision_receipt(identity_only), identity_only["stored"])["decision"] == "terminal_conflict",
          "post-terminal identity conflict was not parked")
    nonmonotonic = copy.deepcopy(GOLDEN["base_receipt"])
    nonmonotonic["revision"] = 2
    expect_reason(lambda: WSC.decide_receipt(nonmonotonic, None), "receipt_revision_nonmonotonic", "monotonic receipt")


def test_capacity_and_event_size_boundaries() -> None:
    for vector in GOLDEN["capacity_vectors"]:
        result = WSC.validate_pending_capacity(vector["pending"])
        check(result["disposition"] == vector["disposition"], f"capacity drift at {vector['pending']}")
    for vector in GOLDEN["event_size_vectors"]:
        body = b"x" * vector["bytes"]
        try:
            WSC.validate_event_size_bytes(body)
            accepted = True
        except WSC.ContractError as exc:
            accepted = False
            check(exc.reason == "event_size_exceeded", "event-size reason drift")
        check(accepted == vector["accepted"], f"event-size boundary drift at {vector['bytes']}")


def test_privacy_rejection_and_output_absence() -> None:
    accepted = WSC.map_receipt(GOLDEN["base_receipt"], REGISTRY)
    output_bytes = WSC.canonical_json_bytes(accepted)
    expected_bytes = WSC.canonical_json_bytes(GOLDEN["expected_contracts"])
    health_bytes = WSC.canonical_json_bytes(accepted["health"])
    for canary in GOLDEN["privacy_canaries"]:
        receipt = copy.deepcopy(GOLDEN["base_receipt"])
        receipt[canary["field"]] = canary["value"]
        error = expect_reason(lambda receipt=receipt: WSC.map_receipt(receipt, REGISTRY), "receipt_fields_invalid", "privacy canary")
        encoded = canary["value"].encode("utf-8")
        check(encoded not in output_bytes and encoded not in expected_bytes and encoded not in health_bytes,
              f"privacy canary reached accepted output: {canary['field']}")
        check(canary["value"] not in error, f"privacy canary reached error: {canary['field']}")
    unknown_phase = copy.deepcopy(GOLDEN["base_receipt"])
    unknown_phase["phase_id"] = "free-form-model-phase"
    error = expect_reason(lambda: WSC.map_receipt(unknown_phase, REGISTRY), "phase_unknown", "model phase")
    check("free-form-model-phase" not in error and b"free-form-model-phase" not in output_bytes,
          "raw/model phase reached output or error")
    for phase_id in GOLDEN["phase_inputs"]:
        quoted = json.dumps(phase_id, ensure_ascii=False).encode("utf-8")
        check(quoted not in output_bytes, "raw phase identifier reached mapped output")


def test_no_side_effect_or_prohibited_import_surface() -> None:
    module_source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(module_source, filename=str(MODULE_PATH))
    allowed_imports = {"__future__", "hashlib", "json", "re", "unicodedata", "typing"}
    imported: set[str] = set()
    prohibited_calls = {"open", "print", "exec", "eval", "compile", "__import__"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            check(node.func.id not in prohibited_calls, f"prohibited module call: {node.func.id}")
    check(imported <= allowed_imports, f"prohibited module imports: {sorted(imported - allowed_imports)}")
    check(not any(isinstance(node, (ast.AsyncFunctionDef, ast.Await, ast.Yield, ast.YieldFrom)) for node in ast.walk(tree)),
          "async/background execution surface present")
    embedded_raw_ids = [
        entry["phase_id"] for entry in REGISTRY["entries"]
        if json.dumps(entry["phase_id"], ensure_ascii=False) in module_source
    ]
    check(not embedded_raw_ids, "production module embeds reviewed raw phase identifiers")


TESTS = [
    test_schema_closure_and_versions,
    test_canonicalization_and_digests,
    test_phase_registry_and_blueprint_source,
    test_total_decision_model_and_terminal_uniqueness,
    test_capacity_and_event_size_boundaries,
    test_privacy_rejection_and_output_absence,
    test_no_side_effect_or_prohibited_import_surface,
]


def main() -> int:
    for test in TESTS:
        try:
            test()
        except Exception as exc:
            FAILURES.append(f"{test.__name__}: {type(exc).__name__}: {exc}")
    if FAILURES:
        for failure in FAILURES:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    health = GOLDEN["expected_contracts"]["health"]
    print(f"PASS: workflow shadow pure contract ({len(TESTS)} groups)")
    print("B2_C1_CONTRACT_HEALTH=" + json.dumps({
        "authority": health["authority"], "coverage": health["coverage"]
    }, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
