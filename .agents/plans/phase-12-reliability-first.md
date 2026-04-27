# Phase 12 — Reliability-First: Delegation, RAG Quality, Memory Gate

Status: `planned`
Created: 2026-04-26
Owner: Claude (orchestrator) / Qwen (implementation slices)
Predecessor: Phase 11 (complete — 11.6 deferred)

## Context: Senior Review Findings (2026-04-26)

An external senior engineering review identified this system as a net-negative on
velocity due to compounding complexity, not insufficient features. Six findings:

1. Delegation success 23.5% — worse than not delegating
2. RAG recall share 0% for route_search — context is noise, not signal
3. Agent memory has no validation gate — hallucinates can poison all future agents
4. Progressive disclosure masks complexity rather than eliminating it
5. Cloud Burst admits local failure without fixing it
6. NixOS-first claim undermined by imperative shell fallbacks

**Directive**: Freeze new feature development. Fix reliability to ≥90% delegation
success and ≤10s P95 latency before re-enabling any feature work (including 11.6).

---

## Objective

Three independent workstreams, all targeting measurable reliability improvements:

1. **12.1** — Delegation root-cause diagnosis and fix
2. **12.2** — RAG noise reduction (context quality gate)
3. **12.3** — Memory validation gate

---

## Evidence Baselines

| Metric | Current | Target |
|--------|---------|--------|
| `ai_coordinator_delegate` success rate | 23.5% | ≥90% |
| `route_search` P95 latency | 59,496ms | ≤10,000ms |
| RAG recall share (route_search) | 0% | — (gate added, not a recall target) |
| Memory writes with validation | 0% | 100% of new writes |
| http_server.py line count | 9,600 | ≤2,000 (Phase 12.4) |

---

## Scope Lock

In scope:
- Phase 12.1: Diagnose why delegation fails (timeout? model? fallback chain bugs?)
- Phase 12.2: Add retrieval confidence gate — suppress context injection below threshold
- Phase 12.3: Add human/score approval gate for `aq-memory add` writes
- Phase 12.4: Continue http_server.py decomposition to <2000 lines (remaining ~7600 lines)

Out of scope:
- Cloud Burst / Phase 11.6 (gated on delegation ≥80%)
- New agent model additions
- OpenRouter integration changes
- Streaming / SSE changes
- Anything that adds lines to http_server.py without removing more

---

## Phase 12.1 — Delegation Root-Cause Diagnosis

Status: `pending`

**Problem**: `ai_coordinator_delegate` succeeds 23.5% of the time. The pre-rebuild
number may have improved post-rebuild, but there is no post-rebuild measurement yet.

**Diagnosis plan** (in order of likelihood):
1. **Timeout**: llama.cpp inference takes 90–120s; delegation chain timeout may be
   shorter than one inference cycle. Check `_build_delegation_fallback_chain` timeout
   values against actual inference latency.
2. **Fallback chain misconfiguration**: The chain may be exhausting all targets before
   getting a valid response. Check `_assess_delegated_response_quality` scoring —
   is it rejecting valid responses as low quality?
3. **Model quality**: Quantized Qwen 35B at 12 GPU layers may produce responses the
   quality assessor scores as failures even when semantically correct.
4. **Queue depth starvation**: If llama.cpp has a queue depth of 0 (idle), the delegate
   path may be hitting a race condition on startup.

**Deliverables**:
- Diagnosis report in `.agent/workflows/phase-12-delegation-diagnosis.md`
- Specific root cause(s) identified with log evidence
- Fix PR targeting the identified cause(s)

**Validation**:
```bash
# After nixos-rebuild: measure actual success rate
aq-report --metric delegation_success --since=24h
# Compare to 23.5% baseline
```

---

## Phase 12.2 — RAG Noise Reduction (Retrieval Confidence Gate)

Status: `pending`

**Problem**: RAG recall share is 0% for route_search queries, yet context is still
being prepended. This means every query gets token overhead with no signal benefit —
"hallucination bait" per the senior review.

**Fix strategy**:
- In `route_handler.py` / `search_router.py`, add a `retrieval_confidence` check
  before context injection
- If AIDB returns results with score < 0.65 (configurable via env var
  `AI_RETRIEVAL_MIN_CONFIDENCE`), do NOT inject retrieved context into prompt
- Log `context_suppressed=true` in the route decision record for observability
- This reduces prompt size for low-quality retrievals without changing the retrieval
  pipeline itself

**Non-goals**: Do not change Qdrant schema, embeddings, or AIDB ingest. The retrieval
pipeline is not broken — the injection decision is.

**Files**:
- `ai-stack/mcp-servers/hybrid-coordinator/search_router.py` (add confidence gate)
- `nix/modules/core/options.nix` (add `AI_RETRIEVAL_MIN_CONFIDENCE` env var option)

**Validation**:
```bash
python3 -m py_compile ai-stack/mcp-servers/hybrid-coordinator/search_router.py
# Synthetic: send a query with low-score AIDB results, verify no context injected
# Check logs for context_suppressed=true entries
```

---

## Phase 12.3 — Memory Validation Gate

Status: `pending`

**Problem**: Agents (including quantized local models) can write to procedural memory
via `aq-memory add` with no human review or score threshold. A hallucinated "best
practice" becomes authoritative for all future agents.

**Fix strategy**:
- Add a `--draft` flag to `aq-memory add` that writes to a staging table/file
  instead of live memory
- Live memory only accepts writes from:
  1. Human-approved (`--approve` flag, requires interactive confirmation)
  2. Score-gated: the memory entry is evaluated by a second call with quality score ≥0.8
     before promotion
- Add `aq-memory review` subcommand to list pending draft entries for human approval
- Add `aq-memory promote <id>` to move draft → live

**Files**:
- `scripts/ai/aq-memory` (add `--draft`, `review`, `promote` subcommands)
- `.agent/GLOBAL-RULES.md` (document the gate policy)

**Validation**:
```bash
bash -n scripts/ai/aq-memory
# Test: aq-memory add --draft "test entry" → appears in draft, not live
# Test: aq-memory promote <id> → moves to live
```

---

## Phase 12.4 — Continue http_server.py Decomposition

Status: `pending` (blocked on Phase 12.1 root-cause — don't move code we're debugging)

**Problem**: http_server.py is still 9,600 lines. Target is <2,000.

**Remaining extraction targets** (after Phases 11.2–11.5):

| Target Module | Handler Group | Approx Lines |
|---------------|---------------|-------------|
| `real_time_learning_handlers.py` | `_apply_real_time_learning`, `_meta_learning_*`, `_capability_gap_*` | ~400 |
| `query_handlers.py` | `handle_query`, `handle_orchestrate`, `handle_search` (core query path) | ~800 |
| `knowledge_handlers.py` | `handle_knowledge_*`, `handle_sync_*`, `handle_catalog_*` | ~600 |
| `admin_handlers.py` | `handle_config_*`, `handle_control_*`, `handle_reload_*` | ~400 |
| `auth_middleware.py` | `api_key_middleware`, `loopback_bypass`, `rate_limiter` | ~300 |

**Execution order**: Extract `auth_middleware.py` first (smallest, most isolated),
then `real_time_learning_handlers.py`, then `query_handlers.py` (most critical path).

**Gate**: Do NOT start until Phase 12.1 diagnosis is complete. Moving delegation
code while debugging it creates a moving target.

---

## Execution Ledger

| Date | Slice | Result | Evidence |
|------|-------|--------|----------|
| — | — | — | — |

---

## Success Gate for Phase 11.6 Re-Enablement

Phase 11.6 (Cloud Burst) may be re-enabled when ALL of the following are true:
- `ai_coordinator_delegate` success rate ≥80% sustained over 24h
- `aq-qa 0` passes with 39+ checks, 0 failures
- `http_server.py` < 5,000 lines (ensuring burst logic has a stable home)
- nixos-rebuild has been run with Phase 10/11 commits deployed

Until then: `git stash show stash@{0}` to inspect the shelved work.
