#!/usr/bin/env python3
"""Focused L2A shadow policy, context, parity, QA, and dashboard checks."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[2]
POLICY_LIB = ROOT / "scripts/ai/lib/local_inference_policy.py"
CONTEXT_LIB = ROOT / "scripts/ai/lib/local_inference_context.py"
L1_FIXTURE = ROOT / "scripts/testing/fixtures/local-inference-contract-v1-golden.json"
L2_FIXTURE = ROOT / "scripts/testing/fixtures/local-inference-l2a-golden.json"
FAILURES: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        FAILURES.append(message)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


POL = load(POLICY_LIB, "l2a_policy_test")
CTX = POL.CTX
LIC = POL.LIC


def l1_vector() -> dict:
    return LIC.parse_json_strict(L1_FIXTURE.read_bytes())["vectors"][0]


def l2_vector() -> dict:
    return LIC.parse_json_strict(L2_FIXTURE.read_bytes())["vectors"][0]


def base_request(tier: str = "standard", profile: str = "continue-local") -> dict:
    return POL.build_caller_request(LIC.normalize_chat_request(l1_vector()["chat"]), tier, profile)


def expect_reason(fn, reason: str, label: str) -> None:
    try:
        fn()
        FAILURES.append(f"{label}: expected {reason}")
    except (POL.PolicyError, CTX.ContextError) as exc:
        check(exc.reason_code == reason, f"{label}: expected {reason}, got {exc.reason_code}")


def resolve(
    request: dict | None = None,
    *,
    tier: str = "standard",
    trusted: dict | None = None,
    ingress: dict | None = None,
    profile_facts: dict | None = None,
    policy: dict | None = None,
) -> dict:
    vector = l2_vector()
    return POL.build_and_resolve(
        request or base_request(tier),
        trusted or copy.deepcopy(l1_vector()["trusted"]),
        ingress or copy.deepcopy(vector["trusted_ingress"][tier]),
        profile_facts or copy.deepcopy(vector["profile_facts"]),
        policy or POL.load_policy(ROOT),
    )


def test_policy_schema_and_closed_shape() -> None:
    schema = LIC.parse_json_strict((ROOT / "config/schemas/local-inference-policy.schema.json").read_bytes())
    policy = POL.load_policy(ROOT)
    jsonschema.Draft202012Validator.check_schema(schema)
    LIC._schema_is_offline_strict(schema)
    jsonschema.Draft202012Validator(schema).validate(policy)
    check(policy["profile_catalog"]["realization"] == "immutable_injected_snapshot",
          "policy does not require injected profile realization")
    check("model" not in json.dumps(policy["profile_decisions"]), "profile decisions duplicate model realization")
    bad = copy.deepcopy(policy)
    bad["ambient_admin"] = True
    expect_reason(lambda: POL._validate_policy_shape(bad), "policy_shape_invalid", "open policy root")


def test_caller_tier_golden_parity_and_binding_mutations() -> None:
    result = POL.run_golden_vectors(ROOT)
    check(result["caller_tier_parity"] == "pass" and result["vector_count"] == 4,
          "caller-tier golden parity did not pass")
    schema = LIC.parse_json_strict((ROOT / "config/schemas/local-inference-request.schema.json").read_bytes())
    plans = []
    for tier in ("flagship", "standard", "budget", "deterministic"):
        outcome = resolve(tier=tier)
        jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(outcome["request"])
        plans.append(LIC.canonical_json_bytes(outcome["resolved_plan"]))
    check(len(set(plans)) == 1, "non-binding caller tiers changed resolved plan bytes")

    forged = base_request("flagship")
    forged["requester"]["model_class"] = "flagship"
    standard_plan = resolve(base_request("standard"), tier="standard")["resolved_plan"]
    forged_plan = resolve(forged, tier="standard")["resolved_plan"]
    check(forged_plan == standard_plan, "untrusted caller model class changed effective plan")

    bad_ingress = copy.deepcopy(l2_vector()["trusted_ingress"]["standard"])
    bad_ingress["authenticated_model_class"] = "invented"
    expect_reason(lambda: resolve(ingress=bad_ingress), "trusted_caller_tier_invalid", "forged trusted tier")

    binding = POL.load_policy(ROOT)
    binding["caller_tiers"]["deterministic"]["budgets"]["output_tokens"] = 200
    changed = resolve(tier="deterministic", policy=binding)["resolved_plan"]
    check(changed["budgets"]["output_tokens"] == 200 and changed != standard_plan,
          "binding caller-tier budget mutation did not change the plan")
    profile_facts = copy.deepcopy(l2_vector()["profile_facts"])
    profile_facts["continue-local"]["budgets"]["input_tokens"] = 900
    changed_profile = resolve(profile_facts=profile_facts)["resolved_plan"]
    check(changed_profile["budgets"]["input_tokens"] == 900, "binding profile cap was ignored")


def test_profile_eligibility_authority_and_budget_failures() -> None:
    for profile in ("local-coding", "ralph", "default"):
        expect_reason(
            lambda p=profile: resolve(base_request(profile=p)),
            "profile_policy_unavailable",
            f"unavailable profile {profile}",
        )
    blocked = base_request()
    blocked["task"]["domain"] = "architecture"
    expect_reason(lambda: resolve(blocked), "task_domain_ineligible", "blocked architecture domain")
    decomposed = base_request()
    decomposed["task"]["task_class"] = "decomposed_edit"
    decomposed["execution"].update({"mode": "ralph", "preferred_lane": "tool_agent", "side_effects": "write"})
    expect_reason(lambda: resolve(decomposed), "task_class_ineligible", "decomposed edit")

    bad_facts = copy.deepcopy(l2_vector()["profile_facts"])
    bad_facts["continue-local"]["budgets"]["deadline_ms"] = 0
    expect_reason(lambda: resolve(profile_facts=bad_facts), "profile_budget_invalid", "magic-zero budget")
    missing = copy.deepcopy(l1_vector()["trusted"])
    missing.pop("runtime_tools")
    expect_reason(lambda: resolve(trusted=missing), "trusted_facts_invalid", "malformed trusted facts")

    write = base_request(profile="local-tool-calling")
    write["task"]["task_class"] = "single_edit"
    write["execution"].update({
        "mode": "agent", "preferred_lane": "tool_agent", "side_effects": "write",
        "allowed_tools": ["*", "write_file"], "max_tool_calls": 2,
    })
    facts = copy.deepcopy(l2_vector()["profile_facts"])
    facts["local-tool-calling"] = copy.deepcopy(facts.pop("continue-local"))
    expect_reason(lambda: resolve(write, profile_facts=facts), "write_authority_missing", "unleased wildcard write")


def test_redaction_no_leak_and_required_context_block() -> None:
    rules = POL.load_policy(ROOT)["context"]["redaction_rule_ids"]
    samples = {
        "credential_assignment": "password=AQ_SYNTHETIC_PASSWORD",
        "bearer_token": "Bearer AQ_SYNTHETIC_BEARER",
        "private_key": "-----BEGIN PRIVATE KEY-----\nAQ_SYNTHETIC\n-----END PRIVATE KEY-----",
        "email_address": "person@example.invalid",
    }
    for rule, secret in samples.items():
        outcome = CTX.prepare_context(
            [{"role": "user", "content": secret, "call_id": None}], inline_max_chars=1000, rule_ids=rules
        )
        encoded = json.dumps(outcome, sort_keys=True)
        check(secret not in encoded, f"{rule} leaked original value")
        check(any(item["rule_id"] == rule and set(item) == {"rule_id", "digest"} for item in outcome["redactions"]),
              f"{rule} report is not bounded to ID+digest")
        repeated = CTX.prepare_context(outcome["messages"], inline_max_chars=1000, rule_ids=rules)
        check(repeated["messages"] == outcome["messages"] and repeated["context_digest"] == outcome["context_digest"],
              f"{rule} redaction is not idempotent")
    expect_reason(
        lambda: CTX.prepare_context(
            [{"role": "system", "content": "api_key=AQ_REQUIRED", "call_id": None}],
            inline_max_chars=1000, rule_ids=rules,
        ),
        "required_context_redacted",
        "required system redaction",
    )


def test_message_pairing_and_deterministic_compaction() -> None:
    rules = POL.load_policy(ROOT)["context"]["redaction_rule_ids"]
    valid = [
        {"role": "system", "content": "system", "call_id": None},
        {"role": "user", "content": "old " * 40, "call_id": None},
        {"role": "assistant", "content": "tool call", "call_id": "call-1"},
        {"role": "tool", "content": "tool result", "call_id": "call-1"},
        {"role": "user", "content": "newest", "call_id": None},
    ]
    one = CTX.prepare_context(valid, inline_max_chars=180, rule_ids=rules)
    two = CTX.prepare_context(valid, inline_max_chars=180, rule_ids=rules)
    check(one == two and one["compacted_count"] > 0, "compaction is not deterministic")
    check(one["summary_position"] == "after_system" and one["summary"].startswith("[COMPACTED "),
          "deterministic summary position/shape drift")
    check({item["call_id"] for item in one["messages"] if item["call_id"]} == {"call-1"},
          "newest complete tool pair was not preserved")
    used = sum(len(item["content"]) for item in one["messages"]) + len(one["summary"])
    check(used <= 180, "compaction exceeded Unicode-code-point budget")
    a = CTX.prepare_context([{"role": "user", "content": "e\u0301", "call_id": None}], inline_max_chars=20, rule_ids=rules)
    b = CTX.prepare_context([{"role": "user", "content": "é", "call_id": None}], inline_max_chars=20, rule_ids=rules)
    check(a["context_digest"] == b["context_digest"], "NFC-equivalent context digests differ")

    two_pairs = [
        {"role": "system", "content": "system", "call_id": None},
        {"role": "assistant", "content": "old call", "call_id": "old"},
        {"role": "tool", "content": "old result", "call_id": "old"},
        {"role": "assistant", "content": "new call", "call_id": "new"},
        {"role": "tool", "content": "new result", "call_id": "new"},
    ]
    grouped = CTX.prepare_context(two_pairs, inline_max_chars=108, rule_ids=rules)
    CTX.validate_message_order(grouped["messages"])
    grouped_ids = [item["call_id"] for item in grouped["messages"] if item["call_id"]]
    check(all(grouped_ids.count(call_id) == 2 for call_id in set(grouped_ids)),
          "compaction retained a partial assistant/tool pair")

    cases = [
        ([{"role": "tool", "content": "x", "call_id": "c"}], "orphan_tool_result"),
        ([{"role": "assistant", "content": "x", "call_id": "c"}], "incomplete_tool_pair"),
        ([{"role": "assistant", "content": "x", "call_id": "c"}, {"role": "tool", "content": "y", "call_id": "d"}], "mismatched_tool_pair"),
        ([{"role": "assistant", "content": "x", "call_id": "c"}, {"role": "tool", "content": "y", "call_id": "c"}, {"role": "assistant", "content": "z", "call_id": "c"}, {"role": "tool", "content": "q", "call_id": "c"}], "duplicate_call_id"),
    ]
    for messages, reason in cases:
        expect_reason(lambda m=messages: CTX.validate_message_order(m), reason, reason)
    overflow = [
        {"role": "system", "content": "S" * 60, "call_id": None},
        {"role": "user", "content": "old", "call_id": None},
    ]
    expect_reason(
        lambda: CTX.prepare_context(overflow, inline_max_chars=50, rule_ids=rules),
        "context_budget_mandatory_overflow",
        "mandatory context overflow",
    )


def test_strict_json_shadow_metadata() -> None:
    check(CTX.parse_exact_json('{"ok":true}') == {"ok": True}, "exact JSON object failed")
    for raw, reason in [
        ("prose {\"ok\":true}", "strict_json_invalid"),
        ("```json\n{\"ok\":true}\n```", "strict_json_invalid"),
        ('{"a":1,"a":2}', "duplicate_json_key"),
        ('{"a":NaN}', "non_finite_number"),
    ]:
        expect_reason(lambda value=raw: CTX.parse_exact_json(value), reason, f"strict JSON {reason}")
    metadata = CTX.strict_json_metadata("json", True)
    check(metadata == {
        "contract": "exact_json_only", "response_format": {"type": "json_object"},
        "wire_visibility": "shadow_internal_until_l2b",
    }, "shadow strict-JSON metadata drift")
    outcome = resolve()
    check("response_format" not in LIC.canonical_json_bytes(outcome["request"]).decode(),
          "shadow response_format leaked into v1 request bytes")
    check("response_format" not in LIC.canonical_json_bytes(outcome["resolved_plan"]).decode(),
          "shadow response_format leaked into resolved-plan bytes")


def test_health_dashboard_qa_and_adoption_guard() -> None:
    health = POL.policy_health(ROOT)
    check(health["status"] == "healthy" and health["caller_tier_parity"] == "pass",
          "L2A policy health is not healthy")
    check(health["vector_count"] == 4 and health["redaction_vector_count"] == 4 and health["compaction_vector_count"] == 3,
          "L2A health vector counts drift")
    with tempfile.TemporaryDirectory() as td:
        missing = POL.policy_health(ROOT, Path(td) / "missing.json")
        check(missing["status"] == "unavailable" and missing["reason_code"] == "policy_fixture_missing",
              "missing L2A fixture did not fail unavailable")
        bad = Path(td) / "bad.json"
        bad.write_text("not json", encoding="utf-8")
        malformed = POL.policy_health(ROOT, bad)
        check(malformed["status"] == "degraded" and malformed["caller_tier_parity"] == "fail",
              "malformed L2A fixture did not fail degraded")
        policy_root = Path(td) / "policy-root"
        (policy_root / "config" / "schemas").mkdir(parents=True)
        (policy_root / "config" / "schemas" / "local-inference-policy.schema.json").write_bytes(
            (ROOT / "config" / "schemas" / "local-inference-policy.schema.json").read_bytes()
        )
        invalid_policy = POL.load_policy(ROOT)
        invalid_policy["strict_json"]["wire_visibility"] = "live"
        (policy_root / "config" / "local-inference-policy.json").write_text(
            json.dumps(invalid_policy), encoding="utf-8"
        )
        invalid_health = POL.policy_health(policy_root)
        check(invalid_health["status"] == "degraded" and invalid_health["schema_status"] == "invalid",
              "dashboard health labeled a schema-invalid policy valid")

    backend = ROOT / "dashboard/backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    from api.routes import aistack
    aistack._LOCAL_INFERENCE_POLICY_MODULE = None
    projected = aistack._local_inference_l2a_health()
    check(projected["status"] == "healthy" and projected["mode"] == "shadow_fixture_only",
          "dashboard L2A health projection failed")

    class Invented:
        @staticmethod
        def policy_health(_root):
            return {
                "status": "healthy", "policy_version": "local-inference-l2a-v1",
                "schema_status": "valid", "caller_tier_parity": "pass", "vector_count": 0,
                "context_adapter_version": "context-l2a-v1", "compaction_policy_version": "compact-l2a-v1",
                "redaction_vector_count": 0, "compaction_vector_count": 0, "profile_decisions": {},
                "digest": None, "reason_code": "attacker_reason",
            }
    aistack._LOCAL_INFERENCE_POLICY_MODULE = Invented()
    rejected = aistack._local_inference_l2a_health()
    check(rejected["status"] == "degraded" and rejected["reason_code"] == "invalid_policy_health_projection",
          "dashboard accepted invented L2A health")

    live_surfaces = [
        "scripts/ai/aq-chat", "scripts/ai/delegate-to-local", "scripts/ai/lib/dispatch.py",
        "scripts/ai/lib/task_config.py", "ai-stack/switchboard/switchboard.py",
        "ai-stack/mcp-servers/hybrid-coordinator/route_handler.py",
        "ai-stack/agents/runtimes/local_agent_runtime.py",
        "ai-stack/mcp-servers/ralph-wiggum/server.py",
    ]
    for rel in live_surfaces:
        text = (ROOT / rel).read_text(encoding="utf-8")
        check("local_inference_policy" not in text and "local_inference_context" not in text,
              f"live surface adopted L2A shadow module: {rel}")

    js = (ROOT / "assets/dashboard.js").read_text(encoding="utf-8")
    check("local_inference_l2a" in js and '"Policy Shadow"' in js and '"· tier parity"' in js,
          "dashboard L2A rows missing")
    phase0 = (ROOT / "scripts/testing/harness_qa/phases/phase0.py").read_text(encoding="utf-8")
    bash = (ROOT / "scripts/ai/_aq-qa-bash").read_text(encoding="utf-8")
    check('"0.10.38"' in phase0 and '"0.10.38"' in bash, "dual QA ID 0.10.38 missing")
    registry = json.loads((ROOT / "config/validation-check-registry.json").read_text())
    entry = next((item for item in registry["checks"] if item.get("id") == "local-inference-contract-l2a"), None)
    required = {
        ".agent/PROJECT-LOCAL-INFERENCE-CONTRACT-PRD.md", ".agent/PROJECT-LOCAL-INFERENCE-L2A-PLAN.md",
        "config/schemas/local-inference-policy.schema.json", "config/local-inference-policy.json",
        "scripts/ai/lib/local_inference_context.py", "scripts/ai/lib/local_inference_policy.py",
        "scripts/testing/fixtures/local-inference-l2a-golden.json", "scripts/testing/test-local-inference-l2a.py",
        "scripts/testing/harness_qa/phases/phase0.py", "scripts/ai/_aq-qa-bash",
        "config/validation-check-registry.json", "dashboard/backend/api/routes/aistack.py", "assets/dashboard.js",
    }
    check(bool(entry) and required.issubset(set(entry["trigger_paths"])),
          "focused CI omits an L2A behavior/dashboard surface")


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
    print(f"PASS: {len(tests)} local-inference L2A checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
