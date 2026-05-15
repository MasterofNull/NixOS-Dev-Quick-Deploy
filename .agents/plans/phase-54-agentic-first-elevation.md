# Phase 54 — Agentic-First Architecture Elevation

**ID:** PHASE-54
**Status:** PLANNING
**PRD:** `.agent/PROJECT-AGENTIC-FIRST-ELEVATION-PRD.md`
**Goal:** Link memory, routing, retrieval, and execution into an intentional agentic-first architecture.
**Gemini collaboration task:** `gemini-20260514-171425-i7ecuo` (routing/topology analysis — check before starting 54.2)
**aq-qa target:** 72 checks (from 59; +13 new)

---

## Why This Phase

After 53 phases of spec-driven development the harness works. Now the question is whether it _thinks_. The 2025–2026 research consensus is clear: world-class agentic systems treat memory as an OS abstraction, route by semantic intent, make RAG a default not an option, checkpoint workflow execution, and run continuous evaluation. This phase wires those four missing connective tissues.

---

## Pre-Conditions (must be true before executing any slice)

- [ ] Gemini routing analysis complete: `delegate-to-gemini --status gemini-20260514-171425-i7ecuo`
- [ ] Gemini output integrated into PRD Themes B and C (update PRD before 54.2)
- [ ] `aq-qa 0` passes all 59 current checks
- [ ] PostgreSQL accessible (needed by 54.4, 54.5, 54.6)
- [ ] AIDB :8002 healthy with logic-patterns project ≥10 docs (Phase 52 gate)

---

## Sub-Phases

### 54.1 — Unified Memory Layer `[implementer]`

**Objective:** Introduce `MemoryBroker` as the single interface for all memory read/write operations in the coordinator. Wire temporal validity and a recall benchmark gate.

**Deliverables:**
- `ai-stack/mcp-servers/hybrid-coordinator/memory_broker.py`
  - `MemoryBroker` class: `write(type, content, valid_from, valid_until)` / `read(type, query, top_k)`
  - Types: `working` (Redis TTL=3600), `episodic` (AIDB project=episodic), `semantic` (AIDB project=semantic), `procedural` (AIDB project=procedural)
  - Temporal filter on reads: skip docs where `valid_until < now()`
  - Contradiction logger: if new write conflicts with existing (cosine similarity >0.92 + contradicts keyword check), write both + flag `contradicted=True` on older doc
- `scripts/ai/aq-memory-recall-benchmark`
  - 20-question test pack against AIDB semantic + episodic projects
  - Pass gate: ≥85% correct retrievals (judged by cosine similarity ≥0.75 to ground truth)
  - Output: JSON scorecard
- aq-qa checks:
  - `1.0.1`: `MemoryBroker` importable from coordinator package
  - `1.0.2`: AIDB has projects `episodic` and `procedural` (create if absent)
  - `1.0.3`: `aq-memory-recall-benchmark` runs and returns `pass_rate >= 0.85`

**Dependencies:** None (can start immediately after pre-conditions met)

---

### 54.2 — Intent-Aware Routing `[implementer]`

**Objective:** Add lightweight intent classification before every coordinator `/query` dispatch. Route based on intent, not just static profile.

**Wait for:** Gemini analysis (`gemini-20260514-171425-i7ecuo`) — merge findings before implementing intent taxonomy.

**Deliverables:**
- `ai-stack/mcp-servers/hybrid-coordinator/intent_classifier.py`
  - `IntentClassifier` class: embeds query via llama-embed :8081, cosine-matches against intent prototype embeddings
  - Intent taxonomy v1: `code_generation`, `code_review`, `knowledge_lookup`, `planning`, `math_reasoning`, `tool_execution`, `delegation`
  - Sub-50ms target (use cached prototypes; re-embed prototypes only on config reload)
  - Returns `{intent, confidence, fallback_profile}`
- `config/intent-routing-map.json`
  - Intent → profile mapping: hot-reloadable via `POST /control/intent/reload`
  - Each entry: `{intent, profile, min_confidence, fallback_profile}`
- Routing log: every `/query` response includes `intent_classification: {intent, confidence, profile_selected}`
- aq-qa checks:
  - `1.0.4`: `IntentClassifier` importable; prototype embeddings cached on startup
  - `1.0.5`: `GET /control/intent/map` returns current routing map; accuracy probe ≥0.80

**Dependencies:** 54.1 (MemoryBroker — procedural memory stores intent-profile outcomes)

---

### 54.3 — Active RAG Pipeline `[implementer]`

**Objective:** Make retrieval augmentation the default for every coordinator query. Bring L6 health to green.

**Deliverables:**
- `ai-stack/mcp-servers/hybrid-coordinator/rag_augmentor.py`
  - `RagAugmentor` class: wraps LLM prompt construction
  - On every `/query` call: classify intent → select AIDB project → run vector search → inject top-k as `[CONTEXT]` block in system prompt
  - Project selection by intent: `knowledge_lookup`→semantic, `code_*`→logic-patterns, `planning`→episodic, others→semantic
  - Retrieval timeout: 500ms hard cap; on timeout, skip augmentation + log `rag_skipped=True`
  - Retrieval logged: `{project, hits, latency_ms, skipped}` per query
- L6 health gate: `GET /api/health/layered` L6 = healthy iff last 5 queries had `rag_skipped=False`
- aq-report update: RAG posture reads retrieval log; posture = `active` when >80% of queries augmented
- aq-qa checks:
  - `1.0.6`: `RagAugmentor` importable; test query to coordinator returns `rag_augmented=True` in response metadata
  - `1.0.7`: `GET /api/health/layered` returns L6 status present; posture transitions to `active` after 5 augmented queries

**Dependencies:** 54.2 (intent classifier needed for project selection)

---

### 54.4 — Durable DAG Execution `[implementer]`

**Objective:** Workflows can checkpoint at each node and resume from the last successful state after failure.

**Deliverables:**
- PostgreSQL table: `workflow_checkpoints(id, workflow_id, completed_nodes jsonb, node_outputs jsonb, pending_nodes jsonb, created_at, updated_at)`
- `WorkflowCheckpointer` mixin for `WorkflowExecutor` (Phase 49):
  - After each node completes: `UPSERT workflow_checkpoints WHERE workflow_id=...`
  - On executor init: check if checkpoint exists → resume from `pending_nodes` with `node_outputs` as pre-loaded context
- `POST /workflow/run/{id}/resume` endpoint: loads checkpoint, re-enqueues pending nodes
- Dead-letter queue: failed nodes at max retries → `workflow_dlq` Redis list + dashboard alert in Command Deck
- Evolving orchestration log: `workflow_execution_patterns(workflow_id, pattern_type, latency_ms, success, created_at)` → surfaced in aq-report as "patterns" section
- Checkpoint TTL: PostgreSQL `pg_cron` job or Python sweeper: delete checkpoints >7 days old
- aq-qa checks:
  - `1.0.8`: `workflow_checkpoints` table exists in PostgreSQL
  - `1.0.9`: `POST /workflow/run/{id}/resume` registered and responds 200 on valid checkpoint
  - `1.0.10`: DLQ key accessible in Redis; dashboard alert rule references DLQ length

**Dependencies:** None (independent of 54.1–54.3; can run in parallel with 54.2)

---

### 54.5 — Observability Spine `[implementer]`

**Objective:** Every coordinator query has a complete end-to-end trace stored and queryable.

**Deliverables:**
- PostgreSQL table: `query_traces(trace_id uuid, query text, intent text, profile text, retrieval_hits int, retrieval_latency_ms int, rag_skipped bool, llm_model text, tokens_in int, tokens_out int, llm_latency_ms int, total_latency_ms int, trace_at timestamptz)`
- `TraceCollector` context manager in coordinator: wraps every `/query` handler; commits trace on exit (success or error)
- `GET /api/traces` in dashboard:
  - Query params: `?limit=100&intent=<intent>&min_latency_ms=<n>`
  - Returns last N traces with full schema
- Dashboard panel: "Query Traces" card in Intelligence lane (Phase 53 lens system)
  - Columns: trace_id (short), intent, profile, RAG hit/miss, total latency, timestamp
  - Auto-refresh every 30s
- Slow trace alert: if `total_latency_ms > 30000` → append to dashboard Command Deck alert list
- aq-qa checks:
  - `1.0.11`: `query_traces` table exists; `GET /api/traces` returns records
  - `1.0.12`: After 3 test queries, `query_traces` has ≥3 rows with `intent` populated

**Dependencies:** 54.2 (intent field), 54.3 (rag_skipped field); can stub missing fields and fill as 54.2/54.3 land

---

### 54.6 — Continuous Spec-Driven Evaluation `[implementer]`

**Objective:** Every phase commit triggers eval. Regressions are caught automatically.

**Deliverables:**
- `POST /eval/run` coordinator endpoint:
  - Triggers: 12-case SWE benchmark (Phase 43) + full aq-qa suite
  - Stores result in PostgreSQL `eval_trend(id, phase_tag, score, checks_passed, checks_failed, run_at)`
- `GET /eval/trend` endpoint: last 10 runs as JSON
- Dashboard eval panel update: render trend as sparkline (last 10 scores) + current pass/fail count
- Pre-commit hook integration: `scripts/governance/tier0-validation-gate.sh` gains eval gate call:
  - If last eval score drops >5% from previous run → block commit with message + show delta
  - Skip gate if `SKIP_EVAL_GATE=1` env var set (escape hatch for non-code commits)
- Regression auto-flag: after each run, compare check list against previous run; if any check newly fails → append to dashboard alert list
- aq-qa check:
  - `1.0.13`: `eval_trend` table exists; `GET /eval/trend` returns ≥1 entry; `/eval/run` responds 202

**Dependencies:** 54.5 (traces table confirms DB access pattern); eval gate integration touches `tier0-validation-gate.sh` — validate with `bash -n`

---

## Execution Order

```
Pre-conditions (Gemini check, aq-qa green)
  ↓
54.1 (Memory)  ←parallel→  54.4 (Durable DAG)
  ↓
54.2 (Intent Routing)  ←parallel→  54.5 (Observability stub)
  ↓
54.3 (Active RAG)
  ↓
54.5 (Observability full — fill intent/rag fields)
  ↓
54.6 (Continuous Eval)
  ↓
Full acceptance gate (72 checks, all criteria met)
```

---

## Validation Gates Per Slice

| Slice | Gate Command | Pass Condition |
|-------|-------------|----------------|
| 54.1 | `aq-qa 0` + `aq-memory-recall-benchmark` | checks 1.0.1–1.0.3 pass; recall ≥85% |
| 54.2 | `aq-qa 0` | checks 1.0.4–1.0.5 pass |
| 54.3 | `aq-qa 0` + L6 health check | checks 1.0.6–1.0.7 pass; L6 = healthy |
| 54.4 | `aq-qa 0` + DAG resume test | checks 1.0.8–1.0.10 pass; resume cycle succeeds |
| 54.5 | `aq-qa 0` + traces query | checks 1.0.11–1.0.12 pass |
| 54.6 | `aq-qa 0` + eval run | check 1.0.13 pass; regression gate functional |
| **Full** | `aq-qa 0` | **72 checks passing, 0 failing** |

---

## Commit Template

```
feat(phase-54.N): <slice description>

- <specific change 1>
- <specific change 2>
- aq-qa checks: 1.0.X, 1.0.Y pass

Co-Authored-By: claude-sonnet-4-6 <noreply@anthropic.com>
```

---

## Rollback

Each slice is independently reversible:
- 54.1: delete `memory_broker.py`; delete AIDB `episodic`+`procedural` projects; remove aq-qa checks
- 54.2: delete `intent_classifier.py` + `intent-routing-map.json`; remove routing log field from /query
- 54.3: delete `rag_augmentor.py`; revert L6 health gate; aq-report posture reverts to `historical`
- 54.4: `DROP TABLE workflow_checkpoints`; remove resume endpoint; remove DLQ alert
- 54.5: `DROP TABLE query_traces`; remove traces endpoint + dashboard panel
- 54.6: `DROP TABLE eval_trend`; remove eval endpoints; remove pre-commit eval gate

---

## Architecture Map After Phase 54

```
Query In
  ↓
IntentClassifier (54.2) — <50ms, embedding-based
  ↓
RagAugmentor (54.3) — async retrieval, 500ms cap
  ↓
[AIDB: semantic | logic-patterns | episodic] ← MemoryBroker (54.1)
  ↓
Coordinator dispatch → LLM (local Qwen3 :8080)
  ↓
TraceCollector (54.5) — full span logged
  ↓
MemoryBroker.write(episodic, response)
  ↓
Response Out

DAG Workflows → WorkflowCheckpointer (54.4) → PostgreSQL checkpoints
EvalRunner (54.6) → eval_trend → pre-commit gate
```

---

## Notes for Implementer

- Never hardcode ports — use `AIDB_PORT`, `LLAMA_EMBED_PORT`, `HYBRID_COORDINATOR_PORT` from env
- All new Python files: `py_compile` before commit
- All new shell scripts: `bash -n` before commit
- PostgreSQL access: use existing coordinator DB connection; do not open new pool
- AIDB project creation: `POST /documents` with `project=episodic` auto-creates project
- llama-embed :8081 endpoint: check it's healthy before relying on it in IntentClassifier; fall back to keyword heuristics if down
