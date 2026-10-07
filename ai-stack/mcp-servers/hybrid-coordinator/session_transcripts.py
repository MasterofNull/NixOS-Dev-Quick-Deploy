"""Session transcript extraction and redaction utilities."""

import json
import re
from typing import Any, Dict, List


def redact_secrets(text: str) -> str:
    """Redact common secret patterns from text with [REDACTED] placeholder.

    Patterns redacted:
    - OpenAI API keys (sk-...)
    - GitHub tokens (gh[pousr]_...)
    - AWS Access Key IDs (AKIA...)
    - Bearer tokens
    - Long hex strings (40+ chars, likely hash-based secrets)
    - PEM private keys
    """
    patterns = [
        r'sk-[A-Za-z0-9_-]{16,}',                                    # OpenAI keys
        r'gh[pousr]_[A-Za-z0-9]{20,}',                               # GitHub tokens
        r'AKIA[0-9A-Z]{16}',                                         # AWS Access Key ID
        r'(?i)bearer\s+[A-Za-z0-9._-]{16,}',                         # Bearer tokens
        r'\b[0-9a-fA-F]{40,}\b',                                     # Long hex (40+ chars)
        r'-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----',  # PEM keys
    ]

    result = text
    for pattern in patterns:
        result = re.sub(pattern, '[REDACTED]', result)
    return result


def extract_history(raw: bytes) -> List[Dict[str, str]]:
    """Extract chat history from multiple session formats.

    Parses Claude Code JSONL, Codex JSONL, and Continue JSON formats,
    extracting only text content. Returns the last 20 messages (≤1200 chars each).
    Redacts secrets from each message before truncation.
    """
    messages: List[Dict[str, str]] = []
    raw_str = raw.decode("utf-8", errors="replace")

    # Try JSONL formats (Claude Code / Codex)
    for line in raw_str.split("\n"):
        line = line.strip()
        if not line:
            continue

        try:
            obj = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue

        # Claude Code JSONL: type in ["user", "assistant"], message.content is str or list of blocks
        if obj.get("type") in {"user", "assistant"}:
            role = obj["type"]
            msg_obj = obj.get("message", {})
            content = msg_obj.get("content", "")

            # Handle list of blocks (e.g., tool_use, text)
            if isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                content = " ".join(text_parts)

            # Redact secrets, truncate to 1200 chars, skip empty
            content = redact_secrets(str(content).strip())[:1200]
            if content:
                messages.append({"role": role, "content": content})

        # Codex JSONL: type=="response_item", payload.type=="message", payload.role in ["user", "assistant"]
        elif obj.get("type") == "response_item":
            payload = obj.get("payload", {})
            if payload.get("type") == "message" and payload.get("role") in {"user", "assistant"}:
                role = payload["role"]
                content_list = payload.get("content", [])
                text_parts = []
                if isinstance(content_list, list):
                    for item in content_list:
                        if isinstance(item, dict) and item.get("type") in {"input_text", "output_text"}:
                            text_parts.append(item.get("text", ""))
                content = redact_secrets(" ".join(text_parts).strip())[:1200]
                if content:
                    messages.append({"role": role, "content": content})

    # Try single-object Continue JSON format
    if not messages:
        try:
            obj = json.loads(raw_str)
            if isinstance(obj, dict) and "history" in obj:
                history_list = obj["history"]
                if isinstance(history_list, list):
                    for item in history_list:
                        if isinstance(item, dict):
                            msg = item.get("message", {})
                            if isinstance(msg, dict):
                                role = msg.get("role")
                                content = msg.get("content", "")

                                # Handle str or list of blocks; keep only text type
                                if isinstance(content, list):
                                    text_parts = []
                                    for block in content:
                                        if isinstance(block, dict) and block.get("type") == "text":
                                            text_parts.append(block.get("text", ""))
                                    content = " ".join(text_parts)

                                # Only include user/assistant roles
                                if role in {"user", "assistant"}:
                                    content = redact_secrets(str(content).strip())[:1200]
                                    if content:
                                        messages.append({"role": role, "content": content})
        except (json.JSONDecodeError, ValueError, KeyError):
            pass

    # Return last 20 messages
    return messages[-20:] if messages else []
