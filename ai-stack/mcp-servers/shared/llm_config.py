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
  - chat_template_kwargs: {"enable_thinking": True, "thinking_budget": N}
    Safe thinking mode. thinking_budget caps the thinking phase at N tokens,
    forcing content generation within the remaining max_tokens budget.
    Use only for research/PRSI profiles where deliberation adds value.
    N is capped at 200 for Renoir APU (200s at 1 tok/s — within 900s chunk timeout).
  - max_tokens capped via LLAMA_MAX_TOKENS env var
    At 1-2 tok/s on Renoir APU, 4096 tokens = up to 68-minute slot lock when
    a client disconnects mid-stream. Use the smallest budget that fits the task.

SCOPE: local llama.cpp calls only.
Remote LLMs (Claude, Gemini, OpenAI) use different API conventions and are
NOT built with this function.

Modal task profiles (Phase 162, extended Phase 172):
  build_llama_payload() accepts task_type= to activate a named profile.
  Profiles set temperature, frequency_penalty, enable_thinking, and thinking_budget.
  Explicit keyword args always override the profile.

Usage:
    from shared.llm_config import build_llama_payload, AGENT_TOOL_CALL_MAX_TOKENS

    payload = build_llama_payload(messages, max_tokens=AGENT_TOOL_CALL_MAX_TOKENS)
    payload = build_llama_payload(messages, stream=True)
    payload = build_llama_payload(messages, max_tokens=8, temperature=0.0, model="local")
    payload = build_llama_payload(messages, task_type="structured")   # activates profile
    payload = build_llama_payload(messages, task_type="reasoning")    # higher temp, prose
    payload = build_llama_payload(messages, task_type="research")     # thinking enabled, 100 tok budget
    payload = build_llama_payload(messages, task_type="deep_reasoning")  # thinking enabled, 150 tok budget
"""

import os
from dataclasses import dataclass
from typing import Any, Optional

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


# ---------------------------------------------------------------------------
# Modal task profiles (Phase 162)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TaskProfile:
    """Payload parameters matched to a class of task.

    Modal design: each profile is only active when the task type matches.
    enable_thinking defaults to False for most profiles (Renoir APU 1 tok/s —
    unbounded thinking fills the entire budget before content generates).
    Safe thinking is gated behind thinking_budget: when set, the model is
    capped at N thinking tokens and must generate content in the remainder.

    max_tokens_hint: profile-driven budget suggestion. Used when no explicit
    --max-tokens or env-var budget is set. Allows each task class to carry
    a reasonable default without hard-coding one value for all task types.
    Priority: explicit > DIRECT_MAX_TOKENS env > LLAMA_MAX_TOKENS env > hint > mode default.

    thinking_budget: max tokens the model may use for the thinking phase.
    None = thinking disabled. When set, max_tokens_hint must cover
    thinking_budget + expected content tokens (both come from same budget).
    Hardware ceiling: 200 tokens (200s at 1 tok/s, within 900s chunk timeout).
    """
    name: str
    temperature: float
    frequency_penalty: float
    enable_thinking: bool
    suggested_remote_profile: str   # switchboard lane for equivalent remote tasks
    description: str
    max_tokens_hint: int            # suggested budget when no explicit/env override
    thinking_budget: Optional[int] = None  # None = disabled; N = cap thinking at N tokens


TASK_PROFILES: dict[str, TaskProfile] = {
    # Deterministic structured output — JSON, strict format, ralph mode.
    # frequency_penalty=0.0: cumulative penalty causes early EOS on dense
    # JSON where structural tokens ('"', ':', '{') appear hundreds of times.
    "structured": TaskProfile(
        name="structured",
        temperature=0.0,
        frequency_penalty=0.0,
        enable_thinking=False,
        suggested_remote_profile="remote-tool-calling",
        description="JSON output, strict format, ralph mode",
        max_tokens_hint=512,
    ),
    # Tiny budget: yes/no, one-liners, pings.
    "lookup": TaskProfile(
        name="lookup",
        temperature=0.1,
        frequency_penalty=0.0,
        enable_thinking=False,
        suggested_remote_profile="remote-free",
        description="Quick Q&A, yes/no, one-liner",
        max_tokens_hint=150,
    ),
    # Code generation and debugging. frequency_penalty=0.0 avoids truncation
    # on repeated structural tokens in code (same reason as structured).
    "code": TaskProfile(
        name="code",
        temperature=0.15,
        frequency_penalty=0.0,
        enable_thinking=False,
        suggested_remote_profile="remote-coding",
        description="Write, fix, refactor code",
        max_tokens_hint=1200,
    ),
    # Architecture, analysis, design decisions. Higher temperature for more
    # exploratory prose. Mild frequency_penalty is safe for natural language.
    # enable_thinking=False until hardware supports larger budgets without timeout.
    "reasoning": TaskProfile(
        name="reasoning",
        temperature=0.5,
        frequency_penalty=0.05,
        enable_thinking=False,
        suggested_remote_profile="remote-reasoning",
        description="Architecture, analysis, design, explain-why",
        max_tokens_hint=1800,
    ),
    # Agent tool calls and harness operations.
    "agent": TaskProfile(
        name="agent",
        temperature=0.3,
        frequency_penalty=0.0,
        enable_thinking=False,
        suggested_remote_profile="local-agent",
        description="Tool calls, agent steps, harness ops",
        max_tokens_hint=512,
    ),
    # Research, PRSI, and discovery tasks. Thinking enabled with a hard budget
    # cap so the model deliberates before answering without filling all tokens.
    # Budget: 100 thinking + 800 content = 900 total (900s worst case at 1 tok/s).
    # Use for PRSI self-questioning, harness audits, root-cause analysis.
    "research": TaskProfile(
        name="research",
        temperature=0.4,
        frequency_penalty=0.0,
        enable_thinking=True,
        suggested_remote_profile="remote-reasoning",
        description="PRSI, discovery, root-cause analysis, harness audits",
        max_tokens_hint=900,
        thinking_budget=100,
    ),
    # Deep reasoning for multi-hop architecture/design decisions. Higher
    # thinking budget (150 tok) for complex synthesis; larger content window.
    # Budget: 150 thinking + 1000 content = 1150 total.
    # Use only for high-value planning tasks — not routine agent steps.
    "deep_reasoning": TaskProfile(
        name="deep_reasoning",
        temperature=0.5,
        frequency_penalty=0.05,
        enable_thinking=True,
        suggested_remote_profile="remote-reasoning",
        description="Architecture, multi-hop design, PRSI loop planning",
        max_tokens_hint=1150,
        thinking_budget=150,
    ),
}

_TASK_PROFILE_NAMES = frozenset(TASK_PROFILES)


def get_task_profile(task_type: Optional[str]) -> Optional[TaskProfile]:
    """Return the TaskProfile for task_type, or None if unknown/absent."""
    if not task_type:
        return None
    return TASK_PROFILES.get(task_type)


def build_llama_payload(
    messages: list,
    *,
    max_tokens: int | None = None,
    temperature: float | None = None,
    stream: bool = False,
    role: str | None = None,
    task_type: str | None = None,
    **extra: Any,
) -> dict:
    """Build a llama.cpp-compatible chat completion payload.

    This is the single source of truth for all local model request payloads.
    Never build inline dicts for llama.cpp calls — always use this function.

    Args:
        messages: Chat messages list (OpenAI format).
        max_tokens: Token budget. If None, reads LLAMA_MAX_TOKENS env var,
                    falling back to AGENT_TASK_MAX_TOKENS (1200).
        temperature: Sampling temperature. If None, defers to task_type profile
                     or falls back to 0.3. Explicit value always wins.
        stream: Set True to request SSE streaming.
        role: Authority role (orchestrator/architect/implementer/reviewer).
              Injects a compact role block into the system prompt (~25-35 tokens).
              None = no injection. Never set for EMBEDDED agents.
        task_type: Modal task profile name
              (structured/lookup/code/reasoning/agent/research/deep_reasoning).
              When set, activates profile-specific temperature, frequency_penalty,
              enable_thinking, and thinking_budget. Explicit keyword args override the profile.
              "research" and "deep_reasoning" enable safe thinking with a hard token ceiling.
        **extra: Additional payload fields forwarded verbatim
                 (e.g. stop=[...], tools=[...], cache_prompt=True).
                 frequency_penalty in **extra overrides the profile value.

    Returns:
        dict ready to POST to /v1/chat/completions.
    """
    profile = get_task_profile(task_type)

    _max_tokens = (
        max_tokens
        if max_tokens is not None
        else int(os.environ.get("LLAMA_MAX_TOKENS", str(AGENT_TASK_MAX_TOKENS)))
    )
    # temperature: explicit arg > profile > legacy default 0.3
    _temperature = temperature if temperature is not None else (
        profile.temperature if profile else 0.3
    )
    # frequency_penalty: **extra override > profile > legacy default 0.05
    _freq_penalty = extra.pop("frequency_penalty", profile.frequency_penalty if profile else 0.05)
    # enable_thinking + thinking_budget: profile-driven.
    # Safe thinking: only enabled when thinking_budget is set in the profile,
    # capping the thinking phase so content tokens are never crowded out.
    _enable_thinking = profile.enable_thinking if profile else False
    _thinking_budget: Optional[int] = profile.thinking_budget if profile else None

    # ARCH CONSTRAINT: enable_thinking is a Jinja2 chat-template variable.
    # It MUST be in chat_template_kwargs — top-level is silently ignored by
    # llama.cpp, causing Qwen3-35B to fill all tokens with reasoning_content.
    _ctk: dict[str, Any] = {"enable_thinking": _enable_thinking}
    if _enable_thinking and _thinking_budget is not None:
        _ctk["thinking_budget"] = _thinking_budget

    _messages = _inject_role(messages, role) if role else messages
    payload: dict[str, Any] = {
        "messages": _messages,
        "temperature": _temperature,
        "max_tokens": _max_tokens,
        "chat_template_kwargs": _ctk,
        # Anti-loop guardrails.
        # repeat_penalty=1.08 + repeat_last_n=64 guard the sliding window.
        # frequency_penalty is profile-driven: 0.0 for structured/code (cumulative
        # penalty causes early EOS on dense tokens), 0.05 for reasoning (prose).
        "repeat_penalty": 1.08,
        "repeat_last_n": 64,
        "frequency_penalty": _freq_penalty,
        # Phase 173: enable llama.cpp KV-cache prefix reuse for multi-turn sessions.
        # cache_prompt=True tells llama.cpp to cache this prompt's KV state and reuse
        # it on subsequent requests sharing the same prefix (system prompt + history).
        # Improves cache_hit_rate metric (target ≥50%; PRSI found 17.2% without this).
        # Callers may override to False via **extra if needed.
        "cache_prompt": True,
    }
    if stream:
        payload["stream"] = True
        # Request usage stats in the final SSE chunk so callers can track token spend.
        payload["stream_options"] = {"include_usage": True}
    # Extra fields (stop sequences, tool schemas, cache flags, model name, etc.)
    # are forwarded without modification. frequency_penalty was already popped above.
    payload.update(extra)
    return payload
