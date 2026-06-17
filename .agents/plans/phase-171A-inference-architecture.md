# Phase 171-A — Local Inference Architecture (No-Rebuild Slice)

**Status:** Implemented  
**Orchestrator:** Claude Sonnet 4.6  
**Collaboration:** collab_1 (multi-agent PRD — Gemini + Local Agent + Claude team contributions)

---

## Problem Summary

Recurring 504 timeouts and silent failures in the local inference stack caused by:
1. Token budget constants calibrated for 10 tok/s; actual throughput is 3.45 tok/s
2. Routing decisions scattered across 4 files with no canonical SSOT
3. `build_llama_payload()` bypassed in `interaction_tracker.py` and `route_handler.py`
4. No CI enforcement preventing future SSOT regressions

---

## Phase A Changes (no nixos-rebuild required, coordinator restart needed)

### A1 — LOCAL_TOK_PER_SEC throughput anchor
**File:** `ai-stack/mcp-servers/shared/llm_config.py`

Added:
- `LOCAL_TOK_PER_SEC = 3.45` — measured from `llamacpp:predicted_tokens_seconds`, overridable via env var
- `LOCAL_QUEUE_OVERHEAD_SECONDS = 60` — conservative queue wait budget for startup contention
- Updated comment block to reflect actual 3.45 tok/s budget math

Budget math at 3.45 tok/s:
- Tool call: 256 tokens = 74s each
- Synthesis: 800 tokens = 232s
- Sync-safe: 2 tool calls × 74s + 232s + 60s overhead = 500s → `delegateTimeoutSeconds` ≥ 530s

### A2 — RoutingClass SSOT
**File:** `ai-stack/mcp-servers/hybrid-coordinator/intent_classifier.py`

Added `RoutingClass` enum and `classify_routing()` function as the single canonical routing
decision point. Previously scattered:
- `_LONG_RUNNING_TASK_PHRASES` frozenset in `ai_coordinator_handlers.py` (removed)
- Fast-path logic in `chat_intent.py` (unchanged — operates on a different layer)

`RoutingClass` values: `FAST_PATH | SYNC_DELEGATE | ASYNC_DELEGATE | AGENT_LOOP | DIRECT`

**File:** `ai-stack/mcp-servers/hybrid-coordinator/extensions/ai_coordinator_handlers.py`

Updated auto-async detection to use `classify_routing()` from the SSOT instead of the
inline frozenset. Now also promotes `AGENT_LOOP` tasks to async_mode (was missing).

### A3 — build_llama_payload CI gate + SSOT fixes
**File:** `scripts/governance/tier0-validation-gate.sh`

Added `gate_llama_payload_ssot()` — grep-based check that fails if any `.py` in `ai-stack/`
constructs a raw `{"messages": ..., "max_tokens": ...}` dict without `build_llama_payload()`.
Excludes: test files, embedding endpoint callers, remote API callers.

**Files fixed:**
- `ai-stack/mcp-servers/hybrid-coordinator/extensions/interaction_tracker.py` — `_extract_learnable_pattern()` was building raw payload; migrated to `build_llama_payload(..., task_type="reasoning")`
- `ai-stack/mcp-servers/hybrid-coordinator/core/route_handler.py` — fallback LLM call in route synthesis was building raw payload; migrated to `build_llama_payload(..., task_type="reasoning")`

---

## Phase B Changes (require nixos-rebuild)

| Item | File | Change |
|------|------|--------|
| B1 | `nix/hosts/hyperd/facts.nix` | `delegateTimeoutSeconds = 530` (math: 2 tools × 74s + 232s + 60s queue + 30s slack) |
| B2 | `nix/modules/core/options.nix` | Add `delegateSyncMaxEstimatedSeconds` option (200s threshold for auto-async) |
| B3 | `ai-stack/switchboard/switchboard.py` | `injectHints = True` for `local-tool-calling` and `continue-local` profiles |
| B4 | `config/routing-policy.yaml` | `default_prefer_local: true` |

---

## Phase C Changes (new service or significant infrastructure)

| Item | Change |
|------|--------|
| C1 | Dashboard panel: active agent task monitor (reads `*.progress.json`) |
| C2 | aq-qa throughput calibration check against `LOCAL_TOK_PER_SEC` |
| C3 | Queue contention investigation: identify periodic chat-completion callers |

---

## Validation

After coordinator restart:
```bash
# Confirm RoutingClass SSOT works
python3 -c "
import sys; sys.path.insert(0, 'ai-stack/mcp-servers')
from intent_classifier import classify_routing, RoutingClass
assert classify_routing('run a self improvement slice') == RoutingClass.ASYNC_DELEGATE
assert classify_routing('what time is it') == RoutingClass.SYNC_DELEGATE
assert classify_routing('run agent loop') == RoutingClass.AGENT_LOOP
print('RoutingClass SSOT OK')
"

# Confirm LOCAL_TOK_PER_SEC importable
python3 -c "
import sys; sys.path.insert(0, 'ai-stack/mcp-servers')
from shared.llm_config import LOCAL_TOK_PER_SEC, LOCAL_QUEUE_OVERHEAD_SECONDS
assert LOCAL_TOK_PER_SEC == 3.45
print('Throughput anchor OK')
"

# Confirm CI gate catches a violation
echo 'json={"messages": [{"role":"user","content":"test"}], "max_tokens": 100}' > /tmp/test_violation.py
grep -n '"messages"\s*:' /tmp/test_violation.py | grep '"max_tokens"' && echo "gate would catch this"
rm /tmp/test_violation.py
```
