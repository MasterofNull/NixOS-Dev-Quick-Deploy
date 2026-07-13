#!/usr/bin/env python3
"""Pure L2A context preparation primitives.

This module is shadow-only. It performs no filesystem, environment, clock,
network, model, subprocess, logging, lifecycle, or telemetry operations.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class ContextError(ValueError):
    code: str
    reason_code: str
    safe_message: str

    def __str__(self) -> str:
        return f"{self.code}:{self.reason_code}"


_RULES = {
    "credential_assignment": re.compile(
        r"(?i)\b(api[_-]?key|access[_-]?token|password|secret)\b(\s*[:=]\s*)([^\s,;]+)"
    ),
    "bearer_token": re.compile(r"(?i)\bBearer\s+([A-Za-z0-9._~+/-]{8,})"),
    "private_key": re.compile(
        r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
        re.DOTALL,
    ),
    "email_address": re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"),
}
_REDACTED_VALUE = re.compile(r"\[REDACTED:[a-z_]+:[0-9a-f]{64}\]")


def _fail(reason: str, message: str, code: str = "invalid_request") -> None:
    raise ContextError(code, reason, message)


def _nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def _digest(value: str) -> str:
    return hashlib.sha256(_nfc(value).encode("utf-8")).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ContextError("invalid_request", "context_not_canonical", "Context is not canonical JSON") from exc


def parse_exact_json(raw: str | bytes) -> dict[str, Any]:
    """Parse one exact JSON object; prose, fences, duplicate keys, and NaN fail."""
    text = raw.decode("utf-8") if isinstance(raw, bytes) else raw

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            key = _nfc(key)
            if key in result:
                _fail("duplicate_json_key", "JSON contains a duplicate key")
            result[key] = value
        return result

    def nonfinite(_value: str) -> None:
        _fail("non_finite_number", "JSON contains a non-finite number")

    try:
        value = json.loads(text, object_pairs_hook=pairs, parse_constant=nonfinite)
    except ContextError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContextError("invalid_request", "strict_json_invalid", "Response must be exact JSON") from exc
    if not isinstance(value, dict):
        _fail("strict_json_not_object", "Response must be one JSON object")
    return value


def strict_json_metadata(artifact_format: str, response_format_supported: bool) -> dict[str, Any]:
    """Return shadow-only metadata; never place it in v1 request/resolved-plan bytes."""
    if artifact_format != "json":
        return {"contract": None, "response_format": None, "wire_visibility": "shadow_internal_until_l2b"}
    return {
        "contract": "exact_json_only",
        "response_format": {"type": "json_object"} if response_format_supported else None,
        "wire_visibility": "shadow_internal_until_l2b",
    }


def validate_message_order(messages: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Validate the v1 message/call-id ordering contract and return an NFC copy."""
    normalized: list[dict[str, Any]] = []
    seen_call_ids: set[str] = set()
    for index, raw in enumerate(messages):
        if not isinstance(raw, Mapping) or set(raw) != {"role", "content", "call_id"}:
            _fail("context_message_shape_invalid", "Context message fields are invalid")
        role, content, call_id = raw["role"], raw["content"], raw["call_id"]
        if role not in {"system", "user", "assistant", "tool"} or not isinstance(content, str):
            _fail("context_message_shape_invalid", "Context message role or content is invalid")
        if call_id is not None and not isinstance(call_id, str):
            _fail("context_call_id_invalid", "Context call ID is invalid")
        call_id = _nfc(call_id) if isinstance(call_id, str) else None
        if role == "system" and index != 0:
            _fail("system_message_not_leading", "System message must be first")
        if role in {"system", "user"} and call_id is not None:
            _fail("context_call_id_invalid", "System and user messages cannot carry call IDs")
        if role == "assistant" and call_id is not None:
            if call_id in seen_call_ids:
                _fail("duplicate_call_id", "Tool call IDs must be unique")
            if index + 1 >= len(messages):
                _fail("incomplete_tool_pair", "Assistant tool call is missing its tool result")
            following = messages[index + 1]
            if following.get("role") != "tool" or following.get("call_id") != raw["call_id"]:
                _fail("mismatched_tool_pair", "Assistant tool call and result IDs must match")
            seen_call_ids.add(call_id)
        if role == "tool":
            if call_id is None or index == 0:
                _fail("orphan_tool_result", "Tool result must follow an assistant tool call")
            previous = messages[index - 1]
            if previous.get("role") != "assistant" or previous.get("call_id") != raw["call_id"]:
                _fail("orphan_tool_result", "Tool result must be adjacent to its assistant tool call")
        normalized.append({"role": role, "content": _nfc(content), "call_id": call_id})
    return normalized


def _redact_text(text: str, rule_ids: Sequence[str]) -> tuple[str, list[dict[str, str]]]:
    value = _nfc(text)
    reports: list[dict[str, str]] = []
    for rule_id in rule_ids:
        pattern = _RULES.get(rule_id)
        if pattern is None:
            _fail("redaction_rule_unknown", "Configured redaction rule is unknown", "malformed_result")

        def replacement(match: re.Match[str]) -> str:
            if rule_id == "credential_assignment":
                secret = match.group(3)
                if _REDACTED_VALUE.fullmatch(secret):
                    return match.group(0)
                reports.append({"rule_id": rule_id, "digest": _digest(secret)})
                return f"{match.group(1)}{match.group(2)}[REDACTED:{rule_id}:{_digest(secret)}]"
            secret = match.group(1) if rule_id == "bearer_token" else match.group(0)
            reports.append({"rule_id": rule_id, "digest": _digest(secret)})
            prefix = "Bearer " if rule_id == "bearer_token" else ""
            return f"{prefix}[REDACTED:{rule_id}:{_digest(secret)}]"

        value = pattern.sub(replacement, value)
    return value, reports


def _summary(evicted: Sequence[Mapping[str, Any]]) -> str:
    serialized = _canonical_bytes(list(evicted))
    chars = sum(len(str(item["content"])) for item in evicted)
    return f"[COMPACTED messages={len(evicted)} chars={chars} sha256={hashlib.sha256(serialized).hexdigest()}]"


def prepare_context(
    messages: Sequence[Mapping[str, Any]],
    *,
    inline_max_chars: int,
    rule_ids: Sequence[str],
    artifact_format: str = "text",
    response_format_supported: bool = False,
) -> dict[str, Any]:
    """Redact and compact context deterministically under the L2A shadow contract."""
    if not isinstance(inline_max_chars, int) or isinstance(inline_max_chars, bool) or inline_max_chars < 1:
        _fail("context_budget_invalid", "Context budget must be a positive integer")
    ordered = validate_message_order(messages)
    redacted: list[dict[str, Any]] = []
    reports: list[dict[str, str]] = []
    for index, message in enumerate(ordered):
        content, found = _redact_text(message["content"], rule_ids)
        if index == 0 and message["role"] == "system" and found:
            _fail("required_context_redacted", "Required system context contains protected data", "unauthorized")
        redacted.append({**message, "content": content})
        reports.extend(found)

    mandatory: set[int] = {0} if redacted and redacted[0]["role"] == "system" else set()
    pair_starts = [i for i, item in enumerate(redacted[:-1]) if item["role"] == "assistant" and item["call_id"] is not None]
    if pair_starts:
        latest = pair_starts[-1]
        mandatory.update({latest, latest + 1})

    total = sum(len(item["content"]) for item in redacted)
    if total <= inline_max_chars:
        kept = redacted
        summary = ""
        evicted: list[dict[str, Any]] = []
    else:
        kept_indexes = set(mandatory)
        evicted = [item for i, item in enumerate(redacted) if i not in kept_indexes]
        summary = _summary(evicted) if evicted else ""
        mandatory_chars = sum(len(redacted[i]["content"]) for i in kept_indexes) + len(summary)
        if mandatory_chars > inline_max_chars:
            _fail("context_budget_mandatory_overflow", "Mandatory context cannot fit the effective budget")
        optional_units: list[set[int]] = []
        index = 0
        while index < len(redacted):
            if index in kept_indexes:
                index += 1
                continue
            item = redacted[index]
            if item["role"] == "assistant" and item["call_id"] is not None:
                optional_units.append({index, index + 1})
                index += 2
                continue
            if item["role"] == "tool":
                _fail("context_pair_grouping_failed", "Validated tool pair lost its assistant", "malformed_result")
            optional_units.append({index})
            index += 1
        for unit in reversed(optional_units):
            candidate_indexes = kept_indexes | unit
            candidate_evicted = [item for i, item in enumerate(redacted) if i not in candidate_indexes]
            candidate_summary = _summary(candidate_evicted) if candidate_evicted else ""
            candidate_chars = sum(len(redacted[i]["content"]) for i in candidate_indexes) + len(candidate_summary)
            if candidate_chars <= inline_max_chars:
                kept_indexes = candidate_indexes
                evicted = candidate_evicted
                summary = candidate_summary
        kept = [item for i, item in enumerate(redacted) if i in kept_indexes]

    prepared = {
        "messages": copy.deepcopy(kept),
        "summary": summary,
        "summary_position": "after_system" if kept and kept[0]["role"] == "system" else "first",
        "redactions": reports,
        "compacted_count": len(evicted),
        "budget_unit": "nfc_unicode_code_points",
        "strict_json": strict_json_metadata(artifact_format, response_format_supported),
    }
    prepared["context_digest"] = hashlib.sha256(
        _canonical_bytes({"messages": prepared["messages"], "summary": summary})
    ).hexdigest()
    used = sum(len(item["content"]) for item in kept) + len(summary)
    if used > inline_max_chars:
        _fail("context_budget_invariant_failed", "Prepared context exceeds its effective budget", "malformed_result")
    return prepared


__all__ = [
    "ContextError", "parse_exact_json", "prepare_context", "strict_json_metadata",
    "validate_message_order",
]
