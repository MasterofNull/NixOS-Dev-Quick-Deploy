# Evidence — trend_database naive/aware datetime crash — 2026-10-15

## Symptom
`ai-autonomous-improvement.service` failed every hourly run (>= 2026-10-15T10:32 local):
`TypeError: can't compare offset-naive and offset-aware datetimes` at `collect_all_metrics` sort -> `RuntimeError: metric-sync-failed`. Also failed tier0 QA 0.1.2 (failed AI unit) for every commit.

## Root cause
SQLite collectors (`collect_routing_metrics` x3, `collect_experiment_metrics`) built `time` with bare `datetime.fromisoformat()` (naive), while run-event metrics are UTC-aware. Secondary (pre-existing): SQL `since` cutoffs were built from local `datetime.now()` with `T` separator and string-compared against UTC `CURRENT_TIMESTAMP` rows, skewing the 24h window by the UTC offset.

## Fix
- `_to_utc()` helper; all four `fromisoformat` sites and every snapshot normalized to UTC-aware before sort.
- Routing cutoff = `datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")` (matches SQLite CURRENT_TIMESTAMP, verified writers llm_router.py:306,320,332, query-router.sh:56); experiments cutoff = UTC isoformat (matches autoresearch.py:88).
- `compute_trend` Postgres `since` unchanged (out of scope).

## Validation
- `scripts/testing/test-trend-database-tz.py`: PASS under TZ=America/Los_Angeles and TZ=UTC; FAILS on original code with the production TypeError.
- `test-run-event-metrics.py`: All tests passed. py_compile clean.
- Live read-only: `collect_all_metrics(24)` against live DBs completed, all times UTC-aware.

## Review
Independent claude-sonnet reviewer: PASS_WITH_FOLLOWUPS -> followup (cutoff skew) folded -> PASS. Subject sha256 08a8596968126c7d37f0814dc0dbcfcb091c42b9fc9c47a944d5de6a83b412cd.

## Activation (Rule 15)
Integrated/ON: existing hourly timer `ai-autonomous-improvement.timer` runs this code from the primary checkout path; takes effect once the primary checkout carries main with this fix (no rebuild). Observable: unit state + tier0 QA 0.1.2. Intervenable: timer. PM-tracked: issues-backlog AUTONOMOUS-IMPROVEMENT entry (bug fix, no plan tracker).
