# Skill: provider-request-error-recovery

## Origin
Promoted from auto-generated stub (gap pattern count=124, failure_class=`provider_request_error`).
Pattern observed across delegation feedback — highest-frequency unaddressed gap in training data.

## Problem Pattern
When a provider call fails (local llama.cpp, Gemini, Codex), agents retry with the same payload,
producing repeated failures. Root causes are usually one of: context overflow, malformed payload,
empty content due to thinking tokens, or rate/timeout limits. The fix is always: diagnose first,
simplify payload, then retry once.

## When to Use
- Any delegation or API call returns empty response, HTTP 4xx/5xx, or JSON parse error
- `delegate-to-local` / `delegate-to-gemini` / `delegate-to-codex` exits non-zero
- aq-qa probe returns unexpected or empty output
- Model response is empty string despite HTTP 200 (thinking token bleed)

## Guidance

### Step 1 — Capture the specific failure
Do not retry blind. Log the full response before doing anything:
```bash
# For llama.cpp direct:
curl -sf http://127.0.0.1:8080/v1/chat/completions -d "$payload" 2>&1 | python3 -c "
import json, sys
r = sys.stdin.read()
try: d = json.loads(r); print(json.dumps(d, indent=2)[:2000])
except: print('RAW:', r[:1000])
"
```

Classify the failure:
| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| Empty `content` field, HTTP 200 | Thinking tokens enabled | Add `chat_template_kwargs: {"enable_thinking": false}` |
| HTTP 400 | Malformed payload (bad role, null field) | Inspect payload structure |
| HTTP 413 / context error | Prompt too long | Reduce `max_tokens`, truncate prompt |
| Timeout / 504 | Token budget too large | Cap `max_tokens` to ≤180 for local |
| `json.JSONDecodeError` on 200 | Model prepended prose before JSON | Use `rfind('{"function"')` extraction |

### Step 2 — Simplify the payload
- Reduce `max_tokens`: local hard ceiling = 180 (`_LOCAL_MAX_TOKENS_HARD_CEILING`)
- Strip any thinking-mode flags
- Shorten the prompt: remove examples, reduce context, state the task in ≤3 sentences
- For aq-qa probes expecting simple output: use a single-sentence prompt, e.g. `"Respond with the word OK only."`

### Step 3 — Single retry
Retry exactly once with the simplified payload. If it fails again → stop, report to orchestrator
with the captured error details. Never loop on the same failure (RETRY BUDGET rule: max 3 total).

### Step 4 — Seed the fix
If you discover a new provider-specific failure mode, seed it to `error-solutions` RAG collection
and add a row to the MEMORY.md Promoted Bug Patterns section.

## References
- MEMORY.md: "local delegate 504 = token budget too large"
- MEMORY.md: "mixed prose+JSON parse break"
- MEMORY.md: `enable_thinking` must be in `chat_template_kwargs`, not top-level
- `ai-stack/local-agents/ai_coordinator.py`: `_LOCAL_MAX_TOKENS_HARD_CEILING`
- `scripts/ai/lib/build_llama_payload` SSOT
