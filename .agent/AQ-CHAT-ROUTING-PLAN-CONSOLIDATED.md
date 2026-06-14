# Implementation Plan: aq-chat Unified Routing & Tool-Calling
## Version: CONSOLIDATED v1.1 (LOCKED)
## PRD Reference: AQ-CHAT-ROUTING-PRD-CONSOLIDATED.md v0.3 (locked)
## Status: LOCKED — all 4 teams signed off; 3 amendments applied (see sign-off table)
## Date: 2026-06-13

## Sign-off Register

| Team | Verdict | Key conditions absorbed |
|------|---------|------------------------|
| Claude | APPROVED WITH NOTES | E.1 default path → harness_paths SSOT + absolute fallback (applied) |
| Gemini | APPROVED WITH CONDITIONS | OQ-FINAL-1 reinforced as HARD GATE; DC-2 nuance added; aiofiles fallback added to E.1 (applied) |
| Codex | APPROVED | conditional_defer: ["delegate_to_remote"] added to A.3 parity contract (applied) |
| Local (proxy) | APPROVED | A.3 sys.path note noted; watchdog variable rename noted (non-blocking, not applied) |

---

## Consolidation Summary

Four independent plans received: Claude, Gemini, Codex, Local (proxy).
All teams agree on: phase ordering A→B→C→D→E, Phase A as P0, ToolMode 3-state enum,
D3 HUD format, explicit `stream:True` in fast-path, `max_tokens=1024`, asyncio patterns,
advisory:true stall events, single nixos-rebuild for B.4+E.5.

**Divergences resolved in this document:**

| # | Divergence | Decision | Rationale |
|---|-----------|----------|-----------|
| DC-1 | Phase A dispatch: import ai_coordination.py vs inline HTTP | **Inline HTTP dispatch** | Import chain risk in subprocess (tool_registry, collective_memory, agent_pool_manager deps); inline is bounded and reversible |
| DC-2 | B.4 rebuild vs coordinator restart | **nixos-rebuild required** | Coordinator reads Nix store copy (`repoSource = builtins.path{...}`); systemctl restart won't find chat_intent.py until new derivation is activated. **Bonus:** `scripts/ai/lib` is also in coordinator's live `PYTHONPATH` (via `REPO_ROOT` env), so B.4 may work even before rebuild — but rebuild is the guaranteed path; the try/except fallback covers the gap either way |
| DC-3 | Deferred tools: Codex defers 3, Local defers 2 | **No deferrals — all 14 tools required** | Goal is full local agent harness access. Budget solved by ultra-compressed descriptions (≤25 chars), not tool removal. Coordinator mediates prsi_orchestrate + run_opencode — loopback HTTP dispatch works for all 14. |
| DC-4 | Parity contract: hand-maintained vs auto-generated | **Auto-generated** | `python3 -c "from ai_coordination import register_ai_coordination_tools; ..."` is the SSOT; hand-maintained drifts immediately |
| DC-5 | harness_health endpoint | **`GET /api/health/layered`** | Returns OSI stack; model needs layer-specific reasoning, not just up/down |

---

## Code Baseline (verified by all teams, cross-checked)

| File | Key facts |
|------|-----------|
| `scripts/ai/aq-chat` L60-67 | `TOOL_FREE_PHRASES` set literal |
| `scripts/ai/aq-chat` L68-74 | `TOOL_FREE_SPEC_PHRASES` set literal |
| `scripts/ai/aq-chat` L108 | `local_tools_enabled: bool` |
| `scripts/ai/aq-chat` L165-169 | `_should_bypass_tools_for_turn()` |
| `scripts/ai/aq-chat` L372-396 | `_build_coordinator_delegate_payload()` |
| `scripts/ai/aq-chat` L390-392 | `chat_template_kwargs: {"enable_thinking": False}`, `frequency_penalty: 0.0` — AC-12 pre-satisfied for coordinator path; fast-path MUST replicate |
| `scripts/ai/aq-chat` L659-688 | `_write_feedback()` records `self.active_profile` (always "local") — AC-4 bug |
| `scripts/ai/aq-chat` L729-757 | `/tools` handler loads full Phase 11 `build_registry()` — AC-2 bug |
| `scripts/ai/aq-chat` L813 | HUD: `[{self.active_profile}]` — never shows wire profile — AC-11 bug |
| `ai-stack/agents/runtimes/local_agent_runtime.py` L98-162 | `TOOL_SCHEMAS`: exactly 3 tools (`route_search`, `recall_memory`, `run_harness_cli`) — AC-1 bug |
| `ai-stack/local-agents/agent_executor.py` L592 | `_emit_step_telemetry()` writes `hybrid-events.jsonl` — no `AQ_AGENT_RUN_EVENTS_PATH`, no Phase E events |
| `scripts/ai/aq-agent-loop` L77-98 | `build_registry()` registers 29 tools — no event emission |
| `ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py` L1491-1493 | `_is_tool_free` inline set literal — duplicate of aq-chat phrases |
| `ai-stack/local-agents/builtin_tools/ai_coordination.py` L731 | 14 handlers + `register_ai_coordination_tools()` |
| `harness_paths.py` ~L68 | `AGENT_RUN_EVENTS: Path = TELEMETRY_DIR / "agent-run-events.jsonl"` — already registered |

---

## Phase A — Tool Registry Fix

**Priority:** P0 (CRITICAL). Closes capability blackout: 26 of 29 tools are invisible to
the interactive runtime. No rebuild required. Independent of all other phases.

---

### A.1 — Token budget audit (mandatory pre-step)

**File:** `ai-stack/agents/runtimes/local_agent_runtime.py` (lines 98-162)
**Change:** Read-only. Compute current baseline:

```bash
python3 -c "
import sys; sys.path.insert(0, 'ai-stack/agents/runtimes')
import importlib, json
spec = importlib.util.spec_from_file_location('lrt', 'ai-stack/agents/runtimes/local_agent_runtime.py')
# Alternative: just read the TOOL_SCHEMAS block and paste into a temp file
print('baseline ~350 tokens; verify with json.dumps(TOOL_SCHEMAS)')
"
```

**Budget allocation:** 350t existing + ≤450t new = ≤800t total. All 14 tools MUST be included — no deferrals.

**Strategy: ultra-compressed descriptions.** The model needs the tool name and when to call it — not prose. Descriptions ≤25 chars. Strip ALL `default` fields. Strip `enum` lists where type+description is sufficient. This is the lever, not tool removal.

Budget per tier with ultra-compressed descriptions:
- Zero-param (get_working_memory, mesh_discovery, harness_health, get_prsi_pending): ≤20t each → 80t
- Single-param (get_hint, query_aidb, query_context, get_workflow_status): ≤30t each → 120t
- Multi-param (store_memory, recommend_agent_for_task, collective_memory_search, prsi_orchestrate, run_opencode, delegate_to_remote): ≤40t each → 240t
- **Total new: ~440t. With 350t existing: ~790t — within 800t budget.**

**NO deferrals.** All 14 tools are first-class. If budget is tight after writing, compress descriptions further — do not remove tools. The goal is full harness access for the local agent.

**Implementation contract:** Measure `len(json.dumps(TOOL_SCHEMAS)) / 4` after each batch of 3 new tools. If approaching 800t, compress descriptions further. Never drop a tool.

**Acceptance gate:** Pre-condition for A.2. Token count logged in PULSE.log.
**Dependencies:** None.

---

### A.2 — Expand TOOL_SCHEMAS in local_agent_runtime.py

**File:** `ai-stack/agents/runtimes/local_agent_runtime.py`
**Lines to change:** After line 162 (end of current TOOL_SCHEMAS list): +120–180 lines.
Also `_dispatch_tool()` handler (~lines 392-440 area): +80–100 lines.

**Change (schema extension):** Append all 14 AI coordination tool schemas to `TOOL_SCHEMAS`. Use the
existing 3-entry format exactly. Descriptions MUST be ≤25 chars — ultra-compressed to fit budget while preserving full tool access. No deferrals.

**Change (dispatch handler — CRITICAL):** For each new tool, add a dispatch case in
`_dispatch_tool()`. Use inline HTTP calls, NOT `ai_coordination.py` imports (DC-1
decision). Each handler is a direct loopback HTTP call using `HYBRID_URL` (already
defined at module top — do NOT hardcode).

**Endpoint map (pre-verified against ai_coordination.py handler bodies):**

| Tool name | Method | Endpoint | Body fields |
|-----------|--------|----------|-------------|
| `get_hint` | POST | `{HYBRID_URL}/api/hints` | `{"query": args["hint_query"]}` |
| `query_aidb` | POST | `{HYBRID_URL}/vector/search` | `{"query": args["query"], "collection": "knowledge", "limit": args.get("limit", 5)}` |
| `store_memory` | POST | `{HYBRID_URL}/api/memory/store` | `{"content": ..., "memory_type": ..., "importance": ..., "tags": ...}` |
| `get_working_memory` | GET | `{HYBRID_URL}/api/memory/working` | no body |
| `mesh_discovery` | GET | `{HYBRID_URL}/api/agents/pool` | no body |
| `harness_health` | GET | `{HYBRID_URL}/api/health/layered` | no body (DC-5 decision) |
| `get_workflow_status` | GET | `{HYBRID_URL}/api/workflow/{id}/status` | path param from `args["workflow_id"]` |
| `recommend_agent_for_task` | POST | `{HYBRID_URL}/api/agents/recommend` | `{"task_description": args["task_description"]}` |
| `collective_memory_search` | POST | `{HYBRID_URL}/vector/search` | `{"query": ..., "collection": "solved_issues", "limit": ...}` |
| `get_prsi_pending` | GET | `{HYBRID_URL}/api/prsi/pending` | no body |
| `query_context` | POST | `{HYBRID_URL}/api/context/query` | `{"query": args["query"]}` |
| `delegate_to_remote` | POST | `{HYBRID_URL}/api/delegate` | full args passthrough |
| `prsi_orchestrate` | POST | `{HYBRID_URL}/api/prsi/orchestrate` | all args passthrough |
| `run_opencode` | POST | `{HYBRID_URL}/api/tools/opencode` | all args passthrough |

**Note on prsi_orchestrate + run_opencode:** These tools call coordinator-mediated
functionality (PRSI orchestration workflow + opencode subprocess). The coordinator
handles the complexity — the dispatch handler just calls the coordinator endpoint.
Verify these endpoints exist in the live route table (OQ-FINAL-1). If an endpoint is
missing, add it to the coordinator as part of Phase A (coordinator additions are restart-only,
no rebuild). Do NOT remove the tool schema — the local agent must have access.

**Implementation helper:** Extract dispatch into a single helper method:
```python
async def _dispatch_coordination_tool(self, name: str, args: dict, client) -> dict:
    # single match/dispatch block for all 12 tools
    ...
```

**Validation step (mandatory):**
```bash
python3 -c "
import sys; sys.path.insert(0, 'ai-stack/agents/runtimes')
from local_agent_runtime import TOOL_SCHEMAS
import json
count = len(json.dumps(TOOL_SCHEMAS)) / 4
names = [t['function']['name'] for t in TOOL_SCHEMAS]
print(f'Tools: {len(names)} | Token est: {count:.0f} / 800 budget')
assert count <= 800, f'BUDGET EXCEEDED'
print(names)
"
```

**Acceptance gate:** AC-1 (partial). Token count ≤800. Tool names verified.
**Dependencies:** A.1 complete.

---

### A.3 — Write auto-generated tool parity contract

**File:** `.agent/tool-parity-contract.json` (new file)
**Change:** Generate from `ai_coordination.py`:

```bash
python3 -c "
import sys, json
sys.path.insert(0, 'ai-stack/local-agents')
sys.path.insert(0, 'ai-stack/local-agents/builtin_tools')
from ai_coordination import register_ai_coordination_tools
from tool_registry import ToolRegistry
r = ToolRegistry()
register_ai_coordination_tools(r)
print(json.dumps({
  'schema_version': '1',
  'schema_token_budget_ceiling': 800,
  'required_tools': [t.name for t in r.tools.values()],
  'deferred_tools': [],
  'deferred_reason': 'All 14 tools are required — no deferrals. Budget managed via ultra-compressed descriptions (<=25 chars).',
  'generated_at': '2026-06-13'
}, indent=2))
" > .agent/tool-parity-contract.json
```

Add a Makefile/script target or CI step that re-runs this generation and diffs against
the committed contract — flag as FAIL if diverged.

**Acceptance gate:** File exists, valid JSON, `required_tools` matches A.2 additions.
**Dependencies:** A.2 complete (tool names finalized).

---

### A.4 — Fix `/tools` display in aq-chat

**File:** `scripts/ai/aq-chat` (lines 729-757, `_show_tools()`)
**Change:** Two display modes:

**`/tools` (default — runtime-actual):**
- Load `TOOL_SCHEMAS` from `local_agent_runtime.py` (import OR read `.agent/tool-parity-contract.json` — Option B preferred to avoid startup import; Gemini OQ-IMPL-3)
- Load full `build_registry(tool_manifest="full")` tool names
- Show each schema-registered tool: `  ✓ get_hint`
- Show each registry tool NOT in schemas: `  [GAP] self_improve  (Phase 11 only)`

**`/tools all` (full Phase 11 registry):**
- Load `build_registry(tool_manifest="full")` as before (29 tools)
- Show all without filtering

**Implementation note:** Use `.agent/tool-parity-contract.json` as the source for
runtime-actual tool names (read JSON, no module import overhead at HUD time).
Cache result after first read: `self._parity_contract_cache`.

**Acceptance gate:** AC-2 (`/tools` shows runtime-actual with `[GAP]` labels).
**Dependencies:** A.2 (schemas expanded), A.3 (contract JSON).

---

### A.5 — Add aq-qa CI parity check

**File:** Test fixture for aq-qa suite
**Change:** New aq-qa check:
1. Read `.agent/tool-parity-contract.json`
2. Import `local_agent_runtime.TOOL_SCHEMAS` (or parse from file), extract names
3. Assert every `required_tools` entry is in TOOL_SCHEMAS
4. Assert `len(json.dumps(TOOL_SCHEMAS)) / 4 <= schema_token_budget_ceiling`
5. On failure: diff required vs actual names

**Acceptance gate:** AC-1 fully satisfied. aq-qa 0 includes this check.
**Dependencies:** A.3.

---

### A.6 — Per-iteration tool hot-swap in agent loop

**File:** `ai-stack/agents/runtimes/local_agent_runtime.py` + `ai-stack/local-agents/agent_executor.py`
**Priority:** HIGH — required for full harness integration. Tools must be hot-swappable during execution, not locked at task-start.

**Design:** After each tool call result, the agent's active tool set is refreshed from `TOOL_CATALOG` based on what was just learned. This mirrors how agentic cache and progressive disclosure work — the right tools are available at each crucial moment.

**Change in local_agent_runtime.py:** Add `_refresh_tools_from_result()`:
```python
def _refresh_tools_from_result(
    tool_name: str,
    result_text: str,
    current_tools: list[dict],
    max_tools: int = 6,
) -> list[dict]:
    """Hot-swap: expand active tool set based on tool result content.
    
    Never removes tools already selected (monotonic expansion).
    Reads TOOL_CATALOG — catalog is always complete regardless of what's in context.
    """
    current_names = {t["function"]["name"] for t in current_tools}
    result_lower = result_text.lower()
    additions: list[str] = []
    
    # Result analysis → tool expansion candidates
    if any(k in result_lower for k in _TOOL_SELECT_MEMORY_KW) and "store_memory" not in current_names:
        additions.append("store_memory")
    if any(k in result_lower for k in _TOOL_SELECT_WORKFLOW_KW) and "get_workflow_status" not in current_names:
        additions.extend(["get_workflow_status", "prsi_orchestrate"])
    if any(k in result_lower for k in _TOOL_SELECT_DELEGATE_KW) and "delegate_to_remote" not in current_names:
        additions.append("delegate_to_remote")
    if any(k in result_lower for k in _TOOL_SELECT_HEALTH_KW) and "harness_health" not in current_names:
        additions.append("harness_health")
    if any(k in result_lower for k in _TOOL_SELECT_MESH_KW) and "mesh_discovery" not in current_names:
        additions.append("mesh_discovery")
    
    # Add up to max_tools (never exceed budget)
    result_tools = list(current_tools)
    for name in additions:
        if len(result_tools) >= max_tools:
            break
        if name in TOOL_CATALOG:
            result_tools.append(_slim_schema(TOOL_CATALOG[name]))
    return result_tools
```

**Wire into run() loop:** After dispatching a tool and receiving a result, call:
```python
_active_tools = _refresh_tools_from_result(tool_name, result_str, _active_tools)
# Next LLM call uses the refreshed set
payload = _build_inference_payload(messages, selected_tools=_active_tools)
```

**Same pattern in agent_executor.py:** `_execute_with_tools()` should call an equivalent
`_refresh_tools_from_result()` after each tool dispatch. The agent's working memory
(via `get_working_memory` or `store_memory` calls) also drives which tools are surfaced.

**Key properties:**
- TOOL_CATALOG is always complete — hot-swap source never runs out
- Active set is monotonically expanding (tools added, never removed mid-task)
- `_slim_schema()` makes adding a tool mid-execution cheap (~50 tokens)
- Works with the harness cache: if a tool was already used this session, its schema is already in KV cache

**Acceptance gate:** Agent test: start with a search-only task, confirm that after finding a memory-related result, `store_memory` is added to the active set for the next iteration without restarting.
**Dependencies:** A.2 (TOOL_CATALOG + _select_tools_for_task defined), A.1 complete.
**Rebuild:** No.

---

## Phase B — Shared Classifier + ToolMode

**Priority:** High. Eliminates dual keyword list maintenance drift.
**Constraint:** `chat_intent.py` must be pure Python — no service imports, no HTTP calls.
Importable by both `aq-chat` (CLI) and `ai_coordinator_handlers.py` (service).

---

### B.1 — Create scripts/ai/lib/chat_intent.py

**File:** `scripts/ai/lib/chat_intent.py` (new file)
**Change:** Implement shared classifier:

```python
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Literal, Optional

class ToolMode(Enum):
    ENABLED = "enabled"
    DISABLED_SESSION = "disabled_session"
    DISABLED_TURN = "disabled_turn"

@dataclass
class TurnClassification:
    mode: Literal["conversational", "agentic"]
    confidence: float
    matched_phrase: Optional[str]

# Migrated verbatim from aq-chat lines 60-74:
TOOL_FREE_PHRASES: frozenset[str] = frozenset({
    # ... exact content from aq-chat L60-67
})

TOOL_FREE_SPEC_PHRASES: frozenset[str] = frozenset({
    # ... exact content from aq-chat L68-74
})

def classify_chat_intent(text: str) -> TurnClassification:
    """Conservative: default agentic. Only conversational when phrase matches."""
    lower = text.lower().strip()
    for phrase in TOOL_FREE_PHRASES:
        if phrase in lower:
            return TurnClassification("conversational", 0.9, phrase)
    for phrase in TOOL_FREE_SPEC_PHRASES:
        if phrase in lower:
            return TurnClassification("conversational", 0.85, phrase)
    return TurnClassification("agentic", 1.0, None)

def is_conversational(text: str) -> bool:
    return classify_chat_intent(text).mode == "conversational"
```

**Conservative default rationale:** False "conversational" → tools stripped → model
can't call tools → hallucination. False "agentic" → coordinator overhead (~50s). The
asymmetric failure cost favors conservative agentic default.

**Acceptance gate:** `python3 -c "from chat_intent import classify_chat_intent; print(classify_chat_intent('what time is it'))"` returns "conversational".
**Dependencies:** None.

---

### B.2 — Add unit tests for chat_intent.py

**File:** `scripts/testing/test-chat-intent.py` (new file, or existing test suite)
**Change:** 30+ test cases covering:
- All phrases in TOOL_FREE_PHRASES → expect "conversational"
- All phrases in TOOL_FREE_SPEC_PHRASES → expect "conversational"
- Tool-inviting phrases ("list files", "search for", "run harness") → expect "agentic"
- ToolMode enum values and transitions
- is_conversational() helper
- Edge cases: empty string, whitespace-only, mixed case, embedded phrases

**Acceptance gate:** AC-6, AC-7, AC-8, AC-9.
**Dependencies:** B.1.

---

### B.3 — Import chat_intent.py in aq-chat; replace dual flags with ToolMode

**File:** `scripts/ai/aq-chat` (~lines 60-74, 108, 165-169)
**Change:**
1. Remove `TOOL_FREE_PHRASES` and `TOOL_FREE_SPEC_PHRASES` set literals (lines 60-74)
2. Add import block:
   ```python
   _LIB = Path(__file__).resolve().parent / "lib"
   if str(_LIB) not in sys.path:
       sys.path.insert(0, str(_LIB))
   from chat_intent import (TOOL_FREE_PHRASES, TOOL_FREE_SPEC_PHRASES,
                            classify_chat_intent, is_conversational, ToolMode)
   ```
3. Replace `local_tools_enabled: bool` (~line 108) with `self.tool_mode: ToolMode = ToolMode.ENABLED`
4. Update `_should_bypass_tools_for_turn()` (~line 165) to delegate to `is_conversational()`

**sys.path note:** Verify that aq-chat already sets up `lib/` in sys.path at lines ~1-20.
If so, the explicit insert may be redundant but harmless with the `not in` guard.

**Acceptance gate:** AC-5 (grep: no TOOL_FREE_PHRASES literal outside chat_intent.py).
**Dependencies:** B.1, B.2.

---

### B.4 — Import chat_intent.py in ai_coordinator_handlers.py

**File:** `ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py`
(~lines 1491-1493)
**Change:** Replace inline `_is_tool_free` set literal with import:
```python
try:
    import os as _os, sys as _sys
    _CHAT_INTENT_PATH = _os.path.join(
        _os.environ.get("REPO_ROOT", ""), "scripts", "ai", "lib"
    )
    if _CHAT_INTENT_PATH not in _sys.path:
        _sys.path.insert(0, _CHAT_INTENT_PATH)
    from chat_intent import TOOL_FREE_PHRASES as _is_tool_free
except ImportError:
    _is_tool_free = {"what time is it", "what's the date", "tell me a joke",
                     "how are you", "hello", "thanks"}
```

**Rebuild requirement:** YES (nixos-rebuild switch required — DC-2 decision).
The coordinator service reads from the Nix store copy of the repo. `systemctl restart`
alone won't find `chat_intent.py` until a new derivation is activated. Until rebuild,
the `except ImportError` fallback phrase set ensures no service disruption.

**Acceptance gate:** AC-5 post-rebuild.
**Dependencies:** B.1.

---

## Phase C — HUD Transparency + Training Fix

**Priority:** Medium. Fixes operator confusion and training data poisoning.
No rebuild required.

---

### C.1 — Add _build_prompt_text() pure function

**File:** `scripts/ai/aq-chat`
**Change:** Extract HUD string construction into a testable pure function:
```python
def _build_prompt_text(active_profile: str, wire_profile: str,
                       tool_mode: ToolMode, tool_count: int,
                       verbose: bool = False) -> str: ...
```

Wire profile abbreviation map:
```python
_PROFILE_ABBREV = {
    "local-tool-calling": "ltc",
    "continue-local": "cl",
    "local-chat-new": "lcn",
    "default": "def",
}
```

**Acceptance gate:** AC-3 (unit test with known inputs → known output strings).
**Dependencies:** B.1 (ToolMode available).

---

### C.2 — Implement D3 HUD format

**File:** `scripts/ai/aq-chat` (~line 813)
**Change:** Replace `[{self.active_profile}]` with computed HUD:

| State | HUD output |
|-------|-----------|
| ENABLED (non-verbose) | `[local \| ltc \| tools:15] ❯` |
| ENABLED (verbose) | `[local \| local-tool-calling \| tools:15] ❯` |
| DISABLED_SESSION | `[local \| ltc \| tools:off] ❯` |
| DISABLED_TURN | `[local \| off \| turn] ❯` |

**Caching requirement:** `_runtime_tool_count()` MUST be computed once at startup and
cached as `self._tool_count_cache`. Re-running on every HUD render causes perceptible
UI stutter. Implementation: `len(parity_contract["required_tools"])` from the JSON
cached on first read.

**Acceptance gate:** AC-11 (HUD reflects correct profile and tool mode on every turn).
**Dependencies:** C.1, A.3 (parity contract for tool count).

---

### C.3 — Fix _write_feedback() wire profile recording

**File:** `scripts/ai/aq-chat` (lines 659-688)
**Change:**
1. Replace `profile: self.active_profile` with `profile: self._wire_profile`
   (the field that tracks the actual switchboard profile used for this turn)
2. Add `tool_mode: self.tool_mode.value` to the feedback record
3. Add `fast_path: bool` field (True if fast-path was used for this turn)

**Training data integrity note:** Log a Rule 11 entry in `memory/issues-backlog.md`
documenting that all `delegation-feedback.jsonl` entries prior to this commit have
`profile: "local"` instead of the actual wire profile. Estimated count and date range
should be included. Training pipeline owners should apply a weight reduction or
retroactive re-label to these entries.

**Acceptance gate:** AC-4 (new feedback entries have correct wire profile).
**Dependencies:** B.3 (ToolMode enum available in aq-chat).

---

### C.4 — Session-start banner

**File:** `scripts/ai/aq-chat`
**Change:** Emit one-time informational banner at session start:
```
[aq-chat] Profile: local-tool-calling | Fast-path: enabled | Tools: 15 available
```
Suppressed by `--quiet` flag. Fires only once per session (after profile negotiation).

**Acceptance gate:** Visual inspection.
**Dependencies:** C.2.

---

## Phase D — Conversational Fast-Path

**Priority:** High. ~50s latency savings per conversational turn (skips 500-token
coordinator system prompt at 1 tok/s floor).
**Critical constraints:**
- `max_tokens=1024` MUST be set explicitly (continue-local has no ceiling — caller controls)
- `enable_thinking: False` MUST be in `chat_template_kwargs` (not top-level)
- `frequency_penalty: 0.0` MUST be set (prevents token blackout on dense JSON)
- `stream: True` MUST be set explicitly (switchboard forces stream=True for local targets
  per Phase 109.1; set it explicitly and parse SSE — all 4 teams agree on this)

---

### D.1 — Add _build_fast_path_payload() to aq-chat

**File:** `scripts/ai/aq-chat`
**Change:** New method:
```python
async def _build_fast_path_payload(self, messages: list[dict]) -> dict:
    from lib.dispatch import build_llama_payload
    payload = build_llama_payload(messages, max_tokens=1024, task_type="conversational")
    payload["chat_template_kwargs"] = {"enable_thinking": False}  # Qwen3 CRITICAL
    payload["frequency_penalty"] = 0.0
    payload["stream"] = True  # switchboard forces this; be explicit
    return payload
```

**Acceptance gate:** AC-12 (field inspection confirms all 4 required fields present).
**Dependencies:** B.1 (is_conversational available for guard).

---

### D.2 — Add fast-path eligibility guard and routing in _stream_chat()

**File:** `scripts/ai/aq-chat` (~line 323, `_stream_chat()`)
**Change:**
```python
# At entry to _stream_chat(), before coordinator delegate logic:
if (self.tool_mode == ToolMode.ENABLED
    and is_conversational(user_text)
    and not self._no_fastpath
    and not self._last_turn_had_tool_calls):
    return await self._stream_fast_path(user_text, messages)
# Fall through to coordinator delegate path
```

`_last_turn_had_tool_calls: bool` — session flag, set True when coordinator returns
a response with `tool_calls_made > 0` or `local_tool_budget_exhausted: True`
(Gemini OQ-IMPL-6 resolution: Option A, lower risk than context_history modification).
Set False on every fast-path turn.

Add `--no-fastpath` CLI flag (parse_args) → `self._no_fastpath = True`. Debug/operator
escape hatch with no UX impact in normal use.

**Acceptance gate:** AC-10 (fast-path activates on conversational turns).
**Dependencies:** D.1.

---

### D.3 — Implement _stream_fast_path() with SSE parsing

**File:** `scripts/ai/aq-chat`
**Change:** New async method that:
1. Calls `_build_fast_path_payload(messages)` (D.1)
2. POSTs to `{SWITCHBOARD_URL}/v1/chat/completions` with `X-AI-Profile: continue-local`
3. Parses SSE response using the existing `_parse_sse_response_body()` pattern
4. Renders response to HUD
5. Records to `_write_feedback()` with `fast_path: True`

**Response parsing note:** Use the `_parse_sse_response_body()` helper from
`ai_coordinator_handlers.py` as the reference implementation. Do NOT attempt
`response.json()` — switchboard forces SSE for local targets.

**Acceptance gate:** AC-10, AC-11.
**Dependencies:** D.2.

---

### D.4 — Emit routing_decision event before HTTP request

**File:** `scripts/ai/aq-chat`
**Change:** Before every `await client.post(...)` in both fast-path and coordinator-
delegate paths, emit a routing event:
```python
asyncio.create_task(self._write_routing_event({
    "event_type": "routing_decision",
    "task_id": self._session_id,
    "path": "fast_path" if using_fast_path else "coordinator",
    "profile": wire_profile,
    "classification": classification.mode,
    "seq": self._next_routing_seq(),
    "ts": time.time(),
}))
```

Event path from `harness_paths.py`: `from harness_paths import AGENT_RUN_EVENTS`
(already registered at `TELEMETRY_DIR / "agent-run-events.jsonl"`). Import this
constant rather than re-deriving the path.

**Order requirement:** `asyncio.create_task()` fires the write task BEFORE the
`await client.post()` line. This guarantees AC-13: routing event precedes response.

**Acceptance gate:** AC-13 (routing event timestamp < response timestamp in same-turn log).
**Dependencies:** D.3.

---

## Phase E — Agent Loop Event Streaming

**Priority:** High. Directly answers the user's monitoring question. Closes the
push-vs-poll observability gap. After this phase, every local inference step emits a
structured event consumable by monitors, cron triggers, and agentic workflows.

**Two writers:** coordinator delegate path (`agent_executor.py`) and direct path
(`aq-agent-loop`). Both emit to `AQ_AGENT_RUN_EVENTS_PATH`.

---

### E.1 — Add _emit_agent_event() to agent_executor.py

**File:** `ai-stack/local-agents/agent_executor.py` (~line 592+)
**Change:** New async helper and seq counter:

```python
_agent_event_seq: dict[str, int] = {}  # module-level

# Path resolution: prefer harness_paths SSOT; fall back to absolute /var/lib path.
# Never use a relative path — agent_executor.py runs from Nix store (EROFS).
try:
    from harness_paths import AGENT_RUN_EVENTS as _AGENT_RUN_EVENTS_PATH
except ImportError:
    _AGENT_RUN_EVENTS_PATH = Path(os.environ.get(
        "AQ_AGENT_RUN_EVENTS_PATH",
        "/var/lib/ai-stack/hybrid/telemetry/agent-run-events.jsonl"
    ))

class LocalAgentExecutor:
    async def _emit_agent_event(self, event_type: str, payload: dict) -> None:
        """Fire-and-forget. Never raises."""
        path = Path(os.environ.get("AQ_AGENT_RUN_EVENTS_PATH", str(_AGENT_RUN_EVENTS_PATH)))
        seq = _agent_event_seq.get(self.task_id, 0) + 1
        _agent_event_seq[self.task_id] = seq
        _reset_watchdog_time[0] = time.time()  # any emit resets watchdog
        event = {
            "task_id": self.task_id,  # mandatory top-level per D6
            "seq": seq,
            "event_type": event_type,
            "ts": time.time(),
            **payload,
        }
        asyncio.create_task(self._async_append_jsonl(path, event))

    async def _async_append_jsonl(self, path: Path, event: dict) -> None:
        try:
            try:
                import aiofiles
                async with aiofiles.open(path, "a") as f:
                    await f.write(json.dumps(event) + "\n")
            except ImportError:
                # aiofiles not available: use asyncio.to_thread as fallback
                await asyncio.to_thread(
                    lambda: path.open("a").write(json.dumps(event) + "\n")
                )
        except Exception:
            pass  # fire-and-forget: never raise
```

**aiofiles availability:** Verify with `python3 -c "import aiofiles"` in coordinator venv
before implementation. If absent, the `asyncio.to_thread` fallback above is correct.
Prefer adding `aiofiles` to the coordinator's Python environment (OQ-FINAL-5) over
relying on the fallback long-term.

**seq dict cleanup:** After emitting `agent_complete` or `agent_failed`:
`_agent_event_seq.pop(self.task_id, None)` — prevents unbounded growth in
long-running coordinator process (Claude OQ-I6, Codex OQ-CODE-4, both raised this).

**Acceptance gate:** AC-E1 (events appear in file during run).
**Dependencies:** None.

---

### E.2 — Instrument event call sites in agent_executor.py

**File:** `ai-stack/local-agents/agent_executor.py` (`_execute_with_tools()`)
**Change:** Add `await self._emit_agent_event(...)` calls:

| Event type | Emit location | Payload fields | Security note |
|-----------|--------------|----------------|---------------|
| `agent_step_start` | Top of each iteration | `step_num`, `message_count` | |
| `agent_tool_intent` | After parsing tool call, BEFORE dispatch | `tool_name`, `arg_keys` (key names only, NO values) | AC-E5: no arg values |
| `agent_tool_result` | After dispatch returns | `tool_name`, `success`, `result_chars` | No result content |
| `agent_synthesis_start` | After all tool results, before final LLM call | `tool_call_count` | |
| `agent_complete` | After synthesis, before return | `result_chars`, `tool_call_count` | + seq dict cleanup |
| `agent_failed` | In except/timeout handler | `error_type`, `step_num` | + seq dict cleanup |
| `agent_stall` | From watchdog (E.3) | `step_num`, `advisory: True`, `stall_seconds` | |

**AC-E5 security enforcement:** `arg_keys = list(args.keys())` — never `args.values()`
or `str(args)`. User prompt content must not appear. Add a code comment at each
`agent_tool_intent` emit site: `# AC-E5: arg_keys only, not arg values`.

**Acceptance gate:** AC-E2 (all 7 event types appear in a test run).
**Dependencies:** E.1.

---

### E.3 — Add stall watchdog to agent_executor.py

**File:** `ai-stack/local-agents/agent_executor.py`
**Change:** In `_execute_with_tools()` async context:

```python
stall_timeout = int(os.environ.get("STALL_TIMEOUT_OVERRIDE", "300"))
loop = asyncio.get_running_loop()  # NOT get_event_loop() — deprecated
_reset_watchdog_time = [time.time()]  # mutable container for closure

def _watchdog_fire():
    elapsed = time.time() - _reset_watchdog_time[0]
    if elapsed >= stall_timeout:
        asyncio.create_task(self._emit_agent_event("agent_stall", {
            "step_num": _current_step[0],
            "advisory": True,  # does NOT abort the loop
            "stall_seconds": elapsed,
            "last_tool_called": _last_tool_name[0],  # name only, no result
        }))
    loop.call_later(stall_timeout, _watchdog_fire)

loop.call_later(stall_timeout, _watchdog_fire)
```

**Design invariants:**
- Watchdog NEVER aborts the loop — advisory only
- `advisory: True` in payload prevents false-positive pages in monitoring systems
- Watchdog resets on ANY `_emit_agent_event()` call (the `_reset_watchdog_time[0]` assignment in E.1)
- `STALL_TIMEOUT_OVERRIDE` env var enables 5s CI testing without clock mocking

**CI test pattern:**
```python
os.environ["STALL_TIMEOUT_OVERRIDE"] = "5"
# run task that stalls after 2 tool calls
# assert agent_stall event appears within 10s
```

**Acceptance gate:** AC-E3.
**Dependencies:** E.1, E.2.

---

### E.4 — Instrument aq-agent-loop event emission

**File:** `scripts/ai/aq-agent-loop`
**Change:** Add the same `_emit_agent_event()` pattern. Do NOT import from
`agent_executor.py` — aq-agent-loop is a standalone script; copy the helper function.
Set `task_id` from the `run_task()` argument. Read `AQ_AGENT_RUN_EVENTS_PATH` at
module top:
```python
import os
from pathlib import Path
_AGENT_RUN_EVENTS = Path(os.environ.get(
    "AQ_AGENT_RUN_EVENTS_PATH",
    ".agents/telemetry/agent-run-events.jsonl"
))
```

Emit the same 7 event types at the same call sites in the `run_task()` loop.

Add `run_attempt: int` field (default 1) to all events from this path. If the harness
retry mechanism calls `run_task()` with the same `task_id`, increment this field.
This disambiguates events from multiple attempts in `agent-run-events.jsonl`
(Local team OQ-L4).

**Acceptance gate:** AC-E1, AC-E2 from aq-agent-loop invocations.
**Dependencies:** E.1 design finalized.

---

### E.5 — NixOS tmpfiles rule for agent-run-events.jsonl permissions

**File:** `nix/modules/roles/mcp-servers.nix` (or equivalent tmpfiles block)
**Change:**
```nix
systemd.tmpfiles.rules = [
  "f /var/lib/ai-stack/hybrid/telemetry/agent-run-events.jsonl 0664 ai-hybrid ai-stack -"
  "z /var/lib/ai-stack/hybrid/telemetry/agent-run-events.jsonl 0664 ai-hybrid ai-stack -"
];
```

**Why both rules:** `f` creates with correct mode if absent. `z` relabels an existing
file (which may have been created by a previous run with wrong permissions).
Per MEMORY.md "Shared JSONL write permission (CRITICAL)" pattern.

**Two writers:** `ai-hybrid` (coordinator, agent_executor.py) and `hyperd`
(aq-agent-loop direct invocations). Both need write. Both are in `ai-stack` group.

**Requires nixos-rebuild:** YES. Commit with B.4 for a single rebuild.

**Acceptance gate:** AC-E4 (both paths append without EPERM after rebuild).
**Dependencies:** None. Commit alongside B.4.

---

## Cross-Phase Concerns

### Rollback Strategy

| Phase | Rollback | Restart needed? |
|-------|---------|----------------|
| A | Revert `local_agent_runtime.py` TOOL_SCHEMAS list extension | No |
| B.1–B.3 | Revert `chat_intent.py` creation + `aq-chat` import changes | No |
| B.4 | Revert `ai_coordinator_handlers.py` + nixos-rebuild (fallback phrase set activates immediately during rebuild) | YES — nixos-rebuild |
| C | Revert HUD + feedback changes in `aq-chat` | No |
| D | `--no-fastpath` flag disables at runtime; full revert removes D.2 guard | No |
| E.1–E.4 | Events are additive; revert = remove emit calls; no data loss | No |
| E.5 | Revert tmpfiles rule + nixos-rebuild | YES — nixos-rebuild |

### Rebuild Requirements

**Exactly one nixos-rebuild needed.** Commit all code changes (A through E.4), then:
```bash
nixos-rebuild switch --flake .#hyperd-ai-dev
```
This single rebuild activates:
- B.4: coordinator picks up new Nix store derivation with `chat_intent.py` accessible
- E.5: tmpfiles rules create/relabel `agent-run-events.jsonl` with correct permissions

### Order of Operations for Same-Session Testing

1. **Phase A**: `local_agent_runtime.py` + parity contract + `/tools` fix → verify with `aq-chat /tools`
2. **Phase B.1–B.3**: `chat_intent.py` + `aq-chat` refactor → `python3 scripts/testing/test-chat-intent.py`
3. **Phase C**: HUD + feedback fix → verify HUD renders correctly, check feedback JSONL
4. **Phase D**: fast-path → test with `--no-fastpath` first (coordinator), then without; tail `agent-run-events.jsonl`
5. **Phase E.1–E.4**: event emission → `aq-agent-loop --task "list open issues"`, tail events
6. **Commit all code changes**
7. **`nixos-rebuild switch`** → activates B.4 + E.5
8. **`aq-qa 0 --machine`** → verify 114/114 minimum (+ any new Phase A/E checks)
9. **B.4 verification**: test coordinator path still passes `aq-qa 0`

---

## Open Implementation Questions

The following questions are unresolved at the code level. They are NOT blockers unless
marked BLOCKER.

### OQ-FINAL-1: Endpoint map verification (**HARD GATE — must complete before A.2 code is written**)
The endpoint map in A.2 was derived by reading `ai_coordination.py` handler bodies. Each
endpoint must be verified against the live coordinator route table before any dispatch
handler code is written. Run:
```bash
curl -s http://127.0.0.1:8003/openapi.json | python3 -m json.tool | grep '"path"'
```
Cross-check each entry in the A.2 endpoint map table against this output.
Missing endpoints → defer that tool to `conditional_defer` list in the parity contract.
**This is not an implementation detail — it is a pre-condition for A.2. Gemini team
flagged this as a required condition in plan sign-off. Implementer must produce a
verified endpoint map as the first artifact of Phase A.**

### OQ-FINAL-2: Token budget exact count (BLOCKER for A.2)
Use the character-count proxy `len(json.dumps(TOOL_SCHEMAS)) / 4` for quick measurement.
For exact count, use tiktoken with `cl100k_base` tokenizer + add 10% safety margin
(target ≤720 cl100k_base tokens for ≤800 llama.cpp tokens). The two tokenizers differ;
the margin accounts for this.

### OQ-FINAL-3: has_prior_tool_call detection in fast-path
`context_history` in aq-chat stores `{"role": ..., "content": ...}` — tool call metadata
not stored. Use Option A: `self._last_turn_had_tool_calls: bool` session flag. Set True
when coordinator response includes `tool_calls_made > 0` or `local_tool_budget_exhausted`.
Verify what fields the coordinator delegate response body actually returns before implementing.

### OQ-FINAL-4: chat_intent.py import in coordinator (pre-rebuild behavior)
Until nixos-rebuild, the coordinator tries `REPO_ROOT + "scripts/ai/lib"` path. If
`REPO_ROOT` is set correctly, the live-repo copy of `chat_intent.py` is importable even
before rebuild. Verify: `echo $REPO_ROOT` in the coordinator service context
(`journalctl -u ai-hybrid-coordinator | grep REPO_ROOT` or check service env).
If REPO_ROOT is set correctly, B.4 works before rebuild (bonus).

### OQ-FINAL-5: aiofiles availability in agent_executor.py context
E.1 uses `aiofiles` for async file writes. Verify `aiofiles` is in the coordinator's
Python environment. If not available, use `asyncio.to_thread(path.open("a").write, ...)` 
as a fallback. Check: `python3 -c "import aiofiles"` in the coordinator venv.

### OQ-FINAL-6: seq monotonicity across concurrent coordinator tasks (non-blocker)
`_agent_event_seq` dict is module-level. In the coordinator (long-running process,
sequential tasks), this is correct. If future code runs tasks concurrently in the same
process, the dict requires a lock. Document in issues-backlog.md as a follow-on concern.

### OQ-FINAL-7: stall watchdog interaction with Phase 165 stagnation guard
Phase 165 already has a stagnation guard in `agent_executor.py` that detects repeated
`validate_before_commit` calls and injects a nudge. The new Phase E watchdog fires on
wall-clock silence (300s). These are orthogonal: Phase 165 guard is pattern-based
(detects specific repeating tool call patterns), Phase E watchdog is time-based. No
conflict, but document both mechanisms in AGENTS.md so operators understand the signals.

---

## Acceptance Criteria Cross-Reference

| AC# | Satisfied by | Phase |
|-----|-------------|-------|
| AC-1 | A.2 + A.5 | A |
| AC-2 | A.4 | A |
| AC-3 | C.1 unit test | C |
| AC-4 | C.3 | C |
| AC-5 | B.3 (grep audit) | B |
| AC-6, AC-7 | B.2 unit tests | B |
| AC-8, AC-9 | B.3 (ToolMode integration) | B |
| AC-10 | D.2 | D |
| AC-11 | C.2 + D.2 | C, D |
| AC-12 | D.1 field inspection | D |
| AC-13 | D.4 | D |
| AC-14 | aq-qa 0 --machine after each phase | All |
| AC-15 | No changes to delegate-to-local path | All |
| AC-E1 | E.1 + E.4 | E |
| AC-E2 | E.2 + E.4 | E |
| AC-E3 | E.3 + STALL_TIMEOUT_OVERRIDE test | E |
| AC-E4 | E.5 post-rebuild | E |
| AC-E5 | E.2 (arg_keys only) + code review | E |

---

## Files Modified Summary

**Phase A (no rebuild):**
- `ai-stack/agents/runtimes/local_agent_runtime.py` — TOOL_SCHEMAS + `_dispatch_tool()`
- `.agent/tool-parity-contract.json` — new file (auto-generated)
- `scripts/ai/aq-chat` — `/tools` display fix

**Phase B (B.4 requires rebuild):**
- `scripts/ai/lib/chat_intent.py` — new file
- `scripts/testing/test-chat-intent.py` — new file
- `scripts/ai/aq-chat` — import chat_intent, replace bool with ToolMode
- `ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py` — import chat_intent

**Phase C (no rebuild):**
- `scripts/ai/aq-chat` — HUD + feedback fix + banner

**Phase D (no rebuild):**
- `scripts/ai/aq-chat` — fast-path + routing event emission

**Phase E (E.5 requires rebuild):**
- `ai-stack/local-agents/agent_executor.py` — event emission + watchdog
- `scripts/ai/aq-agent-loop` — event emission
- `nix/modules/roles/mcp-servers.nix` (or equivalent) — tmpfiles rules

**Total rebuild count: 1** (B.4 + E.5 in one commit → one nixos-rebuild switch)

---

## Commit Strategy

Three commits:

1. **`feat(agents): Phase A — expand TOOL_SCHEMAS to 15 tools, fix /tools display, add parity contract CI`**
   Files: local_agent_runtime.py, tool-parity-contract.json, aq-chat (/tools section), aq-qa fixture

2. **`feat(routing): Phase B-D — chat_intent.py, ToolMode enum, HUD transparency, fast-path`**
   Files: chat_intent.py, test-chat-intent.py, aq-chat (all B/C/D changes), ai_coordinator_handlers.py

3. **`feat(observability): Phase E — agent loop event streaming, stall watchdog, tmpfiles perms (rebuild)`**
   Files: agent_executor.py, aq-agent-loop, mcp-servers.nix

The rebuild commit (3) is last so `nixos-rebuild switch` picks up all changes together.

---

*Consolidated from: PLAN-claude.md, PLAN-gemini.md, PLAN-codex.md, PLAN-local.md*
*Divergences resolved: DC-1 through DC-5 (see sign-off register above)*
*Amendments applied: v1.1 — conditional_defer field, harness_paths SSOT in E.1, aiofiles fallback, OQ-FINAL-1 hard gate, DC-2 nuance*
*Consolidation author: Claude orchestrator*
*Date: 2026-06-13*
*Status: LOCKED v1.1 — all 4 teams approved — ready for Phase A delegation*
