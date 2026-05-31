# Phase 20 — World Model: Predictive Context Warming

Status: `complete`
Created: 2026-04-30
Owner: Claude (orchestrator) / Qwen (implementation)
Source: System Assessment & AGI Scaffold Architecture (2026-04-30)
Predecessor: Phase 18 (agent mesh — collective memory), Phase 13 (knowledge ingestion)

---

## Objective

Give the AI stack lightweight anticipation: based on patterns in recent queries, time of day,
and project state, proactively warm the semantic cache and pre-load relevant context before
the user asks. This reduces first-query latency and makes the stack feel "aware" of ongoing work.

This is the final layer of the AGI scaffold — it requires Phases 16–19 to be functional
before full activation, but can be deployed in passive/logging mode earlier.

---

## Scope Lock

In scope:
- `ai-stack/world-model/` (new directory):
  - `intent_forecaster.py` — predicts likely next query from recency patterns
  - `context_warmer.py` — pre-loads AIDB + semantic cache for predicted queries
  - `pattern_index.py` — builds/updates query-sequence patterns in PostgreSQL
- Hybrid coordinator endpoint: `GET /world/forecast` (passive read of current prediction)
- Systemd timer: `ai-context-warmer.timer` — runs context warming every 15 minutes
- Route registration in `ai-stack/mcp-servers/hybrid-coordinator/http_server.py`
- PostgreSQL table: `query_sequence_patterns`

Out of scope:
- Spinning up ephemeral NixOS VMs for sandboxed experimentation (requires too much RAM)
- Training ML models (lightweight heuristics only — no model fine-tuning)
- Changes to existing query routing or cache invalidation
- Changes to AIDB schema or Qdrant collections

Constraints:
- Pattern matching is purely heuristic (recency + co-occurrence + time-of-day)
- NO user behavioral data persisted beyond rolling 7d window
- Context warming calls existing `/query` with `skip_gap_tracking=true` to avoid pollution
- PostgreSQL table must have RLS or restricted service user (no world-model data leaks)
- Timer runs only when `WORLD_MODEL_ENABLED=true` (declarative kill switch)
- Performance budget: warming job must complete within 60s per run

---

## Context References

Files to read first:
- `ai-stack/mcp-servers/hybrid-coordinator/route_handler.py` (query pattern available here)
- `ai-stack/database/postgres/schemas/` (existing schema patterns)
- `ai-stack/mcp-servers/hybrid-coordinator/memory_context_handlers.py` (AIDB interaction pattern)
- `nix/modules/roles/ai-stack.nix` (systemd timer pattern)
- `nix/modules/core/options.nix` (option definition pattern)

---

## Steps

### 20.1 — Pattern Index (PostgreSQL)

**Owner**: Qwen
**Files**:
- `ai-stack/world-model/pattern_index.py` (new)
- `ai-stack/database/postgres/migrations/` — new migration file

Tasks:
1. Create migration file `V20__world_model_query_patterns.sql`:
   ```sql
   CREATE TABLE IF NOT EXISTS query_sequence_patterns (
     id SERIAL PRIMARY KEY,
     query_hash TEXT NOT NULL,
     query_summary TEXT NOT NULL,     -- first 120 chars of query
     hour_of_day INT NOT NULL,        -- 0-23
     day_of_week INT NOT NULL,        -- 0-6
     follow_on_hashes TEXT[],         -- hashes of queries that followed within 1h
     occurrence_count INT DEFAULT 1,
     last_seen TIMESTAMPTZ DEFAULT NOW(),
     created_at TIMESTAMPTZ DEFAULT NOW()
   );
   CREATE INDEX IF NOT EXISTS idx_qsp_hash ON query_sequence_patterns(query_hash);
   CREATE INDEX IF NOT EXISTS idx_qsp_hour ON query_sequence_patterns(hour_of_day);
   ```
2. Create `PatternIndex` class in `pattern_index.py`:
   - `record(query_text, previous_hash=None)` — upsert into table; link to previous if provided
   - `predict_next(current_hash, top_k=3)` → list of `(query_summary, probability)` tuples:
     - Query: "what follows `current_hash` most often at this hour of day?"
     - Falls back to "most frequent queries at this hour" if no specific follow-ons
   - `prune_old(days=7)` — delete rows where `last_seen < NOW() - interval '7 days'`
   - Reads DB connection from `POSTGRES_*` env vars (existing pattern)

Validation:
- `python3 -m py_compile ai-stack/world-model/pattern_index.py`
- Migration: `psql $DB_URL < migration.sql` exits 0
- `python3 -c "from pattern_index import PatternIndex; p = PatternIndex(); p.record('test query')"`

### 20.2 — Intent Forecaster

**Owner**: Qwen
**Files**: `ai-stack/world-model/intent_forecaster.py` (new)

Tasks:
1. Create `IntentForecaster` class:
   - `forecast(session_id=None)` → `ForecastResult`:
     - `predictions`: list of `{query: str, confidence: float, source: str}` (top 3)
     - `sources`: `recency` | `pattern` | `time_of_day`
     - Combines signals:
       1. Last 3 queries this session (recency) — highest weight
       2. Pattern index follow-on predictions — medium weight
       3. Time-of-day most-frequent queries — low weight (fallback)
   - `get_recent_queries(session_id, limit=3)` → list from Redis session store
     (reads `multi_turn:<session_id>` if available, else recent `/query` logs)
   - Returns empty list gracefully if no data available

Validation:
- `python3 -m py_compile ai-stack/world-model/intent_forecaster.py`
- `python3 -c "from intent_forecaster import IntentForecaster; print(IntentForecaster().forecast())"`

### 20.3 — Context Warmer

**Owner**: Qwen
**Files**: `ai-stack/world-model/context_warmer.py` (new)

Tasks:
1. Create `ContextWarmer` class:
   - `warm(predictions, dry_run=False)`:
     - For each prediction with `confidence > WORLD_MODEL_WARM_THRESHOLD` (default 0.4):
       - Call `POST /query` with `{"query": pred.query, "skip_gap_tracking": true,
         "context_source": "world_model_prewarm"}`
       - Log: `{query_hash, timestamp, confidence, cache_hit_after}`
     - dry_run=True: log intent only, no HTTP calls
   - Respects budget: max `WORLD_MODEL_MAX_WARM_QUERIES` per run (default 5)
   - Writes warming log to `${DATA_DIR}/hybrid/telemetry/world-model-warm-latest.json`

Validation:
- `python3 -m py_compile ai-stack/world-model/context_warmer.py`
- `WORLD_MODEL_MAX_WARM_QUERIES=1 python3 -c "from context_warmer import ContextWarmer; ContextWarmer().warm([], dry_run=True)"`

### 20.4 — Systemd Timer + Entry Point

**Owner**: Qwen
**Files**:
- `scripts/ai/aq-context-warm` (new script — CLI entry point)
- `nix/modules/roles/ai-stack.nix` (add `ai-context-warmer.service` + `ai-context-warmer.timer`)

Tasks:
1. Create `scripts/ai/aq-context-warm`:
   ```bash
   #!/usr/bin/env bash
   set -euo pipefail
   # Run intent forecaster + context warmer
   exec python3 -c "
   from world_model.intent_forecaster import IntentForecaster
   from world_model.context_warmer import ContextWarmer
   import sys
   dry_run = '--dry-run' in sys.argv
   predictions = IntentForecaster().forecast()
   ContextWarmer().warm(predictions, dry_run=dry_run)
   " "$@"
   ```
2. In `ai-stack.nix`, add service + timer following existing timer pattern (e.g. `ai-weekly-report.timer`):
   - Service: `ai-context-warmer.service` (Type=oneshot, ExecStart=`aq-context-warm`)
   - Timer: `ai-context-warmer.timer` (OnCalendar=`*:0/15` — every 15 minutes)
   - Condition: `WORLD_MODEL_ENABLED=true` checked in script before running

Validation:
- `bash -n scripts/ai/aq-context-warm`
- `nix-instantiate --parse nix/modules/roles/ai-stack.nix` exits 0
- After rebuild: `systemctl status ai-context-warmer.timer` shows enabled

### 20.5 — Forecast Endpoint + Declarative Options

**Owner**: Qwen
**Files**:
- `ai-stack/mcp-servers/hybrid-coordinator/http_server.py` (add route)
- `nix/modules/core/options.nix`

Tasks:
1. Add `GET /world/forecast` in `http_server.py` (simple inline handler — no new module needed):
   - Returns latest warming log + top 3 predictions from `IntentForecaster().forecast()`
   - Requires API key auth
2. Add to `options.nix` under `mySystem.aiStack`:
   ```nix
   worldModel = {
     enable = mkEnableOption "Predictive context warming";
     warmThreshold = mkOption { type = types.str; default = "0.4"; };
     maxWarmQueriesPerRun = mkOption { type = types.int; default = 5; };
     patternRetentionDays = mkOption { type = types.int; default = 7; };
   };
   ```
3. Inject `WORLD_MODEL_ENABLED`, `WORLD_MODEL_WARM_THRESHOLD`, `WORLD_MODEL_MAX_WARM_QUERIES`
   into hybrid coordinator and context warmer service envs

Validation:
- `nix-instantiate --parse nix/modules/core/options.nix` exits 0
- `curl -s -H "X-API-Key: $(cat /run/secrets/hybrid_coordinator_api_key)" http://localhost:8003/world/forecast | python3 -m json.tool`

---

## Verification Matrix

Before marking any task done:
1. `python3 -m py_compile` for all new Python files
2. `bash -n scripts/ai/aq-context-warm`
3. `nix-instantiate --parse` for all touched Nix files
4. PostgreSQL migration applied: `psql $DB_URL -c "\d query_sequence_patterns"` shows table
5. `aq-context-warm --dry-run` exits 0, writes log file
6. `GET /world/forecast` returns 200 with `predictions` key
7. `aq-qa 0` → 39+ passed, 0 failed (warming must not pollute gap tracking)
8. Rollback: `WORLD_MODEL_ENABLED=false` in Nix options; timer auto-disables

---

## Work Queue

### Task: WM-001
- Phase: 20.1
- Owner agent: claude
- Files: `ai-stack/world-model/pattern_index.py`, `ai-stack/database/postgres/migrations/V20__world_model_query_patterns.sql`
- Status: **done** (2026-05-01)

### Task: WM-002
- Phase: 20.2
- Owner agent: claude
- Files: `ai-stack/world-model/intent_forecaster.py`
- Status: **done** (2026-05-01)

### Task: WM-003
- Phase: 20.3
- Owner agent: claude
- Files: `ai-stack/world-model/context_warmer.py`
- Status: **done** (2026-05-01)

### Task: WM-004
- Phase: 20.4
- Owner agent: claude
- Files: `scripts/ai/aq-context-warm`, `nix/modules/roles/ai-stack.nix`
- Status: **done** (2026-05-01)

### Task: WM-005
- Phase: 20.5
- Owner agent: claude
- Files: `ai-stack/mcp-servers/hybrid-coordinator/http_server.py`, `nix/modules/core/options.nix`
- Status: **done** (2026-05-01)

---

## Rollback

- Kill switch: `WORLD_MODEL_ENABLED=false` (declarative) → rebuild → timer disabled
- PostgreSQL table: `DROP TABLE query_sequence_patterns;` (no foreign key dependencies)
- Warming log: delete `${DATA_DIR}/hybrid/telemetry/world-model-warm-latest.json`
- Generation rollback: `sudo nixos-rebuild switch --rollback`
