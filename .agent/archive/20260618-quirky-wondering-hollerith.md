# Full System Flush: Feature Parity & Agent Integration Plan

## Context

Audit of three surface areas revealed that the local agent stack is significantly under-equipped:
agents dispatched via `aq-agent-loop` have only file/shell/git tools — no AIDB access, no
coordinator memory storage, no hints, no mesh discovery. Multiple LLM callers bypass
`build_llama_payload()` and will cause Qwen3-35B thinking-token fills. Routing defaults to
prefer-remote, and key profiles skip context injection.

**Goal:** Full parity — every agent payload reaches the model correctly, every tool the system
was designed to expose is actually available, routing defaults match the local-first intent.

---

## Phase A — Immediate (live repo edits, no rebuild needed)

### A1 — Add AI coordination tools to aq-agent-loop

**File:** `scripts/ai/aq-agent-loop` (~line 71-76)

`build_registry()` only registers `file_tools`, `shell_tools`, `git_tools`. Add:
```python
from ai_coordination import register_ai_coordination_tools
register_ai_coordination_tools(registry)
```

Import also needs `_LOCAL_AGENTS/builtin_tools` already on sys.path (it is, at line 42-44).

This gives local agents: `query_aidb`, `store_memory`, `get_hint`, `get_working_memory`,
`mesh_discovery`, `delegate_to_remote`, `harness_health`, `query_context`, etc.

### A2 — Wire store_memory_handler to actual coordinator endpoint

**File:** `ai-stack/local-agents/builtin_tools/ai_coordination.py`, `store_memory_handler` (~line 160-186)

Currently a placeholder returning `{"success": False, "error": "not yet implemented"}`.
Fix to POST to `http://127.0.0.1:8003/memory/store`:
```python
async def store_memory_handler(content, context_type="note", importance=0.5, tags=None):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{HYBRID_COORDINATOR_URL}/memory/store", json={
                "content": content,
                "memory_type": context_type,
                "importance": importance,
                "tags": tags or [],
                "source": "local-agent",
            })
            return resp.json() if resp.status_code == 200 else {"success": False, "error": resp.text}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

### A3 — Fix collective_memory_search_handler wrong endpoint

**File:** `ai-stack/local-agents/builtin_tools/ai_coordination.py`, `collective_memory_search_handler` (~line 386-398)

Calls `/documents/search` which doesn't exist in AIDB. Fix to use AIDB's `/vector/search`:
```python
resp = await client.post(f"{AIDB_URL}/vector/search", json={
    "query": query,
    "collection": "knowledge",
    "limit": limit,
})
```

### A4 — Fix unsafe LLM payloads in live-repo scripts (5 files)

All five need the same 3-line header fix to import and use `build_llama_payload()`.
Canonical import pattern (adapt sys.path to file location):

```python
import sys
from pathlib import Path
_SHARED = Path(__file__).resolve().parents[N] / "ai-stack" / "mcp-servers" / "shared"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))
from llm_config import build_llama_payload, AGENT_TASK_MAX_TOKENS
```

Files to fix:

| File | Parent depth N | Function to fix | Current max_tokens |
|------|----------------|-----------------|-------------------|
| `scripts/ai/claude-local-wrapper.py` | 2 | `_fallback_local()` line 108-112 | 2000 |
| `scripts/ai/lib/model-client.py` | 3 | `chat()` line 32-38 | 4096 |
| `ai-stack/self-improvement/llm_code_reviewer.py` | 2 | `_query_local_model()` line 163-174 | 2000 |
| `ai-stack/autonomous-improvement/trigger_engine.py` | 2 | `call_local_llm()` line 88-104 | 500 |
| `ai-stack/local-orchestrator/mcp_client.py` | 2 | `llm_chat()` line 458-462 | caller-provided |

For each, replace the inline payload dict with `build_llama_payload(messages, max_tokens=AGENT_TASK_MAX_TOKENS, task_type="lookup")`.
Keep existing `temperature` where it makes sense to pass it as `build_llama_payload(..., temperature=...)`.

---

## Phase B — Rebuild-required changes

### B1 — Add register_git_tools to initialize_builtin_tools

**File:** `ai-stack/local-agents/__init__.py` (~line 118-122, after code_execution block)

```python
try:
    from .builtin_tools.git_tools import register_git_tools
    register_git_tools(registry)
except ImportError as e:
    logger.warning(f"Failed to import git_tools: {e}")
```

This ensures the coordinator's `mcp_handlers.py` (which calls `initialize_builtin_tools`) also exposes git tools to the MCP protocol.

### B2 — Enable hints injection for local interactive profiles

**File:** `ai-stack/switchboard/switchboard.py`

Two profile changes:
1. `local-tool-calling` (line 350-362): `"injectHints": False` → `True`
2. `continue-local` (line ~250-262): `"injectHints": False` → `True`

These are the primary interactive local profiles (aq-chat uses `local-tool-calling`;
Continue editor uses `continue-local`). Context injection improves response quality.

Note: injectHints adds ~200 tokens per request. With n_ctx=8192 this is acceptable.
`coordinator-internal` and `embedding-local` profiles must stay `False`.

### B3 — Fix routing default to prefer local

**File:** `config/routing-policy.yaml` (line 13)

`default_prefer_local: false` → `default_prefer_local: true`

This ensures callers that don't specify a profile route to local by default, matching
the local-first design intent. Remote profiles remain available via explicit profile selection.

### B4 — Fix coordinator-side unsafe LLM payloads (2 files)

These are imported by running services and could cause thinking-token fills:

**File:** `ai-stack/meta-optimization/meta_optimizer.py`, `call_local_llm()` (~line 136-149)
**File:** `ai-stack/autoresearch/local_model_optimizer.py`, `_evaluate_config()` (~line 172-180)

Both need the same `build_llama_payload()` migration as Phase A files.
Both are reachable from coordinator endpoints:
- `meta_optimizer.py` → `real_time_learning_engine.py` → coordinator RAPID_ADAPTOR
- `local_model_optimizer.py` → `ai_coordinator_handlers.py` → `POST /control/autoresearch/run`

---

## Phase C — Validation

Run in order after each phase:

```bash
# After Phase A:
bash scripts/ai/delegate-to-local --mode agent \
  --prompt 'Use query_aidb to find error patterns for "agent synthesis truncated". Return the top result title.' \
  --wait
# Expect: result with AIDB content, not "tool not found"

bash scripts/ai/delegate-to-local --mode agent \
  --prompt 'Store this memory: "Phase 162 system flush complete: all AI coordination tools registered". Return {"stored": true}.' \
  --wait
# Expect: {"stored": true} with coordinator confirmation

# After Phase B (post-rebuild):
aq-qa 0
# Expect: 108/108 passed

# Run training ingest to pick up new agent_memory_store events:
python3 ai-stack/local-agents/training_ingest.py --hours 4
# Expect: dataset grows (new store events are higher quality training signal)

# Check hints are now injected to local-tool-calling:
curl -s -X POST http://127.0.0.1:8085/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-AI-Profile: local-tool-calling" \
  -d '{"messages": [{"role":"user","content":"test"}], "max_tokens": 10}' | \
  python3 -c "import json,sys; d=json.load(sys.stdin); print('hints_injected' in str(d) or d.get('usage',{}))"
```

---

## Files modified

**Phase A (no rebuild):**
- `scripts/ai/aq-agent-loop` — add register_ai_coordination_tools
- `ai-stack/local-agents/builtin_tools/ai_coordination.py` — fix store_memory + collective_memory_search
- `scripts/ai/claude-local-wrapper.py` — build_llama_payload migration
- `scripts/ai/lib/model-client.py` — build_llama_payload migration
- `ai-stack/self-improvement/llm_code_reviewer.py` — build_llama_payload migration
- `ai-stack/autonomous-improvement/trigger_engine.py` — build_llama_payload migration
- `ai-stack/local-orchestrator/mcp_client.py` — build_llama_payload migration

**Phase B (requires nixos-rebuild):**
- `ai-stack/local-agents/__init__.py` — add register_git_tools
- `ai-stack/switchboard/switchboard.py` — injectHints for local profiles
- `config/routing-policy.yaml` — default_prefer_local: true
- `ai-stack/meta-optimization/meta_optimizer.py` — build_llama_payload migration
- `ai-stack/autoresearch/local_model_optimizer.py` — build_llama_payload migration

---

## Commit strategy

Two commits:
1. `feat(agents): Phase 162A — register ai coordination tools + fix store_memory + payload hardening (7 files, no rebuild)`
2. `feat(agents): Phase 162B — git_tools in initialize_builtin_tools, hints parity, routing default local-first (rebuild required)`
