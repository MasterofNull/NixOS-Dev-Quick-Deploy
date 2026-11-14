# Health-alert recovery: design acceptance and implementation boundary

## Frozen design provenance

`DESIGN.md` is a byte-exact copy of the accepted design, SHA256
`3b2e607c106f2f8fe1d5c1fa3a3a4eb4e4da74c8aaddbf6b48681a5c06ac1b65`. It was re-reviewed
PLAN_READY_WITH_FOLLOWUPS by Simurg@claude/sonnet (author lane codex) because the originally reviewed bytes
(`e1dcc399...fd552`) were lost from /tmp; the persisted copy only adds a provenance header and STATUS line. Gemini
(`ciflmn`) and Claude (`4mzeac`) accepted the original claims. This records provenance only; it is not an
implementation review or activation attestation.

## Delivered boundary

Scope is one producer/key: source `ai-stack-health-monitor`, dedup key `qa-phase-0`. No Nix, service or timer change.

- Queue: raw `dedup_key` and `observation_generation` persisted; every scoped failure observation (including a
  content-identical dedup push) increments the generation under the queue lock.
- `snapshot_recovery_candidate()` (locked, legacy migration only on exactly one exact-identity candidate) and
  `retire_recovered()` (lock-held exact id/source/key/pending/generation compare, archive as `recovered`, mirror
  snapshot refreshed). `last_machine_recovery()` scans the newest 200 archive records.
- Monitor: snapshot before the probe; `is_complete_clean_phase0_result` is the single clean predicate;
  `_monitor_returncode` is assigned from the real subprocess result.
- API `last_machine_recovery` (null or exactly four fields); dashboard "Recent recovery" row; QA 86.1/86.7/86.8.

## Review followups folded in

1. Generation increment persists on the unchanged-dedup branch inside the same lock; mirror snapshot written on retirement.
2. Freshness and SKIP outcomes keep the alert pending (fail closed). Phase 0 emits SKIP results on hosts lacking
   some dependencies, so a clean retirement needs a run with zero skips; this is intended and reported honestly.
3. Consumer audit of the `recovered` archive status: `get_all`/`aq-alerts` read only the active queue (recovered
   rows never enter it); `aq-approve` acts only on `pending`; `aq-system-state` counts `pending` and `auto_ok`
   only; `aq-pm-tracker` requires `approved`. No consumer change needed; existing counts are unchanged.
4. The design note's `gc()` is `_gc_expired` in source (cosmetic).

## Known limitation

`scripts/testing/test-dashboard-qa-provider-probe.py::test_dashboard_html_has_exactly_six_probe_rows` fails on
origin/main before this slice (card row count drift in the dashboard HTML); it is unrelated and not changed here.
