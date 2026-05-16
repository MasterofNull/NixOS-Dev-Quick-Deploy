# System Assessment & Fix PRD
**Date**: 2026-05-15
**Assessment by**: Claude Sonnet 4.6 (Orchestrator) + Gemini (Architecture) + Codex (Code Audit) + Qwen (Health Scan)
**Status**: PHASE A+B COMPLETE — pending nixos-rebuild + verification

---

## Agent Assessment Summary

### Gemini Findings (Architecture Review)
- P0: hints tool 30.6% OK → root cause: wrong audit log path (FIXED)
- P0: audit-post.sh Python heredoc shell injection (FIXED)
- P1: Postgres query-gaps table empty (interaction_tracker CONTINUOUS_LEARNING path broken)
- P1: hints_feedback 0% OK (permission or payload issue)
- P1: Zero remote fallback coverage (no test exercising remote route)
- P2: Continuation downshift inactive (TokenBudgetContext.detect_phase logic)
- P2: Suspicious 98.9% cache hit rate (cache key may be too coarse)
- P2: Memory recall miss rate 0% (threshold may be too low, returning noise)

### Codex Findings (Code Audit)
- P1-SEC: X-Forwarded-For spoofable loopback bypass (FIXED — removed header trust)
- P1-BUG: asyncio.coroutine() removed in Python 3.12 → events never reach CL (FIXED)
- P1-BUG: agent-events CL payload schema mismatch (stripped payload lacks fields CL expects)
- P1-SEC: audit-post.sh heredoc injection (FIXED — rewritten with sys.argv)
- P2: GET /api/memory/facts missing (FIXED — added endpoint)
- P2: latency_ms ValueError on non-integer input → 500 response
- P2: Unknown event_type silently coerced to task_completed (pollutes audit metrics)

### Qwen (Local) — timed out (expected — 300s limit for full health scan)

---

## Executive Summary

Full-stack assessment of NixOS-Dev-Quick-Deploy AI harness revealed:
- **1 P0 Bug** ✅ — hints engine reads wrong audit log path → 30–70% hints failure rate
- **1 P0 Bug** ✅ — coordinator cannot write to audit log → Phase 56 agent-events silently failing
- **1 P1-SEC** ✅ — X-Forwarded-For loopback bypass spoofable by any remote client
- **1 P1-BUG** ✅ — asyncio.coroutine() removed in Python 3.12 → events never reach ContinuousLearning
- **1 P1-SEC** ✅ — audit-post.sh Python heredoc shell injection on summary/task fields
- **1 P2-FEAT** ✅ — GET /api/memory/facts missing (aq-session-start constraints hydration broken)
- **1 P1 Gap** ✅ — 14 uncommitted Phase 56 files committed (sub_type, session saving)
- **1 P1 Gap** ✅ — `.agents/sessions/` gitignored
- **1 P1 Bug** ✓ — `qa_check` 0% success → historical; system now 60/60 healthy
- **2 P1 Issues** — route_search 5.4% failure + hints_feedback 0% OK (P2 phase investigation)
- **1 P1 Gap** — aq-qa 0.8.1 always skipping (pending rebuild + delegation seed)
- **1 P1 BUG** — agent-events → CL payload schema mismatch (stripped payload lacks CL fields)
- **1 P2 Gap** — Postgres query-gaps table empty (interaction_tracker broken)
- **1 P2 Gap** — Memory recall miss rate 0% suspicious
- **1 P2 Gap** — Continuation downshift 0/10
- **1 P2 Bug** — latency_ms ValueError on invalid input → HTTP 500
- **1 P2 Bug** — Unknown event_type silently coerced → audit pollution

---

## Detailed Findings

### P0-001 — hints_engine wrong audit log path
**File**: `ai-stack/mcp-servers/hybrid-coordinator/knowledge/hints_engine.py:856`
**Error**: `Permission denied: '/var/log/nixos-ai-stack/tool-audit.jsonl'`
**Root cause**:
- `hints_engine.py` defaults to `/var/log/nixos-ai-stack/tool-audit.jsonl` when `TOOL_AUDIT_LOG_PATH` env is not set
- The coordinator service does NOT have `TOOL_AUDIT_LOG_PATH` in its environment (it's only set for the audit-sidecar service at mcp-servers.nix:1885)
- The `/var/log/nixos-ai-stack/` directory is `drwxr-x---` owned by `hyperd:users` — coordinator (`ai-hybrid:ai-stack`) cannot enter the directory
- **Impact**: 30–70% of hints requests fail with `hints_engine_unavailable` → aq-report shows 58.5% hints OK, last-hour 30.6%

**Fix required**:
1. Add `TOOL_AUDIT_LOG_PATH=/var/log/ai-audit-sidecar/tool-audit.jsonl` to coordinator service environment in `nix/modules/services/mcp-servers.nix` (after line 1062)
2. Fix `hints_engine.py:856` default fallback to match sidecar path
3. nixos-rebuild switch to deploy

### P0-002 — Coordinator cannot write agent-events to audit log
**File**: `ai-stack/mcp-servers/hybrid-coordinator/http_server.py:1857`
**Error**: Silent write failure — no traceable error since Phase 56 catches exceptions
**Root cause**:
- Phase 56 `POST /api/agent-events` writes to `TOOL_AUDIT_LOG_PATH` = `/var/log/ai-audit-sidecar/tool-audit.jsonl`
- File permissions: `-rw-r-----` (640) owned by `ai-audit:ai-stack`
- Coordinator (`ai-hybrid`, group `ai-stack`) has group read but NOT group write
- tmpfiles rule at mcp-servers.nix:657 sets 0640 — intentionally read-only for group
- **Impact**: All delegation events posted by `delegate-to-*` scripts fail silently; aq-qa 0.8.1 skips forever; institutional memory loop broken

**Fix required**:
1. Change tmpfiles rule from `0640` to `0660` (add group write for ai-stack members)
2. OR use a separate coordinator-writable path for agent-events (e.g., `${dataDir}/agent-events.jsonl`) — preferred for separation of concerns
3. nixos-rebuild switch

### P1-001 — 14 uncommitted Phase 56 files
**Files**: `scripts/ai/lib/audit-write.sh`, `audit-post.sh`, `delegate-to-*` (×4), `aq-commit-facts`, `continuous_learning.py`, `http_server.py`, `agent_registry.py`, `AGENTS.md`, `CLAUDE.md`, `.agents/plans/PROJECT-AI-HARNESS-EVOLUTION-PRD.md`
**Root cause**: API signature was extended (added `sub_type` param to `audit_event_start`/`audit_event_end`; added `audit_save_session` function) but changes not committed
**Impact**: Working tree is dirty; git log is misleading; any rollback would lose these changes

**Fix required**: Review diffs, commit all Phase 56.9 changes with proper message

### P1-002 — .agents/sessions/ untracked + not gitignored
**File**: `.gitignore`
**Root cause**: Phase 56 `audit_save_session` creates session JSON files at `.agents/sessions/`, but neither the directory nor its files are gitignored
**Impact**: Session transcripts will bloat the repo on next `git add -A`

**Fix required**: Add `.agents/sessions/` to `.gitignore`

### P1-003 — qa_check tool 0% success (7 errors)
**Endpoint**: `POST /qa/check`
**Symptom**: aq-report shows 7 qa_check calls, 0 successes, 7 errors
**Root cause**: Unknown — endpoint exists in route table. Likely: postgres unavailable OR eval runner misconfigured
**Impact**: QA auto-checks fail silently; quality gate data missing from reports

**Fix required**: Debug `POST /qa/check` — test directly, check error logs

### P1-004 — route_search 5.4% failure rate
**Tool**: `route_search` — 735 errors out of 13,638 calls
**Root cause**: Likely intermittent AIDB/llama.cpp connection timeouts during high-load periods
**Impact**: ~1 in 20 queries fails to route correctly

**Fix required**:
1. Check error pattern in traces
2. Add retry logic to `_execute_query_search` for AIDB connection errors
3. Improve circuit-breaker backoff

### P1-005 — hints_feedback 0% OK (1 error)
**Tool**: `hints_feedback` — 1 call, 0 successes
**Root cause**: Low sample but needs investigation
**Impact**: Feedback loop for hints improvement broken

### P1-006 — aq-qa 0.8.1 never passing
**Check**: Delegation 24h success rate
**Root cause**: The audit trail (`POST /api/agent-events`) writes fail silently (P0-002), so no delegation events accumulate in tool-audit.jsonl for `/stats/delegate` to count
**Impact**: Ongoing blind spot in delegation health monitoring

**Fix required**: Fix P0-002 first, then run any delegation to seed the check

### P2-001 — Postgres query-gaps table empty
**Symptom**: aq-report shows "No gaps data (Postgres unavailable or table empty)"
**Root cause**: Either Postgres connection is failing at gaps query level, or the gaps-collection query isn't being committed
**Impact**: PRSI gap identification not working; aq-report §7 always empty

### P2-002 — Memory recall miss rate 0% (suspicious)
**Symptom**: aq-report shows memory recall miss rate 0.0% across 813 recall calls
**Root cause**: If all 813 recall calls truly succeed, this is healthy. But if the miss counter is not being incremented on cache misses, the metric is wrong
**Impact**: False confidence in recall quality

### P2-003 — Continuation downshift 0/10
**Symptom**: 0/10 coverage for continuation downshift
**Root cause**: Either no sessions are crossing the downshift threshold, or the downshift probe is not running correctly
**Impact**: Context-window overflow protection not being exercised

---

## Fix Plan (Phased)

### Phase A — P0 Fixes (THIS SESSION, ~2h)

**A.1 Fix hints_engine audit log path** (code + nix)
- Edit `hints_engine.py:856`: change default to `/var/log/ai-audit-sidecar/tool-audit.jsonl`
- Edit `mcp-servers.nix` coordinator env: add `TOOL_AUDIT_LOG_PATH=/var/log/ai-audit-sidecar/tool-audit.jsonl`
- Commit + nixos-rebuild switch

**A.2 Fix audit log write permissions** (nix)
- Edit `mcp-servers.nix:657`: change tmpfiles rule from `0640` to `0660` for tool-audit.jsonl
- Add `/var/log/ai-audit-sidecar` to coordinator `ReadWritePaths`
- Commit + nixos-rebuild switch

**A.3 Commit uncommitted Phase 56 changes** (git)
- Review diffs, stage all 14 files
- Commit with "feat(phase-56.9): sub_type taxonomy, session saving, audit API extension"

### Phase B — P1 Fixes (THIS SESSION, ~1h)

**B.1 .gitignore sessions dir**
- Add `.agents/sessions/` to `.gitignore`

**B.2 Debug qa_check 0% failure**
- Test `POST /qa/check` directly, check logs
- Fix root cause

**B.3 Verify end-to-end audit trail**
- Run `delegate-to-local --mode direct --prompt "ping" --wait`
- Run `aq-qa 0.8.1` — expect PASS
- Run `aq-qa 56` — expect 16/16

### Phase C — P2 Fixes (Next session)

**C.1 Postgres gaps table investigation**
**C.2 Memory recall miss counter validation**
**C.3 Continuation downshift probe check**
**C.4 route_search retry/circuit-breaker hardening**

---

## Fix Status (Phase A+B+C.0)

| Fix | Commit | Status |
|-----|--------|--------|
| P0-001 hints wrong audit path | 3717dcdd | ✅ |
| P0-002 audit log 0640 → 0660 | mcp-servers.nix | ✅ |
| P0-002 serviceWritablePaths + env | mcp-servers.nix | ✅ |
| P1-SEC X-Forwarded-For bypass | http_server.py | ✅ |
| P1-BUG asyncio.coroutine Py3.12 | http_server.py | ✅ |
| P1-SEC audit-post.sh heredoc injection | ff051abb | ✅ |
| P2-FEAT GET /api/memory/facts | http_server.py | ✅ |
| P1 CL payload schema mismatch | 48de031d | ✅ |
| P2 memory/facts top_k kwarg | 48de031d | ✅ |
| tmpfiles mkAfter z-rule (mutableLogDir) | 48de031d | ✅ pending rebuild |
| P1-001 Phase 56 uncommitted files | 7e5beec7 | ✅ |
| P1-002 .agents/sessions/ gitignore | committed | ✅ |

## Success Criteria

- [x] POST /api/agent-events writes to tool-audit.jsonl successfully
- [x] aq-qa 0.8.1 → PASS (seeded + fixed)
- [x] aq-qa 0: 61/61 passed
- [x] aq-qa 56: 16/16
- [x] All Phase 56 changes committed
- [x] .agents/sessions/ gitignored
- [ ] hints OK rate ≥ 90% — pending rebuild (lib.mkAfter tmpfiles fix)
- [ ] GET /api/memory/facts — returns facts (fixed, pending restart)
- [ ] CL receives properly structured events — fixed, pending restart

## Phase C Remaining (P2)

- **C.1** Postgres query-gaps: `interaction_tracker.sync_query_gaps_to_jsonl` writes to
  `/var/log/nixos-ai-stack/query-gaps.jsonl` — currently 488 bytes so data IS there;
  aq-report "No gaps data" means Postgres SELECT returns empty, not file-empty.
  Root cause: `query_gaps` table may never be populated if AIDB confidence always > threshold.
- **C.2** Memory recall miss rate 0% — counter likely not incremented; metrics cosmetic issue
- **C.3** Continuation downshift 0/10 — no real continuation queries in test window; P2 behavioral gap
- **C.4** route_search 5.4% failure — add retry logic to _execute_query_search

---

*Agent findings will be merged here when Gemini/Codex/Qwen outputs arrive.*
