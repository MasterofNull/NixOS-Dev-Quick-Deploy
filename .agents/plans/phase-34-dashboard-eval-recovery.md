# Phase 34 — Dashboard Layer Health + Eval Recovery

**ID:** PLAN-PHASE-34
**Date:** 2026-05-13
**Owner:** hyperd
**Objective:** Wire the aq-qa layers{} JSON into the Command Center Dashboard,
fix the broken aq-report → metrics pipeline, and recover eval score above threshold.

---

## Context

PRSI queue reports system **degraded**:
- `eval_latest_below_threshold: 50.0 < 60.0` — promptfoo eval at 50%, threshold 60%
- `cache_hit_below_threshold: 0.0 < 50.0` — stale signal from 2026-03-04 (embedding cache now 96%)

Dashboard `/api/metrics` shows:
- `eval_latest_pct: null` — eval data not flowing to dashboard
- `aq_report: false` — aq-report availability broken

PLAN-2026-05-13-QA Phase 3 explicitly called for a "Command Center Dashboard Layer Health
visualization" fed by the `layers{}` JSON. That JSON is now produced; the endpoint is missing.

---

## Slices

### 34.1 — Dashboard `/api/health/layered` endpoint
**What:** Add `GET /api/health/layered` to `dashboard/backend/api/routes/health.py`.
The route runs `aq-qa 0 --json` as a subprocess and returns the `layers{}` structure
plus `degraded_confidence`, `passed`, `failed`, `skipped`, `duration_s`.

**Acceptance:**
- `curl http://127.0.0.1:8889/api/health/layered` returns 200 JSON with `layers` key
- Response includes `degraded_confidence` bool
- Timeout 60s (aq-qa phase 0 runs ~25s)
- Caches result 30s to avoid hammering aq-qa on every dashboard refresh

### 34.2 — Fix aq-report → dashboard metrics pipeline
**What:** Dashboard `/api/metrics` shows `aq_report: false`. Locate the metrics
collector that sources aq-report data (`api/services/metrics_collector.py`), find the
breakage (likely subprocess path or output format mismatch post-harness refactor),
fix it so `eval_latest_pct` and `hint_adoption_pct` populate.

**Acceptance:**
- `curl http://127.0.0.1:8889/api/metrics` returns non-null `eval_latest_pct`
- `aq_report: true` in availability section

### 34.3 — Eval run + threshold recovery
**What:** Run `scripts/automation/run-eval.sh` to get a fresh baseline. Diagnose
which prompts are failing (promptfoo output). Fix either the eval config or the
underlying inference issues driving the 50% score. Target ≥ 70% (the script's
own acceptance threshold).

**Acceptance:**
- `run-eval.sh` exits 0 (score ≥ 70%)
- PRSI `eval_latest_below_threshold` degradation clears on next cycle

---

## Slice Order

34.1 → 34.2 → 34.3

## Validation (each slice)
```bash
scripts/governance/tier0-validation-gate.sh --pre-commit
python3 -m py_compile <changed .py files>
aq-qa 0
```

## Rollback
- 34.1: Remove the `/health/layered` route — no state change to other services
- 34.2: Revert metrics_collector.py — falls back to `aq_report: false` (current state)
- 34.3: Eval config changes are git-tracked; revert if score regresses

**Status:** IN PROGRESS — 34.1 next
**Owner:** Claude Sonnet 4.6
