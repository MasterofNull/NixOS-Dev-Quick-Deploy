# Phase 16 — Identity Kernel: Persistent Self-Model

Status: `pending`
Created: 2026-04-30
Owner: Claude (orchestrator) / Qwen (implementation slices)
Source: System Assessment & AGI Scaffold Architecture (2026-04-30)
Predecessor: Phase 15.1 + 15.3 (model fleet manager + agentic memory journal — complete)

---

## Objective

Give the AI stack a persistent, append-only identity that survives reboots. The system
should be able to answer `GET /identity/self` with a structured narrative summary of its
own capabilities, relationships, and operational history — reconstructed from journal replay
on each boot.

This is the prerequisite foundation for all higher-order AGI scaffold layers (Phases 17–20).

---

## Scope Lock

In scope:
- `ai-stack/identity-kernel/` module (new directory)
  - `narrative_engine.py` — append-only journal, summary generation
  - `value_constitution.py` — user-editable value hierarchy loader/validator
  - `checkpoint_service.py` — systemd-compatible checkpoint writer (every N minutes)
- NixOS module: `nix/modules/services/identity-kernel.nix`
- NixOS option: `mySystem.aiStack.identityKernel.*` in `nix/modules/core/options.nix`
- Hybrid coordinator endpoint: `GET /identity/self`
- Route registration in `ai-stack/mcp-servers/hybrid-coordinator/http_server.py`

Out of scope:
- Affective/values modulation of outputs (Phase 19)
- Agent mesh shared memory (Phase 18)
- Inference model changes
- Qdrant schema changes

Constraints:
- NixOS-first: journal stored under a declarative state path (no hardcoded `/var/lib/...`)
- No secrets in journal entries; paths redacted before write
- Identity checkpoint must not block query path (async write)
- Value constitution must be user-editable YAML/JSON (not hardcoded)

---

## Context References

Files to read first:
- `ai-stack/mcp-servers/hybrid-coordinator/http_server.py` (route registration pattern)
- `ai-stack/mcp-servers/hybrid-coordinator/agentic_memory_journal.py` (existing journal — reuse pattern)
- `nix/modules/core/options.nix` (port/option definitions — follow pattern exactly)
- `nix/modules/roles/ai-stack.nix` (systemd unit pattern)
- `nix/modules/services/mcp-servers.nix` (env injection pattern)

---

## Steps

### 16.1 — Narrative Engine (Core Journal)

**Owner**: Qwen
**Files**: `ai-stack/identity-kernel/narrative_engine.py` (new)

Tasks:
1. Read `agentic_memory_journal.py` to understand existing Redis hot + AIDB persistent pattern
2. Create `narrative_engine.py` with:
   - `append_event(event_type, payload)` — writes timestamped entry to append-only JSONL file
   - `replay_journal(since=None)` — reads journal, returns ordered events
   - `generate_summary()` — produces dict: `{capabilities, relationships, history_tail, uptime_sessions}`
   - Journal stored at `${IDENTITY_JOURNAL_PATH:-/var/lib/ai-stack/identity/journal.jsonl}`
3. Event types: `boot`, `capability_registered`, `user_interaction`, `agent_collaboration`,
   `self_improvement`, `error_pattern`, `value_update`

Validation:
- `python3 -m py_compile ai-stack/identity-kernel/narrative_engine.py`
- Unit smoke: `python3 -c "from narrative_engine import NarrativeEngine; e = NarrativeEngine('/tmp/test-journal.jsonl'); e.append_event('boot', {'session': 1}); print(e.generate_summary())"`

### 16.2 — Value Constitution Loader

**Owner**: Qwen
**Files**: `ai-stack/identity-kernel/value_constitution.py` (new), `config/identity-values.yaml` (new)

Tasks:
1. Create `config/identity-values.yaml` with default value hierarchy:
   ```yaml
   values:
     - name: reciprocity
       weight: 1.0
       description: Give back as much as received
     - name: inclusivity
       weight: 0.9
       description: Surface all relevant perspectives
     - name: empathy
       weight: 0.9
       description: Model user emotional state
     - name: beauty
       weight: 0.7
       description: Prefer elegant, clear solutions
     - name: compassion
       weight: 0.8
       description: Reduce friction and frustration
   ```
2. Create `value_constitution.py`:
   - `load(path)` — reads YAML, validates schema, returns ordered value list
   - `get_active_weights()` — returns `{name: weight}` dict for runtime use
   - Fails hard if YAML malformed (startup gate)

Validation:
- `python3 -m py_compile ai-stack/identity-kernel/value_constitution.py`
- `python3 -c "from value_constitution import ValueConstitution; v = ValueConstitution('config/identity-values.yaml'); print(v.get_active_weights())"`

### 16.3 — Checkpoint Service

**Owner**: Qwen
**Files**: `ai-stack/identity-kernel/checkpoint_service.py` (new)

Tasks:
1. Create `checkpoint_service.py`:
   - Reads `IDENTITY_CHECKPOINT_INTERVAL_SECONDS` env var (default 300)
   - On interval: calls `narrative_engine.generate_summary()` → writes to
     `${IDENTITY_CHECKPOINT_PATH:-/var/lib/ai-stack/identity/checkpoint.json}`
   - On startup: replays journal and writes initial checkpoint
   - Designed to run as a lightweight thread inside the hybrid coordinator process
     OR as a standalone systemd oneshot (configurable via `IDENTITY_SERVICE_MODE`)

Validation:
- `python3 -m py_compile ai-stack/identity-kernel/checkpoint_service.py`
- Smoke: `IDENTITY_SERVICE_MODE=oneshot python3 checkpoint_service.py --dry-run` exits 0

### 16.4 — HTTP Endpoint

**Owner**: Qwen
**Files**: `ai-stack/identity-kernel/identity_handlers.py` (new), `http_server.py` (route registration only)

Tasks:
1. Create `identity_handlers.py` following the existing extracted handler pattern:
   - `init(app_globals)` — receives shared state (journal_path, value_constitution)
   - `register_routes(app)` — registers:
     - `GET /identity/self` → returns `{summary, values, uptime_sessions, last_checkpoint}`
     - `POST /identity/event` → appends event (internal use, API-key protected)
   - No inline business logic in http_server.py
2. In `http_server.py`: add `import identity_handlers` and `identity_handlers.register_routes(http_app)`

Validation:
- `python3 -m py_compile ai-stack/identity-kernel/identity_handlers.py`
- `curl -s http://localhost:8003/identity/self | python3 -m json.tool`
- Response must include `summary`, `values`, `uptime_sessions` keys

### 16.5 — NixOS Module + Declarative Options

**Owner**: Qwen
**Files**: `nix/modules/services/identity-kernel.nix` (new), `nix/modules/core/options.nix` (extend)

Tasks:
1. Add to `options.nix` under `mySystem.aiStack`:
   ```nix
   identityKernel = {
     enable = mkEnableOption "Persistent AGI identity kernel";
     checkpointIntervalSeconds = mkOption { type = types.int; default = 300; };
     journalPath = mkOption { type = types.str; default = "/var/lib/ai-stack/identity"; };
     valueConstitutionFile = mkOption { type = types.path; };
   };
   ```
2. Create `nix/modules/services/identity-kernel.nix`:
   - `systemd.tmpfiles.rules` entry for journal dir
   - Inject `IDENTITY_JOURNAL_PATH`, `IDENTITY_CHECKPOINT_PATH`, `IDENTITY_CHECKPOINT_INTERVAL_SECONDS`,
     `IDENTITY_VALUE_CONSTITUTION` into `ai-hybrid-coordinator` service env
3. Import in `nix/modules/roles/ai-stack.nix`

Validation:
- `nix-instantiate --parse nix/modules/services/identity-kernel.nix` exits 0
- `nix-instantiate --parse nix/modules/core/options.nix` exits 0
- After nixos-rebuild: `systemctl show ai-hybrid-coordinator | grep IDENTITY_JOURNAL_PATH`

---

## Verification Matrix

Before marking any task done:
1. `python3 -m py_compile` for all touched Python files
2. `bash -n` for all touched shell scripts
3. `nix-instantiate --parse` for all touched Nix files
4. `GET /identity/self` returns valid JSON with required keys
5. `aq-qa 0` → 39+ passed, 0 failed (no regressions)
6. Journal file exists and is writable after service restart
7. Rollback: `sudo nixos-rebuild switch --rollback`

---

## Work Queue

### Task: IDK-001
- Phase: 16.1
- Owner agent: qwen
- Files: `ai-stack/identity-kernel/narrative_engine.py`
- Commands:
  - `cat ai-stack/mcp-servers/hybrid-coordinator/agentic_memory_journal.py | head -60`
  - `python3 -m py_compile ai-stack/identity-kernel/narrative_engine.py`
- Success criteria:
  - py_compile passes
  - `generate_summary()` returns dict with `capabilities`, `history_tail`, `uptime_sessions`
- Rollback: delete `ai-stack/identity-kernel/narrative_engine.py`
- Status: pending

### Task: IDK-002
- Phase: 16.2
- Owner agent: qwen
- Files: `ai-stack/identity-kernel/value_constitution.py`, `config/identity-values.yaml`
- Commands:
  - `python3 -m py_compile ai-stack/identity-kernel/value_constitution.py`
  - `python3 -c "from value_constitution import ValueConstitution; print(ValueConstitution('config/identity-values.yaml').get_active_weights())"`
- Success criteria:
  - All 5 values loaded with weights
  - Malformed YAML raises `ValueError` (not silent skip)
- Status: pending

### Task: IDK-003
- Phase: 16.3
- Owner agent: qwen
- Files: `ai-stack/identity-kernel/checkpoint_service.py`
- Commands:
  - `python3 -m py_compile ai-stack/identity-kernel/checkpoint_service.py`
- Status: pending

### Task: IDK-004
- Phase: 16.4
- Owner agent: qwen
- Files: `ai-stack/identity-kernel/identity_handlers.py`, `ai-stack/mcp-servers/hybrid-coordinator/http_server.py`
- Commands:
  - `python3 -m py_compile ai-stack/identity-kernel/identity_handlers.py`
  - `curl -s http://localhost:8003/identity/self | python3 -m json.tool`
- Status: pending

### Task: IDK-005
- Phase: 16.5
- Owner agent: qwen
- Files: `nix/modules/services/identity-kernel.nix`, `nix/modules/core/options.nix`
- Commands:
  - `nix-instantiate --parse nix/modules/services/identity-kernel.nix`
  - `nix-instantiate --parse nix/modules/core/options.nix`
- Status: pending

---

## Rollback

Each task is independently rollable:
- Python files: `git revert <commit>` or delete file
- Nix files: `sudo nixos-rebuild switch --rollback` (generation rollback)
- Journal data: JSONL is append-only, safe to truncate from `journalPath`
