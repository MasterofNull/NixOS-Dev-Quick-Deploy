# Phase 9 — Intent Contract Completeness + OpenRouter Delegation Hardening

Status: `active`
Created: 2026-04-24
Owner: Claude (orchestrator) / Qwen (implementation slices)
Predecessor: Phase 8 (all slices committed; nixos-rebuild deployment pending)

## Objective

Two high-impact gaps identified from aq-report live signals (2026-04-24):

1. **Intent contract coverage** — 88.2% over 17 runs (target: 100%). The running
   service auto-injects a partial contract (user_intent, query, objective) but omits
   `definition_of_done`, `depth_expectation`, `spirit_constraints`,
   `no_early_exit_without`. 2 historic sessions have no contract at all.
2. **OpenRouter delegation empty_content failures** — 2 failed delegate calls
   (`empty_content=2`). Root cause: poorly-scoped prompts sent to OpenRouter via
   the delegate path produce empty completions; no retry or fallback exists.

## Evidence from aq-report (2026-04-24)

| Signal | Value | Target |
|--------|-------|--------|
| Workflow intent-contract coverage | 88.2% (17 runs) | 100% |
| Sessions with no intent_contract | 2 | 0 |
| OpenRouter empty_content failures | 2 | 0 |
| ai_coordinator_delegate success (last hour) | 0% | ≥50% post-rebuild |
| aq-qa checks | 39/39 pass | 39/39 |
| task_tooling_quality.total (7d) | 2 | ≥1 ✅ |

## Scope Lock

In scope:
- Phase 9.1: Intent contract auto-injection completeness (fill all required fields)
- Phase 9.2: OpenRouter empty_content retry + prompt hardening in delegate path
- Phase 9.3: Post-rebuild delegate success rate smoke gate (`aq-qa` 0.8.x)
- Phase 9.4: Commit + validate parity suite with new front-door gate wired

Out of scope:
- Model changes or quantization
- New service units (use existing env vars)
- Changes to qdrant schema or AIDB ingest

## Phase 9.1 — Intent Contract Auto-Injection Completeness

**Problem**: `/workflow/run/start` auto-injects `intent_contract` with only 3 fields
when none is provided. Missing: `definition_of_done`, `depth_expectation`,
`spirit_constraints`, `no_early_exit_without`.

**Fix strategy**:
- In `handle_workflow_run_start()` (or equivalent), extend the auto-injection block
  to populate all 5 required fields with sensible defaults:
  - `definition_of_done`: `"Task complete when objective is achieved and validated"`
  - `depth_expectation`: `"minimum"`
  - `spirit_constraints`: `[]`
  - `no_early_exit_without`: `[]`
- Wire declaratively via `nix/modules/roles/ai-stack.nix` env var
  `AI_WORKFLOW_DEFAULT_DEPTH` (default: `minimum`)

**Files**:
- `ai-stack/mcp-servers/hybrid-coordinator/http_server.py`

**Validation**:
- `python3 -m py_compile ai-stack/mcp-servers/hybrid-coordinator/http_server.py`
- Smoke: `curl -X POST localhost:8003/workflow/run/start -d '{"query":"test"}'`
  → response `intent_contract` must include all 5 fields

## Phase 9.2 — OpenRouter Empty-Content Retry

**Problem**: Delegate calls to OpenRouter return `empty_content=true` on 2 recorded
calls. The error is swallowed without retry or prompt simplification fallback.

**Fix strategy**:
- In the OpenRouter completion path inside `http_server.py`, detect `empty_content`
  responses (empty string or whitespace-only content with HTTP 200)
- On first empty: retry once with a simplified prompt (strip tool-call schemas,
  reduce to plain text instruction + output-format hint)
- On second empty: return `{"error": "openrouter_empty_content", "retried": true}`
  and emit a telemetry event for aq-report tracking
- Add `openrouter_empty_content_retries` counter to tool audit metadata

**Files**:
- `ai-stack/mcp-servers/hybrid-coordinator/http_server.py`

**Validation**:
- `python3 -m py_compile ai-stack/mcp-servers/hybrid-coordinator/http_server.py`
- aq-report `recommendations` should no longer flag empty_content after next rebuild

## Phase 9.3 — Post-Rebuild Delegate Success Rate Gate

**Problem**: No `aq-qa` check validates `ai_coordinator_delegate` live success rate
after nixos-rebuild deploys Phase 8 fixes. Without a gate, regression is silent.

**Fix strategy**:
- Add `aq-qa` check `0.8.1: delegate 1h success rate ≥ 50%` that:
  - Queries PostgreSQL `tool_audit_log` for `tool_name = 'ai_coordinator_delegate'`
    events in the last 1h
  - Skips (SKIP) if fewer than 3 calls in window (insufficient sample)
  - FAILs only if ≥ 3 calls and success rate < 50%
- Wire as non-blocking (SKIP-friendly) so it doesn't break fresh deploys

**Files**:
- `scripts/ai/aq-qa`

**Validation**:
- `bash -n scripts/ai/aq-qa`
- `aq-qa 0` → new check visible and SKIPs on fresh deploy (no data yet)

## Phase 9.4 — Front-Door Gate Commit + Parity Suite Wire

**Status**: DONE — `test-local-orchestrator-frontdoor.sh` committed in `601fbd8`
and wired into `run-advanced-parity-suite.sh`.

**Validation**:
- `bash scripts/testing/test-local-orchestrator-frontdoor.sh` → PASS ✅

## Execution Order

```
9.4 (done) → 9.3 → 9.1 → 9.2
```

Rationale: gate first (aq-qa health observable), then contract completeness (broadest
coverage impact), then OpenRouter retry (lower frequency but higher agent trust impact).

## Rollback

Each slice is independently rollbackable via `git revert`. http_server.py changes
require `sudo nixos-rebuild switch` after revert. aq-qa changes take effect immediately.

## Success Criteria (Program-Level)

- [ ] Intent contract coverage = 100% over next 7d run window
- [ ] OpenRouter empty_content failures = 0 in next 7d window
- [ ] `aq-qa 0` shows `0.8.1` check (SKIP or PASS, never FAIL unexpectedly)
- [ ] `run-advanced-parity-suite.sh` includes front-door gate and passes
- [ ] Phase 8 nixos-rebuild deployed and `ai_coordinator_delegate` 1h success ≥ 50%
