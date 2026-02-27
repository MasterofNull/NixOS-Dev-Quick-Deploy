#!/usr/bin/env python3
"""Telemetry privacy helpers: opt-in gating and deterministic text hashing."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Tuple


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

# Phase 15.3.2 — Secret patterns to redact from telemetry
# These patterns detect common secret formats before they enter telemetry logs
SECRET_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("openai_api_key", re.compile(r"sk-[A-Za-z0-9]{48}")),
    ("openai_api_key_new", re.compile(r"sk-proj-[A-Za-z0-9]{48}")),
    ("anthropic_api_key", re.compile(r"sk-ant-[A-Za-z0-9\-_]{90,}")),
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("aws_secret_key", re.compile(r"aws_secret_access_key\s*[=:]\s*[A-Za-z0-9/+=]{40}")),
    ("github_token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
    ("gitlab_token", re.compile(r"glpat-[A-Za-z0-9\-]{20,}")),
    ("private_key_rsa", re.compile(r"-----BEGIN RSA PRIVATE KEY-----")),
    ("private_key_openssh", re.compile(r"-----BEGIN OPENSSH PRIVATE KEY-----")),
    ("private_key_ec", re.compile(r"-----BEGIN EC PRIVATE KEY-----")),
    ("jwt_token", re.compile(r"eyJ[A-Za-z0-9\-_]+\.eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+")),
    ("password_field", re.compile(r"(?i)password\s*[=:]\s*[^\s]{8,}")),
    ("bearer_token", re.compile(r"Bearer\s+[A-Za-z0-9\-_\.]{20,}")),
]


def is_sensitive_field(field_name: str) -> bool:
    key = field_name.lower()
    return any(token in key for token in SENSITIVE_FIELD_TOKENS)


def redact_text(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def redact_secrets(value: str) -> Tuple[str, List[str]]:
    """
    Scan text for secret patterns and redact them.
    
    Returns:
        (redacted_text, list of detected secret types)
    """
    redacted = value
    detected: List[str] = []
    
    for secret_name, pattern in SECRET_PATTERNS:
        if pattern.search(redacted):
            detected.append(secret_name)
            redacted = pattern.sub(f"[REDACTED:{secret_name}]", redacted)
    
    return redacted, detected


def scrub_telemetry_payload(value: Any, *, parent_key: str = "") -> Any:
    if isinstance(value, dict):
        return {k: scrub_telemetry_payload(v, parent_key=k) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub_telemetry_payload(v, parent_key=parent_key) for v in value]
    if isinstance(value, str) and parent_key and is_sensitive_field(parent_key):
        # Phase 15.3.2 — First redact secrets, then hash for privacy
        redacted, detected = redact_secrets(value)
        if detected:
            # Log detection (caller can handle logging)
            return f"[REDACTED:secrets_detected:{','.join(detected)}]"
        return redact_text(redacted)
    # Phase 15.3.2 — Also scan non-sensitive fields for secrets
    if isinstance(value, str) and len(value) > 20:
        redacted, detected = redact_secrets(value)
        if detected:
            return f"[REDACTED:secrets_detected:{','.join(detected)}]"
        return redacted
    return value
