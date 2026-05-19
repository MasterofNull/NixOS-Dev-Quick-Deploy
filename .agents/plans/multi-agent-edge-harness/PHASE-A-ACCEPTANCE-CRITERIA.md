# Phase A Acceptance Criteria (AM-C5 — Normative Gates)

> All items below are PASS/FAIL gates. Phase A is not complete until all pass.
> Source: Codex sign-off amendment AM-C5 + COMBINED-PRD.md §5.
> Run against: http://127.0.0.1:8889/api/models (dashboard API)

## Gate 1 — Model Catalog Load
- [ ] `GET /api/models` returns HTTP 200
- [ ] Response contains `models` array with ≥1 entry
- [ ] Every entry has fields: `id`, `name`, `state`, `quant_tier`, `ram_estimate_gb`, `swap_sla_tier`, `audit_log`
- [ ] At least one model has `state: "available"` or `state: "active"`

## Gate 2 — Full State Machine (AM-C4)
- [ ] `ModelState` enum contains all 10 states: available, downloading, downloaded, verified, warming, candidate, active, retiring, archived, failed
- [ ] Invalid transitions raise `ValueError` (e.g., available → active directly is rejected)
- [ ] `audit_log` array is populated on every state transition
- [ ] `audit_log` entries contain: `ts`, `from`, `to` fields

## Gate 3 — Download + Progress SSE
- [ ] `POST /api/models/{id}/download` returns `{"status": "download_started", "model_id": "..."}` for an available model
- [ ] `GET /api/models/{id}/download/stream` returns `Content-Type: text/event-stream`
- [ ] SSE stream emits `event: progress` events with `bytes_done`, `total`, `pct` fields
- [ ] SSE stream emits `event: done` on completion/failure
- [ ] Model state transitions: `available → downloading → downloaded → verified`
- [ ] Duplicate download request on already-downloading model returns 409

## Gate 4 — Promote / Hot-Swap
- [ ] `POST /api/models/{id}/promote` on non-VERIFIED model returns HTTP 409
- [ ] `POST /api/models/{id}/promote` on VERIFIED model triggers state: `verified → warming → candidate → active`
- [ ] Response includes: `success`, `duration_s`, `sla_tier`, `sla_met`, `message`
- [ ] `swap_sla_tier` value from catalog entry is used for SLA measurement
- [ ] `GET /api/models/{id}/promote/stream` emits phase events: `starting`, `symlink_update`, `done`

## Gate 5 — SLA Tier Measurement (AM-G1)
- [ ] `swap_sla_tier` field present in every catalog entry (`gpu_fast` or `cpu_fallback`)
- [ ] `sla_met: true` when `duration_s ≤ 5.0` and tier is `gpu_fast`
- [ ] `sla_met: true` when `duration_s ≤ 30.0` and tier is `cpu_fallback`
- [ ] `sla_met: false` emitted as structured event when budget exceeded (not a silent miss)

## Gate 6 — Rollback
- [ ] Previous active model transitions to `retiring → archived` on successful promote
- [ ] If health check fails, new model goes to `failed`, previous active restored to `active`
- [ ] `POST /api/models/{id}/rollback` on `archived` model re-promotes it
- [ ] Rollback on non-archived/non-verified model returns HTTP 409

## Gate 7 — CPU-Fallback Queue Buffer (AM-C4)
- [ ] During swap window, llama.cpp health returns non-200 for up to 30s
- [ ] Dashboard "Hot-Swap" button shows swap progress bar during this window
- [ ] SSE stream continues emitting keep-alives during health polling
- [ ] After swap completes, `sla_met` reflects actual measured duration

## Gate 8 — Audit Event Emission
- [ ] Every state transition appends to `audit_log`
- [ ] `audit_log` is persisted to `/var/lib/ai-stack/hybrid/model-registry.json`
- [ ] Registry survives process restart (load from JSON on startup)
- [ ] `audit_log` capped at 50 entries (oldest trimmed)

## Gate 9 — Auth (AM-C2)
- [ ] Requests from loopback (127.0.0.1) are accepted without X-API-Key
- [ ] Requests from non-loopback without X-API-Key return HTTP 403
- [ ] Requests from non-loopback with valid X-API-Key return 200

## Gate 10 — Dashboard Panel
- [ ] `section-model-lifecycle` panel visible in dashboard at http://127.0.0.1:8889
- [ ] Catalog table renders all models with state badges matching 10-state machine
- [ ] "Download" button appears for `available`/`failed` models
- [ ] "Hot-Swap" button appears for `verified` models only
- [ ] "Rollback" button appears for `archived` models
- [ ] Active model name + SLA tier + last swap duration shown in header
- [ ] Panel auto-refreshes every 20 seconds

---

## Running the Gates

```bash
# Manual smoke test (requires model in 'verified' state)
BASE=http://127.0.0.1:8889

# Gate 1
curl -s $BASE/api/models | python3 -m json.tool | grep -E '"state"|"id"'

# Gate 2 — state machine unit test
python3 -c "
import sys; sys.path.insert(0, 'ai-stack/mcp-servers/hybrid-coordinator')
from model_registry import ModelState
assert ModelState.AVAILABLE.can_transition_to(ModelState.DOWNLOADING)
assert not ModelState.AVAILABLE.can_transition_to(ModelState.ACTIVE)
print('State machine: OK')
"

# Gate 3 — trigger download (replace MODEL_ID)
curl -s -X POST $BASE/api/models/qwen3-4b/download
curl -s "$BASE/api/models/qwen3-4b/download/stream" | head -5

# Gate 9 — auth check
curl -s -o /dev/null -w "%{http_code}" http://1.2.3.4:8889/api/models  # should be unreachable externally
```

---
*Gates authored from Codex AM-C5 + PLAN-SIGNOFF.md · 2026-05-19*
