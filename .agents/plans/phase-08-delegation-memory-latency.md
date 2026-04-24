# Phase 8 — Delegation Reliability, Memory Integration, Inference Latency

Status: `active`
Created: 2026-04-24
Owner: Claude (orchestrator) / Qwen (implementation slices)
Predecessor: Phase 7 (Phases 0–7 complete, all gates green)

## Objective

Three high-impact improvements discovered via `aq-prime` + `aq-report` analysis:

1. **Delegation reliability** — `ai_coordinator_delegate` had 75% failure rate (6/8 errors) due to 60s timeout vs 90-120s qwen inference time. **Fixed in commit a36e715.**
2. **Memory integration** — Memory recall at 0% of route_search calls despite 296 recall calls total. Long-horizon task detection was only checking continuation queries. **Fixed in commit a36e715.**
3. **Inference latency reduction** — route_search P95=55503ms (7d). Root cause: bimodal distribution — p50=1ms (vector search) vs 970 outlier calls >10s that trigger LLM inference. Max observed: 418s. Not a qdrant issue; is hardware-bounded qwen inference.

## Scope Lock

In scope:
- Phase 8.1: Inference path timeout cap for `/query` LLM generation (hard cap + partial-result fallback)
- Phase 8.2: Memory recall active injection into `/query` warm path when `memory_recall_priority=true`
- Phase 8.3: Remote routing enablement — currently 0% remote, 100% local; switchboard remote profile validation
- Phase 8.4: `aider-task-audit.jsonl` task_tooling_quality telemetry recovery (still 0 in runtime)
- Phase 8.5: `ai_coordinator_delegate` smoke gate (post-fix validation + CI gate)

Out of scope:
- Model upgrades or quantization changes
- New NixOS service units (use existing service env vars)
- Changes to qdrant schema

## Evidence from aq-report (2026-04-24)

| Signal | Value | Target |
|--------|-------|--------|
| ai_coordinator_delegate success | 25% (2/8) | ≥90% |
| Memory recall share of route_search | 0.0% | ≥10% |
| route_search P95 (7d) | 55503ms | ≤15000ms |
| route_search >10s outliers | 970/32740 (3%) | ≤0.5% |
| Eval latest | 100% | ≥80% |
| Cache hit rate | 88% | ≥85% |
| Hint diversity entropy | healthy | healthy |
| Remote routing share | 0% | — (blocked by profile config) |
| task_tooling_quality.total | 0 | ≥1 |

## Phase 8.1 — Inference Path Timeout Cap

**Problem**: Some `/query` calls with `generate_response=true` or semantic autorun paths invoke llama-cpp inference. These inherit qwen's 90-120s latency, driving P95 to 55s and max to 418s.

**Fix strategy**:
- Add `AI_QUERY_LLM_TIMEOUT_S` env var (default 120s) to cap LLM generation in `/query`
- On timeout: return partial result with `{"truncated": true, "reason": "llm_timeout"}` rather than error
- Wire declaratively via `nix/modules/roles/ai-stack.nix` under hybrid-coordinator env

**Files**:
- `ai-stack/mcp-servers/hybrid-coordinator/http_server.py` (around line 6180 where generate_response is invoked)
- `nix/modules/roles/ai-stack.nix` (env var injection)

**Validation**:
- `python3 -m py_compile ai-stack/mcp-servers/hybrid-coordinator/http_server.py`
- `scripts/testing/validate-runtime-declarative.sh`
- Smoke: `curl -s -X POST localhost:8003/query -d '{"query":"test","generate_response":true,"timeout_s":5}'` → should return within 10s

## Phase 8.2 — Memory Recall Active Injection

**Problem**: `_should_prioritize_memory_recall()` now covers more cases (commit a36e715), but the `/query` handler needs to actively call `/memory/recall` when `memory_recall_priority=true` and inject results into the RAG context before returning.

**Current state**: `memory_recall_priority` flag is set and passed to `tooling_layer`, but no actual recall call is made in the hot path — agents must make a separate call.

**Fix strategy**:
- In `handle_query()`: when `memory_recall_priority=true`, attempt `/memory/recall` with a 2s budget timeout
- Inject recall results into the `context` dict as `prior_memory` before qdrant search
- Record `memory_recall_attempted=true` in audit_metadata regardless of outcome

**Files**:
- `ai-stack/mcp-servers/hybrid-coordinator/http_server.py` (handle_query, ~line 5957)

**Validation**:
- `aq-report` → `memory_recall.share_of_route_search` should increase from 0%
- Smoke: `curl -X POST localhost:8003/query -d '{"query":"current work remaining tasks"}'` → response should include `memory_recall_attempted: true`

## Phase 8.3 — Remote Profile Validation + Switchboard Health

**Problem**: Remote routing is 0% over 7d. The switchboard has remote profiles configured but they may have stale/invalid status. No CI gate enforces remote profile availability.

**Fix strategy**:
- Audit `_switchboard_ai_coordinator_state()` return: confirm remote profiles are reachable
- Add `check-remote-profiles.sh` smoke gate that validates at least 1 remote alias is configured
- Wire as optional (warn-only) gate in `scripts/automation/run-advanced-parity-suite.sh`

**Files**:
- `scripts/testing/check-remote-profiles.sh` (new)
- `scripts/automation/run-advanced-parity-suite.sh` (add warn-only step)

**Validation**:
- `bash -n scripts/testing/check-remote-profiles.sh`
- Manual: `curl localhost:8003/switchboard/state` → remote_aliases present

## Phase 8.4 — Aider Task Audit Telemetry Recovery

**Problem**: `task_tooling_quality.total` = 0 in aq-report. The `aider-task-audit.jsonl` at `/var/log/nixos-ai-stack/aider-task-audit.jsonl` should be emitting after aider-wrapper fix from 2026-03-04. Requires verification that the service is actually writing to the correct path.

**Fix strategy**:
- Check `TASK_AUDIT_LOG_PATH` is set in aider-wrapper service env
- Verify write permissions on `/var/log/nixos-ai-stack/`
- If path or perms wrong, fix declaratively in Nix module

**Files**:
- `nix/modules/roles/ai-stack.nix` (aider-wrapper env section)

**Validation**:
- `ls -la /var/log/nixos-ai-stack/aider-task-audit.jsonl` → exists and non-empty after a task run
- `aq-report` → `task_tooling_quality.total` ≥ 1

## Phase 8.5 — Delegate Smoke Gate

**Problem**: No CI gate validates `ai_coordinator_delegate` health post-fix. The 60→180s fix (commit a36e715) needs a regression guard.

**Fix strategy**:
- Add `scripts/testing/check-ai-coordinator-delegate-smoke.sh`
- Test: POST `/control/ai-coordinator/delegate` with a simple task and `timeout_s=10` → should return `runtime_not_found` or `local_agent_timeout` (not HTTP 500/4xx)
- Wire as step in `scripts/automation/run-advanced-parity-suite.sh`

**Files**:
- `scripts/testing/check-ai-coordinator-delegate-smoke.sh` (new)
- `scripts/automation/run-advanced-parity-suite.sh` (add step)

**Validation**:
- `bash -n scripts/testing/check-ai-coordinator-delegate-smoke.sh`
- `scripts/testing/check-ai-coordinator-delegate-smoke.sh` → PASS

## Execution Order

```
8.5 → 8.4 → 8.2 → 8.1 → 8.3
```
Rationale: smoke gate first (validates the fix already deployed), then observability recovery, then active memory injection, then latency cap, then remote profile (lowest urgency).

## Rollback

Each slice is independently rollbackable via `git revert`. No NixOS rebuild required for http_server.py changes (service restarts via `systemctl restart hybrid-coordinator`). Nix module changes require `sudo nixos-rebuild switch`.

## Success Criteria (Program-Level)

- [ ] `ai_coordinator_delegate` success rate ≥ 90% in next 7d window
- [ ] Memory recall share > 5% of route_search calls
- [ ] route_search >10s outlier rate ≤ 1% (from 3%)
- [ ] `task_tooling_quality.total` ≥ 1
- [ ] All new gate scripts pass in `run-advanced-parity-suite.sh`
- [ ] Phase 7 program gate remains green throughout
