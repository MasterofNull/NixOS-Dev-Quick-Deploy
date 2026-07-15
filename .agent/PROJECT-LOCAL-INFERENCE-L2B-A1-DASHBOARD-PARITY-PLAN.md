# Local Inference L2B-A.1 Dashboard Parity Follow-up

Status: **ACCEPTED — COMMITTED `66391367`**
Parent: `.agent/PROJECT-LOCAL-INFERENCE-L2B-A-PLAN.md`
Trigger: accepted L2B-A module reports `source_shape_parity` and `actual_ssot_parity`, but the web
dashboard sanitizer/card drops both fields.

## Outcome

The Command Center preserves, sanitizes, and visibly renders all four accepted shadow-transport
parity dimensions: payload, stream, executable source shape, and actual SSOT. No transport,
inference, routing, lifecycle, policy, schema, or service behavior changes.

## Exact inventory

1. `.agent/PROJECT-LOCAL-INFERENCE-L2B-A1-DASHBOARD-PARITY-PLAN.md`
2. `dashboard/backend/api/routes/aistack.py`
3. `assets/dashboard.js`
4. `scripts/testing/test-local-inference-l2b.py`

No other file is permitted.

## Requirements

- Backend default and sanitizer include `source_shape_parity` and `actual_ssot_parity` with only
  `pass|fail|unavailable` values.
- A healthy projection requires all four parity values to be `pass`; a missing, malformed, or failed
  value degrades with the existing stable reason code and exposes no exception text.
- The card shows all four dimensions without raw prompts, source predicates, paths, headers, output,
  environment values, or secrets.
- Focused tests prove direct health → sanitizer → card contract preservation and adversarially mutate
  each new field to missing/unknown/fail.
- Existing async offload/cache behavior remains unchanged; no network call or deployment occurs.

## Validation

```bash
python3 scripts/testing/test-local-inference-l2b.py
python3 -m py_compile dashboard/backend/api/routes/aistack.py
node --check assets/dashboard.js
scripts/governance/tier0-validation-gate.sh --pre-commit
```

## Stop conditions

Stop for any fifth file, transport/module/policy/schema edit, live request, new endpoint, inference
change, lifecycle/store work, prompt/path exposure, async event-loop blocking, or need to reinterpret
the accepted parity semantics.
