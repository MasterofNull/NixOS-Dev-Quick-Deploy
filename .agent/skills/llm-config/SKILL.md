# LLM Config Skill
## Tags
llm, llama, qwen3, build_llama_payload, enable_thinking, chat_template_kwargs, max_tokens,
token_budget, switchboard, profile, model
## When to Use
Writing llama.cpp payloads; configuring inference parameters; seeing empty/truncated responses;
setting up a new agent task; choosing a switchboard profile; token budget questions.

---

## 1. The Mandatory Rule: enable_thinking

```python
# CORRECT — must be in chat_template_kwargs:
payload = {
    "messages": [...],
    "chat_template_kwargs": {"enable_thinking": False},
    "max_tokens": 512,
}

# WRONG — top-level is SILENTLY IGNORED by llama.cpp:
payload = {
    "messages": [...],
    "enable_thinking": False,    # does nothing
    "max_tokens": 512,
}
```

With thinking enabled (the default), Qwen3 emits reasoning tokens that produce an empty
`content` field in the response. The agent receives a blank answer and loops.
**This must be `False` in every llama.cpp request without exception.**

---

## 2. SSOT: build_llama_payload()

All llama.cpp calls MUST use `build_llama_payload()` from `shared/llm_config.py`. Never
construct the payload dict inline.

```python
from shared.llm_config import build_llama_payload  # or import from local path

payload = build_llama_payload(
    messages=messages,        # list of {role, content} dicts
    max_tokens=180,           # optional; env-driven if None
    temperature=0.3,          # optional; default 0.3
    role="implementer",       # optional; injects role system prompt
)
```

The function automatically:
- Injects `chat_template_kwargs: {enable_thinking: false}`
- Applies `LLAMA_MAX_TOKENS` env ceiling
- Adds `stream_options: {include_usage: true}` for token tracking
- Injects role-specific system prompt when `role=` is set

**NEVER re-implement these fields inline** — the SSOT function is the contract.

---

## 3. Token Budget Chain (priority order)

```
1. Explicit caller value (build_llama_payload(max_tokens=N))
2. DIRECT_MAX_TOKENS env var (set by delegate-to-local caller shell)
3. LLAMA_MAX_TOKENS env var (global ceiling, default 1200)
4. Mode default (direct=4096, agent=512, hybrid=768)
5. _LOCAL_MAX_TOKENS_HARD_CEILING=180 (coordinator delegation only)
```

**Coordinator delegation hard ceiling**: `ai_coordinator.py:412` enforces 180 tokens maximum
for ALL local profile delegations. At 1 tok/s on Renoir APU: P95 = ~244s. This is expected.

**Direct delegation** via `delegate-to-local --mode direct` uses chain above — no hard ceiling.
Set `DIRECT_MAX_TOKENS=512` for focused tasks to avoid multi-minute waits.

---

## 4. Switchboard Profiles

Always choose the right profile via `x-ai-profile: <name>` header to :8085.

| Profile | Target | Max in | Max out | Hints | Use for |
|---------|--------|--------|---------|-------|---------|
| `continue-local` | local | 1200 | 768 | no | IDE inline chat |
| `local-agent` | local | 3500 | 1024 | **YES** | Agent tasks, PRSI, harness ops |
| `local-tool-calling` | local | 2400 | 768 | no | Built-in tool execution |
| `embedded-assist` | local | 1800 | 512 | no | Low-token embedded queries |
| `remote-coding` | remote | 5000 | 1800 | no | Implementation, refactoring |
| `remote-reasoning` | remote | 6000 | 1800 | no | Architecture, policy, tradeoffs |
| `remote-gemini` | remote | 3500 | 1400 | no | Discovery, planning, synthesis |
| `remote-default` | remote | 3500 | 1024 | no | General remote tasks |
| `remote-free` | remote | 3500 | 1200 | no | Low-cost probing |
| `embedding-local` | local embed | 512 | 256 | no | Embeddings only |

**MLFQ priority**: `agent_type=human` in coordinator delegate payload = L0 interactive
priority. Omitting it or using `agent_type=background` = deprioritized under CPU load.

---

## 5. role: "tool" for Tool Results

Qwen3's chat template ONLY recognizes `role: "tool"` for tool call results.
Using `role: "function"` is silently dropped — model never sees the tool result and
hallucinates on every subsequent turn.

```python
# CORRECT:
messages.append({"role": "tool", "content": json.dumps(tool_result)})

# WRONG — silently dropped:
messages.append({"role": "function", "content": json.dumps(tool_result)})
```

---

## 6. Streaming + Token Tracking

```python
# Always use stream=True + stream_options for token tracking:
payload["stream"] = True
payload["stream_options"] = {"include_usage": True}

# Handle the final usage chunk (choices=[] is normal for the usage event):
for chunk in response_iter:
    if chunk.get("choices"):
        # normal token chunk — extract delta.content
    elif chunk.get("usage"):
        # final usage event — extract prompt_tokens, completion_tokens
```

If `stream=False`, token counts are not returned (llama.cpp limitation).

---

## 7. Stop Sequences

For structured output (JSON, code blocks), add stop sequences to prevent hallucination:

```python
payload["stop"] = ["</code>", "```\n\n", "\n\nHuman:", "\n\nUser:"]
```

For Nix expressions, add `"in\n"` to stop after `let ... in` sections if you want
bounded output.
