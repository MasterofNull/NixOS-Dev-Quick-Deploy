# Phase 22 — Eval Recovery + Fleet Resilience

Status: `in_progress`
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

Status: **pending nixos-rebuild**

---

### 22.2 — Redis Rate-Limit Tracking per Provider (model_fleet_manager.py)

**Problem**: `_fleet_model_available()` in `delegation_handlers.py` checks per-model cooldown in Redis.
But when a model returns `Retry-After: 60` the cooldown is set from `_COOLDOWN_BY_CODE[429]=300s`.
We're not parsing the actual `Retry-After` header so cooldowns may be too long or too short.

**Fix**:
- Add `record_rate_limit_with_retry_after(model_id, retry_after_seconds)` to `model_fleet_manager.py`
- Wire it into `ai_coordinator_handlers.py` delegate error path: parse `Retry-After` header from remote response
- If `Retry-After` is present, use it instead of the fixed 300s cooldown

**Files**:
- `ai-stack/mcp-servers/hybrid-coordinator/model_fleet_manager.py`
- `ai-stack/mcp-servers/hybrid-coordinator/ai_coordinator_handlers.py`

Status: **planned**

---

### 22.3 — Eval Gap-Pack Run + Score Recovery

**Problem**: PRSI shows `eval_latest_below_threshold:50.0<60.0`. Root cause unknown — needs eval run.

**Diagnosis**:
```bash
python3 scripts/automation/run-gap-eval-pack.py --limit 20 2>&1 | tail -20
```

**Fix options** (after diagnosis):
- If gaps are NixOS-knowledge misses → import missing knowledge to AIDB
- If retrieval precision is low → adjust embedding similarity threshold
- If eval scoring is too strict → review scoring rubric

**Files**: `scripts/automation/run-gap-eval-pack.py`, AIDB knowledge import

Status: **planned** (depends on eval run result)

---

### 22.4 — Hint Diversity Source Expansion

**Finding**: hint-audit.jsonl shows 1 injection in 7d — accurate, not a bug.
Aider-wrapper usage dropped because direct Claude Code replaced it as the primary execution path.
The hybrid coordinator's `_inject_semantic_tooling()` writes to the hint-audit.jsonl via aider-wrapper;
since aider-wrapper isn't being invoked, injections are naturally low.

**Options**:
A. Accept: hint injection is an aider-wrapper concern; direct Claude Code doesn't use that path.
   Update aq-report section 14 to clarify the metric scope.
B. Extend: add hint injection tracking for direct coordinator `/query` calls (new JSONL or DB write).
   This captures the much larger volume of orchestrate/synthesize calls.

**Recommendation**: Option B — wire injection tracking into coordinator `/query` synthesis path.
This gives a truer picture of hint utilization across all execution paths.

**Files**:
- `ai-stack/mcp-servers/hybrid-coordinator/http_server.py` (synthesis hint tracking)
- `scripts/ai/aq-report` (section 14 scope clarification)

Status: **planned** (lower priority than 22.1-22.3)

---

## Verification Matrix

1. ⏳ `sudo nixos-rebuild switch --flake .#hyperd-ai-dev` (user terminal action)
2. ⏳ `systemctl show ai-hybrid-coordinator` → Phase 21 env vars active
3. ⏳ `aq-qa 0` → 40/0 after rebuild
4. ⏳ `aq-report` → delegate success rate improvement (24h window post-rebuild)
5. ⏳ Gap-eval-pack → eval score ≥60%
6. ⏳ `aq-report` → cache_hit improving (8 seeds done 2026-05-01)

---

## Work Queue

### Task: P22-001
- Phase: 22.1
- Owner: User (terminal) + Claude (validation)
- Action: `sudo nixos-rebuild switch --flake .#hyperd-ai-dev`
- Status: **pending** (requires user terminal action)

### Task: P22-002
- Phase: 22.2
- Owner: Claude
- Files: `model_fleet_manager.py`, `ai_coordinator_handlers.py`
- Status: **in_progress** (see implementation below)

### Task: P22-003
- Phase: 22.3
- Owner: Claude
- Files: `scripts/automation/run-gap-eval-pack.py`
- Status: **planned**

### Task: P22-004
- Phase: 22.4
- Owner: Claude
- Files: `http_server.py`, `scripts/ai/aq-report`
- Status: **planned** (lower priority)
