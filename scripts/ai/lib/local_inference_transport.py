#!/usr/bin/env python3
"""Pure L2B-A payload planning and transport observation decoding."""

from __future__ import annotations

import codecs
import copy
import hashlib
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


@dataclass(frozen=True)
class TransportError(ValueError):
    code: str
    reason_code: str
    safe_message: str
    retryable: bool = False

    def __str__(self) -> str:
        return f"{self.code}:{self.reason_code}"

    def as_fault(self) -> dict[str, Any]:
        return {
            "document_kind": "parser_fault",
            "code": "transport_error",
            "reason_code": self.reason_code,
            "message": self.safe_message,
            "retryable": False,
        }


def _fail(reason: str, message: str, code: str = "transport_error") -> None:
    raise TransportError(code, reason, message)


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            _fail(
                "duplicate_json_key",
                "JSON contains a duplicate key",
                "malformed_result",
            )
        result[key] = value
    return result


def parse_exact_json(raw: str | bytes) -> dict[str, Any]:
    try:
        value = json.loads(
            raw,
            object_pairs_hook=_pairs,
            parse_constant=lambda _x: _fail(
                "non_finite_number",
                "JSON contains a non-finite number",
                "malformed_result",
            ),
        )
    except TransportError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TransportError(
            "malformed_result",
            "strict_json_invalid",
            "Input must be one exact JSON document",
        ) from exc
    if not isinstance(value, dict):
        _fail(
            "strict_json_not_object",
            "Input must be one JSON object",
            "malformed_result",
        )
    return value


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise TransportError(
            "malformed_result", "non_canonical_value", "Value is not canonical JSON"
        ) from exc


def _digest(domain: str, value: Any) -> str:
    return hashlib.sha256(domain.encode() + b"\0" + canonical_bytes(value)).hexdigest()


def _schema(repo_root: Path, name: str) -> dict[str, Any]:
    return parse_exact_json((repo_root / "config" / "schemas" / name).read_bytes())


def _validate(instance: Any, schema: Mapping[str, Any]) -> None:
    try:
        from jsonschema import Draft202012Validator, FormatChecker

        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(instance)
    except ImportError as exc:
        raise TransportError(
            "malformed_result", "validator_unavailable", "Schema validator unavailable"
        ) from exc
    except Exception as exc:
        raise TransportError(
            "malformed_result",
            "schema_validation_failed",
            "Document violates transport schema",
        ) from exc


def load_policy(repo_root: Path) -> dict[str, Any]:
    policy = parse_exact_json(
        (repo_root / "config" / "local-inference-transport-policy.json").read_bytes()
    )
    _validate(
        policy, _schema(repo_root, "local-inference-transport-policy.schema.json")
    )
    return policy


_TOKEN = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
_FORBIDDEN = {"authorization", "cookie", "proxy-authorization", "x-api-key", "api-key"}
_INGRESS_HEADERS = {"accept", "content-type"}
_CAPABILITY_FIELDS = {
    "streaming",
    "response_format",
    "tools",
    "cache_prompt",
    "thinking",
}
_RESOLVED_FIELDS = {
    "profile",
    "model",
    "messages",
    "max_tokens",
    "temperature",
    "effective_role",
    "task_type",
    "artifact_format",
    "stop",
    "frequency_penalty",
    "tools",
    "tool_choice",
}


def validate_headers(
    claim: Mapping[str, Any], target_rule: Mapping[str, Any]
) -> list[dict[str, str]]:
    if (
        set(claim) != {"document_kind", "headers"}
        or claim.get("document_kind") != "untrusted_header_claim"
        or not isinstance(claim.get("headers"), list)
    ):
        _fail(
            "header_claim_invalid", "Header claim shape is invalid", "invalid_request"
        )
    seen: set[str] = set()
    for item in claim["headers"]:
        if (
            not isinstance(item, Mapping)
            or set(item) != {"name", "value"}
            or not isinstance(item["name"], str)
            or not isinstance(item["value"], str)
        ):
            _fail("header_shape_invalid", "Header pair is invalid", "invalid_request")
        name = item["name"]
        lower = name.lower()
        if not name.isascii() or not _TOKEN.fullmatch(name):
            _fail("header_name_invalid", "Header name is invalid", "invalid_request")
        if lower in seen:
            _fail(
                "duplicate_header", "Duplicate header is forbidden", "invalid_request"
            )
        seen.add(lower)
        if lower in _FORBIDDEN or lower not in _INGRESS_HEADERS:
            _fail("header_forbidden", "Header is not permitted", "unauthorized")
    return []


def _is_message(value: Any) -> bool:
    return isinstance(value, Mapping) and isinstance(value.get("role"), str)


def _messages_preserve_prepared_input(
    prepared: Sequence[Any], emitted: Sequence[Any], authority_sha256: str
) -> bool:
    """Allow only the canonical builder's bounded system-prompt projection."""
    if not all(_is_message(m) for m in emitted):
        return False
    if len(emitted) not in {len(prepared), len(prepared) + 1}:
        return False
    prepared_non_system = [m for m in prepared if m.get("role") != "system"]
    emitted_non_system = [m for m in emitted if m.get("role") != "system"]
    if emitted_non_system != prepared_non_system:
        return False
    emitted_system = [m for m in emitted if m.get("role") == "system"]
    prepared_system = [m for m in prepared if m.get("role") == "system"]
    if len(emitted_system) != 1 or len(prepared_system) > 1:
        return False
    system = emitted_system[0]
    if set(system) != {"role", "content"} or not isinstance(system["content"], str):
        return False
    if hashlib.sha256(system["content"].encode("utf-8")).hexdigest() != authority_sha256:
        return False
    if prepared_system:
        original = prepared_system[0]
        if set(original) != {"role", "content"} or not isinstance(
            original["content"], str
        ):
            return False
        if system["content"].count(original["content"]) != 1:
            return False
    return True


def build_transport_plan(
    resolved: Mapping[str, Any],
    trusted: Mapping[str, Any],
    header_claim: Mapping[str, Any],
    policy: Mapping[str, Any],
    builder: Callable[..., dict[str, Any]],
    *,
    target: str,
    decoder_mode: str,
) -> dict[str, Any]:
    if target not in policy["targets"]:
        _fail(
            "transport_target_unknown",
            "Transport target is unknown",
            "unavailable_profile",
        )
    rule = policy["targets"][target]
    if rule["status"] != "registered" or decoder_mode not in rule["decoder_modes"]:
        _fail(
            "transport_target_unavailable",
            "Transport target is unavailable",
            "unavailable_profile",
        )
    required_trusted = {
        "document_kind",
        "profile",
        "model",
        "snapshot_revision",
        "builder_revision",
        "builder_sha256",
        "capabilities",
        "authority",
    }
    if (
        set(trusted) != required_trusted
        or trusted.get("document_kind") != "trusted_snapshot"
        or not isinstance(trusted.get("capabilities"), Mapping)
        or set(trusted["capabilities"]) != _CAPABILITY_FIELDS
        or not all(
            isinstance(value, bool) for value in trusted["capabilities"].values()
        )
        or not isinstance(trusted.get("authority"), Mapping)
        or set(trusted["authority"])
        != {"system_message_sha256", "chat_template_kwargs"}
        or not isinstance(trusted["authority"].get("system_message_sha256"), str)
        or not re.fullmatch(
            r"[a-f0-9]{64}", trusted["authority"]["system_message_sha256"]
        )
        or not isinstance(
            trusted["authority"].get("chat_template_kwargs"), Mapping
        )
    ):
        _fail(
            "trusted_snapshot_invalid",
            "Trusted transport snapshot is invalid",
            "unauthorized",
        )
    if set(resolved) - _RESOLVED_FIELDS:
        _fail(
            "resolved_plan_fields_invalid",
            "Resolved transport input contains unknown fields",
            "invalid_request",
        )
    if resolved.get("effective_role") not in {
        "orchestrator",
        "architect",
        "implementer",
        "reviewer",
    }:
        _fail("resolved_role_invalid", "Resolved role is invalid", "invalid_request")
    if (
        not isinstance(resolved.get("max_tokens"), int)
        or isinstance(resolved.get("max_tokens"), bool)
        or resolved["max_tokens"] < 1
    ):
        _fail(
            "resolved_max_tokens_invalid",
            "Resolved max_tokens is invalid",
            "invalid_request",
        )
    if not isinstance(resolved.get("temperature"), (int, float)) or isinstance(
        resolved.get("temperature"), bool
    ):
        _fail(
            "resolved_temperature_invalid",
            "Resolved temperature is invalid",
            "invalid_request",
        )
    if not isinstance(resolved.get("task_type"), str) or not resolved["task_type"]:
        _fail(
            "resolved_task_type_invalid",
            "Resolved task_type is invalid",
            "invalid_request",
        )
    if resolved.get("artifact_format", "text") not in {"text", "json"}:
        _fail(
            "resolved_artifact_format_invalid",
            "Resolved artifact_format is invalid",
            "invalid_request",
        )
    canonical = policy["canonical_builder"]
    if (
        trusted["builder_revision"] != canonical["revision"]
        or trusted["builder_sha256"] != canonical["sha256"]
    ):
        _fail(
            "builder_binding_mismatch",
            "Canonical builder binding differs",
            "unauthorized",
        )
    if (
        resolved.get("profile") != trusted["profile"]
        or resolved.get("model") != trusted["model"]
    ):
        _fail(
            "profile_model_binding_mismatch",
            "Resolved route differs from trusted snapshot",
            "unauthorized",
        )
    validate_headers(header_claim, rule)
    messages_before = copy.deepcopy(resolved.get("messages"))
    if not isinstance(messages_before, list) or not all(
        _is_message(m) for m in messages_before
    ):
        _fail("messages_invalid", "Prepared messages are invalid", "invalid_request")
    stream = decoder_mode == "openai_sse"
    caps = trusted["capabilities"]
    if stream and not caps.get("streaming"):
        _fail(
            "streaming_unsupported", "Streaming is unsupported", "unavailable_profile"
        )
    kwargs: dict[str, Any] = {
        "max_tokens": resolved.get("max_tokens"),
        "temperature": resolved.get("temperature"),
        "stream": stream,
        "role": resolved.get("effective_role"),
        "task_type": resolved.get("task_type"),
        "model": trusted["model"],
    }
    artifact_format = resolved.get("artifact_format", "text")
    if artifact_format == "json":
        if not caps.get("response_format"):
            _fail(
                "response_format_unsupported",
                "JSON response format is unsupported",
                "unavailable_profile",
            )
        kwargs["response_format"] = {"type": "json_object"}
    for key in ("stop", "frequency_penalty"):
        if key in resolved:
            kwargs[key] = copy.deepcopy(resolved[key])
    if resolved.get("tools"):
        if not caps.get("tools"):
            _fail("tools_unsupported", "Tools are unsupported", "unauthorized")
        kwargs["tools"] = copy.deepcopy(resolved["tools"])
        kwargs["tool_choice"] = resolved.get("tool_choice", "auto")
    original_resolved = copy.deepcopy(resolved)
    original_trusted = copy.deepcopy(trusted)
    payload = builder(copy.deepcopy(messages_before), **kwargs)
    if resolved != original_resolved or trusted != original_trusted:
        _fail(
            "builder_input_mutation",
            "Builder mutated transport inputs",
            "malformed_result",
        )
    if not isinstance(payload, dict) or not set(payload).issubset(
        set(rule["body_allowlist"])
    ):
        _fail(
            "builder_output_fields_invalid",
            "Builder returned forbidden payload fields",
            "malformed_result",
        )
    if (
        not isinstance(payload.get("messages"), list)
        or not _messages_preserve_prepared_input(
            messages_before,
            payload["messages"],
            trusted["authority"]["system_message_sha256"],
        )
        or payload.get("model") != trusted["model"]
    ):
        _fail(
            "builder_output_binding_invalid",
            "Builder returned invalid messages or model",
            "malformed_result",
        )
    if (
        payload.get("max_tokens") != resolved.get("max_tokens")
        or bool(payload.get("stream", False)) != stream
    ):
        _fail(
            "builder_output_budget_invalid",
            "Builder changed budget or stream mode",
            "malformed_result",
        )
    if payload.get("temperature") != resolved.get("temperature"):
        _fail(
            "builder_output_sampling_invalid",
            "Builder changed sampling configuration",
            "malformed_result",
        )
    defaults = policy["builder_defaults"]
    for key in ("repeat_penalty", "repeat_last_n", "cache_prompt"):
        if payload.get(key) != defaults[key]:
            _fail(
                "builder_output_defaults_invalid",
                "Builder changed a frozen payload default",
                "malformed_result",
            )
    for key in ("stop", "frequency_penalty", "tools", "tool_choice"):
        if key in resolved and payload.get(key) != resolved[key]:
            _fail(
                "builder_output_value_invalid",
                "Builder changed an explicitly resolved value",
                "malformed_result",
            )
        if (
            key not in resolved
            and key in payload
            and key in {"stop", "tools", "tool_choice"}
        ):
            _fail(
                "builder_output_value_invalid",
                "Builder invented a caller-controlled value",
                "malformed_result",
            )
    if stream and payload.get("stream_options") != {"include_usage": True}:
        _fail(
            "builder_output_stream_options_invalid",
            "Streaming usage options are invalid",
            "malformed_result",
        )
    if artifact_format == "json" and payload.get("response_format") != {
        "type": "json_object"
    }:
        _fail(
            "builder_output_response_format_invalid",
            "Builder omitted strict JSON response format",
            "malformed_result",
        )
    if artifact_format != "json" and "response_format" in payload:
        _fail(
            "builder_output_response_format_invalid",
            "Builder invented a response format",
            "malformed_result",
        )
    thinking = payload.get("chat_template_kwargs")
    if (
        not isinstance(thinking, Mapping)
        or set(thinking) - {"enable_thinking", "thinking_budget"}
        or not isinstance(thinking.get("enable_thinking"), bool)
        or (
            "thinking_budget" in thinking
            and (
                not thinking["enable_thinking"]
                or not isinstance(thinking["thinking_budget"], int)
                or isinstance(thinking["thinking_budget"], bool)
                or thinking["thinking_budget"] < 1
            )
        )
    ):
        _fail(
            "thinking_configuration_invalid",
            "Builder returned invalid thinking configuration",
            "malformed_result",
        )
    if dict(thinking) != dict(trusted["authority"]["chat_template_kwargs"]):
        _fail(
            "thinking_configuration_binding_mismatch",
            "Builder thinking configuration differs from the trusted snapshot",
            "unauthorized",
        )
    if thinking["enable_thinking"] and not caps.get("thinking"):
        _fail(
            "thinking_unsupported",
            "Builder enabled unsupported thinking",
            "malformed_result",
        )
    if payload.get("cache_prompt") and not caps.get("cache_prompt"):
        _fail(
            "cache_unsupported", "Builder enabled unsupported cache", "malformed_result"
        )
    headers = [
        {
            "name": "accept",
            "value": "text/event-stream" if stream else "application/json",
        },
        {"name": "content-type", "value": "application/json"},
    ]
    generated = {
        "x-agent-role": resolved.get("effective_role"),
        "x-ai-profile": trusted["profile"],
        "x-profile-snapshot-revision": trusted["snapshot_revision"],
    }
    for name, value in generated.items():
        if name in rule["header_allowlist"] and isinstance(value, str):
            headers.append({"name": name, "value": value})
    headers.sort(key=lambda item: item["name"])
    semantic = {
        "profile": trusted["profile"],
        "model": trusted["model"],
        "snapshot_revision": trusted["snapshot_revision"],
        "payload": payload,
    }
    wire = {"headers": headers, "payload": payload}
    output = {
        "document_kind": "canonical_output",
        "headers": headers,
        "payload": payload,
        "canonical_wire_utf8": canonical_bytes(wire).decode("utf-8"),
        "semantic_digest": _digest(policy["digest_version"] + ":semantic", semantic),
        "wire_digest": _digest(policy["digest_version"] + ":wire", wire),
    }
    return {
        "document_kind": "transport_plan",
        "contract_version": "1.0",
        "policy_version": policy["policy_version"],
        "adapter_version": policy["adapter_version"],
        "digest_version": policy["digest_version"],
        "target": target,
        "decoder_mode": decoder_mode,
        "snapshot_revision": trusted["snapshot_revision"],
        "canonical": output,
    }


class TransportDecoder:
    def __init__(
        self,
        mode: str,
        identity: Mapping[str, str],
        limits: Mapping[str, int],
        *,
        artifact_format: str = "text",
    ):
        if mode not in {"buffered_json", "openai_sse"}:
            _fail("decoder_mode_invalid", "Decoder mode is invalid", "invalid_request")
        if set(identity) != {"request_id", "run_id", "trace_id"}:
            _fail(
                "transport_identity_invalid",
                "Transport identity is invalid",
                "invalid_request",
            )
        self.mode, self.identity, self.limits = mode, dict(identity), dict(limits)
        if artifact_format not in {"text", "json"}:
            _fail(
                "artifact_format_invalid",
                "Artifact format is invalid",
                "invalid_request",
            )
        self.artifact_format = artifact_format
        self._decoder = codecs.getincrementaldecoder("utf-8")("strict")
        self._text = ""
        self._total = 0
        self._cancelled = False
        self._terminal = False
        self._raw_line_bytes = 0
        self._raw_event_bytes = 0
        self._raw_pending_cr = False
        self._text_pending_cr = False
        self._sse_buffer = ""
        self._sse_documents: list[dict[str, Any]] = []
        self._sse_done = 0
        self._sse_upstream_error = False

    def feed(self, data: bytes) -> None:
        if self._terminal or self._cancelled:
            _fail(
                "post_terminal_bytes",
                "Bytes arrived after terminal state",
                "malformed_result",
            )
        if not isinstance(data, bytes):
            _fail(
                "transport_bytes_required",
                "Decoder accepts bytes only",
                "invalid_request",
            )
        self._total += len(data)
        if self._total > self.limits["max_total_bytes"]:
            _fail(
                "transport_total_oversized",
                "Transport exceeds total byte limit",
                "malformed_result",
            )
        if self.mode == "openai_sse":
            self._scan_sse_bytes(data)
        try:
            decoded = self._decoder.decode(data, final=False)
        except UnicodeDecodeError as exc:
            raise TransportError(
                "malformed_result", "invalid_utf8", "Transport is not strict UTF-8"
            ) from exc
        if self.mode == "buffered_json":
            self._text += decoded
        else:
            self._consume_sse_text(self._normalize_sse_text(decoded))

    def _scan_sse_bytes(self, data: bytes) -> None:
        for byte in data:
            if self._raw_pending_cr:
                self._raw_pending_cr = False
                if byte == 0x0A:
                    continue
            if byte in {0x0A, 0x0D}:
                if self._raw_line_bytes == 0:
                    self._raw_event_bytes = 0
                self._raw_line_bytes = 0
                self._raw_pending_cr = byte == 0x0D
                continue
            self._raw_line_bytes += 1
            self._raw_event_bytes += 1
            if self._raw_line_bytes > self.limits["max_line_bytes"]:
                _fail(
                    "sse_line_oversized",
                    "SSE line exceeds limit",
                    "malformed_result",
                )
            if self._raw_event_bytes > self.limits["max_event_bytes"]:
                _fail(
                    "sse_event_oversized",
                    "SSE event exceeds limit",
                    "malformed_result",
                )

    def _normalize_sse_text(self, text: str, *, final: bool = False) -> str:
        normalized: list[str] = []
        index = 0
        if self._text_pending_cr:
            normalized.append("\n")
            self._text_pending_cr = False
            if text.startswith("\n"):
                index = 1
        while index < len(text):
            char = text[index]
            if char == "\r":
                if index + 1 < len(text):
                    normalized.append("\n")
                    if text[index + 1] == "\n":
                        index += 1
                elif final:
                    normalized.append("\n")
                else:
                    self._text_pending_cr = True
            else:
                normalized.append(char)
            index += 1
        if final and self._text_pending_cr:
            normalized.append("\n")
            self._text_pending_cr = False
        return "".join(normalized)

    def _consume_sse_text(self, text: str) -> None:
        self._sse_buffer += text
        while "\n\n" in self._sse_buffer:
            block, self._sse_buffer = self._sse_buffer.split("\n\n", 1)
            self._accept_sse_block(block)

    def _accept_sse_block(self, block: str) -> None:
        data_lines: list[str] = []
        for line in block.split("\n"):
            if not line or line.startswith(":"):
                continue
            if not line.startswith("data:"):
                _fail(
                    "sse_field_invalid",
                    "Only SSE data fields are supported",
                    "malformed_result",
                )
            data_lines.append(line[5:].lstrip(" "))
        joined = "\n".join(data_lines)
        if self._sse_done:
            if joined == "[DONE]":
                _fail("duplicate_done", "SSE has duplicate DONE", "malformed_result")
            _fail(
                "post_terminal_bytes",
                "Bytes follow the SSE terminal marker",
                "malformed_result",
            )
        if not data_lines:
            return
        if len(joined.encode("utf-8")) > self.limits["max_event_bytes"]:
            _fail("sse_event_oversized", "SSE event exceeds limit", "malformed_result")
        if joined == "[DONE]":
            self._sse_done = 1
            return
        document = parse_exact_json(joined)
        if "error" in document:
            if self._sse_upstream_error:
                _fail(
                    "upstream_error_conflict",
                    "Upstream error is duplicated",
                    "malformed_result",
                )
            self._sse_upstream_error = True
        elif self._sse_upstream_error:
            _fail(
                "post_error_event",
                "SSE data follows upstream error",
                "malformed_result",
            )
        self._sse_documents.append(document)
        if len(self._sse_documents) > self.limits["max_events"]:
            _fail(
                "sse_event_count_oversized",
                "SSE event count exceeds limit",
                "malformed_result",
            )

    def cancel(self) -> list[dict[str, Any]]:
        if self._terminal:
            _fail(
                "already_terminal", "Transport is already terminal", "malformed_result"
            )
        if self._cancelled:
            return []
        self._cancelled = True
        return [self._obs(1, "cancelled", {})]

    def _obs(self, sequence: int, kind: str, data: dict[str, Any]) -> dict[str, Any]:
        return {
            "document_kind": "transport_observation",
            "identity": dict(self.identity),
            "sequence": sequence,
            "kind": kind,
            "data": data,
        }

    def finish(self) -> dict[str, Any]:
        if self._cancelled:
            return self._summary(
                "cancelled", [self._obs(1, "cancelled", {})], "", [], None, None
            )
        if self._terminal:
            _fail("duplicate_finish", "Decoder already finished", "malformed_result")
        try:
            decoded = self._decoder.decode(b"", final=True)
        except UnicodeDecodeError as exc:
            raise TransportError(
                "malformed_result", "truncated_utf8", "Transport ends in partial UTF-8"
            ) from exc
        if self.mode == "buffered_json":
            self._text += decoded
        else:
            self._consume_sse_text(self._normalize_sse_text(decoded, final=True))
        result = (
            self._decode_buffered()
            if self.mode == "buffered_json"
            else self._decode_sse()
        )
        self._terminal = True
        return result

    def _decode_buffered(self) -> dict[str, Any]:
        if "[DONE]" in self._text:
            _fail(
                "done_in_buffered_json",
                "Buffered JSON cannot contain DONE",
                "malformed_result",
            )
        return self._decode_documents(
            [parse_exact_json(self._text)], done_required=False
        )

    def _decode_sse(self) -> dict[str, Any]:
        if self._sse_buffer:
            if self._sse_done:
                _fail(
                    "post_terminal_bytes",
                    "Bytes follow the SSE terminal marker",
                    "malformed_result",
                )
            _fail(
                "sse_truncated_eof",
                "SSE ended without an event separator",
                "malformed_result",
            )
        if not self._sse_upstream_error and self._sse_done != 1:
            _fail(
                "sse_done_missing",
                "Successful SSE requires one DONE",
                "malformed_result",
            )
        return self._decode_documents(
            self._sse_documents, done_required=not self._sse_upstream_error
        )

    def _decode_documents(
        self, documents: Sequence[Mapping[str, Any]], done_required: bool
    ) -> dict[str, Any]:
        observations: list[dict[str, Any]] = []
        content = ""
        usage = None
        finish = None
        tools: dict[int, dict[str, Any]] = {}
        seq = 1
        error_seen = False
        for doc in documents:
            if not isinstance(doc, Mapping):
                _fail(
                    "upstream_document_invalid",
                    "Upstream document is invalid",
                    "malformed_result",
                )
            if "error" in doc:
                error = doc["error"]
                if (
                    set(doc) != {"error"}
                    or not isinstance(error, Mapping)
                    or set(error) - {"message", "type", "code", "param"}
                    or not isinstance(error.get("message"), str)
                    or len(error["message"]) > 512
                    or any(
                        value is not None and not isinstance(value, (str, int))
                        for value in error.values()
                    )
                ):
                    _fail(
                        "upstream_error_invalid",
                        "Upstream error object is invalid",
                        "malformed_result",
                    )
                if error_seen or observations:
                    _fail(
                        "upstream_error_conflict",
                        "Upstream error conflicts with prior data",
                        "malformed_result",
                    )
                error_seen = True
                observations.append(
                    self._obs(seq, "upstream_error", {"error": doc["error"]})
                )
                seq += 1
                continue
            if set(doc) - {"choices", "usage"} or "choices" not in doc:
                _fail(
                    "upstream_fields_invalid",
                    "Upstream document contains unknown fields",
                    "malformed_result",
                )
            if error_seen:
                _fail(
                    "post_error_event",
                    "Data follows upstream error",
                    "malformed_result",
                )
            choices = doc.get("choices", [])
            if not isinstance(choices, list):
                _fail("choices_invalid", "Choices must be an array", "malformed_result")
            for choice in choices:
                if (
                    not isinstance(choice, Mapping)
                    or set(choice) - {"index", "delta", "message", "finish_reason"}
                    or ("delta" in choice) == ("message" in choice)
                    or (
                        "index" in choice
                        and (
                            not isinstance(choice["index"], int)
                            or isinstance(choice["index"], bool)
                            or choice["index"] < 0
                        )
                    )
                ):
                    _fail(
                        "choice_fields_invalid",
                        "Upstream choice contains unknown or invalid fields",
                        "malformed_result",
                    )
                delta = choice.get("delta", choice.get("message")) or {}
                if not isinstance(delta, Mapping) or set(delta) - {
                    "content",
                    "tool_calls",
                }:
                    _fail(
                        "delta_fields_invalid",
                        "Upstream delta contains unknown fields",
                        "malformed_result",
                    )
                piece = delta.get("content")
                if piece is not None:
                    if (
                        finish is not None
                        or usage is not None
                        or not isinstance(piece, str)
                    ):
                        _fail(
                            "content_order_invalid",
                            "Content ordering is invalid",
                            "malformed_result",
                        )
                    content += piece
                    observations.append(self._obs(seq, "content", {"content": piece}))
                    seq += 1
                fragments = delta.get("tool_calls", []) or []
                if not isinstance(fragments, list):
                    _fail(
                        "tool_fragments_invalid",
                        "Tool fragments must be an array",
                        "malformed_result",
                    )
                for fragment in fragments:
                    if not isinstance(fragment, Mapping) or set(fragment) - {
                        "index",
                        "id",
                        "type",
                        "function",
                    }:
                        _fail(
                            "tool_fragment_fields_invalid",
                            "Tool fragment contains unknown fields",
                            "malformed_result",
                        )
                    index = fragment.get("index")
                    if (
                        not isinstance(index, int)
                        or isinstance(index, bool)
                        or index < 0
                        or finish is not None
                    ):
                        _fail(
                            "tool_fragment_invalid",
                            "Tool fragment index is invalid",
                            "malformed_result",
                        )
                    fn = fragment.get("function") or {}
                    if not isinstance(fn, Mapping) or set(fn) - {"name", "arguments"}:
                        _fail(
                            "tool_function_fields_invalid",
                            "Tool function fragment contains unknown fields",
                            "malformed_result",
                        )
                    if index not in tools and (
                        not isinstance(fragment.get("id"), str)
                        or not fragment["id"]
                        or not isinstance(fragment.get("type"), str)
                        or not fragment["type"]
                        or not isinstance(fn.get("name"), str)
                        or not fn["name"]
                    ):
                        _fail(
                            "tool_identity_first_fragment_missing",
                            "First tool fragment must establish identity",
                            "malformed_result",
                        )
                    state = tools.setdefault(
                        index,
                        {
                            "index": index,
                            "id": fragment.get("id"),
                            "type": fragment.get("type"),
                            "name": fn.get("name"),
                            "arguments": "",
                        },
                    )
                    for key, observed in (
                        ("id", fragment.get("id")),
                        ("type", fragment.get("type")),
                        ("name", fn.get("name")),
                    ):
                        if observed is not None:
                            if state[key] is not None and state[key] != observed:
                                _fail(
                                    "tool_identity_drift",
                                    "Tool identity changed",
                                    "malformed_result",
                                )
                            state[key] = observed
                    args = fn.get("arguments", "")
                    if not isinstance(args, str):
                        _fail(
                            "tool_arguments_invalid",
                            "Tool arguments fragment is invalid",
                            "malformed_result",
                        )
                    state["arguments"] += args
                observed_finish = choice.get("finish_reason")
                if observed_finish is not None:
                    if not isinstance(observed_finish, str) or finish is not None:
                        _fail(
                            "duplicate_finish_reason",
                            "Finish reason is duplicated",
                            "malformed_result",
                        )
                    finish = observed_finish
            if doc.get("usage") is not None:
                if usage is not None:
                    _fail("duplicate_usage", "Usage is duplicated", "malformed_result")
                if finish is None:
                    _fail(
                        "usage_before_finish",
                        "Usage precedes the finish reason",
                        "malformed_result",
                    )
                candidate_usage = doc["usage"]
                if (
                    not isinstance(candidate_usage, Mapping)
                    or set(candidate_usage)
                    - {"prompt_tokens", "completion_tokens", "total_tokens"}
                    or any(
                        not isinstance(value, int)
                        or isinstance(value, bool)
                        or value < 0
                        for value in candidate_usage.values()
                    )
                ):
                    _fail(
                        "usage_invalid",
                        "Usage snapshot is invalid",
                        "malformed_result",
                    )
                usage = dict(candidate_usage)
        if error_seen:
            return self._summary("upstream_error", observations, "", [], None, None)
        if finish is None:
            _fail(
                "finish_reason_missing",
                "Successful response lacks finish reason",
                "malformed_result",
            )
        completed_tools = []
        for index in sorted(tools):
            tool = tools[index]
            if not all(tool[key] for key in ("id", "type", "name")):
                _fail(
                    "tool_identity_incomplete",
                    "Tool identity is incomplete",
                    "malformed_result",
                )
            arguments = parse_exact_json(tool["arguments"])
            item = {**tool, "arguments": arguments}
            completed_tools.append(item)
            observations.append(self._obs(seq, "tool_call", item))
            seq += 1
        observations.append(self._obs(seq, "finish", {"reason": finish}))
        seq += 1
        if usage is not None:
            observations.append(self._obs(seq, "usage", {"usage": usage}))
            seq += 1
        observations.append(self._obs(seq, "done", {}))
        if self.artifact_format == "json":
            parse_exact_json(content)
        return self._summary(
            "done", observations, content, completed_tools, usage, finish
        )

    def _summary(
        self,
        state: str,
        observations: list[dict[str, Any]],
        content: str,
        tools: list[dict[str, Any]],
        usage: Any,
        finish: Any,
    ) -> dict[str, Any]:
        return {
            "document_kind": "decode_summary",
            "mode": self.mode,
            "terminal_state": state,
            "content": content,
            "tool_calls": tools,
            "usage": usage,
            "finish_reason": finish,
            "output_digest": _digest(
                "transport-output-v1", {"content": content, "tool_calls": tools}
            )
            if state == "done"
            else None,
            "observations": observations,
        }


def assemble_terminal_candidate(
    event: Mapping[str, Any],
    result: Mapping[str, Any],
    *,
    event_schema: Mapping[str, Any],
    result_schema: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(event, Mapping) or not isinstance(result, Mapping):
        _fail(
            "candidate_evidence_missing",
            "Terminal candidate evidence is missing",
            "malformed_result",
        )
    required_result = {"usage", "timing", "provenance", "resolved_plan"}
    if not required_result.issubset(result):
        _fail(
            "candidate_evidence_missing",
            "Terminal candidate lacks mandatory evidence",
            "malformed_result",
        )
    _validate(event, event_schema)
    _validate(result, result_schema)
    return {
        "document_kind": "v1_candidate_wrapper",
        "candidate_kind": "terminal_candidate",
        "authoritative": False,
        "event": copy.deepcopy(dict(event)),
        "result": copy.deepcopy(dict(result)),
    }



# ─── L2B-B — pure payload normalization & canonical transformer ────────────
# Enforces the four L2B-B invariants ahead of dispatch to either local
# endpoint: (1) NFC UTF-8 + key-sorted canonical form, (2) non-finite floats
# removed rather than rejected outright, (3) no external credential fields
# ever touch the normalized envelope, (4) fail-closed schema validation with
# an opaque, non-leaking rejection on any violation.

_NORMALIZATION_ENDPOINTS = {"/v1/chat/completions", "/v1/completions"}

_FORBIDDEN_PAYLOAD_KEYS = {
    "authorization",
    "api_key",
    "apikey",
    "api-key",
    "bearer_token",
    "cookie",
    "proxy-authorization",
    "x-api-key",
}

# Approximate resident VRAM footprint per known local model, used only to
# enforce the single-model 27 GB budget below — never to route or dispatch.
_KNOWN_MODEL_VRAM_GB: dict[str, float] = {
    "qwen3-35b": 22.5,
    "qwen3-8b": 8.0,
    "llama-8b": 8.0,
}

_VRAM_BUDGET_GB = 27.0


def _scan_forbidden_keys(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, val in value.items():
            if isinstance(key, str) and key.lower() in _FORBIDDEN_PAYLOAD_KEYS:
                _fail(
                    "forbidden_credential_field",
                    "Payload must not carry external credential fields",
                    "unauthorized",
                )
            _scan_forbidden_keys(val)
    elif isinstance(value, list):
        for item in value:
            _scan_forbidden_keys(item)


def _reject_non_string_keys(value: Any) -> None:
    """Fail closed on any non-string mapping key before it can reach a bare
    comparison (e.g. ``sorted()``) that would raise an uncaught ``TypeError``.
    """
    if isinstance(value, Mapping):
        for key, val in value.items():
            if not isinstance(key, str):
                _fail(
                    "normalization_key_invalid",
                    "Payload object keys must be strings",
                    "invalid_request",
                )
            _reject_non_string_keys(val)
    elif isinstance(value, list):
        for item in value:
            _reject_non_string_keys(item)


def _strip_non_finite(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Mapping):
        return {key: _strip_non_finite(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_strip_non_finite(item) for item in value]
    return value


def _nfc_normalize(value: Any) -> Any:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, Mapping):
        # Keys are guaranteed str by `_reject_non_string_keys` before this
        # runs; normalize them to NFC same as values so a decomposed-Unicode
        # key canonicalizes deterministically instead of slipping through.
        return {
            unicodedata.normalize("NFC", key): _nfc_normalize(val)
            for key, val in value.items()
        }
    if isinstance(value, list):
        return [_nfc_normalize(item) for item in value]
    return value


def _deep_sorted(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _deep_sorted(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_deep_sorted(item) for item in value]
    return value


def validate_vram_budget(
    resident_vram_gb: Mapping[str, float], *, budget_gb: float = _VRAM_BUDGET_GB
) -> None:
    """Reject concurrent model residency exceeding the strict VRAM budget."""
    if not isinstance(resident_vram_gb, Mapping) or not resident_vram_gb:
        _fail(
            "vram_budget_shape_invalid",
            "Resident VRAM declaration is invalid",
            "invalid_request",
        )
    total = 0.0
    for name, size in resident_vram_gb.items():
        if (
            not isinstance(name, str)
            or not isinstance(size, (int, float))
            or isinstance(size, bool)
            or size < 0
        ):
            _fail(
                "vram_budget_shape_invalid",
                "Resident VRAM declaration is invalid",
                "invalid_request",
            )
        total += float(size)
    if total > budget_gb:
        _fail(
            "vram_budget_exceeded",
            "Concurrent model residency exceeds the VRAM budget",
            "unavailable_profile",
        )


def normalize_endpoint_payload(
    payload: Mapping[str, Any], *, endpoint: str
) -> dict[str, Any]:
    """Pure, deterministic canonical-form normalization for one dispatch payload.

    Applies NFC UTF-8 normalization, recursive key sorting, and non-finite
    float removal. Never mutates the input; never performs I/O.
    """
    if endpoint not in _NORMALIZATION_ENDPOINTS:
        _fail(
            "normalization_endpoint_unknown",
            "Normalization endpoint is unknown",
            "unavailable_profile",
        )
    if not isinstance(payload, Mapping):
        _fail(
            "normalization_payload_invalid",
            "Normalization payload must be a JSON object",
            "invalid_request",
        )
    _reject_non_string_keys(payload)
    _scan_forbidden_keys(payload)
    working = _strip_non_finite(copy.deepcopy(dict(payload)))
    working = _nfc_normalize(working)
    return _deep_sorted(working)


def canonical_transformer(
    payload: Mapping[str, Any],
    *,
    endpoint: str,
    repo_root: Path,
    resident_vram_gb: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Normalize, schema-validate, and canonically transform a dispatch payload.

    Fail-closed: any invariant violation (unknown endpoint, malformed shape,
    forbidden credential field, VRAM budget breach, or schema mismatch)
    returns a ``REJECTED_SCHEMA_INVALID`` envelope carrying only a safe
    message and reason code — never a raw exception, stack trace, or file
    system path.
    """
    try:
        if resident_vram_gb is not None:
            validate_vram_budget(resident_vram_gb)
        normalized = normalize_endpoint_payload(payload, endpoint=endpoint)
        envelope: dict[str, Any] = {
            "document_kind": "normalized_local_inference_payload",
            "schema_version": "1",
            "endpoint": endpoint,
            "payload": normalized,
        }
        if resident_vram_gb is not None:
            envelope["resident_vram_gb"] = _deep_sorted(dict(resident_vram_gb))
        schema = _schema(repo_root, "local-inference-payload-v1.json")
        _validate(envelope, schema)
        wire = canonical_bytes(envelope)
        return {
            "document_kind": "normalization_result",
            "status": "ACCEPTED",
            "endpoint": endpoint,
            "canonical_wire_utf8": wire.decode("utf-8"),
            "schema_signature": _digest("local-inference-payload-v1:schema", envelope),
        }
    except TransportError as exc:
        return {
            "document_kind": "normalization_result",
            "status": "REJECTED_SCHEMA_INVALID",
            "endpoint": endpoint,
            "reason_code": exc.reason_code,
            "message": exc.safe_message,
            "audit_trace": {"code": exc.code, "reason_code": exc.reason_code},
        }


_ASSETS = (
    "config/local-inference-transport-policy.json",
    "config/schemas/local-inference-transport.schema.json",
    "config/schemas/local-inference-transport-policy.schema.json",
    "config/schemas/local-inference-payload-v1.json",
    "scripts/ai/lib/local_inference_transport.py",
    "scripts/testing/fixtures/local-inference-l2b-payload-golden.json",
    "scripts/testing/fixtures/local-inference-l2b-stream-golden.json",
    "scripts/testing/fixtures/l2b_b_golden_payloads.json",
)


def transport_asset_digest(repo_root: Path) -> str:
    digest = hashlib.sha256()
    for rel in _ASSETS:
        digest.update(rel.encode() + b"\0" + (repo_root / rel).read_bytes() + b"\0")
    return digest.hexdigest()


def characterize_source_shapes(
    repo_root: Path, source_shapes: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Execute bounded literal source predicates from the committed parity fixture."""
    results: list[dict[str, Any]] = []
    for shape in source_shapes:
        rel = shape.get("path")
        predicates = shape.get("predicates")
        if not isinstance(rel, str) or not isinstance(predicates, list) or not predicates:
            _fail(
                "source_shape_invalid",
                "Source-shape evidence is malformed",
                "malformed_result",
            )
        source = (repo_root / rel).read_text(encoding="utf-8")
        passed = True
        for predicate in predicates:
            if (
                not isinstance(predicate, Mapping)
                or set(predicate) != {"kind", "literal", "min_count"}
                or predicate.get("kind") not in {"contains", "absent"}
                or not isinstance(predicate.get("literal"), str)
                or not predicate["literal"]
                or not isinstance(predicate.get("min_count"), int)
                or isinstance(predicate["min_count"], bool)
                or predicate["min_count"] < 1
            ):
                _fail(
                    "source_shape_predicate_invalid",
                    "Source-shape predicate is malformed",
                    "malformed_result",
                )
            count = source.count(predicate["literal"])
            predicate_passed = (
                count >= predicate["min_count"]
                if predicate["kind"] == "contains"
                else count == 0
            )
            passed = passed and predicate_passed
        results.append({"id": shape.get("id"), "path": rel, "passed": passed})
    return {
        "status": "pass" if results and all(item["passed"] for item in results) else "fail",
        "count": len(results),
        "results": results,
    }


def transport_health(repo_root: Path) -> dict[str, Any]:
    default = {
        "status": "unavailable",
        "mode": "shadow_fixture_only",
        "policy_version": "unknown",
        "adapter_version": "unknown",
        "digest_version": "unknown",
        "schema_status": "unavailable",
        "payload_parity": "unavailable",
        "stream_parity": "unavailable",
        "source_shape_parity": "unavailable",
        "actual_ssot_parity": "unavailable",
        "payload_normalization_status": "unavailable",
        "target_decisions": {},
        "payload_vector_count": 0,
        "stream_vector_count": 0,
        "digest": None,
        "freshness": "commit_fixture",
        "reason_code": "transport_assets_missing",
    }
    try:
        policy = load_policy(repo_root)
        transport_schema = _schema(repo_root, "local-inference-transport.schema.json")
        _validate(
            {
                "document_kind": "parser_fault",
                "code": "transport_error",
                "reason_code": "fixture_probe",
                "message": "probe",
                "retryable": False,
            },
            transport_schema,
        )
        payload_fixture = parse_exact_json(
            (
                repo_root
                / "scripts/testing/fixtures/local-inference-l2b-payload-golden.json"
            ).read_bytes()
        )
        stream_fixture = parse_exact_json(
            (
                repo_root
                / "scripts/testing/fixtures/local-inference-l2b-stream-golden.json"
            ).read_bytes()
        )
        payload_count = len(payload_fixture.get("vectors", []))
        stream_count = len(stream_fixture.get("vectors", []))
        if payload_count < 1 or stream_count < 1:
            _fail(
                "transport_fixture_empty",
                "Transport fixtures are empty",
                "malformed_result",
            )
        shape_health = characterize_source_shapes(
            repo_root, payload_fixture.get("source_shapes", [])
        )
        if shape_health["status"] != "pass":
            _fail(
                "source_shape_parity_mismatch",
                "Executable source-shape parity failed",
                "malformed_result",
            )
        actual_vectors = payload_fixture.get("actual_ssot_vectors", [])
        if not actual_vectors:
            _fail(
                "actual_ssot_vectors_missing",
                "Actual builder parity vectors are missing",
                "malformed_result",
            )
        for vector in actual_vectors:
            wire = parse_exact_json(vector["expected_canonical_wire_utf8"].encode("utf-8"))
            system_messages = [
                item
                for item in wire.get("payload", {}).get("messages", [])
                if item.get("role") == "system"
            ]
            if (
                len(system_messages) != 1
                or hashlib.sha256(
                    system_messages[0]["content"].encode("utf-8")
                ).hexdigest()
                != vector.get("expected_system_message_sha256")
                or wire["payload"].get("chat_template_kwargs")
                != vector.get("expected_chat_template_kwargs")
            ):
                _fail(
                    "actual_ssot_vector_invalid",
                    "Actual builder parity vector authority is invalid",
                    "malformed_result",
                )
        for rel, expected in payload_fixture.get("live_source_manifest", {}).items():
            path = repo_root / rel
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                _fail(
                    "live_source_manifest_drift",
                    "Frozen live source hash changed",
                    "malformed_result",
                )
            if "local_inference_transport" in path.read_text(encoding="utf-8"):
                _fail(
                    "live_transport_adopted",
                    "Live source imported shadow transport",
                    "malformed_result",
                )
        trusted = {
            "document_kind": "trusted_snapshot",
            "profile": "continue-local",
            "model": "fixture-model",
            "snapshot_revision": "fixture-snapshot-v1",
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
                    b"[Role: implementer] transport health fixture"
                ).hexdigest(),
                "chat_template_kwargs": {"enable_thinking": False},
            },
        }
        resolved = {
            "profile": "continue-local",
            "model": "fixture-model",
            "messages": [{"role": "user", "content": "fixture"}],
            "max_tokens": 32,
            "temperature": 0.0,
            "effective_role": "implementer",
            "task_type": "structured",
            "artifact_format": "text",
            "frequency_penalty": 0.0,
        }

        def fixture_builder(messages: list, **kwargs: Any) -> dict[str, Any]:
            emitted_messages = copy.deepcopy(messages)
            emitted_messages.insert(
                0,
                {
                    "role": "system",
                    "content": f"[Role: {kwargs['role']}] transport health fixture",
                },
            )
            built = {
                "messages": emitted_messages,
                "model": kwargs["model"],
                "max_tokens": kwargs["max_tokens"],
                "temperature": kwargs["temperature"],
                "stream": kwargs["stream"],
                "frequency_penalty": kwargs["frequency_penalty"],
                "chat_template_kwargs": {"enable_thinking": False},
                "cache_prompt": True,
                "repeat_penalty": policy["builder_defaults"]["repeat_penalty"],
                "repeat_last_n": policy["builder_defaults"]["repeat_last_n"],
            }
            if kwargs["stream"]:
                built["stream_options"] = {"include_usage": True}
            return built

        for vector in payload_fixture["vectors"]:
            target = vector.get("target")
            if target == "ralph":
                if policy["targets"][target]["status"] != "unavailable_route_contract":
                    _fail(
                        "ralph_fixture_invalid",
                        "Ralph must remain unavailable",
                        "malformed_result",
                    )
                continue
            build_transport_plan(
                resolved,
                trusted,
                {"document_kind": "untrusted_header_claim", "headers": []},
                policy,
                fixture_builder,
                target=target,
                decoder_mode=vector["mode"],
            )
        for vector in stream_fixture["vectors"]:
            raw = "".join(vector["chunks"]).encode("utf-8")
            whole = TransportDecoder(
                vector["mode"],
                {
                    "request_id": "11111111-1111-4111-8111-111111111111",
                    "run_id": "22222222-2222-4222-8222-222222222222",
                    "trace_id": "33333333-3333-4333-8333-333333333333",
                },
                policy["limits"],
            )
            whole.feed(raw)
            one = whole.finish()
            split = TransportDecoder(vector["mode"], whole.identity, policy["limits"])
            for byte in raw:
                split.feed(bytes([byte]))
            if one != split.finish():
                _fail(
                    "stream_fixture_parity_mismatch",
                    "Stream split parity failed",
                    "malformed_result",
                )
        normalization_probe = canonical_transformer(
            {
                "model": "fixture-model",
                "messages": [{"role": "user", "content": "normalization probe"}],
                "max_tokens": 1,
                "temperature": 0.0,
            },
            endpoint="/v1/chat/completions",
            repo_root=repo_root,
        )
        if normalization_probe["status"] != "ACCEPTED":
            _fail(
                "payload_normalization_probe_failed",
                "Payload normalization self-check failed",
                "malformed_result",
            )
        return {
            "status": "healthy",
            "mode": "shadow_fixture_only",
            "policy_version": policy["policy_version"],
            "adapter_version": policy["adapter_version"],
            "digest_version": policy["digest_version"],
            "schema_status": "valid",
            "payload_parity": "pass",
            "stream_parity": "pass",
            "source_shape_parity": "pass",
            "actual_ssot_parity": "pass",
            "payload_normalization_status": "pass",
            "target_decisions": {
                name: value["status"] for name, value in policy["targets"].items()
            },
            "payload_vector_count": payload_count,
            "actual_ssot_vector_count": len(actual_vectors),
            "source_shape_count": shape_health["count"],
            "stream_vector_count": stream_count,
            "digest": transport_asset_digest(repo_root),
            "freshness": "commit_fixture",
            "reason_code": "transport_fixture_parity_pass",
        }
    except FileNotFoundError:
        return default
    except TransportError:
        return {
            **default,
            "status": "degraded",
            "schema_status": "invalid",
            "payload_parity": "fail",
            "stream_parity": "fail",
            "source_shape_parity": "fail",
            "actual_ssot_parity": "fail",
            "payload_normalization_status": "fail",
            "reason_code": "transport_fixture_invalid",
        }
    except Exception:
        return {
            **default,
            "status": "degraded",
            "payload_parity": "fail",
            "stream_parity": "fail",
            "source_shape_parity": "fail",
            "actual_ssot_parity": "fail",
            "payload_normalization_status": "fail",
            "reason_code": "transport_fixture_invalid",
        }


__all__ = [
    "TransportDecoder",
    "TransportError",
    "assemble_terminal_candidate",
    "build_transport_plan",
    "canonical_bytes",
    "canonical_transformer",
    "characterize_source_shapes",
    "load_policy",
    "normalize_endpoint_payload",
    "parse_exact_json",
    "transport_asset_digest",
    "transport_health",
    "validate_headers",
    "validate_vram_budget",
]
