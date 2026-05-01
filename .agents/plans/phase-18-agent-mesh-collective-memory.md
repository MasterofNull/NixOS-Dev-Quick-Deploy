# Phase 18 — Agent Mesh: Collective Memory for Multi-Agent Teams

Status: `complete`
Created: 2026-04-30
Owner: Claude (orchestrator) / Qwen (implementation)
Source: System Assessment & AGI Scaffold Architecture (2026-04-30)
Predecessor: Phase 13 (memory systems — complete), Phase 16 (identity kernel)

---

## Objective

Extend `agent_spawner.py` so that multi-agent teams share state during a collaboration
and write a collaboration record to AIDB when they finish. When the next team forms for
a similar task, the coordinator retrieves the top-3 relevant past collaborations as L2
context — so agents don't start from zero every time.

Current state: each team is a stateless subprocess cluster with no inter-agent message
passing and no post-collaboration memory.

---

## Scope Lock

In scope:
- `ai-stack/local-agents/agent_spawner.py` — add Redis pub/sub blackboard + experience_replay retrieval
- `ai-stack/local-agents/collective_memory.py` (new) — collaboration serialization + AIDB write
- `ai-stack/local-agents/experience_replay.py` (new) — AIDB retrieval of past collaborations
- Hybrid coordinator endpoint: `GET /agents/mesh/status` and `GET /agents/mesh/collaborations`
- Route registration in `ai-stack/mcp-servers/hybrid-coordinator/agents_task_handlers.py`

Out of scope:
- Changing agent role definitions or spawner subprocess mechanics
- Changing AIDB schema
- Adding new agent roles
- Identity kernel integration (Phase 16 — separate)

Constraints:
- Redis pub/sub channel: `agent-mesh:<team_id>` (namespaced, no collision with existing channels)
- Collaboration records stored in AIDB with `project=agent-collaborations`
- Retrieval uses existing `/vector/search` endpoint (no new AIDB API surface)
- Blackboard is ephemeral (Redis TTL=3600s); collaboration archive is permanent (AIDB)
- Never store secrets or prompt content verbatim — store metadata and outcome only

---

## Context References

Files to read first:
- `ai-stack/local-agents/agent_spawner.py` (full file — 649 lines)
- `ai-stack/mcp-servers/hybrid-coordinator/agentic_memory_journal.py` (Redis + AIDB pattern)
- `ai-stack/mcp-servers/hybrid-coordinator/agents_task_handlers.py` (route registration pattern)
- `nix/modules/core/options.nix` (option definition pattern)

---

## Steps

### 18.1 — Collective Memory Module

**Owner**: Qwen
**Files**: `ai-stack/local-agents/collective_memory.py` (new)

Tasks:
1. Create `CollectiveMemory` class:
   - `__init__(redis_url, aidb_url, aidb_api_key)` — from env vars
   - `blackboard_set(team_id, key, value)` — `HSET agent-mesh:<team_id> <key> <value>`, TTL=3600
   - `blackboard_get(team_id, key)` — `HGET agent-mesh:<team_id> <key>`
   - `blackboard_broadcast(team_id, message)` — `PUBLISH agent-mesh:<team_id> <message>`
   - `archive_collaboration(team_id, metadata)` — writes to AIDB:
     ```
     POST /documents
     {
       content: "<task_summary> | roles: <roles> | outcome: <outcome> | patterns: <patterns>",
       project: "agent-collaborations",
       title: "collab-<team_id>",
       relative_path: "collaborations/<team_id>.json"
     }
     ```
   - `metadata` dict must include: `task_summary`, `roles`, `outcome`, `duration_s`,
     `patterns` (list of strings — what worked / what didn't)

Validation:
- `python3 -m py_compile ai-stack/local-agents/collective_memory.py`
- `python3 -c "from collective_memory import CollectiveMemory; print('ok')"`

### 18.2 — Experience Replay Module

**Owner**: Qwen
**Files**: `ai-stack/local-agents/experience_replay.py` (new)

Tasks:
1. Create `ExperienceReplay` class:
   - `retrieve(task_description, top_k=3)` → list of past collaboration records:
     - `POST /vector/search` to AIDB with `{"query": task_description, "limit": top_k, "project": "agent-collaborations"}`
     - Returns list of `{content, metadata, distance}` (use `distance` field — score is null per MEMORY.md)
     - Filters: `distance < 0.5` (close semantic match only)
   - `format_as_context(records)` → str — formats top-k for injection into team prompt:
     ```
     === Past Collaboration Context ===
     [1] Task: <task_summary> | Roles: <roles> | Outcome: <outcome>
         Patterns that worked: <patterns>
     ```
   - Returns empty string if no matches (graceful degradation)

Validation:
- `python3 -m py_compile ai-stack/local-agents/experience_replay.py`
- `python3 -c "from experience_replay import ExperienceReplay; r = ExperienceReplay(); print(r.format_as_context([]))"`

### 18.3 — Wire Into agent_spawner.py

**Owner**: Qwen
**Files**: `ai-stack/local-agents/agent_spawner.py`

Tasks:
1. Read `agent_spawner.py` fully — identify `spawn_team()` or equivalent entry point
2. Before spawning:
   - Instantiate `ExperienceReplay` and call `retrieve(task_description)`
   - If records found: prepend `format_as_context(records)` to team briefing/prompt
3. On team completion callback (or after subprocess join):
   - Instantiate `CollectiveMemory` and call `archive_collaboration(team_id, metadata)`
   - `metadata.patterns` = summarize what tools/steps succeeded vs failed from logs
4. Add env var reads: `AGENT_MESH_REDIS_URL`, `AGENT_MESH_AIDB_URL`, `AGENT_MESH_AIDB_KEY`
   — fall back to `REDIS_URL`, `AIDB_URL`, `AIDB_API_KEY_FILE` if mesh-specific vars absent

Validation:
- `python3 -m py_compile ai-stack/local-agents/agent_spawner.py`
- Dry-spawn smoke: launch a minimal team with `--dry-run` flag if supported, verify no crash

### 18.4 — Mesh Status Endpoints

**Owner**: Qwen
**Files**: `ai-stack/mcp-servers/hybrid-coordinator/agents_task_handlers.py`

Tasks:
1. Add to `agents_task_handlers.py` (follow existing `register_routes` pattern):
   - `GET /agents/mesh/status` → `{active_teams: [...], redis_connected: bool, aidb_connected: bool}`
   - `GET /agents/mesh/collaborations?limit=10` → recent collaboration records from AIDB
2. Both endpoints require API key auth (reuse existing auth middleware pattern)

Validation:
- `python3 -m py_compile ai-stack/mcp-servers/hybrid-coordinator/agents_task_handlers.py`
- `curl -s -H "X-API-Key: $(cat /run/secrets/hybrid_coordinator_api_key)" http://localhost:8003/agents/mesh/status | python3 -m json.tool`

### 18.5 — Declarative Options

**Owner**: Qwen
**Files**: `nix/modules/core/options.nix`

Tasks:
1. Add under `mySystem.aiStack`:
   ```nix
   agentMesh = {
     enable = mkEnableOption "Agent mesh collective memory";
     collaborationRetentionDays = mkOption { type = types.int; default = 90; };
     blackboardTtlSeconds = mkOption { type = types.int; default = 3600; };
   };
   ```
2. Inject `AGENT_MESH_ENABLED`, `AGENT_MESH_BLACKBOARD_TTL` into spawner service env (if applicable)

Validation:
- `nix-instantiate --parse nix/modules/core/options.nix` exits 0

---

## Verification Matrix

Before marking any task done:
1. `python3 -m py_compile` for all touched Python files
2. `nix-instantiate --parse` for Nix files
3. `GET /agents/mesh/status` returns 200 with `redis_connected: true`
4. `GET /agents/mesh/collaborations` returns 200 (empty list is acceptable before first collab)
5. `aq-qa 0` → 39+ passed, 0 failed
6. Rollback: `git revert <commits>`, Redis TTL auto-expires mesh keys

---

## Work Queue

### Task: AMC-001
- Phase: 18.1
- Owner agent: claude
- Files: `ai-stack/local-agents/collective_memory.py`
- Status: **done** (2026-04-30)

### Task: AMC-002
- Phase: 18.2
- Owner agent: claude
- Files: `ai-stack/local-agents/experience_replay.py`
- Status: **done** (2026-04-30)

### Task: AMC-003
- Phase: 18.3
- Owner agent: claude
- Files: `ai-stack/local-agents/agent_spawner.py`
- Status: **done** (2026-04-30)

### Task: AMC-004
- Phase: 18.4
- Owner agent: claude
- Files: `ai-stack/mcp-servers/hybrid-coordinator/agents_task_handlers.py`
- Status: **done** (2026-04-30)

### Task: AMC-005
- Phase: 18.5
- Owner agent: claude
- Files: `nix/modules/core/options.nix`
- Status: **done** (2026-04-30)

---

## Rollback

- Python module additions: delete new files, `git revert` agent_spawner.py changes
- Redis blackboard keys: TTL=3600s auto-expire; `redis-cli DEL "agent-mesh:*"` for immediate cleanup
- AIDB collaboration records: `DELETE /documents` filtered by `project=agent-collaborations`
- Nix options: generation rollback (`sudo nixos-rebuild switch --rollback`)
