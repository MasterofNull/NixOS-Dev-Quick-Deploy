# Phase 55 — Temporal Memory, Crystalline Distillation & Agent Ops SRE
# Status: PLANNED
# PRD: .agents/plans/PROJECT-AI-HARNESS-EVOLUTION-PRD.md (Section 5, Claude annotations)
# Depends on: Phase 54 COMPLETE (commits 4a6cd30c–b62dd21f)

## Objective
Complete the three genuine gaps identified in collaborative Gemini/Claude PRD review that Phase 54 did not address:
- Supersession logic (temporal fact invalidation)
- Crystalline memory (session distillation)
- Agent Ops SRE profile (reasoning drift detection)

aq-qa target: 16 new checks (1.1.1–1.1.16), total 87 checks.

---

## Execution Order DAG

55.0 ──► 55.1 ──► 55.3 ──► 55.2

Rationale: retrieval gate first (so memory work does not build on a failing `/query` path);
supersession second (so crystallization can tag distilled insights with valid_until);
drift detection second (builds on existing TraceCollector table, no new infra);
crystallization last (most compute-intensive, depends on both).

---

## Slice 55.0 — Retrieval Gate Stabilization (Codex Precondition)

### Problem
`aq-qa 0` is blocked before Phase 55 can safely begin. The original
`ai-security-audit.service` failure is fixed, but both remaining failures converge on
the hybrid `/query` path:

- `0.5.6` Continue/editor prompt to feedback smoke
- `0.7.2` hybrid `/query` retrieval smoke

Observed response:

```json
{"error":"route_search_failed","detail":"Expecting value: line 1 column 1 (char 0)"}
```

### Deliverables
1. Restore `/query` retrieval success for the existing smoke payloads.
2. Preserve existing `/health`, `/hints`, `/workflow/plan`, and `/v1/orchestrate` behavior.
3. Add/adjust a focused regression check if the fix touches parsing or route error handling.
4. Rerun `aq-qa 0` before implementing 55.1.

### Validation
- `scripts/testing/smoke-continue-editor-flow.sh`
- `aq-qa 0` checks `0.5.6` and `0.7.2`
- `scripts/governance/tier0-validation-gate.sh --pre-commit`

---

## Slice 55.1 — Supersession Logic (Temporal Fact Invalidation)

### Problem
AIDB stores vector embeddings without temporal validity. New facts never deprecate old ones,
causing context rot: agents retrieve stale constraints alongside current ones.

### Deliverables
1. `ai-stack/mcp-servers/hybrid-coordinator/memory_superseder.py`
   - `MemorySuperseder` class
   - `supersede(fact_id, replacement_text, reason)` → marks old doc `valid_until=now()` in AIDB metadata, stores replacement
   - `GET /memory/supersede/history` → last N supersession events
   - `POST /memory/supersede` → `{fact_id, replacement, reason}` → `{superseded: bool, old_valid_until}`
   - PostgreSQL `memory_supersessions` table (idempotent DDL)
   - Atomic: old invalidation + new ingest in single transaction or neither

2. AIDB metadata extension: `valid_until` field on ingest payloads
   - `POST /documents` already accepts arbitrary metadata; coordinator sets `valid_until` on stale docs

3. Auth: add `/memory/supersede` to both `LOOPBACK_AGENT_PREFIXES` (core/auth_middleware.py) AND inline `agent_prefixes` in http_server.py:~1412

### aq-qa checks (1.1.1–1.1.4)
- 1.1.1: MemorySuperseder importable
- 1.1.2: `POST /memory/supersede` registered (returns valid JSON)
- 1.1.3: `GET /memory/supersede/history` registered
- 1.1.4: supersession DDL present in memory_superseder.py

---

## Slice 55.3 — Agent Ops SRE Profile (Reasoning Drift Detection)

### Problem
`TraceCollector` captures latency and intent per query but not reasoning quality drift:
repeated tool retries, intent flip-flop across a session, escalating token cost per query.
No alert surface exists for the operator when the system starts "thrashing."

### Deliverables
1. `drift_analyzer.py`
   - `DriftAnalyzer` class
   - `compute_drift(window=20)` → reads last N rows from `query_traces`, scores:
     - `intent_flip_rate`: fraction of consecutive queries with different intent
     - `retry_escalation`: avg retries per trace (from trace metadata if available)
     - `latency_trend`: slope of total_ms over window (positive = degrading)
     - Combined `drift_score` 0.0–1.0
   - `GET /api/traces/drift` → `{drift_score, window_size, alert_triggered, breakdown}`
   - Alert threshold from `config/runtime-budget-policy.json` key `drift_alert_threshold` (default 0.7)
   - Degrades gracefully: postgres unavailable → `{drift_score: null, error: "postgres_unavailable"}`

2. Switchboard profile `agent-ops` in `config/switchboard-profiles.json` (if exists) or new `config/agent-ops-profile.json`
   - Routes to SRE-optimized system prompt focused on system health, not task completion
   - Activates automatically when drift_score > threshold (coordinator sets profile hint)

3. Auth: add `/api/traces/drift` to both auth layers

### aq-qa checks (1.1.5–1.1.9)
- 1.1.5: DriftAnalyzer importable
- 1.1.6: `GET /api/traces/drift` registered and returns valid JSON
- 1.1.7: drift_score is null or float 0–1 (not error) when postgres unavailable
- 1.1.8: `drift_alert_threshold` key present in runtime-budget-policy.json
- 1.1.9: agent-ops profile config file present

---

## Slice 55.2 — Crystalline Memory (Session Distillation Pipeline)

### Problem
Continue/agent sessions accumulate raw chat logs. No pipeline compresses them into
structured episodic insights. Token bloat increases with session count; agents re-derive
known facts on every new session.

### Deliverables
1. `memory_crystallizer.py`
   - `MemoryCrystallizer` class
   - `crystallize_session(session_path)` → reads session JSON → sends to Qwen via llama.cpp
     with distillation prompt → extracts structured facts → stores to AIDB `episodic` collection
   - Idempotent: tracks `session_hash` in `crystallized_sessions` PostgreSQL table; re-run is no-op
   - `valid_until` set on distilled facts using supersession logic from 55.1
   - `GET /memory/crystalline/status` → `{sessions_processed, insights_stored, last_run}`
   - `POST /memory/crystalline/run` → trigger distillation for a session path (202 accepted, background)

2. `scripts/ai/aq-crystallize` — CLI to trigger crystallization manually
   - Usage: `aq-crystallize [--session-dir PATH] [--dry-run]`
   - Reads from `~/.continue/sessions/` by default

3. Auth: add `/memory/crystalline/` to both auth layers

### aq-qa checks (1.1.10–1.1.16)
- 1.1.10: MemoryCrystallizer importable
- 1.1.11: `GET /memory/crystalline/status` registered (returns valid JSON)
- 1.1.12: `POST /memory/crystalline/run` registered (202 or error JSON)
- 1.1.13: crystallized_sessions DDL present in memory_crystallizer.py
- 1.1.14: idempotency: session_hash tracking present in DDL
- 1.1.15: aq-crystallize script present and executable
- 1.1.16: `/memory/crystalline/` in both auth prefix lists

---

## Spec-Driven Constraints (Mandatory for All Slices)

1. Every new endpoint must have an aq-qa check before PR merges.
2. All new AIDB schema changes must be idempotent (IF NOT EXISTS pattern).
3. Supersession writes must be atomic — PostgreSQL transaction wrapping both invalidation and new ingest.
4. Crystallization must be idempotent — session_hash in processed table, re-run is no-op.
5. Drift score degrades gracefully — null (not error) when postgres unavailable.
6. DUAL AUTH GATE: always patch BOTH `LOOPBACK_AGENT_PREFIXES` in `core/auth_middleware.py`
   AND inline `agent_prefixes` in `http_server.py` `_is_loopback_agent_request()` (~line 1412).

---

## Validation Gate

After all slices:
```bash
aq-qa 55       # 16/16 new checks
aq-qa 0        # no regression on phase 0
aq-qa 54       # 13/13 still passing
```

Commit format: `feat(memory): phase 55 — temporal supersession + crystalline distillation + agent-ops drift`
