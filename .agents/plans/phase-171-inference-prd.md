---
title: "Phase 171 — Local Inference Architecture PRD"
status: "active"
collaboration: "collab_1"
orchestrator: "Claude Sonnet 4.6"
teams: ["claude-orchestrator", "gemini", "local-qwen3"]
created: "2026-06-17"
last_updated: "2026-06-17"
implementation_status:
  phase_a: "COMPLETE — commit cb884b40 (2026-06-15)"
  phase_b: "COMPLETE — commits 99b984a6, e0795f33 (2026-06-17); requires nixos-rebuild"
  phase_c: "PARTIAL — aq-qa check d18c74e1; dashboard panel + queue investigation pending"
---

# Phase 171 — Local Inference Architecture PRD
# Multi-Agent Collaboration collab_1

**Orchestrator:** Claude Sonnet 4.6  
**Teams:** Claude Orchestrator · Gemini · Local/Qwen3 (in progress — see §8)  
**Problem:** Recurring 504 timeouts and silent failures in local inference stack  

---

## Executive Summary

The local inference stack had three root causes for 504 timeouts and silent failures:

1. **Wrong throughput anchor**: Token budget constants calibrated for 10 tok/s; actual measured
   throughput is 3.45 tok/s from `llamacpp:predicted_tokens_seconds`. Every timeout was
   2.3-3.5× too tight.

2. **Fragmented routing**: The `ASYNC_DELEGATE` decision was scattered across 4 files with no
   canonical SSOT. `_LONG_RUNNING_TASK_PHRASES` frozenset in `ai_coordinator_handlers.py` was
   the only gate — new task patterns had to be patched in the wrong place.

3. **SSOT compliance gap**: Multiple LLM callers bypassed `build_llama_payload()`, risking
   silent thinking-token fills from Qwen3-35B's chat template `enable_thinking` requirement.
   No CI enforcement prevented regressions.

**Budget math at 3.45 tok/s (corrected):**
- Tool call: 256 tokens = 74s each
- Synthesis: 800 tokens = 232s
- Sync-safe: 2 tool calls × 74s + 232s synthesis + 60s queue overhead = 500s
- `delegateTimeoutSeconds` must be ≥ 530s for 2-tool sync tasks (500s + 30s slack)
- 3+ tool tasks MUST route `ASYNC_DELEGATE` (3 × 74s + 232s + 60s = 514s — exceeds safe window)

---

## Area 1: Task Classification Policy

### Consensus Finding

Both teams agree on a single canonical routing decision layer. **Disagree on location**:
- Claude team: consolidate into existing `intent_classifier.py` (simpler, already wired)
- Gemini team: create new `routing_policy.py` (cleaner separation of concerns)

**Resolution:** `intent_classifier.py` consolidation wins for Phase A (zero new files, coordinator
already imports it). `routing_policy.py` refactor deferred to future architecture cleanup.

### Implemented (Phase A — commit cb884b40)

`RoutingClass` enum and `classify_routing()` added to
`ai-stack/mcp-servers/hybrid-coordinator/intent_classifier.py`:

```
FAST_PATH      — conversational, no tools, <60s
SYNC_DELEGATE  — ≤2 tool calls (configurable via AI_DELEGATE_SYNC_MAX_ESTIMATED_S), <200s estimated
ASYNC_DELEGATE — 3+ tool calls, 200s–2000s estimated
AGENT_LOOP     — >10 tool calls or explicit "run agent loop" intent
DIRECT         — no-tool analysis, draft, debate
```

`_LONG_RUNNING_TASK_PHRASES` frozenset removed from `ai_coordinator_handlers.py`.
Auto-async promotion now uses `classify_routing()` from SSOT — also promotes `AGENT_LOOP` tasks
(was missing from the old frozenset check).

### Implemented (Phase B — commit e0795f33)

`_SYNC_TOOL_BUDGET` derived from env var `AI_DELEGATE_SYNC_MAX_ESTIMATED_S` (default 200s):
`floor(200 / 74) = 2` → `tool_count_hint > 2` routes async. Configurable without code change.

### Remaining

- Area 1 is architecturally complete.
- Future: ML-based tool count estimation (SRE preference) deferred to Phase D.

---

## Area 2: Timeout Chain Calibration

### Consensus Finding

All teams align: `LOCAL_TOK_PER_SEC = 3.45` from `/metrics` must be the single source of truth
for all budget derivations. Gemini proposes `QUEUE_OVERHEAD_S = 45` (Claude uses 60s — more
conservative; Claude's value wins). Gemini suggests 600s timeout ceiling; Claude derives 530s
from math. Claude's derived value is more precise.

### Implemented (Phase A — commit cb884b40)

`ai-stack/mcp-servers/shared/llm_config.py`:
```python
LOCAL_TOK_PER_SEC: float = float(os.environ.get("LOCAL_TOK_PER_SEC", "3.45"))
LOCAL_QUEUE_OVERHEAD_SECONDS: int = 60
AGENT_TOOL_CALL_MAX_TOKENS = 256   # 74s × 3.45 tok/s ≈ 256 tokens
AGENT_TASK_MAX_TOKENS = 800        # 232s × 3.45 tok/s ≈ 800 tokens
```

### Implemented (Phase B — commits 99b984a6, e0795f33)

`nix/hosts/hyperd/facts.nix`:
```nix
aiHarness.runtime.delegateTimeoutSeconds = 530;
```

`nix/modules/core/options.nix` — new option:
```nix
delegateSyncMaxEstimatedSeconds = lib.mkOption { default = 200; ... };
```

`nix/modules/services/mcp-servers.nix`:
```
AI_DELEGATE_SYNC_MAX_ESTIMATED_S=200
```

**Requires `nixos-rebuild switch`** to activate `AI_DELEGATE_TIMEOUT_S=530` and
`AI_DELEGATE_SYNC_MAX_ESTIMATED_S=200` in coordinator env.

### Open Question

Gemini asks: approve hard 600s timeout ceiling in Nix?  
**Orchestrator answer:** 530s is more defensible — derived from math (500s + 30s slack), not
from a round number. Re-evaluate after Phase C queue investigation if contention adds >70s overhead.

---

## Area 3: Queue Isolation

### Consensus Finding

**Option A (second llama.cpp instance) is BLOCKED** — unanimous: 22.5GB model × 2 = 45GB
exceeds 27GB system RAM on Renoir APU. No NixOS config makes this viable.

- Claude team: **Option B** — rate-limit periodic chat-completion callers after identifying them.
- Gemini team: **Option C** — strip LLM prompts from health probes entirely (passive-only health).
  Gemini's Option C is stronger than B: rate-limiting a caller that shouldn't be calling at all
  is the wrong fix.

**Resolution:** Option C. Identify callers → strip LLM calls from health checks → replace with
passive `GET /health` + `GET /slots`. Gemini's framing is correct.

### Not Yet Implemented (Phase C)

**Step 1 — identify actual slot consumers:**

```bash
# Watch what's actually queuing
journalctl -u ai-llama-server -f --output cat 2>/dev/null &
# Find periodic chat-completion senders
grep -rn "asyncio.sleep\|v1/chat/completions" \
  ai-stack/ --include="*.py" | grep -v "test_\|\.pyc"
```

**Step 2 — strip LLM calls from health probes:**  
Replace any `v1/chat/completions` call inside a health-check or poller with:
- `GET http://127.0.0.1:8080/health` (llama.cpp health)
- `GET http://127.0.0.1:8080/slots` (slot occupancy)

**Acceptance criteria:**
- Agent task first-step elapsed < 120s (was up to 371s with queue wait)
- `GET /slots` shows state=0 (idle) during coordinator quiet period
- No LLM prompt appears in llama-server logs during a `aq-qa 0` run

**Phase C owner:** Orchestrator (Claude) assigns as a focused queue-investigation slice.

---

## Area 4: build_llama_payload SSOT Compliance + CI Enforcement

### Consensus Finding

All teams agree this is the highest-confidence, lowest-risk change. Both SSOT violations
(meta_optimizer.py, local_model_optimizer.py) were already fixed before this PRD was written.

### Implemented (Phase A — commit cb884b40)

`scripts/governance/tier0-validation-gate.sh` — new gate `gate_llama_payload_ssot()`:
- Detects `"messages"\s*:` + `"max_tokens"` outside `build_llama_payload()` in `ai-stack/*.py`
- Excludes: tests, embedding callers (8081), remote API callers (Claude/Gemini/OpenAI)

Two violations found and fixed:
- `interaction_tracker.py:492` — migrated to `build_llama_payload(..., task_type="reasoning")`
- `route_handler.py:1903` — migrated to `build_llama_payload(..., task_type="reasoning")`

**Gemini note on `# noqa: llama-payload` override:** Accepted for `scripts/` directory only.
The gate already excludes `scripts/` via the `ai-stack/` scope constraint.

### Remaining

- None. Phase A complete. CI gate active.

---

## Area 5: Observability — Agent Task Duration + Throughput Health

### Consensus Finding

Both teams agree on filesystem heartbeat approach (`.progress.json`) over Redis/queue approach.
Both agree aq-qa throughput calibration check is Phase A; dashboard panel is Phase C.

### Implemented (Phase A — commit d18c74e1)

`scripts/testing/test-local-inference-throughput.py`:
- Reads `llamacpp:predicted_tokens_seconds` from `GET /metrics`
- Fails if measured tok/s drifts > 50% from `LOCAL_TOK_PER_SEC`
- SKIPs gracefully when llama.cpp is unreachable or no inference has run (exit 0)

Wired into `phase0.py` as aq-qa check **0.10.22** (IDs 0.10.15–0.10.21 occupied by Phase 165/166).

**Gemini's 15% warning threshold vs Claude's 50% failure threshold:**  
Both can coexist: 15% warning (informational) + 50% failure (blocks commit). Implementation
with both thresholds deferred to Phase C (requires aq-qa result to support `warn` state).
Current implementation uses 50% as the single gate.

### Not Yet Implemented (Phase C)

**Dashboard active-agent-task panel:**

`agent_executor.py` already writes `.agents/delegation/outputs/*.progress.json`. Dashboard backend
needs a new endpoint:

```python
# dashboard/backend/api/routes/aistack.py
@router.get("/api/aistack/agent-tasks/active")
async def get_active_agent_tasks():
    """Return in-progress agent tasks from *.progress.json files."""
    ...
```

Frontend card: task ID, step N, tool calls completed, elapsed time, last tool, status.

**Acceptance criteria:**
- Dashboard shows active task within 10s of agent_executor writing a new step
- Refresh interval: 10s
- File permission model: `.progress.json` written with mode 0644 so dashboard user can read

---

## Risk Register (Consolidated)

| Risk | Severity | Mitigation |
|------|----------|------------|
| Throughput variability under thermal throttle | Medium | `LOCAL_TOK_PER_SEC` env-override + aq-qa 50% drift gate |
| RoutingClass SSOT deploy gap (restart window) | Low | Phase A adds before removing old frozenset — safe |
| Token reduction at 207 vs 256 | Low | Keeping 256 (74s/call); don't derive lower from formula |
| CI false positives on grep gate | Low | Require `"messages"\s*:` (dict key form) not bare string |
| Queue contention source unknown | Medium | Phase C investigation before rate-limiting |
| Dashboard file permissions for `.progress.json` | Low | Phase C: verify 0644 mode, add tmpfiles.d if needed |
| Gemini's 600s ceiling vs 530s | None | 530s is math-derived; re-evaluate after queue investigation |

---

## Implementation Status

| Item | Phase | Status | Commit |
|------|-------|--------|--------|
| `LOCAL_TOK_PER_SEC` constant in llm_config.py | A | ✓ DONE | cb884b40 |
| `RoutingClass` SSOT in intent_classifier.py | A | ✓ DONE | cb884b40 |
| `classify_routing()` replaces frozenset in handlers | A | ✓ DONE | cb884b40 |
| SSOT gate in tier0-validation-gate.sh | A | ✓ DONE | cb884b40 |
| interaction_tracker.py SSOT fix | A | ✓ DONE | cb884b40 |
| route_handler.py SSOT fix | A | ✓ DONE | cb884b40 |
| `delegateTimeoutSeconds = 530` in facts.nix | B | ✓ DONE | 99b984a6 |
| aq-qa throughput calibration check 0.10.22 | A | ✓ DONE | d18c74e1 |
| `delegateSyncMaxEstimatedSeconds` Nix option | B | ✓ DONE | e0795f33 |
| `AI_DELEGATE_SYNC_MAX_ESTIMATED_S` env var | B | ✓ DONE | e0795f33 |
| `_SYNC_TOOL_BUDGET` derived from env in classify_routing | B | ✓ DONE | e0795f33 |
| injectHints for local-tool-calling/continue-local | B | ✓ ALREADY TRUE | — |
| `default_prefer_local: true` in routing-policy.yaml | B | ✓ ALREADY TRUE | — |
| nixos-rebuild to activate B items | B | **PENDING** | — |
| Queue contention investigation + strip LLM health calls | C | PENDING | — |
| Dashboard active-agent-task monitor panel | C | PENDING | — |

---

## Cross-Team Synthesis

### Points of Agreement (All Teams)
- `LOCAL_TOK_PER_SEC = 3.45` is the correct anchor (empirical, from `/metrics`)
- `build_llama_payload()` must be the only legal llama.cpp payload constructor
- Option A (second llama.cpp instance) is blocked by RAM math on this hardware
- File-system `.progress.json` is correct for agent progress (simpler than Redis)
- Queue contention investigation must precede rate-limiting

### Claude-Only Positions (Accepted)
- 530s timeout is more defensible than Gemini's 600s (math-derived vs round number)
- 50% drift threshold for aq-qa (vs Gemini's 15% warning — warn state deferred to Phase C)
- `intent_classifier.py` for RoutingClass (vs Gemini's `routing_policy.py`)
- Keep 256 tokens/tool call (vs derived 207 — lower budget risks JSON truncation)

### Gemini-Only Positions (Accepted)
- Option C (strip LLM calls from health probes) is stronger than Option B (rate-limit)
- Deterministic progress heartbeats for long-running tasks (already in agent_executor)

### Local Agent / Qwen3 (Pending — section 8 below)

---

## §8 — Local Agent Contribution (Pending)

Task `local-20260617-093201-gfpqzx` is still running as of PRD synthesis time
(step 9, 1849s elapsed). The local agent has live tool access and can verify actual file states,
empirical queue-wait measurements, and service configurations.

**Expected contributions once complete:**
- Verification of file states (which SSOT fixes are confirmed live vs theoretical)
- Empirical queue-wait timing from `.log.steps.jsonl` (elapsed_s deltas)
- Any live-service discoveries not visible from static code analysis

**Action:** Update this section with the local agent's output when `gfpqzx` completes.
Check: `python3 scripts/ai/lib/pending-update list` for status.

---

## Orchestrator Verdict

All Phase A and Phase B items are implemented. **`nixos-rebuild switch` is needed** to activate:
- `AI_DELEGATE_TIMEOUT_S=530` (prevents 504 on 2-tool sync tasks)
- `AI_DELEGATE_SYNC_MAX_ESTIMATED_S=200` (configurable sync/async threshold)

Phase C items (queue investigation + dashboard panel) are the remaining work. Phase C can be
executed as independent focused slices — they do not block the core stability improvements
already in production on coordinator restart.

**SYNTHESIS_COMPLETE — Phase 171 core stabilization: 11 items done across A/B; 2 items pending
(Phase C): queue contention investigation + dashboard active-task monitor panel.**
