---
doc_type: skill
id: strict-json-output-contract
title: Strict JSON Output Contract
status: active
tags: [json, prompt-contract, validation]
description: "Strict JSON Output Contract"

---

# Skill: strict-json-output-contract

## Origin
Promoted from auto-generated stub (gap pattern count=110, failure_class=`provider_request_error`).
Companion to `provider-request-error-recovery` — addresses the prompt-contract side of the same failure.

## Problem Pattern
Agents send prompts to models without enforcing JSON-only output. Models prepend prose, add
explanations, or wrap JSON in markdown fences. Downstream `json.loads()` fails silently or
raises, causing task failures that look like provider errors but are actually contract violations.

## When to Use
- Prompting any model for structured output (tool calls, API responses, data extraction)
- Writing aq-qa probe prompts that expect a specific response format
- Building delegation prompts where the response will be parsed programmatically
- Any task where "validate before acceptance" is the acceptance criterion

## Guidance

### Rule: always state the contract explicitly
Never assume a model will return JSON. State it in the prompt:
```
Respond with valid JSON only. No prose, no markdown fences, no explanation.
```
For aq-qa probe tasks expecting a single word/phrase:
```
Respond with the word OK only. No other text.
```

### Enforce with `response_format` where supported
For llama.cpp (OpenAI-compatible):
```python
payload = {
    "messages": [...],
    "response_format": {"type": "json_object"},  # forces JSON mode
    "max_tokens": 180,
}
```
Note: not all models respect this — always validate the response even when set.

### Validate before acceptance
```python
import json

def parse_model_json(raw: str) -> dict:
    """Extract JSON from model response, tolerating prose prefix."""
    raw = raw.strip()
    # Try direct parse first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Strip markdown fences
    if raw.startswith("```"):
        raw = raw.split("```")[1].lstrip("json").strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    # Find last JSON object (model prepended prose)
    idx = raw.rfind('{"')
    if idx >= 0:
        try:
            return json.loads(raw[idx:])
        except json.JSONDecodeError:
            pass
    raise ValueError(f"No valid JSON found in response: {raw[:200]}")
```

### For aq-qa probes: check exact match before passing
```python
response = response.strip().lower()
expected = "ok"
assert response == expected, f"Expected '{expected}', got '{response[:100]}'"
```
If the model returns anything other than the exact expected value, the probe FAILS — do not
accept partial matches or prose wrappers as passing.

### Prompt template for strict structured output
```
Task: <task description>

Requirements:
- Respond with valid JSON only
- Schema: {"field": "value", ...}
- No prose, no markdown, no explanation before or after the JSON

JSON response:
```

## References
- `ai-stack/agent-memory/MEMORY.md`: "mixed prose+JSON parse break" — `rfind('{"function"')` extraction pattern
- `tool_registry.parse_tool_call_from_llama` — existing implementation of this pattern
- Companion skill: `provider-request-error-recovery` — handles what to do when this contract is violated
