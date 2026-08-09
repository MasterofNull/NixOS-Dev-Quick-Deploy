---
doc_type: reference
title: Autonomous-improvement metric-sync + deviation resilience
source: ai-stack/autonomous-improvement/trend_database.py
tags: [autonomous-improvement, metric-sync, trend-database, deviation, schema-drift]
---

# Autonomous-improvement metric-sync + deviation resilience

Status: active
Owner: AI Stack Maintainers
Last Updated: 2026-08-08

## Symptom
`ai-autonomous-improvement.service` failed on every run (and failed `nixos-rebuild switch` with exit 4):

```
❌ Metric sync failed: no such column: timestamp
sqlite3.OperationalError: no such column: timestamp
... workflow_deviation_io.DeviationWriteError: deviation-target-unsafe
RuntimeError: metric-sync-failed-and-deviation-receipt-unavailable
```

## Root cause (two distinct producer bugs)
1. **Primary — schema drift.** `trend_database.py`'s experiment collector queried
   `SELECT timestamp ... FROM experiments`, but `ai-stack/autoresearch/experiments.sqlite`'s `experiments`
   table records creation time as **`created_at`**, not `timestamp`. Unlike the `routing_log` collector
   (which guards a missing source), the experiments collector only checked the file exists, not the schema.
   This crashed the metric-sync pipeline every cycle.
2. **Secondary — deviation target.** On metric-sync failure the loop writes a deviation receipt to
   `AQ_WORKFLOW_DEVIATION_LOG_PATH`, previously the shared `/var/lib/ai-stack/hybrid/telemetry/`
   (ai-hybrid-owned, `0770` group-writable). `workflow_deviation_io._open_locked` correctly rejects a
   non-owner / group-writable dir (`deviation-target-unsafe`), so the hyperd-run service could not even
   record the deviation — turning a recoverable observation failure into a hard crash.

## Fix
- `trend_database.py`: query `created_at` (the real column) and add a schema-drift guard — if the
  expected columns are absent, skip that source gracefully instead of crashing the whole cycle.
- `autonomous-improvement.nix`: point `AQ_WORKFLOW_DEVIATION_LOG_PATH` at a service-private dir
  (`${dataDir}/deviations/…`) created by tmpfiles as `hyperd:users 0750` (owner-only writable), so the
  fail-loud deviation path passes the safety check and actually records.

## Validation
Corrected query runs against the live `experiments.sqlite` (no more `no such column`); `routing_decisions`
queries were always valid. Nix parses + the new deviation path evals in `.#hyperd-ai-dev`. Full service
success confirms on the next rebuild / timer run.

## Note
An improvement loop that cannot observe metrics should degrade (skip the cycle, record a deviation), never
crash the system or a rebuild. The schema-drift guard generalizes that resilience to any single source.
