# Phase 22 — Eval Recovery + Fleet Resilience

Status: `in_progress` (P22-001 through P22-007 done; P22-008 committed pending rebuild; P22-004 in_progress)
Created: 2026-05-01
Owner: Claude (orchestrator/implementer)
Predecessor: Phase 21 (Operational Hardening — all tasks committed, pending nixos-rebuild)

---

## Objective

Three-part improvement cycle targeting the remaining gaps after Phase 21:

1. **Post-rebuild validation** — confirm Phase 21 code changes are live in the running service
2. **Eval score recovery** — aq-qa 0.8.1 (delegate success rate) and PRSI eval score (50% < 60% threshold)
3. **Fleet resilience** — Redis-backed per-provider rate-limit tracking + Retry-After header respect

Telemetry baseline (2026-05-01):
- aq-qa: 39 passed / 1 failed (0.8.1: delegate success rate 0%, 3/3 calls failed — remote-profile path)
- PRSI degradation: `eval_latest_below_threshold:50.0<60.0`, `cache_hit_below_threshold:0.0<50.0`
- hint-audit.jsonl: 1 injection in 7d (correct — aider-wrapper usage dropped; direct Claude Code replaced it)
- PRSI queue: `tighten_openrouter_delegation_contract` rejected (stale — remote disabled)

---

## Scope Lock

In scope:
- Post-rebuild validation of Phase 21 env var changes
- Redis rate-limit tracking per provider/model (`model_fleet_manager.py`)
- Retry-After header parsing in `delegation_handlers.py`
- Eval gap-pack run to understand 50% eval score
- Cache prewarm (8 queries seeded — 2026-05-01)

Out of scope:
- aider-wrapper hint injection frequency (legitimate low usage — direct Claude Code replaced it)
- Training or fine-tuning models
- New AGI phases
- AIDB schema changes

---

## Sub-phases

### 22.1 — Post-Rebuild Validation (OP-003)

**Requires**: `sudo nixos-rebuild switch --flake .#hyperd-ai-dev`

After rebuild, confirm:
```bash
# Phase 21.1 retry params active
systemctl show ai-hybrid-coordinator --property=Environment | grep AI_DELEGATE_LOCAL_SLOT

# Phase 21.2 remote URL cleared
systemctl show ai-hybrid-coordinator --property=Environment | grep SWITCHBOARD_REMOTE_URL

# OP-007 aliases corrected
systemctl show ai-hybrid-coordinator --property=Environment | grep SWITCHBOARD_REMOTE_ALIAS

# Phase 21 combined: health gate
aq-qa 0  # target: 40/0
```

Expected post-rebuild results:
- `AI_DELEGATE_LOCAL_SLOT_BUSY_MAX_RETRIES=4` ✓
- `SWITCHBOARD_REMOTE_URL=` (empty) ✓
- `SWITCHBOARD_REMOTE_ALIAS_GEMINI=google/gemini-2.0-flash-exp:free` ✓
- `SWITCHBOARD_REMOTE_ALIAS_FREE=meta-llama/llama-3.3-70b-instruct:free` ✓
- aq-qa 0.8.1: delegate success rate ≥50% (remote profiles now skipped → local handles all calls)

Status: **done** (2026-05-01 — rebuild confirmed; env vars live; aq-qa 39/0)

Confirmed results:
- `AI_DELEGATE_LOCAL_SLOT_BUSY_MAX_RETRIES=4` ✓
- `SWITCHBOARD_REMOTE_URL=` (empty) ✓
- `SWITCHBOARD_REMOTE_ALIAS_GEMINI=google/gemini-2.0-flash-exp:free` ✓
- `SWITCHBOARD_REMOTE_ALIAS_FREE=meta-llama/llama-3.3-70b-instruct:free` ✓
- aq-qa 39 passed / 0 failed / 1 skipped (0.8.1 insufficient sample — correct)

---

### 22.2 — Redis Rate-Limit Tracking per Provider (model_fleet_manager.py)

Status: **done** (2026-05-01 — implemented; `record_error_with_retry_after()` in model_fleet_manager.py;
wired into ai_coordinator_handlers.py delegate error path at lines ~1433 and ~1873)

---

### 22.3 — Eval Gap-Pack Run + Score Recovery

Status: **done** (2026-05-01 — aq-report §4: runs=2, latest=100.0%, mean=100.0%, stable)

---

### 22.4 — Hint Diversity Source Expansion

**Finding**: hint-audit.jsonl shows 1 injection in 7d — accurate, not a bug.
Aider-wrapper usage dropped because direct Claude Code replaced it as the primary execution path.
The hybrid coordinator's `_inject_semantic_tooling()` writes to the hint-audit.jsonl via aider-wrapper;
since aider-wrapper isn't being invoked, injections are naturally low.

**Recommendation**: Option B — wire injection tracking into coordinator `/query` synthesis path.
This gives a truer picture of hint utilization across all execution paths.

**Files**:
- `ai-stack/mcp-servers/hybrid-coordinator/http_server.py` (synthesis hint tracking)
- `scripts/ai/aq-report` (section 14 scope clarification)

Status: **in_progress** (2026-05-02)

---

## Verification Matrix

1. ✅ `sudo nixos-rebuild switch --flake .#hyperd-ai-dev` — done
2. ✅ `systemctl show ai-hybrid-coordinator` → Phase 21 env vars active — confirmed
3. ✅ `aq-qa 0` → 39/0 (0 failed, 1 skipped — correct)
4. ✅ `aq-report` → eval=100%, cache warming (28% hit rate, low sample)
5. ✅ Gap-eval-pack → eval score 100% (P22-006)
6. ✅ `aq-report` → cache_hit at 28% (25 samples, warming)
7. ⏳ P22-004 hint tracking in /query — in_progress
8. ⏳ nixos-rebuild for cache_prompt fix (commit 84b7231d)

---

## Work Queue

### Task: P22-001 ✅ DONE (2026-05-01)
- Phase: 22.1
- Owner: User (terminal) + Claude (validation)
- Action: `sudo nixos-rebuild switch --flake .#hyperd-ai-dev`
- Status: **done** — rebuild confirmed; env vars live; aq-qa 39/0

### Task: P22-002 ✅ DONE (2026-05-01)
- Phase: 22.2
- Owner: Claude
- Files: `model_fleet_manager.py`, `ai_coordinator_handlers.py`
- Status: **done** — `record_error_with_retry_after()` implemented and wired

### Task: P22-003 ✅ DONE (2026-05-01)
- Phase: 22.3
- Owner: Claude
- Files: `scripts/automation/run-gap-eval-pack.py`
- Status: **done** — eval score 100%, aq-report §4 confirmed

### Task: P22-004
- Phase: 22.4
- Owner: Claude
- Files: `http_server.py`, `scripts/ai/aq-report`
- Status: **in_progress** (2026-05-02)

### Task: P22-008 ✅ COMMITTED (2026-05-02, pending nixos-rebuild)
- Phase: 22.8 — Cold prefill elimination via KV-cache reuse
- Owner: Claude
- File: `nix/modules/services/switchboard.nix`
- Commit: `84b7231d`
- Fix: inject `cache_prompt=true` for all local `chat/completions` payloads;
  eliminates ~11.8 s cold prefill on the fixed profile-card prefix after first request
- Status: **committed** — activate with `sudo nixos-rebuild switch --flake .#hyperd-ai-dev`

### Task: P22-005 ✅ DONE (2026-05-01)
- Phase: 22.5 — Architectural: eliminate remote model hardcoding
- Owner: Claude
- Root cause: `agent_pool_manager.py` contained hardcoded model IDs
  (meta-llama, deepseek-r1, gemini-flash-exp, dolphin-mistral, gpt-3.5-turbo,
  claude-haiku). This violated local-first design — the pool should reflect
  operator configuration, not Python source code.
- Fix (commit c9e509d9): `_initialize_default_agents()` now reads
  `SWITCHBOARD_REMOTE_ALIAS_*` env vars set by Nix at build time.
  When all vars are empty (local-only deployment) → pool is empty → local llama.cpp
  handles all inference. Remote models enter the pool only when the operator
  configures aliases in `remoteModelAliases.*` Nix options.
- Pool deduplicates by model_id; infers provider + tier from slug.
- Status: **done**

### Task: P22-006
- Phase: 22.6 — Eval score DB refresh
- Owner: Claude
- Finding: PRSI showed `eval_latest_below_threshold:50.0<60.0` — reading stale DB
  records from early March 2026 (gap_pack_v1: 1/4=25%). Current eval runs show
  100% (3/3 and 4/4). Gap-eval-pack now writes new 100% score to scores.sqlite.
- Status: **done** (score updated 2026-05-01)

### Task: P22-007
- Phase: 22.7 — PRSI stale item cleanup
- Owner: Claude
- Action: rejected `tighten_openrouter_delegation_contract` PRSI item (id: 57bd1e2235b54705)
  — stale since remote routing disabled (commit 23043d71)
- Cache prewarm: 8 seeds sent to hybrid coordinator (2026-05-01)
- Status: **done**
