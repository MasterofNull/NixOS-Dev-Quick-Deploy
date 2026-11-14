# FREEZE

PLAN_READY_WITH_FOLLOWUPS, owner approved MVP 2026-11-13 (asked in CLI).

## Seats
- gemini (author): APPROVED
- claude architecture: CONCERNS
- claude KISS/failure-modes: CONCERNS
- local seat local-20261113-184833-6db4tv: pending at freeze; admissible late
- codex: unavailable (session window closed); recorded, not substituted

## Frozen MVP
- S1: aq-context-packet v0
- S2: aq-land runs tier0 on touched scope before review
- S3: delegate-to-local power/thermal gate (AC or battery>=50%, 5-min loadavg with hysteresis enter 0.70*ncpu exit 0.55*ncpu, CPU temp<80C; unreadable sensor = defer, never drop)
- S4: append-only receipt JSONL with real token counts + post-redaction scan-or-quarantine + `aq-scoreboard` CLI with raw counts

## Deferred
F3 system1 router/trajectory distillation, F4 reciprocity, dashboard card, quota arbitrage, unmeasured KPIs (sub-20ms, vw_per_kt).
Exemplar budget (if ever added) counts inside the 2,500 cap.
