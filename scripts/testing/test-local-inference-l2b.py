#!/usr/bin/env python3
"""Focused L2B-A shadow transport contract checks."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
FAILURES: list[str] = []


def check(value: bool, message: str) -> None:
    if not value:
        FAILURES.append(message)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


T = load(ROOT / "scripts/ai/lib/local_inference_transport.py", "l2b_transport_test")


def expect(reason: str, fn, label: str) -> None:
    try:
        fn()
        FAILURES.append(f"{label}: expected {reason}")
    except T.TransportError as exc:
        check(
            exc.reason_code == reason,
            f"{label}: got {exc.reason_code}, expected {reason}",
        )


def identity() -> dict[str, str]:
    return {
        "request_id": "11111111-1111-4111-8111-111111111111",
        "run_id": "22222222-2222-4222-8222-222222222222",
        "trace_id": "33333333-3333-4333-8333-333333333333",
    }


def trusted() -> dict:
    p = T.load_policy(ROOT)
    system_message = "[Role: implementer] bounded fixture role"
    return {
        "document_kind": "trusted_snapshot",
        "profile": "continue-local",
        "model": "local-test",
        "snapshot_revision": "snapshot-v1",
        "builder_revision": p["canonical_builder"]["revision"],
        "builder_sha256": p["canonical_builder"]["sha256"],
        "capabilities": {
            "streaming": True,
            "response_format": True,
            "tools": True,
            "cache_prompt": True,
            "thinking": False,
        },
        "authority": {
            "system_message_sha256": hashlib.sha256(
                system_message.encode("utf-8")
            ).hexdigest(),
            "chat_template_kwargs": {"enable_thinking": False},
        },
    }


def resolved() -> dict:
    return {
        "profile": "continue-local",
        "model": "local-test",
        "messages": [{"role": "user", "content": "hello"}],
        "max_tokens": 64,
        "temperature": 0.0,
        "effective_role": "implementer",
        "task_type": "structured",
        "artifact_format": "json",
        "frequency_penalty": 0.0,
    }


def test_schemas_policy_and_manifest() -> None:
    transport_schema = None
    for name in (
        "local-inference-transport.schema.json",
        "local-inference-transport-policy.schema.json",
    ):
        schema = json.loads((ROOT / "config/schemas" / name).read_text())
        if name == "local-inference-transport.schema.json":
            transport_schema = schema
        jsonschema.Draft202012Validator.check_schema(schema)
        check(
            "http"
            not in json.dumps(schema.get("$defs", {})).replace(
                "https://json-schema.org", ""
            ),
            f"{name} has external ref",
        )
    assert transport_schema is not None
    tool_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": transport_schema["$defs"],
        "$ref": "#/$defs/toolDefinition",
    }
    tool_call_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": transport_schema["$defs"],
        "$ref": "#/$defs/toolCall",
    }
    for document, schema, label in (
        (
            {"type": "function", "function": {"name": "bad", "parameters": 7}},
            tool_schema,
            "scalar tool parameters",
        ),
        (
            {"index": 0, "id": "call", "type": "function", "name": "bad", "arguments": 7},
            tool_call_schema,
            "scalar tool arguments",
        ),
    ):
        try:
            jsonschema.Draft202012Validator(schema).validate(document)
            FAILURES.append(f"{label} accepted")
        except jsonschema.ValidationError:
            pass
    policy = T.load_policy(ROOT)
    check(
        policy["targets"]["ralph"]["status"] == "unavailable_route_contract",
        "Ralph not explicit unavailable",
    )
    fixture = json.loads(
        (
            ROOT / "scripts/testing/fixtures/local-inference-l2b-payload-golden.json"
        ).read_text()
    )
    for rel, expected_hash in fixture["live_source_manifest"].items():
        path = ROOT / rel
        check(
            hashlib.sha256(path.read_bytes()).hexdigest() == expected_hash,
            f"live source drift: {rel}",
        )
        if path.suffix == ".py" or path.name in {"aq-chat"}:
            check(
                "local_inference_transport" not in path.read_text(encoding="utf-8"),
                f"live import adopted: {rel}",
            )
    source_shapes = fixture.get("source_shapes", [])
    check(
        {item.get("path") for item in source_shapes}
        == set(fixture["live_source_manifest"]),
        "source-shape evidence does not cover the frozen live manifest",
    )
    check(
        {item.get("id") for item in source_shapes}
        == {
            "canonical-builder",
            "dispatch-direct",
            "embedded-assist",
            "aq-chat-fast-path",
            "coordinator-route",
            "coordinator-client",
            "coordinator-handler",
            "local-runtime",
            "switchboard",
            "ralph-unavailable",
        },
        "required observed source shapes are not frozen",
    )
    shape_health = T.characterize_source_shapes(ROOT, source_shapes)
    check(shape_health["status"] == "pass", "executable source-shape parity failed")
    broken_shapes = copy.deepcopy(source_shapes)
    broken_shapes[0]["predicates"][0]["literal"] = "def impossible_builder_shape("
    check(
        T.characterize_source_shapes(ROOT, broken_shapes)["status"] == "fail",
        "source-shape predicates did not fail closed",
    )


def actual_ssot_wire(environment: dict[str, str]) -> str:
    """Execute the committed builder in an isolated, explicitly declared env."""
    program = textwrap.dedent(
        """
        import hashlib
        import importlib.util
        import os
        import pathlib
        import sys

        root = pathlib.Path(sys.argv[1]).resolve()

        def load(path, name):
            spec = importlib.util.spec_from_file_location(name, path)
            if spec is None or spec.loader is None:
                raise RuntimeError(name)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            return module

        transport = load(
            root / "scripts/ai/lib/local_inference_transport.py", "l2b_sub_transport"
        )
        llm = load(
            root / "ai-stack/mcp-servers/shared/llm_config.py", "l2b_sub_llm_config"
        )
        policy = transport.load_policy(root)
        system_message = llm.ROLE_SYSTEM_PROMPTS["implementer"]
        if os.environ["FABLE_PARITY"] != "0":
            system_message += "\\n\\n" + llm.FABLE_PARITY_SYSTEM_PROMPT
        trusted = {
            "document_kind": "trusted_snapshot",
            "profile": "continue-local",
            "model": "local-test",
            "snapshot_revision": "snapshot-v1",
            "builder_revision": policy["canonical_builder"]["revision"],
            "builder_sha256": policy["canonical_builder"]["sha256"],
            "capabilities": {
                "streaming": True,
                "response_format": True,
                "tools": True,
                "cache_prompt": True,
                "thinking": False,
            },
            "authority": {
                "system_message_sha256": hashlib.sha256(
                    system_message.encode("utf-8")
                ).hexdigest(),
                "chat_template_kwargs": {"enable_thinking": False},
            },
        }
        resolved = {
            "profile": "continue-local",
            "model": "local-test",
            "messages": [{"role": "user", "content": "hello"}],
            "max_tokens": 128,
            "temperature": 0.0,
            "effective_role": "implementer",
            "task_type": "agent",
            "artifact_format": "text",
            "frequency_penalty": 0.0,
        }
        plan = transport.build_transport_plan(
            resolved,
            trusted,
            {"document_kind": "untrusted_header_claim", "headers": []},
            policy,
            llm.build_llama_payload,
            target="switchboard",
            decoder_mode="openai_sse",
        )
        sys.stdout.write(plan["canonical"]["canonical_wire_utf8"])
        """
    )
    minimal_env = {
        "FABLE_PARITY": environment["FABLE_PARITY"],
        "LLAMA_MAX_TOKENS": environment["LLAMA_MAX_TOKENS"],
        "PYTHONHASHSEED": "0",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }
    completed = subprocess.run(
        [sys.executable, "-I", "-c", program, str(ROOT)],
        check=False,
        capture_output=True,
        text=True,
        env=minimal_env,
        timeout=30,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip())
    return completed.stdout


def test_actual_ssot_golden_subprocess() -> None:
    fixture = json.loads(
        (
            ROOT / "scripts/testing/fixtures/local-inference-l2b-payload-golden.json"
        ).read_text()
    )
    check(
        fixture["builder_environment"]["declared_names"]
        == ["FABLE_PARITY", "LLAMA_MAX_TOKENS"],
        "actual-builder environment declaration drifted",
    )
    observed: dict[str, str] = {}
    for vector in fixture["actual_ssot_vectors"]:
        wire = actual_ssot_wire(vector["environment"])
        observed[vector["id"]] = wire
        check(
            wire == vector["expected_canonical_wire_utf8"],
            f"actual SSOT canonical bytes drift: {vector['id']}",
        )
        payload = json.loads(wire)["payload"]
        system_message = next(
            item["content"] for item in payload["messages"] if item["role"] == "system"
        )
        check(
            hashlib.sha256(system_message.encode()).hexdigest()
            == vector["expected_system_message_sha256"]
            and payload["chat_template_kwargs"]
            == vector["expected_chat_template_kwargs"],
            f"actual SSOT authority drift: {vector['id']}",
        )
    check(
        len(set(observed.values())) == 2,
        "FABLE_PARITY states do not freeze distinct relevant payloads",
    )
    canary = fixture["builder_environment"]["forbidden_ambient_canary"]
    prior = os.environ.get(canary)
    os.environ[canary] = "999999"
    try:
        for vector in fixture["actual_ssot_vectors"]:
            check(
                actual_ssot_wire(vector["environment"])
                == vector["expected_canonical_wire_utf8"],
                f"ambient payload variable affected isolated builder: {vector['id']}",
            )
    finally:
        if prior is None:
            os.environ.pop(canary, None)
        else:
            os.environ[canary] = prior


def test_builder_binding_headers_and_once() -> None:
    policy = T.load_policy(ROOT)
    calls: list[tuple] = []

    def builder(messages, **kwargs):
        calls.append((copy.deepcopy(messages), copy.deepcopy(kwargs)))
        emitted_messages = copy.deepcopy(messages)
        emitted_messages.insert(
            0,
            {
                "role": "system",
                "content": "[Role: implementer] bounded fixture role",
            },
        )
        built = {
            "messages": emitted_messages,
            "model": kwargs["model"],
            "max_tokens": kwargs["max_tokens"],
            "temperature": kwargs["temperature"],
            "stream": kwargs["stream"],
            "frequency_penalty": kwargs["frequency_penalty"],
            "response_format": kwargs["response_format"],
            "chat_template_kwargs": {"enable_thinking": False},
            "cache_prompt": True,
            "repeat_penalty": policy["builder_defaults"]["repeat_penalty"],
            "repeat_last_n": policy["builder_defaults"]["repeat_last_n"],
        }
        if kwargs["stream"]:
            built["stream_options"] = {"include_usage": True}
        return built

    plan = T.build_transport_plan(
        resolved(),
        trusted(),
        {"document_kind": "untrusted_header_claim", "headers": []},
        policy,
        builder,
        target="switchboard",
        decoder_mode="openai_sse",
    )
    transport_schema = json.loads(
        (ROOT / "config/schemas/local-inference-transport.schema.json").read_text()
    )
    jsonschema.Draft202012Validator(
        transport_schema, format_checker=jsonschema.FormatChecker()
    ).validate(plan)
    check(
        len(calls) == 1 and plan["canonical"]["payload"]["stream"] is True,
        "builder call parity failed",
    )
    check(
        plan["canonical"]["headers"]
        == sorted(plan["canonical"]["headers"], key=lambda x: x["name"]),
        "headers not canonical",
    )
    for headers, reason in [
        ([{"name": "Authorization", "value": "secret"}], "header_forbidden"),
        (
            [
                {"name": "Accept", "value": "application/json"},
                {"name": "accept", "value": "text/event-stream"},
            ],
            "duplicate_header",
        ),
        ([{"name": "Bad Header", "value": "x"}], "header_name_invalid"),
    ]:
        expect(
            reason,
            lambda h=headers: T.validate_headers(
                {"document_kind": "untrusted_header_claim", "headers": h},
                policy["targets"]["switchboard"],
            ),
            reason,
        )
    bad = trusted()
    bad["builder_sha256"] = "0" * 64
    expect(
        "builder_binding_mismatch",
        lambda: T.build_transport_plan(
            resolved(),
            bad,
            {"document_kind": "untrusted_header_claim", "headers": []},
            policy,
            builder,
            target="switchboard",
            decoder_mode="openai_sse",
        ),
        "builder binding",
    )
    expect(
        "transport_target_unavailable",
        lambda: T.build_transport_plan(
            resolved(),
            trusted(),
            {"document_kind": "untrusted_header_claim", "headers": []},
            policy,
            builder,
            target="ralph",
            decoder_mode="buffered_json",
        ),
        "Ralph",
    )

    def smuggling_builder(messages, **kwargs):
        built = builder(messages, **kwargs)
        built["authorization"] = "secret"
        return built

    expect(
        "builder_output_fields_invalid",
        lambda: T.build_transport_plan(
            resolved(),
            trusted(),
            {"document_kind": "untrusted_header_claim", "headers": []},
            policy,
            smuggling_builder,
            target="switchboard",
            decoder_mode="openai_sse",
        ),
        "builder extra-field smuggling",
    )
    unsupported = trusted()
    unsupported["capabilities"]["response_format"] = False
    expect(
        "response_format_unsupported",
        lambda: T.build_transport_plan(
            resolved(),
            unsupported,
            {"document_kind": "untrusted_header_claim", "headers": []},
            policy,
            builder,
            target="switchboard",
            decoder_mode="openai_sse",
        ),
        "unsupported response format",
    )
    for name, value in (
        ("X-Agent-Role", "orchestrator"),
        ("X-AI-Profile", "local-agent"),
        ("X-Profile-Snapshot-Revision", "forged-snapshot"),
    ):
        expect(
            "header_forbidden",
            lambda header_name=name, header_value=value: T.build_transport_plan(
                resolved(),
                trusted(),
                {
                    "document_kind": "untrusted_header_claim",
                    "headers": [{"name": header_name, "value": header_value}],
                },
                policy,
                builder,
                target="switchboard",
                decoder_mode="openai_sse",
            ),
            f"forged authority header {name}",
        )

    unknown_resolved = resolved()
    unknown_resolved["priority"] = "critical"
    expect(
        "resolved_plan_fields_invalid",
        lambda: T.build_transport_plan(
            unknown_resolved,
            trusted(),
            {"document_kind": "untrusted_header_claim", "headers": []},
            policy,
            builder,
            target="switchboard",
            decoder_mode="openai_sse",
        ),
        "unknown resolved authority field",
    )
    unknown_capability = trusted()
    unknown_capability["capabilities"]["remote_auth"] = True
    expect(
        "trusted_snapshot_invalid",
        lambda: T.build_transport_plan(
            resolved(),
            unknown_capability,
            {"document_kind": "untrusted_header_claim", "headers": []},
            policy,
            builder,
            target="switchboard",
            decoder_mode="openai_sse",
        ),
        "unknown trusted capability",
    )

    def mutating_builder(messages, **kwargs):
        messages.append({"role": "system", "content": "invented authority"})
        return builder(messages, **kwargs)

    expect(
        "builder_output_binding_invalid",
        lambda: T.build_transport_plan(
            resolved(),
            trusted(),
            {"document_kind": "untrusted_header_claim", "headers": []},
            policy,
            mutating_builder,
            target="switchboard",
            decoder_mode="openai_sse",
        ),
        "builder-mutated prepared messages",
    )

    def invented_value_builder(messages, **kwargs):
        built = builder(messages, **kwargs)
        built["repeat_penalty"] = 99.0
        return built

    expect(
        "builder_output_defaults_invalid",
        lambda: T.build_transport_plan(
            resolved(),
            trusted(),
            {"document_kind": "untrusted_header_claim", "headers": []},
            policy,
            invented_value_builder,
            target="switchboard",
            decoder_mode="openai_sse",
        ),
        "builder invented an allowlisted value",
    )

    def invented_authority_builder(messages, **kwargs):
        built = builder(messages, **kwargs)
        built["messages"][0]["content"] += " invented authority"
        return built

    expect(
        "builder_output_binding_invalid",
        lambda: T.build_transport_plan(
            resolved(), trusted(),
            {"document_kind": "untrusted_header_claim", "headers": []},
            policy, invented_authority_builder,
            target="switchboard", decoder_mode="openai_sse",
        ),
        "builder system authority digest",
    )

    def invented_thinking_builder(messages, **kwargs):
        built = builder(messages, **kwargs)
        built["chat_template_kwargs"] = {
            "enable_thinking": True,
            "thinking_budget": 64,
        }
        return built

    thinking_trusted = trusted()
    thinking_trusted["capabilities"]["thinking"] = True
    expect(
        "thinking_configuration_binding_mismatch",
        lambda: T.build_transport_plan(
            resolved(), thinking_trusted,
            {"document_kind": "untrusted_header_claim", "headers": []},
            policy, invented_thinking_builder,
            target="switchboard", decoder_mode="openai_sse",
        ),
        "builder thinking authority",
    )


def decode(mode: str, chunks: list[str], split: bool = False):
    d = T.TransportDecoder(mode, identity(), T.load_policy(ROOT)["limits"])
    raw = "".join(chunks).encode()
    if split:
        for byte in raw:
            d.feed(bytes([byte]))
    else:
        for chunk in chunks:
            d.feed(chunk.encode())
    return d.finish()


def test_stream_vectors_and_splits() -> None:
    fixture = json.loads(
        (
            ROOT / "scripts/testing/fixtures/local-inference-l2b-stream-golden.json"
        ).read_text()
    )
    for vector in fixture["vectors"]:
        one = decode(vector["mode"], vector["chunks"])
        two = decode(vector["mode"], vector["chunks"], split=True)
        check(one == two, f"byte-split parity failed: {vector['id']}")
    success = decode(fixture["vectors"][1]["mode"], fixture["vectors"][1]["chunks"])
    check(
        success["content"] == "hé"
        and [o["kind"] for o in success["observations"]][-3:]
        == ["finish", "usage", "done"],
        "SSE content/usage ordering drift",
    )
    tool = decode(fixture["vectors"][4]["mode"], fixture["vectors"][4]["chunks"])
    check(
        tool["tool_calls"][0]["arguments"] == {"q": 1}, "tool fragments not exact JSON"
    )
    err = decode(fixture["vectors"][3]["mode"], fixture["vectors"][3]["chunks"])
    check(
        err["terminal_state"] == "upstream_error" and len(err["observations"]) == 1,
        "upstream error terminal drift",
    )


def test_malformed_cancel_and_limits() -> None:
    limits = T.load_policy(ROOT)["limits"]
    expect(
        "sse_done_missing",
        lambda: decode(
            "openai_sse",
            ['data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'],
        ),
        "missing DONE",
    )
    expect(
        "duplicate_done",
        lambda: decode("openai_sse", ["data: [DONE]\n\ndata: [DONE]\n\n"]),
        "duplicate DONE",
    )
    expect(
        "post_terminal_bytes",
        lambda: decode(
            "openai_sse",
            [
                'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n: late\n\n'
            ],
        ),
        "post terminal comment",
    )
    expect(
        "usage_before_finish",
        lambda: decode(
            "openai_sse",
            ['data: {"choices":[],"usage":{"prompt_tokens":1}}\n\ndata: [DONE]\n\n'],
        ),
        "usage before finish",
    )
    expect(
        "invalid_utf8",
        lambda: (lambda d: d.feed(b"\xff"))(
            T.TransportDecoder("openai_sse", identity(), limits)
        ),
        "invalid UTF8",
    )
    d = T.TransportDecoder("openai_sse", identity(), limits)
    first = d.cancel()
    second = d.cancel()
    check(
        len(first) == 1 and first[0]["kind"] == "cancelled" and second == [],
        "cancel is not idempotent",
    )
    expect("post_terminal_bytes", lambda: d.feed(b"x"), "bytes after cancel")


def test_adversarial_decoder_shapes() -> None:
    limits = T.load_policy(ROOT)["limits"]
    tiny_total = dict(limits)
    tiny_total["max_total_bytes"] = 4
    oversized = T.TransportDecoder("openai_sse", identity(), tiny_total)
    expect(
        "transport_total_oversized",
        lambda: oversized.feed(b"12345"),
        "oversized SSE feed",
    )
    tiny_event = dict(limits)
    tiny_event["max_event_bytes"] = 8
    event_oversized = T.TransportDecoder("openai_sse", identity(), tiny_event)
    expect(
        "sse_event_oversized",
        lambda: event_oversized.feed(b'data: {"choices":[]}\n\n'),
        "oversized SSE event",
    )
    expect(
        "upstream_fields_invalid",
        lambda: decode(
            "openai_sse",
            [
                'data: {"id":"untrusted","choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'
                "data: [DONE]\n\n"
            ],
        ),
        "unknown upstream response field",
    )
    expect(
        "delta_fields_invalid",
        lambda: decode(
            "openai_sse",
            [
                'data: {"choices":[{"delta":{"reasoning_content":"hidden"},"finish_reason":"stop"}]}\n\n'
                "data: [DONE]\n\n"
            ],
        ),
        "unknown delta field",
    )
    expect(
        "tool_identity_first_fragment_missing",
        lambda: decode(
            "openai_sse",
            [
                'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\\"q\\":"}}]},"finish_reason":null}]}\n\n',
                'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call-1","type":"function","function":{"name":"lookup","arguments":"1}"}}]},"finish_reason":"tool_calls"}]}\n\n',
                "data: [DONE]\n\n",
            ],
        ),
        "late tool identity establishment",
    )


def test_strict_json_and_candidate() -> None:
    for raw, reason in [
        (b'{"a":1,"a":2}', "duplicate_json_key"),
        (b"```json\n{}\n```", "strict_json_invalid"),
        (b'{"a":NaN}', "non_finite_number"),
    ]:
        expect(reason, lambda value=raw: T.parse_exact_json(value), reason)
    event_schema = json.loads(
        (ROOT / "config/schemas/local-inference-event.schema.json").read_text()
    )
    result_schema = json.loads(
        (ROOT / "config/schemas/local-inference-result.schema.json").read_text()
    )
    expect(
        "candidate_evidence_missing",
        lambda: T.assemble_terminal_candidate(
            {}, {}, event_schema=event_schema, result_schema=result_schema
        ),
        "candidate missing evidence",
    )
    identifier = "00000000-0000-4000-8000-000000000001"
    event = {
        "contract_version": "1.0",
        "request_id": identifier,
        "run_id": identifier,
        "trace_id": identifier,
        "sequence": 1,
        "event_type": "completed",
        "terminal": True,
        "payload": {
            "content_delta": None,
            "usage_delta": {"input_tokens": 1, "output_tokens": 1},
            "tool": None,
            "validation_check": None,
        },
        "error": None,
    }
    result = {
        "contract_version": "1.0",
        "request_id": identifier,
        "run_id": identifier,
        "trace_id": identifier,
        "session_id": None,
        "sequence": 1,
        "status": "complete",
        "resolved_plan": {
            "contract_version": "1.0",
            "config_version": "fixture-v1",
            "mode": "direct",
            "requested_profile": "continue-local",
            "profile": "continue-local",
            "model": "fixture-model",
            "task_class": "tiny",
            "effective_role": "implementer",
            "side_effects": "none",
            "tools": [],
            "budgets": {
                "input_tokens": 1,
                "output_tokens": 1,
                "deadline_ms": 1,
                "queue_wait_ms": 1,
                "max_tool_calls": 0,
            },
            "queue_band": "normal",
            "fallback": {
                "mode": "deny",
                "allowed_profiles": [],
                "max_attempts": 1,
                "equivalence_registry_version": "fixture-v1",
            },
            "capability_delta": [],
            "reasons": ["fixture_candidate"],
        },
        "artifact": {"format": "text", "content": "ok", "schema_valid": True},
        "claims": [],
        "validation": {"results": [], "missing_evidence": []},
        "effects": {"changed_files": [], "executed_tools": []},
        "usage": {"input_tokens": 1, "output_tokens": 1, "tool_calls": 0},
        "timing": {"queue_ms": 0, "ttft_ms": 0, "inference_ms": 1, "total_ms": 1},
        "provenance": {
            "producer": "l2b-a-fixture",
            "template_version": "fixture-v1",
            "context_digest": "0" * 64,
            "input_digest": "1" * 64,
            "output_digest": "2" * 64,
        },
        "error": None,
        "limitations": [],
        "next_action": "",
    }
    wrapped = T.assemble_terminal_candidate(
        event,
        result,
        event_schema=event_schema,
        result_schema=result_schema,
    )
    check(wrapped["authoritative"] is False, "candidate claimed lifecycle authority")
    malformed = dict(result)
    malformed["unexpected"] = True
    expect(
        "schema_validation_failed",
        lambda: T.assemble_terminal_candidate(
            event,
            malformed,
            event_schema=event_schema,
            result_schema=result_schema,
        ),
        "candidate accepted schema-invalid result",
    )
    strict = T.TransportDecoder(
        "buffered_json",
        identity(),
        T.load_policy(ROOT)["limits"],
        artifact_format="json",
    )
    strict.feed(
        b'{"choices":[{"message":{"content":"not json"},"finish_reason":"stop"}]}'
    )
    expect("strict_json_invalid", strict.finish, "JSON artifact final parse")


def test_health_dashboard_qa_and_inventory() -> None:
    health = T.transport_health(ROOT)
    check(
        health["status"] == "healthy"
        and health["payload_parity"] == health["stream_parity"] == "pass",
        "transport health failed",
    )
    check(
        health["source_shape_parity"] == health["actual_ssot_parity"] == "pass",
        "transport health overstated executable parity",
    )
    backend = ROOT / "dashboard/backend"
    sys.path.insert(0, str(backend))
    from api.routes import aistack

    aistack._LOCAL_INFERENCE_TRANSPORT_MODULE = T
    aistack._LOCAL_INFERENCE_TRANSPORT_CACHE = {"digest": None, "payload": None}
    projected = aistack._local_inference_l2b_health_sync()
    check(
        projected["status"] == "healthy"
        and projected["mode"] == "shadow_fixture_only"
        and projected["source_shape_parity"] == "pass"
        and projected["actual_ssot_parity"] == "pass",
        "dashboard health projection failed",
    )

    class HealthStub:
        def __init__(self, raw=None, error: Exception | None = None):
            self.raw = raw
            self.error = error

        @staticmethod
        def transport_asset_digest(_root: Path) -> str:
            return "f" * 64

        def transport_health(self, _root: Path):
            if self.error is not None:
                raise self.error
            return copy.deepcopy(self.raw)

    baseline = T.transport_health(ROOT)
    original_module = aistack._LOCAL_INFERENCE_TRANSPORT_MODULE
    try:
        adversarial = []
        for field in ("source_shape_parity", "actual_ssot_parity"):
            missing = copy.deepcopy(baseline)
            missing.pop(field)
            adversarial.append((f"missing {field}", missing))
            malformed = copy.deepcopy(baseline)
            malformed[field] = "internal/path/secret"
            adversarial.append((f"malformed {field}", malformed))
            failed = copy.deepcopy(baseline)
            failed[field] = "fail"
            adversarial.append((f"failed {field}", failed))
        for label, raw in adversarial:
            aistack._LOCAL_INFERENCE_TRANSPORT_MODULE = HealthStub(raw=raw)
            aistack._LOCAL_INFERENCE_TRANSPORT_CACHE = {"digest": None, "payload": None}
            result = aistack._local_inference_l2b_health_sync()
            check(result["status"] == "degraded", f"{label} did not degrade")
            check(
                result["source_shape_parity"] in {"fail", "unavailable"}
                and result["actual_ssot_parity"] in {"fail", "unavailable"},
                f"{label} escaped the closed parity enum",
            )
            check(
                "internal/path/secret" not in json.dumps(result),
                f"{label} exposed untrusted health content",
            )
        aistack._LOCAL_INFERENCE_TRANSPORT_MODULE = HealthStub(
            error=RuntimeError("/nix/store/private prompt=secret")
        )
        aistack._LOCAL_INFERENCE_TRANSPORT_CACHE = {"digest": None, "payload": None}
        failed_closed = aistack._local_inference_l2b_health_sync()
        check(
            failed_closed["status"] == "unavailable"
            and failed_closed["source_shape_parity"] == "unavailable"
            and failed_closed["actual_ssot_parity"] == "unavailable"
            and "secret" not in json.dumps(failed_closed),
            "transport exception did not fail closed",
        )
    finally:
        aistack._LOCAL_INFERENCE_TRANSPORT_MODULE = original_module
        aistack._LOCAL_INFERENCE_TRANSPORT_CACHE = {"digest": None, "payload": None}

    dashboard_source = (ROOT / "dashboard/backend/api/routes/aistack.py").read_text()
    check(
        "await asyncio.to_thread(_local_inference_l2b_health_sync)" in dashboard_source,
        "dashboard health is not offloaded from the async event loop",
    )
    dashboard_js = (ROOT / "assets/dashboard.js").read_text()
    check(
        'value === "pass" || value === "fail" || value === "unavailable"'
        in dashboard_js
        and "closedParityState(l2b.source_shape_parity)" in dashboard_js
        and "closedParityState(l2b.actual_ssot_parity)" in dashboard_js,
        "dashboard client does not fail closed on malformed parity values",
    )
    for field, label in (
        ("source_shape_parity", "· source shape"),
        ("actual_ssot_parity", "· actual SSOT"),
    ):
        check(
            field in dashboard_js and label in dashboard_js,
            f"dashboard card does not visibly render {field}",
        )
    phase = (ROOT / "scripts/testing/harness_qa/phases/phase0.py").read_text()
    bash = (ROOT / "scripts/ai/_aq-qa-bash").read_text()
    check('"0.10.39"' in phase and '"0.10.39"' in bash, "dual QA ID missing")
    registry = json.loads((ROOT / "config/validation-check-registry.json").read_text())
    entry = next(
        (
            x
            for x in registry["checks"]
            if x.get("id") == "local-inference-contract-l2b-a"
        ),
        None,
    )
    check(
        bool(entry) and len(entry["trigger_paths"]) == 14,
        "focused inventory is not exact 14",
    )


for fn in (
    test_schemas_policy_and_manifest,
    test_actual_ssot_golden_subprocess,
    test_builder_binding_headers_and_once,
    test_stream_vectors_and_splits,
    test_malformed_cancel_and_limits,
    test_adversarial_decoder_shapes,
    test_strict_json_and_candidate,
    test_health_dashboard_qa_and_inventory,
):
    try:
        fn()
    except Exception as exc:
        FAILURES.append(f"{fn.__name__}: {type(exc).__name__}: {exc}")

if FAILURES:
    print("FAIL: local-inference L2B-A")
    for failure in FAILURES:
        print(f" - {failure}")
    raise SystemExit(1)
print("PASS: 8 local-inference L2B-A checks")
