"""
llm_config — SSOT for local LLM (llama.cpp) payload construction.

ALL code that calls the local llama.cpp server MUST use build_llama_payload()
instead of building inline dicts. This ensures constraints are applied once,
here, and propagate automatically to every call site.

Centralised constraints:
  - chat_template_kwargs: {"enable_thinking": False}
    Jinja2 template variable required by Qwen3-35B on llama.cpp.
    Top-level enable_thinking is silently ignored — it MUST be nested here.
    Without this, Qwen3-35B fills all max_tokens with reasoning_content,
    leaving the response content field empty.
  - max_tokens capped via LLAMA_MAX_TOKENS env var
    At 1-2 tok/s on Renoir APU, 4096 tokens = up to 68-minute slot lock when
    a client disconnects mid-stream. Use the smallest budget that fits the task.

SCOPE: local llama.cpp calls only.
Remote LLMs (Claude, Gemini, OpenAI) use different API conventions and are
NOT built with this function.

Usage:
    from shared.llm_config import build_llama_payload, AGENT_TOOL_CALL_MAX_TOKENS

    payload = build_llama_payload(messages, max_tokens=AGENT_TOOL_CALL_MAX_TOKENS)
    payload = build_llama_payload(messages, stream=True)
    payload = build_llama_payload(messages, max_tokens=8, temperature=0.0, model="local")
"""

import os
from typing import Any

# Compact role-authority blocks injected into the system prompt when task.role is set.
# ~25-35 tokens each. Only injected when role is explicitly assigned — never for EMBEDDED.
# Source of truth for role definitions: docs/architecture/role-matrix.md
ROLE_SYSTEM_PROMPTS: dict[str, str] = {
    "orchestrator": "[Role: orchestrator] Open/close sessions, assign slices, accept work, commit integration. You may route other agents.",
    "architect":    "[Role: architect] Draft architecture docs, flag risks, write PRDs. Requires orchestrator review before commit.",
    "implementer":  "[Role: implementer] Execute assigned slice only. Validate output. Propose commit. Do not re-scope goals.",
    "reviewer":     "[Role: reviewer] Explicit pass/fail verdict against criteria. Do not review your own work.",
}


def _inject_role(messages: list, role: str) -> list:
    """Prepend compact role block to the first system message, or insert one if absent."""
    role_prefix = ROLE_SYSTEM_PROMPTS.get(role)
    if not role_prefix:
        return messages
    msgs = list(messages)
    sys_idx = next((i for i, m in enumerate(msgs) if m.get("role") == "system"), None)
    if sys_idx is not None:
        msgs[sys_idx] = {
            "role": "system",
            "content": role_prefix + "\n\n" + msgs[sys_idx]["content"],
        }
    else:
        msgs.insert(0, {"role": "system", "content": role_prefix})
    return msgs


# Token budget constants — override at call site or via LLAMA_MAX_TOKENS env var.
# At 1-2 tok/s on Renoir APU:
#   512  tokens = 256-512s max generation
#   1200 tokens = 600-1200s max generation
#   4096 tokens = up to 68 minutes (NEVER use as default)
AGENT_TOOL_CALL_MAX_TOKENS = 512   # Tool call JSON (50-100 tokens) + short summaries
AGENT_TASK_MAX_TOKENS = 1200       # Multi-turn agent task responses
PROBE_MAX_TOKENS = 20              # Speed / health probes


def build_llama_payload(
    messages: list,
    *,
    max_tokens: int | None = None,
    temperature: float = 0.3,
    stream: bool = False,
    role: str | None = None,
    **extra: Any,
) -> dict:
    """Build a llama.cpp-compatible chat completion payload.

    This is the single source of truth for all local model request payloads.
    Never build inline dicts for llama.cpp calls — always use this function.

    Args:
        messages: Chat messages list (OpenAI format).
        max_tokens: Token budget. If None, reads LLAMA_MAX_TOKENS env var,
                    falling back to AGENT_TASK_MAX_TOKENS (1200).
        temperature: Sampling temperature (default 0.3).
        stream: Set True to request SSE streaming.
        **extra: Additional payload fields forwarded verbatim
                 (e.g. stop=["<|im_end|>"], tools=[...], cache_prompt=True).
        role: Authority role for this call (orchestrator/architect/implementer/reviewer).
              When set, injects a compact role block into the system prompt (~25-35 tokens).
              None = no injection (implementer behaviour is the implicit default).
              Never set for EMBEDDED agents — they have no text generation to guide.

    Returns:
        dict ready to POST to /v1/chat/completions.
    """
    _max_tokens = (
        max_tokens
        if max_tokens is not None
        else int(os.environ.get("LLAMA_MAX_TOKENS", str(AGENT_TASK_MAX_TOKENS)))
    )
    _messages = _inject_role(messages, role) if role else messages
    payload: dict[str, Any] = {
        "messages": _messages,
        "temperature": temperature,
        "max_tokens": _max_tokens,
        # ARCH CONSTRAINT: enable_thinking is a Jinja2 chat-template variable.
        # It MUST be in chat_template_kwargs — top-level is silently ignored by
        # llama.cpp, causing Qwen3-35B to fill all tokens with reasoning_content.
        "chat_template_kwargs": {"enable_thinking": False},
    }
    if stream:
        payload["stream"] = True
        # Request usage stats in the final SSE chunk so callers can track token spend.
        # llama.cpp emits a usage-only chunk after [DONE] when this is set.
        payload["stream_options"] = {"include_usage": True}
    # Extra fields (stop sequences, tool schemas, cache flags, model name, etc.)
    # are forwarded without modification.
    payload.update(extra)
    return payload
