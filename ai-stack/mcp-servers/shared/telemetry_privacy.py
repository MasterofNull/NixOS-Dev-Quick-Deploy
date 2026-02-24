#!/usr/bin/env python3
"""Telemetry privacy helpers: opt-in gating and deterministic text hashing."""

from __future__ import annotations

import hashlib
from typing import Any


SENSITIVE_FIELD_TOKENS = (
    "prompt",
    "query",
    "response",
    "message",
    "text",
    "input",
    "output",
    "original_response",
    "augmented_prompt",
)


def is_sensitive_field(field_name: str) -> bool:
    key = field_name.lower()
    return any(token in key for token in SENSITIVE_FIELD_TOKENS)


def redact_text(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def scrub_telemetry_payload(value: Any, *, parent_key: str = "") -> Any:
    if isinstance(value, dict):
        return {k: scrub_telemetry_payload(v, parent_key=k) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub_telemetry_payload(v, parent_key=parent_key) for v in value]
    if isinstance(value, str) and parent_key and is_sensitive_field(parent_key):
        return redact_text(value)
    return value
