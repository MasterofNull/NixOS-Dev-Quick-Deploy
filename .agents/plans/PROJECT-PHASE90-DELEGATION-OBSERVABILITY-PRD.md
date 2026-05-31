# Phase 90 — Delegation Observability & Metric Hygiene
**Status**: IN PROGRESS | **Owner**: claude-sonnet-4-6 | **Started**: 2026-05-31

---

## 1. Problem Statement

`aq-report` shows `ai_coordinator_delegate` success rate at 51.6% — but the live 24h rate is
82.4%. The gap is caused by:

1. **18 stale `running` entries** (orphaned May 30): tasks dispatched but never posted a
   completion event. These count as implicit failures in the long-window aggregate.
2. **Unclassified `http_status_500` errors**: all failures land in `error_message="http_status_500"`.
   No structured `failure_reason` field — impossible to distinguish timeout vs backend crash
   vs empty response. Blocks targeted remediation.
3. **Single-window metric**: aq-report reports one aggregate rate over 7d, hiding the fact
   that current health (82.4%) is much better than the historical drag.

## 2. Goals

- Stale `running` entries are expired/reclassified automatically (no manual cleanup needed).
- Every delegate failure carries a `failure_reason` enum value in the audit log.
- aq-report shows 24h and 7d rates side-by-side so operators can distinguish current health
  from historical drag.

## 3. Out of Scope

- Changing the dispatch logic or retry strategy (separate concern).
- `recall_agent_memory` — only 1 error in recent 5k entries; not a current issue.
- Any changes to the llama.cpp backend or MLFQ scheduler.

## 4. Acceptance Criteria

- [N/A] **90.1 (TTL expiry)**: Stale `running` entries already excluded from rate calculation by
      `_TERMINAL_OUTCOMES` check in `/stats/delegate`. The 51.6% vs 82.4% gap is real historical
      errors, not orphaned entries — no TTL sweep needed. Revised scope: `failure_reason` on new
      entries; existing stale entries unaffected (correct behaviour).
- [x] **90.2**: `failure_reason` field added to audit entries via `_classify_failure_reason()`.
      Values: `backend_500`, `empty_response`, `timeout`, `context_overflow`, `unknown`.
      `/stats/delegate` includes `failure_breakdown` map; falls back to classifier for legacy entries.
- [x] **90.3**: aq-report Section 8 (Recent Health Snapshot) shows `24h: X%  |  7d: Y%` for
      `ai_coordinator_delegate`. Computed via `_compute_delegate_rate()` from audit log; no HTTP call
      needed. Both `format_md` and `format_text` updated.
- [ ] **tier0**: 17/17 pass. Coordinator restart required for 90.2 changes.

## 5. Slices

### 90.1 — Stale Running Entry TTL Expiry
- **File**: `http_server_impl.py` — add `_expire_stale_running_entries()` function
- **Trigger**: called at coordinator startup + every hour via the existing maintenance loop
- **TTL**: 2 hours (configurable via `DELEGATE_RUNNING_ENTRY_TTL_H` env var)
- **Effect**: entries older than TTL in `running` state are rewritten as `timed_out`

### 90.2 — Structured failure_reason
- **File**: `http_server_impl.py` — extract `failure_reason` from HTTP status + error body
- **Schema**: `failure_reason: "backend_500" | "empty_response" | "timeout" | "context_overflow" | "unknown"`
- **Surface**: audit log + `/stats/delegate` response `failure_breakdown` field

### 90.3 — aq-report 24h/7d split
- **File**: `scripts/ai/aq-report` — Section 5 delegate stats
- **Change**: call `/stats/delegate?window=86400` (24h) alongside existing 7d call;
  display as `24h: X%  7d: Y%`

## 6. Rollback

All changes are additive (new fields, new TTL sweep). Rollback = revert the 3 file edits.
